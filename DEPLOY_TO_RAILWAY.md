# 🚀 Deploy to Railway — Cursor Task

Please do everything below for me, step by step, without asking unless something is missing.

---

## What we are doing
Deploying this Telegram bot to Railway so it runs 24/7 in the cloud.
The bot is already working locally. We just need to ship it.

---

## Step 1 — Add the Procfile
Create a file called `Procfile` (no extension) in the root of this project with exactly this content:

    worker: python bot.py

---

## Step 2 — Initialize a git repository
Run these commands:

    git init
    git add .
    git commit -m "initial commit — phonics bot"

If git is not installed, tell me.
If there is already a git repo initialized, skip git init and just add + commit.

---

## Step 3 — Check .gitignore is protecting secrets
Verify that `.env` and `progress.json` are listed in `.gitignore`.
If they are not, add them.
Then confirm `.env` is NOT being tracked by git:

    git ls-files .env

If it returns anything, run:

    git rm --cached .env

---

## Step 4 — Tell me what to do on GitHub (you cannot do this part)
Tell me clearly:
1. Go to https://github.com/new
2. Create a new PRIVATE repository called `phonics-bot`
3. Do NOT initialize it with a README (we already have files)
4. Copy the repository URL it gives me (looks like https://github.com/MYNAME/phonics-bot.git)
5. Come back and paste the URL here so you can continue

Wait for me to paste the GitHub URL before continuing.

---

## Step 5 — Push to GitHub
Once I give you the GitHub URL, run:

    git remote add origin PASTE_URL_HERE
    git branch -M main
    git push -u origin main

If it asks for credentials, tell me to set up a GitHub personal access token at:
https://github.com/settings/tokens
(Classic token, with "repo" scope checked)

---

## Step 6 — Tell me what to do on Railway (you cannot do this part either)
Tell me clearly:
1. Go to https://railway.app and sign up with my GitHub account
2. Click "New Project" → "Deploy from GitHub repo"
3. Select the `phonics-bot` repository
4. Click the deployment → go to the "Variables" tab
5. Add each of these variables one by one (I will fill in the values):

   TELEGRAM_TOKEN        = (from @BotFather on Telegram)
   ANTHROPIC_API_KEY     = (from https://console.anthropic.com)
   DAILY_TIP_HOUR        = 11
   DAILY_TIP_MINUTE      = 0
   OPENAI_API_KEY        = (optional — voice + /falar; leave empty if not set up)

   No chat IDs in Railway — each user is registered when they send /start (stored in progress.json).
   progress.json and cache.json (lesson pre-cache) reset on redeploy unless you add a Railway volume.

6. After adding variables, click "Deploy" or it may deploy automatically
7. Go to the "Logs" tab and watch for the line: "Bot running..."
8. If you see that line, it worked!

---

## Step 7 — Verify it works
Tell me to open Telegram and send /start to the bot.
If it replies, deployment was successful.

---

## After everything is done, tell me:
1. ✅ What was completed automatically
2. 👤 What I still need to do manually (and where)
3. 🔄 How to redeploy in the future when I make code changes (just `git push`?)
4. 📋 How to see the bot logs on Railway
