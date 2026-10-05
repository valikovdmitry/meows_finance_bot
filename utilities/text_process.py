from utilities.file_manager import load_data_from_file
import re


def find_args(text):
    amount, text_without_amount = _extract_amount(text)
    if not amount:
        return 0, 0, 0

    cat, cat_alias = _match_category_with_alias(text_without_amount)
    if cat == "- Нераспознанное":
        return amount, cat, text_without_amount.strip()

    desc = text_without_amount
    if cat_alias:
        desc = _remove_alias_once(text_without_amount, cat_alias)
    return amount, cat, desc.strip()


def find_amount_and_description(text):
    amount, text_without_amount = _extract_amount(text)
    return amount, text_without_amount.strip()


def find_category(text):
    cat, _alias = _match_category_with_alias(text)
    return cat


def _normalize_text(text):
    cleaned = text.lower().replace("ё", "е")
    cleaned = re.sub(r"[^\w\s.,-]", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned, flags=re.UNICODE).strip()
    return cleaned


def _extract_amount(text):
    # Поддержка: 150, 150к, 200 тысяч, 3 миллиона, 3 000 000, 120,5.
    match = re.search(
        r"(?<!\w)"
        r"((?:\d{1,3}(?:[\s\u00a0]\d{3})+|\d+)(?:[.,]\d+)?)"
        r"(?:\s*(к|k|тыс(?:яча|ячи|ячу|яч)?|млн|миллион(?:а|ов)?))?"
        r"(?:\s*(?:vnd|₫|вьетнамск\w*\s+донг\w*|донг\w*|rub|rur|₽|руб\w*))?",
        text.casefold().replace("ё", "е"),
        flags=re.UNICODE,
    )
    if not match:
        return 0, text

    raw_num = match.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")
    suffix = match.group(2)
    try:
        amount = float(raw_num)
    except ValueError:
        return 0, text

    if suffix in {"к", "k"} or (suffix and suffix.startswith("тыс")):
        amount *= 1000
    elif suffix in {"млн", "миллион", "миллиона", "миллионов"}:
        amount *= 1_000_000

    text_without_amount = (text[:match.start()] + " " + text[match.end():]).strip()
    text_without_amount = re.sub(r"\s+", " ", text_without_amount)
    return amount, text_without_amount


def _build_aliases_for_category(key, value):
    aliases = []
    base = key[3:] if key.startswith(" - ") else key
    aliases.append(base.strip().lower())
    for part in value.split(","):
        alias = part.strip().lower()
        if alias:
            aliases.append(alias)
    # Длинные алиасы проверяем первыми.
    aliases = sorted(set(aliases), key=len, reverse=True)
    return aliases


def _match_category_with_alias(text):
    dict_val = load_data_from_file()
    if not dict_val:
        return "- Нераспознанное", ""

    normalized = _normalize_text(text)
    best = None
    for key, value in dict_val.items():
        for alias in _build_aliases_for_category(key, value):
            idx = normalized.find(alias)
            if idx < 0:
                continue
            candidate = (idx, -len(alias), key, alias)
            if best is None or candidate < best:
                best = candidate

    if best is None:
        return "- Нераспознанное", ""
    return best[2], best[3]


def _remove_alias_once(text, alias):
    pattern = re.compile(re.escape(alias), flags=re.IGNORECASE)
    return pattern.sub("", text, count=1).strip()
