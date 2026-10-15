import importlib
import io
import json
import threading
import urllib.error

import fitz
import pytest


@pytest.fixture
def core(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "state"))
    import localpdf_insight.core as module
    return importlib.reload(module)


def make_pdf(path, pages):
    with fitz.open() as doc:
        for text in pages:
            doc.new_page().insert_text((72, 72), text)
        doc.save(path)
    return path


def indexed(core, tmp_path):
    path = make_pdf(tmp_path / "report.pdf", [
        "Turbine efficiency increased substantially in the annual energy report.",
        "Retail occupancy reached 94 percent across all shopping centres.",
    ])
    store = core.LibraryStore()
    store.add_paths([str(path)])
    index = core.HybridIndex(store)
    index.index_path(store.items[0])
    return path, store, index


def test_repeated_query_words_keep_results(core, tmp_path):
    _, _, index = indexed(core, tmp_path)
    once = index.text_search("turbine efficiency")
    repeated = index.text_search("turbine turbine efficiency efficiency")
    assert repeated and repeated[0]["page"] == once[0]["page"] == 1
    assert repeated[0]["score"] == pytest.approx(once[0]["score"])


def test_missing_file_survives_reload_and_restores_search(core, tmp_path):
    path, _, _ = indexed(core, tmp_path)
    parked = path.with_suffix(".disconnected")
    path.rename(parked)
    store = core.LibraryStore()
    assert len(store.items) == 1
    index = core.HybridIndex(store)
    assert not index.is_indexed(store.items[0])
    assert index.text_search("turbine") == []
    store.save()
    parked.rename(path)
    restored = core.LibraryStore()
    assert core.HybridIndex(restored).text_search("turbine")[0]["page"] == 1


def test_changed_pdf_does_not_return_stale_evidence(core, tmp_path):
    path, store, index = indexed(core, tmp_path)
    path.unlink()
    make_pdf(path, ["Updated report contains only a new retail overview."])
    assert not index.is_indexed(store.items[0])
    assert index.text_search("turbine") == []
    assert store.refresh_changed_ids()
    index.index_path(store.items[0])
    assert index.text_search("retail")


def test_library_corruption_keeps_recovery_bytes(core):
    core.ensure_dirs()
    damaged = b'{"unfinished": '
    core.LIBRARY_FILE.write_bytes(damaged)
    store = core.LibraryStore()
    assert store.warnings
    assert next(core.APP_HOME.glob("library.recovery-*.json")).read_bytes() == damaged
    store.save()
    assert next(core.APP_HOME.glob("library.recovery-*.json")).read_bytes() == damaged


def test_invalid_pdf_does_not_close_current_document(core, tmp_path):
    valid = make_pdf(tmp_path / "valid.pdf", ["Original readable report remains open after the error."])
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"invalid pdf")
    engine = core.PDFEngine()
    engine.open(str(valid))
    with pytest.raises(Exception):
        engine.open(str(broken))
    assert engine.path == valid and engine.page_count == 1
    assert engine.render_page(0).width > 0
    engine.close()


def test_cancel_on_final_page_never_marks_index_complete(core, tmp_path):
    path = make_pdf(tmp_path / "cancel.pdf", ["Enough native PDF text to exercise last page cancellation."])
    store = core.LibraryStore()
    store.add_paths([str(path)])
    index = core.HybridIndex(store)
    cancel = threading.Event()
    assert not index.index_path(store.items[0], lambda _: cancel.set(), cancel)
    assert not index.is_indexed(store.items[0])
    assert index.index_path(store.items[0])


def test_visual_ranking_tracks_actual_images(core, tmp_path, monkeypatch):
    _, store, index = indexed(core, tmp_path)
    item = store.items[0]
    candidates = [{"item": item, "page": n, "score": 10-n, "snippet": "evidence"} for n in [1, 2]]
    index.page_image_path(item, 1).unlink()
    calls = []
    def generate(prompt, model, images, timeout):
        calls.append(images)
        return "1"
    monkeypatch.setattr(core, "ollama_generate", generate)
    assert index.visual_rerank("report", candidates, "vision")[0]["page"] == 2
    assert len(calls[0]) == 1
    index.page_image_path(item, 2).unlink()
    assert index.visual_rerank("report", candidates, "vision", max_pages=1) == candidates


def test_chatty_visual_ranking_does_not_parse_page_numbers(core, tmp_path, monkeypatch):
    _, store, index = indexed(core, tmp_path)
    candidates = [{"item": store.items[0], "page": n} for n in [1, 2]]
    monkeypatch.setattr(core, "ollama_generate", lambda *a, **kw: "The 2 reports are useful in 2026.")
    assert index.visual_rerank("report", candidates, "vision") == candidates


@pytest.mark.parametrize("failure,expected", [
    (TimeoutError("slow"), "timed out"),
    (urllib.error.HTTPError("http://127.0.0.1:11434", 404, "missing", {}, io.BytesIO()), "was not found"),
    (ValueError("bad json"), "invalid response"),
])
def test_ollama_errors_are_actionable(core, monkeypatch, failure, expected):
    class Opener:
        def open(self, *args, **kwargs):
            raise failure
    monkeypatch.setattr(core.urllib.request, "build_opener", lambda *a: Opener())
    with pytest.raises(RuntimeError, match=expected):
        core.ollama_generate("question", "missing-model")


def test_ollama_disables_proxies_and_redirects(core, monkeypatch):
    captured = []
    def build(*handlers):
        captured.extend(handlers)
        class Opener:
            def open(self, request, timeout):
                assert request.full_url == core.OLLAMA_GENERATE_URL
                return io.BytesIO(json.dumps({"response": "Valid local answer"}).encode())
        return Opener()
    monkeypatch.setattr(core.urllib.request, "build_opener", build)
    assert core.ollama_generate("question", "model") == "Valid local answer"
    assert captured[0].proxies == {}
    with pytest.raises(RuntimeError, match="redirect"):
        captured[1].redirect_request(None, None, 302, "", {}, "https://external.invalid")


def test_legacy_identity_stable_and_evidence_has_revision(core, tmp_path):
    path,store,index=indexed(core,tmp_path)
    original_id=store.items[0].id
    evidence=index.text_search('turbine')[0]
    assert len(evidence['source_revision'])==64
    path.unlink();make_pdf(path,['A changed contract with updated turbine specifications.'])
    store.refresh_changed_ids()
    assert store.items[0].id==original_id
    assert evidence['source_revision']!=core.content_signature(path)


def test_evidence_generation_requests_bounded_json_and_reports_truncation(core, monkeypatch):
    captured=[]
    class Opener:
        def open(self, request, timeout):
            captured.append(json.loads(request.data))
            return io.BytesIO(json.dumps({'response':'{"claims":', 'done_reason':'length'}).encode())
    monkeypatch.setattr(core.urllib.request,'build_opener',lambda *args:Opener())
    with pytest.raises(RuntimeError,match='output limit'):
        core.ollama_generate('question','model',json_output=True)
    assert captured[0]['format']=='json'
    assert captured[0]['options']['num_predict']==1024
    assert captured[0]['options']['temperature']==0.1
