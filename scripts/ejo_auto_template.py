#!/usr/bin/env python3
"""ejo_auto_template.py — если до 8:00 нет исправленного ЕЖО, v1 становится шаблоном."""
import os, sys, shutil, glob
from datetime import datetime, timedelta, timezone

BISHKEK = timezone(timedelta(hours=6))
TEMPLATE = "/home/hermes-workspace/Alikhan-migration/bot/templates/ЕЖО_шаблон.xlsx"
TMP_DIR = "/tmp"

def main():
    now = datetime.now(BISHKEK)
    # Yesterday's date in Bishkek
    yesterday = (now - timedelta(days=1)).date()
    date_str = yesterday.strftime("%Y-%m-%d")

    # Check if a corrected version was ever processed (template updated AFTER v1 generation)
    # All EJO files for yesterday, sorted by modification time (newest last)
    all_files = sorted(glob.glob(f"{TMP_DIR}/ЕЖО_{date_str}*.xlsx"), key=os.path.getmtime)
    if not all_files:
        print(f"[SKIP] No EJO files for {date_str}")
        return

    # Use the most recently modified file as the authoritative source
    latest = all_files[-1]
    latest_name = os.path.basename(latest)

    # Check if EJO already has corrections (more than just v1 auto-generated)
    # v1 = auto-generated. v2+ = user corrected. 
    has_corrections = len(all_files) > 1
    if has_corrections:
        # Check if any version > v1 exists and was created after v1
        v1_files = [f for f in all_files if '_v1.xlsx' in f or '_v1.' in f]
        if v1_files and len(all_files) > len(v1_files):
            print(f"[EXISTS] EJO already corrected for {date_str} ({latest_name}), skipping poll request")
            # Still update template if needed
            if os.path.exists(TEMPLATE) and os.path.getmtime(TEMPLATE) >= os.path.getmtime(latest):
                print(f"[SKIP] Template already up to date (≥ {latest_name})")
                return
            # Update template from latest corrected version
            backup = TEMPLATE + f".backup_{date_str}"
            if os.path.exists(TEMPLATE):
                shutil.copy2(TEMPLATE, backup)
                print(f"[BACKUP] {backup}")
            shutil.copy2(latest, TEMPLATE)
            print(f"[TEMPLATE] {latest_name} → {TEMPLATE}")
            print(f"[OK] Template updated from corrected EJO")
            return

    # Check if template already matches this version
    if os.path.exists(TEMPLATE) and os.path.getmtime(TEMPLATE) >= os.path.getmtime(latest):
        print(f"[SKIP] Template already up to date (≥ {latest_name})")
        return

    # Backup old template, then update from latest version
    backup = TEMPLATE + f".backup_{date_str}"
    if os.path.exists(TEMPLATE):
        shutil.copy2(TEMPLATE, backup)
        print(f"[BACKUP] {backup}")

    shutil.copy2(latest, TEMPLATE)
    print(f"[TEMPLATE] {latest_name} → {TEMPLATE}")
    print(f"[OK] Template updated from latest EJO")

if __name__ == "__main__":
    main()
