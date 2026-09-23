from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from utilities.file_manager import load_data_from_file


DEFAULT_CATEGORIES = [
    " - Нормальная еда",
    " - Аутсайт итинг",
    " - Для дома",
    " - Вредная еда",
    " - Настя",
    " - Дима",
    " - Транспорт",
    " - Спорт, хобби",
    " - Медицина",
    " - Лекарства, БАДы",
    " - Подписки",
    " - Терапевт",
    " - Крупные",
    " - Цветы",
    " - Билеты, мероприятия",
    " - Штрафы и проценты",
    " - Связь",
    " - Миск, разное",
    " - Нераспознанное",
    " - Кофе зерна",
    " - Расчет",
    " - Покупка денег",
    " - Приход денег",
]


def get_all_categories():
    categories = load_data_from_file() or {}
    result = list(categories.keys())
    normalized = {category.strip().lstrip("-").strip().casefold() for category in result}
    for category in DEFAULT_CATEGORIES:
        key = category.strip().lstrip("-").strip().casefold()
        if key not in normalized:
            result.append(category)
            normalized.add(key)
    return result


def get_categories_for_keyboard():
    return [category for category in get_all_categories() if "нераспознан" not in category.lower()]


def build_category_keyboard(show_all=False):
    categories = get_categories_for_keyboard()
    if not show_all:
        categories = categories[:6]

    rows = []
    row = []
    for idx, category in enumerate(categories):
        row.append(
            InlineKeyboardButton(
                text=category[3:] if category.startswith(" - ") else category,
                callback_data=f"catidx:{idx}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if not show_all and len(get_categories_for_keyboard()) > 6:
        rows.append([InlineKeyboardButton(text="Показать все", callback_data="cat_show_all")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="cat_cancel")])
    return InlineKeyboardMarkup(rows)


def build_post_save_keyboard(transaction_id=None):
    undo_callback = f"undo_tx:{transaction_id}" if transaction_id else "undo_last"
    edit_callback = f"edit_tx:{transaction_id}" if transaction_id else "edit_last"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="↩️ Отменить", callback_data=undo_callback),
                InlineKeyboardButton(text="✏️ Изменить категорию", callback_data=edit_callback),
            ]
        ]
    )


def build_main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Update"), KeyboardButton("Тест"), KeyboardButton("Дожим сейчас")]],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )
