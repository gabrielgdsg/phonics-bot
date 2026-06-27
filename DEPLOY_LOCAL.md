# 🖥️ Deploy to GERALDO-PC (192.168.1.170)
# Same pattern as Kapiva — Docker + nginx

# ═══════════════════════════════════════════════════════════════
# STEP 1 — Copy project to GERALDO-PC
# ═══════════════════════════════════════════════════════════════

# From your Linux machine (where you have the project):
rsync -avz ~/phonics_bot/ user@192.168.1.170:~/phonics_bot/

# Or via SSH:
# ssh user@192.168.1.170
# Then git clone your GitHub repo there


# ═══════════════════════════════════════════════════════════════
# STEP 2 — Create .env on GERALDO-PC
# ═══════════════════════════════════════════════════════════════

# SSH into GERALDO-PC:
ssh user@192.168.1.170
cd ~/phonics_bot

cp .env.example .env
nano .env
# Fill in: TELEGRAM_TOKEN, ANTHROPIC_API_KEY, DB_PASSWORD, OPENAI_API_KEY
# DATABASE_URL should be: postgresql://phonics:YOURPASSWORD@db:5432/phonics


# ═══════════════════════════════════════════════════════════════
# STEP 3 — Build and start containers
# ═══════════════════════════════════════════════════════════════

cd ~/phonics_bot
docker compose up -d --build

# Check they're running:
docker compose ps

# Watch bot logs:
docker compose logs -f bot

# Watch DB logs:
docker compose logs -f db


# ═══════════════════════════════════════════════════════════════
# STEP 4 — Run the schema (first time only)
# ═══════════════════════════════════════════════════════════════

# The schema.sql runs automatically on first DB start (via docker-entrypoint-initdb.d)
# If you need to run it manually:
docker compose exec db psql -U phonics -d phonics -f /docker-entrypoint-initdb.d/schema.sql

# Verify tables were created:
docker compose exec db psql -U phonics -d phonics -c "\dt"


# ═══════════════════════════════════════════════════════════════
# STEP 5 — Populate the DB with lesson content
# ═══════════════════════════════════════════════════════════════

# Connect to the DB from your local machine:
psql postgresql://phonics:YOURPASSWORD@192.168.1.170:5433/phonics

# Or from inside GERALDO-PC:
docker compose exec db psql -U phonics -d phonics

# Then paste the INSERT statements from PT_COURSE_GENERATION.md
# one lesson at a time as you generate them


# ═══════════════════════════════════════════════════════════════
# STEP 6 — Nginx setup (same as Kapiva)
# ═══════════════════════════════════════════════════════════════

# On GERALDO-PC (assuming nginx is already installed from Kapiva):
sudo cp ~/phonics_bot/nginx.conf /etc/nginx/sites-available/phonics-bot
sudo ln -s /etc/nginx/sites-available/phonics-bot /etc/nginx/sites-enabled/
sudo nginx -t        # test config
sudo systemctl reload nginx


# ═══════════════════════════════════════════════════════════════
# STEP 7 — Keep bot running after GERALDO-PC restarts
# ═══════════════════════════════════════════════════════════════

# Docker Compose already handles this via restart: unless-stopped
# But make sure Docker starts on boot:
sudo systemctl enable docker

# To verify after a reboot:
docker compose ps   # should show both containers as "Up"


# ═══════════════════════════════════════════════════════════════
# USEFUL COMMANDS
# ═══════════════════════════════════════════════════════════════

# Restart just the bot (after code changes):
docker compose restart bot

# Rebuild after code changes:
docker compose up -d --build bot

# Stop everything:
docker compose down

# Stop and wipe DB (careful!):
docker compose down -v

# See bot logs live:
docker compose logs -f bot

# Connect to DB:
docker compose exec db psql -U phonics -d phonics

# Check how many lessons are in the DB:
# docker compose exec db psql -U phonics -d phonics -c "SELECT lang, COUNT(*) FROM lessons GROUP BY lang;"

# Check how many tips are in the DB:
# docker compose exec db psql -U phonics -d phonics -c "SELECT COUNT(*) FROM daily_tips;"


# ═══════════════════════════════════════════════════════════════
# MIGRATING FROM RAILWAY
# ═══════════════════════════════════════════════════════════════

# When ready to move from Railway to local:
# 1. Start local containers and verify they work
# 2. Stop the Railway deployment (or delete the service)
# 3. The bot will now run from GERALDO-PC
# 4. Make sure GERALDO-PC doesn't sleep (disable sleep in Windows/Linux power settings)

# NOTE: The bot uses polling (not webhooks) so it doesn't need
# to be reachable from the internet — it reaches out to Telegram,
# not the other way around. No port forwarding needed for polling mode.


# ═══════════════════════════════════════════════════════════════
# REQUIREMENTS UPDATE
# ═══════════════════════════════════════════════════════════════

# Add asyncpg to requirements.txt for PostgreSQL support:
# asyncpg==0.29.0
# (Already added in the updated requirements.txt)
