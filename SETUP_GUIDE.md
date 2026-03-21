# 🇧🇷→🇬🇧 English Learning Bot — Setup Guide

A Telegram bot that sends you daily English tips and lets you chat to learn English,
built for a Brazilian parent teaching their toddler. Powered by Claude AI.

---

## What you'll need (all free or very cheap)

| Thing | Cost | Where to get it |
|---|---|---|
| Telegram account | Free | You already have it ✅ |
| Telegram Bot Token | Free | @BotFather on Telegram |
| Anthropic API key | ~$1–3/month | console.anthropic.com |
| A server | Free tier available | Railway, Render, or a VPS |
| OpenAI key (voice only) | Tiny — cents/month | platform.openai.com |

---

## Step 1 — Create your Telegram bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. *English Helper*) and a username (e.g. `minha_english_bot`)
4. BotFather gives you a token like: `7123456789:AAFxxx...`
5. **Copy and save that token** — you'll need it

---

## Step 2 — Get your Anthropic API key

1. Go to **https://console.anthropic.com**
2. Sign up / log in
3. Go to **API Keys** → **Create Key**
4. Copy and save it (starts with `sk-ant-...`)

> 💡 You can use this same key for all your projects — no need for multiple accounts.

---

## Step 3 — Set up the bot on your computer (or server)

### Install Python (if you don't have it)
Download from https://python.org — version 3.11 or newer.

### Download the bot files
Put `bot.py`, `requirements.txt`, and `.env.example` in a folder, e.g. `english-bot/`

### Install dependencies
```bash
cd english-bot
pip install -r requirements.txt
```

### Create your .env file
```bash
cp .env.example .env
```
Open `.env` and fill in:
```
TELEGRAM_TOKEN=paste_your_token_here
ANTHROPIC_API_KEY=paste_your_key_here
YOUR_CHAT_ID=0        ← leave as 0 for now
DAILY_TIP_HOUR=11     ← 11 UTC = 8am Brazil time
```

---

## Step 4 — First run (to get your Chat ID)

```bash
python bot.py
```

Now open Telegram, find your bot, and send `/start`.

The bot will reply with your **Chat ID** (a number like `123456789`).

1. **Stop the bot** (Ctrl+C)
2. Open `.env` and set `YOUR_CHAT_ID=123456789`
3. Run the bot again: `python bot.py`

✅ Now the daily tips are scheduled!

---

## Step 5 — Enable voice messages (optional but great)

1. Go to **https://platform.openai.com**
2. Sign up and add a small amount of credit (even $5 lasts a very long time)
3. Create an API key
4. Add it to `.env`:
   ```
   OPENAI_API_KEY=sk-...
   ```
5. Restart the bot

Now you can send voice messages in Portuguese and get English replies!

---

## Running 24/7 on a free server

### Option A: Railway (recommended, easiest)
1. Go to **https://railway.app** and sign up with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Push your bot folder to a GitHub repo first
4. Add your environment variables in Railway's dashboard (same as your `.env`)
5. Railway runs it 24/7 for free (within their free tier)

### Option B: Render.com
Similar to Railway. Create a **Background Worker** service.

### Option C: Your own computer
Just run `python bot.py` whenever you want to use it. Daily tips only send while it's running.

---

## Using the bot

| Command | What it does |
|---|---|
| `/start` | Introduction and your chat ID |
| `/tip` | Get a word or expression right now |
| `/reading` | Early reading tips for your daughter |
| `/help` | Show all commands |
| Any text | Chat freely in English or Portuguese |
| 🎙️ Voice message | Speak, get transcribed + English reply |

### Example chats

**You:** *Como se diz quando a criança faz bagunça?*
**Bot:** When your child makes a mess, you can say: "Oh, what a mess! Let's tidy up together." ...

**You:** *What does "daylight" mean?*
**Bot:** *Daylight* means the natural light we have during the day... 🌅

---

## Using one API key for multiple projects

Yes! You use **one Anthropic account** and **one API key** for all your bots/projects.
Just paste the same `ANTHROPIC_API_KEY` in each project's `.env` file.
You're billed by usage (tokens), not by project.

---

## Cost estimate (per month)

| Service | Estimated cost |
|---|---|
| Anthropic (Claude) | ~$1–3 |
| OpenAI (Whisper voice) | < $1 |
| Railway/Render server | Free tier |
| **Total** | **~$2–4/month** |

---

## Next steps / future ideas

- 📖 **Sight words trainer** — bot sends 3 sight words a week as your daughter gets older
- 🔤 **Phonics mode** — learn letter sounds together (great from age 3)
- 🖼️ **Picture flash cards** — bot sends an image + word daily
- 🧠 **Quiz mode** — bot tests you on words from past weeks

---

*Built with ❤️ using Python, python-telegram-bot, and Claude (Anthropic)*
