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

### GIVEN metadata fallback extractor helper `document-extraction.fallback_text_format`
- WHEN `_fallback_text(filename, data_length, path)` строит локальную metadata-строку
- THEN формат `[document metadata: filename=...]` сохраняет filename, optional path, optional bytes и подставляет `document` для пустого filename

### GIVEN подсчёт содержательного текста `document-extraction.meaningful_len_ignores_whitespace`
- WHEN `_meaningful_len(text)` считает длину текста
- THEN пробелы, переводы строк и табы игнорируются; пустой/whitespace-only текст даёт 0

### GIVEN base64 и data URI payload `document-extraction.decode_base64_data_uri`
- WHEN `_decode_base64(value)` получает plain base64 или `data:*;base64,` URI
- THEN префикс data URI отбрасывается, пустой payload даёт `b""`, а некорректный padding пробрасывает `binascii.Error`

## Update Rule
Менялся extractor → обнови `INDEX.md` (endpoint) + эту карточку.
