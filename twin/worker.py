"""
Hermes Twin Worker — агент на ноутбуке.
Слушает Redis-команды от VPS-Hermes, выполняет их через hermes CLI,
отправляет результаты обратно.

Запуск: python worker.py
Зависимости: pip install redis
"""
import redis, json, time, subprocess as sp, sys, os, threading

REDIS_HOST = "72.60.16.105"
REDIS_PORT = 6379
CMD_CHANNEL = "hermes:bridge:commands"
RES_CHANNEL = "hermes:bridge:results"

r = None
my_id = f"twin-{int(time.time())}"

def log(msg, kind="info"):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{kind}] {msg}", flush=True)

def connect_redis():
    global r
    for attempt in range(10):
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, 
                           decode_responses=True, socket_connect_timeout=5)
            r.ping()
            log("Redis connected")
            return True
        except Exception as e:
            log(f"Redis attempt {attempt+1}: {e}", "warn")
            time.sleep(3)
    return False

def execute_command(cmd):
    """Execute a command and return result."""
    ctype = cmd.get("type", "ping")
    cid = cmd.get("id", "?")
    
    if ctype == "ping":
        return {"id": cid, "status": "ok", "result": "pong", "twin": my_id}
    
    elif ctype == "whatsapp.status":
        # Check WhatsApp connection via hermes gateway
        try:
            res = sp.run(["hermes", "gateway", "status"], 
                        capture_output=True, text=True, timeout=10)
            return {"id": cid, "status": "ok", "result": res.stdout.strip()}
        except Exception as e:
            return {"id": cid, "status": "error", "result": str(e)}
    
    elif ctype == "whatsapp.send":
        # Send WhatsApp message — Twin forwards via hermes gateway
        chat = cmd.get("chat", "")
        text = cmd.get("text", "")
        # Write to a file that the main Alikhan bot picks up
        try:
            with open("/tmp/twin_outgoing.txt", "a") as f:
                f.write(f"{chat}|{text}\n")
            return {"id": cid, "status": "ok", "result": "queued"}
        except Exception as e:
            return {"id": cid, "status": "error", "result": str(e)}
    
    elif ctype == "browser.open":
        url = cmd.get("url", "")
        try:
            res = sp.run(["hermes", "browser", "open", url],
                        capture_output=True, text=True, timeout=30)
            return {"id": cid, "status": "ok", "result": res.stdout[:500]}
        except Exception as e:
            return {"id": cid, "status": "error", "result": str(e)}
    
    else:
        return {"id": cid, "status": "error", "result": f"unknown type: {ctype}"}

def send_result(result):
    try:
        r.publish(RES_CHANNEL, json.dumps(result))
    except Exception as e:
        log(f"Send error: {e}", "error")

def command_listener():
    """Listen for commands on Redis pub/sub."""
    p = r.pubsub()
    p.subscribe(CMD_CHANNEL)
    log(f"Listening on {CMD_CHANNEL}")
    
    for msg in p.listen():
        if msg["type"] != "message":
            continue
        try:
            cmd = json.loads(msg["data"])
            cid = cmd.get("id", "?")
            log(f"Command: {cmd.get('type','?')} [{cid}]")
            result = execute_command(cmd)
            send_result(result)
        except json.JSONDecodeError:
            log(f"Bad JSON: {msg['data'][:50]}", "error")
        except Exception as e:
            log(f"Handler error: {e}", "error")

def heartbeat_loop():
    """Send periodic heartbeats."""
    while True:
        time.sleep(30)
        send_result({"type": "heartbeat", "id": my_id, "time": time.time()})

def main():
    log(f"Twin Worker starting [{my_id}]")
    
    if not connect_redis():
        log("Cannot connect to Redis. Exiting.", "error")
        sys.exit(1)
    
    # Send startup notification
    send_result({"type": "startup", "id": my_id, "time": time.time()})
    
    # Start heartbeat thread
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    
    # Start command listener (blocking)
    command_listener()

if __name__ == "__main__":
    main()
