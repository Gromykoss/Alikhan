# Hermes Bridge Stability — Fix Recipe

Applied 2026-07-17. Covers the "Timeout in AwaitingInitialSync" / HTTP 000 crash and the rapid 440 reconnect loop.

## Root Cause

`bridge.js` line 1118: `startSocket()` called without `.catch()`.
When Baileys initial sync times out, the async promise rejects → unhandled rejection → Node.js process dies.
Compounded by flat 3-second reconnect on `connection === 'close'` which hammered WhatsApp servers.

## Fix 1: `connectWithRetry()` wrapper (bridge.js)

Add BEFORE the `if (PAIR_ONLY)` block at the bottom of bridge.js:

```javascript
const MAX_BACKOFF_MS = 60_000;
let retryBackoffMs = 1000;

async function connectWithRetry() {
  while (true) {
    try {
      await startSocket();
      retryBackoffMs = 1000;
      await sleep(1000);
    } catch (err) {
      const message = err?.message || String(err);
      const isLoggedOut =
        message.includes('logged out') ||
        message.includes('401');
      if (isLoggedOut) {
        console.error('❌ WhatsApp session logged out. Exiting so systemd can restart cleanly.');
        process.exit(1);
      }
      console.error(
        `⚠️  Bridge connection failed: ${message}. ` +
        `Retrying in ${(retryBackoffMs / 1000).toFixed(1)}s…`
      );
      await sleep(retryBackoffMs);
      retryBackoffMs = Math.min(retryBackoffMs * 2, MAX_BACKOFF_MS);
    }
  }
}
```

Then replace `startSocket();` in the non-PAIR_ONLY branch with:
```javascript
connectWithRetry().catch((err) => {
  console.error('❌ Fatal bridge error:', err?.message || err);
  process.exit(1);
});
```

## Fix 2: Inner reconnect with backoff (bridge.js)

Replace the flat `setTimeout(startSocket, ...)` in the `connection.update` handler:

```javascript
let _reconnectBackoffMs = 1000;
const _RECONNECT_BACKOFF_CAP = 30_000;

// In connection === 'close' handler:
if (reason === 428) {
  _reconnectBackoffMs = 1000;
  setTimeout(() => startSocket().catch(err => {
    console.error('⚠️  Reconnect attempt failed:', err?.message || err);
  }), 1000);
} else {
  const delay = _reconnectBackoffMs;
  _reconnectBackoffMs = Math.min(_reconnectBackoffMs * 2, _RECONNECT_BACKOFF_CAP);
  setTimeout(() => startSocket().catch(err => {
    console.error('⚠️  Reconnect attempt failed:', err?.message || err);
  }), delay);
}

// On successful connection:
_reconnectBackoffMs = 1000;  // reset
```

## Fix 3: systemd user service

File: `~/.config/systemd/user/hermes-whatsapp-bridge.service`

```ini
[Unit]
Description=Hermes WhatsApp Bridge (Baileys)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/.hermes/hermes-agent/scripts/whatsapp-bridge
Environment=NODE_ENV=production
Environment=WHATSAPP_MODE=bot
Environment=WHATSAPP_ALLOWED_USERS=*
Environment=WHATSAPP_DM_POLICY=open
Environment=WHATSAPP_FORWARD_OWNER_MESSAGES=true
Environment=HERMES_IMAGE_CACHE_DIR=%h/.hermes/image_cache
Environment=HERMES_DOCUMENT_CACHE_DIR=%h/.hermes/document_cache
Environment=HERMES_AUDIO_CACHE_DIR=%h/.hermes/audio_cache
ExecStart=%h/.hermes/node/bin/node bridge.js --mode bot --session %h/.hermes/sessions/whatsapp --port 3000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hermes-whatsapp-bridge
NoNewPrivileges=yes
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=default.target
```

Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable hermes-whatsapp-bridge.service
systemctl --user start hermes-whatsapp-bridge.service
```

## 440 Conflict Note

Reason 440 = "replaced" — another session (phone) is active on the same WhatsApp account.
This is **expected behavior**, not a bug. The bridge cannot coexist with an active phone session.
Exponential backoff prevents rate-limiting; bridge reconnects when the phone goes idle.

## Verification

```bash
systemctl --user status hermes-whatsapp-bridge   # active (running)
curl -s http://127.0.0.1:3000/health             # {"status":"connected"/"disconnected",...}
journalctl --user -u hermes-whatsapp-bridge -f    # follow logs
```
