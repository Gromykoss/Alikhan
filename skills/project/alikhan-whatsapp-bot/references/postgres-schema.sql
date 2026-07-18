-- PostgreSQL tables for Alikhan bot
-- Host: evolution-postgres (Docker) or 172.18.0.4 (host)
-- DB: evolution_db, User: evolution, Password: SuperSecretGrok2026

-- Calendar events
CREATE TABLE IF NOT EXISTS bot_calendar_events (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    created_by TEXT,
    source_message_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    event_start TIMESTAMPTZ NOT NULL,
    event_end TIMESTAMPTZ,
    timezone TEXT NOT NULL DEFAULT 'Asia/Bishkek',
    remind_at TIMESTAMPTZ,
    remind_minutes_before INTEGER,
    reminder_sent BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Message memory
CREATE TABLE IF NOT EXISTS bot_memory_messages (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    sender TEXT,
    message_time TIMESTAMPTZ,
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    message_type TEXT DEFAULT 'text',  -- 'text', 'image', 'document'
    content TEXT,
    file_name TEXT,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversation summaries
CREATE TABLE IF NOT EXISTS bot_memory_summaries (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    messages_until_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Group participants
CREATE TABLE IF NOT EXISTS bot_group_participants (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    participant_id TEXT,
    participant_alt TEXT,
    push_name TEXT,
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    UNIQUE(chat_id, participant_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_calendar_chat_start ON bot_calendar_events(chat_id, event_start);
CREATE INDEX IF NOT EXISTS idx_calendar_remind ON bot_calendar_events(reminder_sent, remind_at) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_memory_chat_time ON bot_memory_messages(chat_id, message_time);
CREATE INDEX IF NOT EXISTS idx_summaries_chat ON bot_memory_summaries(chat_id);
