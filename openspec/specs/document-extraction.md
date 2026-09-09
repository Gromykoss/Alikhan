# Domain: document-extraction

## Role
Распознавание документов (.docx/.xlsx/.pdf) → текст → `ojr_section5_asbuilt_docs` (исполнительная документация).

## Canonical Sources
- `INDEX.md` (endpoint `:8099/extract-document`)
- `bot/document_extractor.py` (имплементация)

## Code Owners
- `bot/document_extractor.py` (локальный fallback)
- `bot/alikhan-document-extractor.service` (`:8099`)

## Neighbor Risks
- `data-ingestion` (документ → сырьё)
- `ojr-data-contract` (section5)

## Known Traps
- `.docx` extractor `:8099` может вернуть только metadata → локальный `_extract_docx_text()` (zipfile + ElementTree).
- Пропуска (транспорт) → `ojr_pass_register`, НЕ section5.

### GIVEN .docx, extractor :8099 вернул только metadata `document-extraction.docx_metadata_fallback_local`
<!-- no-ci -->
**UNTESTED (CI):** исполняемого теста нет (долг); fallback живёт в клиенте `bot/whatsapp_commands.py::_extract_docx_text()` (вызывается после metadata-ответа сервиса :8099), покрыт боевой эксплуатацией.
- WHEN клиент `_extract_docx_text()` (`bot/whatsapp_commands.py`) разбирает .docx после metadata-ответа сервиса :8099
- THEN текст извлечён локально (zipfile + ElementTree), НЕ metadata

## Update Rule
Менялся extractor → обнови `INDEX.md` (endpoint) + эту карточку.
