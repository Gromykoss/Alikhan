# Alikhan Daily Snapshot — technical reference
# See also: alikhan-daily-snapshot skill for the operational guide

## Evolution (17.07.2026)

| Ver | Change | Problem it fixed |
|-----|--------|-----------------|
| v1 | Bullet-point list | Unreadable, no narrative |
| v2 | Grok narrative via xAI | 90s timeout (ask_grok without image falls to Ollama) |
| v3 | ask_grok_raw directly | Wastes xAI tokens (~500/snapshot) |
| v4 | **Ollama for narrative**, xAI only for vision | Current — token-efficient |

## Data flow

```
bot_memory_messages          bot_memory_facts              bot_poll_state
├── content (text)           ├── category                  ├── chat_id
├── message_type             ├── building                  ├── poll_date
├── tags->>'description'     ├── fact                      └── data (JSONB)
├── tags->>'building'        ├── source                        └── collected:
├── file_name (documents)    └── created_at                        ├── "2.1.5":
└── created_at                                                      │   ├── actual_today: 45.0
                                                                    │   └── volume: 45.0
        ↓                           ↓                              └── ...
   generate_daily_snapshot()  ────→  gathers  ←──────
                ↓
           Ollama prompt (ask_ollama, 30s timeout)
                ↓
         bot_memory_facts
         (category='снимок_дня', chat_id required)
```

## Prompt rules (hard-won)

1. **Don't mix sources** — photos say "no equipment visible", QA says "1 loader". Prompt must explicitly forbid merging.
2. **Compact > complete** — 3 photos × 120 chars beats 5 × 200 on qwen3:8b within 30s.
3. **Dry tone** — "no conclusions, no evaluations" as first instruction. Otherwise models add "recommend increased oversight".

## Timeouts

| Call | Timeout | Why |
|------|---------|-----|
| `ask_ollama()` | 30s | Enough for 600 tokens on qwen3:8b |
| `ask_grok_raw()` | 60s | xAI API, used for vision only |
| wttr.in | 10s | Weather is non-critical |
