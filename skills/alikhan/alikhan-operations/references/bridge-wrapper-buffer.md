# Bridge Wrapper v2 — Message Buffer (16.07.2026)

## Problem

The Hermes WhatsApp bridge `/messages` endpoint is **destructive**:
```js
app.get('/messages', (req, res) => {
  const msgs = messageQueue.splice(0, messageQueue.length);
  res.json(msgs);
});
```
This means **whoever calls first consumes ALL messages** for all chat IDs.

The Alikhan bot has two message consumers:
- **Sandbox main loop** — polls every 3s, processes commands, sends replies
- **PROD listener thread** — polls every 10s, saves media/text, runs QA parser

When PROD thread polls first, it consumes sandbox messages that contain commands like «Алихан запускай опрос». The command gets saved as text and parsed by QA (0 facts), but **never reaches the sandbox main loop** to trigger the poll start.

## Solution

`bridge_wrapper.py` v2 implements a local buffer:

```python
_BUFFER = []  # global message cache

def _fetch_and_buffer():
    """Fetch all messages from bridge and add to buffer."""
    br = requests.get(f"{BRIDGE}/messages", timeout=10)
    new_msgs = br.json() if br.ok else []
    _BUFFER.extend(new_msgs)
    if len(_BUFFER) > 200:
        _BUFFER = _BUFFER[-200:]

def _drain_buffer(remote_jid):
    """Return messages matching remote_jid, removing them from buffer."""
    if not remote_jid:
        msgs = _BUFFER[:]; _BUFFER = []; return msgs
    matched = [m for m in _BUFFER if remote_jid in m.get("chatId", "")]
    _BUFFER = [m for m in _BUFFER if remote_jid not in m.get("chatId", "")]
    return matched
```

Each `findMessages` call:
1. `_fetch_and_buffer()` — drain bridge into local cache
2. `_drain_buffer(remoteJid)` — return only messages for the requested group

The `remoteJid` filter is extracted from the Evolution API request body:
```python
body = json or {}
remote_jid = body.get("where", {}).get("key", {}).get("remoteJid", "")
```

## Verification

```bash
# Send a message to sandbox group — should appear with [MSG] in log
tail -f /tmp/bot.log | grep -v collation
# Expect: [MSG] 1784206935...
# Then: [POLL] Started poll #N for 2026-07-16
```

PROD thread should show `[PROD] ...` only for PRODUCTION group messages, never sandbox.
