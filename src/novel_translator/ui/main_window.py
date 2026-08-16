from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from PySide6.QtCore import QSettings, Qt, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from novel_translator.application.facade import ApplicationFacade
from novel_translator.application.services.translation_service import TranslationProgress
from novel_translator.domain.model.catalog import model_options_for

from .style import APP_STYLESHEET
from .workers import FunctionWorker

logger = logging.getLogger(__name__)
WidgetT = TypeVar("WidgetT", bound=QWidget)


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
        last_project = self.settings_store.value("last_project", "", type=str)
        if last_project:
            self.recent_label.setText(f"Last project: {last_project}")

    def _build_shell(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar_panel = QWidget()
        sidebar_panel.setObjectName("sidebar")
        sidebar_panel.setFixedWidth(232)
        sidebar_layout = QVBoxLayout(sidebar_panel)
        sidebar_layout.setContentsMargins(16, 20, 16, 18)
        sidebar_layout.setSpacing(4)
        brand = QLabel("Novel Translator")
        brand.setObjectName("brand")
        sidebar_layout.addWidget(brand)
        brand_caption = QLabel("Local-first translation workspace")
        brand_caption.setObjectName("brandCaption")
        sidebar_layout.addWidget(brand_caption)
        sidebar_layout.addSpacing(26)
        section = QLabel("WORKSPACE")
        section.setObjectName("sidebarSection")
        sidebar_layout.addWidget(section)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("navigation")
        self.sidebar.addItems(["Open project", "Overview", "Chapters", "Translation", "Results", "Context", "Settings", "Logs"])
        self.sidebar.currentRowChanged.connect(self._select_page)
        sidebar_layout.addWidget(self.sidebar, 1)
        footer = QLabel("Novel Translator\nDesktop workspace")
        footer.setObjectName("brandCaption")
        sidebar_layout.addWidget(footer)
        layout.addWidget(sidebar_panel)
        self.pages = QStackedWidget()
        self.pages.setObjectName("contentArea")
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

    def _page_layout(self, subtitle: str, title: str) -> tuple[QWidget, QVBoxLayout]:
        """Create a consistent page canvas with predictable alignment."""
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        if subtitle:
            description = QLabel(subtitle)
            description.setObjectName("pageSubtitle")
            description.setWordWrap(True)
            layout.addWidget(description)
        return page, layout

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        return card, layout

    @staticmethod
    def _set_button_role(button: QPushButton, role: str) -> None:
        """Apply a dynamic stylesheet role immediately after assigning it."""
        button.setProperty("role", role)
        button.style().unpolish(button)
        button.style().polish(button)

    @staticmethod
    def _optional_option(control: WidgetT, label: str) -> tuple[QCheckBox, WidgetT]:
        """Pair an optional provider parameter with an explicit enable switch."""
        enabled = QCheckBox(label)
        control.setEnabled(False)
        enabled.toggled.connect(control.setEnabled)
        return enabled, control

    @staticmethod
    def _configure_table(table: QTableWidget) -> None:
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

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
        page, layout = self._page_layout("Open an existing workspace to import chapters, translate, and export your novel.", "Welcome")
        card, card_layout = self._card()
        section_title = QLabel("Open a project")
        section_title.setObjectName("sectionTitle")
        card_layout.addWidget(section_title)
        guidance = QLabel("Select the project folder that contains novel.yaml and the project database.")
        guidance.setObjectName("muted")
        guidance.setWordWrap(True)
        card_layout.addWidget(guidance)
        button = QPushButton("Open project folder…")
        self._set_button_role(button, "primary")
        button.setMinimumWidth(190)
        button.clicked.connect(self._choose_project)
        card_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.recent_label = QLabel("")
        self.recent_label.setObjectName("muted")
        card_layout.addWidget(self.recent_label)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _dashboard_page(self) -> QWidget:
        page, layout = self._page_layout("A concise view of project health and the next action to take.", "Overview")
        self.dashboard_title = QLabel("No project open")
        self.dashboard_title.setObjectName("sectionTitle")
        layout.addWidget(self.dashboard_title)
        self.dashboard_details = QLabel("Choose Start / Open to open a project.")
        self.dashboard_details.setObjectName("muted")
        self.dashboard_details.setWordWrap(True)
        layout.addWidget(self.dashboard_details)
        buttons = QHBoxLayout()
        for label, row in (("Import", 2), ("Translate", 3), ("Settings", 6), ("Export", -1)):
            button = QPushButton(label)
            if label == "Translate":
                self._set_button_role(button, "primary")
            if row >= 0:
                button.clicked.connect(lambda _checked=False, target=row: self.sidebar.setCurrentRow(target))
            else:
                button.clicked.connect(self._export_novel)
            buttons.addWidget(button)
        actions, actions_layout = self._card()
        actions_title = QLabel("Quick actions")
        actions_title.setObjectName("sectionTitle")
        actions_layout.addWidget(actions_title)
        actions_layout.addLayout(buttons)
        layout.addWidget(actions)
        layout.addStretch()
        return page

    def _source_page(self) -> QWidget:
        page, layout = self._page_layout("Import chapter files, then select a row to inspect the original text.", "Chapters")
        card, card_layout = self._card()
        top = QHBoxLayout()
        import_button = QPushButton("Choose input folder and preview/import")
        self._set_button_role(import_button, "primary")
        import_button.clicked.connect(self._choose_import)
        top.addWidget(import_button)
        top.addStretch()
        card_layout.addLayout(top)
        self.chapter_table = QTableWidget(0, 4)
        self.chapter_table.setHorizontalHeaderLabels(["Chapter", "Status", "Source hash", "Path"])
        self._configure_table(self.chapter_table)
        self.chapter_table.cellClicked.connect(self._show_chapter)
        card_layout.addWidget(self.chapter_table, 1)
        self.source_preview = QPlainTextEdit()
        self.source_preview.setReadOnly(True)
        self.source_preview.setPlaceholderText("Select a chapter to inspect source text")
        card_layout.addWidget(self.source_preview, 1)
        layout.addWidget(card, 1)
        return page

    def _jobs_page(self) -> QWidget:
        page, layout = self._page_layout("Choose a chapter range and monitor progress without leaving the workspace.", "Translation")
        controls_card, controls_layout = self._card()
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
        self._set_button_role(start, "primary")
        start.clicked.connect(self._start_translation)
        form.addWidget(start)
        form.addStretch()
        controls_layout.addLayout(form)
        layout.addWidget(controls_card)
        jobs_card, jobs_layout = self._card()
        self.job_table = QTableWidget(0, 7)
        self.job_table.setHorizontalHeaderLabels(["ID", "Chapter", "Status", "Provider", "Model", "Tokens", "Duration"])
        self._configure_table(self.job_table)
        self.job_table.cellClicked.connect(self._show_job_results)
        jobs_layout.addWidget(self.job_table, 1)
        self.job_log = QPlainTextEdit()
        self.job_log.setReadOnly(True)
        jobs_layout.addWidget(self.job_log, 1)
        layout.addWidget(jobs_card, 1)
        return page

    def _results_page(self) -> QWidget:
        page, layout = self._page_layout("Inspect the selected job's provider calls and parsed response.", "Results")
        self.results_title = QLabel("Model inspector")
        self.results_title.setObjectName("pageTitle")
        layout.addWidget(self.results_title)
        controls = QHBoxLayout()
        refresh = QPushButton("Refresh latest result")
        refresh.clicked.connect(self._refresh_results)
        controls.addWidget(refresh)
        controls.addStretch()
        card, card_layout = self._card()
        card_layout.addLayout(controls)
        self.results_text = QPlainTextEdit()
        self.results_text.setReadOnly(True)
        card_layout.addWidget(self.results_text, 1)
        layout.addWidget(card, 1)
        return page

    def _context_page(self) -> QWidget:
        page, layout = self._page_layout(
            "Browse every table in this project's database. This viewer is read-only; select a row to see its complete content.",
            "Context",
        )
        card, card_layout = self._card()
        top = QHBoxLayout()
        self.context_table_selector = QComboBox()
        self.context_table_selector.setMinimumWidth(230)
        self.context_table_selector.currentTextChanged.connect(self._refresh_database_table)
        top.addWidget(QLabel("Database table"))
        top.addWidget(self.context_table_selector)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_context)
        top.addWidget(refresh)
        export = QPushButton("Export context YAML")
        export.clicked.connect(self._export_context)
        top.addWidget(export)
        top.addStretch()
        card_layout.addLayout(top)
        self.context_table_info = QLabel("Open a project to browse its database.")
        self.context_table_info.setObjectName("muted")
        card_layout.addWidget(self.context_table_info)
        self.context_table = QTableWidget(0, 0)
        self._configure_table(self.context_table)
        self.context_table.horizontalHeader().setStretchLastSection(False)
        self.context_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.context_table.cellClicked.connect(self._show_database_row)
        card_layout.addWidget(self.context_table, 2)
        self.context_row_detail = QPlainTextEdit()
        self.context_row_detail.setReadOnly(True)
        self.context_row_detail.setPlaceholderText("Select a row to inspect every field, including long text and JSON.")
        card_layout.addWidget(self.context_row_detail, 1)
        self._context_database_rows: list[dict[str, str]] = []
        layout.addWidget(card, 1)
        return page

    def _settings_page(self) -> QWidget:
        page, layout = self._page_layout("Configure translation behaviour and provider access for this project.", "Settings")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setStyleSheet("background: #f6f8fb;")
        content = QWidget()
        content.setObjectName("settingsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 12, 0)
        content_layout.setSpacing(16)

        self.provider_edit = QComboBox()
        self.provider_edit.addItems(["ollama", "deepseek", "gemini"])
        self.model_edit = QLineEdit()
        self.model_preset_edit = QComboBox()
        self.model_preset_edit.currentIndexChanged.connect(self._apply_model_preset)
        self.provider_edit.currentTextChanged.connect(self._provider_changed)
        self.model_preset_label = QLabel("Model preset")
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
        self.temperature_enabled, self.temperature_edit = self._optional_option(self.temperature_edit, "Temperature")
        self.top_p_edit = QDoubleSpinBox()
        self.top_p_edit.setRange(0, 1)
        self.top_p_edit.setSingleStep(0.05)
        self.top_p_enabled, self.top_p_edit = self._optional_option(self.top_p_edit, "Top-p")
        self.top_k_edit = QSpinBox()
        self.top_k_edit.setRange(1, 1000)
        self.top_k_enabled, self.top_k_edit = self._optional_option(self.top_k_edit, "Top-k")
        self.context_size_edit = QSpinBox()
        self.context_size_edit.setRange(256, 262144)
        self.context_size_enabled, self.context_size_edit = self._optional_option(self.context_size_edit, "Context size")
        self.think_edit = QCheckBox("Enable model thinking (Ollama only)")
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

        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        project_card, project_layout = self._card()
        project_title = QLabel("Project")
        project_title.setObjectName("sectionTitle")
        project_layout.addWidget(project_title)
        project_form = QFormLayout()
        project_form.setVerticalSpacing(10)
        project_form.addRow("Title", self.title_edit)
        project_form.addRow("Source language", self.source_language_edit)
        project_form.addRow("Target language", self.target_language_edit)
        project_form.addRow("Prompt version", self.prompt_version_edit)
        project_form.addRow("Log level", self.log_level_edit)
        project_layout.addLayout(project_form)
        top_row.addWidget(project_card, 1)

        provider_card, provider_layout = self._card()
        provider_title = QLabel("Provider connection")
        provider_title.setObjectName("sectionTitle")
        provider_layout.addWidget(provider_title)
        provider_form = QFormLayout()
        provider_form.setVerticalSpacing(10)
        provider_form.addRow("Provider", self.provider_edit)
        provider_form.addRow(self.model_preset_label, self.model_preset_edit)
        provider_form.addRow("Model", self.model_edit)
        provider_form.addRow("Base URL", self.base_url_edit)
        provider_form.addRow("Timeout (seconds)", self.timeout_edit)
        provider_form.addRow("Max retries", self.retries_edit)
        provider_form.addRow("Provider API key", self.api_key_edit)
        provider_layout.addLayout(provider_form)
        self._refresh_model_presets(self.provider_edit.currentText())
        top_row.addWidget(provider_card, 1)
        content_layout.addLayout(top_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)
        translation_card, translation_layout = self._card()
        translation_title = QLabel("Translation flow")
        translation_title.setObjectName("sectionTitle")
        translation_layout.addWidget(translation_title)
        translation_form = QFormLayout()
        translation_form.setVerticalSpacing(10)
        translation_form.addRow("Target chars", self.target_chars_edit)
        translation_form.addRow("Maximum chars", self.max_chars_edit)
        translation_form.addRow("Minimum chars", self.min_chars_edit)
        translation_form.addRow("Continuity", self.continuity_edit)
        translation_form.addRow("Tail paragraphs", self.tail_paragraphs_edit)
        translation_layout.addLayout(translation_form)
        bottom_row.addWidget(translation_card, 1)

        options_card, options_layout = self._card()
        options_title = QLabel("Model options")
        options_title.setObjectName("sectionTitle")
        options_layout.addWidget(options_title)
        hint = QLabel("Select only the options you want to send. Unselected values use the provider default and are omitted from novel.yaml.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        options_layout.addWidget(hint)
        options_form = QFormLayout()
        options_form.setVerticalSpacing(10)
        options_form.addRow(self.temperature_enabled, self.temperature_edit)
        options_form.addRow(self.top_p_enabled, self.top_p_edit)
        options_form.addRow(self.top_k_enabled, self.top_k_edit)
        options_form.addRow(self.context_size_enabled, self.context_size_edit)
        options_form.addRow("", self.think_edit)
        options_layout.addLayout(options_form)
        bottom_row.addWidget(options_card, 1)
        content_layout.addLayout(bottom_row)
        actions_card, actions_layout = self._card()
        actions_title = QLabel("Apply changes")
        actions_title.setObjectName("sectionTitle")
        actions_layout.addWidget(actions_title)
        actions = QHBoxLayout()
        save = QPushButton("Validate and save settings")
        self._set_button_role(save, "primary")
        save.clicked.connect(self._save_settings)
        actions.addWidget(save)
        check = QPushButton("Check provider configuration")
        check.clicked.connect(self._check_provider_config)
        actions.addWidget(check)
        reset = QPushButton("Reset project data…")
        self._set_button_role(reset, "danger")
        reset.clicked.connect(self._confirm_reset_project)
        actions.addWidget(reset)
        actions.addStretch()
        actions_layout.addLayout(actions)
        content_layout.addWidget(actions_card)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _logs_page(self) -> QWidget:
        page, layout = self._page_layout("Recent file logs and actions performed in this desktop session.", "Logs")
        card, card_layout = self._card()
        controls = QHBoxLayout()
        refresh = QPushButton("Refresh logs")
        refresh.clicked.connect(self._refresh_logs)
        controls.addWidget(refresh)
        open_folder = QPushButton("Open logs folder")
        open_folder.clicked.connect(self._open_logs_folder)
        controls.addWidget(open_folder)
        controls.addStretch()
        card_layout.addLayout(controls)
        self.logs_text = QPlainTextEdit()
        self.logs_text.setReadOnly(True)
        card_layout.addWidget(self.logs_text, 1)
        layout.addWidget(card, 1)
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

    def _confirm_reset_project(self) -> None:
        if not self.facade:
            return self._show_error("Open a project first")
        answer = QMessageBox.warning(
            self,
            "Reset project data",
            "This permanently removes the project database, imported chapters, translated chapters, and exported files.\n\n"
            "novel.yaml and logs will be kept. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._run_worker(self.facade.reset_project, done=self._after_reset_project)

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

    def _after_reset_project(self, _result: object) -> None:
        self._selected_job_id = None
        self.source_preview.clear()
        self.job_log.clear()
        self.results_text.clear()
        self._record_activity("Project data reset")
        self.statusBar().showMessage("Project data reset; configuration kept")
        self._refresh_chapters()
        self._refresh_jobs()
        self._refresh_context()
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
        current = self.context_table_selector.currentText()
        tables = self.facade.list_database_tables()
        signals_were_blocked = self.context_table_selector.blockSignals(True)
        self.context_table_selector.clear()
        self.context_table_selector.addItems(tables)
        if current in tables:
            self.context_table_selector.setCurrentText(current)
        self.context_table_selector.blockSignals(signals_were_blocked)
        self._refresh_database_table()

    def _refresh_database_table(self) -> None:
        if not self.facade:
            return
        table_name = self.context_table_selector.currentText()
        if not table_name:
            self.context_table.clear()
            self.context_table.setRowCount(0)
            self.context_table.setColumnCount(0)
            self.context_table_info.setText("This project database has no tables yet.")
            self.context_row_detail.clear()
            self._context_database_rows = []
            return
        try:
            table = self.facade.get_database_table(table_name)
            self._context_database_rows = table.rows
            self.context_table.clear()
            self.context_table.setColumnCount(len(table.columns))
            self.context_table.setHorizontalHeaderLabels(table.columns)
            self.context_table.setRowCount(len(table.rows))
            for row_index, row in enumerate(table.rows):
                for column_index, column_name in enumerate(table.columns):
                    value = row[column_name]
                    cell = QTableWidgetItem(value)
                    cell.setToolTip(value)
                    self.context_table.setItem(row_index, column_index, cell)
                    self.context_table.setColumnWidth(column_index, 180)
            self.context_table_info.setText(f"{table.name}: {len(table.rows)} row(s), {len(table.columns)} column(s)")
            self.context_row_detail.clear()
        except Exception as error:
            self._context_database_rows = []
            self.context_table.setRowCount(0)
            self.context_table.setColumnCount(0)
            self.context_row_detail.clear()
            self._show_error(str(error))

    def _show_database_row(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._context_database_rows):
            values = self._context_database_rows[row]
            self.context_row_detail.setPlainText(
                "\n\n".join(f"{column_name}\n{'─' * len(column_name)}\n{value}" for column_name, value in values.items())
            )

    def _provider_changed(self, provider: str) -> None:
        self._refresh_model_presets(provider)
        if provider != "ollama":
            options = model_options_for(provider)
            if options:
                self.model_edit.setText(options[0]["id"])

    def _refresh_model_presets(self, provider: str) -> None:
        options = model_options_for(provider)
        self.model_preset_edit.blockSignals(True)
        self.model_preset_edit.clear()
        if options:
            self.model_preset_edit.addItem("Choose a model preset…", "")
            for option in options:
                self.model_preset_edit.addItem(f"{option['label']} · {option['status']}", option["id"])
        self.model_preset_edit.setEnabled(bool(options))
        self.model_preset_label.setVisible(bool(options))
        self.model_preset_edit.setVisible(bool(options))
        self.model_preset_edit.blockSignals(False)

    def _apply_model_preset(self, _index: int) -> None:
        model_id = self.model_preset_edit.currentData()
        if model_id:
            self.model_edit.setText(str(model_id))

    def _load_settings_form(self) -> None:
        if not self.facade:
            return
        settings = self.facade.session.settings
        self.title_edit.setText(settings.title)
        self.source_language_edit.setText(settings.source_language)
        self.target_language_edit.setText(settings.target_language)
        self.provider_edit.setCurrentText(settings.model.provider)
        self._refresh_model_presets(settings.model.provider)
        self.model_edit.setText(settings.model.name)
        preset_index = self.model_preset_edit.findData(settings.model.name)
        self.model_preset_edit.setCurrentIndex(preset_index if preset_index >= 0 else 0)
        self.base_url_edit.setText(settings.model.base_url)
        self.prompt_version_edit.setCurrentText(settings.prompt_version)
        self.timeout_edit.setValue(settings.model.request_timeout_seconds)
        self.retries_edit.setValue(settings.model.max_retries)
        options = settings.model.options
        self.temperature_edit.setValue(options.temperature if options.temperature is not None else 0.2)
        self.temperature_enabled.setChecked(options.temperature is not None)
        self.top_p_edit.setValue(options.top_p if options.top_p is not None else 0.9)
        self.top_p_enabled.setChecked(options.top_p is not None)
        self.top_k_edit.setValue(options.top_k if options.top_k is not None else 40)
        self.top_k_enabled.setChecked(options.top_k is not None)
        self.context_size_edit.setValue(options.num_ctx if options.num_ctx is not None else 16384)
        self.context_size_enabled.setChecked(options.num_ctx is not None)
        self.think_edit.setChecked(options.think is True)
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
                            "temperature": self.temperature_edit.value() if self.temperature_enabled.isChecked() else None,
                            "top_p": self.top_p_edit.value() if self.top_p_enabled.isChecked() else None,
                            "top_k": self.top_k_edit.value() if self.top_k_enabled.isChecked() else None,
                            "num_ctx": self.context_size_edit.value() if self.context_size_enabled.isChecked() else None,
                            "think": True if self.think_edit.isChecked() else None,
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
        if settings.model.provider in {"deepseek", "gemini"} and settings.model.api_key is None:
            return self._show_error(f"{settings.model.provider.title()} API key is not configured")
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
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()
