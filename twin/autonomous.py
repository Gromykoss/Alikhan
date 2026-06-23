"""
Autonomous Twin listener — uses local git (no API calls).
Polls git pull every N seconds, checks twin-commands.md.
"""
import time, subprocess as sp, os, sys

# Use existing vault path or accept as argument
VAULT_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/hermes-vault")
COMMANDS_FILE = "30_Logs/twin-commands.md"
POLL_S = 15

def git_pull():
    return sp.run(["git", "pull"], cwd=VAULT_PATH, capture_output=True, text=True)

def read_commands():
    path = os.path.join(VAULT_PATH, COMMANDS_FILE)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]

def execute_and_respond(command):
    """Execute command and respond via git."""
    result = None
    
    if command.startswith("ping:"):
        result = "pong: " + command.split(":", 1)[1].strip()
    
    elif command.startswith("browser:"):
        url_part = command.split("|")[0].replace("browser:", "").replace("open", "").strip()
        print(f"  🌐 Opening: {url_part}")
        result = f"browser-task: open {url_part} — ready for Hermes session"
    
    else:
        result = f"unknown-command: {command[:50]}"
    
    if result:
        path = os.path.join(VAULT_PATH, COMMANDS_FILE)
        with open(path, "a") as f:
            f.write(f"\n{result}")
        sp.run(["git", "add", COMMANDS_FILE], cwd=VAULT_PATH, capture_output=True)
        sp.run(["git", "commit", "-m", f"bridge: {result[:50]}"], cwd=VAULT_PATH, capture_output=True)
        sp.run(["git", "push"], cwd=VAULT_PATH, capture_output=True, timeout=30)
        print(f"  ✅ {result[:80]}")

def main():
    print(f"Twin Worker — vault: {VAULT_PATH}")
    
    processed = set()
    
    while True:
        try:
            git_pull()
            for cmd in read_commands():
                if cmd and not cmd in processed and not cmd.startswith("pong:") and not cmd.startswith("echo:"):
                    processed.add(cmd)
                    print(f"New command: {cmd[:60]}")
                    execute_and_respond(cmd)
        except Exception as e:
            print(f"🚫 {e}")
        
        time.sleep(POLL_S)

if __name__ == "__main__":
    main()
