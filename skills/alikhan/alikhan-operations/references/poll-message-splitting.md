# Poll Message Splitting (16.07.2026)

## Problem

WhatsApp has a message length limit (~4096 characters). The poll message with 37+ work items exceeded this limit. The `send_msg()` function truncates at 3800 chars, so the residuals list was cut off mid-message.

## Solution

Split `build_poll_message()` to return a tuple: `(header, residuals_or_None)`.

- **Header** (message 1): QA summary — personnel, equipment, incidents, materials, photos, plans. Fits in ~500 chars.
- **Residuals** (message 2, if any work items): work codes with ostatok, organized by building. Sent separately after a 1-second delay.

```python
def build_poll_message(work_items, qa_status):
    """Returns (header_part, residuals_part_or_None)."""
    # ... build header lines ...
    header = '\n'.join(lines)
    
    if not work_items:
        return header, None
    
    # Build residuals separately
    resid_lines = ["📊 **Остатки работ:**\n..."]
    residuals = '\n'.join(resid_lines)
    return header, residuals
```

Caller in `main_waha.py`:
```python
header, residuals = _build_poll_msg(work_items, qa_status)
send_msg(SANDBOX, header)
if residuals:
    time.sleep(1)
    send_msg(SANDBOX, residuals)
```

## Capacity guidelines

- Header: always < 1000 chars
- Residuals: ~100 chars per work item. At 37 items = ~3700 chars. Fits in one message.
- If residuals exceed 4000 chars, split further by building.
