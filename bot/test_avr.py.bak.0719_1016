from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook

from bot.avr import generate_ks2, generate_ks6, load_pricing


def _write_ejo(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ежедневный отчет"
    rows = [
        ("2.1.1", "Планировка", "м3", 1007, 10, 14),
        ("2.1.2", "Разработка грунта", "м3", 20, 3.5, 3.5),
        ("7.1.1", "Сети", "м", 30, 0, 5),
        ("9.9.9", "Новая работа", "шт", 8, 2, 2),
        ("2.9.9", "Без факта", "шт", 5, 0, 0),
    ]
    for row_number, (code, description, unit, plan, monthly, cumulative) in enumerate(rows, 24):
        sheet.cell(row_number, 3, code)
        sheet.cell(row_number, 4, description)
        sheet.cell(row_number, 10, unit)
        sheet.cell(row_number, 11, plan)
        sheet.cell(row_number, 16, monthly)
        sheet.cell(row_number, 19, cumulative)
    workbook.save(path)


def _write_pricing(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ВОР"
    for row_number, (code, price) in enumerate((("2.1.1", 600), ("2.1.2", 11800), ("7.1.1", 50)), 1):
        sheet.cell(row_number, 2, code)
        sheet.cell(row_number, 6, price)
    workbook.save(path)


def test_pricing_uses_exact_vor_code_and_column_f(tmp_path):
    pricing_path = tmp_path / "pricing.xlsx"
    _write_pricing(pricing_path)
    pricing = load_pricing(pricing_path)
    assert pricing["2.1.1"]["unit_price"] == 600
    assert "2.1" not in pricing


def test_generate_ks2_from_ejo(tmp_path, monkeypatch):
    ejo_path = tmp_path / "ejo.xlsx"
    pricing_path = tmp_path / "pricing.xlsx"
    _write_ejo(ejo_path)
    _write_pricing(pricing_path)
    monkeypatch.setenv("KS2_CUSTOMER", "Тестовый заказчик")
    monkeypatch.setenv("KS2_ADVANCE_RETENTION_PERCENT", "10")
    monkeypatch.setenv("KS2_WARRANTY_RETENTION_PERCENT", "5")

    path, summary = generate_ks2(date(2026, 7, 1), date(2026, 7, 31),
                                 pricing_path, ejo_path, tmp_path)

    assert Path(path).exists()
    workbook = load_workbook(path, data_only=True)
    sheet = workbook["КС-2"]
    assert sheet["B1"].value == "Тестовый заказчик"
    description_rows = {sheet.cell(row, 2).value: row for row in range(14, sheet.max_row + 1)}
    plan_row = description_rows["Планировка"]
    assert sheet.cell(plan_row, 4).value == 1007
    assert sheet.cell(plan_row, 5).value == 600
    assert sheet.cell(plan_row, 7).value == 4
    assert sheet.cell(plan_row, 9).value == 10
    assert sheet.cell(plan_row, 11).value == 14
    assert "Без факта" not in description_rows
    assert summary["total"] == Decimal("47300")
    assert summary["missing_prices"] == ["9.9.9"]


def test_generate_ks6_cumulative_and_groups_by_first_digit(tmp_path):
    ejo_path = tmp_path / "ejo.xlsx"
    pricing_path = tmp_path / "pricing.xlsx"
    _write_ejo(ejo_path)
    _write_pricing(pricing_path)

    path, summary = generate_ks6(date(2026, 7, 31), pricing_path, ejo_path, tmp_path)

    assert Path(path).name == "КС-6_2026-07.xlsx"
    workbook = load_workbook(path, data_only=True)
    sheet = workbook["КС-6"]
    code_rows = {sheet.cell(row, 1).value: row for row in range(5, sheet.max_row + 1)}
    assert sheet.cell(code_rows["2.1.1"], 6).value == 14
    assert sheet.cell(code_rows["2.1.1"], 7).value == 993
    assert "Этап 7" in code_rows
    assert "Этап 9" in code_rows
    assert summary["total"] == Decimal("49950")
    assert summary["missing_prices"] == ["9.9.9"]
