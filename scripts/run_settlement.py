import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bot.utilities.settlement import calculate_settlement, format_settlement_report
from config import SPREADSHEET_ID
from sheets.auth import get_service
from sheets.sheets_manager import get_transactions


def main():
    rows = get_transactions(get_service(), SPREADSHEET_ID)
    print(format_settlement_report(calculate_settlement(rows)))


if __name__ == "__main__":
    main()
