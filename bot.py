#!/usr/bin/env python3
"""
English + Portuguese Phonics Telegram Bot — v4
Features:
  /course          — tap buttons to pick English CLR or Portuguese Fonética
  /next en|pt      — jump to your next lesson automatically
  /lesson en|pt N  — open a specific lesson
  /semana          — generate a full weekly activity plan (PT) with printout bundle
  /atividade       — today's activity idea in Portuguese
  /atividades en   — today's activity idea in English
  /falar <word>    — bot sends a voice message pronouncing the word correctly (TTS)
  Daily morning message: English tip + Portuguese activity nudge
  Progress saved in progress.json
"""

import os
import json
import logging
import tempfile
import re
from datetime import time, date
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import anthropic
import httpx
from usage_logger import log_usage, init_usage_table

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # avoid logging Telegram URLs (token)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DAILY_TIP_HOUR    = int(os.getenv("DAILY_TIP_HOUR", "11"))
DAILY_TIP_MINUTE  = int(os.getenv("DAILY_TIP_MINUTE", "0"))
PREWARM_LESSON_CACHE = os.getenv("PREWARM_LESSON_CACHE", "0").strip().lower() in ("1", "true", "yes", "on")

PROGRESS_FILE = Path("progress.json")
CACHE_FILE = Path("cache.json")

# Optional persistence in Railway Postgres (recommended over volumes).
try:
    import psycopg2  # type: ignore
    from psycopg2.extras import RealDictCursor  # type: ignore
except Exception:  # pragma: no cover
    psycopg2 = None
    RealDictCursor = None

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Postgres KV storage (persists bot state across redeploys) ─────────────────

def _db_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()

def db_available() -> bool:
    return bool(_db_url()) and psycopg2 is not None

def get_db():
    url = _db_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    # Railway often uses postgresql:// ; psycopg2 supports it, but keep compatibility with older forms.
    url = url.replace("postgresql://", "postgres://", 1)
    # Prevent hangs if Postgres is temporarily unreachable.
    return psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=5)

def init_kv_table() -> None:
    if not db_available():
        return
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bot_kv (
                        key TEXT PRIMARY KEY,
                        value JSONB NOT NULL,
                        updated_at TIMESTAMP DEFAULT NOW()
                    );
                    """
                )
            conn.commit()
    except Exception as e:
        logger.warning("Postgres KV init failed; falling back to local files: %s", e)

def kv_get(key: str) -> dict | None:
    if not db_available():
        return None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM bot_kv WHERE key = %s", (key,))
                row = cur.fetchone()
                if not row:
                    return None
                return row["value"]
    except Exception as e:
        logger.warning("Postgres KV read failed; falling back to local files: %s", e)
        return None

def kv_set(key: str, value: dict) -> None:
    if not db_available():
        raise RuntimeError("DB not available")
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bot_kv (key, value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (key, json.dumps(value)),
                )
            conn.commit()
    except Exception as e:
        # Don't break the bot if Postgres is down.
        logger.warning("Postgres KV write failed; falling back to local files: %s", e)

# ── Per-user data (progress + config) ────────────────────────────────────────
# Stored in progress.json as:
# {
#   "lessons": {"en": 1, "pt": 1},
#   "users": {
#     "123456789": {
#       "lang": "en",            # default chat language: "en" or "pt"
#       "daily_tip": true,       # receive English tip daily
#       "daily_activity": true,  # receive daily activity
#       "activity_lang": "en",   # language for activities
#     }
#   }
# }
# Users are auto-registered when they send /start.
# No chat IDs needed in .env — the bot learns who to message on its own.

DEFAULT_CONFIG = {
    "lang": "en",
    "daily_tip": True,
    # Only the "tip of the day" is proactive; daily activity is generated only when the user asks.
    "daily_activity": False,
    "activity_lang": "en",
}

def load_data() -> dict:
    if db_available():
        raw = kv_get("data")
        if isinstance(raw, dict):
            return raw

    if PROGRESS_FILE.exists():
        try:
            raw = json.loads(PROGRESS_FILE.read_text())
        except Exception:
            raw = None
        else:
            if isinstance(raw, dict) and "lessons" not in raw and ("en" in raw or "pt" in raw):
                raw = {
                    "lessons": {
                        "en": int(raw.get("en", 1)),
                        "pt": int(raw.get("pt", 1)),
                    },
                    "users": raw.get("users", {}),
                }
                save_data(raw)
            if isinstance(raw, dict):
                return raw

    return {"lessons": {"en": 1, "pt": 1}, "users": {}}

def save_data(data: dict) -> None:
    if db_available():
        kv_set("data", data)
        return
    PROGRESS_FILE.write_text(json.dumps(data, indent=2))

def register_user(chat_id: int) -> None:
    """Auto-register a user with default config when they send /start."""
    data = load_data()
    uid = str(chat_id)
    if uid not in data.get("users", {}):
        data.setdefault("users", {})[uid] = DEFAULT_CONFIG.copy()
        save_data(data)
        logger.info(f"New user registered: {chat_id}")

def get_user_config(chat_id: int) -> dict:
    data = load_data()
    uid = str(chat_id)
    # Register on first access if not yet known
    if uid not in data.get("users", {}):
        data.setdefault("users", {})[uid] = DEFAULT_CONFIG.copy()
        save_data(data)
    return data["users"][uid]

def set_user_config(chat_id: int, key: str, value) -> None:
    data = load_data()
    uid = str(chat_id)
    data.setdefault("users", {}).setdefault(uid, DEFAULT_CONFIG.copy())[key] = value
    save_data(data)

def get_all_user_ids() -> list[int]:
    """Return all registered chat IDs."""
    return [int(uid) for uid in load_data().get("users", {}).keys()]

DAILY_TIP_HISTORY_LIMIT = 14
TIP_EXPRESSION_POOL = [
    "all done", "tidy up", "look at that", "well done", "let's go", "come here",
    "careful", "slow down", "listen", "inside voice", "big hug", "high five",
    "take turns", "clean hands", "all clean", "good sharing", "wait a second",
    "sit down", "stand up", "time to sleep", "bath time", "good morning",
    "good night", "hungry", "thirsty", "try again", "great job", "be kind",
    "use gentle hands", "quiet feet", "good helper", "thank you", "you're welcome",
]

def load_daily_tip_history() -> list[dict]:
    """Return recent daily tip entries stored in progress.json."""
    data = load_data()
    hist = data.get("daily_tip_history", [])
    if not isinstance(hist, list):
        return []
    out: list[dict] = []
    for entry in hist:
        if not isinstance(entry, dict):
            continue
        if not isinstance(entry.get("date"), str):
            continue
        tip = entry.get("tip")
        if not isinstance(tip, str):
            continue
        expr = entry.get("expression")
        if expr is not None and not isinstance(expr, str):
            expr = None
        expr_norm = entry.get("expression_norm")
        if expr_norm is not None and not isinstance(expr_norm, str):
            expr_norm = None
        if expr and not expr_norm:
            expr_norm = expr.casefold()
        out.append({"date": entry["date"], "expression": expr, "expression_norm": expr_norm, "tip": tip})
    return out

def save_daily_tip_history(history: list[dict]) -> None:
    data = load_data()
    data["daily_tip_history"] = history[-DAILY_TIP_HISTORY_LIMIT:]
    save_data(data)

def extract_daily_tip_expression(tip_text: str) -> str | None:
    """Extract the expression/word from common tip formats."""
    # Typical format: 🌟 *All done*
    m = re.search(r"🌟\\s*\\*([^*]+)\\*", tip_text)
    if m:
        expr = m.group(1).strip()
        return expr or None

    # Fallback 1: label line uses a generic star in markdown, expression is on the next line.
    # Example:
    # 🌟 *Word or Expression of the Day*
    # all done
    m2 = re.search(r"🌟\\s*\\*[^*]+\\*\\s*\\n\\s*([^\\n\\r]+)", tip_text)
    if m2:
        expr = m2.group(1).strip()
        return expr or None

    # Fallback 2: plain-text heading, expression on next line.
    # Example:
    # 🌟 Word or Expression of the Day
    # Gentle
    m3 = re.search(
        r"🌟\\s*Word\\s+or\\s+Expression\\s+of\\s+the\\s+Day\\s*\\n\\s*([^\\n\\r]+)",
        tip_text,
        flags=re.IGNORECASE,
    )
    if m3:
        expr = m3.group(1).strip()
        return expr or None

    # Fallback 3: first non-empty line after any line containing "word or expression".
    lines = [ln.strip() for ln in tip_text.splitlines()]
    for i, ln in enumerate(lines):
        simple = re.sub(r"[*_`🌟:]", "", ln).strip().casefold()
        if "word or expression" in simple:
            for nxt in lines[i + 1 : i + 5]:
                if not nxt:
                    continue
                if nxt.startswith(("📖", "🏠", "🎵")):
                    break
                return nxt.strip(" -*_`")

    return None

def build_tip_prompt_for_expression(expr: str, recent_expr_display: list[str]) -> str:
    avoid_list = ", ".join(recent_expr_display) if recent_expr_display else "none"
    return (
        DAILY_TIP_PROMPT
        + "\n\n"
        + "MANDATORY RULES:\n"
        + f"- Use EXACTLY this expression today: {expr}\n"
        + "- Keep the exact section structure.\n"
        + f"- Do NOT use any of these recent expressions: {avoid_list}\n"
    )

def pick_non_repeating_expression(recent_expr_norm: list[str]) -> str:
    used = set(recent_expr_norm)
    for expr in TIP_EXPRESSION_POOL:
        if expr.casefold() not in used:
            return expr
    # If everything in pool was used recently, cycle by day.
    return TIP_EXPRESSION_POOL[date.today().toordinal() % len(TIP_EXPRESSION_POOL)]

def build_fallback_tip(expr: str) -> str:
    return (
        "🌟 Word or Expression of the Day\n"
        f"{expr}\n\n"
        "📖 What it means\n"
        f"A useful everyday expression: \"{expr}\".\n\n"
        "🏠 Use it at home today\n"
        f"• \"Can you say: {expr}?\"\n"
        f"• \"Let's use '{expr}' during play time.\"\n\n"
        "🎵 Toddler tip\n"
        "Use it during a short game and repeat it with gestures so it sticks naturally."
    )

def generate_daily_tip_with_history() -> str:
    """Generate a daily tip, avoiding recent repetitions."""
    today = date.today().isoformat()
    history = load_daily_tip_history()

    # If the job runs twice, reuse today's tip.
    for entry in history:
        if entry.get("date") == today and isinstance(entry.get("tip"), str):
            return entry["tip"]

    recent_expr_norm: list[str] = []
    recent_expr_display: list[str] = []
    for e in history[-7:]:
        expr_display = e.get("expression") or extract_daily_tip_expression(e.get("tip", ""))
        if expr_display:
            recent_expr_display.append(expr_display)
            recent_expr_norm.append(expr_display.casefold())
            # Backfill in-memory so future save keeps normalized data.
            if not e.get("expression"):
                e["expression"] = expr_display
                e["expression_norm"] = expr_display.casefold()

    recent_expr_norm = [x for x in recent_expr_norm if x]
    forced_expr = pick_non_repeating_expression(recent_expr_norm)
    forced_expr_norm = forced_expr.casefold()

    tip = ""
    expr = None
    expr_norm = None

    # Try a few times to force the selected expression.
    for _ in range(3):
        user_message = build_tip_prompt_for_expression(forced_expr, recent_expr_display)
        tip = ask_claude(user_message, system=SYSTEM_EN, temperature=0.6)
        expr = extract_daily_tip_expression(tip)
        expr_norm = expr.casefold() if expr else None
        if expr_norm == forced_expr_norm and expr_norm not in recent_expr_norm:
            break

    if not tip:
        tip = build_fallback_tip(forced_expr)
        expr = forced_expr
        expr_norm = forced_expr_norm
    elif expr_norm != forced_expr_norm or expr_norm in recent_expr_norm:
        # Absolute fallback: never allow a duplicate expression.
        tip = build_fallback_tip(forced_expr)
        expr = forced_expr
        expr_norm = forced_expr_norm

    # Upsert today's entry.
    history = [e for e in history if e.get("date") != today]
    history.append({"date": today, "expression": expr, "expression_norm": expr_norm, "tip": tip})
    save_daily_tip_history(history)
    return tip


# ── Cache system ──────────────────────────────────────────────────────────────
# cache.json stores:
# {
#   "lessons": {
#     "en_1": "extra tips text...",
#     "pt_7": "extra tips text...",
#     ...all 64 lessons, generated once ever
#   },
#   "semana": {
#     "week": "2024-W03",         # ISO week string
#     "plan": "Monday...",        # the full plan text
#   }
# }

def load_cache() -> dict:
    if db_available():
        raw = kv_get("cache")
        if isinstance(raw, dict):
            return raw

    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            pass
    return {}

def save_cache(cache: dict) -> None:
    if db_available():
        kv_set("cache", cache)
        return
    CACHE_FILE.write_text(json.dumps(cache, indent=2))

def get_cached_lesson(lang: str, num: int) -> str | None:
    return load_cache().get("lessons", {}).get(f"{lang}_{num}")

def set_cached_lesson(lang: str, num: int, text: str) -> None:
    cache = load_cache()
    cache.setdefault("lessons", {})[f"{lang}_{num}"] = text
    save_cache(cache)

def get_cached_semana() -> str | None:
    """Return cached weekly plan if it's from the current ISO week."""
    cache = load_cache()
    semana = cache.get("semana", {})
    current_week = date.today().strftime("%G-W%V")
    if semana.get("week") == current_week:
        return semana.get("plan")
    return None

def set_cached_semana(plan: str) -> None:
    cache = load_cache()
    cache["semana"] = {
        "week": date.today().strftime("%G-W%V"),
        "plan": plan,
    }
    save_cache(cache)

def lessons_cache_complete() -> bool:
    """True if all 64 lessons are already cached."""
    cached = load_cache().get("lessons", {})
    return all(f"{lang}_{n}" in cached for lang in ("en", "pt") for n in range(1, 33))

async def prewarm_lessons_cache() -> None:
    """Background task: generate and cache all 64 lesson enrichments if not done yet."""
    if lessons_cache_complete():
        logger.info("Lesson cache already complete — skipping pre-warm.")
        return

    logger.info("Pre-warming lesson cache (64 lessons)... this runs once ever.")
    count = 0
    for lang in ("en", "pt"):
        system = SYSTEM_PT if lang == "pt" else SYSTEM_EN
        for num in range(1, 33):
            if get_cached_lesson(lang, num):
                continue  # already cached
            label, tips = get_lesson_info(lang, num)
            if lang == "pt":
                prompt = (
                    f"Vou fazer essa lição de fonética com minha filha de 2 anos agora. "
                    f"Me dê 2–3 dicas práticas extras para fazer em casa. Curto e direto. Em português.\n\n"
                    f"{label}\n\n{tips}"
                )
            else:
                prompt = (
                    f"I am about to do this phonics lesson with my 2-year-old daughter. "
                    f"Give me 2–3 extra practical tips for doing this at home. Short and actionable. English only.\n\n"
                    f"{label}\n\n{tips}"
                )
            enriched = ask_claude(prompt, system=system)
            set_cached_lesson(lang, num, enriched)
            count += 1
            logger.info(f"Cached {lang} lesson {num} ({count}/64)")

    logger.info("Lesson cache pre-warm complete — all 64 lessons cached forever.")

def get_next_lesson(lang: str) -> int:
    return load_data().get("lessons", {}).get(lang, 1)

def mark_lesson_done(lang: str, num: int) -> None:
    data = load_data()
    lessons = data.setdefault("lessons", {"en": 1, "pt": 1})
    if num >= lessons.get(lang, 1):
        lessons[lang] = min(num + 1, 32)
    save_data(data)

def load_progress() -> dict:
    """Backwards compat shim — returns lesson progress."""
    return load_data().get("lessons", {"en": 1, "pt": 1})

def save_progress(progress: dict) -> None:
    data = load_data()
    data["lessons"] = progress
    save_data(data)

# ── System prompts ────────────────────────────────────────────────────────────

SYSTEM_EN = """You are a warm, encouraging English teacher assistant for a Brazilian Portuguese speaker who is:
1. Learning English themselves (intermediate level).
2. Teaching English to their 2-year-old daughter using the Children Learning Reading (CLR) phonics method by Jim Yang.
3. Also teaching Portuguese phonics using an adapted CLR method for Brazilian Portuguese.

Rules:
- ALWAYS reply in English only. Do NOT add Portuguese translations unless the user explicitly asks.
- If the user writes in Portuguese, understand it naturally and reply in English.
- Keep answers practical, warm, and encouraging.
- For grammar corrections, show the correct form gently — never make the user feel bad.
- The daughter is 2 years and 3 months old and speaks a lot of Portuguese already.
"""

SYSTEM_PT = """Você é um assistente de fonetismo caloroso e encorajador para uma criança brasileira de 2 anos e 3 meses.
O pai/mãe está ensinando português usando um método adaptado do CLR (Children Learning Reading) de Jim Yang.

Regras:
- Responda SEMPRE em português brasileiro.
- Seja caloroso, prático e encorajador.
- Dê dicas concretas e acionáveis para sessões curtas (3–5 minutos) com uma criança pequena.
- Use linguagem simples — o pai/mãe está aprendendo junto com a criança.
"""

DAILY_TIP_PROMPT = """Generate a daily English tip for a Brazilian parent learning English and teaching it to their 2-year-old.

Format exactly like this:
🌟 *Word or Expression of the Day*
[word or expression]

📖 *What it means*
[simple, clear definition — English only]

🏠 *Use it at home today*
• "[example sentence with toddler]"
• "[example sentence for adult use]"

🎵 *Toddler tip*
[A song, game, or routine that reinforces this word naturally for a 2-year-old]

Pick something genuinely useful for daily home life. Think: daylight, tidy up, splash around, peek-a-boo, all done, gentle, careful, well done, let's go, come here, look at that.
"""

# ── Activity system prompts ───────────────────────────────────────────────────

SYSTEM_ACTIVITIES_PT = """Você é um assistente especializado em atividades para crianças pequenas, 
ajudando uma mãe brasileira que fica em casa com sua filha de 2 anos e 3 meses.

Regras:
- Responda SEMPRE em português brasileiro, de forma calorosa e prática.
- As atividades devem usar materiais simples que já existem em casa (papel, pote, água, arroz, tinta, etc).
- Quando precisar de algo especial, diga que pode ser impresso ou comprado barato.
- Adapte sempre para a faixa etária: 2 anos e 3 meses — curiosa, ativa, aprende com repetição e brincadeira.
- Inclua sempre: objetivo da atividade (o que ela aprende), materiais, passo a passo simples, e uma dica extra.
- Categorias possíveis: sensorial, artes, movimento, culinária, livros, educacional (números/cores/formas).
- Seja animada e encorajadora — a mãe precisa de inspiração, não de pressão.
"""

SYSTEM_ACTIVITIES_EN = """You are a specialist in activities for young children,
helping a Brazilian stay-at-home parent with their 2-year-3-month-old daughter.

Rules:
- Reply in English only.
- Activities must use simple materials already at home (paper, containers, water, rice, paint, etc).
- Always adapted for age 2y3m — curious, active, learns through repetition and play.
- Always include: learning goal, materials, simple steps, and a bonus tip.
- Categories: sensory play, arts & crafts, movement, cooking together, storytime, educational (numbers/colors/shapes).
- Be warm and encouraging.
"""

DAILY_ACTIVITY_PROMPT = """Sugira UMA atividade para hoje para uma criança de 2 anos e 3 meses.
A mãe está em casa e precisa de algo simples, divertido e que não bagunce muito.

Formato exato:
🎨 *Atividade do dia*
[nome da atividade]

🎯 *O que ela aprende*
[objetivo em uma linha]

🧺 *O que você vai precisar*
[lista curta de materiais simples]

👣 *Como fazer*
[3 a 5 passos bem simples]

💡 *Dica extra*
[uma dica prática para a mãe]

Varie entre: sensorial, artes, movimento, culinária, livros, educacional.
"""

WEEKLY_PLAN_PROMPT = """Crie um plano semanal de atividades (segunda a domingo) para uma criança de 2 anos e 3 meses.
A mãe está em casa com ela o dia todo. Use materiais simples que já existem em casa.

Para cada dia, forneça:
- Nome da atividade
- Categoria (sensorial / artes / movimento / culinária / livros / educacional)
- Materiais necessários
- Passos simples (máximo 4)
- O que a criança aprende

No final, depois dos 7 dias, adicione uma seção:
📋 *PARA IMPRIMIR ESTA SEMANA*
Liste todos os itens que precisam ser impressos (moldes, cartões, fichas) com uma descrição simples de cada um.
Se não houver nada para imprimir, diga "Nenhum impresso necessário esta semana — aproveite!"

Formato de cada dia:
━━━━━━━━━━━━━━
📅 *[DIA DA SEMANA]*
🎯 [Nome da atividade] — _[categoria]_
🧺 Materiais: [lista]
👣 [passo 1] / [passo 2] / [passo 3]
🌱 Aprende: [objetivo]
"""

# ── CLR English lesson data ───────────────────────────────────────────────────
CLR_EN_LESSONS = {
    (1,6):  ("Letters A, B, C, T", "Introduce each letter sound one at a time. Words: AB, CAB, AT, BAT, CAT. Say the SOUND not the name — 'a' as in apple, not 'ay'. Keep sessions to 3–5 minutes max."),
    (7,9):  ("Adding U", "New sound: U. Words: BUT, CUT, CUB, TUB, TAB. Practice blending slowly: C-U-B = CUB. Always left to right, finger under each letter."),
    (10,10):("Adding S", "New sound: S. Words: SAT, BUS, SUB, STUB, BATS, CAST. First sentences: 'The cat sat.' Point to each word as you read aloud."),
    (11,12):("Adding P", "New sound: P. Words: PAT, TAP, PUB, CUP, PASS. Sentence: 'Pass the cup.' Clap the sounds: P-A-T = PAT."),
    (13,13):("Adding O", "New vowel: O. Words: BOT, COP, POP, POT, SPOT, STOP. Point to real STOP signs outside — instant recognition moment!"),
    (14,14):("Adding H", "New sound: H. Words: HAS, HAT, HUT, HOT, HOP. Sentence: 'He has a hat.' Ask her: where's YOUR hat?"),
    (15,15):("Adding N", "New sound: N. Words: NOT, BUN, CAN, PAN, TAN, PANTS. Sentence: 'I can hop.' Turn it into a physical game."),
    (16,16):("Review",   "No new letter. Review all words from lessons 1–15. Go through flashcards quickly — celebrate fast recognition with claps."),
    (17,17):("Adding G", "New sound: G. Words: HOG, BAG, BUG, TUG, HUG. Sentence: 'Give me a hug!' Make it physical — toddlers love hugs."),
    (18,18):("Adding D", "New sound: D. Words: DAD, HAD, SAD, DOG, HAND, SAND. Sentence: 'Dad had a hot dog.' She'll love hearing DAD in print."),
    (19,19):("Adding I", "New vowel: I. Words: HIS, DID, HIT, BIT, PIT, SIT, PIN, BIN. Keep it silly — 'Sit in the bin!' Toddlers love absurd sentences."),
    (20,20):("Adding F", "New sound: F. Words: FOG, FUN, FAN, FIT, FAST, FAT. Speed up 'The fat cat is so fast' each time — she'll giggle."),
    (21,21):("Adding R", "New sound: R. Words: RAT, RUG, RUN, FROG, DROP, CRIB. 'The rat drags the frog.' Make it dramatic and silly."),
    (22,22):("Adding M", "New sound: M. Words: MUD, MAP, MAN, MOM, MAT, MUFFIN. 'I miss mom and dad.' Very emotionally resonant."),
    (23,23):("Adding E", "New vowel: E. Words: BED, RED, PET, NET, REST, BEST. 'Ted's pet rests on the bed.' Perfect for bedtime reading."),
    (24,24):("Adding J and K", "New sounds: J, K. Words: JAM, JOG, JUMP, BACK, PACK, KICK, TICKET. 'Jack just had jam.' Practice KICK — fun to say and do."),
    (25,25):("Lowercase", "Same words now in lowercase. Show her 'CAT' and 'cat' are the same word — just a different outfit. Go one word at a time."),
    (26,26):("Adding L", "New sound: L. Words: LOT, LOG, LAND, CLOCK, LOCK, BALL, BELL. 'Lots of dogs got lost.' Count the L words together."),
    (27,27):("Adding X", "New sound: X. Words: BOX, SIX, MIX, FOX, TEXT, RELAX. 'The cat, hat, and bat are mixed in the box.' Great physical sorting game."),
    (28,28):("Adding Y", "New sound: Y. Words: FUNNY, BUNNY, SUNNY, YUMMY, SILLY, MOMMY, DADDY. 'The funny bunny is smelly.' She will LOVE this one."),
    (29,29):("Adding QU", "New sound: QU (always together). Words: QUIT, QUICK, QUIET, QUILT. 'It is so quiet.' Great for whispering at bedtime."),
    (30,30):("W and WH", "Words: WILL, WIN, WHY, WHEN, WHAT, WHERE. These are question words — use them in real questions during the day."),
    (31,31):("Adding V", "New sound: V. Words: VAN, VET, GIVE, HAVE, GLOVE. Talk about what a vet does — great if she loves animals."),
    (32,32):("Adding Z", "New sound: Z. Words: ZIP, ZAP, BUZZ, FIZZ, QUIZ. 'Run in a zig zag.' Make it a physical game — run zig zag together!"),
}

# ── Portuguese phonics lesson data (32 individual entries) ────────────────────
CLR_PT_LESSONS = {
    (1,1):  ("Vogal A", "Apresente apenas a letra A hoje. Diga o SOM 'ah' — não o nome. Palavras: AMÁ, AI, AVÓ. Aponte para objetos reais: ÁGUA, AVIÃO. Sessão de 3 minutos. Repita 'A... A... A...' e deixe ela copiar. Uma letra, muitas repetições — só isso por hoje."),
    (2,2):  ("Vogal E", "Som novo: 'eh' como em ELA. Palavras: ELA, EU, ELE. Compare com o A da sessão anterior — segure dois cartões e peça para ela apontar para o A, depois o E. A diferença entre 'ah' e 'eh' é a lição toda de hoje."),
    (3,3):  ("Vogal I", "Som novo: 'ee' como em IDA. Palavras: IDA, IR, IA. Agora você tem A E I — jogue um jogo simples: fale um som, ela aponta para o cartão certo. 'Onde está o I?' Três vogais já são suficientes para uma criança pequena. Elogie cada acerto."),
    (4,4):  ("Vogal O", "Som novo: 'oh' como em OVO. Palavras: OVO, OI, OSO. OI é perfeito — ela fala toda hora como cumprimento. Mostre a palavra OI e veja a reação dela. Quatro vogais agora: A E I O."),
    (5,5):  ("Vogal U", "Som novo: 'u' como em UVA. Palavras: UVA, UM, UÊ. Segure uma uva (ou figura) e diga U-VA devagar. Agora você tem as cinco vogais. Passe essa sessão toda revisando: A E I O U em ordem, depois misturadas."),
    (6,6):  ("Revisão das 5 vogais", "Sem letra nova hoje. Revisão completa: A E I O U. Coloque os cinco cartões no chão. Fale um som — ela corre para o cartão certo. Torne físico e divertido. Cronometre quantos segundos ela leva para achar cada um. Comemore cada acerto. Essa é a base de tudo."),
    (7,7):  ("Consoante M", "Som novo: 'mm' — lábios fechados, depois abre. Palavras: MÃE, MÃO, MAMÃ, MIAU. MÃE é a palavra mais poderosa do vocabulário dela — ver escrita pela primeira vez é um momento especial. Una devagar: M... Ã... E... = MÃE. Deixe ela segurar o cartão quando acertar."),
    (8,8):  ("Consoante P", "Som novo: 'p' — um pequeno sopro de ar. Palavras: PAI, PÉ, PIA, PIPA. PAI é sua arma secreta — ela fala dezenas de vezes por dia. O momento em que ela ler PAI sozinha será inesquecível. Una: P... A... I... = PAI. Pratique MÃE + PAI lado a lado."),
    (9,9):  ("Consoante B", "Som novo: 'b' — como P mas com voz. Palavras: BOLA, BEBÊ, BOCA. Role uma bola pelo chão e diga B-O-L-A a cada rolada. A ação física grava a palavra. Tente também BEBÊ com uma boneca — ela pode segurar o 'bebê' enquanto lê o cartão."),
    (10,10):("Consoante T + Revisão", "Som novo: 't' — língua no céu da boca. Palavras: TATU, TETO, PATO, BOTA. Revise M P B primeiro — passe pelos cartões antes de introduzir o T. PATO é ótimo: faça ele grasnar toda vez que ela ler. Frases: 'O PATO É MIO.' 'A BOTA É MIA.'"),
    (11,11):("Consoante D", "Som novo: 'd' — como T mas com voz. Palavras: DEDO, DADO, DORME. Toque o dedo dela e diga D-E-D-O — a palavra e a parte do corpo ao mesmo tempo. Essa conexão tátil é poderosa para crianças pequenas. Tente DORME na hora de dormir: 'hora de DORME?'"),
    (12,12):("Consoante V", "Som novo: 'v' — dente de cima no lábio de baixo, vibrando. Palavras: VACA, VELA, VOVÓ, UVA. VOVÓ é emocionalmente poderosa — se a avó é presente na vida dela, ver o nome escrito é mágico. Faça a vaca mugir para VACA. Segure uma uva para UVA."),
    (13,13):("Consoante F", "Som novo: 'f' — mesma posição que o V mas sem vibração. Palavras: FADA, FOCA, FOFA, FOME. FOFA ela ouve o tempo todo — 'que FOFA!' Ver escrito vai arrancá-la uma gargalhada. Compare V e F: mesma boca, um vibra, o outro não."),
    (14,14):("Consoante N", "Som novo: 'n' — língua no céu da boca, som sai pelo nariz. Palavras: NANA, NINHO, NEVE, NABO. Use NANA na hora de dormir — é a palavra mais suave do conjunto. 'NANA, NANA' enquanto balança. NINHO com figura de ninho de pássaro é bonito e memorável."),
    (15,15):("Revisão geral — Lição 15", "Sem letra nova. Revisão completa das lições 7–14: M P B T D V F N. Coloque todos os cartões no chão. Você fala FADA, ela acha. Depois troca: ela escolhe um cartão, você lê juntos. Comemore cada acerto em voz alta. Anote quais palavras ela hesita — revise essas amanhã."),
    (16,16):("Consoante L", "Som novo: 'l' — ponta da língua no céu, lados abertos. Palavras: LEÃO, LOBO, BOLO, LAMA, LUA. BOLO é ótimo motivador — prometa um bolo de verdade depois de uma boa sessão! LEÃO e LOBO são animais empolgantes. LUA é linda para uma sessão noturna — olhem a lua juntos."),
    (17,17):("Consoante C (CA CO CU)", "Som novo: 'k' duro — MAS APENAS antes de A, O, U hoje. Palavras: CAMA, COPO, CUBO, CUCO. CAMA é perfeita — ela conhece a própria cama profundamente. Importante: NÃO introduza CE ou CI ainda. Esses têm um som completamente diferente e chegam na lição 26. Diga claramente: 'C antes de A faz KA. C antes de O faz KO.'"),
    (18,18):("Consoante G (GA GO GU)", "Som novo: 'g' duro — APENAS antes de A, O, U. Palavras: GATO, GOLA, GUGU, PEGA. GATO é maravilhoso se ela ama gatos. GUGU é instantaneamente reconhecível. Mesma regra do C: NÃO introduza GE ou GI ainda — chegam depois com som diferente."),
    (19,19):("Consoante R (som suave)", "Som novo: R suave — apenas entre vogais, como em 'cara'. Palavras: CARA, PURO, FORA, CARO, TIRO. Este é o R gentil, NÃO o R forte do início das palavras. Em CARA o R é suave como um toque leve. O R forte (como em RATO) fica para o Estágio 2. Por agora: R apenas no meio das palavras."),
    (20,20):("Consoante S", "Som novo: 's' — ar entre os dentes. Palavras: SAPO, SUCO, MESA, SOLO. SAPO PULA é uma música folclórica brasileira famosa — se ela conhece, ver SAPO escrito é um momento enorme de reconhecimento. Pergunte: 'O sapo pula... onde?' Aponte para SAPO no cartão enquanto ela canta."),
    (21,21):("Revisão + Frases completas", "Sem letra nova. Revisão das lições 16–20: L C G R S. Agora monte frases completas com os cartões: 'O GATO DORME NA CAMA.' 'O SAPO PULA NA LAMA.' Passe o dedo sob cada palavra da esquerda para a direita ao ler em voz alta. Esse é um momento grande — ela está lendo frases em português."),
    (22,22):("Dígrafo LH", "Som novo: LH — um som único do português, como 'lh' em 'talha' ou 'lli' em 'million'. Palavras: FILHO, FOLHA, OLHA, GALHO. OLHA! é o mais natural — você já fala o tempo todo: 'OLHA o gatinho!' 'OLHA a lua!' Use em momentos reais hoje. Toda vez que falar OLHA, aponte para algo e faça a conexão com o cartão."),
    (23,23):("Dígrafo NH", "Som novo: NH — nasal, como 'ny' em 'canyon'. Palavras: NINHO, BANHO, MINHA, LINHA. HORA DO BANHO é dito todos os dias — escreva num cartão e mostre na hora do banho. MINHA BOLA, MINHA CAMA — o possessivo MINHA dá a ela propriedade sobre palavras que ela ama."),
    (24,24):("Dígrafo CH", "Som novo: CH — como 'sh' em inglês. Palavras: CHÃO, CHUVA, BICHO, CHAVE. CH é na verdade fácil para crianças pequenas porque o som é muito claro. CAI NO CHÃO é algo que ela vive — crianças pequenas caem muito! Conecte a palavra ao momento real quando acontecer hoje."),
    (25,25):("Letra X (som CH)", "Letra nova: X — mas hoje APENAS o som 'ch/sh'. Palavras: XÍCARA, XALE, PEIXE, CAIXA, ROXO. Importante: X tem quatro sons possíveis em português. Não mencione essa complexidade ainda. Ensine apenas: 'X pode soar como CH.' PEIXE é ótimo com figura ou brinquedo de peixe. CAIXA — coloque um brinquedo dentro de uma caixa e rotule."),
    (26,26):("J e G suave (GE GI)", "Duas letras, um som: 'j' suave — como o 's' em 'leisure' em inglês. Palavras: JOGO, HOJE, GELO, GIRAFA, FEIJÃO. J sempre faz esse som. G faz esse som APENAS antes de E ou I — essa é a regra. GIRAFA é empolgante com figura ou brinquedo. FEIJÃO ela conhece da comida — ótima âncora."),
    (27,27):("Cedilha Ç", "Símbolo novo: Ç — sempre soa como S, nunca como K. Palavras: MAÇÃ, POÇO, AÇAÍ, FAÇO. MAÇÃ é perfeita — segure uma maçã de verdade. AÇAÍ ela provavelmente adora. A cedilha (o gancho embaixo do C) é o sinal: 'este C faz som de S.' Aponte para o gancho cada vez."),
    (28,28):("Vogais nasais: ÃO, EM, IM", "Sons novos: vogais nasais — ar sai pelo nariz E pela boca. Palavras: MÃO, PÃO, BEM, SIM, TAMBÉM. Segure a mão dela e diga MÃO DA MÃE — físico e lindo. PÃO com pão de verdade é o melhor apoio. SIM e BEM são pequeninhos mas poderosos — ela usa todo dia. Zumba o som nasal: mmm-ÃO."),
    (29,29):("Vogais nasais: OM, UM, AN", "Mais vogais nasais. Palavras: BOM, SOM, UM, CANTO, TANTO. BOM DIA! — comece cada sessão a partir de agora com essa frase escrita num cartão. Ela fala toda manhã, agora pode ler. SOM é divertido — faça um som e pergunte 'que SOM é esse?' UM é o número um — contem coisas juntos."),
    (30,30):("Revisão de todos os dígrafos", "Sem conteúdo novo. Revisão completa: LH NH CH X J/G-suave Ç e todas as vogais nasais. Jogue assim: ela escolhe um cartão virado para baixo, vira, lê. Cada acerto ganha um adesivo ou um high five. Anote quais dígrafos ela ainda hesita — esses recebem atenção extra antes do Estágio 2."),
    (31,31):("Letras minúsculas — parte 1", "Mesmas palavras, agora em minúsculo: mãe, pai, bola, gato, sapo, cama. Mostre as duas versões lado a lado: MÃE / mãe. Diga: 'mesma palavra, roupa diferente.' Comece apenas com as palavras que ela conhece melhor em maiúsculo. NÃO apresse — essa é uma virada conceitual e precisa de paciência."),
    (32,32):("Letras minúsculas + Leitura livre", "Última lição do Estágio 1. Mais minúsculas: filho, banho, chuva, maçã, girafa, leão. Depois leia um livro ilustrado brasileiro juntos — qualquer Ziraldo, A Bolsa Amarela, ou Palavra de Honra. Aponte para as palavras ao ler. Ela completou o Estágio 1. Ela está lendo. Parabéns para os dois — isso exigiu dedicação de verdade."),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_lesson_info(lang: str, num: int) -> tuple[str, str]:
    """Returns (label, tips) for a lesson. Tips language matches lang."""
    data = CLR_EN_LESSONS if lang == "en" else CLR_PT_LESSONS
    for (start, end), (title, tips) in data.items():
        if start <= num <= end:
            label = f"📚 *{'English CLR' if lang == 'en' else 'Português — Fonética'} — {'Lesson' if lang == 'en' else 'Lição'} {num}: {title}*"
            return label, tips
    return "❌", f"{'Lesson' if lang == 'en' else 'Lição'} {num} not found. Valid range: 1–32."


def user_system(chat_id: int) -> str:
    """Return default system prompt based on user's configured language."""
    cfg = get_user_config(chat_id)
    return SYSTEM_PT if cfg.get("lang") == "pt" else SYSTEM_EN

def user_is_pt(chat_id: int) -> bool:
    return get_user_config(chat_id).get("lang") == "pt"

def activity_system(chat_id: int) -> str:
    """Return activity system prompt based on user's activity language preference."""
    cfg = get_user_config(chat_id)
    return SYSTEM_ACTIVITIES_PT if cfg.get("activity_lang") == "pt" else SYSTEM_ACTIVITIES_EN

def activity_prompt(chat_id: int) -> str:
    cfg = get_user_config(chat_id)
    if cfg.get("activity_lang") == "pt":
        return DAILY_ACTIVITY_PROMPT
    return (
        "Suggest ONE simple home activity for a 2-year-3-month-old child for today. "
        "Name, learning goal, materials, 3–5 steps, bonus tip. English only. Simple home materials."
    )


def ask_claude(
    user_message: str,
    system: str = None,
    *,
    temperature: float | None = None,
) -> str:
    if system is None:
        system = SYSTEM_EN
    create_kwargs = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "system": system,
        "messages": [{"role": "user", "content": user_message}],
    }
    if temperature is not None:
        create_kwargs["temperature"] = temperature

    response = claude.messages.create(**create_kwargs)
    log_usage("phonics-bot", response)
    return response.content[0].text


async def transcribe_voice(file_bytes: bytes) -> str:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return "[Voice not set up — add OPENAI_API_KEY to .env]"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {openai_key}"},
            files={"file": ("voice.ogg", file_bytes, "audio/ogg")},
            data={"model": "whisper-1"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("text", "")


async def text_to_speech(text: str) -> bytes | None:
    """Convert text to speech using OpenAI TTS. Returns mp3 bytes or None."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return None
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "tts-1",
                "input": text,
                "voice": "nova",   # clear, friendly female voice
                "speed": 0.85,     # slightly slower — easier to follow
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content


async def deliver_lesson(send_fn, lang: str, num: int, mark_done: bool = False) -> None:
    """Fetch lesson info + enrichment (from cache if available) and send to user."""
    label, tips = get_lesson_info(lang, num)
    system = SYSTEM_PT if lang == "pt" else SYSTEM_EN

    # Try cache first — instant and free
    enriched = get_cached_lesson(lang, num)
    if not enriched:
        # Cache miss — generate and store for next time
        if lang == "pt":
            prompt = (
                f"Vou fazer essa lição de fonética com minha filha de 2 anos agora. "
                f"Me dê 2–3 dicas práticas extras para fazer em casa. Curto e direto. Em português.\n\n"
                f"{label}\n\n{tips}"
            )
        else:
            prompt = (
                f"I am about to do this phonics lesson with my 2-year-old daughter. "
                f"Give me 2–3 extra practical tips for doing this at home. Short and actionable. English only.\n\n"
                f"{label}\n\n{tips}"
            )
        enriched = ask_claude(prompt, system=system)
        set_cached_lesson(lang, num, enriched)
        logger.info(f"Lesson {lang}_{num} generated and cached.")

    progress = load_progress()
    done_emoji = "✅" if num < progress.get(lang, 1) else "▶️"
    next_num = min(num + 1, 32)

    # Done button + next lesson button
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"✅ {'Mark done' if lang == 'en' else 'Marcar como feita'}",
                callback_data=f"done_{lang}_{num}"
            ),
            InlineKeyboardButton(
                f"➡️ {'Next' if lang == 'en' else 'Próxima'} ({next_num})",
                callback_data=f"lesson_{lang}_{next_num}"
            ),
        ]
    ])

    await send_fn(f"{label}\n\n{tips}", parse_mode="Markdown")
    await send_fn(
        f"{'💡 *Extra tips:*' if lang == 'en' else '💡 *Dicas extras:*'}\n\n{enriched}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

    if mark_done:
        mark_lesson_done(lang, num)


# ── Command handlers ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    # Auto-register this user for daily messages
    register_user(chat_id)
    is_pt = user_is_pt(chat_id)

    if is_pt:
        welcome = (
            "👋 <b>Olá!</b> Sou sua assistente de atividades e fonetismo.\n\n"
            "💬 Fale comigo à vontade — respondo sempre em português\n"
            "📅 Você receberá uma dica em inglês e uma atividade toda manhã\n"
            "🎙️ Mensagens de voz também funcionam\n"
            "⚙️ Use o menu de configurações para personalizar tudo\n\n"
            "Um menu rápido foi fixado no topo desta conversa 📌"
        )
    else:
        welcome = (
            "👋 <b>Hello!</b> I'm your English and phonics assistant.\n\n"
            "💬 Chat freely — I always reply in English\n"
            "📅 You'll get a daily English tip + activity every morning\n"
            "🎙️ Voice messages supported\n"
            "⚙️ Use the Settings menu to personalise everything\n\n"
            "A pinned quick-menu has been set at the top of this chat 📌"
        )

    await update.message.reply_text(welcome, parse_mode="HTML")

    # Send and pin the quick-access menu
    menu_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇬🇧 English Course",    callback_data="course_en"),
            InlineKeyboardButton("🇧🇷 Curso Português",   callback_data="course_pt"),
        ],
        [
            InlineKeyboardButton("⏭️ Next EN lesson",     callback_data="next_en"),
            InlineKeyboardButton("⏭️ Próxima PT lição",   callback_data="next_pt"),
        ],
        [
            InlineKeyboardButton("🎨 Atividade do dia",   callback_data="quick_activity"),
            InlineKeyboardButton("📅 Plano da semana",    callback_data="quick_semana"),
        ],
        [
            InlineKeyboardButton("💡 Tip of the day",     callback_data="quick_tip"),
            InlineKeyboardButton("📖 Reading tips",       callback_data="quick_reading"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings / Config",  callback_data="quick_config"),
        ],
    ])
    pinned = await context.bot.send_message(
        chat_id=chat_id,
        text="📌 *Quick Menu* — tap anything to start:",
        parse_mode="Markdown",
        reply_markup=menu_keyboard,
    )
    try:
        await context.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=pinned.message_id,
            disable_notification=True,
        )
    except TelegramError as e:
        logger.warning("Could not pin quick menu: %s", e)


async def course_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show course selection buttons."""
    progress = load_progress()
    en_next = progress.get("en", 1)
    pt_next = progress.get("pt", 1)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"🇬🇧 English CLR (lesson {en_next}/32)",
                callback_data=f"course_en"
            ),
        ],
        [
            InlineKeyboardButton(
                f"🇧🇷 Português — Fonética (lição {pt_next}/32)",
                callback_data=f"course_pt"
            ),
        ],
    ])
    await update.message.reply_text(
        "📚 *Which course?*\nTap to see the lesson menu:",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/next en  or  /next pt"""
    args = context.args
    if not args or args[0].lower() not in ("en", "pt"):
        await update.message.reply_text(
            "Use `/next en` for English or `/next pt` for Portuguese.",
            parse_mode="Markdown",
        )
        return
    lang = args[0].lower()
    num = get_next_lesson(lang)
    if num > 32:
        msg = "🎉 You've completed all 32 lessons! Well done!" if lang == "en" else "🎉 Você completou todas as 32 lições! Parabéns!"
        await update.message.reply_text(msg)
        return
    send = update.message.reply_text
    await deliver_lesson(send, lang, num)


async def lesson_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/lesson en 14  or  /lesson pt 7"""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage:\n`/lesson en 14` — English lesson 14\n`/lesson pt 7` — Portuguese lesson 7",
            parse_mode="Markdown",
        )
        return
    lang = args[0].lower()
    if lang not in ("en", "pt"):
        await update.message.reply_text("Use `en` or `pt`. Example: `/lesson en 14`", parse_mode="Markdown")
        return
    try:
        num = int(args[1])
    except ValueError:
        await update.message.reply_text("Please give a lesson number. Example: `/lesson pt 7`", parse_mode="Markdown")
        return
    if not 1 <= num <= 32:
        await update.message.reply_text("Lesson number must be between 1 and 32.")
        return

    send = update.message.reply_text
    await deliver_lesson(send, lang, num)


async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("✨ Getting your tip...")
    tip = generate_daily_tip_with_history()
    await update.message.reply_text(tip, parse_mode="Markdown")


async def reading_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("📚 Getting reading tips...")
    advice = ask_claude(
        "Give practical early reading guidance for a 2-year-3-month-old child. "
        "The parent is Brazilian, teaching both English and Portuguese phonics. "
        "Cover: realistic expectations at this age, one activity to start this week, "
        "one phonics tip, and one free YouTube read-aloud book recommendation. "
        "English only. Be encouraging and brief.",
        system=SYSTEM_EN,
    )
    await update.message.reply_text(advice, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 *Commands:*\n\n"
        "*Courses:*\n"
        "📚 /course — pick a course with buttons\n"
        "⏭️ /next en — next English lesson\n"
        "⏭️ /next pt — next Portuguese lesson\n"
        "📖 /lesson en 14 — specific English lesson\n"
        "📖 /lesson pt 7 — specific Portuguese lesson\n\n"
        "*Activities:*\n"
        "🎨 /atividade — activity of the day (Portuguese)\n"
        "🎨 /atividade en — activity of the day (English)\n"
        "📅 /semana — full weekly plan + printout list\n\n"
        "*English learning:*\n"
        "🔊 /falar <word> — hear correct pronunciation\n"
        "💡 /tip — word of the day\n"
        "📖 /reading — literacy guidance\n\n"
        "Or send any text or voice message!",
        parse_mode="Markdown",
    )


# ── Callback query handler (button taps) ─────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    send = query.message.reply_text

    # Course selection → show lesson menu
    if data.startswith("course_"):
        lang = data.split("_")[1]
        progress = load_progress()
        current = progress.get(lang, 1)
        label = "🇬🇧 English CLR" if lang == "en" else "🇧🇷 Português — Fonética"
        word = "Lesson" if lang == "en" else "Lição"

        # Build a grid of lesson buttons (8 per row × 4 rows)
        buttons = []
        row = []
        for n in range(1, 33):
            done = "✅" if n < current else ("▶️" if n == current else f"{n}")
            row.append(InlineKeyboardButton(done, callback_data=f"lesson_{lang}_{n}"))
            if len(row) == 8:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        await send(
            f"{label}\n\nYour progress: {word} {current}/32\n\nTap a lesson to open it:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    # Lesson tap from menu
    elif data.startswith("lesson_"):
        _, lang, num_str = data.split("_")
        num = int(num_str)
        await deliver_lesson(send, lang, num)

    # Mark lesson as done
    elif data.startswith("done_"):
        _, lang, num_str = data.split("_")
        num = int(num_str)
        mark_lesson_done(lang, num)
        next_num = min(num + 1, 32)
        word = "Lesson" if lang == "en" else "Lição"
        msg = (
            f"✅ {word} {num} marked as done! Your next lesson is {word} {next_num}.\n"
            f"Use /next {'en' if lang == 'en' else 'pt'} when you're ready."
            if lang == "en" else
            f"✅ Lição {num} marcada como feita! Sua próxima lição é a Lição {next_num}.\n"
            f"Use /next pt quando estiver pronta."
        )
        await send(msg)

    # Pinned menu: next lesson shortcuts
    elif data in ("next_en", "next_pt"):
        lang = data.split("_")[1]
        num = get_next_lesson(lang)
        if num > 32:
            msg = "🎉 You've completed all 32 lessons!" if lang == "en" else "🎉 Você completou todas as 32 lições!"
            await send(msg)
        else:
            await deliver_lesson(send, lang, num)

    # Pinned menu: quick tip
    elif data == "quick_tip":
        await send("✨ Getting your tip of the day...")
        tip = generate_daily_tip_with_history()
        await send(tip, parse_mode="Markdown")

    # Pinned menu: reading tips
    elif data == "quick_reading":
        await send("📚 Getting reading tips...")
        advice = ask_claude(
            "Give practical early reading guidance for a 2-year-3-month-old child. "
            "The parent is Brazilian, teaching both English and Portuguese phonics. "
            "Cover: realistic expectations at this age, one activity to start this week, "
            "one phonics tip, and one free YouTube read-aloud book recommendation. "
            "English only. Be encouraging and brief.",
            system=SYSTEM_EN,
        )
        await send(advice, parse_mode="Markdown")

    # Pinned menu: activity of the day
    elif data == "quick_activity":
        await send("🎨 Buscando a atividade do dia...")
        activity = ask_claude(DAILY_ACTIVITY_PROMPT, system=SYSTEM_ACTIVITIES_PT)
        await send(activity, parse_mode="Markdown")

    # Pinned menu: weekly plan
    elif data == "quick_semana":
        plan = get_cached_semana()
        if not plan:
            await send("📅 Criando o plano da semana... aguarde!")
            plan = ask_claude(WEEKLY_PLAN_PROMPT, system=SYSTEM_ACTIVITIES_PT)
            set_cached_semana(plan)
        if len(plan) > 4000:
            mid = plan.find("━━━", 2000)
            if mid == -1:
                mid = 2000
            await send(plan[:mid], parse_mode="Markdown")
            await send(plan[mid:], parse_mode="Markdown")
        else:
            await send(plan, parse_mode="Markdown")

    # Pinned menu: config
    elif data == "quick_config":
        chat_id = query.message.chat_id
        is_pt = user_is_pt(chat_id)
        title = "⚙️ *Configurações*" if is_pt else "⚙️ *Settings*"
        subtitle = (
            "Toque para alternar cada opção\\. As mudanças são imediatas\\."
            if is_pt else
            "Tap any option to toggle it\\. Changes take effect immediately\\."
        )
        await send(
            f"{title}\n\n{subtitle}",
            parse_mode="MarkdownV2",
            reply_markup=build_config_keyboard(chat_id),
        )
    elif data == "cfg_lang":
        chat_id = query.message.chat_id
        cfg = get_user_config(chat_id)
        new_lang = "pt" if cfg.get("lang") == "en" else "en"
        set_user_config(chat_id, "lang", new_lang)
        label = "🇧🇷 Português" if new_lang == "pt" else "🇬🇧 English"
        msg = f"✅ Idioma alterado para {label}!" if new_lang == "pt" else f"✅ Language switched to {label}!"
        await query.message.edit_reply_markup(reply_markup=build_config_keyboard(chat_id))
        await send(msg)

    elif data == "cfg_tip":
        chat_id = query.message.chat_id
        cfg = get_user_config(chat_id)
        new_val = not cfg.get("daily_tip", True)
        set_user_config(chat_id, "daily_tip", new_val)
        is_pt = user_is_pt(chat_id)
        msg = (
            f"{'✅ Dica diária em inglês ativada!' if new_val else '⬜️ Dica diária em inglês desativada.'}"
            if is_pt else
            f"{'✅ Daily English tip enabled!' if new_val else '⬜️ Daily English tip disabled.'}"
        )
        await query.message.edit_reply_markup(reply_markup=build_config_keyboard(chat_id))
        await send(msg)

    elif data == "cfg_activity":
        chat_id = query.message.chat_id
        cfg = get_user_config(chat_id)
        new_val = not cfg.get("daily_activity", True)
        set_user_config(chat_id, "daily_activity", new_val)
        is_pt = user_is_pt(chat_id)
        msg = (
            f"{'✅ Atividade diária ativada!' if new_val else '⬜️ Atividade diária desativada.'}"
            if is_pt else
            f"{'✅ Daily activity enabled!' if new_val else '⬜️ Daily activity disabled.'}"
        )
        await query.message.edit_reply_markup(reply_markup=build_config_keyboard(chat_id))
        await send(msg)

    elif data == "cfg_actlang":
        chat_id = query.message.chat_id
        cfg = get_user_config(chat_id)
        new_lang = "pt" if cfg.get("activity_lang") == "en" else "en"
        set_user_config(chat_id, "activity_lang", new_lang)
        is_pt = user_is_pt(chat_id)
        label = "🇧🇷 Português" if new_lang == "pt" else "🇬🇧 English"
        msg = (
            f"✅ Atividades agora em {label}!"
            if is_pt else
            f"✅ Activities now in {label}!"
        )
        await query.message.edit_reply_markup(reply_markup=build_config_keyboard(chat_id))
        await send(msg)


def build_config_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Build the config menu keyboard showing current state for this user."""
    cfg = get_user_config(chat_id)
    is_pt = cfg.get("lang") == "pt"

    def tog(val: bool) -> str:
        return "✅" if val else "⬜️"

    lang_label    = f"💬 Chat: {'🇧🇷 Português' if is_pt else '🇬🇧 English'} — tap to switch"
    tip_label     = f"{tog(cfg.get('daily_tip', True))} Daily English tip"
    act_lang      = cfg.get("activity_lang", "en")
    act_lang_lbl  = f"🎨 Activity language: {'🇧🇷 PT' if act_lang == 'pt' else '🇬🇧 EN'} — tap to switch"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lang_label,    callback_data="cfg_lang")],
        [InlineKeyboardButton(tip_label,     callback_data="cfg_tip")],
        [InlineKeyboardButton(act_lang_lbl,  callback_data="cfg_actlang")],
    ])


async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/config — show the per-user settings menu."""
    chat_id = update.effective_chat.id
    is_pt = user_is_pt(chat_id)
    title = "⚙️ *Configurações*" if is_pt else "⚙️ *Settings*"
    subtitle = (
        "Toque para alternar cada opção\\. As mudanças são imediatas\\."
        if is_pt else
        "Tap any option to toggle it\\. Changes take effect immediately\\."
    )
    await update.message.reply_text(
        f"{title}\n\n{subtitle}",
        parse_mode="MarkdownV2",
        reply_markup=build_config_keyboard(chat_id),
    )


# ── Text + voice handlers ─────────────────────────────────────────────────────

async def falar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/falar <word or phrase> — sends a TTS voice message with correct pronunciation."""
    if not context.args:
        await update.message.reply_text(
            "Use: `/falar thoroughly`\nI'll send you a voice message with the correct pronunciation.",
            parse_mode="Markdown",
        )
        return

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        await update.message.reply_text(
            "Voice not set up yet — add `OPENAI_API_KEY` to your .env file.",
            parse_mode="Markdown",
        )
        return

    word = " ".join(context.args)
    await update.message.reply_text(f"🔊 Pronouncing: *{word}*...", parse_mode="Markdown")

    # Ask Claude for pronunciation context first
    explanation = ask_claude(
        f"Give a very brief pronunciation guide for the English word or phrase: '{word}'. "
        f"One sentence max. Focus on sounds a Brazilian speaker finds tricky. English only.",
        system=SYSTEM_EN,
    )

    audio_bytes = await text_to_speech(word)
    if audio_bytes:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        with open(tmp_path, "rb") as f:
            await update.message.reply_voice(voice=f, caption=f"🗣️ *{word}*\n\n{explanation}", parse_mode="Markdown")
        os.unlink(tmp_path)
    else:
        await update.message.reply_text(f"🗣️ *{word}*\n\n{explanation}", parse_mode="Markdown")


async def atividade_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/atividade — today's activity in Portuguese. /atividades en — in English."""
    args = context.args
    lang = args[0].lower() if args and args[0].lower() == "en" else "pt"

    if lang == "en":
        await update.message.reply_text("🎨 Getting today's activity...")
        result = ask_claude(
            "Suggest ONE simple home activity for a 2-year-3-month-old child for today. "
            "Use the same format as usual: name, learning goal, materials, steps, bonus tip. "
            "English only. Use simple materials found at home.",
            system=SYSTEM_ACTIVITIES_EN,
        )
    else:
        await update.message.reply_text("🎨 Buscando a atividade do dia...")
        result = ask_claude(DAILY_ACTIVITY_PROMPT, system=SYSTEM_ACTIVITIES_PT)

    await update.message.reply_text(result, parse_mode="Markdown")


async def semana_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/semana — full weekly activity plan, cached per ISO week."""
    plan = get_cached_semana()
    if plan:
        await update.message.reply_text("📅 *Plano da semana* _(do cache — sem custo extra)_", parse_mode="Markdown")
    else:
        await update.message.reply_text("📅 Criando o plano da semana... isso pode levar alguns segundos!")
        plan = ask_claude(WEEKLY_PLAN_PROMPT, system=SYSTEM_ACTIVITIES_PT)
        set_cached_semana(plan)

    # Split if too long for one message
    if len(plan) > 4000:
        mid = plan.find("━━━", 2000)
        if mid == -1:
            mid = 2000
        await update.message.reply_text(plan[:mid], parse_mode="Markdown")
        await update.message.reply_text(plan[mid:], parse_mode="Markdown")
    else:
        await update.message.reply_text(plan, parse_mode="Markdown")

    await update.message.reply_text(
        "💡 *Dica:* Salve esse plano e imprima os itens listados na seção 'Para Imprimir' antes de segunda\\-feira\\!",
        parse_mode="MarkdownV2",
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    reply = ask_claude(update.message.text, system=user_system(chat_id))
    await update.message.reply_text(reply, parse_mode="Markdown")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    is_pt = user_is_pt(chat_id)
    await update.message.reply_text("🎙️ Transcrevendo..." if is_pt else "🎙️ Transcribing...")
    tg_file = await context.bot.get_file(update.message.voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await tg_file.download_to_drive(tmp.name)
        with open(tmp.name, "rb") as f:
            file_bytes = f.read()
    transcript = await transcribe_voice(file_bytes)
    if transcript.startswith("["):
        await update.message.reply_text(transcript)
        return
    said_label = "🗣️ *Você disse:*" if is_pt else "🗣️ *You said:*"
    await update.message.reply_text(f'{said_label} "{transcript}"', parse_mode="Markdown")
    reply = ask_claude(f"The user said (via voice): {transcript}", system=user_system(chat_id))
    await update.message.reply_text(reply, parse_mode="Markdown")


# ── Daily messages ────────────────────────────────────────────────────────────

async def send_daily_tip(context: ContextTypes.DEFAULT_TYPE) -> None:
    # Proactive only: "tip of the day" (for all users who have daily_tip enabled).
    # Daily activity is generated only when the user asks via /atividade or /atividades.
    targets: list[int] = []
    for chat_id in get_all_user_ids():
        cfg = get_user_config(chat_id)
        if cfg.get("daily_tip", True):
            targets.append(chat_id)

    if not targets:
        return

    tip = generate_daily_tip_with_history()
    for chat_id in targets:
        await context.bot.send_message(chat_id=chat_id, text=tip, parse_mode="Markdown")

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error while processing update", exc_info=context.error)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    init_usage_table()
    init_kv_table()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("course",     course_command))
    app.add_handler(CommandHandler("next",       next_command))
    app.add_handler(CommandHandler("lesson",     lesson_command))
    app.add_handler(CommandHandler("tip",        tip_command))
    app.add_handler(CommandHandler("reading",    reading_command))
    app.add_handler(CommandHandler("falar",      falar_command))
    app.add_handler(CommandHandler("atividade",  atividade_command))
    app.add_handler(CommandHandler("atividades", atividade_command))
    app.add_handler(CommandHandler("semana",     semana_command))
    app.add_handler(CommandHandler("config",     config_command))
    app.add_handler(CommandHandler("help",       help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_error_handler(on_error)

    # Always schedule daily messages — sends to all registered users
    app.job_queue.run_daily(
        send_daily_tip,
        time=time(hour=DAILY_TIP_HOUR, minute=DAILY_TIP_MINUTE),
    )
    logger.info(f"Daily messages scheduled at {DAILY_TIP_HOUR:02d}:{DAILY_TIP_MINUTE:02d}")

    # Optional: Pre-warm lesson cache in background (can trigger up to 64 Claude calls).
    if PREWARM_LESSON_CACHE:
        async def prewarm_job(ctx):
            await prewarm_lessons_cache()

        app.job_queue.run_once(prewarm_job, when=30)
        logger.info("Lesson cache pre-warm enabled (PREWARM_LESSON_CACHE=1).")
    else:
        logger.info("Lesson cache pre-warm disabled (set PREWARM_LESSON_CACHE=1 to enable).")

    logger.info("Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
