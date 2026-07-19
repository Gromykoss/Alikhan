from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from bot.avr import generate_ks2, generate_ks6, load_pricing


SAMPLES = [
    {"vor_code": "2.1.1", "work_name": "Планировка", "unit": "м3", "volume": 10, "building": "Общежитие"},
    {"vor_code": "2.1.2", "work_name": "Разработка грунта", "unit": "м3", "volume": 3.5, "building": "АБК"},
    {"vor_code": "9.9.9", "work_name": "Новая работа", "unit": "шт", "volume": 2, "building": "Галерея"},
]


def test_pricing_has_known_vor_code():
    pricing = load_pricing()
    assert pricing["2.1.1"]["unit_price"] == 600
    assert pricing["2.1.1"]["plan_qty"] == 1007


def test_generate_ks2_from_samples(tmp_path):
    path, summary = generate_ks2(date(2026, 7, 1), date(2026, 7, 31), SAMPLES, output_dir=tmp_path)
    assert Path(path).exists()
    workbook = load_workbook(path, data_only=True)
    sheet = workbook["КС-2"]
    assert sheet["A5"].value == "2.1.2"  # sorted by building, then code
    assert any(cell.value == "Требует расценки" for row in sheet.iter_rows() for cell in row)
    assert summary["total"] == 47300
    assert summary["missing_prices"] == ["9.9.9"]


def test_generate_ks6_from_samples(tmp_path):
    path, summary = generate_ks6(date(2026, 7, 31), SAMPLES, output_dir=tmp_path)
    assert Path(path).name == "КС-6_2026-07.xlsx"
    workbook = load_workbook(path, data_only=True)
    sheet = workbook["КС-6"]
    code_rows = {sheet.cell(row, 1).value: row for row in range(5, sheet.max_row + 1)}
    assert sheet.cell(code_rows["2.1.1"], 6).value == 10
    assert sheet.cell(code_rows["2.1.1"], 7).value == 997
    assert summary["missing_prices"] == ["9.9.9"]
