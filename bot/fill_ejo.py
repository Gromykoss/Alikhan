#!/usr/bin/env python3
"""fill_ejo.py — ЕЖО: погода + QA-факты → 3 листа (новый формат без Фототчет)"""
import sys, os, re, requests, json, urllib.request, base64, glob
from datetime import datetime, timedelta
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter as _gcl
from openpyxl.cell.cell import MergedCell
from openpyxl.styles import Alignment
from secret_config import get_evo_key

EVO = "http://127.0.0.1:8080"
KEY = get_evo_key(required=True)
TEMPLATE = "/home/hermes-workspace/Alikhan-migration/bot/templates/ЕЖО_шаблон.xlsx"


def get_active_phases(date):
    """Return set of phase_num values that are active on the given date.
    Reads bot_schedule_phases from DB, returns set of int phase_num
    where status='active' AND start_date <= date."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from db import get_conn
        import psycopg2.extras
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT DISTINCT phase_num FROM bot_schedule_phases "
            "WHERE status='active' AND start_date <= %s",
            (date,)
        )
        active = {r['phase_num'] for r in cur.fetchall() if r['phase_num'] is not None}
        cur.close()
        conn.close()
        print(f"[ACTIVE PHASES] {sorted(active)}", flush=True)
        return active
    except Exception as e:
        print(f"[ACTIVE PHASES ERR] {e}", flush=True)
        # Fallback: active phases 3,4,5,6,7 (as specified in task)
        return {3, 4, 5, 6, 7}


def calc_completion_pct(ws):
    """Calculate overall completion % across ALL work items (all sections).
    Weighted by plan_volume: sum(plan × completion_rate) / sum(plan) × 100.
    Section 1 (ПСД) = 6% of total project, always 100% complete.
    Other rows: rate = S/K (fact/plan), capped at 1.0.
    Column K(11) = план_всего (Кол-во), Column S(19) = факт_всего.
    Column C(3) = код работ.
    Returns percentage as integer (0-100)."""
    PSED_WEIGHT = 0.06  # ПСД = 6% от общего проекта
    total_weighted = 0.0
    total_weight = 0.0
    for r in range(24, ws.max_row + 1):
        cd = ws.cell(r, 3).value
        if not cd:
            continue
        code = str(cd).strip()
        if code.startswith('1.'):
            continue  # section 1 handled separately via PSED_WEIGHT
        k_val = ws.cell(r, 11).value
        try:
            plan = float(k_val) if k_val else 0.0
        except (ValueError, TypeError):
            plan = 0.0
        if plan <= 0:
            continue
        s_val = ws.cell(r, 19).value
        try:
            fact = float(s_val) if s_val else 0.0
        except (ValueError, TypeError):
            fact = 0.0
        rate = min(fact / plan, 1.0) if plan > 0 else 0.0
        total_weighted += plan * rate
        total_weight += plan
    if total_weight <= 0:
        return 0
    base_pct = total_weighted / total_weight * 100
    # Add section 1 (ПСД = 6%, 100% complete)
    result = round(base_pct * (1 - PSED_WEIGHT) + PSED_WEIGHT * 100)
    return min(result, 100)


def get_aibikon_headcount(date=None):
    """Extract АйБиКон headcount from latest timesheet, grouped by profession.
    Returns dict: {'total': N, 'by_prof': {'профессия': кол-во, ...}}"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from db import get_conn
        import psycopg2.extras
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, tags FROM bot_memory_messages WHERE message_type='document' AND content ILIKE '%табель%' ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row or not row.get('tags'):
            return {'total': 5, 'by_prof': {}}
        tags = row['tags'] if isinstance(row['tags'], dict) else {}
        msg_id = tags.get('msg_id', '')
        if not msg_id:
            return {'total': 5, 'by_prof': {}}
        payload = json.dumps({"message": {"key": {"id": msg_id}}}).encode()
        req = urllib.request.Request(f"{EVO}/chat/getBase64FromMediaMessage/alikhan",
            data=payload, headers={"apikey": KEY, "Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=30)
        b64 = json.loads(resp.read().decode()).get("base64", "")
        if not b64:
            return {'total': 5, 'by_prof': {}}
        import tempfile, base64 as _b64
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tf:
            tf.write(_b64.b64decode(b64))
            tf.flush()
            wb = load_workbook(tf.name, data_only=True)
        os.unlink(tf.name)
        
        # Find day-of-month column: column 5 = day 1
        if date:
            day = date.day
        else:
            day = datetime.now().day
        day_col = 5 + day - 1  # column 5 = day 1
        
        # Map табель professions → template professions
        PROF_MAP = {
            'рук.проекта': 'Руководителя строительства',
            'зам.рук.проекта': 'Руководителя строительства',
            'геодезист': 'Инженер геодезист',
            'тб': 'Инженер ТБ и ОТ',
            'пто': 'Инженер ПТО',
            'электрик': 'Электрик',
        }
        
        by_prof = {}
        for sn in wb.sheetnames:
            # Skip unrelated sheets
            if not any(w in sn.lower() for w in ['жер', 'итр', 'айбикон', 'джеруй', 'табель']):
                continue
            ws = wb[sn]
            for r in range(1, ws.max_row + 1):
                num = ws.cell(r, 1).value
                name = ws.cell(r, 2).value
                prof_raw = ws.cell(r, 3).value  # Должность (column C)
                if name and str(name).strip() and not any(w in str(name).lower() for w in ['фио', 'директор', 'руководител', 'согласовано', 'и.о.рук']):
                    try:
                        n = int(str(num).replace('№', '').strip())
                        if n >= 1:
                            cell = ws.cell(r, day_col)
                            val = cell.value
                            # Skip explicit non-work values (отпуск, etc.)
                            if val is not None and str(val).strip().lower() in ('отпуск', 'отп', 'больничный'):
                                continue
                            # Check cell fill color: solid fill with non-white theme = worked 8h
                            fill = cell.fill
                            if fill.patternType == 'solid' and fill.fgColor.theme is not None and fill.fgColor.theme != 0:
                                prof = str(prof_raw).strip().lower() if prof_raw else ''
                                # Try exact lowercase match first, then original case
                                prof_name = PROF_MAP.get(prof)
                                if prof_name is None:
                                    prof_name = PROF_MAP.get(str(prof_raw).strip().lower())
                                if prof_name is None:
                                    prof_name = prof  # keep original if not mapped
                                by_prof[prof_name] = by_prof.get(prof_name, 0) + 1
                    except:
                        pass
        wb.close()
        total = sum(by_prof.values())
        return {'total': max(total, 1), 'by_prof': by_prof}
    except Exception as e:
        print(f"[TABEL ERR] {e}", flush=True)
        return {'total': 5, 'by_prof': {}}


def get_code_source():
    """Use latest report to find all work codes (user may add sub-items)."""
    import glob
    files = sorted(glob.glob("/tmp/ЕЖО_20*_v*.xlsx"))
    for f in reversed(files):
        if f != TEMPLATE:
            try:
                wb = load_workbook(f, data_only=True)
                if wb.sheetnames:
                    return wb, wb[wb.sheetnames[0]]
            except: pass
    return None, None


def db():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db import get_conn; return get_conn()


def qa(date, cat=None):
    import psycopg2, psycopg2.extras
    c = db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    ds = date.strftime("%Y-%m-%d")
    c.execute("SELECT fact FROM bot_memory_facts WHERE fact_date=%s AND source='qa'" + (f" AND category='{cat}'" if cat else ""), (ds,))
    r = c.fetchall(); c.close(); return r


def weather(date):
    try:
        ds = date.strftime('%Y-%m-%d')
        url = (f"https://api.open-meteo.com/v1/forecast?latitude=42.284&longitude=72.765"
               f"&daily=temperature_2m_max,temperature_2m_min,wind_speed_10m_max,wind_direction_10m_dominant"
               f"&current=relative_humidity_2m,pressure_msl&timezone=Asia/Bishkek&start_date={ds}&end_date={ds}")
        r = requests.get(url, timeout=15)
        if r.status_code != 200: return {}
        d = r.json(); dl = d.get('daily',{}); cr = d.get('current',{})
        w = {}
        if dl:
            mx, mn = dl['temperature_2m_max'][0], dl['temperature_2m_min'][0]
            ws, wd = dl['wind_speed_10m_max'][0], dl['wind_direction_10m_dominant'][0]
            dirs = ['С','СВ','В','ЮВ','Ю','ЮЗ','З','СЗ']
            w['t'] = f"{round((mx+mn)/2)}°C"
            w['w'] = f"{dirs[round(wd/45)%8]} {str(ws).replace('.', ',')} км/ч" if wd is not None else f"{str(ws).replace('.', ',')} км/ч"
        if cr:
            hum = cr.get('relative_humidity_2m', 50)
            w['h'] = f"{hum}%"
            if cr.get('pressure_msl'): w['p'] = f"{round(cr['pressure_msl']*0.75006)} мм рт.ст."
            if hum > 90: vis = '2-3 км'
            elif hum > 75: vis = '5-7 км'
            elif hum > 60: vis = '8-10 км'
            else: vis = '10+ км'
            w['v'] = vis
        return w
    except: return {}


def incidents(date):
    f = qa(date, 'инцидент')
    if not f: return "0"
    for x in f:
        if 'нет' in (x['fact'] or '').lower(): return "0"
    return str(len(f))


def staff(date):
    f = qa(date, 'персонал'); mp = {'атантай':'Атантай','майкадам':'Майкадам','наватек':'Наватек'}
    r = {}
    for x in f:
        t = (x['fact'] or '').lower()
        # Combined format: "Атантай ИТР 1, рабочих 6"
        m1 = re.search(r'(атантай|майкадам|наватек)\s+(\d+)\s*итр[,\s]*(\d+)\s*рабоч', t)
        m2 = re.search(r'(атантай|майкадам|наватек)\s*итр\s*(\d+)[,\s]*рабоч\w*\s*(\d+)', t, re.I)
        m3 = re.search(r'итр\s*(\d+)[,\s]*рабоч\w*\s*(\d+)\s*\(?(\w+)', t, re.I)
        if m1: nm, i, wk = mp[m1.group(1)], int(m1.group(2)), int(m1.group(3))
        elif m2: nm, i, wk = mp[m2.group(1)], int(m2.group(2)), int(m2.group(3))
        elif m3: nm, i, wk = mp.get(m3.group(3).lower(), ''), int(m3.group(1)), int(m3.group(2))
        else:
            # Split format: "Атантай ИТР 1" or "Атантай 6 рабочих"
            m4 = re.search(r'(атантай|майкадам|наватек)\s+итр\s+(\d+)', t)
            m5 = re.search(r'(атантай|майкадам|наватек)\s+(\d+)\s*рабоч', t)
            if m4:
                nm = mp[m4.group(1)]
                if nm not in r: r[nm] = {'t':0,'i':0,'w':0}
                r[nm]['i'] += int(m4.group(2)); r[nm]['t'] += int(m4.group(2))
            if m5:
                nm = mp[m5.group(1)]
                if nm not in r: r[nm] = {'t':0,'i':0,'w':0}
                wk = int(m5.group(2)); r[nm]['w'] += wk; r[nm]['t'] += wk
            continue
        if nm: r[nm] = {'t': i+wk, 'i': i, 'w': wk}
    for n in ['Атантай','Майкадам','Наватек','Алтын-Тас']:
        if n not in r: r[n] = {'t':0,'i':0,'w':0}
    return r


def volumes(date):
    """{code: vol}. Supports 3- and 4-part codes. Comma decimals. Bare = done.
    Queries ALL QA facts (any category) — regex filters for work code patterns."""
    f = qa(date)  # all categories — regex below filters for work codes
    dn, pn = {}, {}
    for x in f:
        txt = (x.get('fact','') or '').replace(',', '.')
        # Match 3-part (2.3.1) or 4-part (2.2.3.1) codes
        m = re.search(r'(\d+\.\d+\.\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)', txt)
        if m:
            cd, vl = m.group(1), float(m.group(2))
            is_done = 'сделано' in txt.lower()
            is_plan = 'план' in txt.lower()
            if is_done or (not is_done and not is_plan): dn[cd] = vl
            elif is_plan and cd not in dn: pn[cd] = vl
    r = dict(pn); r.update(dn); return r


def photos(date):
    import psycopg2, psycopg2.extras
    c = db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT coalesce(tags->>'building','Общий план') as b, count(*) as n FROM bot_memory_messages WHERE message_type='image' AND DATE(created_at)=%s GROUP BY 1", (date.strftime('%Y-%m-%d'),))
    ct = {'Общежитие':0,'АБК':0,'Галерея':0,'Общий план':0}
    for r in c.fetchall():
        b = r['b']
        if b == 'без тега': b = 'Общий план'
        if b in ct: ct[b] = r['n']
        elif b: ct['Общий план'] += r['n']
    c.close(); return ct


def yesterday_cum(date, code):
    yd = date - timedelta(days=1)
    for v in range(10,0,-1):
        p = f"/tmp/ЕЖО_{yd.strftime('%Y-%m-%d')}_v{v}.xlsx"
        if os.path.exists(p):
            try:
                wb = load_workbook(p, data_only=True); ws = wb[wb.sheetnames[0]]
                for r in range(24, ws.max_row+1):
                    if str(ws.cell(r,3).value) == code:
                        pm = ws.cell(r,16).value; pt = ws.cell(r,19).value; wb.close()
                        return (float(pm) if pm else 0, float(pt) if pt else 0)
                wb.close()
            except: pass
    return (0, 0)


def yellow(cell):
    try: return any(c in str(cell.fill.start_color.rgb).upper() for c in ['FFFF00','FFEB9C','FFD700','FFC000','FFCC00'])
    except: return False


def sw(ws, r, c, v, center=False, keep_fill=False):
    cell = ws.cell(row=r, column=c)
    if isinstance(cell, MergedCell):
        for mr in ws.merged_cells.ranges:
            if cell.coordinate in mr: cell = ws.cell(row=mr.min_row, column=mr.min_col); break
    was_yellow = yellow(cell)
    cell.value = v
    if center: cell.alignment = Alignment(horizontal='center', vertical='center')
    # Clear yellow fill after writing (user wants white, not yellow leftovers)
    if was_yellow and v is not None and not keep_fill:
        from openpyxl.styles import PatternFill
        cell.fill = PatternFill(fill_type=None)


def set_fill(ws, r, c, theme, tint=0.0):
    """Set cell fill using theme color + tint. theme=3 (blue), theme=4 (yellow)."""
    from openpyxl.styles import PatternFill, Color
    cell = ws.cell(row=r, column=c)
    cell.fill = PatternFill(patternType='solid', start_color=Color(theme=theme, tint=tint))


def fill(date):
    wb = load_workbook(TEMPLATE, data_only=True)  # preserve cached values, drop formulas
    w = weather(date); inc = incidents(date); stf = staff(date); vols = volumes(date)
    print(f"[VOLUMES] Found {len(vols)} work codes: {vols}", flush=True)
    if not vols:
        print(f"[VOLUMES] WARNING: No volume data found for {date}. Check QA facts for work code patterns (e.g. 3.3.2.1 = 2000).", flush=True)
    aibikon = get_aibikon_headcount(date)  # from timesheet for report date
    df = date.strftime('%d.%m.%Y')
    src_wb, src_ws = get_code_source()
    
    # Load active phases from DB
    active_phases = get_active_phases(date)
    
    for name in wb.sheetnames:
        ws = wb[name]
        if name == "Ежедневный отчет":
            sw(ws, 6, 4, df, True)
            # Fill yellow cells by position (instruction matching unreliable on filled templates)
            # Staff data for direct cell filling
            def staff_val(contractor, key):
                if contractor == 'Алтын-Тас': return '0'
                s = stf.get(contractor, {'t':0,'i':0,'w':0})
                if key == 't': return str(s['t'])
                if key == 'th': return str(s['t'] * 8)  # human-hours
                if key == 'i': return str(s['i'])
                if key == 'ih': return str(s['i'] * 8)  # ITR human-hours
                return '0'
            swaps = {
                'G4': w.get('t'), 'G5': w.get('w'), 'D6': df,
                'G6': w.get('h'), 'G7': w.get('v'), 'G8': w.get('p'),
                'E11': inc, 'F11': inc, 'G11': inc,
                'E12': inc, 'F12': inc, 'G12': inc,
                'M11': str(aibikon['total']), 'N11': staff_val('Атантай','t'),
                'O11': staff_val('Майкадам','t'), 'P11': staff_val('Наватек','t'),
                'M12': str(aibikon['total'] * 8), 'N12': staff_val('Атантай','th'),
                'O12': staff_val('Майкадам','th'), 'P12': staff_val('Наватек','th'),
                'M17': str(aibikon['total'] * 8), 'N17': staff_val('Атантай','th'),
                'O17': staff_val('Майкадам','th'), 'P17': staff_val('Наватек','th'),
                'Q11': staff_val('Алтын-Тас','t'), 'Q12': staff_val('Алтын-Тас','th'),
                'Q17': staff_val('Алтын-Тас','th'), 'Q18': staff_val('Алтын-Тас','ih'),
                'M18': str(aibikon['total'] * 8), 'N18': staff_val('Атантай','ih'),
                'O18': staff_val('Майкадам','ih'), 'P18': staff_val('Наватек','ih'),
            }
            def get_val(spec):
                if isinstance(spec, str): return spec
                if isinstance(spec[0], dict):  # {stf, name, key}
                    d = spec
                    cname = spec[1]
                    key = spec[2] if len(spec) > 2 else None
                    s = d[0].get(cname, {'t':0,'i':0,'w':0})
                    if key == 't': return str(s['t'])
                    elif key == 'i': return str(s['i'])
                    elif key == 'w': return str(s['w'])
                    else: return str(s['t'] * 8)  # human-hours
                return None
            weather_cells = {'G4', 'G5', 'G6', 'G7', 'G8'}
            for ref, spec in swaps.items():
                col_l, row_n = ord(ref[0]) - ord('A') + 1, int(ref[1:])
                cell = ws.cell(row=row_n, column=col_l)
                if yellow(cell):
                    val = get_val(spec)
                    if val is not None:
                        sw(ws, row_n, col_l, val, True, keep_fill=(ref in weather_cells))
            # Personnel header cells must always come from current data. The
            # template may contain user-corrected, non-yellow values from the
            # previous report.
            for ref in [
                'M11', 'N11', 'O11', 'P11', 'Q11',
                'M12', 'N12', 'O12', 'P12', 'Q12',
                'M17', 'N17', 'O17', 'P17', 'Q17',
                'M18', 'N18', 'O18', 'P18', 'Q18',
            ]:
                col_l, row_n = ord(ref[0]) - ord('A') + 1, int(ref[1:])
                val = get_val(swaps[ref])
                if val is not None:
                    sw(ws, row_n, col_l, val, True)
            # Weather cells must always be current (keep yellow fill)
            for ref in ['G4', 'G5', 'G6', 'G7', 'G8']:
                col_l, row_n = ord(ref[0]) - ord('A') + 1, int(ref[1:])
                val = swaps.get(ref)
                if val is not None:
                    sw(ws, row_n, col_l, val, True, keep_fill=True)
            # Also fill yellow instruction cells (for any missed)
            for row in ws.iter_rows():
                for cell in row:
                    if not yellow(cell) or not cell.value: continue
                    ins = str(cell.value).lower() if cell.value else ''; val = None
                    if val: sw(ws, cell.row, cell.column, val, True)
            # Clear daily values for ALL rows (prevents template contamination from previous days)
            # Cumulative columns (16, 17, 19, 20, 21) are preserved — they carry forward via yesterday_cum()
            for r in range(24, 852):  # rows up to 851 are data
                cd_val = ws.cell(r, 3).value
                if cd_val:  # any row with a VOR code
                    for c in [12, 13, 14]:  # only daily columns
                        sw(ws, r, c, None)
                    # Also clear cumulative if code has work today (will be refilled)
                    if str(cd_val) in vols:
                        for c in [16, 19, 21]:
                            sw(ws, r, c, None)
            # Clear ALL yellow from data rows (will re-add for active rows)
            from openpyxl.styles import PatternFill, Color
            for r in range(24, 852):
                for c in range(1, 22):
                    cell = ws.cell(r, c)
                    if yellow(cell):
                        cell.fill = PatternFill(fill_type=None)
            
            # Determine which section phase a row belongs to based on row order
            # Work items are ordered by section: rows 24-60 = Phase 2, rows 61-84 = Phase 3, etc.
            # We need to map phase_num based on section boundaries
            # Phase mapping based on template structure:
            # R22: '2 ЭТАП' → Phase 2 (already completed, but keep in template)
            # R61: '3 ЭТАП' → Phase 3
            # R85: '4 ЭТАП' → Phase 4
            # R131: '5. ЭТАП' → Phase 5
            # R591: '6 ЭТАП' → Phase 6
            # R717: '7 ЭТАП' → Phase 7
            # R794: '8 ЭТАП' → Phase 8
            section_boundaries = {
                2: (24, 60),
                3: (61, 84),
                4: (85, 130),
                5: (131, 590),
                6: (591, 716),
                7: (717, 793),
                8: (794, 851),
            }
            
            def get_phase_for_row(row_num):
                for phase, (start, end) in section_boundaries.items():
                    if start <= row_num <= end:
                        return phase
                return None
            
            # Identify which phases are "active" — either in active_phases set
            # or the phase has vols data for today
            phases_with_vols = set()
            for r in range(24, 852):
                cd = ws.cell(r, 3).value
                if cd and str(cd) in vols:
                    phase = get_phase_for_row(r)
                    if phase:
                        phases_with_vols.add(phase)
            
            # A phase is "in work" if it's in active_phases OR has volumes today
            in_work_phases = active_phases | phases_with_vols
            print(f"[IN WORK PHASES] phases_with_vols={sorted(phases_with_vols)} active={sorted(active_phases)} → in_work={sorted(in_work_phases)}", flush=True)
            
            # Fill volumes for today
            for r in range(24, 852):
                cd = ws.cell(r,3).value
                if not cd or str(cd) not in vols: continue
                cs = str(cd); v = vols[cs]
                mp = ws.cell(r,15).value; tp = ws.cell(r,18).value
                k_plan = ws.cell(r,11).value
                # Read cumulative FROM TEMPLATE (previous report)
                def parse_val(val):
                    if val is None: return 0
                    try: return float(val)
                    except: return 0
                prev_p = parse_val(ws.cell(r,16).value)
                # Use yesterday's file for clean cumulative data
                yp, ys = yesterday_cum(date, cs)
                # If code has work today, use yesterday's cumulative (template may
                # already include today's data after user correction — avoid double-count)
                if v > 0:
                    prev_p = yp
                    prev_s = ys
                else:
                    # No work today — keep template value (or yesterday's if larger)
                    prev_p = max(prev_p, yp)
                    prev_s = max(parse_val(ws.cell(r,19).value), ys)

                # Daily values
                sw(ws, r, 12, v, True)
                sw(ws, r, 13, v, True)
                sw(ws, r, 14, 1, True)
                # Month cumulative
                sw(ws, r, 16, round(prev_p+v, 2), True)
                if mp: sw(ws, r, 17, round((prev_p+v)/float(mp), 2), True)
                # Total cumulative
                sw(ws, r, 19, round(prev_s+v, 2), True)
                if tp: sw(ws, r, 20, round((prev_s+v)/float(tp), 2), True)
                # L = M = факт за сутки
                sw(ws, r, 12, v, True)
                sw(ws, r, 13, v, True)
                sw(ws, r, 14, 1, True)
                # Write plain numbers (never formulas)
                sw(ws, r, 16, round(prev_p+v, 2), True)
                if mp: sw(ws, r, 17, round((prev_p+v)/float(mp), 2), True)  # fraction for % format
                sw(ws, r, 19, round(prev_s+v, 2), True)
                if tp: sw(ws, r, 20, round((prev_s+v)/float(tp), 2), True)  # fraction for % format
                if k_plan and prev_s+v > 0:
                    try: sw(ws, r, 21, round(float(k_plan)-prev_s-v, 1), True)
                    except: pass
            
            # OVERRIDE: Row 77 (3.3.2.1) — hardcoded cumulative = 5790 (72.5% of 7981.29)
            # User confirmed: month cumulative fact = 5790, total cumulative = 5790
            sw(ws, 77, 16, 5790, True)   # P77 month cumulative
            sw(ws, 77, 19, 5790, True)   # S77 total cumulative
            sw(ws, 77, 17, 0.725, True)  # Q77 month % (fraction for % format)
            sw(ws, 77, 20, 0.725, True)  # T77 total % (fraction for % format)
            try: sw(ws, 77, 21, round(float(ws.cell(77,11).value or 0) - 5790, 1), True)  # U77 remaining
            except: pass
            
            # Apply yellow fill: entire rows A-U for work items WITH volumes today
            # Only rows where L (plan) or M (fact) column has a value
            yellow_fill = PatternFill(start_color=Color(rgb='FFFF00'), end_color=Color(rgb='FFFF00'), fill_type='solid')
            for r in range(24, 852):
                cd = ws.cell(r, 3).value
                if not cd:
                    continue
                # Check if row has volume data for today (L=12 or M=13)
                plan_val = ws.cell(r, 12).value
                fact_val = ws.cell(r, 13).value
                has_volume = False
                try:
                    if plan_val is not None and float(plan_val) > 0:
                        has_volume = True
                    if fact_val is not None and float(fact_val) > 0:
                        has_volume = True
                except (ValueError, TypeError):
                    pass
                if has_volume:
                    # Entire row A-U yellow
                    for c in range(1, 22):
                        ws.cell(r, c).fill = yellow_fill
            
            # Style section header rows: light blue (theme=3, tint=0.8) instead of yellow
            for r in range(22, 852):
                cell_a = ws.cell(r, 1)
                if yellow(cell_a) and cell_a.value and 'ЭТАП' in str(cell_a.value).upper():
                    for c in range(1, 22):
                        set_fill(ws, r, c, 3, 0.8)
            # Row 20 subheader: bold, 14pt, solid fill
            from openpyxl.styles import Font as _Font
            for c in range(1, 22):
                cell = ws.cell(20, c)
                cell.font = _Font(bold=True, size=14)
            # "Количество" → "Кол-во"
            if ws.cell(20, 11).value and 'Количество' in str(ws.cell(20, 11).value):
                sw(ws, 20, 11, 'Кол-во', True)
            # Remove yellow "—" cells → None
            for r in range(24, 852):
                for c in [12, 13, 14]:
                    cell = ws.cell(r, c)
                    if str(cell.value).strip() == '—':
                        cell.value = None
            
            # CHANGE 3: Write completion % to K853, clear J853 placeholder
            pct = calc_completion_pct(ws)
            print(f"[COMPLETION %] Вычислено: {pct}% → K853", flush=True)
            # Clear J853 "x%" placeholder
            sw(ws, 853, 10, None)
            # K853 = completion with % sign + yellow fill
            sw(ws, 853, 11, f"{pct}%", True)
            yellow_fill = PatternFill(start_color=Color(rgb='FFFF00'), end_color=Color(rgb='FFFF00'), fill_type='solid')
            ws.cell(853, 11).fill = yellow_fill  # K853
            
            # CHANGE 1: Photo report in rows 856-859 (was separate sheet "Фототчет")
            building_cols = {'Общежитие': 2, 'АБК': 3, 'Галерея': 4, 'Общий план': 5, 'Общие планы': 5}
            # Map template labels to building names
            label_to_building = {
                'общежите': 'Общежитие',  # template has this typo
                'общежитие': 'Общежитие',
                'абк': 'АБК',
                'галерея': 'Галерея',
                'общие планы': 'Общий план',
                'общий план': 'Общий план',
            }
            # Determine which building column each row maps to
            photo_rows = {}  # building_name -> (row_num, col_num)
            for r in range(856, 860):
                a_val = str(ws.cell(r, 1).value or '').strip().lower()
                if a_val in label_to_building:
                    bld = label_to_building[a_val]
                    col = building_cols.get(bld, 5)
                    photo_rows[bld] = (r, col)
            print(f"[PHOTO ROWS] {photo_rows}", flush=True)
            
            # Download and insert photos from DB
            import psycopg2, psycopg2.extras
            c = db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            c.execute(
                "SELECT content as fp, tags->>'building' as b FROM bot_memory_messages "
                "WHERE message_type='image' AND DATE(created_at)=%s",
                (date.strftime('%Y-%m-%d'),)
            )
            
            # Fixed photo column positions: 1→C, 2→E, 3→J, 4→N, 5→Q
            PHOTO_COLS = [3, 5, 10, 14, 17]
            
            # Track photo count per building
            photo_count = {'Общежитие': 0, 'АБК': 0, 'Галерея': 0, 'Общий план': 0}
            
            # Clear ALL old images from template
            ws._images.clear()
            
            # Unmerge cells in photo rows 856-859
            merged_to_remove = []
            for mr in ws.merged_cells.ranges:
                if mr.min_row >= 856 and mr.min_row <= 859:
                    merged_to_remove.append(str(mr))
            for mr_str in merged_to_remove:
                ws.unmerge_cells(mr_str)
            
            for p in c.fetchall():
                bld = p['b'] or 'Общий план'
                if bld in ('без тег', 'без тега'):
                    bld = 'Общий план'
                if bld not in photo_rows:
                    if 'Общий план' in photo_rows:
                        bld = 'Общий план'
                    else:
                        continue
                row_num, _ = photo_rows.get(bld, photo_rows.get('Общий план', (859, 5)))
                idx = photo_count.get(bld, 0)
                if idx >= len(PHOTO_COLS):
                    continue
                photo_col = PHOTO_COLS[idx]
                photo_count[bld] = idx + 1
                
                msg_id = p.get('fp', '')
                if msg_id:
                    try:
                        req = urllib.request.Request(
                            f"{EVO}/chat/getBase64FromMediaMessage/alikhan",
                            data=json.dumps({"message": {"key": {"id": msg_id}}}).encode(),
                            headers={"apikey": KEY, "Content-Type": "application/json"}
                        )
                        resp = urllib.request.urlopen(req, timeout=30)
                        b64 = json.loads(resp.read().decode()).get("base64", "")
                        if b64:
                            import io, base64 as _b64
                            img_data = _b64.b64decode(b64)
                            from openpyxl.drawing.image import Image as XI
                            img = XI(io.BytesIO(img_data))
                            img.width = 355
                            img.height = 267
                            col_letter = chr(64 + photo_col)
                            ws.add_image(img, f"{col_letter}{row_num}")
                    except Exception as ex:
                        print(f"Photo err: {ex}", flush=True)
            c.close()
        
        if name == "Персонал и техника":
            sw(ws, 4, 1, df, True)
            # Fill АйБиКон professions from timesheet (by_prof)
            prof_rows = {
                'Руководителя строительства': 9,
                'Инженер геодезист': 10,
                'Инженер ТБ и ОТ': 11,
                'Инженер ПТО': 12,
                'Электрик': 13,
            }
            by_prof = aibikon.get('by_prof', {})
            for prof_name, row_num in prof_rows.items():
                sw(ws, row_num, 2, str(by_prof.get(prof_name, 0)), True)
            # HARDCODE: Руководителя строительства всегда 1 (row 9)
            # Even if timesheet has 0 or 2+, the руководитель is always exactly 1 person.
            sw(ws, 9, 2, "1", True)
            # Update total row (row 8) for АйБиКон
            sw(ws, 8, 2, str(aibikon['total']), True)
            for nm, tr, ps in [
                ('Атантай',14,[(15,'i'),(16,'w'),(17,None),(18,None),(19,None)]),
                ('Майкадам',20,[(21,'i'),(22,'w')]),
                ('Наватек',23,[(24,'i'),(25,'i'),(26,'i'),(27,'w'),(28,None),(29,None)]),
                ('Алтын-Тас',30,[(31,None),(32,'w')]),
            ]:
                d = stf.get(nm, {'t':0,'i':0,'w':0})
                sw(ws, tr, 2, str(d['t']), True)
                il, ns = d['i'], sum(1 for _,r in ps if r=='i')
                for rw, rl in ps:
                    if rl == 'i': v = str(il) if ns <= 1 else ('1' if il > 0 else '0'); il -= 1 if ns > 1 and il > 0 else 0
                    elif rl == 'w': v = str(d['w'])
                    else: v = '0'
                    sw(ws, rw, 2, v, True)
            et = ' '.join(x.get('fact','') for x in qa(date, 'техника')).lower()
            sw(ws, 35, 1, 'Статистика по технике', True)
            sw(ws, 36, 1, 'Наименование', True); sw(ws, 36, 2, 'Кол-во', True)
            equip = {37:'Самосвал',38:'Экскаватор',39:'Фронтальный погрузчик',40:'Каток',41:'Бетононасос'}
            for r, en in equip.items():
                sw(ws, r, 1, en, True)
                sw(ws, r, 2, '0' if 'нет' in et else str(max(et.count(en.lower()[:5]),0)), True)
        if name == "Материалы и планы":
            sw(ws, 4, 1, df, True)
            # Materials: parse from QA data 'документация' category
            # Look for facts matching 'материал' or 'материалы'
            mat_facts = [f['fact'] for f in qa(date, 'документация')]
            # Also search all categories for material keywords
            all_qa = qa(date)
            for fx in all_qa:
                f_text = (fx.get('fact','') or '').lower()
                cat = (fx.get('category','') or '').lower()
                if 'материал' in f_text and fx['fact'] not in mat_facts:
                    mat_facts.append(fx['fact'])
            if mat_facts and not any('не планируется' in f.lower() or 'нет' in f.lower() for f in mat_facts):
                # Has new material data — parse and fill rows 13-22
                # Format example: "Поставка материалов ТСП - 288м2"
                # Parse material name + quantity from QA facts
                parsed_materials = []
                for fact in mat_facts:
                    # Try to parse: "Материал X - 100м2" or "X 100м2" or "X = 100 м2"
                    m = re.search(r'(?:материал[:s]*)?(.+?)\s*[-=]\s*(\d+(?:[.,]\d+)?)\s*(м[2³]|м3|т|шт|кг|кв\.м)', fact, re.I)
                    if m:
                        name = m.group(1).strip().capitalize()
                        qty = m.group(2).replace(',', '.')
                        unit = m.group(3)
                        parsed_materials.append({'name': name, 'qty': qty, 'unit': unit})
                    else:
                        # Fallback: just take the whole text as material name with quantity
                        m2 = re.search(r'(\d+(?:[.,]\d+)?)\s*(м[2³]|м3|т|шт|кг)', fact, re.I)
                        if m2:
                            # Remove numeric part to get name
                            name = re.sub(r'\s*[-=]\s*\d+(?:[.,]\d+)?.*$', '', fact).strip()
                            name = re.sub(r'^\d+[.)]\s*', '', name).strip().capitalize()
                            qty = m2.group(1).replace(',', '.')
                            unit = m2.group(2)
                            parsed_materials.append({'name': name or 'Материал', 'qty': qty, 'unit': unit})
                if parsed_materials:
                    # Clear ONLY rows that will be filled (avoid leaving stale values in unused rows)
                    for row in range(13, 23):
                        for c in [2, 3, 4, 5, 6, 7, 8]:
                            sw(ws, row, c, None, True)
                    # Fill parsed materials starting at row 14 (first data row under header)
                    for i, mat in enumerate(parsed_materials[:10]):  # max 10 materials
                        row = 14 + i
                        sw(ws, row, 1, str(i + 1), True)       # №
                        sw(ws, row, 2, mat['name'], True)      # Наименование
                        sw(ws, row, 3, mat['unit'], True)      # Ед.изм
                        sw(ws, row, 4, mat['qty'], True)       # Кол-во
                print(f"[MATERIALS] Parsed {len(parsed_materials)} material items from QA", flush=True)
            else:
                # No new material data — preserve existing template values
                # Only clear yellow cells (which are old automatically filled values)
                # Keep non-yellow values (user corrections from previous days)
                for row in range(13, 23):
                    for c in [2, 3, 4, 5, 6, 7, 8]:
                        cell = ws.cell(row=row, column=c)
                        if yellow(cell):
                            sw(ws, row, c, None, True)
                print(f"[MATERIALS] No new material data — preserving template values", flush=True)
            for cr in ['F6','H6','F13']:
                ci = ord(cr[0])-ord('A')+1; rn = int(cr[1:])
                cell = ws.cell(row=rn, column=ci)
                old_v = str(cell.value or '')
                # Keep label text, replace date
                if 'Всего' in old_v or 'Остаток' in old_v:
                    import re as _re
                    # Replace ALL date patterns with current date
                    new_label = _re.sub(r'\d{2}\.\d{2}\.\d{4}г?\.?', f'{df}г.', old_v)
                    # If no date was found, append; otherwise replacement sufficed
                    if not _re.search(r'\d{2}\.\d{2}\.\d{4}', new_label):
                        new_label = f'{old_v.strip()} на {df}г.'
                    sw(ws, rn, ci, new_label, True)
                elif yellow(cell):
                    sw(ws, rn, ci, df, True)

            ws1 = wb[wb.sheetnames[0]]
            code_info = {}
            for r in range(24, ws1.max_row+1):
                cd = ws1.cell(r,3).value; bd = ws1.cell(r,1).value
                nm = ws1.cell(r,4).value; un = ws1.cell(r,10).value
                if cd and bd: code_info[str(cd)] = (str(bd), str(nm)[:80] if nm else '', str(un) if un else '')
            bld_plans = {'Общежитие': [], 'АБК': [], 'Галерея': []}
            pf = [x['fact'] for x in qa(date) if 'план' in (x.get('fact','') or '').lower()]
            for p in pf:
                txt = p.replace(',', '.')
                m = re.search(r'(\d+\.\d+\.\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)', txt)
                if m:
                    code, qty = m.group(1), m.group(2)
                    if code in code_info:
                        bld = code_info[code][0]
                        if bld in bld_plans:
                            bld_plans[bld] = [(c,n,u,q) for (c,n,u,q) in bld_plans[bld] if c!=code]
                            nm = code_info[code][1]; un = code_info[code][2]
                            bld_plans[bld].append((code, nm, un, qty))
            bld_rows = [('АБК', 16), ('Общежитие', 19), ('Галерея', 22)]
            seq = 1
            for bld, start_row in bld_rows:
                # Building header row: seq number + building name
                sw(ws, start_row - 1, 1, str(seq), True)
                sw(ws, start_row - 1, 2, bld, True)
                seq += 1
                items = bld_plans.get(bld, [])
                for i in range(2):
                    row = start_row + i
                    if i < len(items):
                        code, nm, un, qty = items[i]
                        sw(ws, row, 1, code, True)
                        sw(ws, row, 2, nm, True)
                        sw(ws, row, 3, un, True)
                        sw(ws, row, 4, qty, True)
                        for r in range(24, ws1.max_row+1):
                            if str(ws1.cell(r,3).value) == code:
                                ost = ws1.cell(r,21).value
                                if ost: sw(ws, row, 6, ost, True)
                                break
                    else:
                        sw(ws, row, 1, None, True); sw(ws, row, 2, None, True)
                        sw(ws, row, 3, None, True); sw(ws, row, 4, None, True)
                        sw(ws, row, 6, None, True)  # clear leftover остаток
        ds = date.strftime("%Y-%m-%d"); v = 1
    while os.path.exists(f"/tmp/ЕЖО_{ds}_v{v}.xlsx"): v += 1
    op = f"/tmp/ЕЖО_{ds}_v{v}.xlsx"
    wb.save(op)
    print(f"✅ {op} (v{v})")
    return op


if __name__ == "__main__":
    d = datetime.strptime(sys.argv[1], "%Y-%m-%d") if len(sys.argv) > 1 else datetime.now()
    ds = d.strftime("%Y-%m-%d")
    # Guard: skip if EJO already exists for this date
    existing = sorted(glob.glob(f"/tmp/ЕЖО_{ds}_v*.xlsx"))
    if existing:
        print(f"⚠️ ЕЖО за {ds} уже существует (v{len(existing)}). Пропускаю.", file=sys.stderr)
        sys.exit(0)
    fill(d)
