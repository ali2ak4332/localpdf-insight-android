import os
from pathlib import Path

import fitz


def _make_pdf(path: Path, pages: list[str]):
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_pdf_extract_and_library_search(tmp_path, monkeypatch):
    # core reads LOCALAPPDATA at import time; isolate app state before import.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "state"))
    import importlib
    import localpdf_insight.core as core
    core = importlib.reload(core)

    a = tmp_path / "alpha.pdf"
    b = tmp_path / "beta.pdf"
    _make_pdf(a, ["Alpha turbine efficiency improved to 61 percent in 2026."])
    _make_pdf(b, ["Beta retail occupancy reached 94 percent in 2025."])

    engine = core.PDFEngine()
    engine.open(str(a))
    pages = engine.extract()
    assert pages and "turbine" in pages[0].text.lower()
    engine.close()

    store = core.LibraryStore()
    assert store.add_paths([str(a), str(b)]) == 2
    assert store.add_paths([str(a)]) == 0

    index = core.HybridIndex(store)
    for item in list(store.items):
        assert index.index_path(item)

    results = index.text_search("turbine efficiency", top_k=3)
    assert results
    assert results[0]["item"].name == "alpha.pdf"
    assert results[0]["page"] == 1


def test_content_duplicate_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "state2"))
    import importlib, shutil
    import localpdf_insight.core as core
    core = importlib.reload(core)

    a = tmp_path / "original.pdf"
    copy = tmp_path / "copy.pdf"
    _make_pdf(a, ["Same contents"])
    shutil.copyfile(a, copy)

    store = core.LibraryStore()
    assert store.add_paths([str(a)]) == 1
    assert store.add_paths([str(copy)]) == 0
