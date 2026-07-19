from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from bot.avr import generate_ks2, generate_ks6, load_pricing


SAMPLES = [
    {"vor_code": "2.1.1", "work_name": "Планировка", "unit": "м3", "volume": 4,
     "building": "Общежитие", "work_date": date(2026, 6, 30)},
    {"vor_code": "2.1.1", "work_name": "Планировка", "unit": "м3", "volume": 10,
     "building": "Общежитие", "work_date": date(2026, 7, 10)},
    {"vor_code": "2.1.2", "work_name": "Разработка грунта", "unit": "м3", "volume": 3.5,
     "building": "АБК", "work_date": date(2026, 7, 11)},
    {"vor_code": "9.9.9", "work_name": "Новая работа", "unit": "шт", "volume": 2,
     "building": "Галерея", "work_date": date(2026, 7, 12)},
]


def test_pricing_has_known_vor_code():
    pricing = load_pricing()
    assert pricing["2.1.1"]["unit_price"] == 600
    assert pricing["2.1.1"]["plan_qty"] == 1007


def test_generate_ks2_from_samples(tmp_path, monkeypatch):
    monkeypatch.setenv("KS2_CUSTOMER", "Тестовый заказчик")
    monkeypatch.setenv("KS2_CONTRACTOR", "Тестовый подрядчик")
    monkeypatch.setenv("KS2_ADVANCE_RETENTION_PERCENT", "10")
    monkeypatch.setenv("KS2_WARRANTY_RETENTION_PERCENT", "5")
    path, summary = generate_ks2(date(2026, 7, 1), date(2026, 7, 31), SAMPLES, output_dir=tmp_path)
    assert Path(path).exists()
    workbook = load_workbook(path, data_only=True)
    sheet = workbook["КС-2"]
    assert sheet.max_column == 14
    assert sheet["A1"].value == "Заказчик:"
    assert sheet["B1"].value == "Тестовый заказчик"
    assert sheet["A7"].value.startswith("АКТ №")
    assert sheet["A11"].value == "№ п/п"
    assert sheet["D11"].value == "По Договору"
    assert sheet["G11"].value == "Выполнено за предыдущий период"
    assert sheet["I11"].value == "Выполнено за отчётный период"
    assert sheet["K11"].value == "Всего с начала периода"
    assert sheet["M11"].value == "Не заполняется"
    assert sheet["N11"].value == "% выполнения работ"
    description_rows = {sheet.cell(row, 2).value: row for row in range(14, sheet.max_row + 1)}
    plan_row = next(row for description, row in description_rows.items() if description and description.startswith("Планировка"))
    assert sheet.cell(plan_row, 7).value == 4
    assert sheet.cell(plan_row, 9).value == 10
    assert sheet.cell(plan_row, 11).value == 14
    assert sheet.cell(plan_row, 13).value is None
    assert any(cell.value == "Требует расценки" for row in sheet.iter_rows() for cell in row)
    assert summary["total"] == 47300
    assert summary["missing_prices"] == ["9.9.9"]
    labels = {sheet.cell(row, 1).value: row for row in range(14, sheet.max_row + 1)}
    assert sheet.cell(labels["Итого"], 10).value == 47300
    assert sheet.cell(labels["Удержание аванса (10%)"], 10).value == 4730
    assert sheet.cell(labels["Гарантийное удержание (5%)"], 10).value == 2365
    assert sheet.cell(labels["К оплате"], 10).value == 40205


def test_generate_ks6_from_samples(tmp_path):
    path, summary = generate_ks6(date(2026, 7, 31), SAMPLES, output_dir=tmp_path)
    assert Path(path).name == "КС-6_2026-07.xlsx"
    workbook = load_workbook(path, data_only=True)
    sheet = workbook["КС-6"]
    code_rows = {sheet.cell(row, 1).value: row for row in range(5, sheet.max_row + 1)}
    assert sheet.cell(code_rows["2.1.1"], 6).value == 14
    assert sheet.cell(code_rows["2.1.1"], 7).value == 993
    assert summary["missing_prices"] == ["9.9.9"]
