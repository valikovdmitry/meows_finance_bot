from pathlib import Path
from zoneinfo import ZoneInfo

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    Defaults,
    MessageHandler,
    ConversationHandler,
    filters,
)

from config import TOKEN, BOT_TIMEZONE
from bot.states import WAITING_FOR_CATEGORY
from bot.handlers.start import start
from bot.handlers.update import update
from bot.handlers.shortcuts import quick_update, quick_test, quick_reminder_now, send_test_message
from bot.handlers.reminders import handle_reminder_reply, on_startup_schedule
from bot.handlers.reminder_setup import (
    ASK_DATE,
    ASK_FREQUENCY,
    ASK_TEXT,
    ASK_TIME,
    remind_cancel,
    remind_set_date,
    remind_set_frequency,
    remind_set_text,
    remind_set_time,
    remind_start,
    reminder_delete,
    reminder_edit_start,
    reminders_list,
)
from bot.handlers.custom_reminders import handle_custom_reminder_ok
from bot.handlers.reports import today_report, week_report, month_report, category_report
from bot.handlers.process import handle_batch_action, process_data, process_photo_data, process_voice_data
from bot.messages.conversation import (
    handle_category,
    handle_post_save_action,
    handle_category_button,
    cancel,
)


READY_FILE = Path("/tmp/meows-finance-bot-ready")


async def on_startup(application: Application) -> None:
    await on_startup_schedule(application)
    READY_FILE.touch()


async def on_shutdown(application: Application) -> None:
    READY_FILE.unlink(missing_ok=True)


# Основная функция для запуска бота
def main() -> None:
    # Создаём объект Application и передаем токен
    application = (
        Application.builder()
        .token(TOKEN)
        .defaults(Defaults(tzinfo=ZoneInfo(BOT_TIMEZONE)))
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    # Определяем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_data),
            MessageHandler(filters.VOICE, process_voice_data),
            MessageHandler(filters.PHOTO, process_photo_data),
            CallbackQueryHandler(handle_post_save_action, pattern=r"^(undo_last|edit_last)$"),
        ],
        states={
            WAITING_FOR_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category),
                CallbackQueryHandler(handle_category_button, pattern=r"^(catidx:\d+|cat_cancel|cat_show_all)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    reminder_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("remind", remind_start),
            CallbackQueryHandler(reminder_edit_start, pattern=r"^reminder_edit:"),
        ],
        states={
            ASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_set_text)],
            ASK_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_set_date)],
            ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_set_time)],
            ASK_FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, remind_set_frequency)],
        },
        fallbacks=[CommandHandler("cancel", remind_cancel)],
        name="reminder_setup_conversation",
        persistent=False,
    )

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("update", update))
    application.add_handler(CommandHandler("test", send_test_message))
    application.add_handler(CommandHandler("reminders", reminders_list))
    application.add_handler(MessageHandler(filters.Regex("^Update$"), quick_update))
    application.add_handler(MessageHandler(filters.Regex("^Тест$"), quick_test))
    application.add_handler(MessageHandler(filters.Regex("^Дожим сейчас$"), quick_reminder_now))
    application.add_handler(MessageHandler(filters.Regex("^(Да|Нет|да|нет)$"), handle_reminder_reply))
    application.add_handler(CommandHandler("today", today_report))
    application.add_handler(CommandHandler("week", week_report))
    application.add_handler(CommandHandler("month", month_report))
    application.add_handler(CommandHandler("category", category_report))
    application.add_handler(CallbackQueryHandler(reminder_delete, pattern=r"^reminder_delete:"))
    application.add_handler(CallbackQueryHandler(handle_custom_reminder_ok, pattern=r"^reminder_ok:"))
    application.add_handler(reminder_conv_handler)
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_batch_action, pattern=r"^batch_(save|cancel):"))

    # Запускаем бота
    application.run_polling()


if __name__ == "__main__":
    main()
