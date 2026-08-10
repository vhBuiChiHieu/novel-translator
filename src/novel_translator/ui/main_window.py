from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSettings, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from novel_translator.application.facade import ApplicationFacade
from novel_translator.application.services.translation_service import TranslationProgress

from .workers import FunctionWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Novel Translator")
        self.resize(1280, 800)
        self.facade: ApplicationFacade | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self.settings_store = QSettings("NovelTranslator", "NovelTranslator")
        self._selected_job_id: int | None = None
        self._activity_lines: list[str] = []
        self._build_shell()

    def _build_shell(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(190)
        self.sidebar.addItems(["Start / Open", "Dashboard", "Source / Chapters", "Translation Jobs", "Results", "Context", "Settings", "Logs"])
        self.sidebar.currentRowChanged.connect(self._select_page)
        layout.addWidget(self.sidebar)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._start_page())
        self.pages.addWidget(self._dashboard_page())
        self.pages.addWidget(self._source_page())
        self.pages.addWidget(self._jobs_page())
        self.pages.addWidget(self._results_page())
        self.pages.addWidget(self._context_page())
        self.pages.addWidget(self._settings_page())
        self.pages.addWidget(self._logs_page())
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.sidebar.setCurrentRow(0)
        self.statusBar().showMessage("Open a project to begin")

    def _select_page(self, row: int) -> None:
        self.pages.setCurrentIndex(row)
        if row == 1 and self.facade:
            self._refresh_dashboard()
        elif row == 2 and self.facade:
            self._refresh_chapters()
        elif row == 3 and self.facade:
            self._refresh_jobs()
        elif row == 4 and self.facade:
            self._refresh_results()
        elif row == 5 and self.facade:
            self._refresh_context()
        elif row == 6 and self.facade:
            self._load_settings_form()
        elif row == 7 and self.facade:
            self._refresh_logs()

    def _start_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Novel Translator")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel("Open a folder containing novel.yaml and the project database."))
        button = QPushButton("Open project folder…")
        button.clicked.connect(self._choose_project)
        layout.addWidget(button)
        self.recent_label = QLabel("")
        layout.addWidget(self.recent_label)
        layout.addStretch()
        return page

    def _dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.dashboard_title = QLabel("No project open")
        self.dashboard_title.setObjectName("pageTitle")
        layout.addWidget(self.dashboard_title)
        self.dashboard_details = QLabel("Choose Start / Open to open a project.")
        self.dashboard_details.setWordWrap(True)
        layout.addWidget(self.dashboard_details)
        buttons = QHBoxLayout()
        for label, row in (("Import", 2), ("Translate", 3), ("Settings", 6), ("Export", -1)):
            button = QPushButton(label)
            if row >= 0:
                button.clicked.connect(lambda _checked=False, target=row: self.sidebar.setCurrentRow(target))
            else:
                button.clicked.connect(self._export_novel)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        layout.addStretch()
        return page

    def _source_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        import_button = QPushButton("Choose input folder and preview/import")
        import_button.clicked.connect(self._choose_import)
        top.addWidget(import_button)
        top.addStretch()
        layout.addLayout(top)
        self.chapter_table = QTableWidget(0, 4)
        self.chapter_table.setHorizontalHeaderLabels(["Chapter", "Status", "Source hash", "Path"])
        self.chapter_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.chapter_table.cellClicked.connect(self._show_chapter)
        layout.addWidget(self.chapter_table)
        self.source_preview = QPlainTextEdit()
        self.source_preview.setReadOnly(True)
        self.source_preview.setPlaceholderText("Select a chapter to inspect source text")
        layout.addWidget(self.source_preview, 1)
        return page

    def _jobs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QHBoxLayout()
        self.first_chapter = QSpinBox()
        self.first_chapter.setMinimum(1)
        self.last_chapter = QSpinBox()
        self.last_chapter.setMinimum(1)
        self.resume_check = QCheckBox("Resume")
        self.force_check = QCheckBox("Force")
        form.addWidget(QLabel("From"))
        form.addWidget(self.first_chapter)
        form.addWidget(QLabel("to"))
        form.addWidget(self.last_chapter)
        form.addWidget(self.resume_check)
        form.addWidget(self.force_check)
        start = QPushButton("Start translation")
        start.clicked.connect(self._start_translation)
        form.addWidget(start)
        form.addStretch()
        layout.addLayout(form)
        self.job_table = QTableWidget(0, 7)
        self.job_table.setHorizontalHeaderLabels(["ID", "Chapter", "Status", "Provider", "Model", "Tokens", "Duration"])
        self.job_table.cellClicked.connect(self._show_job_results)
        layout.addWidget(self.job_table)
        self.job_log = QPlainTextEdit()
        self.job_log.setReadOnly(True)
        layout.addWidget(self.job_log, 1)
        return page

    def _results_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.results_title = QLabel("Model inspector")
        self.results_title.setObjectName("pageTitle")
        layout.addWidget(self.results_title)
        controls = QHBoxLayout()
        refresh = QPushButton("Refresh latest result")
        refresh.clicked.connect(self._refresh_results)
        controls.addWidget(refresh)
        controls.addStretch()
        layout.addLayout(controls)
        self.results_text = QPlainTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)
        return page

    def _context_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.context_filter = QComboBox()
        self.context_filter.addItems(["all", "character", "location", "organization", "term"])
        self.context_filter.currentTextChanged.connect(self._refresh_context)
        top.addWidget(QLabel("Type"))
        top.addWidget(self.context_filter)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_context)
        top.addWidget(refresh)
        export = QPushButton("Export context YAML")
        export.clicked.connect(self._export_context)
        top.addWidget(export)
        top.addStretch()
        layout.addLayout(top)
        self.context_table = QTableWidget(0, 4)
        self.context_table.setHorizontalHeaderLabels(["Type", "Source", "Translation", "Status"])
        layout.addWidget(self.context_table)
        return page

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.settings_form = QFormLayout()
        self.provider_edit = QComboBox()
        self.provider_edit.addItems(["ollama", "deepseek"])
        self.model_edit = QLineEdit()
        self.base_url_edit = QLineEdit()
        self.title_edit = QLineEdit()
        self.source_language_edit = QLineEdit()
        self.target_language_edit = QLineEdit()
        self.prompt_version_edit = QComboBox()
        self.prompt_version_edit.addItems(["translation-v1", "translation-v2"])
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.timeout_edit = QSpinBox()
        self.timeout_edit.setRange(1, 86400)
        self.retries_edit = QSpinBox()
        self.retries_edit.setRange(0, 20)
        self.temperature_edit = QDoubleSpinBox()
        self.temperature_edit.setRange(0, 2)
        self.temperature_edit.setSingleStep(0.05)
        self.top_p_edit = QDoubleSpinBox()
        self.top_p_edit.setRange(0, 1)
        self.top_p_edit.setSingleStep(0.05)
        self.context_size_edit = QSpinBox()
        self.context_size_edit.setRange(256, 262144)
        self.think_edit = QCheckBox("Enable model thinking")
        self.target_chars_edit = QSpinBox()
        self.target_chars_edit.setRange(100, 1000000)
        self.max_chars_edit = QSpinBox()
        self.max_chars_edit.setRange(100, 1000000)
        self.min_chars_edit = QSpinBox()
        self.min_chars_edit.setRange(0, 1000000)
        self.continuity_edit = QCheckBox("Include previous translation tail")
        self.tail_paragraphs_edit = QSpinBox()
        self.tail_paragraphs_edit.setRange(0, 100)
        self.log_level_edit = QComboBox()
        self.log_level_edit.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.settings_form.addRow("Project title", self.title_edit)
        self.settings_form.addRow("Source language", self.source_language_edit)
        self.settings_form.addRow("Target language", self.target_language_edit)
        self.settings_form.addRow("Provider", self.provider_edit)
        self.settings_form.addRow("Model", self.model_edit)
        self.settings_form.addRow("Base URL", self.base_url_edit)
        self.settings_form.addRow("Prompt version", self.prompt_version_edit)
        self.settings_form.addRow("Timeout (seconds)", self.timeout_edit)
        self.settings_form.addRow("Max retries", self.retries_edit)
        self.settings_form.addRow("Temperature", self.temperature_edit)
        self.settings_form.addRow("Top-p", self.top_p_edit)
        self.settings_form.addRow("Context size", self.context_size_edit)
        self.settings_form.addRow("Thinking", self.think_edit)
        self.settings_form.addRow("Chunk target chars", self.target_chars_edit)
        self.settings_form.addRow("Chunk max chars", self.max_chars_edit)
        self.settings_form.addRow("Chunk min chars", self.min_chars_edit)
        self.settings_form.addRow("Continuity", self.continuity_edit)
        self.settings_form.addRow("Tail paragraphs", self.tail_paragraphs_edit)
        self.settings_form.addRow("Log level", self.log_level_edit)
        self.settings_form.addRow("DeepSeek API key", self.api_key_edit)
        layout.addLayout(self.settings_form)
        save = QPushButton("Validate and save settings")
        save.clicked.connect(self._save_settings)
        layout.addWidget(save)
        check = QPushButton("Check provider configuration")
        check.clicked.connect(self._check_provider_config)
        layout.addWidget(check)
        layout.addStretch()
        return page

    def _logs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        refresh = QPushButton("Refresh logs")
        refresh.clicked.connect(self._refresh_logs)
        controls.addWidget(refresh)
        open_folder = QPushButton("Open logs folder")
        open_folder.clicked.connect(self._open_logs_folder)
        controls.addWidget(open_folder)
        controls.addStretch()
        layout.addLayout(controls)
        self.logs_text = QPlainTextEdit()
        self.logs_text.setReadOnly(True)
        layout.addWidget(self.logs_text)
        return page

    def _choose_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open Novel Translator project")
        if not path:
            return
        try:
            self.facade = ApplicationFacade(Path(path))
        except Exception as error:
            self._show_error(str(error))
            return
        self.settings_store.setValue("last_project", path)
        self._record_activity(f"Opened project: {path}")
        self.statusBar().showMessage(f"Opened {path}")
        self.sidebar.setCurrentRow(1)

    def _choose_import(self) -> None:
        if not self.facade:
            return self._show_error("Open a project first")
        path = QFileDialog.getExistingDirectory(self, "Choose chapter input folder")
        if path:
            previews = self.facade.preview_import(Path(path))
            valid = [row for row in previews if row.valid_utf8]
            invalid = [row for row in previews if not row.valid_utf8]
            message = f"{len(valid)} chapter(s) ready to import."
            if invalid:
                message += "\n" + "\n".join(row.error or "Invalid chapter" for row in invalid)
            answer = QMessageBox.question(self, "Import preview", message + "\nImport now?")
            if answer == QMessageBox.StandardButton.Yes:
                self._run_worker(self.facade.import_chapters, Path(path), done=self._after_import)

    def _start_translation(self) -> None:
        if not self.facade:
            return self._show_error("Open a project first")
        first, last = self.first_chapter.value(), self.last_chapter.value()
        if last < first:
            return self._show_error("The final chapter must be greater than or equal to the first chapter")
        worker_holder: list[FunctionWorker] = []

        def emit_progress(progress: TranslationProgress) -> None:
            worker_holder[0].signals.progress.emit(progress)

        worker = FunctionWorker(
            self.facade.translate_range,
            first,
            last,
            resume=self.resume_check.isChecked(),
            force=self.force_check.isChecked(),
            on_progress=emit_progress,
        )
        worker_holder.append(worker)
        worker.signals.progress.connect(self._append_progress)
        worker.signals.result.connect(self._after_translation)
        worker.signals.error.connect(self._handle_worker_error)
        self.thread_pool.start(worker)
        self._record_activity(f"Translation started: chapters {first}–{last}")

    def _run_worker(
        self,
        function: Callable[..., object],
        *args: object,
        done: Callable[[object], None] | None = None,
    ) -> None:
        worker = FunctionWorker(function, *args)
        if done:
            worker.signals.result.connect(done)
        worker.signals.error.connect(self._handle_worker_error)
        self.thread_pool.start(worker)

    def _append_progress(self, progress: TranslationProgress) -> None:
        chunk = f", chunk {(progress.chunk_index or 0) + 1}/{progress.total_chunks}" if progress.chunk_index is not None else ""
        duration = f" ({progress.duration_ms} ms)" if progress.duration_ms is not None else ""
        self._record_activity(
            f"Chapter {progress.chapter_number}{chunk}: {progress.event}{duration}"
            + (f" — {progress.error}" if progress.error else "")
        )

    def _after_import(self, _result: object) -> None:
        self._record_activity("Chapters imported")
        self.statusBar().showMessage("Chapters imported")
        self._refresh_chapters()
        self._refresh_dashboard()

    def _after_translation(self, _result: object) -> None:
        if self.facade:
            jobs = self.facade.list_jobs()
            if jobs:
                self._selected_job_id = jobs[0].id
        self._record_activity("Translation completed")
        self.statusBar().showMessage("Translation completed")
        self._refresh_jobs()
        self._refresh_dashboard()
        self._refresh_results()

    def _record_activity(self, message: str, level: int = logging.INFO) -> None:
        """Keep current UI activity visible even before the async log file refreshes."""
        self._activity_lines.append(message)
        self._activity_lines = self._activity_lines[-250:]
        self.job_log.appendPlainText(message)
        logger.log(level, message)
        if self.pages.currentIndex() == 7:
            self._refresh_logs()

    def _handle_worker_error(self, message: str) -> None:
        self._record_activity(f"Operation failed: {message}", logging.ERROR)
        self._show_error(message)

    def _export_novel(self) -> None:
        if self.facade:
            self._run_worker(self.facade.export_novel, done=lambda path: self.statusBar().showMessage(f"Exported {path}"))

    def _export_context(self) -> None:
        if self.facade:
            self._run_worker(self.facade.export_context, done=lambda path: self.statusBar().showMessage(f"Exported {path}"))

    def _refresh_dashboard(self) -> None:
        if not self.facade:
            return
        dashboard = self.facade.get_dashboard()
        self.dashboard_title.setText(dashboard.project.title or dashboard.project.project_name)
        counts = ", ".join(f"{key}: {value}" for key, value in dashboard.chapter_counts.items())
        health = "Healthy" if dashboard.health_ok else "; ".join(dashboard.health_errors)
        self.dashboard_details.setText(
            f"Project: {dashboard.project.project_name}\n"
            f"{dashboard.project.source_language} → {dashboard.project.target_language}\n"
            f"Model: {dashboard.provider} / {dashboard.model}\n"
            f"Chapters: {counts}\nOpen conflicts: {dashboard.open_conflicts}\nHealth: {health}"
        )

    def _refresh_chapters(self) -> None:
        if not self.facade:
            return
        chapters = self.facade.list_chapters()
        self.chapter_table.setRowCount(len(chapters))
        for row, chapter in enumerate(chapters):
            self.chapter_table.setItem(row, 0, QTableWidgetItem(str(chapter.chapter_number)))
            self.chapter_table.setItem(row, 1, QTableWidgetItem(chapter.status))
            self.chapter_table.setItem(row, 2, QTableWidgetItem(chapter.source_hash))
            self.chapter_table.setItem(row, 3, QTableWidgetItem(chapter.source_path))

    def _show_chapter(self, row: int, _column: int) -> None:
        if not self.facade:
            return
        try:
            chapter_item = self.chapter_table.item(row, 0)
            if chapter_item is None:
                return
            chapter = self.facade.get_chapter(int(chapter_item.text()))
            self.source_preview.setPlainText(chapter.source_text or "")
        except Exception as error:
            self._show_error(str(error))

    def _refresh_jobs(self) -> None:
        if not self.facade:
            return
        jobs = self.facade.list_jobs()
        self.job_table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            values = [str(job.id), str(job.chapter_number or ""), job.status, job.model_provider, job.model_name, f"{job.total_prompt_tokens}/{job.total_output_tokens}", f"{job.total_duration_ms} ms"]
            for column, value in enumerate(values):
                self.job_table.setItem(row, column, QTableWidgetItem(value))

    def _show_job_results(self, row: int, _column: int) -> None:
        if not self.facade:
            return
        job_item = self.job_table.item(row, 0)
        if job_item is None:
            return
        self._selected_job_id = int(job_item.text())
        self.sidebar.setCurrentRow(4)

    def _refresh_results(self) -> None:
        if not self.facade:
            return
        jobs = self.facade.list_jobs()
        if not jobs:
            self._selected_job_id = None
            self.results_title.setText("Model inspector")
            self.results_text.setPlainText("No translation jobs recorded yet.")
            return
        job = next((item for item in jobs if item.id == self._selected_job_id), jobs[0])
        self._selected_job_id = job.id
        self.results_title.setText(f"Model inspector — Chapter {job.chapter_number}, job #{job.id}")
        calls = [call for call in self.facade.list_model_calls() if call.translation_job_id == job.id]
        self.results_text.setPlainText(
            "\n\n".join(call.model_dump_json(indent=2) for call in calls)
            or f"No model calls recorded for job #{job.id}."
        )

    def _refresh_context(self) -> None:
        if not self.facade:
            return
        selected = self.context_filter.currentText()
        rows = self.facade.list_context(None if selected == "all" else selected)
        self.context_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            for column, value in enumerate([item.context_type, item.source, item.translation or "", item.status]):
                self.context_table.setItem(row, column, QTableWidgetItem(value))

    def _load_settings_form(self) -> None:
        if not self.facade:
            return
        settings = self.facade.session.settings
        self.title_edit.setText(settings.title)
        self.source_language_edit.setText(settings.source_language)
        self.target_language_edit.setText(settings.target_language)
        self.provider_edit.setCurrentText(settings.model.provider)
        self.model_edit.setText(settings.model.name)
        self.base_url_edit.setText(settings.model.base_url)
        self.prompt_version_edit.setCurrentText(settings.prompt_version)
        self.timeout_edit.setValue(settings.model.request_timeout_seconds)
        self.retries_edit.setValue(settings.model.max_retries)
        self.temperature_edit.setValue(settings.model.options.temperature)
        self.top_p_edit.setValue(settings.model.options.top_p)
        self.context_size_edit.setValue(settings.model.options.num_ctx)
        self.think_edit.setChecked(settings.model.options.think)
        self.target_chars_edit.setValue(settings.chunk.target_chars)
        self.max_chars_edit.setValue(settings.chunk.max_chars)
        self.min_chars_edit.setValue(settings.chunk.min_chars)
        self.continuity_edit.setChecked(settings.continuity.include_previous_tail)
        self.tail_paragraphs_edit.setValue(settings.continuity.previous_tail_paragraphs)
        self.log_level_edit.setCurrentText(settings.log_level)

    def _save_settings(self) -> None:
        if not self.facade:
            return
        try:
            self.facade.update_settings(
                {
                    "title": self.title_edit.text(),
                    "source_language": self.source_language_edit.text(),
                    "target_language": self.target_language_edit.text(),
                    "prompt_version": self.prompt_version_edit.currentText(),
                    "log_level": self.log_level_edit.currentText(),
                    "chunk": {
                        "target_chars": self.target_chars_edit.value(),
                        "max_chars": self.max_chars_edit.value(),
                        "min_chars": self.min_chars_edit.value(),
                    },
                    "continuity": {
                        "include_previous_tail": self.continuity_edit.isChecked(),
                        "previous_tail_paragraphs": self.tail_paragraphs_edit.value(),
                    },
                    "model": {
                        "provider": self.provider_edit.currentText(),
                        "name": self.model_edit.text(),
                        "base_url": self.base_url_edit.text(),
                        "request_timeout_seconds": self.timeout_edit.value(),
                        "max_retries": self.retries_edit.value(),
                        "options": {
                            "temperature": self.temperature_edit.value(),
                            "top_p": self.top_p_edit.value(),
                            "num_ctx": self.context_size_edit.value(),
                            "think": self.think_edit.isChecked(),
                        },
                    },
                }
            )
            if self.api_key_edit.text():
                self.facade.set_api_key(self.api_key_edit.text())
            self.statusBar().showMessage("Settings saved")
        except Exception as error:
            self._show_error(str(error))

    def _check_provider_config(self) -> None:
        if not self.facade:
            return self._show_error("Open a project first")
        settings = self.facade.session.settings
        if settings.model.provider == "deepseek" and settings.model.api_key is None:
            return self._show_error("DeepSeek API key is not configured")
        self.statusBar().showMessage(
            f"Configuration valid for {settings.model.provider}/{settings.model.name}; connectivity is checked on Start."
        )

    def _refresh_logs(self) -> None:
        if not self.facade:
            return
        files = sorted(self.facade.session.project_path.joinpath("logs").glob("*.log"), reverse=True)
        if not files:
            self.logs_text.setPlainText("\n".join(self._activity_lines) or "No log files yet.")
            return
        try:
            persisted = files[0].read_text(encoding="utf-8", errors="replace")
            current_activity = "\n".join(self._activity_lines)
            self.logs_text.setPlainText(
                f"{persisted}\n\n--- Current UI activity ---\n{current_activity}"
                if current_activity
                else persisted
            )
        except OSError as error:
            self.logs_text.setPlainText(str(error))

    def _open_logs_folder(self) -> None:
        if self.facade:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.facade.session.project_path / "logs")))

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Novel Translator", message)


def run_window() -> int:
    existing_app = QApplication.instance()
    app = existing_app if isinstance(existing_app, QApplication) else QApplication([])
    app.setStyleSheet(
        "QListWidget { background: #20242b; color: #e9edf1; padding: 8px; }"
        "QListWidget::item { padding: 10px; } QListWidget::item:selected { background: #3b82f6; }"
        "#pageTitle { font-size: 24px; font-weight: 600; padding-bottom: 8px; }"
    )
    window = MainWindow()
    window.show()
    return app.exec()
