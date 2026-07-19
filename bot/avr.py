"""Generate KS-2 acceptance acts and KS-6 cumulative work journals."""

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRICING_FILE = PROJECT_ROOT / "report" / "templates" / "ВОР_с_расценками.xlsx"
EJO_FILE = PROJECT_ROOT / "bot" / "templates" / "ЕЖО_шаблон.xlsx"
OUTPUT_DIR = Path("/tmp")
OBJECT_NAME = os.getenv("KS2_OBJECT", "")
CUSTOMER = os.getenv("KS2_CUSTOMER", "")
CONTRACTOR = os.getenv("KS2_CONTRACTOR", "")
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
    """Return exact work-code keyed unit prices from VOR columns B and F."""
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    pricing = {}
    for row in sheet.iter_rows(values_only=True):
        code = _code(row[1] if len(row) > 1 else None)
        unit_price = _decimal(row[5] if len(row) > 5 else None)
        if not code or unit_price is None:
            continue
        pricing[code] = {"code": code, "unit_price": unit_price}
    workbook.close()
    return pricing


def load_ejo(path=EJO_FILE):
    """Read performed work from the canonical EJO worksheet."""
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["Ежедневный отчет"]
        rows = []
        for values in sheet.iter_rows(values_only=True):
            code = _code(values[2] if len(values) > 2 else None)
            monthly = _decimal(values[15] if len(values) > 15 else None) or Decimal("0")
            cumulative = _decimal(values[18] if len(values) > 18 else None) or Decimal("0")
            if not code or (monthly <= 0 and cumulative <= 0):
                continue
            rows.append({
                "code": code,
                "description": str(values[3]).strip() if len(values) > 3 and values[3] else MISSING_PRICE,
                "unit": str(values[9]).strip() if len(values) > 9 and values[9] else "",
                "plan_qty": _decimal(values[10] if len(values) > 10 else None) or Decimal("0"),
                "monthly_qty": monthly,
                "previous_qty": cumulative - monthly,
                "cumulative_qty": cumulative,
                "building": "Все здания",
            })
        return rows
    finally:
        workbook.close()


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _priced_ejo_rows(ejo_path, pricing_path, quantity_key):
    pricing = load_pricing(pricing_path)
    rows = []
    for item in load_ejo(ejo_path):
        price = pricing.get(item["code"], {}).get("unit_price")
        if price is None and "." in item["code"]:
            parent = item["code"].rsplit(".", 1)[0]
            price = pricing.get(parent, {}).get("unit_price")
        rows.append({**item, "unit_price": price,
                     "cost": item[quantity_key] * price if price is not None else None})
    return sorted(rows, key=lambda row: _code_sort(row["code"]))


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


def _env_decimal(name, default="0"):
    value = _decimal(os.getenv(name, default))
    return value if value is not None else Decimal(default)


def _write_ks2_header(sheet, start, end, currency):
    customer = os.getenv("KS2_CUSTOMER", "")
    contractor = os.getenv("KS2_CONTRACTOR", "")
    contract_no = os.getenv("KS2_CONTRACT_NO", "")
    contract_date = os.getenv("KS2_CONTRACT_DATE", "")
    contract_sum = os.getenv("KS2_CONTRACT_SUM", "")
    site = os.getenv("KS2_SITE", "")
    object_name = os.getenv("KS2_OBJECT", "")
    labels = (
        (1, "Заказчик:", customer), (2, "Подрядчик:", contractor),
        (3, "Стройка:", site), (4, "Объект:", object_name),
        (5, "Договор:", f"№ {contract_no} от {contract_date}; сумма {contract_sum} {currency}".strip()),
    )
    for row, label, value in labels:
        sheet.merge_cells(start_row=row, start_column=2, end_row=row, end_column=14)
        sheet.cell(row, 1, label).font = Font(bold=True)
        sheet.cell(row, 2, value)
    sheet.merge_cells("A7:N7")
    sheet["A7"] = f"АКТ № {os.getenv('KS2_ACT_NO', '___')}"
    sheet["A7"].font = Font(size=16, bold=True)
    sheet["A7"].alignment = Alignment(horizontal="center")
    sheet.merge_cells("A8:N8")
    sheet["A8"] = "о приёмке выполненных работ"
    sheet["A8"].font = Font(bold=True)
    sheet["A8"].alignment = Alignment(horizontal="center")
    sheet.merge_cells("A9:N9")
    sheet["A9"] = (f"Дата составления: {date.today():%d.%m.%Y}    "
                   f"Отчётный период: с {start:%d.%m.%Y} по {end:%d.%m.%Y}")
    sheet["A9"].alignment = Alignment(horizontal="center")


def _write_ks2_table_header(sheet):
    vertical = {1: "№ п/п", 2: "Наименование работ", 3: "Ед. изм.", 13: "Не заполняется", 14: "% выполнения работ"}
    for column, value in vertical.items():
        sheet.merge_cells(start_row=11, start_column=column, end_row=13, end_column=column)
        sheet.cell(11, column, value)
    groups = ((4, 6, "По Договору"), (7, 8, "Выполнено за предыдущий период"),
              (9, 10, "Выполнено за отчётный период"), (11, 12, "Всего с начала периода"))
    for first, last, value in groups:
        sheet.merge_cells(start_row=11, start_column=first, end_row=11, end_column=last)
        sheet.cell(11, first, value)
    subheaders = {4: "Кол-во", 5: "Цена за ед.", 6: "Сумма", 7: "Кол-во", 8: "Сумма",
                  9: "Кол-во", 10: "Сумма", 11: "Кол-во", 12: "Сумма"}
    for column, value in subheaders.items():
        sheet.merge_cells(start_row=12, start_column=column, end_row=13, end_column=column)
        sheet.cell(12, column, value)
    for row in sheet.iter_rows(min_row=11, max_row=13, min_col=1, max_col=14):
        for cell in row:
            cell.border = _BORDER
            cell.fill = _SUBHEADER_FILL
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    sheet.row_dimensions[11].height = 32
    sheet.row_dimensions[12].height = 24


def generate_ks2(start_date, end_date, pricing_path=PRICING_FILE, ejo_path=EJO_FILE, output_dir=OUTPUT_DIR):
    """Generate a 14-column KS-2 act for an inclusive reporting period."""
    start, end = _as_date(start_date), _as_date(end_date)
    if start > end:
        raise ValueError("Дата начала периода позже даты окончания")
    rows = [r for r in _priced_ejo_rows(ejo_path, pricing_path, "monthly_qty") if r["monthly_qty"] > 0]
    currency = os.getenv("KS2_CURRENCY", "сом")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "КС-2"
    _write_ks2_header(sheet, start, end, currency)
    _write_ks2_table_header(sheet)
    body_start = 14
    for item_number, item in enumerate(rows, 1):
        row_number = body_start + item_number - 1
        price = item["unit_price"]
        prior_qty = item["previous_qty"]
        current_qty = item["monthly_qty"]
        total_qty = item["cumulative_qty"]
        contract_sum = item["plan_qty"] * price if price is not None else MISSING_PRICE
        prior_sum = prior_qty * price if price is not None else MISSING_PRICE
        current_sum = current_qty * price if price is not None else MISSING_PRICE
        total_sum = total_qty * price if price is not None else MISSING_PRICE
        completion = total_qty / item["plan_qty"] if item["plan_qty"] else Decimal("0")
        values = [item_number, item["description"], item["unit"], item["plan_qty"],
                  price if price is not None else MISSING_PRICE, contract_sum,
                  prior_qty, prior_sum, current_qty, current_sum, total_qty, total_sum, None, completion]
        for col, value in enumerate(values, 1):
            sheet.cell(row_number, col, value)
        sheet.cell(row_number, 14).number_format = "0.00%"
    last_body_row = body_start + len(rows) - 1
    if rows:
        _style_data(sheet, body_start, last_body_row, tuple(range(4, 13)))

    totals_start = max(body_start, last_body_row + 1)
    report_total = sum((row["cost"] or Decimal("0")) for row in rows)
    advance_percent = _env_decimal("KS2_ADVANCE_RETENTION_PERCENT")
    warranty_percent = _env_decimal("KS2_WARRANTY_RETENTION_PERCENT")
    advance = report_total * advance_percent / Decimal("100")
    warranty = report_total * warranty_percent / Decimal("100")
    totals = (("Итого", report_total), (f"Удержание аванса ({advance_percent:g}%)", advance),
              (f"Гарантийное удержание ({warranty_percent:g}%)", warranty),
              ("К оплате", report_total - advance - warranty))
    for offset, (label, value) in enumerate(totals):
        row_number = totals_start + offset
        sheet.merge_cells(start_row=row_number, start_column=1, end_row=row_number, end_column=9)
        sheet.cell(row_number, 1, label).font = Font(bold=True)
        sheet.merge_cells(start_row=row_number, start_column=10, end_row=row_number, end_column=12)
        sheet.cell(row_number, 10, value).font = Font(bold=True)
        sheet.cell(row_number, 10).number_format = '#,##0.00'
        for row in sheet.iter_rows(min_row=row_number, max_row=row_number, min_col=1, max_col=14):
            for cell in row:
                cell.border = _BORDER

    signature_row = totals_start + len(totals) + 2
    sheet.merge_cells(start_row=signature_row, start_column=1, end_row=signature_row, end_column=6)
    sheet.cell(signature_row, 1, "Сдал (Подрядчик): __________________ / __________________")
    sheet.merge_cells(start_row=signature_row, start_column=8, end_row=signature_row, end_column=14)
    sheet.cell(signature_row, 8, "Принял (Заказчик): __________________ / __________________")
    sheet.freeze_panes = "A14"
    sheet.sheet_view.showGridLines = False
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.print_title_rows = "11:13"
    sheet.print_area = f"A1:N{signature_row}"
    for col, width in enumerate((7, 56, 10, 12, 15, 16, 12, 16, 12, 16, 12, 16, 13, 13), 1):
        sheet.column_dimensions[get_column_letter(col)].width = width

    meta = workbook.create_sheet("_meta")
    meta.sheet_state = "hidden"
    meta.append(("period_end", end.isoformat()))
    meta.append(("code", "building", "cumulative_quantity"))
    for item in rows:
        meta.append((item["code"], item["building"], item["cumulative_qty"]))
    path = Path(output_dir) / f"КС-2_{start:%Y-%m}_{end:%Y-%m}.xlsx"
    workbook.save(path)
    return str(path), summarize(rows)


def generate_ks6(as_of_date, pricing_path=PRICING_FILE, ejo_path=EJO_FILE, output_dir=OUTPUT_DIR):
    """Generate a performed-work-only cumulative KS-6 journal through a date."""
    as_of = _as_date(as_of_date)
    rows = _priced_ejo_rows(ejo_path, pricing_path, "cumulative_qty")
    phase_rows = defaultdict(list)
    for item in rows:
        try:
            phase = int(item["code"].split(".", 1)[0])
        except (TypeError, ValueError):
            phase = 0
        phase_rows[phase].append(item)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "КС-6"
    columns = ["Код", "Наименование работ", "Ед.", "Цена за ед., сом", "План, кол-во",
               "Выполнено накопительно", "Остаток", "Стоимость плана, сом", "Выполнено, сом"]
    subtitle = (f"Объект: {OBJECT_NAME} | Заказчик: {CUSTOMER} | Подрядчик: {CONTRACTOR}\n"
                f"Накопительно по состоянию на {as_of:%d.%m.%Y}")
    _setup_sheet(sheet, "ОБЩИЙ ЖУРНАЛ УЧЁТА ВЫПОЛНЕННЫХ РАБОТ (КС-6)", subtitle, columns)
    summary_rows = []
    row_number = 5
    for phase in sorted(phase_rows, key=lambda value: (value == 0, value)):
        items = phase_rows.get(phase)
        if not items:
            continue
        sheet.merge_cells(start_row=row_number, start_column=1, end_row=row_number, end_column=9)
        phase_cell = sheet.cell(row_number, 1, f"Этап {phase}" if phase else "Код без числовой фазы")
        phase_cell.font = Font(bold=True)
        phase_cell.fill = _SUBHEADER_FILL
        phase_cell.border = _BORDER
        row_number += 1
        for details in sorted(items, key=lambda value: _code_sort(value["code"])):
            code = details["code"]
            plan = details["plan_qty"]
            done = details["cumulative_qty"]
            price = details["unit_price"]
            description = details["description"]
            unit = details["unit"]
            values = [code, description, unit, price if price is not None else MISSING_PRICE,
                      plan, done, plan - done, plan * price if price is not None else MISSING_PRICE,
                      done * price if price is not None else MISSING_PRICE]
            for col, value in enumerate(values, 1):
                sheet.cell(row_number, col, value)
            _style_data(sheet, row_number, row_number, (4, 5, 6, 7, 8, 9))
            summary_rows.append({"code": code, "description": description, "building": "Все здания",
                                 "volume": done, "cost": done * price if price is not None else None,
                                 "unit_price": price})
            row_number += 1
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
