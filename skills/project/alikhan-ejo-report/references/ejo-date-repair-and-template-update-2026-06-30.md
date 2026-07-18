# ЕЖО 29.06 date repair + corrected template acceptance (2026-06-30)

## Problem pattern

Bot was left in simulation mode with `SIM_DATE = "2026-06-28"`. Fresh QA facts and photos for the 29.06 report were saved under the wrong date:

- `bot_memory_facts.fact_date = 2026-06-28`
- `bot_memory_messages.created_at::date = 2026-06-28` for images

`fill_ejo.py` uses different date fields by data type:

- QA facts: `bot_memory_facts.fact_date`
- photos: `DATE(bot_memory_messages.created_at)`

So fixing only facts can still produce an empty/partial photo sheet.

## Safe repair workflow

1. Inspect candidate rows by `id`, `created_at`, `source`, `fact_date`, category/fact text.
2. Back up exact rows before update using `row_to_json` into `~/.hermes/backups/alikhan-ejo-<date>-<timestamp>.json`.
3. Update by explicit id list only.
4. For photos, also back up/update `bot_memory_messages.created_at` by explicit id list.
5. Set `SIM_DATE` in both `main_waha.py` and `router.py` to the target report date.
6. Generate `python fill_ejo.py YYYY-MM-DD`.
7. Verify workbook dates and images:
   - no old date hits (`28.06` in this case)
   - expected date cells on all sheets
   - `len(wb['Фототчет']._images)` matches moved photos
8. Restart bot so in-memory `SIM_DATE` changes take effect.

## Corrected report sent back by user

When the user sends an edited `.xlsx` named like `ЕЖО_29.06.2026 АйБиКон.xlsx`, the bot should:

- save it as a document row;
- compare it with latest auto-generated `/tmp/ЕЖО_YYYY-MM-DD_vN.xlsx` by VOR code, not row number;
- replace `templates/ЕЖО_шаблон.xlsx`;
- write `/tmp/ЕЖО_template_YYYY-MM-DD.xlsx`;
- write/overwrite `/tmp/ЕЖО_YYYY-MM-DD_v1.xlsx` as the corrected cumulative base for future `yesterday_cum()`.

`[DOC EXTRACT ERR] <urlopen error [Errno 111] Connection refused>` from the document extractor on `:8099` is non-blocking for EJO template update: the report can still be saved, diffed, and accepted as template. Treat extractor repair as a separate follow-up unless the user asked for document text search/analysis.

## Service/runtime pitfall

After patching `SIM_DATE` in files, the running bot still has the old value in memory until restarted. Verify:

```bash
systemctl --user status alikhan.service --no-pager
ps -eo pid,ppid,etime,cmd | grep '[p]ython.*main_waha.py'
tail -80 /tmp/alikhan.log
```

If a command message crashed after being added to `seen_ids.json`, either manually perform the requested action and report it, or remove the id from `seen_ids.json` and restart the service so the in-memory `seen` set reloads.
