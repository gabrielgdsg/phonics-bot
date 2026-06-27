#!/usr/bin/env python3
"""
English + Portuguese Phonics Telegram Bot — v4
Features:
  /course          — tap buttons to pick English CLR or Portuguese Fonética
  /next en|pt      — jump to your next lesson automatically
  /lesson en|pt N  — open a specific lesson
  /semana          — generate a full weekly activity plan (PT) with printout bundle
  /musica          — children's songs with lyrics, chords, and tips (from DB)
  /atividade       — today's activity idea in Portuguese
  /atividades en   — today's activity idea in English
  /falar <word>    — bot sends a voice message pronouncing the word correctly (TTS)
  Daily morning message: English tip + Portuguese activity nudge
  Progress saved in PostgreSQL (users + lessons tables) when DATABASE_URL is set,
  otherwise progress.json / cache.json locally.
"""

import os
import json
import logging
import tempfile
import re
from datetime import time, date, datetime
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

# ── Course tables (lessons, users, weekly_plans) ─────────────────────────────

_course_db_ready: bool | None = None

def course_db_ready() -> bool:
    """True when the lessons table exists and has at least one PT lesson."""
    global _course_db_ready
    if _course_db_ready is not None:
        return _course_db_ready
    if not db_available():
        _course_db_ready = False
        return False
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_name = 'lessons' LIMIT 1"
                )
                if not cur.fetchone():
                    _course_db_ready = False
                    return False
                cur.execute("SELECT 1 FROM lessons WHERE lang = 'pt' AND num = 1 LIMIT 1")
                _course_db_ready = cur.fetchone() is not None
    except Exception as e:
        logger.warning("Course DB check failed; using local fallbacks: %s", e)
        _course_db_ready = False
    return _course_db_ready

def fetch_lesson_row(lang: str, num: int) -> dict | None:
    if not db_available():
        return None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT title, words, sentences, tips, enrichment, note
                    FROM lessons WHERE lang = %s AND num = %s
                    """,
                    (lang, num),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.warning("lessons SELECT failed: %s", e)
        return None

def format_lesson_body(row: dict, lang: str) -> str:
    parts = [row["tips"]]
    words = row.get("words") or []
    sentences = row.get("sentences") or []
    if words:
        label = "Palavras" if lang == "pt" else "Words"
        parts.append(f"\n*{label}:* " + ", ".join(words))
    if sentences:
        label = "Frases" if lang == "pt" else "Sentences"
        parts.append(f"\n*{label}:*\n" + "\n".join(f"• {s}" for s in sentences))
    return "\n".join(parts)

def migrate_kv_users_to_db() -> None:
    """One-time import of progress.json / bot_kv users into the users table."""
    if not course_db_ready():
        return
    raw = kv_get("data") if db_available() else None
    if not isinstance(raw, dict) and PROGRESS_FILE.exists():
        try:
            raw = json.loads(PROGRESS_FILE.read_text())
        except Exception:
            raw = None
    if not isinstance(raw, dict):
        return
    lessons = raw.get("lessons", {})
    users = raw.get("users", {})
    if not users and not lessons:
        return
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                for uid, cfg in users.items():
                    if not isinstance(cfg, dict):
                        cfg = {}
                    cur.execute(
                        """
                        INSERT INTO users (
                            chat_id, lang, daily_tip, daily_activity, activity_lang,
                            en_lesson, pt_lesson
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (chat_id) DO NOTHING
                        """,
                        (
                            int(uid),
                            cfg.get("lang", "en"),
                            bool(cfg.get("daily_tip", True)),
                            bool(cfg.get("daily_activity", False)),
                            cfg.get("activity_lang", "en"),
                            int(lessons.get("en", 1)),
                            int(lessons.get("pt", 1)),
                        ),
                    )
            conn.commit()
        logger.info("Migrated %d user(s) from local progress into users table", len(users))
    except Exception as e:
        logger.warning("User migration to DB failed: %s", e)

def init_course_db() -> None:
    if not course_db_ready():
        logger.info("Course DB not ready — using hardcoded lessons + local files.")
        return
    migrate_kv_users_to_db()
    logger.info("Course DB ready — lessons, users, and weekly_plans active.")

def daily_tips_db_count(lang: str = "en") -> int:
    if not db_available():
        return 0
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM daily_tips WHERE lang = %s", (lang,))
                return int(cur.fetchone()["n"])
    except Exception:
        return 0

def tip_number_for_date(d: date | None = None) -> int:
    d = d or date.today()
    return d.timetuple().tm_yday

def fetch_daily_tip_row(lang: str, tip_number: int) -> dict | None:
    if not db_available():
        return None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT word, definition, example_1, example_2, toddler_tip
                    FROM daily_tips WHERE lang = %s AND tip_number = %s
                    """,
                    (lang, tip_number),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.warning("daily_tips SELECT failed: %s", e)
        return None

def format_daily_tip_row(row: dict) -> str:
    return (
        f"🌟 *{row['word']}*\n\n"
        f"📖 *What it means*\n{row['definition']}\n\n"
        f"🏠 *Use it at home today*\n"
        f"• {row['example_1']}\n"
        f"• {row['example_2']}\n\n"
        f"🎵 *Toddler tip*\n{row['toddler_tip']}\n\n"
        "_(do banco de dados — sem custo de API)_"
    )

def fetch_songs(lang: str = "pt") -> list[dict]:
    if not db_available():
        return []
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, category FROM songs WHERE lang = %s ORDER BY title",
                    (lang,),
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.warning("songs list failed: %s", e)
        return []

def fetch_song(lang: str, query: str) -> dict | None:
    if not db_available():
        return None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                if query.isdigit():
                    cur.execute(
                        """
                        SELECT title, lyrics, chords, vocabulary_tips, youtube_url, category
                        FROM songs WHERE lang = %s AND id = %s
                        """,
                        (lang, int(query)),
                    )
                else:
                    cur.execute(
                        """
                        SELECT title, lyrics, chords, vocabulary_tips, youtube_url, category
                        FROM songs WHERE lang = %s AND title ILIKE %s
                        LIMIT 1
                        """,
                        (lang, f"%{query}%"),
                    )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.warning("song fetch failed: %s", e)
        return None

def format_song_message(song: dict) -> list[str]:
    """Return message chunks (Telegram limit ~4096)."""
    parts = [
        f"🎵 *{song['title']}* _({song.get('category', 'song')})_\n",
        f"📝 *Letra*\n{song['lyrics']}\n",
    ]
    if song.get("chords"):
        parts.append(f"🎸 *Cifra*\n```\n{song['chords']}\n```\n")
    if song.get("vocabulary_tips"):
        parts.append(song["vocabulary_tips"])
    if song.get("youtube_url"):
        parts.append(f"\n▶️ [YouTube]({song['youtube_url']})")

    full = "\n".join(parts)
    if len(full) <= 4000:
        return [full]
    chunks = []
    for block in parts:
        if chunks and len(chunks[-1]) + len(block) < 3900:
            chunks[-1] += "\n" + block
        else:
            chunks.append(block)
    return chunks

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
    if course_db_ready():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users (chat_id) VALUES (%s)
                        ON CONFLICT (chat_id) DO NOTHING
                        """,
                        (chat_id,),
                    )
                conn.commit()
            logger.info("User registered in DB: %s", chat_id)
            return
        except Exception as e:
            logger.warning("DB register_user failed; falling back: %s", e)

    data = load_data()
    uid = str(chat_id)
    if uid not in data.get("users", {}):
        data.setdefault("users", {})[uid] = DEFAULT_CONFIG.copy()
        save_data(data)
        logger.info(f"New user registered: {chat_id}")

def _user_config_from_row(row: dict) -> dict:
    return {
        "lang": row["lang"],
        "daily_tip": row["daily_tip"],
        "daily_activity": row["daily_activity"],
        "activity_lang": row["activity_lang"],
    }

def get_user_config(chat_id: int) -> dict:
    if course_db_ready():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
                    row = cur.fetchone()
                    if not row:
                        cur.execute(
                            "INSERT INTO users (chat_id) VALUES (%s) RETURNING *",
                            (chat_id,),
                        )
                        row = cur.fetchone()
                    conn.commit()
                    return _user_config_from_row(dict(row))
        except Exception as e:
            logger.warning("DB get_user_config failed; falling back: %s", e)

    data = load_data()
    uid = str(chat_id)
    if uid not in data.get("users", {}):
        data.setdefault("users", {})[uid] = DEFAULT_CONFIG.copy()
        save_data(data)
    return data["users"][uid]

def set_user_config(chat_id: int, key: str, value) -> None:
    if course_db_ready() and key in DEFAULT_CONFIG:
        col = key
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE users SET {col} = %s WHERE chat_id = %s",
                        (value, chat_id),
                    )
                conn.commit()
            return
        except Exception as e:
            logger.warning("DB set_user_config failed; falling back: %s", e)

    data = load_data()
    uid = str(chat_id)
    data.setdefault("users", {}).setdefault(uid, DEFAULT_CONFIG.copy())[key] = value
    save_data(data)

def get_all_user_ids() -> list[int]:
    """Return all registered chat IDs."""
    if course_db_ready():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT chat_id FROM users")
                    return [int(r["chat_id"]) for r in cur.fetchall()]
        except Exception as e:
            logger.warning("DB get_all_user_ids failed; falling back: %s", e)
    return [int(uid) for uid in load_data().get("users", {}).keys()]

def get_user_lesson_progress(chat_id: int) -> dict:
    if course_db_ready():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT en_lesson, pt_lesson FROM users WHERE chat_id = %s",
                        (chat_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        return {"en": int(row["en_lesson"]), "pt": int(row["pt_lesson"])}
        except Exception as e:
            logger.warning("DB get_user_lesson_progress failed; falling back: %s", e)
    return load_data().get("lessons", {"en": 1, "pt": 1})

DAILY_TIP_HISTORY_LIMIT = 5000
TIP_EXPRESSION_POOL = [
    "tidy up", "take turns", "inside voice", "outside voice", "good helper",
    "all set", "almost there", "one more time", "have a go", "give it a try",
    "you did it", "nice and steady", "easy does it", "little by little",
    "hands to yourself", "use your words", "show me", "tell me more",
    "what happened?", "let's check", "let me help", "my turn, your turn",
    "first... then...", "all set to go", "time to switch", "clean as you go",
    "pop it back", "put it away", "line it up", "match them up",
    "spot the difference", "let's figure it out", "choose one", "good noticing",
    "that makes sense", "great thinking", "good question", "that's tricky",
    "let's practice", "keep trying", "you are improving", "nice teamwork",
    "be patient", "take a breath", "quiet hands", "walking feet",
    "eyes on me", "listen carefully", "say it slowly", "try it again",
    "I can do hard things", "that's enough", "all finished", "not yet",
    "ready when you are", "let's tidy together", "use gentle hands",
    "can you help me?", "show me how", "what do you notice?",
    "you can choose", "almost done", "great effort", "small steps",
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
        created_at = entry.get("created_at")
        if created_at is not None and not isinstance(created_at, str):
            created_at = None
        out.append(
            {
                "date": entry["date"],
                "created_at": created_at,
                "expression": expr,
                "expression_norm": expr_norm,
                "tip": tip,
            }
        )
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

def pick_non_repeating_expression(used_expr_norm: list[str]) -> str:
    used = set(used_expr_norm)
    for expr in TIP_EXPRESSION_POOL:
        if expr.casefold() not in used:
            return expr
    return ""

def pick_model_generated_expression(used_expr_norm: list[str]) -> str:
    """Ask Claude for a fresh expression not used before."""
    used_preview = ", ".join(used_expr_norm[-200:]) if used_expr_norm else "none"
    candidate = ask_claude(
        "Suggest ONE useful daily-home English expression for a parent and toddler.\n"
        "Rules:\n"
        "- 1 to 4 words\n"
        "- not basic greetings\n"
        "- no punctuation except apostrophe\n"
        "- output only the expression, no explanation\n"
        f"- do not use any of these already-used expressions: {used_preview}",
        system=SYSTEM_EN,
        temperature=0.8,
    ).strip().strip('"').strip("'")
    return candidate

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

def generate_daily_tip_with_history(force_new: bool = False) -> str:
    """Return today's tip — from DB pool when available, else Claude."""
    today = date.today()
    tip_num = tip_number_for_date(today)

    if not force_new and daily_tips_db_count("en") > 0:
        row = fetch_daily_tip_row("en", tip_num)
        if not row:
            row = fetch_daily_tip_row("en", ((tip_num - 1) % daily_tips_db_count("en")) + 1)
        if row:
            return format_daily_tip_row(row)

    history = load_daily_tip_history()

    # If the job runs twice, reuse today's tip (Claude path only).
    today_iso = today.isoformat()
    if not force_new:
        for entry in reversed(history):
            if entry.get("date") == today_iso and isinstance(entry.get("tip"), str):
                return entry["tip"]

    recent_expr_norm: list[str] = []
    recent_expr_display: list[str] = []
    for e in history:
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
    if not forced_expr:
        # Pool exhausted: generate a new unique expression dynamically.
        for _ in range(5):
            candidate = pick_model_generated_expression(recent_expr_norm)
            candidate_norm = candidate.casefold()
            if candidate and candidate_norm not in recent_expr_norm:
                forced_expr = candidate
                break
    if not forced_expr:
        forced_expr = f"useful phrase {date.today().isoformat()}"

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
    history.append(
        {
            "date": today_iso,
            "created_at": datetime.utcnow().isoformat(timespec="seconds"),
            "expression": expr,
            "expression_norm": expr_norm,
            "tip": tip,
        }
    )
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
    row = fetch_lesson_row(lang, num)
    if row and row.get("enrichment"):
        return row["enrichment"]
    return load_cache().get("lessons", {}).get(f"{lang}_{num}")

def set_cached_lesson(lang: str, num: int, text: str) -> None:
    if course_db_ready():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE lessons SET enrichment = %s
                        WHERE lang = %s AND num = %s
                        """,
                        (text, lang, num),
                    )
                    updated = cur.rowcount
                conn.commit()
            if updated:
                return
        except Exception as e:
            logger.warning("DB set_cached_lesson failed; falling back to file cache: %s", e)
    cache = load_cache()
    cache.setdefault("lessons", {})[f"{lang}_{num}"] = text
    save_cache(cache)

def get_cached_semana() -> str | None:
    """Return cached weekly plan if it's from the current ISO week."""
    current_week = date.today().strftime("%G-W%V")
    if course_db_ready():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT plan_pt FROM weekly_plans WHERE week_iso = %s",
                        (current_week,),
                    )
                    row = cur.fetchone()
                    if row and row.get("plan_pt"):
                        return row["plan_pt"]
        except Exception as e:
            logger.warning("DB get_cached_semana failed; falling back: %s", e)

    cache = load_cache()
    semana = cache.get("semana", {})
    if semana.get("week") == current_week:
        return semana.get("plan")
    return None

def set_cached_semana(plan: str) -> None:
    current_week = date.today().strftime("%G-W%V")
    if course_db_ready():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO weekly_plans (week_iso, plan_pt)
                        VALUES (%s, %s)
                        ON CONFLICT (week_iso) DO UPDATE
                        SET plan_pt = EXCLUDED.plan_pt
                        """,
                        (current_week, plan),
                    )
                conn.commit()
            return
        except Exception as e:
            logger.warning("DB set_cached_semana failed; falling back: %s", e)

    cache = load_cache()
    cache["semana"] = {"week": current_week, "plan": plan}
    save_cache(cache)

def lessons_cache_complete() -> bool:
    """True if all 64 lessons have enrichment (DB or file cache)."""
    if course_db_ready():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS n FROM lessons
                        WHERE enrichment IS NOT NULL AND num BETWEEN 1 AND 32
                        """
                    )
                    row = cur.fetchone()
                    if row and int(row["n"]) >= 64:
                        return True
                    if row and int(row["n"]) >= 32:
                        cur.execute(
                            "SELECT COUNT(*) AS n FROM lessons WHERE lang = 'en' LIMIT 1"
                        )
                        if int(cur.fetchone()["n"]) == 0:
                            return False
        except Exception as e:
            logger.warning("DB lessons_cache_complete check failed: %s", e)
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
                continue  # already in DB or file cache
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

def get_next_lesson(lang: str, chat_id: int) -> int:
    return get_user_lesson_progress(chat_id).get(lang, 1)

def mark_lesson_done(lang: str, num: int, chat_id: int) -> None:
    if course_db_ready():
        col = "en_lesson" if lang == "en" else "pt_lesson"
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {col} FROM users WHERE chat_id = %s",
                        (chat_id,),
                    )
                    row = cur.fetchone()
                    current = int(row[col]) if row else 1
                    if num >= current:
                        cur.execute(
                            f"UPDATE users SET {col} = %s WHERE chat_id = %s",
                            (min(num + 1, 32), chat_id),
                        )
                conn.commit()
            return
        except Exception as e:
            logger.warning("DB mark_lesson_done failed; falling back: %s", e)

    data = load_data()
    lessons = data.setdefault("lessons", {"en": 1, "pt": 1})
    if num >= lessons.get(lang, 1):
        lessons[lang] = min(num + 1, 32)
    save_data(data)

def load_progress(chat_id: int | None = None) -> dict:
    """Backwards compat shim — returns lesson progress for a user."""
    if chat_id is not None:
        return get_user_lesson_progress(chat_id)
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
    (1,1):  ("Vogal A", "Apresente apenas a letra A hoje. Diga o SOM 'ah' — não o nome. Palavras: ANA, ASA, AI, AVÓ, ALÔ. ANA no começo — nome curto. ÁGUA fica para a lição 18 (som GU). ALÔ na hora de brincar de telefone."),
    (2,2):  ("Vogal E", "Som novo: 'eh' como em ELA. Palavras: ELA, EU, ELE. Compare com o A da sessão anterior — segure dois cartões e peça para ela apontar para o A, depois o E. A diferença entre 'ah' e 'eh' é a lição toda de hoje."),
    (3,3):  ("Vogal I", "Som novo: 'ee' como em IDA. Palavras: IDA, IR, IA. Agora você tem A E I — jogue um jogo simples: fale um som, ela aponta para o cartão certo. 'Onde está o I?' Três vogais já são suficientes para uma criança pequena. Elogie cada acerto."),
    (4,4):  ("Vogal O", "Som novo: 'oh' como em OVO. Palavras: OVO, OI, OSO. OI é perfeito — ela fala toda hora como cumprimento. Mostre a palavra OI e veja a reação dela. Quatro vogais agora: A E I O."),
    (5,5):  ("Vogal U", "Som novo: 'u' como em UVA. Palavras: UVA, UM, UÊ. Segure uma uva (ou figura) e diga U-VA devagar. Agora você tem as cinco vogais. Passe essa sessão toda revisando: A E I O U em ordem, depois misturadas."),
    (6,6):  ("Revisão das 5 vogais", "Sem letra nova hoje. Revisão completa: A E I O U. Coloque os cinco cartões no chão. Fale um som — ela corre para o cartão certo. Torne físico e divertido. Cronometre quantos segundos ela leva para achar cada um. Comemore cada acerto. Essa é a base de tudo."),
    (7,7):  ("Consoante M", "Som novo: 'mm' — lábios fechados, depois abre. Palavras: MÃE, MÃO, MIAU, MEIA, MASSA. MÃE é a palavra mais poderosa do vocabulário dela. Una devagar: M... Ã... E... = MÃE. Frases: 'AMO A MÃE.' 'MIAU MIAU.' 'MAMÃE ME AMA.' Deixe ela segurar o cartão MÃE quando acertar."),
    (8,8):  ("Consoante P", "Som novo: 'p' — um pequeno sopro de ar. Palavras: PAI, PÉ, PIA, PATA. PAI é sua arma secreta. NINA é a cachorrinha — use em PATA DA NINA. Frases: 'AMO O PAI.' 'PATA DA NINA.' 'PULA, PAPAI!' Pratique MÃE + PAI lado a lado."),
    (9,9):  ("Consoante B", "Som novo: 'b' — como P mas com voz. Palavras: BOLA, BEBÊ, BOCA, BABA. Role uma bola pelo chão dizendo B-O-L-A. Frases: 'BATI NA BOLA.' 'O BEBÊ BABA.' Tente BEBÊ com uma boneca enquanto lê."),
    (10,10):("Consoante T", "Som novo: 't'. Palavras: TATU, TETO, BOTA, TEIA, TESTA. Frases: 'TEIA NO TETO.' 'TOCA A TESTA.' 'TON TON.' 'TON TON CAIU.' — TPR: toca a testa, bate na porta."),
    (11,11):("Consoante D", "Som novo: 'd' — como T mas com voz. Palavras: DEDO, DADO, DOIS, DINDA. Frases: 'O DEDO DÓI.' 'A DINDA DORME.' 'TOCA O DEDO.' — TPR no dedo."),
    (12,12):("Consoante V", "Som novo: 'v' — dente no lábio de baixo, vibrando. Palavras: VACA, VELA, VOVÓ, VENTO. Frases: 'A VACA FAZ MUU.' 'AMO A VOVÓ.' 'SOPRA!' — TPR: sopra junto."),
    (13,13):("Consoante F", "Som novo: 'f' — mesma boca que V, sem vibração. Palavras: FADA, FOCA, FOFA, FOME. Frases: 'A FADA VOA.' 'TÔ COM FOME.' 'CADÊ A NINA?' — leia tô como ela fala."),
    (14,14):("Consoante N", "Som novo: 'n' — som sai pelo nariz. Palavras: NINA, NARIZ, NADA, NUVEM. Frases: 'A NINA NADA.' 'APONTA O NARIZ.' 'OLHA A NUVEM!' — TPR em cada uma."),
    (15,15):("Revisão Geral — Lições 7 a 14", "Sem letra nova. Revisão M P B T D V F N. Frases: 'PAI TEM BOLA.' 'EU AMO A MAMÃE.' 'CADÊ O PAPAI?' — brinque de esconder."),
    (16,16):("Consoante L", "Som novo: 'l'. Palavras: LOBO, BOLO, LAMA, LUA, LATA. Frases: 'O LOBO UIVA.' 'QUERO BOLO!' 'LAVA A MÃO.' — TPR na hora de lavar."),
    (17,17):("Consoante C (CA CO CU)", "Som novo: 'k' duro — APENAS antes de A, O, U. Palavras: CAMA, COPO, CUBO, CASA. Frases: 'A CASA É NOSSA.' 'VAI PARA A CAMA.' 'O COPO CAI.' NÃO introduza CE ou CI ainda."),
    (18,18):("Consoante G (GA GO GU)", "Som 'g' duro — GA GO GU. Palavras: GATO, GOTA, GALO, GU, GOL, ÁGUA. GU é o dindo. ÁGUA agora — som GU. Frases: 'O GATO MIA.' 'O GALO CANTA.' 'GU FEZ GOL.' 'CAIU UMA GOTA.'"),
    (19,19):("Consoante R (som suave)", "Som R suave entre vogais. Palavras: FORA, LAURA, PERA, DURO. Frases: 'VAMOS LÁ FORA!' 'OI, LAURA!' 'COME A PERA.'"),
    (20,20):("Consoante S", "Som 's'. Palavras: SAPO, SUCO, SOPA, SOLA. Frases: 'O SAPO PULA.' 'COME A SOPA.' 'BATE PALMA.' — TPR: bate palma."),
    (21,21):("Revisão + Frases Completas", "Sem letra nova. Revisão das lições 16–20: L C G R S. Frases: 'O GATO DORME NA CAMA.' 'O SAPO PULA NA LAMA.' 'O BOLO É DA MÃE.' Passe o dedo sob cada palavra da esquerda para a direita."),
    (22,22):("Dígrafo LH", "Som novo: LH — som único do português. Palavras: FILHA, FOLHA, OLHA, GALHO. Frases: 'OLHA O GATO!' 'A FOLHA CAI.' 'É MINHA FILHA.' Use OLHA em momentos reais hoje."),
    (23,23):("Dígrafo NH", "Som novo: NH — nasal, como 'ny' em canyon. Palavras: NINHO, BANHO, MINHA. Frases: 'HORA DO BANHO!' 'É MINHA BOLA.' 'DORME NO NINHO.'"),
    (24,24):("Dígrafo CH", "Som novo: CH — como 'sh' em inglês. Palavras: CHÃO, CHUVA, BICHO, CHAVE. Frases: 'A CHUVA CAI.' 'CAI NO CHÃO.' 'QUE BICHO É?'"),
    (25,25):("Letra X (som CH)", "Letra X — hoje APENAS o som 'ch/sh'. Palavras: XÍCARA, XALE, PEIXE, CAIXA, ROXO. Frases: 'O PEIXE NADA.' 'O PEIXE NA CAIXA.' 'OLHA O ROXO!'"),
    (26,26):("J e G Suave (GE GI)", "Som 'j' suave. Palavras: GEGÊ, GELO, GIRAFA, JACARÉ, JOGO. Frases: 'A GIRAFA COME.' 'TOCA O GELO!' 'JOGO COM PAPAI.'"),
    (27,27):("Cedilha Ç", "Ç sempre soa como S. Palavras: MAÇÃ, AÇAÍ, TAÇA, ALMOÇO. Frases: 'COME A MAÇÃ.' 'QUERO AÇAÍ!' 'HORA DO ALMOÇO!'"),
    (28,28):("Vogais Nasais: ÃO, EM, IM", "Vogais nasais — ar pelo nariz e pela boca. Palavras: MÃO, PÃO, BEM, SIM, TEM. Frases: 'SIM, EU QUERO.' 'PÃO COM MEL.' 'MÃO DA MÃE.'"),
    (29,29):("Vogais Nasais: OM, UM, AN", "Mais vogais nasais. Palavras: BOM, UM, BANCO, DANÇA. Frases: 'BOM DIA!' 'BOA NOITE!' 'HORA DA DANÇA!' — expressões do cotidiano."),
    (30,30):("Revisão de Todos os Dígrafos", "Sem conteúdo novo. Revisão: LH NH CH X J/G-suave Ç e nasais. Frases: 'O FILHO TOMA BANHO.' 'A CHUVA CAI NA MÃO.' 'OBRIGADO!'"),
    (31,31):("Letras Minúsculas — Parte 1", "Palavras em minúsculo: mãe, pai, bola, gato, sapo, cama. Frases: 'o gato dorme.' 'pula, nina!' 'eu amo mamãe.'"),
    (32,32):("Letras Minúsculas + Leitura Livre", "Palavras: filho, banho, chuva, maçã, girafa, leão. Frases: 'o filho toma banho.' 'até logo!' 'a girafa come a folha.' Depois leia um livro ilustrado juntos."),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_lesson_info(lang: str, num: int) -> tuple[str, str]:
    """Returns (label, tips) for a lesson. Tips language matches lang."""
    row = fetch_lesson_row(lang, num)
    if row:
        course = "English CLR" if lang == "en" else "Português — Fonética"
        word = "Lesson" if lang == "en" else "Lição"
        label = f"📚 *{course} — {word} {num}: {row['title']}*"
        return label, format_lesson_body(row, lang)

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


async def deliver_lesson(send_fn, lang: str, num: int, chat_id: int, mark_done: bool = False) -> None:
    """Fetch lesson info + enrichment (from DB if available) and send to user."""
    label, tips = get_lesson_info(lang, num)
    system = SYSTEM_PT if lang == "pt" else SYSTEM_EN

    enriched = get_cached_lesson(lang, num)
    if not enriched:
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
        logger.info("Lesson %s_%s generated on demand.", lang, num)

    next_num = min(num + 1, 32)
    row = fetch_lesson_row(lang, num)
    from_db = bool(row and row.get("enrichment"))

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

    source = "_(do banco de dados)_" if from_db and lang == "pt" else ("_(from database)_" if from_db else "")

    await send_fn(f"{label}\n\n{tips}", parse_mode="Markdown")
    extra_header = "💡 *Dicas extras:*" if lang == "pt" else "💡 *Extra tips:*"
    if source:
        extra_header += f" {source}"
    await send_fn(
        f"{extra_header}\n\n{enriched}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

    if mark_done:
        mark_lesson_done(lang, num, chat_id)


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
            InlineKeyboardButton("🎵 Músicas",            callback_data="quick_musica"),
            InlineKeyboardButton("💡 Tip of the day",     callback_data="quick_tip"),
        ],
        [
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
    chat_id = update.effective_chat.id
    progress = load_progress(chat_id)
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
    chat_id = update.effective_chat.id
    num = get_next_lesson(lang, chat_id)
    if num > 32:
        msg = "🎉 You've completed all 32 lessons! Well done!" if lang == "en" else "🎉 Você completou todas as 32 lições! Parabéns!"
        await update.message.reply_text(msg)
        return
    send = update.message.reply_text
    await deliver_lesson(send, lang, num, chat_id)


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

    chat_id = update.effective_chat.id
    send = update.message.reply_text
    await deliver_lesson(send, lang, num, chat_id)


async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("✨ Getting your tip...")
    tip = generate_daily_tip_with_history()
    await update.message.reply_text(tip, parse_mode="Markdown")

async def nexttip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("✨ Getting a fresh new tip...")
    tip = generate_daily_tip_with_history(force_new=True)
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
        "📅 /semana — full weekly plan + printout list\n"
        "🎵 /musica — children's songs (lyrics + chords + tips)\n\n"
        "*English learning:*\n"
        "🔊 /falar <word> — hear correct pronunciation\n"
        "💡 /tip — word of the day\n"
        "🆕 /nexttip — force a different tip now\n"
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
        chat_id = query.message.chat_id
        progress = load_progress(chat_id)
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
        await deliver_lesson(send, lang, num, query.message.chat_id)

    # Mark lesson as done
    elif data.startswith("done_"):
        _, lang, num_str = data.split("_")
        num = int(num_str)
        chat_id = query.message.chat_id
        mark_lesson_done(lang, num, chat_id)
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
        chat_id = query.message.chat_id
        num = get_next_lesson(lang, chat_id)
        if num > 32:
            msg = "🎉 You've completed all 32 lessons!" if lang == "en" else "🎉 Você completou todas as 32 lições!"
            await send(msg)
        else:
            await deliver_lesson(send, lang, num, chat_id)

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

    # Pinned menu: songs
    elif data == "quick_musica":
        songs = fetch_songs("pt")
        if not songs:
            await send(
                "🎵 Ainda não há músicas no banco. Rode `seed_songs.py` ou gere com SONGS_AND_TIPS_GENERATION.md."
            )
        else:
            lines = "\n".join(f"• {s['title']}" for s in songs)
            await send(
                f"🎵 *Músicas disponíveis:*\n{lines}\n\n"
                "Use `/musica Sapo Cururu` para ver letra, cifra e dicas.",
                parse_mode="Markdown",
            )

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


async def musica_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/musica — list songs or show one by name."""
    args = context.args
    if not args:
        songs = fetch_songs("pt")
        if not songs:
            await update.message.reply_text(
                "🎵 Nenhuma música no banco ainda.\n"
                "As músicas são carregadas via `seed_songs.py` ou os prompts em SONGS_AND_TIPS_GENERATION.md."
            )
            return
        lines = "\n".join(f"{i}. {s['title']}" for i, s in enumerate(songs, 1))
        await update.message.reply_text(
            f"🎵 *Músicas para cantar com a Laura:*\n{lines}\n\n"
            "Exemplo: `/musica Sapo Cururu`",
            parse_mode="Markdown",
        )
        return

    query = " ".join(args)
    song = fetch_song("pt", query)
    if not song:
        await update.message.reply_text(f"Não encontrei \"{query}\". Use `/musica` para ver a lista.", parse_mode="Markdown")
        return

    for chunk in format_song_message(song):
        await update.message.reply_text(chunk, parse_mode="Markdown")


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
    init_course_db()
    if daily_tips_db_count("en") == 0:
        logger.info("daily_tips empty — run: python seed_daily_tips.py")
    if not fetch_songs("pt"):
        logger.info("songs empty — run: python seed_songs.py")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("course",     course_command))
    app.add_handler(CommandHandler("next",       next_command))
    app.add_handler(CommandHandler("lesson",     lesson_command))
    app.add_handler(CommandHandler("tip",        tip_command))
    app.add_handler(CommandHandler("nexttip",    nexttip_command))
    app.add_handler(CommandHandler("reading",    reading_command))
    app.add_handler(CommandHandler("falar",      falar_command))
    app.add_handler(CommandHandler("atividade",  atividade_command))
    app.add_handler(CommandHandler("atividades", atividade_command))
    app.add_handler(CommandHandler("semana",     semana_command))
    app.add_handler(CommandHandler("musica",     musica_command))
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
