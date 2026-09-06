from pathlib import Path

from PySide6.QtCore import QDate, QSettings, Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QApplication,
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
    QProgressDialog,
    QPushButton,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.nasdaq_halts.file_validation import (
    read_input_observations,
    validate_input_file,
)
from analytics.nasdaq_halts.analysis_service import AnalysisService
from analytics.nasdaq_halts.core_source import NasdaqHaltCoreSource
from analytics.nasdaq_halts.models import AnalysisRequest
from ui.nasdaq_halts.results_page import ResultsPage
from ui.nasdaq_halts.batch_results import BatchResultsPage
from ui.nasdaq_halts.reason_codes import (
    ALL_REASON_CODE,
    DEFAULT_HALT_REASON_CODE,
    HALT_REASON_REFERENCE,
    RESUMPTION_REASON_REFERENCE,
    analytical_reason_choices,
)


REASON_CODES = analytical_reason_choices()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.settings = QSettings("QuantLab", "NasdaqHaltAnalytics")
        self._last_file_directory = self.settings.value(
            "last_file_directory", "", type=str
        )

        self.setWindowTitle("QuantLab - Nasdaq HALT Analytics")
        self.setFixedSize(620, 700)

        self._selected_file_path = ""
        self.analysis_service = AnalysisService(
                core_source=NasdaqHaltCoreSource()
            )
        self.results_page = ResultsPage(self._show_manual_page)
        self.batch_results_page = BatchResultsPage(self._show_file_page)


        self.stack = QStackedWidget()
        self.manual_page = self._build_manual_page()
        self.file_page = self._build_file_page()

        self.stack.addWidget(self.manual_page)
        self.stack.addWidget(self.file_page)
        self.stack.addWidget(self.results_page)
        self.stack.addWidget(self.batch_results_page)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.addWidget(self.stack)
        self.setCentralWidget(central)

    def _build_manual_page(self) -> QWidget:
        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title = QLabel("QuantLab - Nasdaq HALT Analytics")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        mode = QLabel("Manual Mode")
        mode.setStyleSheet("font-size: 17px; font-weight: bold;")

        # Top input section
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)

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
        period_layout.setSpacing(2)

        period_layout.addWidget(self.period_edit)

        help_label = QLabel(
            "Leave blank to use all available historical data."
        )
        help_label.setStyleSheet("font-size: 10px; color: #666666;")
        period_layout.addWidget(help_label)

        form.addRow("Ticker", self.ticker_edit)
        form.addRow("Start Date", self.start_date_edit)
        form.addRow("Historical Period (months)", period_container)

        # Reason-code section kept separate so it does not stretch
        # the three input rows vertically.
        self.reason_list = self._build_reason_list()

        reason_row = QHBoxLayout()
        reason_row.setContentsMargins(0, 4, 0, 0)
        reason_row.setSpacing(18)

        reason_label = QLabel("HALT Reason Code")
        reason_label.setFixedWidth(145)

        reason_info = QPushButton("i")
        reason_info.setFixedSize(32, 32)
        reason_info.setToolTip("Nasdaq HALT / RESUMPTION reason-code reference")
        reason_info.setStyleSheet(
            "QPushButton {"
            "font-size: 18px;"
            "font-weight: bold;"
            "border: 2px solid #4A90E2;"
            "border-radius: 15px;"
            "background: white;"
            "color: #2F6FB2;"
            "padding: 0px;"
            "}"
            "QPushButton:hover { background: #EEF6FF; }"
        )
        reason_info.clicked.connect(self._show_reason_code_reference)

        reason_row.addWidget(reason_label)
        reason_row.addWidget(self.reason_list)
        reason_row.addWidget(reason_info, 0, Qt.AlignmentFlag.AlignTop)
        reason_row.addStretch()

        # Buttons
        calculate = QPushButton("CALCULATE")
        calculate.setFixedWidth(130)
        calculate.clicked.connect(self._validate_manual_input)

        file_button = QPushButton("File Mode")
        file_button.setFixedWidth(100)
        file_button.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.file_page)
        )

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(calculate)
        buttons.addWidget(file_button)

        layout.addWidget(title)
        layout.addWidget(mode)
        layout.addSpacing(4)
        layout.addLayout(form)
        layout.addLayout(reason_row)
        layout.addStretch()
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

        file_reason_container = QWidget()
        file_reason_layout = QHBoxLayout(file_reason_container)
        file_reason_layout.setContentsMargins(0, 0, 0, 0)
        file_reason_layout.setSpacing(8)
        file_reason_layout.addWidget(self.file_reason_list)

        file_reason_info = QPushButton("i")
        file_reason_info.setFixedSize(32, 32)
        file_reason_info.setToolTip(
            "Nasdaq HALT / RESUMPTION reason-code reference"
        )
        file_reason_info.setStyleSheet(
            "QPushButton {"
            "font-size: 18px;"
            "font-weight: bold;"
            "border: 2px solid #4A90E2;"
            "border-radius: 15px;"
            "background: white;"
            "color: #2F6FB2;"
            "padding: 0px;"
            "}"
            "QPushButton:hover { background: #EEF6FF; }"
        )
        file_reason_info.clicked.connect(self._show_reason_code_reference)
        file_reason_layout.addWidget(
            file_reason_info,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        file_reason_layout.addStretch()

        form.addRow("Input File", file_widget)
        form.addRow("File Format", format_widget)
        form.addRow("CSV Separator", separator_widget)
        form.addRow("Historical Period (months)", period_container)
        form.addRow("HALT Reason Code", file_reason_container)

        validate = QPushButton("CALCULATE")
        validate.setFixedWidth(130)
        validate.clicked.connect(self._calculate_file_input)

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

        for code in REASON_CODES:
            item = QListWidgetItem(code)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

            item.setCheckState(
                Qt.CheckState.Checked
                if code == DEFAULT_HALT_REASON_CODE
                else Qt.CheckState.Unchecked
            )

            widget.addItem(item)

        # Give Qt enough room for every analytical choice without a scrollbar.
        widget.setFixedHeight(len(REASON_CODES) * 30 + 4)

        widget.itemChanged.connect(
            lambda item: self._handle_reason_code_change(widget, item)
        )

        return widget


    def _handle_reason_code_change(
        self,
        widget: QListWidget,
        item: QListWidgetItem,
    ) -> None:
        """Keep ALL mutually exclusive with explicit HALT reason codes."""
        widget.blockSignals(True)
        try:
            if item.text() == ALL_REASON_CODE:
                if item.checkState() == Qt.CheckState.Checked:
                    for i in range(1, widget.count()):
                        widget.item(i).setCheckState(Qt.CheckState.Unchecked)
                elif not self._selected_reason_codes(widget):
                    self._set_default_reason(widget)
                return

            if item.checkState() == Qt.CheckState.Checked:
                all_item = widget.item(0)
                all_item.setCheckState(Qt.CheckState.Unchecked)
                return

            if not self._selected_reason_codes(widget):
                self._set_default_reason(widget)
        finally:
            widget.blockSignals(False)

    def _set_default_reason(self, widget: QListWidget) -> None:
        for i in range(widget.count()):
            widget.item(i).setCheckState(
                Qt.CheckState.Checked
                if widget.item(i).text() == DEFAULT_HALT_REASON_CODE
                else Qt.CheckState.Unchecked
            )

    def _show_reason_code_reference(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Nasdaq Reason Code Reference")
        dialog.resize(620, 620)

        layout = QVBoxLayout(dialog)

        intro = QLabel(
            "HALT and RESUMPTION codes have different analytical meanings. "
            "T3 is a RESUMPTION action code and is therefore not offered as "
            "a normal HALT-reason selector."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        for title_text, rows in (
            ("HALT reason codes", HALT_REASON_REFERENCE),
            ("RESUMPTION reason codes", RESUMPTION_REASON_REFERENCE),
        ):
            title = QLabel(title_text)
            title.setStyleSheet("font-weight: bold;")
            layout.addWidget(title)

            table = QTableWidget(len(rows), 3)
            table.setHorizontalHeaderLabels(["Code", "Description", "Type"])
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
            table.setColumnWidth(0, 85)
            table.setColumnWidth(1, 380)
            table.horizontalHeader().setStretchLastSection(True)

            for row_index, (code, description, code_type) in enumerate(rows):
                code_item = QTableWidgetItem(code)
                code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                description_item = QTableWidgetItem(description)
                type_item = QTableWidgetItem(code_type)
                type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                table.setItem(row_index, 0, code_item)
                table.setItem(row_index, 1, description_item)
                table.setItem(row_index, 2, type_item)

            table.setMinimumHeight(min(250, 30 + len(rows) * 24))
            layout.addWidget(table)

        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)

        dialog.exec()

    def _normalize_ticker(self, text: str) -> None:
        normalized = text.upper()
        if text != normalized:
            cursor = self.ticker_edit.cursorPosition()
            self.ticker_edit.blockSignals(True)
            self.ticker_edit.setText(normalized)
            self.ticker_edit.setCursorPosition(cursor)
            self.ticker_edit.blockSignals(False)

    def _selected_reason_codes(self, widget: QListWidget) -> list[str]:
        selected = [
            widget.item(i).text()
            for i in range(widget.count())
            if widget.item(i).checkState() == Qt.CheckState.Checked
        ]
        if ALL_REASON_CODE in selected:
            return [ALL_REASON_CODE]
        return selected

    def _browse_input_file(self) -> None:
        if self.csv_radio.isChecked():
            file_filter = "CSV Files (*.csv);;All Files (*.*)"
        else:
            file_filter = "Excel Files (*.xlsx);;All Files (*.*)"

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select input file",
            self._last_file_directory,
            file_filter,
        )

        if not path:
            return

        self._selected_file_path = path
        self.file_path_edit.setText(Path(path).name)
        self.file_path_edit.setToolTip(path)

        self._last_file_directory = str(Path(path).parent)
        self.settings.setValue(
            "last_file_directory",
            self._last_file_directory,
        )

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
            QMessageBox.warning(
                self,
                "Input validation",
                "Ticker is required.",
            )
            self.ticker_edit.setFocus()
            return

        reason_codes = self._selected_reason_codes(self.reason_list)

        if not reason_codes:
            QMessageBox.warning(
                self,
                "Input validation",
                "At least one HALT reason code must be selected.",
            )
            return

        observation_date = self.start_date_edit.date().toPython()
        period_text = self.period_edit.text().strip()
        lookback_months = int(period_text) if period_text else None

        request = AnalysisRequest(
            ticker=ticker,
            observation_date=observation_date,
            lookback_months=lookback_months,
            reason_codes=tuple(reason_codes),
        )

        try:
            result = self.analysis_service.analyze(request)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Analysis error",
                f"The analysis could not be completed.\n\n{exc}",
            )
            return

        self.results_page.set_observation_context(
            ticker=result.ticker,
            observation_date=result.observation_date.strftime("%d/%m/%Y"),
            period=(
                f"{lookback_months} months"
                if lookback_months is not None
                else "All available historical data"
            ),
            reasons=", ".join(result.reason_codes),
        )

        values = {
            "Metric 1": result.metric_1,
            "Metric 2": result.metric_2,
            "Metric 3": result.metric_3,
            "Metric 4": result.metric_4,
            "Metric 5": result.metric_5,
            "Metric 6": result.metric_6,
            "Metric 7": result.metric_7,
            "Metric 8": result.metric_8,
            "Metric 9": result.metric_9,
            "Metric 10": result.metric_10,
            "Metric 11": result.metric_11,
        }

        self.results_page.set_values(values)
        self.stack.setCurrentWidget(self.results_page)

    def _show_manual_page(self) -> None:
        self.stack.setCurrentWidget(self.manual_page)

    def _show_file_page(self) -> None:
        self.stack.setCurrentWidget(self.file_page)

    def _calculate_file_input(self) -> None:
        path = self._selected_file_path

        if not path:
            QMessageBox.warning(
                self,
                "File analysis",
                "Please select an input file.",
            )
            return

        actual_suffix = Path(path).suffix.lower()
        selected_format = ".csv" if self.csv_radio.isChecked() else ".xlsx"

        if actual_suffix != selected_format:
            expected = "CSV (.csv)" if selected_format == ".csv" else "XLSX (.xlsx)"
            actual = actual_suffix or "unknown"
            QMessageBox.warning(
                self,
                "File analysis",
                f"The selected file does not match the selected format.\n\n"
                f"Selected format: {expected}\n"
                f"File extension: {actual}",
            )
            return

        selected_reasons = self._selected_reason_codes(self.file_reason_list)
        if not selected_reasons:
            QMessageBox.warning(
                self,
                "File analysis",
                "At least one HALT reason code must be selected.",
            )
            return

        separator = ";" if self.semicolon_radio.isChecked() else ","
        validation = validate_input_file(path, separator)

        if not validation.valid:
            details = "\n".join(validation.errors)
            QMessageBox.warning(
                self,
                "File validation failed",
                f"Observations: {validation.observation_count}\n"
                f"Invalid dates: {validation.invalid_dates}\n"
                f"Empty tickers: {validation.empty_tickers}\n\n"
                f"{details}",
            )
            return

        period_text = self.file_period_edit.text().strip()
        lookback_months = int(period_text) if period_text else None

        try:
            observations = read_input_observations(path, separator)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "File read error",
                f"The validated file could not be read.\n\n{exc}",
            )
            return

        output_rows = []
        failures = []

        total_observations = len(observations)
        progress = QProgressDialog(
            "Preparing calculations...",
            "Cancel",
            0,
            total_observations,
            self,
        )
        progress.setWindowTitle("QuantLab - Calculating")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()

        cancelled = False

        for index, (observation_datetime, ticker) in enumerate(
            observations,
            start=1,
        ):
            if progress.wasCanceled():
                cancelled = True
                break

            progress.setLabelText(
                f"Calculating {index} of {total_observations}: {ticker}"
            )
            QApplication.processEvents()

            row_number = index + 1
            request = AnalysisRequest(
                ticker=ticker,
                observation_date=observation_datetime.date(),
                lookback_months=lookback_months,
                reason_codes=tuple(selected_reasons),
            )

            try:
                result = self.analysis_service.analyze(request)
            except Exception as exc:
                failures.append(f"Row {row_number} ({ticker}): {exc}")
            else:
                row = {
                    "Date": result.observation_date.strftime("%d/%m/%Y"),
                    "Ticker": result.ticker,
                }
                row.update(result.as_dict())
                output_rows.append(row)

            progress.setValue(index)
            QApplication.processEvents()

        progress.close()

        if cancelled:
            QMessageBox.information(
                self,
                "File analysis cancelled",
                f"Calculation cancelled after "
                f"{len(output_rows) + len(failures)} of "
                f"{total_observations} observations.",
            )
            return

        if not output_rows:
            message = "No observation could be calculated."
            if failures:
                message += "\n\n" + "\n".join(failures[:10])
            QMessageBox.critical(self, "File analysis", message)
            return

        self.batch_results_page.set_source_directory(
            str(Path(path).parent)
        )
        self.batch_results_page.set_rows(output_rows)
        self.stack.setCurrentWidget(self.batch_results_page)

        if failures:
            QMessageBox.warning(
                self,
                "File analysis completed with errors",
                f"Successful: {len(output_rows)}\n"
                f"Failed: {len(failures)}\n\n"
                + "\n".join(failures[:10]),
            )

