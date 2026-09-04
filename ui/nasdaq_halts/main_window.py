from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QFileDialog,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.nasdaq_halts.file_validation import validate_input_file


REASON_CODES = ["LUDP", "M", "T1", "T2", "T3", "T12", "D", "H11"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("QuantLab - Nasdaq HALT Analytics")
        self.setFixedSize(620, 500)

        self._selected_file_path = ""

        self.stack = QStackedWidget()
        self.manual_page = self._build_manual_page()
        self.file_page = self._build_file_page()

        self.stack.addWidget(self.manual_page)
        self.stack.addWidget(self.file_page)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.addWidget(self.stack)
        self.setCentralWidget(central)

    def _build_manual_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(14)

        title = QLabel("QuantLab - Nasdaq HALT Analytics")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        mode = QLabel("Manual Mode")
        mode.setStyleSheet("font-size: 17px; font-weight: bold;")

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(11)

        self.ticker_edit = QLineEdit()
        self.ticker_edit.setPlaceholderText("Ticker ID")
        self.ticker_edit.setFixedWidth(190)
        self.ticker_edit.textChanged.connect(self._normalize_ticker)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setFixedWidth(135)

        self.period_edit = QLineEdit("36")
        self.period_edit.setValidator(QIntValidator(1, 1200, self))
        self.period_edit.setFixedWidth(120)

        period_container = QWidget()
        period_layout = QVBoxLayout(period_container)
        period_layout.setContentsMargins(0, 0, 0, 0)
        period_layout.setSpacing(3)
        period_layout.addWidget(self.period_edit)
        help_label = QLabel("Leave blank to use all available historical data.")
        help_label.setStyleSheet("font-size: 10px; color: #666666;")
        period_layout.addWidget(help_label)

        self.reason_list = self._build_reason_list()

        form.addRow("Ticker", self.ticker_edit)
        form.addRow("Start Date", self.start_date_edit)
        form.addRow("Historical Period (months)", period_container)
        form.addRow("HALT Reason Code", self.reason_list)

        calculate = QPushButton("CALCULATE")
        calculate.setFixedWidth(130)
        calculate.clicked.connect(self._validate_manual_input)

        file_button = QPushButton("File Mode")
        file_button.setFixedWidth(100)
        file_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.file_page))

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(calculate)
        buttons.addWidget(file_button)

        layout.addWidget(title)
        layout.addWidget(mode)
        layout.addSpacing(4)
        layout.addLayout(form)
        layout.addLayout(buttons)
        return page

    def _build_file_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(12)

        title = QLabel("QuantLab - Nasdaq HALT Analytics")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        mode = QLabel("File Mode")
        mode.setStyleSheet("font-size: 17px; font-weight: bold;")

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(11)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("Select an input file")
        self.file_path_edit.setFixedWidth(290)

        browse = QPushButton("Browse...")
        browse.setFixedWidth(90)
        browse.clicked.connect(self._browse_input_file)

        file_row = QHBoxLayout()
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.setSpacing(8)
        file_row.addWidget(self.file_path_edit)
        file_row.addWidget(browse)

        file_widget = QWidget()
        file_widget.setLayout(file_row)

        self.xlsx_radio = QRadioButton("XLSX")
        self.xlsx_radio.setChecked(True)
        self.csv_radio = QRadioButton("CSV")
        self.xlsx_radio.toggled.connect(self._update_file_controls)
        self.csv_radio.toggled.connect(self._update_file_controls)

        format_row = QHBoxLayout()
        format_row.setContentsMargins(0, 0, 0, 0)
        format_row.setSpacing(16)
        format_row.addWidget(self.xlsx_radio)
        format_row.addWidget(self.csv_radio)
        format_row.addStretch()

        format_widget = QWidget()
        format_widget.setLayout(format_row)

        self.comma_radio = QRadioButton("Comma (,)")
        self.semicolon_radio = QRadioButton("Semicolon (;)")
        self.comma_radio.setChecked(True)
        self.comma_radio.setEnabled(False)
        self.semicolon_radio.setEnabled(False)

        separator_row = QHBoxLayout()
        separator_row.setContentsMargins(0, 0, 0, 0)
        separator_row.setSpacing(16)
        separator_row.addWidget(self.comma_radio)
        separator_row.addWidget(self.semicolon_radio)
        separator_row.addStretch()

        separator_widget = QWidget()
        separator_widget.setLayout(separator_row)

        self.file_period_edit = QLineEdit("36")
        self.file_period_edit.setValidator(QIntValidator(1, 1200, self))
        self.file_period_edit.setFixedWidth(120)

        period_container = QWidget()
        period_layout = QVBoxLayout(period_container)
        period_layout.setContentsMargins(0, 0, 0, 0)
        period_layout.setSpacing(3)
        period_layout.addWidget(self.file_period_edit)
        help_label = QLabel("Leave blank to use all available historical data.")
        help_label.setStyleSheet("font-size: 10px; color: #666666;")
        period_layout.addWidget(help_label)

        self.file_reason_list = self._build_reason_list()

        form.addRow("Input File", file_widget)
        form.addRow("File Format", format_widget)
        form.addRow("CSV Separator", separator_widget)
        form.addRow("Historical Period (months)", period_container)
        form.addRow("HALT Reason Code", self.file_reason_list)

        validate = QPushButton("VALIDATE FILE")
        validate.setFixedWidth(130)
        validate.clicked.connect(self._validate_file_input)

        manual = QPushButton("Manual Mode")
        manual.setFixedWidth(100)
        manual.clicked.connect(lambda: self.stack.setCurrentWidget(self.manual_page))

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(validate)
        buttons.addWidget(manual)

        layout.addWidget(title)
        layout.addWidget(mode)
        layout.addSpacing(4)
        layout.addLayout(form)
        layout.addLayout(buttons)
        return page

    def _build_reason_list(self) -> QListWidget:
        widget = QListWidget()
        widget.setFixedWidth(190)
        widget.setFixedHeight(105)
        for code in REASON_CODES:
            item = QListWidgetItem(code)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if code == "LUDP"
                else Qt.CheckState.Unchecked
            )
            widget.addItem(item)
        return widget

    def _normalize_ticker(self, text: str) -> None:
        normalized = text.upper()
        if text != normalized:
            cursor = self.ticker_edit.cursorPosition()
            self.ticker_edit.blockSignals(True)
            self.ticker_edit.setText(normalized)
            self.ticker_edit.setCursorPosition(cursor)
            self.ticker_edit.blockSignals(False)

    def _selected_reason_codes(self, widget: QListWidget) -> list[str]:
        return [
            widget.item(i).text()
            for i in range(widget.count())
            if widget.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _browse_input_file(self) -> None:
        if self.csv_radio.isChecked():
            file_filter = "CSV Files (*.csv);;All Files (*.*)"
        else:
            file_filter = "Excel Files (*.xlsx);;All Files (*.*)"

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select input file",
            "",
            file_filter,
        )

        if not path:
            return

        self._selected_file_path = path
        self.file_path_edit.setText(Path(path).name)
        self.file_path_edit.setToolTip(path)

        suffix = Path(path).suffix.lower()
        if suffix == ".csv":
            self.csv_radio.setChecked(True)
        elif suffix == ".xlsx":
            self.xlsx_radio.setChecked(True)

    def _update_file_controls(self, _checked: bool) -> None:
        csv_selected = self.csv_radio.isChecked()
        self.comma_radio.setEnabled(csv_selected)
        self.semicolon_radio.setEnabled(csv_selected)

        # If the user changes the requested format after selecting a file,
        # the Browse dialog will use the matching filter on its next opening.
        if self._selected_file_path:
            self.file_path_edit.setToolTip(self._selected_file_path)

    def _validate_manual_input(self) -> None:
        ticker = self.ticker_edit.text().strip()
        if not ticker:
            QMessageBox.warning(self, "Input validation", "Ticker is required.")
            self.ticker_edit.setFocus()
            return

        if not self._selected_reason_codes(self.reason_list):
            QMessageBox.warning(
                self, "Input validation",
                "At least one HALT reason code must be selected."
            )
            return

        period = self.period_edit.text().strip() or "all available historical data"
        QMessageBox.information(
            self, "Input validation",
            "Manual input is valid.\n\n"
            f"Ticker: {ticker}\n"
            f"Observation Date: {self.start_date_edit.date().toString('dd/MM/yyyy')}\n"
            f"Historical Period: {period}\n"
            f"HALT Reason Code: {', '.join(self._selected_reason_codes(self.reason_list))}"
        )

    def _validate_file_input(self) -> None:
        path = self._selected_file_path

        if not path:
            QMessageBox.warning(self, "File validation", "Please select an input file.")
            return

        actual_suffix = Path(path).suffix.lower()
        selected_format = ".csv" if self.csv_radio.isChecked() else ".xlsx"

        if actual_suffix != selected_format:
            expected = "CSV (.csv)" if selected_format == ".csv" else "XLSX (.xlsx)"
            actual = actual_suffix or "unknown"
            QMessageBox.warning(
                self,
                "File validation",
                f"The selected file does not match the selected format.\n\n"
                f"Selected format: {expected}\n"
                f"File extension: {actual}\n\n"
                "Please select the matching format or choose another file.",
            )
            return

        if not self._selected_reason_codes(self.file_reason_list):
            QMessageBox.warning(
                self,
                "File validation",
                "At least one HALT reason code must be selected."
            )
            return

        separator = ";" if self.semicolon_radio.isChecked() else ","
        result = validate_input_file(path, separator)

        status = "PASS" if result.valid else "FAILED"
        details = [
            f"File              {result.file_name}",
            f"Format            {result.file_format}",
            f"Observations      {result.observation_count}",
            "",
            f"Date column       {'Found' if result.date_column_found else 'Missing'}",
            f"Ticker column     {'Found' if result.ticker_column_found else 'Missing'}",
            f"Invalid dates     {result.invalid_dates}",
            f"Empty tickers     {result.empty_tickers}",
        ]

        if result.errors:
            details.extend(["", "Errors:"])
            details.extend(result.errors)

        QMessageBox.information(
            self,
            f"File Validation - {status}",
            "\n".join(details),
        )
