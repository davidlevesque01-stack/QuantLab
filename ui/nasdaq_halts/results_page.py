from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


METRIC_DEFINITIONS = [
    ("Metric 1", "Number of Halt Days"),
    ("Metric 2", "Average Halts per Halt Day"),
    ("Metric 3", "Days Since Last Halt"),
    ("Metric 4", "Average Time Between Halt Days"),
    ("Metric 5", "Sequential Halt Days Identified"),
    ("Metric 6", "Number of Sequential Halt-Day Blocks"),
    ("Metric 7", "Average Sequential Block Length"),
    ("Metric 8", "Maximum Sequential Block Length"),
    ("Metric 9", "Number of Halt Days at Close"),
    ("Metric 10", "Did the Ticker HALT the Specified Day?"),
    ("Metric 11", "Number of HALTs on the Specified Day"),
]


class ResultsPage(QWidget):
    def __init__(self, on_back) -> None:
        super().__init__()
        self._on_back = on_back
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("QuantLab - Nasdaq HALT Analytics")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        heading = QLabel("Results")
        heading.setStyleSheet("font-size: 17px; font-weight: bold;")

        self.context_label = QLabel("Observation: —")
        self.context_label.setStyleSheet("font-size: 11px;")

        historical = QLabel("Historical / Predictive Features")
        historical.setStyleSheet("font-weight: bold;")

        self.historical_table = self._make_single_result_table(
            METRIC_DEFINITIONS[:9]
        )

        observation = QLabel("Observation-Day Features")
        observation.setStyleSheet("font-weight: bold;")

        self.observation_table = self._make_single_result_table(
            METRIC_DEFINITIONS[9:]
        )

        back_button = QPushButton("Back")
        back_button.setFixedWidth(90)
        back_button.clicked.connect(self._on_back)

        layout.addWidget(title)
        layout.addWidget(heading)
        layout.addWidget(self.context_label)
        layout.addWidget(historical)
        layout.addWidget(self.historical_table, 1)
        layout.addWidget(observation)
        layout.addWidget(self.observation_table)
        layout.addWidget(back_button, 0, Qt.AlignmentFlag.AlignRight)

    def _make_single_result_table(self, definitions) -> QTableWidget:
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Metric", "Value"])
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 330)

        for number, name in definitions:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(f"{number} - {name}"))
            table.setItem(row, 1, QTableWidgetItem("—"))

        return table

    def set_observation_context(
        self, ticker: str, observation_date: str, period: str, reasons: str
    ) -> None:
        self.context_label.setText(
            f"Ticker: {ticker}    |    Observation Date: {observation_date}    |    "
            f"Period: {period}    |    HALT Reason Code: {reasons}"
        )

    def set_values(self, values: dict[str, object]) -> None:
        for table in (self.historical_table, self.observation_table):
            for row in range(table.rowCount()):
                label = table.item(row, 0).text()
                metric_key = label.split(" - ", 1)[0]
                value = values.get(metric_key, "—")
                table.setItem(row, 1, QTableWidgetItem(str(value)))

    def prepare_batch_table(self, row_count: int) -> QTableWidget:
        table = QTableWidget(row_count, 13)
        headers = ["Date", "Ticker"] + [
            name for _, name in METRIC_DEFINITIONS
        ]
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(False)

        return table
