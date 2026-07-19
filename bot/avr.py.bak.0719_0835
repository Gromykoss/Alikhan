"""Generate KS-2 acceptance acts and KS-6 cumulative work journals."""

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRICING_FILE = PROJECT_ROOT / "report" / "templates" / "ВОР_с_расценками.xlsx"
OUTPUT_DIR = Path("/tmp")
OBJECT_NAME = "ТЗРК Джеруй"
CUSTOMER = "ОсОО Альянс-Алтын"
CONTRACTOR = "ОсОО АйБиКон"
MISSING_PRICE = "Требует расценки"

_THIN = Side(style="thin", color="808080")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_SUBHEADER_FILL = PatternFill("solid", fgColor="D9EAF7")


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _code(value):
    """Normalize Excel/DB work codes without altering their hierarchy."""
    if value is None:
        return ""
    if isinstance(value, float):
        value = int(value) if value.is_integer() else format(value, ".15g")
    return "".join(str(value).strip().lstrip("'").replace(",", ".").split())


def load_pricing(path=PRICING_FILE):
    """Return work-code keyed pricing from columns B:F of the priced VOR."""
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    pricing = {}
    for row in sheet.iter_rows(values_only=True):
        code = _code(row[1] if len(row) > 1 else None)
        description = row[2] if len(row) > 2 else None
        unit = row[3] if len(row) > 3 else None
        plan_qty = _decimal(row[4] if len(row) > 4 else None)
        unit_price = _decimal(row[5] if len(row) > 5 else None)
        # Some real VOR positions have short codes (for example 2.3 or 5.10).
        # Unlike section headings, they carry a unit, quantity, or price.
        if not code or not description or (code.count(".") < 2 and not (unit or plan_qty is not None or unit_price is not None)):
            continue
        pricing[code] = {
            "code": code,
            "description": str(description).strip(),
            "unit": str(unit).strip() if unit else "",
            "plan_qty": plan_qty or Decimal("0"),
            "unit_price": unit_price,
        }
    workbook.close()
    return pricing


def fetch_work_log(start_date=None, end_date=None):
    """Read positive factual volumes from OJR, optionally limited by dates."""
    from db import get_conn
    import psycopg2.extras

    clauses = ["volume > 0", "COALESCE(category, 'объём') <> 'план'"]
    params = []
    if start_date is not None:
        clauses.append("work_date >= %s::date")
        params.append(_as_date(start_date))
    if end_date is not None:
        clauses.append("work_date <= %s::date")
        params.append(_as_date(end_date))
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT vor_code, work_name, unit, volume, building, work_date
               FROM ojr_section3_work_log
               WHERE %s
               ORDER BY work_date, building, vor_code""" % " AND ".join(clauses),
            params,
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        if "cur" in locals():
            cur.close()
        conn.close()


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _filter_entries(entries, start_date=None, end_date=None):
    """Filter dated supplied entries while retaining legacy undated entries."""
    result = []
    for entry in entries:
        value = entry.get("work_date") or entry.get("date")
        if value is None:
            result.append(entry)
            continue
        work_date = _as_date(value)
        if (start_date is None or work_date >= start_date) and (end_date is None or work_date <= end_date):
            result.append(entry)
    return result


def _aggregate(entries):
    grouped = {}
    for entry in entries:
        original_code = entry.get("vor_code") or entry.get("code")
        code = _code(original_code)
        volume = _decimal(entry.get("volume")) or Decimal("0")
        if not code or volume <= 0:
            continue
        key = (code, str(entry.get("building") or "Не указано").strip())
        item = grouped.setdefault(key, {"code": code, "original_code": str(original_code).strip(),
                                        "building": key[1], "volume": Decimal("0"),
                                        "work_name": entry.get("work_name"), "unit": entry.get("unit")})
        item["volume"] += volume
    return list(grouped.values())


def _enrich(entries, pricing):
    result = []
    for item in _aggregate(entries):
        priced = pricing.get(item.get("original_code")) or pricing.get(item["code"], {})
        unit_price = priced.get("unit_price")
        result.append({
            **item,
            "description": priced.get("description") or item.get("work_name") or MISSING_PRICE,
            "unit": priced.get("unit") or item.get("unit") or "",
            "plan_qty": priced.get("plan_qty", Decimal("0")),
            "unit_price": unit_price,
            "cost": item["volume"] * unit_price if unit_price is not None else None,
        })
    return sorted(result, key=lambda row: (row["building"], _code_sort(row["code"])))


def _code_sort(code):
    return tuple(int(part) if part.isdigit() else part for part in code.split("."))


def _setup_sheet(sheet, title, subtitle, columns):
    last_col = get_column_letter(len(columns))
    sheet.merge_cells(f"A1:{last_col}1")
    sheet["A1"] = title
    sheet["A1"].font = Font(size=16, bold=True)
    sheet["A1"].alignment = Alignment(horizontal="center")
    sheet.merge_cells(f"A2:{last_col}2")
    sheet["A2"] = subtitle
    sheet["A2"].alignment = Alignment(horizontal="center", wrap_text=True)
    for index, label in enumerate(columns, 1):
        cell = sheet.cell(4, index, label)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER
    sheet.freeze_panes = "A5"
    sheet.auto_filter.ref = f"A4:{last_col}4"
    sheet.sheet_view.showGridLines = False
    sheet.row_dimensions[4].height = 42


def _style_data(sheet, first_row, last_row, numeric_columns=()):
    for row in sheet.iter_rows(min_row=first_row, max_row=last_row):
        for cell in row:
            cell.border = _BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        for col in numeric_columns:
            sheet.cell(row[0].row, col).number_format = '#,##0.00'


def generate_ks2(start_date, end_date, work_entries=None, pricing_path=PRICING_FILE, output_dir=OUTPUT_DIR):
    """Generate a KS-2 workbook for an inclusive reporting period."""
    start, end = _as_date(start_date), _as_date(end_date)
    if start > end:
        raise ValueError("Дата начала периода позже даты окончания")
    entries = fetch_work_log(start, end) if work_entries is None else _filter_entries(work_entries, start, end)
    rows = _enrich(entries, load_pricing(pricing_path))

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "КС-2"
    subtitle = (f"Объект: {OBJECT_NAME} | Заказчик: {CUSTOMER} | Подрядчик: {CONTRACTOR}\n"
                f"Период: {start:%d.%m.%Y}–{end:%d.%m.%Y} | Дата составления: {date.today():%d.%m.%Y}")
    columns = ["Код", "Наименование работ", "Ед.", "Количество", "Цена за ед., сом", "Стоимость, сом", "Здание"]
    _setup_sheet(sheet, "АКТ О ПРИЁМКЕ ВЫПОЛНЕННЫХ РАБОТ (КС-2)", subtitle, columns)
    for row_number, item in enumerate(rows, 5):
        values = [item["code"], item["description"], item["unit"], item["volume"],
                  item["unit_price"] if item["unit_price"] is not None else MISSING_PRICE,
                  item["cost"] if item["cost"] is not None else MISSING_PRICE, item["building"]]
        for col, value in enumerate(values, 1):
            sheet.cell(row_number, col, value)
    total_row = 5 + len(rows)
    sheet.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=5)
    sheet.cell(total_row, 1, "ИТОГО (без позиций, требующих расценки)").font = Font(bold=True)
    sheet.cell(total_row, 6, sum((r["cost"] or Decimal("0")) for r in rows)).font = Font(bold=True)
    _style_data(sheet, 5, total_row, (4, 5, 6))
    for col, width in enumerate((14, 60, 11, 15, 19, 20, 22), 1):
        sheet.column_dimensions[get_column_letter(col)].width = width
    path = Path(output_dir) / f"КС-2_{start:%Y-%m}_{end:%Y-%m}.xlsx"
    workbook.save(path)
    return str(path), summarize(rows)


def generate_ks6(as_of_date, work_entries=None, pricing_path=PRICING_FILE, output_dir=OUTPUT_DIR):
    """Generate a cumulative KS-6 journal from project start through as_of_date."""
    as_of = _as_date(as_of_date)
    entries = fetch_work_log(end_date=as_of) if work_entries is None else _filter_entries(work_entries, end_date=as_of)
    pricing = load_pricing(pricing_path)
    done_by_code = defaultdict(Decimal)
    log_details = {}
    for item in _aggregate(entries):
        done_by_code[item["code"]] += item["volume"]
        details = log_details.setdefault(item["code"], {})
        details["work_name"] = details.get("work_name") or item.get("work_name")
        details["unit"] = details.get("unit") or item.get("unit")
        details["original_code"] = details.get("original_code") or item.get("original_code")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "КС-6"
    columns = ["Код", "Наименование работ", "Ед.", "Цена за ед., сом", "План, кол-во",
               "Выполнено накопительно", "Остаток", "Стоимость плана, сом", "Выполнено, сом"]
    subtitle = (f"Объект: {OBJECT_NAME} | Заказчик: {CUSTOMER} | Подрядчик: {CONTRACTOR}\n"
                f"Накопительно по состоянию на {as_of:%d.%m.%Y}")
    _setup_sheet(sheet, "ОБЩИЙ ЖУРНАЛ УЧЁТА ВЫПОЛНЕННЫХ РАБОТ (КС-6)", subtitle, columns)
    summary_rows = []
    all_codes = sorted(set(pricing) | set(done_by_code), key=_code_sort)
    for row_number, code in enumerate(all_codes, 5):
        details = log_details.get(code, {})
        item = pricing.get(details.get("original_code")) or pricing.get(code, {})
        plan = item.get("plan_qty", Decimal("0"))
        done = done_by_code[code]
        price = item.get("unit_price")
        description = item.get("description") or details.get("work_name") or MISSING_PRICE
        unit = item.get("unit") or details.get("unit") or ""
        values = [code, description, unit, price if price is not None else MISSING_PRICE,
                  plan, done, plan - done, plan * price if price is not None else MISSING_PRICE,
                  done * price if price is not None else MISSING_PRICE]
        for col, value in enumerate(values, 1):
            sheet.cell(row_number, col, value)
        if done > 0:
            summary_rows.append({"code": code, "description": description, "building": "Все здания",
                                 "volume": done, "cost": done * price if price is not None else None,
                                 "unit_price": price})
    last_row = 4 + len(all_codes)
    _style_data(sheet, 5, last_row, (4, 5, 6, 7, 8, 9))
    for col, width in enumerate((14, 58, 10, 18, 15, 21, 15, 22, 20), 1):
        sheet.column_dimensions[get_column_letter(col)].width = width
    path = Path(output_dir) / f"КС-6_{as_of:%Y-%m}.xlsx"
    workbook.save(path)
    return str(path), summarize(summary_rows)


def summarize(rows):
    """Cost totals by building and top-level VOR work type."""
    by_building, by_work_type = defaultdict(Decimal), defaultdict(Decimal)
    missing = set()
    total = Decimal("0")
    for row in rows:
        if row.get("cost") is None:
            missing.add(row["code"])
            continue
        cost = row["cost"]
        total += cost
        by_building[row.get("building") or "Не указано"] += cost
        by_work_type[row["code"].split(".")[0]] += cost
    return {"total": total, "by_building": dict(by_building),
            "by_work_type": dict(by_work_type), "missing_prices": sorted(missing, key=_code_sort)}


def format_summary(summary):
    lines = [f"Итого: {summary['total']:,.2f} сом"]
    if summary["by_building"]:
        lines.append("По зданиям: " + "; ".join(f"{k}: {v:,.2f}" for k, v in summary["by_building"].items()))
    if summary["by_work_type"]:
        lines.append("По видам работ: " + "; ".join(f"этап {k}: {v:,.2f}" for k, v in summary["by_work_type"].items()))
    if summary["missing_prices"]:
        lines.append("Требуют расценки: " + ", ".join(summary["missing_prices"]))
    return "\n".join(lines)
