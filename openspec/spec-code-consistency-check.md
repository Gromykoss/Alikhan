# Spec-Code Consistency Check

Чеклист сверки спецификаций (openspec/specs/) с кодом. Прогонять при изменении домена/инварианта/теста.

## Проверки

1. **Канон ОЖР = 15 таблиц** — сверка `db/ojr_schema.sql` (16 CREATE) vs DATA_CONTRACT.md vs граф. Расхождение → фикс.
2. **Domain Map** — каждая карточка `openspec/specs/*.md` соответствует реальному файлу кода (не битая ссылка).
3. **Тесты привязаны** — каждый домен имеет ≥1 тест (см. Domain Map). Новый домен без теста = стоп.
4. **Invariants** — Global Invariants в графе актуальны (не противоречат MASTER_SPEC/DATA_CONTRACT).
5. **No duplication** — карточка ссылается на источник, НЕ копирует содержимое MASTER_SPEC/DATA_CONTRACT/CONTRACTS.
6. **Spec Drift Gate** — после изменения есть либо обновление графа/карточки, либо запись `Contract index update: not needed`.

## Команда сверки

```bash
cd /home/hermes-workspace/Alikhan-migration
# Сверка числа таблиц
grep -c "CREATE TABLE" db/ojr_schema.sql   # ожидание 16 (15 канон + pass_register...)
grep -n "таблиц" INDEX.md MASTER_SPEC.md   # канон 15

# Тесты зелёные
/home/hermes-workspace/.hermes/hermes-agent/venv/bin/python3 -m pytest bot/ -q

# Карточки существуют
ls openspec/specs/*.md
```
