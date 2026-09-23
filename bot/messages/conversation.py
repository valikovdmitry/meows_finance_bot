import asyncio
import time

from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler

from config import SPREADSHEET_ID
from bot.states import WAITING_FOR_CATEGORY
from bot.utilities.keyboards import (
    build_category_keyboard,
    build_post_save_keyboard,
    get_categories_for_keyboard,
)
from sheets.auth import get_service
from sheets.sheets_manager import (
    delete_last_transaction,
    delete_transaction_by_id,
    get_transaction_by_id,
    update_transaction_category,
    write_transaction,
)
from utilities.text_process import find_category
from utilities.category_memory import learn_category
from utilities.reply_manager import format_reply


def _write_transaction_sync(m_sum, m_cat, m_desc):
    service = get_service()
    return write_transaction(m_sum, m_cat, m_desc, service)


def _delete_last_transaction_sync():
    service = get_service()
    delete_last_transaction(service, SPREADSHEET_ID)


def _delete_transaction_sync(transaction_id):
    service = get_service()
    return delete_transaction_by_id(service, SPREADSHEET_ID, transaction_id)


def _get_transaction_sync(transaction_id):
    service = get_service()
    return get_transaction_by_id(service, SPREADSHEET_ID, transaction_id)


def _update_transaction_category_sync(transaction_id, category):
    service = get_service()
    return update_transaction_category(service, SPREADSHEET_ID, transaction_id, category)


async def send_success_message(
    update: Update,
    context: CallbackContext,
    m_sum,
    m_cat,
    m_desc,
    elapsed_time,
    source_message_id=None,
    transaction_id=None,
):
    reply_text = format_reply(m_sum, m_cat, m_desc, elapsed_time)
    sent = await update.effective_chat.send_message(
        reply_text,
        parse_mode="HTML",
        reply_markup=build_post_save_keyboard(transaction_id),
    )
    pending = context.user_data.get("pending_tx") or {}
    if source_message_id is None:
        source_message_id = pending.get("source_message_id")
    context.user_data["last_tx"] = {
        "m_sum": m_sum,
        "m_cat": m_cat,
        "m_desc": m_desc,
        "source_message_id": source_message_id,
        "confirmation_message_id": sent.message_id,
        "transaction_id": transaction_id,
    }
    return sent


async def _safe_delete_message(update: Update, message_id: int | None):
    if message_id is None:
        return
    chat = update.effective_chat
    if chat is None:
        return
    try:
        await update.get_bot().delete_message(chat_id=chat.id, message_id=message_id)
    except Exception:
        pass


def _pending_tx(context: CallbackContext):
    if "pending_tx" in context.user_data:
        return context.user_data["pending_tx"]

    m_sum = context.user_data.get("m_sum")
    m_desc = context.user_data.get("m_desc")
    if m_sum is None:
        return None

    return {"m_sum": m_sum, "m_desc": m_desc}


async def handle_category(update: Update, context: CallbackContext) -> int:
    message = update.message.text  # Получаем новую категорию от пользователя
    m_cat = find_category(message)
    pending = _pending_tx(context)
    if not pending:
        await update.effective_chat.send_message("Нет ожидающей транзакции. Отправь сумму и описание заново.")
        return ConversationHandler.END
    m_sum = pending["m_sum"]
    m_desc = pending["m_desc"]
    memory_desc = pending.get("memory_desc", m_desc)
    start_time = context.user_data.get("start_time")
    if m_cat == '- Нераспознанное':
        await update.effective_chat.send_message(
            "Хозяин, не вижу категорию, уточни! 🥺",
            reply_markup=build_category_keyboard(),
        )
        context.user_data["pending_tx"] = pending
        return WAITING_FOR_CATEGORY
    else:
        transaction_id = pending.get("transaction_id")
        if transaction_id:
            updated = await asyncio.to_thread(_update_transaction_category_sync, transaction_id, m_cat)
            if not updated:
                await update.effective_chat.send_message("Не нашел эту транзакцию в таблице.")
                return ConversationHandler.END
        elif pending.get("replace_last"):
            await asyncio.to_thread(_delete_last_transaction_sync)
        if not transaction_id:
            transaction_id = await asyncio.to_thread(_write_transaction_sync, m_sum, m_cat, m_desc)
        await asyncio.to_thread(learn_category, memory_desc, m_cat)

        # Подтверждаем запись и выводим введенные данные
        elapsed_time = None
        if start_time is not None:
            elapsed_time = time.time() - start_time
        await _safe_delete_message(update, pending.get("prompt_message_id"))
        await _safe_delete_message(update, pending.get("confirmation_message_id"))
        await send_success_message(
            update, context, m_sum, m_cat, m_desc, elapsed_time, transaction_id=transaction_id
        )
        context.user_data.pop("pending_tx", None)
        context.user_data.pop("start_time", None)

        return ConversationHandler.END


async def handle_category_button(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    pending = _pending_tx(context)
    if not pending:
        await query.edit_message_text("Нет ожидающей транзакции. Отправь сумму и описание заново.")
        return ConversationHandler.END

    categories = get_categories_for_keyboard()
    data = query.data or ""
    if data == "cat_show_all":
        await query.edit_message_reply_markup(reply_markup=build_category_keyboard(show_all=True))
        return WAITING_FOR_CATEGORY

    if data == "cat_cancel":
        await _safe_delete_message(update, pending.get("prompt_message_id"))
        await _safe_delete_message(update, pending.get("confirmation_message_id"))
        if pending.get("replace_last"):
            original_cat = pending.get("original_cat")
            if not original_cat:
                original_cat = "- Нераспознанное"
            await send_success_message(
                update,
                context,
                pending["m_sum"],
                original_cat,
                pending["m_desc"],
                None,
                source_message_id=pending.get("source_message_id"),
                transaction_id=pending.get("transaction_id"),
            )
        elif pending.get("transaction_id"):
            await send_success_message(
                update,
                context,
                pending["m_sum"],
                pending.get("original_cat", "- Нераспознанное"),
                pending["m_desc"],
                None,
                transaction_id=pending["transaction_id"],
            )
        else:
            await _safe_delete_message(update, pending.get("source_message_id"))
        context.user_data.pop("pending_tx", None)
        context.user_data.pop("start_time", None)
        return ConversationHandler.END

    if not data.startswith("catidx:"):
        return WAITING_FOR_CATEGORY
    try:
        idx = int(data.split(":", 1)[1])
        m_cat = categories[idx]
    except (ValueError, IndexError):
        await query.edit_message_text("Категория устарела, отправь сумму заново.")
        return ConversationHandler.END

    m_sum = pending["m_sum"]
    m_desc = pending["m_desc"]
    memory_desc = pending.get("memory_desc", m_desc)
    transaction_id = pending.get("transaction_id")
    if transaction_id:
        updated = await asyncio.to_thread(_update_transaction_category_sync, transaction_id, m_cat)
        if not updated:
            await query.edit_message_text("Не нашел эту транзакцию в таблице.")
            return ConversationHandler.END
    elif pending.get("replace_last"):
        await asyncio.to_thread(_delete_last_transaction_sync)
    if not transaction_id:
        transaction_id = await asyncio.to_thread(_write_transaction_sync, m_sum, m_cat, m_desc)
    await asyncio.to_thread(learn_category, memory_desc, m_cat)

    start_time = context.user_data.get("start_time")
    elapsed_time = None
    if start_time is not None:
        elapsed_time = time.time() - start_time

    await _safe_delete_message(update, pending.get("prompt_message_id"))
    await _safe_delete_message(update, pending.get("confirmation_message_id"))
    await send_success_message(
        update, context, m_sum, m_cat, m_desc, elapsed_time, transaction_id=transaction_id
    )
    context.user_data.pop("pending_tx", None)
    context.user_data.pop("start_time", None)
    return ConversationHandler.END


async def handle_post_save_action(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data or ""

    if action.startswith("undo_tx:"):
        transaction_id = action.split(":", 1)[1]
        deleted = await asyncio.to_thread(_delete_transaction_sync, transaction_id)
        if not deleted:
            await query.edit_message_text("Эта транзакция уже удалена или не найдена.")
            return ConversationHandler.END
        await _safe_delete_message(update, query.message.message_id)
        return ConversationHandler.END

    if action.startswith("edit_tx:"):
        transaction_id = action.split(":", 1)[1]
        found = await asyncio.to_thread(_get_transaction_sync, transaction_id)
        if not found:
            await query.edit_message_text("Не нашел эту транзакцию в таблице.")
            return ConversationHandler.END
        _row_number, row = found
        prompt_message = await update.effective_chat.send_message(
            "Выбери новую категорию:",
            reply_markup=build_category_keyboard(),
        )
        context.user_data["pending_tx"] = {
            "m_sum": row[3],
            "m_desc": row[5],
            "memory_desc": row[5],
            "prompt_message_id": prompt_message.message_id,
            "confirmation_message_id": query.message.message_id,
            "transaction_id": transaction_id,
            "original_cat": row[4],
        }
        context.user_data["start_time"] = time.time()
        await query.edit_message_reply_markup(reply_markup=None)
        return WAITING_FOR_CATEGORY

    if action == "undo_last":
        last_tx = context.user_data.get("last_tx", {})
        await asyncio.to_thread(_delete_last_transaction_sync)
        await _safe_delete_message(update, last_tx.get("source_message_id"))
        await _safe_delete_message(update, last_tx.get("confirmation_message_id"))
        context.user_data.pop("last_tx", None)
        return ConversationHandler.END

    if action == "edit_last":
        last_tx = context.user_data.get("last_tx")
        if not last_tx:
            await update.effective_chat.send_message("Не нашел последнюю транзакцию для редактирования.")
            return ConversationHandler.END

        prompt_message = await update.effective_chat.send_message(
            "Выбери новую категорию:",
            reply_markup=build_category_keyboard(),
        )
        context.user_data["pending_tx"] = {
            "m_sum": last_tx["m_sum"],
            "m_desc": last_tx["m_desc"],
            "memory_desc": last_tx["m_desc"],
            "source_message_id": last_tx.get("source_message_id"),
            "prompt_message_id": prompt_message.message_id,
            "confirmation_message_id": query.message.message_id,
            "replace_last": True,
            "original_cat": last_tx["m_cat"],
        }
        context.user_data["start_time"] = time.time()
        await query.edit_message_reply_markup(reply_markup=None)
        return WAITING_FOR_CATEGORY

    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext) -> int:
    context.user_data.pop("pending_tx", None)
    context.user_data.pop("start_time", None)
    await update.message.reply_text("Диалог отменен. 🛑")
    return ConversationHandler.END
