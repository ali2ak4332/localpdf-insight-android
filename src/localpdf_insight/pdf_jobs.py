"""PDF work runs in a spawned process, never in a Qt worker thread."""

from dataclasses import asdict


def run_pdf_job(connection, cancel, operation, payload):
    from .core import LibraryStore, HybridIndex, PDFEngine, local_llm_summary, extractive_summary, ollama_generate

    def progress(message):
        connection.send(("progress", message))

    try:
        if operation == "answer_library":
            progress("Searching your private library…")
            result = HybridIndex(LibraryStore()).answer(**payload)
        elif operation in ("summary", "answer_current"):
            from .evidence import answer as grounded_answer, query_tokens, tokens
            progress("Checking page evidence locally…")
            records = payload["records"]
            question = payload.get("question", "Summarize the document")
            terms = set(query_tokens(question))
            candidates = []
            for record in records:
                text = record["text"]
                for offset in range(0, len(text), 1800):
                    excerpt = text[offset:offset + 1800]
                    score = len(terms & set(tokens(excerpt)))
                    if score or operation == "summary":
                        candidates.append({"id": f"p{record['number']}-{offset}", "text": excerpt,
                                           "page": record['number'], "score": score})
            candidates = sorted(candidates, key=lambda c: c['score'], reverse=True)[:8]
            grounded = grounded_answer(question, candidates, strict=True, generate=ollama_generate,
                                       model=payload["model"], operation=operation)
            known = {c['id']: c for c in candidates}
            lines = [grounded['message']]
            if operation == "summary":
                lines.append("Summary uses selected excerpts; it is not an exhaustive document review.")
            for claim in grounded['claims']:
                labels = [f"{payload['document_name']} · p.{known[source_id]['page']}" for source_id in claim['source_ids']]
                lines.append(claim['text'] + "\n" + " / ".join(labels))
            result = "\n\n".join(lines)
        elif operation == "extract":
            engine = PDFEngine()
            try:
                engine.open(payload["path"])
                records = engine.extract(lambda done, total, message: progress(message))
                result = [asdict(record) for record in records]
            finally:
                engine.close()
        elif operation == "index":
            store = LibraryStore()
            index = HybridIndex(store)
            count, errors = 0, []
            for item_id in payload["ids"]:
                if cancel.is_set():
                    break
                item = store.get(item_id)
                if item is None:
                    continue
                try:
                    if not index.index_path(item, progress, cancel):
                        break
                    count += 1
                except Exception as exc:
                    errors.append(f"{item.name}: {exc}")
            result = (count, cancel.is_set(), errors)
        else:
            raise ValueError(f"Unknown PDF operation: {operation}")
        connection.send(("finished", result))
    except Exception as exc:
        connection.send(("error", str(exc)))
    finally:
        connection.close()
