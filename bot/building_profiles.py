import psycopg2, psycopg2.extras, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn

def get_profile_photos(building, limit=5):
    """Get recent confirmed photos for a building"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT id, content FROM bot_memory_messages 
        WHERE message_type='image' AND content LIKE %s 
        ORDER BY created_at DESC LIMIT %s""", (f'%[{building}]%', limit))
    photos = cur.fetchall()
    cur.close(); conn.close()
    return photos

def extract_features_from_full_photo(b64, building):
    """Grok extracts detailed visual features from a full building photo. Returns dict of features."""
    from handlers import ask_grok
    prompt = f"""Это фото здания «{building}» на стройплощадке ТЗРК Джеруй (2700м).
Извлеки ВСЕ визуальные детали которые помогут узнать это здание на других фото (фрагментах):
1. colors: список характерных цветов (профлист, колонны, опалубка, грунт)
2. elements: список видимых конструктивных элементов (двутавры, профлист, опалубка, арматура)
3. surroundings: что вокруг здания (дорога, отвал грунта, бытовки, другие здания, растительность)
4. stage: текущий этап работ (бетонирование/монтаж/земляные работы/армирование)
5. markers: любые уникальные приметы (граффити, маркировка на балках, цветная разметка, особые конструкции)

Ответь СТРОГО JSON: {{"colors":[],"elements":[],"surroundings":[],"stage":"","markers":[]}}"""
    try:
        result = ask_grok(prompt, image_base64=b64, mimetype='image/jpeg', max_tokens=400)
        # Parse JSON from response
        start = result.find('{')
        end = result.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(result[start:end])
    except:
        pass
    return {"colors":[],"elements":[],"surroundings":[],"stage":"","markers":[]}

def identify_building_from_fragment(b64):
    """Compare a fragment photo against both building profiles. Returns building name or None."""
    from handlers import ask_grok
    
    abk_photos = get_profile_photos('АБК', 5)
    dorm_photos = get_profile_photos('Общежитие', 5)
    
    if not abk_photos and not dorm_photos:
        return None
    
    context = f"""Ты — прораб на площадке ТЗРК Джеруй. Два здания: АБК (2 этажа) и Общежитие (3 этажа).
Определи здание по видимым деталям. Сравни с профилями ниже.
Ответь одним словом: АБК, Общежитие, или не_определено.

Профиль АБК:
{chr(10).join(f'- {p["content"][:200]}' for p in abk_photos) if abk_photos else 'нет фото'}

Профиль Общежития:
{chr(10).join(f'- {p["content"][:200]}' for p in dorm_photos) if dorm_photos else 'нет фото'}"""
    
    try:
        result = ask_grok(context, image_base64=b64, mimetype='image/jpeg', max_tokens=20)
        result = result.strip()
        if 'АБК' in result: return 'АБК'
        if 'Общежитие' in result: return 'Общежитие'
    except:
        pass
    return None

def update_building_profile(building, photo_content, features=None):
    """Accumulate features into building profile"""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT visual_features FROM bot_building_profiles WHERE building=%s", (building,))
    row = cur.fetchone()
    current = row['visual_features'] if row and row['visual_features'] else {}
    
    if features:
        for key in ['colors','elements','surroundings','markers']:
            existing = set(current.get(key, []))
            new = set(features.get(key, []))
            current[key] = list(existing | new)[:30]
        current['stage'] = features.get('stage', current.get('stage', ''))
    
    photo_ids = current.get('photo_ids', [])
    photo_ids.append(photo_content[:100])
    current['photo_ids'] = photo_ids[-50:]
    current['photo_count'] = len(photo_ids)
    
    cur.execute("""INSERT INTO bot_building_profiles (building, visual_features, updated_at)
        VALUES (%s, %s::jsonb, NOW()) ON CONFLICT (building) DO UPDATE SET visual_features=%s::jsonb, updated_at=NOW()""",
        (building, json.dumps(current), json.dumps(current)))
    conn.commit(); cur.close(); conn.close()
