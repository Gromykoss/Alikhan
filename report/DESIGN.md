---
version: alpha
name: ЕЖО АйБиКон
description: Формальные строительные отчёты для АйБиКон — чисто, профессионально, читаемо.
colors:
  primary: "#1A2332"
  secondary: "#4A5568"
  tertiary: "#2563EB"
  neutral: "#F7F8FA"
  accent-success: "#047857"
  accent-warning: "#B45309"
  on-primary: "#FFFFFF"
  on-tertiary: "#FFFFFF"
typography:
  h1:
    fontFamily: Arial
    fontSize: 1.5rem
    fontWeight: 700
    lineHeight: 1.2
  h2:
    fontFamily: Arial
    fontSize: 1.25rem
    fontWeight: 600
    lineHeight: 1.3
  h3:
    fontFamily: Arial
    fontSize: 1.1rem
    fontWeight: 600
    lineHeight: 1.3
  body-md:
    fontFamily: Arial
    fontSize: 0.9rem
    lineHeight: 1.4
  table-cell:
    fontFamily: Calibri
    fontSize: 0.85rem
    lineHeight: 1.3
  label-caps:
    fontFamily: Arial
    fontSize: 0.75rem
    fontWeight: 600
    letterSpacing: "0.05em"
rounded:
  sm: 2px
  md: 4px
  lg: 8px
  full: 999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
components:
  report-header:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    padding: 16px
  report-section:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: 12px
  table-header:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-caps}"
    padding: 8px
  table-row:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.primary}"
    padding: 6px
  table-row-alt:
    backgroundColor: "#EDF2F7"
    textColor: "{colors.primary}"
    padding: 6px
  badge-success:
    backgroundColor: "{colors.accent-success}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
    padding: 4px
  badge-warning:
    backgroundColor: "{colors.accent-warning}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
    padding: 4px
---

## Overview

Деловой стиль для строительной отчётности. Чистые линии, минимум декора,
максимум читаемости. Arial для заголовков, Calibri для таблиц — шрифты,
доступные на любом рабочем компьютере без установки.

## Colors

- **Primary (#1A2332):** Заголовки, шапки отчётов, тёмные поверхности.
- **Secondary (#4A5568):** Заголовки таблиц, подписи, разделители.
- **Tertiary (#2563EB):** Акцент — гиперссылки, активные элементы (если HTML).
- **Neutral (#F7F8FA):** Фон страницы, строки таблиц.
- **Accent Success (#059669):** Позитивные индикаторы (план выполнен, норма).
- **Accent Warning (#D97706):** Предупреждения (отклонения, внимание).

## Typography

Arial для структурных элементов; Calibri для табличных данных (совпадает
со стилем Excel-шаблонов ЕЖО). Размеры адаптированы под печать A4.

## Layout

Spacing scale 4px baseline. `md` (12px) для внутренних отступов,
`lg` (16px) для межблочных.

## Components

- `report-header` — шапка отчёта, тёмный фон, белый текст.
- `report-section` — секция с данными, светлый фон.
- `table-header` / `table-row` / `table-row-alt` — строки таблиц.
  `table-row-alt` для zebra-striping через строку.
- `badge-success` / `badge-warning` — индикаторы статуса.

## Do's and Don'ts

- **Do** использовать Arial/Calibri — шрифты из комплекта Windows, не требуют установки.
- **Do** применять zebra-striping для таблиц больше 20 строк.
- **Don't** использовать тени или градиенты в печатных отчётах.
- **Don't** вводить новые цвета — все смысловые значения уже в палитре.
