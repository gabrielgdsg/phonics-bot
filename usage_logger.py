"""
usage_logger.py — shared module for all bots
Logs every Claude API call to PostgreSQL with token counts + cost estimate.
Import and call log_usage() after every claude.messages.create() call.
"""

import os
import logging
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def usage_database_configured() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip())


# Claude Sonnet 4 pricing (per million tokens, as of 2026)
# Update these if Anthropic changes pricing
PRICE_INPUT_PER_M  = 3.00   # $3.00 per 1M input tokens
PRICE_OUTPUT_PER_M = 15.00  # $15.00 per 1M output tokens

def get_db():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    url = url.replace("postgresql://", "postgres://", 1)
    # Prevent hangs if Postgres is temporarily unreachable.
    return psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=5)

def init_usage_table():
    """Create usage_log table if it doesn't exist."""
    if not usage_database_configured():
        logger.warning("DATABASE_URL not set — usage logging disabled until Postgres is linked.")
        return
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usage_log (
                    id SERIAL PRIMARY KEY,
                    bot_name VARCHAR(50) NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    cost_usd NUMERIC(10, 6) NOT NULL DEFAULT 0,
                    endpoint VARCHAR(100) DEFAULT 'messages',
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_usage_bot_date
                    ON usage_log (bot_name, created_at);
            """)
        conn.commit()
    logger.info("Usage table ready.")

def log_usage(bot_name: str, response):
    """
    Log a Claude API response's token usage.
    
    Usage:
        response = claude.messages.create(...)
        log_usage("personal-bot", response)
    """
    try:
        input_tokens  = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = (input_tokens / 1_000_000 * PRICE_INPUT_PER_M +
                output_tokens / 1_000_000 * PRICE_OUTPUT_PER_M)

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO usage_log (bot_name, input_tokens, output_tokens, cost_usd)
                       VALUES (%s, %s, %s, %s)""",
                    (bot_name, input_tokens, output_tokens, round(cost, 6))
                )
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to log usage: {e}")

def get_usage_summary(days: int = 30) -> dict:
    """Return usage summary for the dashboard."""
    if not usage_database_configured():
        return {
            "by_bot": [],
            "daily": [],
            "totals": {},
            "days": days,
        }
    with get_db() as conn:
        with conn.cursor() as cur:
            # Per-bot totals (interval as integer days — works with psycopg2 + Railway Postgres)
            cur.execute("""
                SELECT
                    bot_name,
                    SUM(input_tokens)  AS total_input,
                    SUM(output_tokens) AS total_output,
                    SUM(cost_usd)      AS total_cost,
                    COUNT(*)           AS total_calls,
                    MAX(created_at)    AS last_used
                FROM usage_log
                WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
                GROUP BY bot_name
                ORDER BY total_cost DESC
            """, (days,))
            by_bot = cur.fetchall()

            cur.execute("""
                SELECT
                    bot_name,
                    DATE(created_at) AS day,
                    SUM(cost_usd)    AS daily_cost,
                    COUNT(*)         AS calls
                FROM usage_log
                WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
                GROUP BY bot_name, DATE(created_at)
                ORDER BY day ASC
            """, (days,))
            daily = cur.fetchall()

            cur.execute("""
                SELECT
                    SUM(cost_usd)      AS total_cost,
                    SUM(input_tokens)  AS total_input,
                    SUM(output_tokens) AS total_output,
                    COUNT(*)           AS total_calls
                FROM usage_log
                WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
            """, (days,))
            totals = cur.fetchone()

    return {
        "by_bot": [dict(r) for r in by_bot],
        "daily":  [dict(r) for r in daily],
        "totals": dict(totals) if totals else {},
        "days":   days,
    }
