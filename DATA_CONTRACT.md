# DATA_CONTRACT.md — Единый источник правды по данным Alikhan

## Источник сырья (source of truth для факта прихода)
- `bot_memory_messages` — ЖИВОЙ поток WhatsApp (песочница + боевая). Каждое сообщение/фото/документ = строка. Сюда пишет диспетчер `whatsapp_commands.py` ДО ack. Если строка есть здесь — факт прихода НЕ потерян.

## Производные (только разобранное)
- `ojr_section1_personnel` — ИТР/рабочие (из текстовых сводок/QA)
- `ojr_section3_work_log` — объёмы работ (из текстовых сводок/poll)
- `ojr_photo_log` — строительные фото (из image, classification ∈ caption/construction)
- `ojr_section5_asbuilt_docs` — исполнительная документация (из document)
- `ojr_weather` — погода (Open-Meteo API)
- `ojr_daily_summary` — агрегаты дня

## Граф связей (что куда разбирается)
- text (сводка персонала/объёмов) → parse_qa → ojr_section1_personnel / ojr_section3_work_log
- image (стройка) → _save_prod_photo → ojr_photo_log
- document → _save_prod_document → ojr_section5_asbuilt_docs
- image (не стройка: site_related/unrelated/greeting) → только bot_memory_messages (НЕ в ojr_photo_log)

## Правило проверки разрыва (ключевое)
«Сырьё (bot_memory_messages) растёт, а результат (ojr_*) не растёт = РАЗРЫВ РАЗБОРА, НЕ потеря данных.»
Т.е. если за день в bot_memory_messages N новых image, а в ojr_photo_log +0 — это сломался разбор (код), а не «данные потерялись». Данные в сырье целы.

## Неразобранные категории (осознанно вне ojr_*)
- image classification ∈ {site_related, unrelated, greeting_card, vision_unavailable} — не стройка, только сырьё
- image с building='без тег' — не классифицировано (нет файла для vision), только сырьё
- ЕЖО_*.xlsx документы — output бота, не исполнительная документация
