# MPP File Extraction (2026-07-01)

Microsoft Project (.mpp) files are OLE2 compound documents. Full task extraction requires
MPXJ (Java-based) + jpype — not available in Hermes venv.

## What CAN be extracted (without Java)

### Project metadata (Props14 stream)
```python
import olefile, re

ole = olefile.OleFileIO(tmppath)
props14 = ole.openstream('Props14').read()

# Extract UTF-16LE strings
for m in re.finditer(b'(?:[\\x20-\\xff]{2}){5,}', props14):
    try:
        s = m.group().decode('utf-16-le', errors='ignore')
        if any('\u0400' <= c <= '\u04ff' for c in s):  # Cyrillic
            s = ''.join(c for c in s if c.isprintable() or c in ' \n/\\:')
            print(s.strip())
    except: pass
ole.close()
```

### Project name from Props stream
```python
props = ole.openstream(['   114', 'Props']).read()
text = props.decode('utf-16-le', errors='ignore')
# Project name follows marker \b after \x08
# Example output: "Строительство объекта: «Общежитие на 223 мест...»"
```

### OLE stream structure
Key streams: `   114/TBkndTask/Var2Data` (task data, binary encoded), `Props14` (metadata).

## What CANNOT be extracted (without Java)
- Task names, durations, dependencies, resource assignments
- Gantt chart data
- Calendar exceptions
- These require MPXJ (`pip install mpxj` + `pip install jpype` + Java runtime)

## WhatsApp download
```python
payload = json.dumps({"message": {"key": {"id": mid}}}).encode()
req = urllib.request.Request(f'{EVO}/chat/getBase64FromMediaMessage/alikhan',
    data=payload, headers={'apikey': KEY, 'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req, timeout=60)
b64 = json.loads(resp.read().decode()).get('base64', '')
```
