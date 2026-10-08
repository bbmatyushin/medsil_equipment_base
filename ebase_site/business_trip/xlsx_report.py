"""Отчёт по денежным средствам за месяц (Excel) по командировкам сотрудника.

Раскладка, размеры колонок/строк, объединения и рамки повторяют образец
``docs/business_trip/files/КОМАНДИРОВКИ.xlsx``:

* B2 — «Ф.И.О. …», F2/H2 — заголовок и период;
* C5:D19 — «Получено» (12 пустых строк под ручной ввод, ИТОГО в 19-й строке);
* A22:D35 — «перечислено по командиравкам» (11 строк, ИТОГО в 35-й строке);
* C37:D44 — «остаток на начало/конец месяца» (только заголовки);
* F5:H45 — «израсходовано» (38 строк, ИТОГО в 45-й строке);
* C48:D50 / F48:G50 — «ИТОГО получено» / «ИТОГО расход».

Если командировок больше 11 или затрат больше 38, таблица растягивается вниз,
а блоки под ней сдвигаются на столько же строк.
"""

import calendar
import math
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

# --- Сетка образца ---
RECEIVED_FIRST_ROW = 7
RECEIVED_ROWS = 12  # строки 7–18, ИТОГО — 19
ALLOWANCE_TITLE_ROW = 22
ALLOWANCE_ROWS = 11  # строки 24–34, ИТОГО — 35
SPENT_FIRST_ROW = 7
SPENT_ROWS = 38  # строки 7–44, ИТОГО — 45
TOTALS_ROW = 48  # объединённые строки 48–50

COLUMN_WIDTHS = {
    "A": 14.43,
    "B": 11.43,
    "C": 24.57,
    "D": 20.14,
    "E": 2.29,
    "F": 16.72,
    "G": 24.43,
    "H": 25.86,
}
# Высоты строк 1–21 (выше блоков, которые могут сдвигаться)
TOP_ROW_HEIGHTS = {
    1: 15.0,
    2: 17.35,
    3: 17.35,
    4: 15.0,
    5: 15.0,
    6: 29.25,
    7: 19.5,
    8: 19.5,
    9: 16.5,
    10: 16.5,
    11: 15.75,
    12: 18.75,
    13: 14.25,
    14: 16.5,
}
ROW_HEIGHT = 18.75
LINE_HEIGHT = 15.0  # высота одной строки текста Calibri 11

DATE_FORMAT = "dd/mmm"
MONEY_FORMAT = "#,##0.00"

_thin = Side(style="thin")
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def employee_fio(employee) -> str:
    """Фамилия Имя Отчество сотрудника."""
    return " ".join(
        part
        for part in (employee.last_name, employee.first_name, employee.patron)
        if part
    ).strip()


def report_period(year: int, month: int) -> str:
    """Период отчёта, например «01-31 июля 2026г»."""
    last_day = calendar.monthrange(year, month)[1]
    return f"01-{last_day:02d} {MONTHS_GENITIVE[month]} {year}г"


def money_report_filename(employee, year: int, month: int) -> str:
    last_name = employee.last_name or employee.username
    return f"Отчет_по_ДС_{last_name}_{year}-{month:02d}.xlsx"


def _trip_cities(trip) -> str:
    """Уникальные города пунктов командировки через запятую."""
    cities = []
    for dest in trip.destinations.all():
        if dest.city and dest.city.name not in cities:
            cities.append(dest.city.name)
    return ", ".join(cities)


def _expense_description(expense) -> str:
    description = str(expense.expense_type)
    if expense.comment:
        description += f" — {expense.comment}"
    return description


def _fit_row_height(ws, row, text, width, size=11):
    """Увеличить высоту строки, если текст с переносом не влезает в ширину.

    Высоты строк заданы явно (как в образце), поэтому Excel сам их не
    подгоняет — оцениваем число строк текста по ширине колонки в символах.
    """
    if not text:
        return
    chars_per_line = max(width * 11 / size - 1, 1)
    lines = sum(
        max(math.ceil(len(part) / chars_per_line), 1) for part in str(text).split("\n")
    )
    if lines < 2:
        return
    needed = lines * LINE_HEIGHT * size / 11
    current = ws.row_dimensions[row].height or ROW_HEIGHT
    if needed > current:
        ws.row_dimensions[row].height = needed


def _cell(
    ws,
    row,
    col,
    value=None,
    *,
    bold=False,
    size=11,
    horizontal=None,
    vertical=None,
    wrap=False,
    fmt=None,
    border=True,
):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(name="Calibri", size=size, bold=bold)
    if horizontal or vertical or wrap:
        cell.alignment = Alignment(
            horizontal=horizontal, vertical=vertical, wrap_text=wrap
        )
    if fmt:
        cell.number_format = fmt
    if border:
        cell.border = BORDER
    return cell


def _merged(ws, first_row, first_col, last_row, last_col, value=None, **style):
    """Объединённая ячейка с рамкой по всем входящим в неё ячейкам."""
    for row in range(first_row, last_row + 1):
        for col in range(first_col, last_col + 1):
            ws.cell(row=row, column=col).border = BORDER
    cell = _cell(ws, first_row, first_col, value, **style)
    if (first_row, first_col) != (last_row, last_col):
        ws.merge_cells(
            start_row=first_row,
            start_column=first_col,
            end_row=last_row,
            end_column=last_col,
        )
    return cell


def _width(first_col, last_col):
    return sum(
        COLUMN_WIDTHS[get_column_letter(col)] for col in range(first_col, last_col + 1)
    )


def _header(ws, row, first_col, last_col, text, size=11):
    """Заголовок таблицы/столбца: жирный, по центру, с переносом строк."""
    _merged(
        ws,
        row,
        first_col,
        row,
        last_col,
        text,
        bold=True,
        size=size,
        horizontal="center",
        vertical="center",
        wrap=True,
    )
    _fit_row_height(ws, row, text, _width(first_col, last_col), size)


def _total_label(ws, row, col):
    _cell(ws, row, col, "ИТОГО", bold=True, horizontal="right", vertical="center")


def build_money_report(employee, year: int, month: int, trips) -> Workbook:
    """Сформировать отчёт по денежным средствам за месяц.

    :param employee: сотрудник (``CompanyUser``)
    :param year: год отчёта
    :param month: месяц отчёта
    :param trips: командировки сотрудника за месяц; ожидается prefetch
        ``destinations__department__city`` и ``expenses__expense_type``
    :return: книга openpyxl
    """
    trips = sorted(trips, key=lambda t: (t.beg_dt, t.doc_number or 0))
    expenses = sorted(
        (expense for trip in trips for expense in trip.expenses.all()),
        key=lambda e: e.date,
    )
    # Сдвиг блоков, если данные не влезают в строки образца
    left_shift = max(len(trips) - ALLOWANCE_ROWS, 0)
    right_shift = max(len(expenses) - SPENT_ROWS, 0)

    wb = Workbook()
    ws = wb.active
    ws.title = "ОТЧЕТ"

    # --- Размеры и печать как в образце (A4, книжная, по ширине страницы) ---
    for col, width in COLUMN_WIDTHS.items():
        ws.column_dimensions[col].width = width
    totals_row = TOTALS_ROW + max(left_shift, right_shift)
    for row in range(1, totals_row + 3):
        ws.row_dimensions[row].height = TOP_ROW_HEIGHTS.get(row, ROW_HEIGHT)
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    for side in ("left", "right", "top", "bottom"):
        setattr(ws.page_margins, side, 0.196527777777778)

    # --- Шапка ---
    _cell(ws, 2, 2, f"Ф.И.О. {employee_fio(employee)}", border=False)
    title_style = dict(bold=True, size=14, border=False)
    _cell(ws, 2, 6, "Отчет по денежным средствам за ", **title_style)
    _cell(ws, 2, 8, report_period(year, month), **title_style)

    # --- «Получено» (данных в базе пока нет — пустые строки под ручной ввод) ---
    _header(ws, 5, 3, 4, "Получено")
    _header(ws, 6, 3, 3, "дата")
    _header(ws, 6, 4, 4, "сумма")
    received_last = RECEIVED_FIRST_ROW + RECEIVED_ROWS - 1
    for row in range(RECEIVED_FIRST_ROW, received_last + 1):
        _cell(ws, row, 3, fmt=DATE_FORMAT)
        _cell(ws, row, 4, fmt=MONEY_FORMAT)
    received_total_row = received_last + 1
    _total_label(ws, received_total_row, 3)
    _cell(
        ws,
        received_total_row,
        4,
        f"=SUM(D{RECEIVED_FIRST_ROW}:D{received_last})",
        fmt=MONEY_FORMAT,
    )

    # --- «перечислено по командиравкам» ---
    # Одна строка на командировку: даты командировки, города пунктов и
    # «Командировочные» (allowance_amount). Формат строк может дорабатываться
    # (например, разбивка по пунктам/подразделениям).
    row = ALLOWANCE_TITLE_ROW
    _cell(ws, row, 1)
    _header(ws, row, 2, 4, "перечислено по командиравкам")
    row += 1
    for col, title in enumerate(("Дата с", "Дата по", "Направление", "сумма"), 1):
        _header(ws, row, col, col, title)
    allowance_first = row + 1
    allowance_last = allowance_first + ALLOWANCE_ROWS + left_shift - 1
    data_style = dict(horizontal="center", vertical="center")
    for index, row in enumerate(range(allowance_first, allowance_last + 1)):
        trip = trips[index] if index < len(trips) else None
        _cell(ws, row, 1, trip and trip.beg_dt, fmt=DATE_FORMAT, **data_style)
        _cell(ws, row, 2, trip and trip.end_dt, fmt=DATE_FORMAT, **data_style)
        cities = trip and _trip_cities(trip)
        _cell(ws, row, 3, cities, wrap=True, **data_style)
        _fit_row_height(ws, row, cities, COLUMN_WIDTHS["C"])
        amount = trip and (trip.allowance_amount or Decimal("0"))
        _cell(ws, row, 4, amount, fmt=MONEY_FORMAT, **data_style)
    allowance_total_row = allowance_last + 1
    _cell(ws, allowance_total_row, 1)
    _cell(ws, allowance_total_row, 2)
    _total_label(ws, allowance_total_row, 3)
    _cell(
        ws,
        allowance_total_row,
        4,
        f"=SUM(D{allowance_first}:D{allowance_last})",
        fmt=MONEY_FORMAT,
    )

    # --- Остатки на начало/конец месяца (данных пока нет — только заголовки) ---
    row = allowance_total_row + 2
    for title in ("остаток на начало месяца", "остаток на конец месяца"):
        _header(ws, row, 3, 4, title, size=12)
        _header(ws, row + 1, 3, 3, "ДОЛГ за ООО")
        _header(ws, row + 1, 4, 4, "ДОЛГ за работником")
        ws.row_dimensions[row + 1].height = max(
            ws.row_dimensions[row + 1].height, 20.25
        )
        for col in (3, 4):
            _merged(
                ws,
                row + 2,
                col,
                row + 3,
                col,
                horizontal="center",
                vertical="center",
                fmt=MONEY_FORMAT,
            )
        row += 4
    ws.row_dimensions[row - 1].height = 18.0

    # --- «израсходовано» (затраты на поездку) ---
    _header(ws, 5, 6, 8, "израсходовано ")
    _header(ws, 6, 6, 6, "дата")
    _header(ws, 6, 7, 7, "сумма")
    _header(ws, 6, 8, 8, "описание")
    spent_last = SPENT_FIRST_ROW + SPENT_ROWS + right_shift - 1
    for index, row in enumerate(range(SPENT_FIRST_ROW, spent_last + 1)):
        expense = expenses[index] if index < len(expenses) else None
        _cell(ws, row, 6, expense and expense.date, fmt=DATE_FORMAT, **data_style)
        _cell(ws, row, 7, expense and expense.amount, fmt=MONEY_FORMAT, **data_style)
        description = expense and _expense_description(expense)
        _cell(ws, row, 8, description, wrap=True, **data_style)
        _fit_row_height(ws, row, description, COLUMN_WIDTHS["H"])
    spent_total_row = spent_last + 1
    _total_label(ws, spent_total_row, 6)
    _cell(
        ws,
        spent_total_row,
        7,
        f"=SUM(G{SPENT_FIRST_ROW}:G{spent_last})",
        fmt=MONEY_FORMAT,
    )
    _cell(ws, spent_total_row, 8)

    # --- Итоги (объединённые строки 48–50 образца) ---
    ws.row_dimensions[totals_row - 1].height = 20.25
    ws.row_dimensions[totals_row].height = 30.75
    label_style = dict(bold=True, horizontal="center", vertical="center", wrap=True)
    value_style = dict(horizontal="center", vertical="center", fmt=MONEY_FORMAT)
    last = totals_row + 2
    _merged(ws, totals_row, 3, last, 3, "ИТОГО получено", **label_style)
    _merged(ws, totals_row, 4, last, 4, f"=D{received_total_row}", **value_style)
    _merged(ws, totals_row, 6, last, 6, "ИТОГО расход", **label_style)
    _merged(
        ws,
        totals_row,
        7,
        last,
        7,
        f"=G{spent_total_row}+D{allowance_total_row}",
        **value_style,
    )

    return wb
