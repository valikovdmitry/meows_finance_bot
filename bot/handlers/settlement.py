import asyncio

from telegram import Update
from telegram.ext import CallbackContext

from bot.utilities.settlement import (
    SettlementNotFoundError,
    calculate_settlement,
    format_settlement_report,
    split_report,
)
from config import SPREADSHEET_ID
from sheets.auth import get_service
from sheets.sheets_manager import get_transactions


def _calculate_settlement_sync():
    rows = get_transactions(get_service(), SPREADSHEET_ID)
    return calculate_settlement(rows)


async def show_settlement(update: Update, context: CallbackContext) -> None:
    try:
        result = await asyncio.to_thread(_calculate_settlement_sync)
    except SettlementNotFoundError as exc:
        await update.effective_chat.send_message(str(exc))
        return
    except Exception as exc:
        print(f"Не удалось выполнить расчёт: {exc}")
        await update.effective_chat.send_message("Не удалось прочитать таблицу. Попробуй ещё раз.")
        return

    for message in split_report(format_settlement_report(result)):
        await update.effective_chat.send_message(message)
