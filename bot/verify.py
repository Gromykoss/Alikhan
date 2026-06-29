"""Verification module — Claude Code pattern: verify > write, 2-3x quality.
Checks agent output for hallucinations, completeness, and format compliance.
Returns (verified_text, score, issues_list).
"""
import sys, os
from typing import Optional

def verify_reply(reply: str, question: str, db_facts: Optional[str] = None,
                 db_facts_available: bool = False) -> tuple:
    """Verify agent reply and flag issues. Returns (reply, score_0_100, issues).
    
    Score interpretation:
      90-100: VERIFIED — reply is accurate and complete
      70-89:  MINOR — small issues, still usable
      40-69:  FLAG — needs review, possible hallucination
      0-39:   REJECT — hallucination or completely wrong
    
    db_facts_available: if False, 'уточни в БД' is acceptable.
    """
    from handlers import ask_grok
    
    facts_context = f"\nФакты из БД:\n{db_facts}" if db_facts else "\n(фактов из БД нет)"
    
    leniency_note = ""
    if not db_facts and not db_facts_available:
        leniency_note = "\nВ БД НЕТ фактов по этому запросу — ответ 'уточни в БД' или 'данных нет' считается ПОЛНЫМ и корректным."
    
    prompt = f"""Проверь ответ агента-прораба. Оцени по трём критериям и дай оценку 0-100.
{leniency_note}
{facts_context}

Вопрос прораба: {question[:500]}

Ответ агента: {reply[:500]}

Критерии:
1. ТОЧНОСТЬ: цифры и факты совпадают с данными из БД? Нет выдуманных чисел?
2. ПОЛНОТА: ответ отвечает на вопрос? Не уходит в сторону?
3. ФОРМАТ: коротко (1-2 предложения), по делу, без воды? Стиль прораба?

Верни ТОЛЬКО строку в формате:
SCORE: число
ISSUES: кратко что не так (или OK если всё хорошо)"""
    
    try:
        result = ask_grok(prompt, max_tokens=100).strip()
        score = 70  # default
        issues = "OK"
        
        for line in result.split("\n"):
            if line.upper().startswith("SCORE:"):
                try:
                    score = int(line.split(":")[1].strip())
                except:
                    pass
            elif line.upper().startswith("ISSUES:"):
                issues = line.split(":", 1)[1].strip()
        
        # Apply actions based on score
        if score < 40:
            reply = f"❌ [REJECT {score}] {reply}"
            print(f"[VERIFY] REJECT {score}: {issues}", flush=True)
        elif score < 70:
            reply = f"⚠️ [FLAG {score}] {reply}"
            print(f"[VERIFY] FLAG {score}: {issues}", flush=True)
        elif score < 90:
            print(f"[VERIFY] MINOR {score}: {issues}", flush=True)
        else:
            print(f"[VERIFY] OK {score}", flush=True)
        
        return reply, score, [issues]
        
    except Exception as e:
        print(f"[VERIFY ERR] {e}", flush=True)
        return reply, 70, [str(e)]


def verify_qa_facts(facts_text: str, original_text: str) -> bool:
    """Verify that QA parser didn't lose data. Returns True if all facts preserved."""
    from handlers import ask_grok
    
    prompt = f"""Проверь что все факты из сообщения прораба попали в извлечённые факты.
    
Исходное сообщение: {original_text[:500]}
Извлечённые факты: {facts_text[:500]}

Потеряны ли какие-то цифры, категории или детали? 
Верни ТОЛЬКО: OK или MISSING: что потеряно"""
    
    try:
        result = ask_grok(prompt, max_tokens=60).strip()
        if "OK" in result.upper():
            return True
        print(f"[QA VERIFY] {result}", flush=True)
        return False
    except:
        return True  # fail open — don't block on verification error
