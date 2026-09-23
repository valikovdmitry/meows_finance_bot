from dotenv import load_dotenv
import os


load_dotenv()

# API токены
TOKEN = os.getenv("TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
BOT_TIMEZONE = os.getenv("BOT_TIMEZONE", "Asia/Ho_Chi_Minh")
DAILY_EXPENSE_REMINDERS_ENABLED = os.getenv("DAILY_EXPENSE_REMINDERS_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Путь к Google API ключу
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "data", "creds.json")

# Путь к дамп файлу категорий
SHEETS_DUMP_FILE = os.path.join(BASE_DIR, "data", "sheets_dump.json")

# Память пользовательских соответствий "описание -> категория"
CATEGORY_MEMORY_FILE = os.path.join(BASE_DIR, "data", "category_memory.json")

# Runtime-состояние бота (например, chat_id для напоминаний)
RUNTIME_STATE_FILE = os.path.join(BASE_DIR, "data", "runtime_state.json")
