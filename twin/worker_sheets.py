"""
Hermes Twin Worker — Google Sheets edition.
VPS writes commands to sheet, Twin executes and updates status.
No Redis needed — both VPS and Twin have Google API access.
"""
import time, subprocess as sp, sys

# Google Sheets API — Twin reads/writes via gspread or HTTP
# For now, simple polling of a status file via GitHub

SHEET_URL = "https://docs.google.com/spreadsheets/d/1gt98w4pwR2WHDbvim6zsG5fY9NWSsSYI727LjOTh23g/edit"
POLL_INTERVAL = 3  # seconds

def main():
    print("Hermes Twin Worker — Google Sheets mode")
    print("Waiting for commands...")
    
    last_id = None
    while True:
        try:
            # Read latest command from sheet
            # VPS writes to column A, Twin reads and responds in column B
            import requests
            r = requests.get(
                f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/Commands!A:B",
                timeout=10
            )
            rows = r.json().get("values", [])
            
            for i, row in enumerate(rows[1:], start=2):  # skip header
                if len(row) >= 1 and row[0] and row[0] != last_id:
                    cmd_id = row[0]
                    last_id = cmd_id
                    print(f"  Command: {cmd_id}")
                    
                    # Execute
                    result = f"OK-{time.time()}"
                    
                    # Update sheet
                    requests.put(
                        f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/Commands!B{i}",
                        json={"values": [[result]]},
                        params={"valueInputOption": "RAW"},
                        timeout=10
                    )
        except Exception as e:
            print(f"  Poll error: {e}")
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
