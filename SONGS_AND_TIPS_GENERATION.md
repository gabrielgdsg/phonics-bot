# 🎵 Songs + Daily Tips — Generation Plan
# Self-contained prompts — paste into any Claude interface
# Guitar: intermediate (barre chords OK) | Key: G major | Capo as needed
#
# CHORD FORMAT used in all prompts:
# Chord names written above the syllable where the change happens:
#   G              C
#   Sapo cururu na beira do rio
#   D                    G
#   Quando o sapo canta ó maninha
#
# Available chords: G, C, D, Em, Am, Bm, A7, D7, E7
# Always state capo position if used.
#
# SQL PATTERN for every song:
#   INSERT INTO songs (lang, title, lyrics, chords, vocabulary_tips, youtube_url, age_min, age_max, category)
#   VALUES ('pt', 'TITLE', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', AGE_MIN, AGE_MAX, 'CATEGORY');


# ════════════════════════════════════════════════════════════════
# PORTUGUESE SONGS (20)
# ════════════════════════════════════════════════════════════════

# ── PT SONG 1: Sapo Cururu ─────────────────────────────────────
# PASTE THIS PROMPT INTO CLAUDE:
"""
You are a Brazilian Portuguese children's music and education expert.

Generate a complete song entry for "Sapo Cururu" for a database used by a Brazilian parent
who plays guitar (intermediate level, comfortable with barre chords) singing with their 2-year-old daughter.

Use exactly these labels and sections:

TITLE: Sapo Cururu

LYRICS:
[Full traditional lyrics, with line breaks between verses. Plain text, no chords here.]

CHORDS:
[The full lyrics again, this time with guitar chord names written above the exact syllable
where each chord change happens. Key: G major. State capo position if needed.
Use only: G, C, D, Em, Am, Bm, A7, D7, E7.
Example format:
G              C
Sapo cururu na beira do rio
D                    G
Quando o sapo canta ó maninha
Do the same for every line of every verse.]

VOCABULARY_TIPS:
🎵 *Sapo Cururu*

📖 *Palavras desta música*
[Each important word or expression. Format: • **palavra** — significado simples + como usar no dia a dia]

🎸 *Dicas para tocar no violão*
[Exactly 3 practical tips for playing this song on guitar with a 2-year-old —
suggest a strumming pattern, tempo, and how to keep her engaged while you play]

🗣️ *Como cantar com ela*
[2–3 tips for the singing and interaction side]

🎮 *Brincadeira junto com a música*
[One specific physical game or activity that goes with this song]

🌱 *O que ela aprende*
[2–3 specific learning outcomes]

YOUTUBE_URL: [Best YouTube URL — Galinha Pintadinha, Palavra Cantada, or similar official channel]
AGE_MIN: 12
AGE_MAX: 72
CATEGORY: classic

Reply entirely in Brazilian Portuguese.
"""
# SQL (run after getting Claude's response):
# INSERT INTO songs (lang, title, lyrics, chords, vocabulary_tips, youtube_url, age_min, age_max, category)
# VALUES ('pt', 'Sapo Cururu', $$PASTE_LYRICS$$, $$PASTE_CHORDS$$, $$PASTE_VOCABULARY_TIPS$$, 'PASTE_URL', 12, 72, 'classic');


# ── PT SONG 2: Borboletinha ────────────────────────────────────
"""
You are a Brazilian Portuguese children's music and education expert.
Generate a complete song entry for "Borboletinha" for a Brazilian guitar-playing parent
(intermediate, barre chords OK) teaching their 2-year-old daughter.

TITLE: Borboletinha
LYRICS: [Full lyrics, plain text, line breaks between verses]
CHORDS: [Full lyrics with chord names above the correct syllable. Key: G major.
Chords: G, C, D, Em, Am, Bm, A7, D7, E7. State capo if used.]
VOCABULARY_TIPS:
🎵 *Borboletinha*
📖 *Palavras desta música* [key words + daily use]
🎸 *Dicas para tocar no violão* [3 tips: strumming pattern, tempo, toddler engagement]
🗣️ *Como cantar com ela* [2–3 tips]
🎮 *Brincadeira junto com a música* [one activity]
🌱 *O que ela aprende* [2–3 outcomes]
YOUTUBE_URL: [best official URL]
AGE_MIN: 12 | AGE_MAX: 72 | CATEGORY: classic
Reply in Brazilian Portuguese.
"""
# SQL: INSERT INTO songs (lang, title, lyrics, chords, vocabulary_tips, youtube_url, age_min, age_max, category)
# VALUES ('pt', 'Borboletinha', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 12, 72, 'classic');


# ── PT SONGS 3–20: use this template, changing only the song details ──────────
# For each remaining PT song, paste this template and fill in the bracketed parts:
"""
You are a Brazilian Portuguese children's music and education expert.
Generate a complete song entry for "[SONG TITLE]" for a Brazilian guitar-playing parent
(intermediate, barre chords OK) teaching their 2-year-old daughter.

TITLE: [SONG TITLE]
LYRICS: [Full lyrics, plain text, line breaks between verses]
CHORDS: [Full lyrics with chord names above the correct syllable. Key: G major.
Chords: G, C, D, Em, Am, Bm, A7, D7, E7. State capo if needed.]
VOCABULARY_TIPS:
🎵 *[SONG TITLE]*
📖 *Palavras desta música* [[specific vocabulary focus for this song]]
🎸 *Dicas para tocar no violão* [3 tips: strumming pattern, tempo, toddler engagement]
🗣️ *Como cantar com ela* [2–3 tips]
🎮 *Brincadeira junto com a música* [[specific activity for this song]]
🌱 *O que ela aprende* [2–3 outcomes]
YOUTUBE_URL: [best official URL]
AGE_MIN: [X] | AGE_MAX: [X] | CATEGORY: [classic/lullaby/movement/educational]
Reply in Brazilian Portuguese.
"""

# PT SONG 3: "Atirei o Pau no Gato" | AGE_MIN:24 AGE_MAX:72 | classic
# Extra instruction: include note about how to explain the song's subject to a toddler
# SQL: VALUES ('pt', 'Atirei o Pau no Gato', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 24, 72, 'classic');

# PT SONG 4: "A Barata Diz que Tem" | AGE_MIN:18 AGE_MAX:60 | classic
# SQL: VALUES ('pt', 'A Barata Diz que Tem', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 18, 60, 'classic');

# PT SONG 5: "Fui ao Mercado" | AGE_MIN:24 AGE_MAX:72 | classic
# Extra: focus vocab on food words and counting
# SQL: VALUES ('pt', 'Fui ao Mercado', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 24, 72, 'classic');

# PT SONG 6: "Parabéns pra Você" | AGE_MIN:12 AGE_MAX:120 | classic
# Extra: include a simpler 2-chord version (G and D) alongside the full version
# SQL: VALUES ('pt', 'Parabéns pra Você', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 12, 120, 'classic');

# PT SONG 7: "O Pato" (Vinícius de Moraes) | AGE_MIN:24 AGE_MAX:72 | classic
# Extra: bossa/samba feel — suggest a simplified strumming adaptation for intermediate player
# SQL: VALUES ('pt', 'O Pato', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 24, 72, 'classic');

# PT SONG 8: "Ciranda Cirandinha" | AGE_MIN:24 AGE_MAX:72 | classic
# Extra: circle game instructions adapted for 2 players (parent + toddler)
# SQL: VALUES ('pt', 'Ciranda Cirandinha', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 24, 72, 'classic');

# PT SONG 9: "Um Dois Feijão com Arroz" | AGE_MIN:18 AGE_MAX:60 | educational
# Extra: if mostly spoken, suggest a simple G-D vamp to strum underneath
# SQL: VALUES ('pt', 'Um Dois Feijão com Arroz', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 18, 60, 'educational');

# PT SONG 10: "Uni Duni Tê" | AGE_MIN:18 AGE_MAX:72 | classic
# Extra: counting-out game instructions for 2 players
# SQL: VALUES ('pt', 'Uni Duni Tê', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 18, 72, 'classic');

# PT SONG 11: "O Cravo e a Rosa" | AGE_MIN:36 AGE_MAX:84 | classic
# Focus: flower and nature vocabulary
# SQL: VALUES ('pt', 'O Cravo e a Rosa', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 36, 84, 'classic');

# PT SONG 12: "Carneirinho, Carneirão" | AGE_MIN:0 AGE_MAX:48 | lullaby
# Extra: suggest fingerpicking/arpeggio pattern for lullaby
# SQL: VALUES ('pt', 'Carneirinho, Carneirão', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 0, 48, 'lullaby');

# PT SONG 13: "Nana Neném" | AGE_MIN:0 AGE_MAX:36 | lullaby
# Extra: gentle fingerpicking, very slow tempo
# SQL: VALUES ('pt', 'Nana Neném', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 0, 36, 'lullaby');

# PT SONG 14: "Se Essa Rua Fosse Minha" | AGE_MIN:24 AGE_MAX:84 | classic
# Focus: home, street, city vocabulary
# SQL: VALUES ('pt', 'Se Essa Rua Fosse Minha', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 24, 84, 'classic');

# PT SONG 15: "Capelinha de Melão" | AGE_MIN:24 AGE_MAX:72 | classic
# SQL: VALUES ('pt', 'Capelinha de Melão', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 24, 72, 'classic');

# PT SONG 16: "A Casa" (Vinícius de Moraes) | AGE_MIN:36 AGE_MAX:84 | classic
# Extra: bouncy strumming to match the absurd humor of the song
# SQL: VALUES ('pt', 'A Casa', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 36, 84, 'classic');

# PT SONG 17: "Escravos de Jó" | AGE_MIN:36 AGE_MAX:84 | classic
# Extra: object-passing game for 2 players; when to set guitar down
# SQL: VALUES ('pt', 'Escravos de Jó', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 36, 84, 'classic');

# PT SONG 18: "Pirulito que Bate Bate" | AGE_MIN:18 AGE_MAX:60 | movement
# Focus: body movement vocabulary; upbeat strumming
# SQL: VALUES ('pt', 'Pirulito que Bate Bate', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 18, 60, 'movement');

# PT SONG 19: "Alecrim Dourado" | AGE_MIN:30 AGE_MAX:84 | classic
# SQL: VALUES ('pt', 'Alecrim Dourado', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 30, 84, 'classic');

# PT SONG 20: Best Palavra Cantada song for a 2-year-old (Claude picks — state why)
# AGE_MIN:18 AGE_MAX:72 | movement
# SQL: VALUES ('pt', 'REPLACE_WITH_CHOSEN_TITLE', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 18, 72, 'movement');


# ════════════════════════════════════════════════════════════════
# ENGLISH SONGS (15)
# ════════════════════════════════════════════════════════════════

# ── EN SONG 1: Twinkle Twinkle Little Star ─────────────────────
"""
You are a children's English music and education expert helping a Brazilian parent
who plays guitar (intermediate, barre chords OK) teach English to their 2-year-old daughter.

Generate a complete song entry for "Twinkle Twinkle Little Star".

TITLE: Twinkle Twinkle Little Star
LYRICS: [Full lyrics, plain text, line breaks between verses]
CHORDS: [Full lyrics with chord names above the exact syllable where each chord changes.
Key: G major. Chords: G, C, D, Em, Am, D7. State capo if used.
Write chord names directly above the correct syllable for every line.]
VOCABULARY_TIPS:
🎵 *Twinkle Twinkle Little Star*
📖 *Words in this song* [each key word: **word** — simple definition + how to use at home]
🎸 *Guitar tips* [3 tips: strumming pattern, tempo, how to involve the toddler while playing]
🗣️ *How to sing it with her* [2–3 tips for a non-native English speaking parent]
🎮 *Activity with the song* [one physical activity or game]
🌱 *What she learns* [2–3 specific learning outcomes]
YOUTUBE_URL: [best Cocomelon or Super Simple Songs URL]
AGE_MIN: 6 | AGE_MAX: 72 | CATEGORY: classic
Reply in English. Keep vocabulary simple for a non-native speaker.
"""
# SQL: INSERT INTO songs (lang, title, lyrics, chords, vocabulary_tips, youtube_url, age_min, age_max, category)
# VALUES ('en', 'Twinkle Twinkle Little Star', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 6, 72, 'classic');


# ── EN SONGS 2–15: use this template for each remaining English song ──────────
"""
You are a children's English music and education expert helping a Brazilian guitar-playing parent
(intermediate, barre chords OK) teach English to their 2-year-old daughter.

Generate a complete song entry for "[SONG TITLE]".

TITLE: [SONG TITLE]
LYRICS: [Full lyrics, plain text, line breaks between verses]
CHORDS: [Full lyrics with chord names above the correct syllable. Key: G major.
Chords: G, C, D, Em, Am, Bm, A7, D7, E7. State capo if used.]
VOCABULARY_TIPS:
🎵 *[SONG TITLE]*
📖 *Words in this song* [[specific vocabulary focus]]
🎸 *Guitar tips* [3 tips: strumming pattern, tempo, toddler engagement]
🗣️ *How to sing it with her* [2–3 tips for a non-native English speaking parent]
🎮 *Activity with the song* [[specific activity for this song]]
🌱 *What she learns* [2–3 outcomes]
YOUTUBE_URL: [best Cocomelon or Super Simple Songs URL]
AGE_MIN: [X] | AGE_MAX: [X] | CATEGORY: [classic/movement/educational/lullaby/phonics]
Reply in English.
"""

# EN SONG 2: "Wheels on the Bus" | AGE_MIN:12 AGE_MAX:60 | movement
# Focus: vehicle/transport vocabulary and action words; include all main verses (wheels, wipers, horn, babies, driver)
# SQL: VALUES ('en', 'Wheels on the Bus', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 12, 60, 'movement');

# EN SONG 3: "Old MacDonald Had a Farm" | AGE_MIN:12 AGE_MAX:72 | educational
# Focus: animal names and sounds
# SQL: VALUES ('en', 'Old MacDonald Had a Farm', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 12, 72, 'educational');

# EN SONG 4: "Head Shoulders Knees and Toes" | AGE_MIN:12 AGE_MAX:60 | educational
# Focus: body parts. Note: start slow on guitar, speed up over time
# SQL: VALUES ('en', 'Head Shoulders Knees and Toes', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 12, 60, 'educational');

# EN SONG 5: "If You're Happy and You Know It" | AGE_MIN:12 AGE_MAX:60 | movement
# Focus: emotions and action words
# SQL: VALUES ('en', 'If You''re Happy and You Know It', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 12, 60, 'movement');

# EN SONG 6: "Itsy Bitsy Spider" | AGE_MIN:12 AGE_MAX:60 | classic
# Focus: nature vocabulary; explain finger play while strumming
# SQL: VALUES ('en', 'Itsy Bitsy Spider', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 12, 60, 'classic');

# EN SONG 7: "Row Row Row Your Boat" | AGE_MIN:6 AGE_MAX:60 | classic
# Focus: water/nature vocabulary; mention it can be sung as a round
# SQL: VALUES ('en', 'Row Row Row Your Boat', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 6, 60, 'classic');

# EN SONG 8: "ABC Song" | AGE_MIN:18 AGE_MAX:72 | phonics
# Note: shares melody with Twinkle Twinkle — same chords
# Focus: introducing English alphabet to a Portuguese-dominant child; pronunciation differences
# SQL: VALUES ('en', 'ABC Song', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 18, 72, 'phonics');

# EN SONG 9: "Five Little Ducks" | AGE_MIN:18 AGE_MAX:60 | educational
# Focus: counting down, number vocabulary
# SQL: VALUES ('en', 'Five Little Ducks', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 18, 60, 'educational');

# EN SONG 10: "Baa Baa Black Sheep" | AGE_MIN:12 AGE_MAX:60 | classic
# Note: shares melody family with Twinkle/ABC — same chords
# Focus: colors and everyday objects
# SQL: VALUES ('en', 'Baa Baa Black Sheep', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 12, 60, 'classic');

# EN SONG 11: "You Are My Sunshine" | AGE_MIN:0 AGE_MAX:84 | lullaby
# Extra: suggest gentle fingerpicking or slow strumming; great for bedtime bonding
# SQL: VALUES ('en', 'You Are My Sunshine', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 0, 84, 'lullaby');

# EN SONG 12: "Rain Rain Go Away" | AGE_MIN:18 AGE_MAX:60 | classic
# Focus: weather vocabulary
# SQL: VALUES ('en', 'Rain Rain Go Away', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 18, 60, 'classic');

# EN SONG 13: "Five Little Monkeys Jumping on the Bed" | AGE_MIN:18 AGE_MAX:60 | movement
# Focus: numbers, counting down, fun repetition
# SQL: VALUES ('en', 'Five Little Monkeys Jumping on the Bed', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 18, 60, 'movement');

# EN SONG 14: "The Hokey Pokey" | AGE_MIN:24 AGE_MAX:72 | movement
# Focus: body parts, direction words (in, out, around)
# Extra: suggest when to set guitar down to do the actions
# SQL: VALUES ('en', 'The Hokey Pokey', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 24, 72, 'movement');

# EN SONG 15: "Hickory Dickory Dock" | AGE_MIN:18 AGE_MAX:60 | classic
# Focus: time/clock vocabulary and animal words
# SQL: VALUES ('en', 'Hickory Dickory Dock', $$LYRICS$$, $$CHORDS$$, $$VOCABULARY_TIPS$$, 'URL', 18, 60, 'classic');


# ════════════════════════════════════════════════════════════════
# PART 2 — DAILY TIPS POOL (365 tips, 13 batches)
# ════════════════════════════════════════════════════════════════
# Return ONLY valid JSON — no markdown fences, no preamble, nothing before or after the array.

# ── BATCH 1 (Tips 1–30) ───────────────────────────────────────
"""
You are an English teacher for a Brazilian Portuguese-speaking parent
learning English and teaching it to their 2-year-old daughter.

Generate exactly 30 daily English tips as a JSON array.
Stored in a database, served one per day in rotation.
Each tip: practical word or expression for daily home life with a toddler.

Return ONLY valid JSON, no markdown fences, no preamble:

[
  {
    "tip_number": 1,
    "word": "daylight",
    "definition": "The natural light we have during the day, when the sun is up.",
    "example_1": "Let's play outside while there's still daylight!",
    "example_2": "I try to finish my errands in daylight.",
    "toddler_tip": "Point to the window in the morning and say 'Look, daylight! Time to wake up!' to connect the word to her routine."
  }
]

Tips 1–30. Themes: morning routine (5), outdoor/nature (5), emotions (5),
mealtime (5), playtime (5), bedtime (5), general home (5).
No repeated words. Simple definitions. Natural example sentences.
"""
# SQL: INSERT INTO daily_tips (lang, tip_number, word, definition, example_1, example_2, toddler_tip)
# VALUES ('en', 1, '...', '...', '...', '...', '...'), ... ON CONFLICT (lang, tip_number) DO NOTHING;

# ── BATCH 2 (Tips 31–60) ──────────────────────────────────────
"""
Same rules as Batch 1. Return ONLY valid JSON. Tips 31–60. No repeated words from previous batches.
Themes: hygiene/bath (5), clothing (5), animals (5), body parts (5),
weather (5), colors/shapes (5), movement/exercise (5).
"""

# ── BATCH 3 (Tips 61–90) ──────────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Tips 61–90. No repeated words.
Themes: garden/plants (5), kitchen tools (5), vehicles (5), advanced feelings (5),
chores (5), books/reading (5), social words like 'excuse me' 'take turns' 'share' (5).
"""

# ── BATCH 4 (Tips 91–120) ─────────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Tips 91–120. No repeated words.
Themes: textures/sensory (5), sounds (5), family words (5), celebrations (5),
health/body (5), travel/outings (5), imaginative play (5).
"""

# ── BATCH 5 (Tips 121–150) ────────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Tips 121–150. No repeated words.
Themes: expressions parents say constantly — 'hold on' 'almost there' 'good job'
'be gentle' 'careful' 'let's go' 'come here' 'well done' 'in a minute' (10),
question words in real context (5), praise words (5), transition phrases (10).
"""

# ── BATCH 6 (Tips 151–180) ────────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Tips 151–180. No repeated words.
Themes: seasons and weather in detail (10), cooking/baking with kids (10), art and craft words (10).
"""

# ── BATCH 7 (Tips 181–210) ────────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Tips 181–210. No repeated words.
Themes: music and dance (10), numbers in real context (10), opposites (10).
"""

# ── BATCH 8 (Tips 211–240) ────────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Tips 211–240. No repeated words.
Themes: prepositions in real use — under, beside, through, around (10),
time words — soon, later, yesterday, tomorrow (10),
size and quantity — tiny, enormous, a little bit, almost all (10).
"""

# ── BATCH 9 (Tips 241–270) ────────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Tips 241–270. No repeated words.
Themes: nature walk vocabulary (10), supermarket and shopping (10), doctor and health (10).
"""

# ── BATCH 10 (Tips 271–300) ───────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Tips 271–300. No repeated words.
Themes: kindness and social-emotional language (10), problem-solving words (10),
celebrations and special occasions (10).
"""

# ── BATCH 11 (Tips 301–330) ───────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Tips 301–330. No repeated words.
Themes: simplified common idioms — 'keep an eye on' 'piece of cake'
'hang on' 'hold your horses' 'under the weather' (10),
everyday verbs in toddler context (10), home and tools vocabulary (10).
"""

# ── BATCH 12 (Tips 331–360) ───────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Tips 331–360. No repeated words.
Themes: feelings and empathy language (10), imagination and storytelling words (10),
school readiness — share, listen, wait your turn, raise your hand (10).
"""

# ── BATCH 13 (Tips 361–365) ───────────────────────────────────
"""
Same rules. Return ONLY valid JSON. Exactly 5 tips, tip_number 361 to 365.
Theme: 5 emotionally meaningful milestone expressions for a parent teaching their child English.
Examples: 'I'm proud of you', 'We did it together', 'You're getting so big'.
"""


# ════════════════════════════════════════════════════════════════
# PART 3 — BOT COMMANDS TO ADD (next dev session)
# ════════════════════════════════════════════════════════════════
# /musica         — today's song (rotates daily, alternates PT/EN)
# /musica pt      — random Portuguese song
# /musica en      — random English song
# /musica cifra   — today's song WITH guitar chords
# /musica lista   — browse all songs as buttons
#
# Daily tip: replace API call with:
#   SELECT * FROM daily_tips
#   WHERE lang = 'en'
#   AND tip_number = (EXTRACT(DOY FROM NOW())::int % total_count) + 1
#   → zero API cost, instant, consistent
