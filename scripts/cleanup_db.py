#!/usr/bin/env python3
"""
Полная очистка БД Alikhan (evolution_db) от мусора миграции.
Запуск: python3 scripts/cleanup_db.py [--dry-run]
"""

import sys, subprocess, os

DRY_RUN = "--dry-run" in sys.argv

DB_HOST = os.environ.get("DB_HOST", "")
if not DB_HOST:
    # Resolve Docker container IP
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f",
             "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
             "evolution-postgres"],
            capture_output=True, text=True, timeout=3)
        DB_HOST = result.stdout.strip()
    except Exception:
        DB_HOST = "172.22.0.4"

DB_PASS = os.environ.get("DB_PASS", "")
if not DB_PASS:
    try:
        with open(os.path.expanduser("~/.hermes/secrets.env")) as f:
            for line in f:
                if line.startswith("DB_PASS=") or line.startswith("EVO_DB_PASS="):
                    DB_PASS = line.strip().split("=", 1)[1]
    except Exception:
        pass

# Все psql-вызовы — в часовом поясе Бишкека (UTC+6), как в приложении
# (bot/db.py get_conn: SET TIME ZONE 'Asia/Bishkek'). PGOPTIONS='-c timezone=...'
# — эквивалент SET TIME ZONE на старте сессии: без него created_at::date
# фильтры дают UTC-день и не совпадают с фильтрами приложения.
PSQL = "docker exec -e PGOPTIONS='-c timezone=Asia/Bishkek' evolution-postgres psql -U evolution -d evolution_db"
PG_ENV = {"DB_HOST": DB_HOST, "DB_PASS": DB_PASS}


def run_sql(sql: str, label: str = "") -> str:
    """Execute SQL via docker exec."""
    if DRY_RUN:
        print(f"[DRY-RUN] {label}\n{sql[:300]}...\n")
        return "DRY_RUN"
    result = subprocess.run(
        f'{PSQL} -c "{sql}"',
        shell=True, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"❌ {label}: {result.stderr}")
    else:
        print(f"✅ {label}")
    return result.stdout


def count_sql(sql: str) -> int:
    """Execute SQL and return count from first column."""
    try:
        out = subprocess.run(
            f'{PSQL} -t -c "{sql}"',
            shell=True, capture_output=True, text=True, timeout=15)
        return int(out.stdout.strip()) if out.stdout.strip().isdigit() else 0
    except Exception:
        return -1


def main():
    print("=" * 60)
    print("ОЧИСТКА БД evolution_db")
    print("=" * 60)
    if DRY_RUN:
        print("⚠️  DRY-RUN режим — ничего не удаляется\n")

    # --- STEP 1: БЭКАП уже сделан вручную ---
    print("\n📦 БЭКАП уже создан: /tmp/evolution_db_backup_*.sql")

    # --- STEP 2: Удаление OJR-строк от 18.07.2026 ---
    print("\n🗑️  Шаг 2: Удаление OJR-строк от 2026-07-18")
    tables = [
        "ojr_photo_log",
        "ojr_section1_personnel",
        "ojr_section3_work_log",
        "ojr_daily_summary",
    ]
    for t in tables:
        before = count_sql(f"SELECT COUNT(*) FROM {t} WHERE created_at::date = '2026-07-18'")
        run_sql(f"DELETE FROM {t} WHERE created_at::date = '2026-07-18'", f"DELETE {t}")
        after = count_sql(f"SELECT COUNT(*) FROM {t} WHERE created_at::date = '2026-07-18'")
        print(f"   {t}: {before} → {after} строк (от 18.07)")

    # --- STEP 3: bot_memory_facts ---
    print("\n🗑️  Шаг 3: bot_memory_facts старше 01.07.2026")
    before = count_sql("SELECT COUNT(*) FROM bot_memory_facts WHERE fact_date < '2026-07-01'")
    run_sql("DELETE FROM bot_memory_facts WHERE fact_date < '2026-07-01'", "DELETE facts")
    after = count_sql("SELECT COUNT(*) FROM bot_memory_facts WHERE fact_date < '2026-07-01'")
    print(f"   facts: {before} → {after} строк")

    # --- STEP 4: bot_memory_messages ---
    print("\n🗑️  Шаг 4: bot_memory_messages старше 01.07.2026")
    before = count_sql("SELECT COUNT(*) FROM bot_memory_messages WHERE created_at < '2026-07-01'")
    run_sql("DELETE FROM bot_memory_messages WHERE created_at < '2026-07-01'", "DELETE messages")
    after = count_sql("SELECT COUNT(*) FROM bot_memory_messages WHERE created_at < '2026-07-01'")
    print(f"   messages: {before} → {after} строк")

    # --- STEP 5: Удаление пустых таблиц ---
    print("\n🗑️  Шаг 5: Удаление пустых таблиц (не ojr_/bot_)")
    if not DRY_RUN:
        # Get the list of empty tables to drop
        list_sql = (
            "SELECT relname FROM pg_stat_user_tables "
            "WHERE n_live_tup = 0 AND schemaname = 'public' "
            "AND relname NOT LIKE 'ojr_%' AND relname NOT LIKE 'bot_%'"
        )
        out = subprocess.run(
            f'{PSQL} -t -c "{list_sql}"',
            shell=True, capture_output=True, text=True, timeout=15)
        to_drop = [t.strip() for t in out.stdout.strip().split("\n") if t.strip()]
        for t in to_drop:
            drop_out = subprocess.run(
                f'{PSQL} -c "DROP TABLE IF EXISTS {t} CASCADE"',
                shell=True, capture_output=True, text=True, timeout=15)
            if drop_out.returncode == 0:
                print(f"   🗑️  {t}")
            else:
                print(f"   ⚠️  {t}: {drop_out.stderr.strip()}")
    else:
        # Dry-run: list what would be dropped
        list_sql = """
        SELECT relname FROM pg_stat_user_tables
          WHERE n_live_tup = 0 AND schemaname = 'public'
          AND relname NOT LIKE 'ojr_%' AND relname NOT LIKE 'bot_%'
        ORDER BY relname
        """
        out = subprocess.run(
            f'{PSQL} -t -c "{list_sql}"',
            shell=True, capture_output=True, text=True, timeout=15)
        for line in out.stdout.strip().split("\n"):
            t = line.strip()
            if t:
                print(f"   [DRY-RUN] Would drop: {t}")

    # --- STEP 6: VACUUM FULL ---
    print("\n🧹 Шаг 6: VACUUM FULL (может занять время)...")
    if not DRY_RUN:
        out = subprocess.run(
            f'{PSQL} -c "VACUUM FULL;"',
            shell=True, capture_output=True, text=True, timeout=120)
        if out.returncode == 0:
            print("✅ VACUUM FULL завершён")
        else:
            print(f"⚠️ VACUUM FULL: {out.stderr}")
    else:
        print("[DRY-RUN] Пропускаем VACUUM FULL")

    # --- STEP 7: Очистка /tmp от ЕЖО ---
    print("\n🧹 Шаг 7: Очистка /tmp от ЕЖО_*.xlsx")
    import glob
    files = glob.glob("/tmp/ЕЖО_*.xlsx")
    if not files:
        print("   Нет файлов ЕЖО_*.xlsx в /tmp")
    for f in files:
        if DRY_RUN:
            print(f"   [DRY-RUN] Would remove: {f}")
        else:
            os.remove(f)
            print(f"   🗑️  Удалён: {f}")

    # --- ВЕРИФИКАЦИЯ ---
    print("\n" + "=" * 60)
    print("ВЕРИФИКАЦИЯ")
    print("=" * 60)

    verifications = [
        ("OJR photo_log от 18.07", "SELECT COUNT(*) FROM ojr_photo_log WHERE created_at::date = '2026-07-18'"),
        ("OJR personnel от 18.07", "SELECT COUNT(*) FROM ojr_section1_personnel WHERE created_at::date = '2026-07-18'"),
        ("OJR work_log от 18.07", "SELECT COUNT(*) FROM ojr_section3_work_log WHERE created_at::date = '2026-07-18'"),
        ("OJR daily_summary от 18.07", "SELECT COUNT(*) FROM ojr_daily_summary WHERE created_at::date = '2026-07-18'"),
        ("facts < 01.07", "SELECT COUNT(*) FROM bot_memory_facts WHERE fact_date < '2026-07-01'"),
        ("messages < 01.07", "SELECT COUNT(*) FROM bot_memory_messages WHERE created_at < '2026-07-01'"),
    ]
    all_zero = True
    for label, sql in verifications:
        n = count_sql(sql)
        status = "✅" if n == 0 else "❌"
        if n != 0:
            all_zero = False
        print(f"   {status} {label}: {n}")

    # OJR personnel: show remaining
    personnel = subprocess.run(
        f'{PSQL} -c "SELECT organization_name, position, start_date, end_date FROM ojr_section1_personnel ORDER BY start_date;"',
        shell=True, capture_output=True, text=True, timeout=15)
    print(f"\n📋 OJR personnel (оставшиеся):\n{personnel.stdout}")

    # DB size
    size = subprocess.run(
        f'{PSQL} -t -c "SELECT pg_size_pretty(pg_database_size(\'evolution_db\'));"',
        shell=True, capture_output=True, text=True, timeout=15)
    print(f"💾 Размер БД после очистки: {size.stdout.strip()}")

    # Empty tables remaining
    empty = subprocess.run(
        f'{PSQL} -t -c "SELECT relname FROM pg_stat_user_tables WHERE n_live_tup = 0 AND schemaname = \'public\' AND relname NOT LIKE \'ojr_%\' AND relname NOT LIKE \'bot_%\';"',
        shell=True, capture_output=True, text=True, timeout=15)
    remaining_empty = [t.strip() for t in empty.stdout.strip().split("\n") if t.strip()]
    print(f"📭 Пустых таблиц осталось: {len(remaining_empty)}")

    print("\n" + "=" * 60)
    if all_zero:
        print("✅ ОЧИСТКА ЗАВЕРШЕНА УСПЕШНО")
    else:
        print("⚠️  Есть ненулевые значения — проверьте выше")
    print("=" * 60)


if __name__ == "__main__":
    main()
