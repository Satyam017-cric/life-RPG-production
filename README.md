# Life RPG — Production-Ready Full-Stack Productivity RPG

Life RPG turns real-world tasks into RPG quests. Completing a quest awards server-calculated XP and Gold, raises a category-specific character attribute, updates a consecutive-day streak, and records an immutable activity entry. Users can spend Gold in a persistent shop to unlock themes and badges.

## Why this version is submission-oriented

- Flask backend with server-side sessions and password hashing.
- CSRF protection on state-changing requests.
- User-scoped quest, inventory, history and character queries.
- Non-linear XP progression (`level_threshold = 100 * (level - 1)^1.55`).
- PostgreSQL-ready persistence using SQLAlchemy; SQLite remains available for local development.
- Gunicorn production server.
- Render Blueprint creates the web service and PostgreSQL database together.
- `/health` endpoint for deployment health checks.
- Responsive, semantic, keyboard-friendly HTML and accessible labels/focus states.
- Completion animation / optimistic-feeling async completion flow.
- No `localStorage` use for primary application data.

## Project structure

```text
life-rpg/
├── app.py
├── requirements.txt
├── Procfile
├── render.yaml
├── .env.example
├── .gitignore
├── README.md
├── templates/
│   ├── base.html
│   ├── landing.html
│   ├── login.html
│   ├── signup.html
│   ├── dashboard.html
│   ├── quests.html
│   ├── edit_quest.html
│   ├── character.html
│   ├── shop.html
│   ├── history.html
│   ├── about.html
│   └── error.html
└── static/
    ├── style.css
    └── app.js
```

## Local Windows setup

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY="use-a-long-random-local-secret"
python app.py
```

Open `http://127.0.0.1:5000`.

Without `DATABASE_URL`, local development uses `life_rpg.db`. That file is intentionally ignored by Git so user data is not committed to the repository.

## Production deployment on Render

Use a **Web Service**, not a Static Site. Render's Flask deployment guide uses `gunicorn app:app`, and Render recommends the service and PostgreSQL database share a region for low-latency private connectivity. See the official Render docs:

- https://render.com/docs/deploy-flask
- https://render.com/docs/postgresql-creating-connecting
- https://render.com/docs/configure-environment-variables

### Blueprint deployment

1. Push this project to a public GitHub repository.
2. In Render, choose **New → Blueprint** and select the repository.
3. Render reads `render.yaml` and creates:
   - the `life-rpg` web service;
   - a `life-rpg-db` PostgreSQL database;
   - `SECRET_KEY` as a generated secret;
   - `DATABASE_URL` linked to the database.
4. Deploy.
5. Open the generated `onrender.com` URL.
6. Check `/health` and confirm `{"status":"ok","database":"connected"}`.

### Manual deployment

Web service values:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --workers 2 --threads 4 --timeout 120 app:app`
- Health check path: `/health`

Add these environment variables in Render:

```text
SECRET_KEY=<long-random-secret>
DATABASE_URL=<Render internal PostgreSQL connection URL>
ENV=production
```

Render documents that environment variables are the correct mechanism for secrets and database URLs, and that a Render service can use its database's internal URL when both services are in the same region.

## Required submission demo (90–180 seconds)

Record one continuous screen capture under 100 MB and host it publicly or in the repository. Suggested sequence:

1. Open the public Life RPG URL.
2. Sign up with a new account.
3. Show the command deck and the initial character stats.
4. Create a quest: `Complete 2 coding problems` (Hard is good for the demo).
5. Complete the quest.
6. Show the reward animation and the updated XP, Gold, Intellect and streak.
7. Complete enough additional quests to trigger a level up, or use a deliberately fast demo sequence with Epic quests.
8. Open Shop and purchase an item.
9. Refresh the page.
10. Show that the quest history, character progression and inventory are still present.

**The demo video itself is the only deliverable this package cannot generate automatically:** it needs your own public screen recording to satisfy the 90–180 second rule.

## Security notes

- Passwords are hashed, never stored as plaintext.
- State-changing requests require a per-session CSRF token.
- Flask sessions are HTTP-only and SameSite=Lax; Secure cookies are enabled in production.
- Queries for user-owned resources are scoped by authenticated user ID.
- Reward amounts are determined on the server.
- Production fails fast if `SECRET_KEY` is missing.
- Never commit `.env`, production connection strings, or generated SQLite databases.

## Final acceptance checklist

Before submitting, verify all of these against the public deployment:

- [ ] GitHub repo is public and contains backend + frontend.
- [ ] At least 3 chronological commits exist.
- [ ] `.env.example` is present.
- [ ] README contains local and deployment setup.
- [ ] Public Render URL loads without a 500.
- [ ] `/health` reports a connected PostgreSQL database.
- [ ] Signup/login/logout works.
- [ ] A user cannot access another user's quests by changing an ID in a URL.
- [ ] Quest create/read/update/delete works.
- [ ] Completion awards XP and Gold only once.
- [ ] Level curve is non-linear.
- [ ] Streak updates from completed activity.
- [ ] Attribute changes match quest category.
- [ ] Shop purchase persists.
- [ ] Refresh preserves character, quest and inventory data.
- [ ] Mobile layout works.
- [ ] Tab/Enter/Space navigation is usable.
- [ ] No browser console errors during the demo path.
- [ ] 90–180 second public demo video is linked.
