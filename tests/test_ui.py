import importlib
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "state"))
    import localpdf_insight.core as core
    importlib.reload(core)
    import localpdf_insight.ui as ui
    importlib.reload(ui)
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "settings"))
    errors = []
    monkeypatch.setattr(ui.QMessageBox, "critical", lambda *args: errors.append(args[-1]))
    monkeypatch.setattr(ui.QMessageBox, "warning", lambda *args: errors.append(args[-1]))
    monkeypatch.setattr(ui.QMessageBox, "information", lambda *args: None)
    win = ui.MainWindow()
    win.show()
    app.processEvents()
    yield win, ui, errors
    win.close()
    app.processEvents()


def wait_for(condition, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if condition():
            return
        QTest.qWait(20)
    pytest.fail("Timed out waiting for the application")


def make_pdf(path, label):
    with fitz.open() as doc:
        for n in range(2):
            doc.new_page().insert_text((72, 72), f"{label} turbine report page {n+1}. Revenue AED 125,000 grew by 15%.")
        doc.save(path)
    return str(path)


def test_real_viewer_index_extract_export_and_sources(window, tmp_path, monkeypatch):
    win, ui, errors = window
    pdf = make_pdf(tmp_path / "report.pdf", "Alpha")
    monkeypatch.setattr(ui.QFileDialog, "getOpenFileNames", lambda *a: ([pdf], ""))
    QTest.mouseClick(win.add_btn, Qt.LeftButton)
    assert win._index_job is not None
    job = win._index_job
    win.index_library()
    assert win._index_job is job  # duplicate indexing is blocked
    assert not win.add_btn.isEnabled()
    win.open_pdf_path(pdf)
    win.change_page(1)
    assert win.page_label.text() == "Page 2 / 2"
    assert not win.viewer_image.pixmap().isNull()
    wait_for(lambda: win._index_job is None)
    assert win.add_btn.isEnabled()
    assert win.index.text_search("turbine turbine")
    win.extract_text()
    wait_for(lambda: win._extraction_job is None and "Alpha" in win.tools_output.toPlainText())
    assert len(win.engine.pages) == 2
    target = tmp_path / "export.txt"
    monkeypatch.setattr(ui.QFileDialog, "getSaveFileName", lambda *a: (str(target), ""))
    win.export_text()
    assert "Alpha" in target.read_text()
    target = tmp_path / "export.csv"
    win.export_csv()
    assert "Percentage" in target.read_text(encoding="utf-8-sig")
    evidence = win.index.text_search("turbine", top_k=1)
    win.last_evidence = evidence
    win._render_sources()
    win.open_evidence_page(0)
    assert win.current_page == evidence[0]["page"]-1
    assert not errors


def test_document_switch_cancels_old_extraction(window, tmp_path):
    win, ui, errors = window
    old = make_pdf(tmp_path / "old.pdf", "OldDocument")
    new = make_pdf(tmp_path / "new.pdf", "NewDocument")
    win.open_pdf_path(old)
    win.extract_text()
    old_job = win._extraction_job
    win.open_pdf_path(new)
    win.extract_text()
    wait_for(lambda: win._extraction_job is None and bool(win.engine.pages))
    assert "NewDocument" in win.tools_output.toPlainText()
    assert "OldDocument" not in win.tools_output.toPlainText()
    assert old_job not in win._jobs
    assert not errors


def test_closing_cleans_up_running_child(window, tmp_path):
    win, ui, errors = window
    win.open_pdf_path(make_pdf(tmp_path / "close.pdf", "Closing"))
    win.extract_text()
    job = win._extraction_job
    wait_for(lambda: job.process.pid is not None)
    win.close()
    assert job._stopped
    assert not win._jobs
    assert win.engine.doc is None
    assert not errors


def test_selected_model_persists(window, monkeypatch):
    win, ui, errors = window
    class Dialog:
        model = type("Input", (), {"text": lambda _: "custom-local-model"})()
        def __init__(self, *args):pass
        def exec(self):return ui.QDialog.Accepted
    monkeypatch.setattr(ui, "SettingsDialog", Dialog)
    win.open_settings()
    again = ui.MainWindow()
    try:
        assert again.model_name == "custom-local-model"
    finally:
        again.close()
