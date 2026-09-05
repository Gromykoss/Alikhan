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

## Update Rule
Менялся extractor → обнови `INDEX.md` (endpoint) + эту карточку.
