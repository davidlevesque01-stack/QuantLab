"""CLI entry point for the replay viewer (BT-06a).

Usage:
    python -m ui.replay.app --ticker GPUS --trading-day 2026-08-14
"""

import argparse
import sys
from datetime import date

from PySide6.QtWidgets import QApplication

from ui.replay.main_window import MainWindow


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--trading-day", required=True, type=date.fromisoformat)

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    app = QApplication(sys.argv)
    app.setApplicationName("QuantLab - Replay Viewer")

    window = MainWindow(ticker=args.ticker, trading_day=args.trading_day)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
