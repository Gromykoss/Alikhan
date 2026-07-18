# EJO Methodology — Full User-Facing Documentation

## How It Works

Alikhan is an AI assistant in a WhatsApp group. It listens to everything: voice messages, text, photos, documents. With or without the mention «Алихан» — all messages are saved to the database.

If a message contains EJO data (personnel, equipment, volumes, materials, plans), Alikhan auto-detects and responds:

> ✅ Accepted: 4 facts (Atantay: 1 engineer, 6 workers. Maykadam: 1 engineer, 26 workers)

## Data Formats

All formats auto-recognized:

| Data | How to send |
|------|-------------|
| Personnel | «Atantay: 1 engineer, 6 workers. Maykadam: 1 engineer, 26 workers» |
| Equipment | «No equipment» or «excavator, 2 dump trucks» |
| Incidents | «No incidents» (default: none) |
| Work volumes | «2.2.3.2 = 77.52» (code = value) |
| Plans | «Plan 2.4.2.1 = 500» |
| Materials | «No material deliveries» or «gravel 50m3» |
| Photos | Send photo with caption: «ABK», «Dormitory», «Site overview» |
| Timesheet | Send .xlsx file — Alikhan reads and remembers for the month |

## Daily Cycle

### During the day
Send data to the group. Alikhan auto-detects and confirms. No commands needed.

### Evening — check
Write: «Alikhan start survey» or «Alikhan form EJO»

Alikhan shows what's collected and what's missing:
```
📋 Evening data collection:
✅ Personnel — done
✅ Equipment — done
✅ Incidents — none (default)
✅ Materials — done
📸 ABK (0 of 3) 📸 Site overview (0 of 3)
❌ Work volumes — no data
❌ Tomorrow's plan — missing
```

### If data is missing
The survey suggests what to send. Send it. Check again.

### When everything is collected
«Alikhan end survey» — close, fill defaults, generate EJO.

«Alikhan form EJO» — auto-check + generate .xlsx file.

File arrives in the group. Done.

## Manual Corrections

After auto-generation, corrections can be made:

1. Download EJO from the group
2. Make corrections in Excel
3. Send corrected file back to the group

Alikhan compares auto vs corrected, logs differences. At next EJO, corrections are applied automatically.

**Important:** the corrected file becomes the new template for the next day. Cumulative volumes and plans carry forward from it.

## Commands

| Command | Action |
|---------|--------|
| Alikhan start survey | Launch collected data check |
| Alikhan form EJO | Check + generate EJO |
| Alikhan end survey | Close survey, fill defaults, generate EJO |

## Auto-Filled Fields

- Weather — Open-Meteo API (temperature, wind, humidity, pressure)
- AyBiKon engineers — from monthly timesheet
- Incidents — default «none»
- Photos — into «Photo Report» sheet
- Cumulative volumes — from previous EJO

## Key Rules

1. All group messages are saved — with or without «Alikhan»
2. Work codes in format: code = value
3. Photos with object captions
4. Corrected EJO → new template for next day
