#!/usr/bin/env python3
"""Seed daily_tips table with 365 English tips (no API calls). Run once on Railway or locally."""

from __future__ import annotations

import itertools
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from bot import TIP_EXPRESSION_POOL, get_db  # noqa: E402

EXTRA_EXPRESSIONS = [
    "wash your hands", "brush your teeth", "time for bed", "wake up", "good morning",
    "thank you", "please", "excuse me", "sorry", "you're welcome",
    "come here", "wait here", "hold on", "let's go", "slow down",
    "be careful", "watch out", "look out", "stay close", "hold my hand",
    "share please", "my turn", "your turn", "well done", "great job",
    "not yet", "almost", "one more", "all done", "time to eat",
    "drink water", "sit down", "stand up", "come back", "over here",
    "what's that?", "I see you", "I hear you", "nice try", "keep going",
    "calm down", "deep breath", "gentle please", "soft voice", "loud voice",
    "open wide", "close the door", "turn off", "turn on", "pick it up",
    "put it down", "on the table", "in the box", "under the bed", "behind you",
    "in front", "next to", "on top", "get dressed", "put on shoes",
    "take off shoes", "zip up", "button up", "wash up", "dry off",
    "wipe your face", "blow your nose", "cover your mouth", "sneeze please",
    "feel better", "are you okay?", "I love you", "see you soon", "bye bye",
]

TODDLER_GAMES = [
    "Sing it while you tidy toys together.",
    "Make it a call-and-response game during play.",
    "Use it as a countdown before switching activities.",
    "Pair it with a simple gesture she can copy.",
    "Say it during a daily routine so it sticks naturally.",
]


def build_pool() -> list[str]:
    seen: set[str] = set()
    pool: list[str] = []
    for expr in itertools.chain(TIP_EXPRESSION_POOL, EXTRA_EXPRESSIONS):
        key = expr.casefold()
        if key not in seen:
            seen.add(key)
            pool.append(expr)
    # Pad to 365 with numbered variants
    n = 1
    while len(pool) < 365:
        base = TIP_EXPRESSION_POOL[n % len(TIP_EXPRESSION_POOL)]
        variant = f"{base} ({n})"
        if variant.casefold() not in seen:
            seen.add(variant.casefold())
            pool.append(variant)
        n += 1
    return pool[:365]


def row_for(n: int, word: str) -> tuple:
    game = TODDLER_GAMES[n % len(TODDLER_GAMES)]
    clean = word.split(" (")[0]
    return (
        "en",
        n,
        word,
        f'A useful everyday expression for parents and toddlers: "{clean}".',
        f'"{clean.capitalize()}!" — say it while playing together.',
        f'Use "{clean}" naturally during your routine today.',
        game,
    )


def main() -> None:
    pool = build_pool()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM daily_tips WHERE lang = 'en'")
            if int(cur.fetchone()["n"]) >= 365:
                print("daily_tips already seeded (365+ rows). Skipping.")
                return
            for n, word in enumerate(pool, start=1):
                cur.execute(
                    """
                    INSERT INTO daily_tips (
                        lang, tip_number, word, definition, example_1, example_2, toddler_tip
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (lang, tip_number) DO UPDATE SET
                        word = EXCLUDED.word,
                        definition = EXCLUDED.definition,
                        example_1 = EXCLUDED.example_1,
                        example_2 = EXCLUDED.example_2,
                        toddler_tip = EXCLUDED.toddler_tip
                    """,
                    row_for(n, word),
                )
        conn.commit()
    print(f"Seeded {len(pool)} daily tips into daily_tips.")


if __name__ == "__main__":
    main()
