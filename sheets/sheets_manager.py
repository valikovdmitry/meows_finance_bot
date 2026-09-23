import datetime
import uuid
from config import SPREADSHEET_ID


# Запись транзакции в таблицу
def write_transaction(amount, category, description, service):
    # Уникальный ID без дополнительного запроса к таблице.
    transaction_id = uuid.uuid4().hex[:16]
    transaction_date = datetime.date.today().strftime("%d.%m.%Y")
    transaction_time = datetime.datetime.now().strftime("%H:%M:%S")

    data_to_write = [
        transaction_id,
        transaction_date,
        transaction_time,
        amount,
        category,
        description,
    ]

    response = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="A:F",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={
            "values": [data_to_write]
        },
    ).execute()

    updates = response.get("updates", {})
    updated_range = updates.get("updatedRange", "A:F")
    print(f"Данные записаны в диапазон {updated_range}: {data_to_write}")
    return transaction_id


def write_transactions(transactions, service):
    """Append several already-normalized transactions in one Sheets request."""
    now = datetime.datetime.now()
    transaction_date = now.date().strftime("%d.%m.%Y")
    transaction_time = now.strftime("%H:%M:%S")
    rows = []
    for amount, category, description in transactions:
        transaction_id = uuid.uuid4().hex[:16]
        rows.append([transaction_id, transaction_date, transaction_time, amount, category, description])

    response = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="A:F",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    updated_range = response.get("updates", {}).get("updatedRange", "A:F")
    print(f"Пакет из {len(rows)} транзакций записан в диапазон {updated_range}")
    return [row[0] for row in rows]


def get_transaction_by_id(service, spreadsheet_id, transaction_id):
    rows = get_transactions(service, spreadsheet_id)
    for row_number, row in enumerate(rows, start=2):
        if row and str(row[0]) == str(transaction_id):
            padded = list(row) + [""] * (6 - len(row))
            return row_number, padded[:6]
    return None


def delete_transaction_by_id(service, spreadsheet_id, transaction_id):
    found = get_transaction_by_id(service, spreadsheet_id, transaction_id)
    if not found:
        return False
    row_number, _row = found
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"A{row_number}:F{row_number}",
    ).execute()
    return True


def update_transaction_category(service, spreadsheet_id, transaction_id, category):
    found = get_transaction_by_id(service, spreadsheet_id, transaction_id)
    if not found:
        return None
    row_number, row = found
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"E{row_number}",
        valueInputOption="USER_ENTERED",
        body={"values": [[category]]},
    ).execute()
    row[4] = category
    return row


def update_transaction(service, spreadsheet_id, transaction_id, amount, category, description):
    found = get_transaction_by_id(service, spreadsheet_id, transaction_id)
    if not found:
        return None
    row_number, row = found
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"D{row_number}:F{row_number}",
        valueInputOption="USER_ENTERED",
        body={"values": [[amount, category, description]]},
    ).execute()
    row[3:6] = [amount, category, description]
    return row


# Удаление последней транзакции
def delete_last_transaction(service, SPREADSHEET_ID):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="A1:A1000"  # Ограничиваем диапазон строками 1-1000
    ).execute()

    # Проверяем, сколько строк заполнено
    values = result.get('values', [])

    # Если есть данные, находим последнюю заполненную строку
    if values:
        last_filled_row = len(values)

        # Очищаем эту строку (например, очищаем все столбцы в строке)
        range_to_clear = f"A{last_filled_row}:Z{last_filled_row}"

        # Очищаем строку
        service.spreadsheets().values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_clear
        ).execute()
        print(f"Строка {last_filled_row} была очищена.")
    else:
        print("Нет заполненных строк.")


# Функция получения актуального списка категорий
def get_categories(service, SPREADSHEET_ID):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Категории!A2:B100"
    ).execute()
    values = result.get('values', [])
    dict_val = {}
    for row in values:
        if not row:
            continue
        dict_val[row[0]] = row[1] if len(row) > 1 else ""
    return dict_val


def get_transactions(service, SPREADSHEET_ID):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="A2:F10000",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    return result.get("values", [])


# if __name__ == '__main__':
#     write_transaction()
