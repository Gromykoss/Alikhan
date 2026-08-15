#!/bin/bash
# Alikhan Bridge session restart — every 48h to prevent Baileys key expiry
# Add to crontab: 0 2 */2 * * /home/hermes-workspace/Alikhan-migration/scripts/bridge_48h_restart.sh >> /tmp/bridge_restart.log 2>&1

set -e
TS=$(date -Iseconds)
echo "[$TS] Restarting hermes-whatsapp-bridge..."

systemctl --user restart hermes-whatsapp-bridge

# Wait for bridge to come back up
sleep 5

# Health check
if curl -sf http://127.0.0.1:3000/health > /dev/null 2>&1; then
    echo "[$TS] Bridge restart OK — /health responds"
else
    echo "[$TS] WARNING: Bridge /health not responding after restart"
    exit 1
fi
