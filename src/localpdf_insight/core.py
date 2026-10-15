from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import socket
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

import fitz  # PyMuPDF
from PIL import Image

APP_NAME = "LocalPDF Insight"
OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = os.environ.get("LOCALPDF_MODEL", "gemma3:4b")
APP_HOME = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".localpdf_insight")) / "LocalPDF Insight"
LIBRARY_FILE = APP_HOME / "library.json"
CACHE_DIR = APP_HOME / "cache"
PAGE_CACHE_DIR = CACHE_DIR / "pages"
INDEX_CACHE_DIR = CACHE_DIR / "indexes"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for", "from",
    "had", "has", "have", "he", "her", "his", "i", "if", "in", "into", "is", "it",
    "its", "may", "more", "not", "of", "on", "or", "our", "she", "so", "such", "than",
    "that", "the", "their", "them", "there", "these", "they", "this", "to", "was", "we",
    "were", "will", "with", "would", "you", "your"
}


@dataclass
class PageRecord:
    number: int
    text: str
    used_ocr: bool = False


@dataclass
class LibraryItem:
    id: str
    path: str
    name: str
    size: int
    mtime_ns: int
    page_count: int = 0
    indexed_at: float = 0.0
    content_sig: str = ""


def ensure_dirs() -> None:
    for p in (APP_HOME, CACHE_DIR, PAGE_CACHE_DIR, INDEX_CACHE_DIR):
        p.mkdir(parents=True, exist_ok=True)


def sha_id(path: Path) -> str:
    raw = f"{path.resolve()}|{path.stat().st_size}|{path.stat().st_mtime_ns}".encode("utf-8", "ignore")
    return hashlib.sha256(raw).hexdigest()[:20]


def content_signature(path: Path, sample: int = 2_000_000) -> str:
    """Full-file content signature; `sample` is retained for API compatibility."""
    from .evidence import digest
    return digest(path)


def tokenize(text: str) -> list[str]:
    from .evidence import normalize
    text = normalize(text)
    return [t.lower() for t in re.findall(r"[\w'-]+", text, flags=re.UNICODE) if len(t) > 1 and t.lower() not in STOPWORDS]


def sentence_split(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in re.split(r"(?<=[.!?؟])\s+|(?<=:)\s+(?=[A-Z])", clean) if len(s.strip()) > 20]


def extractive_summary(text: str, max_sentences: int = 12) -> str:
    sentences = sentence_split(text)
    if not sentences:
        return "No readable text was extracted. Scanned PDFs may require Tesseract OCR."
    words = tokenize(text)
    freq = Counter(words)
    if not freq:
        return "\n\n".join(f"• {s}" for s in sentences[:max_sentences])
    max_freq = max(freq.values())
    weights = {w: n / max_freq for w, n in freq.items()}
    ranked: list[tuple[float, int, str]] = []
    for idx, sentence in enumerate(sentences):
        toks = tokenize(sentence)
        if 4 <= len(toks) <= 100:
            score = sum(weights.get(w, 0) for w in toks) / math.sqrt(len(toks))
            ranked.append((score, idx, sentence))
    chosen = sorted(sorted(ranked, reverse=True)[:max_sentences], key=lambda x: x[1])
    return "\n\n".join(f"• {s}" for _, _, s in chosen) if chosen else "\n\n".join(f"• {s}" for s in sentences[:max_sentences])


def chunk_text(text: str, size: int = 12000, overlap: int = 700) -> list[str]:
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += max(1, size - overlap)
    return chunks


def image_to_b64(image: Image.Image, max_side: int = 1600, quality: int = 82) -> str:
    img = image.copy().convert("RGB")
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


class _LocalOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("The local Ollama endpoint tried to redirect the request. Redirects are disabled.")


def ollama_generate(prompt: str, model: str, images: list[str] | None = None, timeout: int = 240,
                    json_output: bool = False) -> str:
    body: dict[str, object] = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
    if json_output:
        body["format"] = "json"
        body["options"]["num_predict"] = 1024
    if images:
        body["images"] = images
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(OLLAMA_GENERATE_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        # Ignore system proxy settings and redirects: document evidence stays on loopback.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _LocalOnlyRedirect())
        with opener.open(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            if data.get("error"):
                raise RuntimeError(f"Ollama: {data['error']}")
            if data.get("done_reason") == "length":
                raise RuntimeError("The local AI response reached its output limit. Try a narrower question.")
            answer = data.get("response")
            if not isinstance(answer, str) or not answer.strip():
                raise RuntimeError("Ollama returned an empty answer. Check the selected model in Settings.")
            return answer.strip()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(f"Ollama model '{model}' was not found. Download it in Ollama or select an installed model in Settings.") from exc
        raise RuntimeError(f"Ollama returned HTTP {exc.code}. Check that the selected model can run on this computer.") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeError("Ollama timed out. Try a smaller model or Fast search.") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Ollama is not reachable. Run SETUP_AND_RUN_WINDOWS.bat or start Ollama, then try again.") from exc
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("Ollama returned an invalid response. Restart Ollama and try again.") from exc


def local_llm_summary(text: str, model: str) -> str:
    chunks = chunk_text(text)
    partials = []
    for i, chunk in enumerate(chunks, 1):
        partials.append(ollama_generate(
            "Summarize this PDF excerpt accurately. Preserve names, dates, quantities, obligations, risks and conclusions. "
            "Do not invent facts. Preserve page markers where useful.\n\n"
            f"EXCERPT {i}/{len(chunks)}:\n{chunk}", model
        ))
    if len(partials) == 1:
        return partials[0]
    return ollama_generate(
        "Combine these partial summaries into one concise structured summary. Remove repetition and retain page references.\n\n" +
        "\n\n".join(partials), model
    )


def extract_entities(records: list[PageRecord]) -> list[dict[str, str]]:
    patterns = {
        "Date": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b",
        "Money": r"\b(?:AED|USD|EUR|GBP|SAR|\$|€|£)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|m|bn))?\b",
        "Percentage": r"(?<!\w)\d+(?:\.\d+)?\s?%(?!\w)",
        "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "Phone": r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)",
    }
    rows: list[dict[str, str]] = []
    seen = set()
    for p in records:
        for kind, pattern in patterns.items():
            for match in re.finditer(pattern, p.text, flags=re.IGNORECASE):
                value = match.group(0).strip()
                key = (p.number, kind, value.lower())
                if key in seen:
                    continue
                seen.add(key)
                left, right = max(0, match.start() - 70), min(len(p.text), match.end() + 100)
                rows.append({"page": str(p.number), "type": kind, "value": value,
                             "context": re.sub(r"\s+", " ", p.text[left:right]).strip()})
    return rows


class PDFEngine:
    def __init__(self) -> None:
        self.path: Path | None = None
        self.doc: fitz.Document | None = None
        self.pages: list[PageRecord] = []

    def open(self, path: str) -> None:
        # Validate the replacement before closing the PDF already being viewed.
        doc = fitz.open(path)
        if doc.needs_pass or not doc.is_pdf or not doc.page_count:
            doc.close()
            raise RuntimeError("Choose a non-empty, unlocked PDF. Password-protected PDFs must be unlocked first.")
        self.close()
        self.path = Path(path)
        self.doc = doc
        self.pages = []

    def close(self) -> None:
        if self.doc is not None:
            self.doc.close()
        self.doc, self.path, self.pages = None, None, []

    @property
    def page_count(self) -> int:
        return len(self.doc) if self.doc else 0

    def render_page(self, index: int, max_width: int = 900, max_height: int = 1100) -> Image.Image:
        if not self.doc:
            raise RuntimeError("No PDF is open")
        page = self.doc[index]
        rect = page.rect
        scale = min(max_width / rect.width, max_height / rect.height, 2.2)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def extract(self, progress: Callable[[int, int, str], None] | None = None) -> list[PageRecord]:
        if not self.doc:
            raise RuntimeError("No PDF is open")
        records, total = [], len(self.doc)
        for i, page in enumerate(self.doc):
            if progress:
                progress(i + 1, total, f"Extracting page {i + 1}/{total}")
            text = page.get_text("text", sort=True).strip()
            used_ocr = False
            if len(re.sub(r"\s+", "", text)) < 30:
                try:
                    tp = page.get_textpage_ocr(language="eng", dpi=220, full=True)
                    ocr_text = page.get_text("text", textpage=tp, sort=True).strip()
                    if len(ocr_text) > len(text):
                        text, used_ocr = ocr_text, True
                except Exception:
                    pass
            records.append(PageRecord(i + 1, text, used_ocr))
        self.pages = records
        return records

    def all_text(self, with_page_markers: bool = True) -> str:
        return "".join((f"\n\n--- Page {p.number} ---\n" if with_page_markers else "\n") + p.text for p in self.pages).strip()


class LibraryStore:
    def __init__(self) -> None:
        ensure_dirs()
        self.items: list[LibraryItem] = []
        self.warnings: list[str] = []
        self._lock = threading.RLock()
        self.load()

    def load(self) -> None:
        with self._lock:
            self.warnings = []
            self.items = []
            if not LIBRARY_FILE.exists():
                return
            try:
                raw = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
                if not isinstance(raw, list):
                    raise ValueError("Expected a list of documents")
            except (ValueError, UnicodeError):
                backup = LIBRARY_FILE.with_name(f"library.recovery-{time.time_ns()}.json")
                shutil.copy2(LIBRARY_FILE, backup)
                self.warnings.append(f"The library metadata was damaged. A recovery copy was saved to {backup}.")
                return
            known_fields = {f.name for f in __import__("dataclasses").fields(LibraryItem)}
            invalid = False
            for entry in raw:
                try:
                    item = LibraryItem(**{k: v for k, v in entry.items() if k in known_fields})
                    if not isinstance(item.path, str) or not item.path or not re.fullmatch(r"[a-f0-9]{20}", item.id):
                        raise ValueError("Invalid document metadata")
                    if not isinstance(item.name, str) or not all(isinstance(v, (int, float)) for v in (item.size, item.mtime_ns, item.page_count, item.indexed_at)):
                        raise ValueError("Invalid document fields")
                    # An unplugged drive must not make a library entry disappear.
                    self.items.append(item)
                except (AttributeError, TypeError, ValueError):
                    invalid = True
            if invalid:
                backup = LIBRARY_FILE.with_name(f"library.recovery-{time.time_ns()}.json")
                shutil.copy2(LIBRARY_FILE, backup)
                self.warnings.append(f"Some library entries could not be loaded. The original metadata is saved to {backup}.")

    def save(self) -> None:
        # Caller must hold self._lock. Write to a temp file and replace
        # atomically so a crash or overlapping writer can't corrupt library.json.
        ensure_dirs()
        tmp = LIBRARY_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps([asdict(x) for x in self.items], indent=2), encoding="utf-8")
        os.replace(tmp, LIBRARY_FILE)

    def add_paths(self, paths: Iterable[str]) -> int:
        with self._lock:
            existing_paths = {Path(x.path).resolve() for x in self.items}
            existing_sigs = set()
            upgraded = False
            for x in self.items:
                if len(x.content_sig) != 64:
                    try:
                        x.content_sig = content_signature(Path(x.path))
                        upgraded = True
                    except OSError:
                        pass
                if x.content_sig and Path(x.path).is_file():
                    existing_sigs.add(x.content_sig)
            if upgraded:
                self.save()
            added = 0
            for raw in paths:
                p = Path(raw)
                if not p.is_file() or p.suffix.lower() != ".pdf" or p.resolve() in existing_paths:
                    continue
                try:
                    sig = content_signature(p)
                except OSError:
                    sig = ""
                if sig and sig in existing_sigs:
                    continue  # same file content already in the library under another path
                st = p.stat()
                item = LibraryItem(sha_id(p), str(p.resolve()), p.name, st.st_size, st.st_mtime_ns, content_sig=sig)
                self.items.append(item)
                existing_paths.add(p.resolve())
                if sig:
                    existing_sigs.add(sig)
                added += 1
            self.save()
            return added

    def remove(self, item_id: str) -> None:
        with self._lock:
            self.items = [x for x in self.items if x.id != item_id]
            self.save()
        shutil.rmtree(INDEX_CACHE_DIR / item_id, ignore_errors=True)
        shutil.rmtree(PAGE_CACHE_DIR / item_id, ignore_errors=True)

    def get(self, item_id: str) -> LibraryItem | None:
        with self._lock:
            return next((x for x in self.items if x.id == item_id), None)

    def update_item(self, item_id: str, **fields: object) -> None:
        """Thread-safe field update + save, used by indexing workers so
        concurrent index_path() calls on different items don't race on
        library.json (each still takes the lock for its own brief update)."""
        with self._lock:
            item = next((x for x in self.items if x.id == item_id), None)
            if item is None:
                return
            for k, v in fields.items():
                setattr(item, k, v)
            self.save()

    def refresh_changed_ids(self) -> set[str]:
        with self._lock:
            changed = set()
            for item in self.items:
                p = Path(item.path)
                if not p.is_file():
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size != item.size or st.st_mtime_ns != item.mtime_ns:
                    old_id = item.id
                    item.size, item.mtime_ns = st.st_size, st.st_mtime_ns
                    # Keep document identity stable; invalidate the old content index only.
                    item.indexed_at = 0
                    item.page_count = 0
                    try:
                        item.content_sig = content_signature(p)
                    except OSError:
                        pass
                    changed.add(old_id)
            if changed:
                self.save()
            return changed


class HybridIndex:
    def __init__(self, store: LibraryStore) -> None:
        self.store = store

    def index_path(self, item: LibraryItem, progress: Callable[[str], None] | None = None,
                    cancel: threading.Event | None = None) -> bool:
        """Indexes one PDF. Returns False (without error) if `cancel` was set
        partway through, leaving any already-written pages.json untouched
        rather than saving a partial index as if it were complete."""
        p = Path(item.path)
        if not p.exists():
            raise RuntimeError(f"File not found: {p}")
        doc = fitz.open(p)
        if doc.needs_pass or not doc.is_pdf or not doc.page_count:
            doc.close()
            raise RuntimeError(f"{item.name}: choose a non-empty, unlocked PDF.")
        out_dir = INDEX_CACHE_DIR / item.id
        page_dir = PAGE_CACHE_DIR / item.id
        out_dir.mkdir(parents=True, exist_ok=True)
        page_dir.mkdir(parents=True, exist_ok=True)
        pages = []
        total = len(doc)
        try:
            for i, page in enumerate(doc):
                if cancel is not None and cancel.is_set():
                    return False
                if progress:
                    progress(f"{item.name}: page {i + 1}/{total}")
                text = page.get_text("text", sort=True).strip()
                used_ocr = False
                if len(re.sub(r"\s+", "", text)) < 30:
                    try:
                        tp = page.get_textpage_ocr(language="eng", dpi=200, full=True)
                        ocr_text = page.get_text("text", textpage=tp, sort=True).strip()
                        if len(ocr_text) > len(text):
                            text, used_ocr = ocr_text, True
                    except Exception:
                        pass
                # Low-resolution cached page is enough for retrieval/reranking and keeps disk use reasonable.
                img_path = page_dir / f"page_{i + 1:05d}.jpg"
                if not img_path.exists():
                    rect = page.rect
                    scale = min(1400 / max(rect.width, rect.height), 2.0)
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(img_path, "JPEG", quality=80, optimize=True)
                pages.append({"page": i + 1, "text": text, "used_ocr": used_ocr, "tokens": tokenize(text)})
        finally:
            doc.close()
        if cancel is not None and cancel.is_set():
            return False
        stat = p.stat()
        if (stat.st_size, stat.st_mtime_ns) != (item.size, item.mtime_ns):
            raise RuntimeError(f"{item.name} changed during indexing. Index it again.")
        pages_file = out_dir / "pages.json"
        tmp_file = out_dir / "pages.json.tmp"
        tmp_file.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_file, pages_file)
        self.store.update_item(item.id, page_count=total, indexed_at=time.time())
        return True

    def is_indexed(self, item: LibraryItem) -> bool:
        try:
            stat = Path(item.path).stat()
            return (stat.st_size, stat.st_mtime_ns) == (item.size, item.mtime_ns) and (INDEX_CACHE_DIR / item.id / "pages.json").exists() and item.indexed_at > 0
        except OSError:
            return False

    def load_pages(self, item: LibraryItem) -> list[dict]:
        f = INDEX_CACHE_DIR / item.id / "pages.json"
        if not f.exists():
            return []
        try:
            pages = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(pages, list) or not all(isinstance(p, dict) and isinstance(p.get("page"), int) and isinstance(p.get("text"), str) for p in pages):
                return []
            return pages
        except (OSError, ValueError):
            return []

    def text_search(self, query: str, top_k: int = 12, items: list[LibraryItem] | None = None) -> list[dict]:
        selected = items if items is not None else self.store.items
        qterms = list(dict.fromkeys(tokenize(query)))
        if not qterms:
            return []
        docs: list[tuple[LibraryItem, dict]] = []
        df = Counter()
        for item in selected:
            if not self.is_indexed(item):
                continue
            for page in self.load_pages(item):
                docs.append((item, page))
                unique = set(page.get("tokens") or tokenize(page.get("text", "")))
                for t in qterms:
                    if t in unique:
                        df[t] += 1
        if not docs:
            return []
        n_docs = len(docs)
        avgdl = sum(max(1, len(page.get("tokens", []))) for _, page in docs) / n_docs
        results = []
        revisions = {}
        for item, page in docs:
            toks = page.get("tokens") or tokenize(page.get("text", ""))
            tf = Counter(toks)
            dl = max(1, len(toks))
            score = 0.0
            for term in qterms:
                if tf[term] == 0:
                    continue
                idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
                k1, b = 1.5, 0.75
                score += idf * ((tf[term] * (k1 + 1)) / (tf[term] + k1 * (1 - b + b * dl / max(avgdl, 1))))
            if score > 0:
                text = page.get("text", "")
                sentences = sentence_split(text)
                ranked = sorted(sentences, key=lambda s: sum(s.lower().count(t) for t in qterms), reverse=True)
                snippet = " ".join(ranked[:4]) if ranked else re.sub(r"\s+", " ", text)[:1400]
                if item.id not in revisions:
                    revisions[item.id] = content_signature(Path(item.path))
                results.append({"item": item, "page": int(page["page"]), "score": score, "snippet": snippet, "source_revision": revisions[item.id]})
        return sorted(results, key=lambda r: r["score"], reverse=True)[:top_k]

    def page_image_path(self, item: LibraryItem, page: int) -> Path:
        return PAGE_CACHE_DIR / item.id / f"page_{page:05d}.jpg"

    def visual_rerank(self, question: str, candidates: list[dict], model: str, max_pages: int = 4) -> list[dict]:
        if not candidates:
            return []
        shortlist = candidates[:max_pages]
        images, labels, image_candidates = [], [], []
        for c in shortlist:
            p = self.page_image_path(c["item"], c["page"])
            if p.exists():
                images.append(base64.b64encode(p.read_bytes()).decode("ascii"))
                image_candidates.append(c)
                labels.append(f"Image {len(images)} = {c['item'].name}, page {c['page']}")
        if not images:
            return candidates
        prompt = (
            "You are reranking PDF pages for a question. Inspect every supplied page image, including tables, charts, diagrams and layout. "
            f"There are exactly {len(images)} images, numbered 1 to {len(images)}.\n"
            "Respond with NOTHING but those numbers, most relevant first, separated by commas — "
            "for example: 3,1,2\n"
            "No words, no explanation, no answer to the question itself.\n\n"
            f"QUESTION: {question}\n" + "\n".join(labels)
        )
        try:
            result = ollama_generate(prompt, model, images=images, timeout=180)
            # Prefer the first line that actually looks like a bare ranking
            # (e.g. "3,1,2"), so stray digits elsewhere in a chatty response
            # (page numbers, model names, etc.) can't scramble the order.
            ranking_line = next(
                (ln for ln in result.splitlines() if re.fullmatch(r"\s*\d+(\s*,\s*\d+)*\s*", ln)),
                None,
            )
            if ranking_line is None:
                return candidates
            order = [int(x) for x in re.findall(r"\d+", ranking_line)]
            reranked, seen = [], set()
            for n in order:
                if 1 <= n <= len(image_candidates) and n not in seen:
                    reranked.append(image_candidates[n - 1]); seen.add(n)
            ranked_keys = {(c["item"].id, c["page"]) for c in reranked}
            reranked.extend(c for c in candidates if (c["item"].id, c["page"]) not in ranked_keys)
            return reranked
        except Exception:
            return candidates

    def answer(self, question: str, model: str, mode: str = "Hybrid", top_k: int = 8,
               items: list[LibraryItem] | None = None) -> tuple[str, list[dict]]:
        # Compatibility adapter: model metadata is never rendered as an authoritative citation.
        from .evidence import answer as grounded_answer
        evidence = self.text_search(question, top_k=top_k, items=items)
        sources = [{"id": f"source-{n}", "text": c['snippet'], "heading": ""}
                   for n, c in enumerate(evidence)]
        result = grounded_answer(question, sources, strict=True, generate=ollama_generate, model=model)
        output = [result['message']]
        for claim in result['claims']:
            labels = []
            for source_id in claim['source_ids']:
                c = evidence[int(source_id.split('-')[1])]
                labels.append(f"{c['item'].name} · p.{c['page']}")
            output.append(claim['text'] + "\n" + " / ".join(labels))
        return "\n\n".join(output), evidence


# -----------------------------
