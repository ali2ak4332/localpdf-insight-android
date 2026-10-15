# LocalPDF Insight 0.1.1 — repair notes

Based on `LocalPDF_Insight_Project_M0.zip` (August 7, 2026), the most recent project archive located. Its README identifies it as the packaged successor to the earlier v2.2.1 prototype. Existing features and local library format are retained.

## Defects repaired

- Windows setup chose `py -3.12` without checking whether that runtime existed. It now probes supported 64-bit interpreters and reuses a valid existing environment.
- PowerShell could unwrap a one-element command array into a string; indexing it selected `p` rather than `python`. Executable and arguments now have separate named properties.
- The fallback Ollama executable was a FileInfo object but startup read its missing `Source` property. Setup now consistently uses an executable path.
- Failed AI setup blocked even ordinary PDF reading. It now reports the AI problem and opens the reader; a reader-only setup option avoids the model download.
- Background operations shared PyMuPDF state with the GUI. Processing now runs in spawned child processes, and results are delivered on the GUI thread.
- Switching PDFs during extraction could populate the new viewer's tools with old data. Old work is cancelled, document state is cleared and stale results are rejected.
- Duplicate indexing could start through Add PDFs and compete for the same cache. Indexing is guarded and library mutations are disabled until it settles. One bad PDF no longer stops the remaining batch.
- BM25 counted duplicate question terms repeatedly in document frequency. A one-page fixture returned one result for `turbine` and none for `turbine turbine` before the fix; both now retrieve the page with the same score.
- Visual reranking mapped image numbers to the wrong PDF when an earlier image was missing. It now maps only images actually supplied and keeps remaining candidates. Chatty non-ranking text no longer scrambles the order.
- Missing files were dropped when loading the library. They now remain listed as unavailable. Changed files do not contribute stale text evidence.
- Malformed library metadata could be silently overwritten after loading an empty library. Recovery now retains the original bytes in a dated backup and shows a message.
- Failed PDF opens closed the previously open document. Replacement documents are validated first.
- Cancellation on the final page could still publish a complete index. The final commit now rechecks cancellation and file identity.
- Ollama failures lacked useful distinctions. Timeouts, missing models and invalid responses now have specific messages. A text-only fallback is clearly labelled.
- The selected model reset each session; it is now persisted. Summary falls back to extracted sentences when AI is unavailable. Sidebar text backgrounds were also corrected.

## Validation

Run `python -m pip install -e ".[test]"`, then `python -m pytest` from the project directory.

The suite uses generated PDF fixtures and real spawned processes for desktop indexing/extraction. It checks rendering, navigation, text/CSV export, source-page jumps, document switching, child-process cleanup and saved settings, as well as backend regression cases. Ollama error/proxy/redirect tests use controlled local test doubles; they do not validate any model's answer quality.

Repair-environment test result: 18 tests passed (4.73 seconds), after successful editable package installation. Environment: Python 3.12, PyMuPDF 1.26.6, Pillow 11.3.0, PySide6 6.11.2, pytest 9.1.1; Linux, Qt offscreen. Windows installer execution and live Ollama inference remain unverified. Optional OCR and Arabic OCR quality were not tested. No Windows executable was built.

## Technical references

- [PyMuPDF multiprocessing guidance](https://pymupdf.readthedocs.io/en/latest/recipes-multiprocessing.html) documents unsupported multithreaded use and recommends process-based work.
- [Qt signals and slots](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/signals_and_slots.html) documents signal delivery and thread affinity.
- [PowerShell return behavior](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_return) explains collection enumeration on return.
- [Ollama Windows documentation](https://docs.ollama.com/windows) documents the local Windows installation and executable distribution.
