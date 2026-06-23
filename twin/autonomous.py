"""
Autonomous Twin listener — polls GitHub for commands, executes, responds.
No human needed. VPS writes to twin-commands.md, Twin detects and responds.
"""
import time, subprocess as sp, requests, os

VAULT_PATH = os.path.expanduser("~/hermes-vault")
COMMANDS_FILE = "30_Logs/twin-commands.md"
GITHUB_REPO = "Gromykoss/hermes-vault"
POLL_S = 15

last_sha = None

def get_latest_commit():
    """Get SHA of latest commit touching commands file."""
    r = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/commits",
        params={"path": COMMANDS_FILE, "per_page": 1},
        timeout=30, verify=False
    )
    if r.ok and r.json():
        return r.json()[0]["sha"]
    return None

def git_pull():
    sp.run(["git", "pull"], cwd=VAULT_PATH, capture_output=True)

def read_commands():
    path = os.path.join(VAULT_PATH, COMMANDS_FILE)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]

def execute_and_respond(command):
    """Execute command and write result."""
    if command.startswith("ping:"):
        result = "pong: " + command.split(":")[1].strip()
    else:
        result = f"unknown: {command[:50]}"
    
    path = os.path.join(VAULT_PATH, COMMANDS_FILE)
    with open(path, "a") as f:
        f.write(f"\n{result}")
    
    sp.run(["git", "add", COMMANDS_FILE], cwd=VAULT_PATH)
    sp.run(["git", "commit", "-m", f"bridge: {result[:50]}"], cwd=VAULT_PATH)
    sp.run(["git", "push"], cwd=VAULT_PATH)
    print(f"  Responded: {result}")

def main():
    global last_sha
    print("Twin Autonomous Worker — GitHub polling")
    
    while True:
        try:
            sha = get_latest_commit()
            if sha and sha != last_sha:
                last_sha = sha
                print(f"New command detected: {sha[:8]}")
                git_pull()
                for cmd in read_commands():
                    if cmd and not cmd.startswith("pong:"):
                        execute_and_respond(cmd)
        except Exception as e:
            print(f"Poll error: {e}")
        
        time.sleep(POLL_S)

if __name__ == "__main__":
    main()
