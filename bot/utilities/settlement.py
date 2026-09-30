import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


GOOGLE_EPOCH = dt.datetime(1899, 12, 30)
SETTLEMENT_CATEGORIES = {"расчет", "расчёт"}
CRYPTO_CATEGORIES = {"покупка денег", "покупка денек", "покупка денёк"}


class SettlementNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class SettlementTransaction:
    row_number: int
    timestamp: dt.datetime
    amount: Decimal
    category: str
    description: str


@dataclass(frozen=True)
class SettlementResult:
    last_settlement: SettlementTransaction
    crypto_rows: tuple[SettlementTransaction, ...]
    nastya_rows: tuple[SettlementTransaction, ...]
    dima_rows: tuple[SettlementTransaction, ...]
    crypto_total: Decimal
    nastya_total: Decimal
    dima_total: Decimal
    amount_to_transfer: Decimal


def normalize_category(value):
    return str(value or "").strip().lstrip("-").strip().casefold()


def parse_datetime(date_value, time_value=0):
    if isinstance(date_value, (int, float)):
        time_fraction = float(time_value or 0) if isinstance(time_value, (int, float)) else 0
        return GOOGLE_EPOCH + dt.timedelta(days=float(date_value) + time_fraction)

    raw_date = str(date_value or "").strip()
    raw_time = str(time_value or "00:00:00").strip()
    if isinstance(time_value, (int, float)):
        raw_time = str(dt.timedelta(seconds=round(float(time_value) * 86400)))

    for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
        for time_format in ("%H:%M:%S", "%H:%M"):
            try:
                return dt.datetime.strptime(
                    f"{raw_date} {raw_time}",
                    f"{date_format} {time_format}",
                )
            except ValueError:
                continue
    return None


def parse_amount(value):
    normalized = str(value).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def calculate_settlement(rows):
    parsed = []
    for row_number, row in enumerate(rows, start=2):
        if len(row) < 5:
            continue
        timestamp = parse_datetime(row[1], row[2] if len(row) > 2 else 0)
        amount = parse_amount(row[3])
        if timestamp is None or amount is None:
            continue
        parsed.append(
            SettlementTransaction(
                row_number=row_number,
                timestamp=timestamp,
                amount=amount,
                category=normalize_category(row[4]),
                description=str(row[5]).strip() if len(row) > 5 else "",
            )
        )

    settlements = [item for item in parsed if item.category in SETTLEMENT_CATEGORIES]
    if not settlements:
        raise SettlementNotFoundError("В таблице не найден предыдущий расчёт.")

    last_settlement = max(settlements, key=lambda item: item.row_number)
    after = [item for item in parsed if item.row_number > last_settlement.row_number]
    crypto_rows = tuple(item for item in after if item.category in CRYPTO_CATEGORIES)
    nastya_rows = tuple(item for item in after if item.category == "настя")
    dima_rows = tuple(item for item in after if item.category == "дима")

    crypto_total = sum((item.amount for item in crypto_rows), Decimal("0"))
    nastya_total = sum((item.amount for item in nastya_rows), Decimal("0"))
    dima_total = sum((item.amount for item in dima_rows), Decimal("0"))
    amount_to_transfer = (crypto_total - nastya_total + dima_total) / Decimal("2")

    return SettlementResult(
        last_settlement=last_settlement,
        crypto_rows=crypto_rows,
        nastya_rows=nastya_rows,
        dima_rows=dima_rows,
        crypto_total=crypto_total,
        nastya_total=nastya_total,
        dima_total=dima_total,
        amount_to_transfer=amount_to_transfer,
    )


def format_amount(value):
    formatted = f"{value:,.2f}".replace(",", " ")
    return formatted.rstrip("0").rstrip(".")


def _format_section(title, rows, total):
    lines = [f"{title} — {format_amount(total)} ₽"]
    if not rows:
        lines.append("• Нет транзакций")
        return lines

    for item in rows:
        description = item.description or "Без описания"
        lines.append(
            f"• {item.timestamp:%d.%m.%Y %H:%M} · {description} · "
            f"{format_amount(item.amount)} ₽ · {item.category} · строка {item.row_number}"
        )
    return lines


def format_settlement_report(result):
    lines = [
        "🧮 Расчёт",
        (
            f"Последний расчёт: {result.last_settlement.timestamp:%d.%m.%Y %H:%M} "
            f"· строка {result.last_settlement.row_number}"
        ),
        "",
    ]
    lines.extend(_format_section("Покупка денег", result.crypto_rows, result.crypto_total))
    lines.append("")
    lines.extend(_format_section("Настя", result.nastya_rows, result.nastya_total))
    lines.append("")
    lines.extend(_format_section("Дима", result.dima_rows, result.dima_total))
    lines.extend(
        [
            "",
            "Формула:",
            (
                f"({format_amount(result.crypto_total)} − {format_amount(result.nastya_total)} "
                f"+ {format_amount(result.dima_total)}) ÷ 2 = "
                f"{format_amount(result.amount_to_transfer)} ₽"
            ),
            "",
        ]
    )

    if result.amount_to_transfer > 0:
        lines.append(f"Итого: Дима должен Насте {format_amount(result.amount_to_transfer)} ₽")
    elif result.amount_to_transfer < 0:
        lines.append(f"Итого: Настя должна Диме {format_amount(abs(result.amount_to_transfer))} ₽")
    else:
        lines.append("Итого: никто никому ничего не должен")
    return "\n".join(lines)


def split_report(text, limit=3900):
    messages = []
    current = []
    current_length = 0
    for line in text.splitlines():
        added_length = len(line) + (1 if current else 0)
        if current and current_length + added_length > limit:
            messages.append("\n".join(current))
            current = [line]
            current_length = len(line)
        else:
            current.append(line)
            current_length += added_length
    if current:
        messages.append("\n".join(current))
    return messages
