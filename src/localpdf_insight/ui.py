from __future__ import annotations

from .core import *
from .qt_jobs import PDFJob, Callbacks

# PySide6 desktop interface
# -----------------------------
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QSettings, QLockFile
from PySide6.QtGui import QAction, QFont, QImage, QPixmap, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSplitter, QStackedWidget, QStatusBar, QTextBrowser, QToolButton, QVBoxLayout, QWidget
)


class SettingsDialog(QDialog):
    def __init__(self, model: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI settings")
        self.setMinimumWidth(470)
        layout = QVBoxLayout(self)
        intro = QLabel("LocalPDF Insight uses Ollama on this computer. Most users can leave these settings unchanged.")
        intro.setWordWrap(True); intro.setObjectName("muted"); layout.addWidget(intro)
        form = QFormLayout()
        self.quality = QComboBox(); self.quality.addItems(["Balanced — Gemma 3 4B", "Advanced — custom Ollama model"])
        self.model = QLineEdit(model); self.model.setPlaceholderText("gemma3:4b")
        self.quality.setCurrentIndex(0 if model == "gemma3:4b" else 1)
        self.model.setEnabled(self.quality.currentIndex() == 1)
        def quality_changed(index):
            self.model.setEnabled(index == 1)
            if index == 0:self.model.setText("gemma3:4b")
        self.quality.currentIndexChanged.connect(quality_changed)
        form.addRow("AI quality", self.quality); form.addRow("Ollama model", self.model); layout.addLayout(form)
        note = QLabel("A vision-capable model is required for Deep search to inspect charts, tables and page layout.")
        note.setWordWrap(True); note.setObjectName("muted"); layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)


class SourceCard(QFrame):
    opened = Signal(int)
    def __init__(self, idx: int, evidence: dict, image_path: Path | None, parent=None):
        super().__init__(parent); self.idx = idx; self.setObjectName("sourceCard"); self.setCursor(Qt.PointingHandCursor)
        row = QHBoxLayout(self); row.setContentsMargins(12, 12, 12, 12); row.setSpacing(12)
        thumb = QLabel(); thumb.setFixedSize(92, 118); thumb.setAlignment(Qt.AlignCenter); thumb.setObjectName("thumbnail")
        if image_path and image_path.exists():
            pix = QPixmap(str(image_path))
            if not pix.isNull(): thumb.setPixmap(pix.scaled(88, 114, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        row.addWidget(thumb)
        body = QVBoxLayout(); title = QLabel(f"{evidence['item'].name}  ·  page {evidence['page']}")
        title.setObjectName("sourceTitle"); title.setWordWrap(True); body.addWidget(title)
        snippet = QLabel(evidence.get("snippet", "")[:420]); snippet.setWordWrap(True); snippet.setObjectName("muted"); snippet.setMaximumHeight(72); body.addWidget(snippet)
        open_btn = QPushButton("Open cited page"); open_btn.setObjectName("linkButton"); open_btn.clicked.connect(lambda: self.opened.emit(self.idx)); body.addWidget(open_btn, 0, Qt.AlignLeft)
        row.addLayout(body, 1)

    def mouseDoubleClickEvent(self, event):
        self.opened.emit(self.idx); super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    LARGE_INDEX_PAGE_WARNING = 1500
    def __init__(self):
        super().__init__(); ensure_dirs()
        self.engine = PDFEngine(); self.store = LibraryStore(); self.index = HybridIndex(self.store)
        self.settings = QSettings("LocalPDF Insight", "LocalPDF Insight")
        self.current_page = 0; self.entities = []; self.last_evidence = []
        self._jobs = set(); self._index_job = None; self._extraction_job = None; self._pending_extract = []
        self._chat_job = None; self._tool_job = None
        self._doc_generation = 0; self._tool_generation = 0; self._chat_generation = 0
        self.model_name = os.environ.get("LOCALPDF_MODEL") or self.settings.value("model", DEFAULT_MODEL, type=str)
        self.setWindowTitle(APP_NAME); self.resize(1440, 920); self.setMinimumSize(1080, 720)
        self._build_ui(); self._apply_style(); self.refresh_library(); QTimer.singleShot(250, self._first_run_hint)

    def _apply_style(self):
        self.setStyleSheet("""
            * { font-family: 'Segoe UI', Arial; font-size: 13px; }
            QMainWindow, QWidget { background: #f6f7f9; color: #1f2937; }
            QLabel { background: transparent; }
            #sidebar { background: #111827; border: 0; }
            #brand { color: white; font-size: 19px; font-weight: 700; }
            #brandSub { color: #9ca3af; font-size: 11px; }
            QToolButton#navButton { color: #d1d5db; background: transparent; border: 0; border-radius: 8px; padding: 11px 12px; text-align: left; }
            QToolButton#navButton:hover { background: #1f2937; color: white; }
            QToolButton#navButton:checked { background: #263244; color: white; font-weight: 600; }
            #pageTitle { font-size: 23px; font-weight: 700; color: #111827; }
            #pageSubtitle, #muted { color: #6b7280; }
            QPushButton { background: white; border: 1px solid #d7dce3; border-radius: 8px; padding: 8px 13px; }
            QPushButton:hover { background: #f9fafb; border-color: #b9c0ca; }
            QPushButton#primary { background: #111827; color: white; border-color: #111827; font-weight: 600; }
            QPushButton#primary:hover { background: #263244; }
            QPushButton#danger { color: #b42318; }
            QPushButton#linkButton { background: transparent; border: 0; color: #2563eb; padding: 2px 0; font-weight: 600; }
            QLineEdit, QComboBox { background: white; border: 1px solid #d7dce3; border-radius: 8px; padding: 9px 10px; min-height: 20px; }
            QTextBrowser { background: white; border: 1px solid #e1e5ea; border-radius: 12px; padding: 14px; selection-background-color: #cfe1ff; }
            QListWidget { background: white; border: 1px solid #e1e5ea; border-radius: 10px; }
            QListWidget::item { padding: 10px 8px; border-bottom: 1px solid #f0f1f3; }
            QListWidget::item:selected { background: #edf3ff; color: #111827; }
            QFrame#sourceCard { background: white; border: 1px solid #e1e5ea; border-radius: 10px; }
            QFrame#sourceCard:hover { border-color: #b8c3d4; }
            #sourceTitle { font-weight: 700; color: #111827; }
            #thumbnail { background: #eef0f3; border-radius: 6px; }
            QProgressBar { border: 0; background: #e9edf2; border-radius: 3px; max-height: 6px; }
            QProgressBar::chunk { background: #2563eb; border-radius: 3px; }
            QStatusBar { background: white; border-top: 1px solid #e5e7eb; color: #6b7280; }
            QSplitter::handle { background: transparent; width: 6px; }
        """)

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root); h = QHBoxLayout(root); h.setContentsMargins(0,0,0,0); h.setSpacing(0)
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(210)
        sv = QVBoxLayout(sidebar); sv.setContentsMargins(16,20,16,18); sv.setSpacing(8)
        brand=QLabel("LocalPDF Insight"); brand.setObjectName("brand"); sub=QLabel("Private document AI"); sub.setObjectName("brandSub")
        sv.addWidget(brand); sv.addWidget(sub); sv.addSpacing(18)
        self.nav_group=QButtonGroup(self); self.nav_group.setExclusive(True)
        for text,idx in [("Library",0),("Chat",1),("Viewer",2),("Tools",3)]:
            b=QToolButton(); b.setObjectName("navButton"); b.setText(text); b.setCheckable(True); b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.clicked.connect(lambda _=False,i=idx:self.pages.setCurrentIndex(i)); b.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); self.nav_group.addButton(b); sv.addWidget(b)
            if idx==0:b.setChecked(True)
        sv.addStretch(); settings=QToolButton(); settings.setObjectName("navButton"); settings.setText("Settings"); settings.clicked.connect(self.open_settings); settings.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); sv.addWidget(settings)
        privacy=QLabel("All document processing stays on this computer."); privacy.setWordWrap(True); privacy.setObjectName("brandSub"); sv.addWidget(privacy); h.addWidget(sidebar)
        self.pages=QStackedWidget(); h.addWidget(self.pages,1); self.pages.addWidget(self._library_page()); self.pages.addWidget(self._chat_page()); self.pages.addWidget(self._viewer_page()); self.pages.addWidget(self._tools_page())
        self.status=QStatusBar(); self.setStatusBar(self.status); self.status.showMessage("Ready — local processing only")
        act_add=QAction("Add PDFs",self); act_add.setShortcut(QKeySequence("Ctrl+O")); act_add.triggered.connect(self.add_library_files); self.addAction(act_add)
        act_find=QAction("Ask library",self); act_find.setShortcut(QKeySequence("Ctrl+K")); act_find.triggered.connect(self.focus_chat); self.addAction(act_find)

    def _page_header(self,title,subtitle):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(0,0,0,10); v.setSpacing(3); t=QLabel(title); t.setObjectName("pageTitle"); s=QLabel(subtitle); s.setObjectName("pageSubtitle"); s.setWordWrap(True); v.addWidget(t); v.addWidget(s); return w

    def _library_page(self):
        page=QWidget(); v=QVBoxLayout(page); v.setContentsMargins(28,24,28,24); v.setSpacing(14); v.addWidget(self._page_header("Document library","Add reports, manuals and PDFs once. LocalPDF Insight keeps a reusable private index on this computer."))
        bar=QHBoxLayout(); add=QPushButton("Add PDFs"); add.setObjectName("primary"); add.clicked.connect(self.add_library_files); self.index_btn=QPushButton("Index new documents"); self.index_btn.clicked.connect(self.index_library); self.cancel_btn=QPushButton("Cancel"); self.cancel_btn.setEnabled(False); self.cancel_btn.clicked.connect(self.cancel_indexing); remove=QPushButton("Remove"); remove.setObjectName("danger"); remove.clicked.connect(self.remove_library_item)
        self.add_btn = add; self.remove_btn = remove
        bar.addWidget(add); bar.addWidget(self.index_btn); bar.addWidget(self.cancel_btn); bar.addStretch(); bar.addWidget(remove); v.addLayout(bar)
        self.index_progress=QProgressBar(); self.index_progress.setTextVisible(False); self.index_progress.setRange(0,1); self.index_progress.setValue(0); v.addWidget(self.index_progress)
        self.library_list=QListWidget(); self.library_list.itemDoubleClicked.connect(lambda _item:self.open_selected_library_pdf()); v.addWidget(self.library_list,1)
        hint=QLabel("Tip: double-click a document to open it. Changed files are detected automatically and marked for re-indexing."); hint.setObjectName("muted"); v.addWidget(hint); return page

    def _chat_page(self):
        page=QWidget(); v=QVBoxLayout(page); v.setContentsMargins(28,24,28,24); v.setSpacing(14); v.addWidget(self._page_header("Ask your documents","Search across the whole library. Deep search can inspect the actual page pixels when a table, chart or layout matters."))
        qr=QHBoxLayout(); self.library_question=QLineEdit(); self.library_question.setPlaceholderText("Ask a question across your PDFs…"); self.library_question.returnPressed.connect(self.ask_library); self.search_mode=QComboBox(); self.search_mode.addItems(["Deep search","Fast search"]); self.search_mode.setFixedWidth(140); ask=QPushButton("Ask"); ask.setObjectName("primary"); ask.clicked.connect(self.ask_library); qr.addWidget(self.library_question,1); qr.addWidget(self.search_mode); qr.addWidget(ask); v.addLayout(qr)
        split=QSplitter(Qt.Horizontal); left=QWidget(); lv=QVBoxLayout(left); lv.setContentsMargins(0,0,4,0); lv.setSpacing(8); al=QLabel("Answer"); al.setObjectName("sourceTitle"); lv.addWidget(al); self.library_answer=QTextBrowser(); self.library_answer.setPlaceholderText("Your answer will appear here with page citations."); lv.addWidget(self.library_answer,1)
        right=QWidget(); rv=QVBoxLayout(right); rv.setContentsMargins(4,0,0,0); rv.setSpacing(8); sl=QLabel("Sources"); sl.setObjectName("sourceTitle"); rv.addWidget(sl); self.sources_scroll=QScrollArea(); self.sources_scroll.setWidgetResizable(True); self.sources_scroll.setFrameShape(QFrame.NoFrame); self.sources_host=QWidget(); self.sources_layout=QVBoxLayout(self.sources_host); self.sources_layout.setContentsMargins(0,0,0,0); self.sources_layout.setSpacing(8); self.sources_layout.addStretch(); self.sources_scroll.setWidget(self.sources_host); rv.addWidget(self.sources_scroll,1); split.addWidget(left); split.addWidget(right); split.setSizes([820,430]); v.addWidget(split,1); return page

    def _viewer_page(self):
        page=QWidget(); v=QVBoxLayout(page); v.setContentsMargins(28,24,28,24); v.setSpacing(12); top=QHBoxLayout(); title=QLabel("PDF viewer"); title.setObjectName("pageTitle"); top.addWidget(title); top.addStretch(); ob=QPushButton("Open PDF"); ob.clicked.connect(self.open_pdf); top.addWidget(ob); v.addLayout(top); nav=QHBoxLayout(); prev=QPushButton("Previous"); prev.clicked.connect(lambda:self.change_page(-1)); nxt=QPushButton("Next"); nxt.clicked.connect(lambda:self.change_page(1)); self.page_label=QLabel("Page 0 / 0"); self.page_label.setObjectName("muted"); nav.addWidget(prev); nav.addWidget(nxt); nav.addWidget(self.page_label); nav.addStretch(); v.addLayout(nav); self.viewer_scroll=QScrollArea(); self.viewer_scroll.setWidgetResizable(True); self.viewer_scroll.setAlignment(Qt.AlignCenter); self.viewer_image=QLabel("Open a PDF or a cited source page."); self.viewer_image.setAlignment(Qt.AlignCenter); self.viewer_image.setObjectName("muted"); self.viewer_scroll.setWidget(self.viewer_image); v.addWidget(self.viewer_scroll,1); return page

    def _tools_page(self):
        page=QWidget(); v=QVBoxLayout(page); v.setContentsMargins(28,24,28,24); v.setSpacing(12); v.addWidget(self._page_header("Current PDF tools","Extract text, create a summary, ask one document directly, or export detected dates, amounts and other structured values.")); actions=QHBoxLayout()
        for text,fn in [("Extract text",self.extract_text),("Summarize",self.summarize),("Ask current PDF",self.answer_current_pdf),("Export text",self.export_text),("Export data CSV",self.export_csv)]: b=QPushButton(text); b.clicked.connect(fn); actions.addWidget(b)
        actions.addStretch(); v.addLayout(actions); self.tool_question=QLineEdit(); self.tool_question.setPlaceholderText("Question for the currently open PDF…"); self.tool_question.returnPressed.connect(self.answer_current_pdf); v.addWidget(self.tool_question); self.tools_output=QTextBrowser(); self.tools_output.setPlaceholderText("Extracted text, summaries and answers appear here."); v.addWidget(self.tools_output,1); return page

    def _first_run_hint(self):
        if self.store.warnings:self.status.showMessage(" ".join(self.store.warnings))
        elif not self.store.items:self.status.showMessage("Start by adding one or more PDFs to your private library.")

    def run_job(self,operation,payload,done=None,error_cleanup=None):
        job=PDFJob(operation,payload,self)
        def onerr(msg):
            if error_cleanup:error_cleanup()
            self.status.showMessage("Operation failed"); QMessageBox.critical(self,APP_NAME,msg)
        callbacks=Callbacks(self.status.showMessage,done,onerr,job)
        job.progress.connect(callbacks.progress); job.finished.connect(callbacks.finished); job.error.connect(callbacks.error)
        def release():
            if self._chat_job is job:self._chat_job=None
            if self._tool_job is job:self._tool_job=None
            self._jobs.discard(job); job.deleteLater()
        callbacks.settled.connect(release); self._jobs.add(job)
        QTimer.singleShot(0,job.start)
        return job

    def stop_job(self,job):
        if job is not None:
            job.stop(); self._jobs.discard(job); job.deleteLater()

    def refresh_library(self):
        changed=self.store.refresh_changed_ids() if self._index_job is None else set()
        for old in changed: shutil.rmtree(INDEX_CACHE_DIR/old,ignore_errors=True); shutil.rmtree(PAGE_CACHE_DIR/old,ignore_errors=True)
        self.library_list.clear()
        for item in self.store.items:
            state="File unavailable" if not Path(item.path).is_file() else ("Ready" if self.index.is_indexed(item) else "Needs indexing"); pages=f" · {item.page_count} pages" if item.page_count else ""; li=QListWidgetItem(f"{item.name}\n{state}{pages}"); li.setData(Qt.UserRole,item.id); li.setSizeHint(QSize(0,58)); self.library_list.addItem(li)

    def selected_item(self):
        li=self.library_list.currentItem(); return self.store.get(li.data(Qt.UserRole)) if li else None

    def add_library_files(self):
        if self._index_job is not None:return
        paths,_=QFileDialog.getOpenFileNames(self,"Add PDFs","","PDF files (*.pdf)")
        if not paths:return
        n=self.store.add_paths(paths); self.refresh_library(); self.status.showMessage(f"Added {n} new PDF(s).")
        if n:self.index_library()

    def remove_library_item(self):
        if self._index_job is not None:return
        item=self.selected_item()
        if item and QMessageBox.question(self,APP_NAME,f"Remove {item.name} from the library?\n\nThe original PDF will not be deleted.")==QMessageBox.Yes:self.store.remove(item.id); self.refresh_library()

    def index_library(self,selected_only=False):
        if self._index_job is not None:return
        selected_id=self.selected_item().id if self.selected_item() else None
        self.refresh_library()
        if selected_only:
            for row in range(self.library_list.count()):
                if self.library_list.item(row).data(Qt.UserRole)==selected_id:self.library_list.setCurrentRow(row)
        items=[self.selected_item()] if selected_only else list(self.store.items); items=[x for x in items if x is not None and not self.index.is_indexed(x)]
        if not items: QMessageBox.information(self,APP_NAME,"Everything selected is already indexed."); return
        est=0
        for it in items:
            try:
                if it.page_count:est+=it.page_count
                else:
                    with fitz.open(it.path) as doc:est+=doc.page_count
            except Exception:pass
        if est>self.LARGE_INDEX_PAGE_WARNING and QMessageBox.question(self,APP_NAME,f"About {est:,} pages need first-time indexing. Continue?")!=QMessageBox.Yes:return
        self.cancel_btn.setEnabled(True); self.index_btn.setEnabled(False); self.add_btn.setEnabled(False); self.remove_btn.setEnabled(False); self.index_progress.setRange(0,0)
        def cleanup():
            self._index_job=None; self.store.load(); self.cancel_btn.setEnabled(False); self.index_btn.setEnabled(True); self.add_btn.setEnabled(True); self.remove_btn.setEnabled(True); self.index_progress.setRange(0,1); self.index_progress.setValue(0); self.refresh_library()
        def done(result):
            cleanup(); count,cancelled,errors=result
            self.status.showMessage(f"Indexing cancelled after {count} document(s)." if cancelled else f"Indexed {count} document(s); {len(errors)} failed.")
            if errors:QMessageBox.warning(self,APP_NAME,"Some PDFs could not be indexed:\n\n"+"\n".join(errors[:8]))
        self._index_job=self.run_job("index",{"ids":[item.id for item in items]},done,cleanup)

    def cancel_indexing(self):
        if self._index_job:self._index_job.cancel(); self.status.showMessage("Cancelling after the current page…")

    def focus_chat(self):
        self.pages.setCurrentIndex(1); self.library_question.setFocus()
        for b in self.nav_group.buttons():b.setChecked(b.text()=="Chat")

    def ask_library(self):
        q=self.library_question.text().strip()
        if not q:return
        if not any(self.index.is_indexed(x) for x in self.store.items):QMessageBox.information(self,APP_NAME,"Index the library first."); return
        self.stop_job(self._chat_job); self.last_evidence=[]
        self.library_answer.setPlainText("Reading the most relevant pages locally…"); self._clear_sources(); mode="Hybrid" if self.search_mode.currentText().startswith("Deep") else "Text"
        self._chat_generation+=1; generation=self._chat_generation
        def done(result):
            if generation!=self._chat_generation:return
            answer,evidence=result; self.last_evidence=evidence; self.library_answer.setPlainText(answer); self._render_sources(); self.status.showMessage("Answer complete")
        self._chat_job=self.run_job("answer_library",{"question":q,"model":self.model_name,"mode":mode},done)

    def _clear_sources(self):
        while self.sources_layout.count()>1:
            item=self.sources_layout.takeAt(0); w=item.widget()
            if w:w.deleteLater()

    def _render_sources(self):
        self._clear_sources()
        for i,e in enumerate(self.last_evidence):
            card=SourceCard(i,e,self.index.page_image_path(e['item'],e['page'])); card.opened.connect(self.open_evidence_page); self.sources_layout.insertWidget(self.sources_layout.count()-1,card)

    def open_evidence_page(self,idx):
        if 0<=idx<len(self.last_evidence):
            e=self.last_evidence[idx]
            try:
                if e.get('source_revision') != content_signature(Path(e['item'].path)):
                    QMessageBox.warning(self,APP_NAME,"This PDF changed after retrieval. Ask again before opening its citation."); return
            except OSError:
                QMessageBox.warning(self,APP_NAME,"The cited PDF is unavailable."); return
            self.open_pdf_path(e['item'].path,max(0,e['page']-1))

    def open_selected_library_pdf(self):
        item=self.selected_item()
        if item:self.open_pdf_path(item.path)

    def open_pdf(self):
        path,_=QFileDialog.getOpenFileName(self,"Open PDF","","PDF files (*.pdf)")
        if path:self.open_pdf_path(path)

    def open_pdf_path(self,path,page=0):
        try:
            self.engine.open(path); self._doc_generation+=1; self._tool_generation+=1
            self.stop_job(self._tool_job); self._tool_job=None
            if self._extraction_job:
                self.stop_job(self._extraction_job); self._extraction_job=None
            self._pending_extract=[]; self.entities=[]; self.tools_output.clear(); self.tool_question.clear()
            self.current_page=max(0,min(page,max(0,self.engine.page_count-1))); self.pages.setCurrentIndex(2); self.show_page()
            for b in self.nav_group.buttons():b.setChecked(b.text()=="Viewer")
            self.status.showMessage(Path(path).name)
        except Exception as exc:QMessageBox.critical(self,APP_NAME,f"Could not open PDF:\n{exc}")

    def show_page(self):
        if not self.engine.doc:return
        viewport=self.viewer_scroll.viewport().size(); img=self.engine.render_page(self.current_page,max(500,viewport.width()-40),max(600,viewport.height()-40)); data=img.convert('RGB').tobytes('raw','RGB'); qimg=QImage(data,img.width,img.height,img.width*3,QImage.Format_RGB888).copy(); pix=QPixmap.fromImage(qimg); self.viewer_image.setPixmap(pix); self.viewer_image.resize(pix.size()); self.page_label.setText(f"Page {self.current_page+1} / {self.engine.page_count}")

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.engine.doc:QTimer.singleShot(100,self.show_page)

    def change_page(self,delta):
        if self.engine.doc:self.current_page=max(0,min(self.engine.page_count-1,self.current_page+delta)); self.show_page()

    def _ensure_pdf(self):
        if not self.engine.doc:QMessageBox.information(self,APP_NAME,"Open a PDF first."); return False
        return True

    def _ensure_extracted_async(self,callback):
        if not self._ensure_pdf():return
        if self.engine.pages:callback(); return
        self.status.showMessage("Extracting text…")
        self._pending_extract.append(callback)
        if self._extraction_job is not None:return
        generation=self._doc_generation
        def cleanup():self._extraction_job=None; self._pending_extract=[]
        def done(records):
            self._extraction_job=None
            if generation!=self._doc_generation:return
            self.engine.pages=[PageRecord(**record) for record in records]
            callbacks,self._pending_extract=self._pending_extract,[]
            for fn in callbacks:fn()
        self._extraction_job=self.run_job("extract",{"path":str(self.engine.path)},done,cleanup)

    def extract_text(self):
        def show():
            self.stop_job(self._tool_job); self._tool_job=None; self._tool_generation+=1
            self.entities=extract_entities(self.engine.pages); self.tools_output.setPlainText(self.engine.all_text()); self.pages.setCurrentIndex(3); self.status.showMessage("Text extraction complete")
            for b in self.nav_group.buttons():b.setChecked(b.text()=="Tools")
        self._ensure_extracted_async(show)

    def summarize(self):
        def go():
            text=self.engine.all_text()
            self.stop_job(self._tool_job); self._tool_job=None
            if not any(p.text.strip() for p in self.engine.pages):self.tools_output.setPlainText("No readable text was extracted. Scanned PDFs may require local Tesseract OCR."); return
            self.tools_output.setPlainText("Creating local summary…"); self._tool_generation+=1; generation=self._tool_generation
            def done(result):
                if generation==self._tool_generation:self.tools_output.setPlainText(str(result)); self.status.showMessage("Summary complete")
            self._tool_job=self.run_job("summary",{"records":[asdict(p) for p in self.engine.pages],"document_name":self.engine.path.name,"model":self.model_name},done)
        self._ensure_extracted_async(go)

    def answer_current_pdf(self):
        q=self.tool_question.text().strip()
        if not q:self.tool_question.setFocus(); return
        def go():
            self.stop_job(self._tool_job); self._tool_job=None
            qterms=tokenize(q); matches=[]
            for p in self.engine.pages:
                score=sum(p.text.lower().count(t) for t in qterms)
                if score:
                    ranked=sorted(sentence_split(p.text),key=lambda s:sum(s.lower().count(t) for t in qterms),reverse=True); matches.append((score,p.number," ".join(ranked[:4]) or p.text[:1400]))
            matches=sorted(matches,reverse=True)[:10]
            if not matches:self.tools_output.setPlainText("No relevant passages found."); return
            context="\n\n".join(f"[Page {p}] {s}" for _,p,s in matches); self.tools_output.setPlainText("Answering locally…")
            self._tool_generation+=1; generation=self._tool_generation
            def done(result):
                if generation==self._tool_generation:self.tools_output.setPlainText(str(result))
            self._tool_job=self.run_job("answer_current",{"question":q,"records":[asdict(p) for p in self.engine.pages],"document_name":self.engine.path.name,"model":self.model_name},done)
        self._ensure_extracted_async(go)

    def export_text(self):
        def go():
            path,_=QFileDialog.getSaveFileName(self,"Export extracted text","","Text files (*.txt)")
            if path:
                if not path.lower().endswith('.txt'):path+='.txt'
                Path(path).write_text(self.engine.all_text(),encoding='utf-8'); self.status.showMessage(f"Saved {Path(path).name}")
        self._ensure_extracted_async(go)

    def export_csv(self):
        def go():
            rows=extract_entities(self.engine.pages); path,_=QFileDialog.getSaveFileName(self,"Export extracted data","","CSV files (*.csv)")
            if path:
                if not path.lower().endswith('.csv'):path+='.csv'
                with open(path,'w',newline='',encoding='utf-8-sig') as f:writer=csv.DictWriter(f,fieldnames=['page','type','value','context']); writer.writeheader(); writer.writerows(rows)
                self.status.showMessage(f"Saved {Path(path).name}")
        self._ensure_extracted_async(go)

    def open_settings(self):
        d=SettingsDialog(self.model_name,self)
        if d.exec()==QDialog.Accepted:self.model_name=d.model.text().strip() or DEFAULT_MODEL; self.settings.setValue("model",self.model_name); self.status.showMessage(f"AI model: {self.model_name}")

    def closeEvent(self,event):
        for job in list(self._jobs):job.stop()
        self._jobs.clear()
        self.engine.close(); event.accept()


def main():
    from multiprocessing import freeze_support
    freeze_support()
    app=QApplication([]); app.setApplicationName(APP_NAME); app.setFont(QFont("Segoe UI",10)); ensure_dirs()
    lock=QLockFile(str(APP_HOME/"application.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None,APP_NAME,"LocalPDF Insight is already running, or its data folder cannot be locked."); return
    try:
        win=MainWindow(); win.show(); app.exec()
    finally:lock.unlock()

if __name__ == "__main__":
    main()
