#!/usr/bin/env python3
"""Ежесуточная проверка логики и архитектуры проекта Alikhan.

Гоняет ПОЛНЫЙ pytest по каталогу bot/ (все test_*.py).
Почему полный, а не выборочный: контаминация типа sys.modules['db']=fake_db
в одном файле заражает ВСЕ тесты после себя — поймать её можно только полным
прогоном. Пример: test_photo_classification.py (вычищен 03.09) валил каскад.

Вывод ДЕТЕРМИНИРОВАН (для cron monitor): без таймстампов и времени выполнения,
чтобы monitor-гейт просыпался только при реальном изменении состояния.

Формат:
  OK: <N> passed
  FAIL: <test::name>, <test::name>, ...
"""
import subprocess

BOT_DIR = "/home/hermes-workspace/Alikhan-migration/bot"
PYTHON = "/home/hermes-workspace/.hermes/hermes-agent/venv/bin/python3"


def main():
    r = subprocess.run(
        [PYTHON, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider"],
        cwd=BOT_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )

    failed = []
    passed_count = 0
    import re

    for line in (r.stdout + "\n" + r.stderr).splitlines():
        s = line.strip()
        # Собираем имена упавших тестов: "FAILED test_x.py::test_y - ..."
        if s.startswith("FAILED "):
            name = s.split("::", 1)[1] if "::" in s else s
            name = name.split(" ")[0].split(" - ")[0].strip()
            if name:
                failed.append(name)
        # Итоговая строка: "30 passed in 14.86s" или "1 failed, 29 passed in ..."
        m = re.search(r"(\d+) passed", s)
        if m and ("in " in s or "failed" in s or "passed" in s):
            passed_count = int(m.group(1))

    failed = sorted(set(failed))

    if r.returncode == 0 and not failed:
        print(f"OK: {passed_count} passed")
    elif failed:
        print("FAIL: " + ", ".join(failed))
    else:
        print(f"ERROR: pytest exit={r.returncode}")


if __name__ == "__main__":
    main()
