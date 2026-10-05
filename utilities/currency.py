import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


AUTO_VND_THRESHOLD = Decimal("200000")
VND_TO_RUB_PER_THOUSAND = Decimal("3")


@dataclass(frozen=True)
class NormalizedAmount:
    amount_rub: Decimal
    source_amount: Decimal
    source_currency: str

    @property
    def was_converted(self) -> bool:
        return self.source_currency == "VND"


def _decimal(value: object) -> Decimal:
    normalized = str(value).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Некорректная сумма") from exc
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля")
    return amount


def has_explicit_vnd(text: str) -> bool:
    normalized = (text or "").casefold().replace("ё", "е")
    return bool(re.search(r"(?:\bvnd\b|₫|\bдонг\w*\b)", normalized))


def normalize_amount(
    amount: object,
    context_text: str = "",
    declared_currency: str | None = None,
) -> NormalizedAmount:
    source_amount = _decimal(amount)
    declared = str(declared_currency or "RUB").upper().strip()
    if declared not in {"RUB", "VND"}:
        raise ValueError("Неизвестная валюта")

    if has_explicit_vnd(context_text) or declared == "VND" or source_amount > AUTO_VND_THRESHOLD:
        currency = "VND"
    else:
        currency = "RUB"

    amount_rub = source_amount
    if currency == "VND":
        amount_rub = (source_amount / Decimal("1000") * VND_TO_RUB_PER_THOUSAND).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    return NormalizedAmount(
        amount_rub=amount_rub,
        source_amount=source_amount,
        source_currency=currency,
    )
