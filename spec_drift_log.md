# Spec Drift Log — <node-name>

> Fail-closed журнал: spec-affecting мутация без записи = нарушение.
> Append-only (старые строки не редактировать). Поля: awk -F'|' → 2=время, 3=что меняю, 4=зачем, 5=что НЕ трогаю, 6=SHA/пусто. `|` в ячейках запрещён (использовать `\|`).

| Время (UTC) | Что меняю | Зачем | Что НЕ трогаю | SHA/пусто |
|---|---|---|---|---|
| 2026-09-06T14:30 | ops/ | SDG v1.4 E2E DAG probe | docs/ |  |
| 2026-09-06T14:07 | ops/ | SDG v1.4 E2E DAG probe (corrected time) | docs/ | fb98e9d895ef |
| 2026-09-06T14:10 | ops/ | SDG v1.4 clean DAG E2E | docs/ |  |
