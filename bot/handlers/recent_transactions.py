import asyncio
import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext

from config import SPREADSHEET_ID
from sheets.auth import get_service
from sheets.sheets_manager import (
    delete_transaction_by_id,
    get_formatted_transaction_by_id,
    get_recent_transactions,
)


PAGE_SIZE = 5


def _recent_page_sync(offset):
    service = get_service()
    return get_recent_transactions(service, SPREADSHEET_ID, offset, PAGE_SIZE)


def _formatted_transaction_sync(transaction_id):
    service = get_service()
    return get_formatted_transaction_by_id(service, SPREADSHEET_ID, transaction_id)


def _delete_transaction_sync(transaction_id):
    service = get_service()
    return delete_transaction_by_id(service, SPREADSHEET_ID, transaction_id)


def _clean_category(category):
    return str(category or "Без категории").strip().lstrip("-").strip()


def _short(value, limit=34):
    text = str(value or "Без описания").strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _list_content(rows, offset, total):
    text = "<b>Последние транзакции</b>"
    buttons = []
    transaction_buttons = []
    for index, row in enumerate(rows, start=1):
        transaction_id, _date, _time, amount, _category, description = row
        number = offset + index
        transaction_buttons.append(
            InlineKeyboardButton(
                f"{number}. {_short(amount, 10)} ₽ · {_short(description, 16)}",
                callback_data=f"recent_view:{transaction_id}:{offset}",
            )
        )
        if len(transaction_buttons) == 2:
            buttons.append(transaction_buttons)
            transaction_buttons = []
    if transaction_buttons:
        buttons.append(transaction_buttons)

    navigation = []
    if offset > 0:
        navigation.append(
            InlineKeyboardButton("◀️ Новее", callback_data=f"recent_page:{max(0, offset - PAGE_SIZE)}")
        )
    if offset + PAGE_SIZE < total:
        navigation.append(
            InlineKeyboardButton("Раньше ▶️", callback_data=f"recent_page:{offset + PAGE_SIZE}")
        )
    if navigation:
        buttons.append(navigation)
    buttons.append(
        [
            InlineKeyboardButton("🔄 Обновить", callback_data=f"recent_page:{offset}"),
            InlineKeyboardButton("Закрыть", callback_data="recent_close"),
        ]
    )
    return text, InlineKeyboardMarkup(buttons)


async def _render_list(update: Update, context: CallbackContext, offset=0):
    rows, total = await asyncio.to_thread(_recent_page_sync, max(0, offset))
    if not rows and offset > 0:
        offset = max(0, offset - PAGE_SIZE)
        rows, total = await asyncio.to_thread(_recent_page_sync, offset)
    if not rows:
        text = "Транзакций пока нет."
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Закрыть", callback_data="recent_close")]]
        )
    else:
        text, keyboard = _list_content(rows, offset, total)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        await update.effective_chat.send_message(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


async def show_recent_transactions(update: Update, context: CallbackContext):
    await _render_list(update, context)


async def _render_detail(query, transaction_id, offset):
    row = await asyncio.to_thread(_formatted_transaction_sync, transaction_id)
    if not row:
        await query.edit_message_text("Транзакция уже удалена или не найдена.")
        return
    _id, date, time, amount, category, description = row
    text = (
        f"<b>{html.escape(str(amount))} ₽</b>\n"
        f"{html.escape(str(description))}\n\n"
        f"Категория: <b>{html.escape(_clean_category(category))}</b>\n"
        f"Дата: {html.escape(str(date))} {html.escape(str(time))}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✏️ Исправить",
                    callback_data=f"recent_edit:{transaction_id}:{offset}",
                ),
                InlineKeyboardButton(
                    "🗑 Удалить",
                    callback_data=f"recent_delete:{transaction_id}:{offset}",
                ),
            ],
            [InlineKeyboardButton("◀️ К списку", callback_data=f"recent_page:{offset}")],
        ]
    )
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def handle_recent_action(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "recent_close":
        context.user_data.pop("pending_recent_edit", None)
        await query.delete_message()
        return

    if data.startswith("recent_page:"):
        await _render_list(update, context, int(data.rsplit(":", 1)[1]))
        return

    action, transaction_id, offset_text = data.split(":", 2)
    offset = int(offset_text)

    if action == "recent_view":
        await _render_detail(query, transaction_id, offset)
        return

    if action == "recent_edit":
        context.user_data["pending_recent_edit"] = {
            "transaction_id": transaction_id,
            "offset": offset,
            "prompt_message_id": query.message.message_id,
        }
        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    "Отмена",
                    callback_data=f"recent_edit_cancel:{transaction_id}:{offset}",
                )
            ]]
        )
        await query.edit_message_text(
            "Отправь правку текстом или голосом.\n\n"
            "Например: «не 900, а 1200», «описание — такси» или «категория Дима».",
            reply_markup=keyboard,
        )
        return

    if action == "recent_edit_cancel":
        context.user_data.pop("pending_recent_edit", None)
        await _render_detail(query, transaction_id, offset)
        return

    if action == "recent_delete":
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Удалить",
                        callback_data=f"recent_delete_confirm:{transaction_id}:{offset}",
                    ),
                    InlineKeyboardButton(
                        "Отмена",
                        callback_data=f"recent_view:{transaction_id}:{offset}",
                    ),
                ]
            ]
        )
        await query.edit_message_text("Точно удалить эту транзакцию?", reply_markup=keyboard)
        return

    if action == "recent_delete_confirm":
        deleted = await asyncio.to_thread(_delete_transaction_sync, transaction_id)
        if not deleted:
            await query.edit_message_text("Транзакция уже удалена или не найдена.")
            return
        last_tx = context.user_data.get("last_tx") or {}
        if last_tx.get("transaction_id") == transaction_id:
            context.user_data.pop("last_tx", None)
        receipt_transactions = context.user_data.get("receipt_transactions", {})
        for message_id, mapped_id in list(receipt_transactions.items()):
            if mapped_id == transaction_id:
                receipt_transactions.pop(message_id, None)
        await _render_list(update, context, offset)
