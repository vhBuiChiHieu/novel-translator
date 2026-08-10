"""Visual language for the desktop application.

Keeping the stylesheet in one place prevents pages from gradually acquiring
slightly different borders, focus states, and interaction behaviour.
"""

APP_STYLESHEET = """
* {
    font-family: Arial;
    font-size: 13px;
    color: #1d2939;
}
QMainWindow, QWidget#appRoot { background: #f6f8fb; }

QWidget#sidebar {
    background: #162033;
    border-right: 1px solid #24334a;
}
QLabel#brand { color: #ffffff; font-size: 18px; font-weight: 700; }
QLabel#brandCaption { color: #a9b7ca; font-size: 11px; }
QLabel#sidebarSection { color: #8fa2ba; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; }

QListWidget#navigation {
    background: transparent;
    border: 0;
    outline: 0;
    padding: 6px 8px;
    color: #c8d4e3;
}
QListWidget#navigation::item {
    border: 1px solid transparent;
    border-radius: 8px;
    margin: 2px 0;
    min-height: 23px;
    padding: 8px 10px;
}
QListWidget#navigation::item:hover { background: #23324a; color: #ffffff; }
QListWidget#navigation::item:selected {
    background: #2d6cdf;
    border-color: #4d83e4;
    color: #ffffff;
    font-weight: 600;
}

QWidget#contentArea { background: #f6f8fb; }
QWidget#page { background: transparent; }
QScrollArea, QScrollArea > QWidget > QWidget { background: #f6f8fb; }
QScrollArea > QWidget > QWidget#settingsContent { background: #f6f8fb; }
QLabel#pageTitle { color: #162033; font-size: 25px; font-weight: 700; }
QLabel#pageSubtitle { color: #667085; font-size: 13px; }
QLabel#sectionTitle { color: #344054; font-size: 14px; font-weight: 700; }
QLabel#metricValue { color: #162033; font-size: 25px; font-weight: 700; }
QLabel#metricLabel { color: #667085; font-size: 11px; font-weight: 600; }
QLabel#muted { color: #667085; }

QFrame#card, QFrame#metricCard {
    background: #ffffff;
    border: 1px solid #e4e7ec;
    border-radius: 12px;
}
QFrame#metricCard { min-height: 84px; }

QPushButton {
    background: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 7px;
    min-height: 19px;
    padding: 7px 12px;
    font-weight: 600;
}
QPushButton:hover { background: #f9fafb; border-color: #98a2b3; }
QPushButton:pressed { background: #eaecf0; border-color: #667085; padding-top: 8px; padding-bottom: 6px; }
QPushButton:focus { border: 2px solid #84adf6; padding: 6px 11px; }
QPushButton:disabled { background: #f2f4f7; border-color: #eaecf0; color: #98a2b3; }
QPushButton[role="primary"] { background-color: #2d6cdf; border-color: #2d6cdf; color: #ffffff; }
QPushButton[role="primary"]:hover { background-color: #215fc9; border-color: #215fc9; color: #ffffff; }
QPushButton[role="primary"]:pressed { background-color: #1d4fa8; border-color: #1d4fa8; color: #ffffff; }
QPushButton[role="primary"]:focus { background-color: #2d6cdf; border-color: #84adf6; color: #ffffff; }
QPushButton[role="danger"] { background-color: #ffffff; border-color: #fda29b; color: #b42318; }
QPushButton[role="danger"]:hover { background-color: #fef3f2; border-color: #f97066; color: #912018; }
QPushButton[role="danger"]:pressed { background-color: #fee4e2; border-color: #f04438; color: #912018; }

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 7px;
    min-height: 20px;
    padding: 6px 8px;
    selection-background-color: #b9d2ff;
}
QPlainTextEdit { padding: 10px; font-family: Consolas; }
QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #98a2b3; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #5b91eb;
    padding: 5px 7px;
}
QComboBox::drop-down { border: 0; width: 28px; }
QComboBox QAbstractItemView { border: 1px solid #d0d5dd; selection-background-color: #e8f0fe; selection-color: #162033; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #98a2b3; border-radius: 4px; background: #ffffff; }
QCheckBox::indicator:hover { border-color: #2d6cdf; }
QCheckBox::indicator:checked { background: #2d6cdf; border-color: #2d6cdf; }

QTableWidget {
    background: #ffffff;
    alternate-background-color: #f9fafb;
    border: 1px solid #e4e7ec;
    border-radius: 8px;
    gridline-color: #eaecf0;
    selection-background-color: #e8f0fe;
    selection-color: #162033;
    outline: 0;
}
QTableWidget::item { border: 0; padding: 7px 8px; }
QTableWidget::item:hover { background: #f2f6fc; }
QHeaderView::section {
    background: #f9fafb;
    color: #667085;
    border: 0;
    border-bottom: 1px solid #e4e7ec;
    padding: 9px 8px;
    font-size: 11px;
    font-weight: 700;
}
QScrollBar:vertical { background: transparent; width: 11px; margin: 4px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #98a2b3; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QStatusBar { background: #ffffff; color: #667085; border-top: 1px solid #e4e7ec; }
QStatusBar::item { border: 0; }
QToolTip { background: #162033; color: #ffffff; border: 0; border-radius: 4px; padding: 5px; }
QMessageBox { background-color: #ffffff; }
QMessageBox QLabel { color: #1d2939; }
QMessageBox QPushButton { color: #1d2939; }
"""
