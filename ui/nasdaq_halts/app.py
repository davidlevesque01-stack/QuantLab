import sys

from PySide6.QtWidgets import QApplication

from ui.nasdaq_halts.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("QuantLab - Nasdaq HALT Analytics")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
