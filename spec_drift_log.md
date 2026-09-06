# Spec Drift Log — <node-name>

> Fail-closed журнал: spec-affecting мутация без записи = нарушение.
> Append-only (старые строки не редактировать). Поля: awk -F'|' → 2=время, 3=что меняю, 4=зачем, 5=что НЕ трогаю, 6=SHA/пусто. `|` в ячейках запрещён (использовать `\|`).

| Время (UTC) | Что меняю | Зачем | Что НЕ трогаю | SHA/пусто |
|---|---|---|---|---|
| 2026-09-06T14:30 | ops/ | SDG v1.4 E2E DAG probe | docs/ | 24ce2c0c0060 |
| 2026-09-06T14:07 | ops/ | SDG v1.4 E2E DAG probe (corrected time) | docs/ | fb98e9d895ef |
| 2026-09-06T14:10 | ops/ | SDG v1.4 clean DAG E2E | docs/ | c8f8cc902420 |
| 2026-09-06T14:11 | ops/ | SDG v1.4 E2E cleanup (удаление probe-файлов) | docs/ | 2891deaae4b5 |
| 2026-09-06T15:05 | ops/ | Удаление мусорного E2E probe-файла из индекса | docs/ | c29698ca623d |
| REHAB | 24ce2c0c | E2E-проба v1.4 без интента: намеренный negative-test гейта, задокументирован в CHRONOLOGY 06.09 | - |  |
| REHAB | 83c2c7b8 | probe3: проба гейта v1.3.1 без интента (отрицательный E2E-тест, 06.09) | - |  |
| REHAB | ce2a7ff5 | E2E final: проба гейта с открытым интентом для проверки PASS-пути (06.09) | - |  |
| REHAB | 61c6e384 | revert E2E final — часть revert-пары пробы гейта 06.09 | - |  |
| REHAB | b79c2720 | rollout-доки 05.09 (v1.3.1, до hooks-раскатки в репо — хук физически не мог сработать) | - |  |
| REHAB | 7d41a09e | авто-синк 05.09 (cron auto-sync, machine-generated state-файлы, до hooks-раскатки) | - |  |
| 2026-09-06T17:37 | ops/_e2e_d16.md | D16 live E2E abort-gigiena | docs/ |  |
