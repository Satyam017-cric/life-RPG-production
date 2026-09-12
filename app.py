import os
import secrets
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
IS_PRODUCTION = os.getenv("RENDER", "").lower() == "true" or os.getenv("ENV", "").lower() == "production"
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError("SECRET_KEY must be configured in production.")
    SECRET_KEY = "local-dev-secret-change-me"

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATABASE")
if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'life_rpg.db')}"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

CATEGORY_MAP = {
    "coding": ("Intellect", "🧠", "Solve, build, debug"),
    "study": ("Knowledge", "📚", "Learn something useful"),
    "fitness": ("Strength", "💪", "Train body and energy"),
    "mindfulness": ("Focus", "🧘", "Protect attention and calm"),
    "reading": ("Wisdom", "📖", "Grow through ideas"),
    "other": ("Discipline", "⚡", "Build consistency"),
}
DIFFICULTY_REWARDS = {
    "easy": {"xp": 30, "gold": 10},
    "medium": {"xp": 65, "gold": 24},
    "hard": {"xp": 120, "gold": 45},
    "epic": {"xp": 200, "gold": 80},
}
SHOP_ITEMS = [
    ("neon", "Neon Grid", "A high-energy cyber grid for your command deck.", "theme", 150, "🌌"),
    ("ember", "Ember Core", "Warm reactor tones for a relentless streak.", "theme", 250, "🔥"),
    ("aether", "Aether Sky", "A calm atmosphere for deep-work sessions.", "theme", 350, "☁️"),
    ("nova", "Nova Badge", "A profile badge for consistent progress.", "badge", 200, "✨"),
    ("titan", "Titan Badge", "A badge earned by heroic difficulty clears.", "badge", 500, "👑"),
    ("focus", "Focus Badge", "A badge for mindfulness milestones.", "badge", 300, "🎯"),
]


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    gold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity: Mapped[date | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    theme: Mapped[str] = mapped_column(String(32), default="default", nullable=False)

    attributes: Mapped["Attributes"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    quests: Mapped[list["Quest"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    activities: Mapped[list["ActivityLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    inventory: Mapped[list["Inventory"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Attributes(Base):
    __tablename__ = "attributes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    intellect: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    knowledge: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    strength: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    focus: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    wisdom: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    discipline: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    user: Mapped[User] = relationship(back_populates="attributes")


class Quest(Base):
    __tablename__ = "quests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    gold_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship(back_populates="quests")


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quest_id: Mapped[int | None] = mapped_column(ForeignKey("quests.id", ondelete="SET NULL"), nullable=True)
    activity_date: Mapped[date] = mapped_column(nullable=False, index=True)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gold_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    user: Mapped[User] = relationship(back_populates="activities")


class ShopItem(Base):
    __tablename__ = "shop_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(250), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    icon: Mapped[str] = mapped_column(String(8), nullable=False)


class Inventory(Base):
    __tablename__ = "inventory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("shop_items.id", ondelete="CASCADE"), nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    user: Mapped[User] = relationship(back_populates="inventory")


Base.metadata.create_all(engine)


def db():
    if "db" not in g:
        g.db = Session(engine)
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    s = g.pop("db", None)
    if s is not None:
        s.close()


def seed_shop():
    s = db()
    if s.scalar(select(func.count(ShopItem.id))) == 0:
        for row in SHOP_ITEMS:
            s.add(ShopItem(item_key=row[0], name=row[1], description=row[2], item_type=row[3], price=row[4], icon=row[5]))
        s.commit()


with app.app_context():
    seed_shop()


def level_threshold(level: int) -> int:
    return 0 if level <= 1 else int(100 * ((level - 1) ** 1.55))


def calculate_level(xp: int) -> int:
    level = 1
    while xp >= level_threshold(level + 1):
        level += 1
    return level


def level_progress(xp: int, level: int):
    current_floor = level_threshold(level)
    next_floor = level_threshold(level + 1)
    needed = max(1, next_floor - current_floor)
    current = max(0, xp - current_floor)
    return current, needed, min(100, round(current / needed * 100))


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.context_processor
def inject_helpers():
    return {
        "csrf_token": get_csrf_token(),
        "level_threshold": level_threshold,
        "level_progress": level_progress,
        "category_map": CATEGORY_MAP,
        "difficulty_rewards": DIFFICULTY_REWARDS,
    }


def require_csrf():
    expected = session.get("csrf_token")
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        abort(400, description="Invalid security token. Refresh the page and try again.")


@app.before_request
def load_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        g.user = db().get(User, user_id)
    if request.method == "POST" and request.endpoint not in {"static", "health"}:
        require_csrf()


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Log in to continue your adventure.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def user_attrs(user: User):
    if not user.attributes:
        user.attributes = Attributes(user_id=user.id)
        db().commit()
    return user.attributes


def refresh_user():
    db().refresh(g.user)


def update_progress(user: User, xp_gain: int, gold_gain: int):
    today = date.today()
    before_level = user.level
    if user.last_activity == today:
        new_streak = user.streak
    elif user.last_activity == today - timedelta(days=1):
        new_streak = user.streak + 1
    else:
        new_streak = 1
    user.xp += xp_gain
    user.gold += gold_gain
    user.streak = new_streak
    user.last_activity = today
    user.level = calculate_level(user.xp)
    return before_level, user.level, user.streak


@app.route("/")
def index():
    if g.user:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        errors = []
        if not 2 <= len(name) <= 80:
            errors.append("Name must be between 2 and 80 characters.")
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must contain at least 8 characters.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("signup.html")
        s = db()
        user = User(name=name, email=email, password_hash=generate_password_hash(password))
        user.attributes = Attributes()
        s.add(user)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            flash("An account with that email already exists.", "danger")
            return render_template("signup.html")
        session.clear()
        session["user_id"] = user.id
        get_csrf_token()
        flash("Character created. Your first quest awaits.", "success")
        return redirect(url_for("dashboard"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db().scalar(select(User).where(User.email == email))
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
        session.clear()
        session["user_id"] = user.id
        get_csrf_token()
        flash("Welcome back, hero.", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.post("/logout")
@login_required
def logout():
    session.clear()
    flash("You have logged out safely.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    s = db()
    quests = s.scalars(select(Quest).where(Quest.user_id == g.user.id).order_by(Quest.status.asc(), Quest.created_at.desc()).limit(8)).all()
    activities = s.execute(
        select(ActivityLog.activity_date, func.sum(ActivityLog.xp_earned).label("xp"), func.sum(ActivityLog.gold_earned).label("gold"))
        .where(ActivityLog.user_id == g.user.id)
        .group_by(ActivityLog.activity_date)
        .order_by(ActivityLog.activity_date.desc())
        .limit(7)
    ).all()
    current, needed, pct = level_progress(g.user.xp, g.user.level)
    completed_count = s.scalar(select(func.count(Quest.id)).where(Quest.user_id == g.user.id, Quest.status == "completed")) or 0
    pending_count = s.scalar(select(func.count(Quest.id)).where(Quest.user_id == g.user.id, Quest.status == "pending")) or 0
    return render_template("dashboard.html", quests=quests, attrs=user_attrs(g.user), activities=activities, xp_current=current, xp_needed=needed, xp_pct=pct, completed_count=completed_count, pending_count=pending_count)


@app.route("/quests")
@login_required
def quests():
    rows = db().scalars(select(Quest).where(Quest.user_id == g.user.id).order_by(Quest.status.asc(), Quest.created_at.desc())).all()
    return render_template("quests.html", quests=rows)


@app.post("/quests/create")
@login_required
def create_quest():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "other")
    difficulty = request.form.get("difficulty", "easy")
    if not title:
        flash("Quest title cannot be empty.", "danger")
        return redirect(url_for("quests"))
    if category not in CATEGORY_MAP:
        category = "other"
    if difficulty not in DIFFICULTY_REWARDS:
        difficulty = "easy"
    reward = DIFFICULTY_REWARDS[difficulty]
    q = Quest(user_id=g.user.id, title=title[:140], description=description[:500], category=category, difficulty=difficulty, xp_reward=reward["xp"], gold_reward=reward["gold"])
    db().add(q)
    db().commit()
    flash("Quest added to your mission board.", "success")
    return redirect(url_for("quests"))


@app.post("/quests/<int:quest_id>/complete")
@login_required
def complete_quest(quest_id):
    s = db()
    q = s.scalar(select(Quest).where(Quest.id == quest_id, Quest.user_id == g.user.id))
    if not q:
        abort(404)
    if q.status == "completed":
        flash("That quest is already complete.", "warning")
        return redirect(url_for("quests"))
    before, after, streak = update_progress(g.user, q.xp_reward, q.gold_reward)
    q.status = "completed"
    q.completed_at = datetime.now(timezone.utc)
    attr_name = {"coding": "intellect", "study": "knowledge", "fitness": "strength", "mindfulness": "focus", "reading": "wisdom", "other": "discipline"}[q.category]
    setattr(user_attrs(g.user), attr_name, getattr(user_attrs(g.user), attr_name) + max(1, q.xp_reward // 30))
    s.add(ActivityLog(user_id=g.user.id, quest_id=q.id, activity_date=date.today(), xp_earned=q.xp_reward, gold_earned=q.gold_reward, category=q.category))
    s.commit()
    payload = {"ok": True, "xp_gained": q.xp_reward, "gold_gained": q.gold_reward, "new_level": after, "level_up": after > before, "streak": streak, "new_xp": g.user.xp}
    if request.headers.get("Accept", "").startswith("application/json"):
        return jsonify(payload)
    if after > before:
        flash(f"LEVEL UP! You reached level {after}.", "success")
    else:
        flash(f"Quest complete! +{q.xp_reward} XP · +{q.gold_reward} Gold.", "success")
    return redirect(url_for("quests"))


@app.route("/quests/<int:quest_id>/edit", methods=["GET", "POST"])
@login_required
def edit_quest(quest_id):
    s = db()
    q = s.scalar(select(Quest).where(Quest.id == quest_id, Quest.user_id == g.user.id))
    if not q:
        abort(404)
    if q.status == "completed":
        flash("Completed quests are locked to preserve the activity record.", "warning")
        return redirect(url_for("quests"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "other")
        difficulty = request.form.get("difficulty", "easy")
        description = request.form.get("description", "").strip()
        if not title:
            flash("Quest title cannot be empty.", "danger")
            return render_template("edit_quest.html", quest=q)
        if category not in CATEGORY_MAP:
            category = "other"
        if difficulty not in DIFFICULTY_REWARDS:
            difficulty = "easy"
        reward = DIFFICULTY_REWARDS[difficulty]
        q.title, q.description, q.category, q.difficulty = title[:140], description[:500], category, difficulty
        q.xp_reward, q.gold_reward = reward["xp"], reward["gold"]
        s.commit()
        flash("Quest updated.", "success")
        return redirect(url_for("quests"))
    return render_template("edit_quest.html", quest=q)


@app.post("/quests/<int:quest_id>/delete")
@login_required
def delete_quest(quest_id):
    s = db()
    q = s.scalar(select(Quest).where(Quest.id == quest_id, Quest.user_id == g.user.id))
    if not q:
        abort(404)
    s.delete(q)
    s.commit()
    flash("Quest removed from your mission board.", "success")
    return redirect(url_for("quests"))


@app.route("/character")
@login_required
def character():
    inventory = db().scalars(select(ShopItem).join(Inventory, Inventory.item_id == ShopItem.id).where(Inventory.user_id == g.user.id).order_by(ShopItem.name)).all()
    return render_template("character.html", attrs=user_attrs(g.user), inventory=inventory)


@app.route("/shop")
@login_required
def shop():
    items = db().scalars(select(ShopItem).order_by(ShopItem.price)).all()
    owned_ids = set(db().scalars(select(Inventory.item_id).where(Inventory.user_id == g.user.id)).all())
    return render_template("shop.html", items=items, owned_ids=owned_ids)


@app.post("/shop/<int:item_id>/buy")
@login_required
def buy_item(item_id):
    s = db()
    item = s.get(ShopItem, item_id)
    if not item:
        abort(404)
    if s.scalar(select(Inventory.id).where(Inventory.user_id == g.user.id, Inventory.item_id == item.id)):
        flash("You already own this item.", "warning")
        return redirect(url_for("shop"))
    if g.user.gold < item.price:
        flash("Not enough Gold for this purchase.", "danger")
        return redirect(url_for("shop"))
    g.user.gold -= item.price
    s.add(Inventory(user_id=g.user.id, item_id=item.id))
    if item.item_type == "theme":
        g.user.theme = item.item_key
    s.commit()
    flash(f"Unlocked {item.name}.", "success")
    return redirect(url_for("shop"))


@app.post("/theme/reset")
@login_required
def reset_theme():
    g.user.theme = "default"
    db().commit()
    flash("Default theme restored.", "success")
    return redirect(url_for("character"))


@app.route("/history")
@login_required
def history():
    logs = db().scalars(select(ActivityLog).where(ActivityLog.user_id == g.user.id).order_by(ActivityLog.activity_date.desc(), ActivityLog.id.desc()).limit(100)).all()
    return render_template("history.html", logs=logs)


@app.route("/about")
def about():
    return render_template("about.html")


@app.get("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "favicon.svg")


@app.get("/health")
def health():
    try:
        db().execute(select(func.count(User.id))).scalar_one()
        return jsonify({"status": "ok", "database": "connected"})
    except Exception:
        return jsonify({"status": "error", "database": "unavailable"}), 503


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=getattr(error, "description", "Bad request.")), 400


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The route or quest you requested was not found."), 404


@app.errorhandler(500)
def server_error(_error):
    return render_template("error.html", code=500, message="The server encountered an unexpected error. Please try again."), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=not IS_PRODUCTION)
