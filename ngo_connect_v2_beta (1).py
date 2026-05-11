import customtkinter as ctk
from customtkinter import CTkScrollableFrame
import pymysql
from tkinter import messagebox
import hashlib
from datetime import datetime, timezone
import re
import datetime

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ============= COLORS =============
COLOR_BG        = "#f8fafc"
COLOR_SIDEBAR   = "#1e293b"
COLOR_ACCENT    = "#2563eb"
COLOR_TEXT      = "#0f172a"
COLOR_TEXT_SEC  = "#64748b"
COLOR_CARD      = "#ffffff"
COLOR_BORDER    = "#e2e8f0"
COLOR_SUCCESS   = "#10b981"
COLOR_WARNING   = "#f59e0b"
COLOR_DANGER    = "#ef4444"
COLOR_LIGHT_BLUE = "#dbeafe"

# ============= PRE-VALIDATED DARPAN IDs =============
# These are sample valid DARPAN IDs that NGOs can use for verification
# Format: State Code (2 letters) / Year (4 digits) / 7-digit unique number
VALID_DARPAN_IDS = {
    "KA/2019/0234567": "Bangalore Trust Foundation",
    "MH/2020/0012345": "Mumbai Social Welfare Society",
    "DL/2018/0567890": "Delhi Community Support",
    "TN/2021/0345678": "Chennai Education Initiative",
    "GJ/2019/0456789": "Ahmedabad Health Foundation",
    "WB/2020/0123456": "Kolkata Women Empowerment",
    "KL/2019/0234568": "Kerala Environmental Alliance",
    "RJ/2021/0567891": "Jaipur Rural Development",
    "UP/2020/0345679": "Lucknow Child Welfare",
    "BR/2019/0123457": "Patna Community Health",
}

def hover(c):
    if not c or not isinstance(c, str) or not c.startswith("#"):
        return c
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join([x*2 for x in c])
    try:
        r = max(0, int(c[0:2], 16) - 20)
        g = max(0, int(c[2:4], 16) - 20)
        b = max(0, int(c[4:6], 16) - 20)
        return f"#{r:02x}{g:02x}{b:02x}"
    except:
        return "#" + c

# ============= FONTS =============
FONT_HERO       = ("Montserrat", 46, "bold")
FONT_TITLE      = ("Montserrat", 22, "bold")
FONT_HEADING    = ("Montserrat", 15, "bold")
FONT_SUBHEADING = ("Montserrat", 12, "bold")
FONT_BODY       = ("Inter", 11)
FONT_SMALL      = ("Inter", 10)

# ============= MYSQL CONFIG =============
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASS = "1983"   # ← Change this to your MySQL password
MYSQL_DB   = "ngoconnect"

CATEGORIES = [
    "Food", "Education", "Health", "Environment", "Shelter",
    "Women & Children", "Elderly Care", "Climate Action",
    "Animal Welfare", "Skill Development"
]

# =============================================================================
# DATABASE LAYER
# =============================================================================

def hash_pw(p):
    return hashlib.sha256(p.encode()).hexdigest()

def db_conn():
    try:
        return pymysql.connect(
            host=MYSQL_HOST, user=MYSQL_USER,
            password=MYSQL_PASS, database=MYSQL_DB,
            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        print(f"[DB] Connection Error: {e}")
        return None

def db_setup():
    """Create tables and auto-migrate missing columns on existing tables."""
    conn = db_conn()
    if not conn:
        print("[DB] Cannot connect — check MYSQL_PASS and that the DB exists.")
        return
    c = conn.cursor()
    try:
        # ── users ──────────────────────────────────────────────────────────
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INT PRIMARY KEY AUTO_INCREMENT,
            email      VARCHAR(120) UNIQUE,
            name       VARCHAR(100),
            phone      VARCHAR(16),
            password   VARCHAR(80),
            role       ENUM('NGO','Volunteer'),
            city       VARCHAR(60),
            skills     TEXT,
            bio        TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reliability_score INT DEFAULT 50,
            ban_until  DATE DEFAULT NULL
        )""")

        # Migration: add skills / bio if they don't exist yet
        for col, typedef in [("skills", "TEXT"), ("bio", "TEXT"), ("reliability_score", "INT DEFAULT 50"), ("ban_until", "DATE DEFAULT NULL")]:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")
            except Exception:
                pass   # column already exists — fine

        # ── ngos ───────────────────────────────────────────────────────────
        c.execute("""
        CREATE TABLE IF NOT EXISTS ngos (
            id          INT PRIMARY KEY AUTO_INCREMENT,
            name        VARCHAR(120) UNIQUE,
            type        VARCHAR(40),
            city        VARCHAR(60),
            description TEXT,
            email       VARCHAR(120),
            phone       VARCHAR(16),
            website     VARCHAR(200),
            darpan_id   VARCHAR(20) UNIQUE NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        for col, typedef in [("website", "VARCHAR(200)"), ("darpan_id", "VARCHAR(20) UNIQUE NOT NULL")]:
            try:
                c.execute(f"ALTER TABLE ngos ADD COLUMN {col} {typedef}")
            except Exception:
                pass

        # ── ngo_members ────────────────────────────────────────────────────
        c.execute("""
        CREATE TABLE IF NOT EXISTS ngo_members (
            id        INT PRIMARY KEY AUTO_INCREMENT,
            ngo_id    INT,
            user_id   INT,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_mem (ngo_id, user_id)
        )""")

        # ── events ─────────────────────────────────────────────────────────
        c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id             INT PRIMARY KEY AUTO_INCREMENT,
            ngo_id         INT,
            title          VARCHAR(200),
            edate          VARCHAR(40),
            etime          VARCHAR(30) DEFAULT '',
            location       VARCHAR(200),
            max_volunteers INT DEFAULT 0,
            category       VARCHAR(40) DEFAULT '',
            description    TEXT,
            requirements   TEXT,
            created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            cancelled      TINYINT(1) DEFAULT 0
        )""")
        for col, typedef in [
            ("etime",          "VARCHAR(30) DEFAULT ''"),
            ("max_volunteers", "INT DEFAULT 0"),
            ("category",       "VARCHAR(40) DEFAULT ''"),
            ("requirements",   "TEXT NULL"),
        ]:
            try:
                c.execute(f"ALTER TABLE events ADD COLUMN {col} {typedef}")
            except Exception:
                pass

        # ── event_participants ─────────────────────────────────────────────
        c.execute("""
        CREATE TABLE IF NOT EXISTS event_participants (
            id          INT PRIMARY KEY AUTO_INCREMENT,
            event_id    INT,
            user_id     INT,
            joined_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            checked_in  TINYINT(1) DEFAULT 0,
            hours_logged FLOAT DEFAULT 0,
            attendance  VARCHAR(20) DEFAULT 'pending',
            UNIQUE KEY uq_part (event_id, user_id)
        )""")
        for col, typedef in [("checked_in",   "TINYINT(1) DEFAULT 0"), ("hours_logged", "FLOAT DEFAULT 0"), ("attendance",   "VARCHAR(20) DEFAULT 'pending'")]:
            try:
                c.execute(f"ALTER TABLE event_participants ADD COLUMN {col} {typedef}")
            except Exception:
                pass

        # ── notifications ──────────────────────────────────────────────────
        c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id      INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT,
            text    TEXT,
            type    VARCHAR(30) DEFAULT 'info',
            seen    TINYINT(1) DEFAULT 0,
            ts      DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

        conn.commit()
        print("[DB] Schema ready.")
    except Exception as e:
        print(f"[DB] Setup Error: {e}")
    finally:
        conn.close()

db_setup()

def run_select(sql, args=()):
    conn = db_conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall() or []
    except Exception as e:
        print(f"[SQL] Error: {e}")
        return []
    finally:
        conn.close()

def run_exec(sql, args=()):
    conn = db_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
        conn.commit()
        return True
    except Exception as e:
        print(f"[SQL] Error: {e}")
        return False
    finally:
        conn.close()

def run_lastid(sql, args=()):
    conn = db_conn()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            lid = cur.lastrowid
        conn.commit()
        return lid
    except Exception as e:
        print(f"[SQL] Error: {e}")
        return None
    finally:
        conn.close()

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def notify(user_id, text, ntype="info"):
    run_exec("INSERT INTO notifications (user_id,text,type) VALUES (%s,%s,%s)",
             (user_id, text, ntype))
    


def apply_noshow_penalty(user_id):
    run_exec("UPDATE users SET reliability_score = reliability_score - 10 WHERE id=%s", (user_id,))
    ban_date = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
    run_exec("UPDATE users SET ban_until=%s WHERE id=%s", (ban_date, user_id))

def apply_attended_reward(user_id):
    run_exec("UPDATE users SET reliability_score = LEAST(reliability_score + 5, 100) WHERE id=%s", (user_id,))

def is_banned(user_id):
    row = run_select("SELECT ban_until FROM users WHERE id=%s", (user_id,))
    if not row or not row[0]["ban_until"]: return False
    return str(row[0]["ban_until"]) >= datetime.date.today().isoformat()

def get_score(user_id):
    row = run_select("SELECT reliability_score FROM users WHERE id=%s", (user_id,))
    return row[0]["reliability_score"] if row else 70

def score_badge(score):
    if score >= 40: return ("⭐ Trusted Volunteer", COLOR_SUCCESS)
    if score >= 0:  return ("", COLOR_TEXT_SEC)
    return ("⚠️ Low Reliability", COLOR_DANGER)


# ═══════════════════════════════════════════════════════════════════════════
# DARPAN ID VALIDATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def validate_darpan_id_format(did):
    """
    Validate NGO DARPAN ID format strictly.
    
    Format: XX/YYYY/NNNNNNN
    - XX: 2 uppercase state code letters (A-Z)
    - YYYY: 4-digit year (1900-2099)
    - NNNNNNN: 7-digit unique number (0000000-9999999)
    
    Examples:
    - KA/2019/0234567 ✓
    - MH/2020/0012345 ✓
    - ka/2019/0234567 ✗ (lowercase)
    - KA/19/0234567 ✗ (year not 4 digits)
    - KA/2019/234567 ✗ (only 6 digits, need 7)
    """
    pattern = r"^[A-Z]{2}/\d{4}/\d{7}$"
    return bool(re.match(pattern, did))

def is_darpan_id_unique(did):
    """Check if DARPAN ID is NOT already registered in database."""
    existing = run_select("SELECT id FROM ngos WHERE darpan_id=%s", (did,))
    return len(existing) == 0

def is_darpan_id_valid_in_registry(did):
    """Check if DARPAN ID exists in pre-validated registry."""
    return did in VALID_DARPAN_IDS

def validate_email(e):
    return bool(re.match(r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$", e))

def validate_date(d):
    parts = d.split("-")
    if len(parts) != 3: return False
    day, month, year = parts
    return day.isdigit() and month.isdigit() and year.isdigit() \
        and 1 <= int(day) <= 31 and 1 <= int(month) <= 12 and len(year) == 4

def validate_time(t):
    def check_single(s):
        s = s.strip().upper()
        if not s.endswith(("AM", "PM")): return False
        hm = s[:-2].strip().split(":")
        return len(hm) == 2 and hm[0].isdigit() and hm[1].isdigit() \
            and 1 <= int(hm[0]) <= 12 and 0 <= int(hm[1]) <= 59
    parts = [p.strip() for p in t.split(" - ")]
    return check_single(parts[0]) if len(parts) == 1 else \
        check_single(parts[0]) and check_single(parts[1])

# =============================================================================
# SHARED UI HELPERS
# =============================================================================

def lbl(parent, text, font, color, **pack_kw):
    w = ctk.CTkLabel(parent, text=text, font=font, text_color=color)
    w.pack(**pack_kw)
    return w

def entry(parent, placeholder, show=None, height=38):
    kw = dict(placeholder_text=placeholder, font=FONT_BODY, height=height, corner_radius=8)
    if show:
        kw["show"] = show
    e = ctk.CTkEntry(parent, **kw)
    e.pack(fill="x", pady=(0, 10))
    return e

def field(parent, label_text, placeholder, show=None):
    lbl(parent, label_text, FONT_SMALL, COLOR_TEXT, anchor="w", pady=(0, 3))
    return entry(parent, placeholder, show)

def btn(parent, text, cmd, fg=None, tc="#fff", w=None, h=40, side=None, padx=0, pady=0):
    color = fg or COLOR_ACCENT

    kw = dict(
        text=text,
        font=FONT_SUBHEADING,
        fg_color=color,
        hover_color=hover(color),   
        text_color=tc,
        height=h,
        corner_radius=10,
        command=cmd
    )

    if w:
        kw["width"] = w

    b = ctk.CTkButton(parent, **kw)

    if side:
        b.pack(side=side, padx=padx, pady=pady)
    else:
        b.pack(fill="x", pady=pady)

    return b

def divider(parent, pady=12):
    f = ctk.CTkFrame(parent, fg_color=COLOR_BORDER, height=1)
    f.pack(fill="x", pady=pady)

def card(parent, **pack_kw):
    c = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=12,
                     border_width=1, border_color=COLOR_BORDER)
    c.pack(**pack_kw)
    return c

def section_title(parent, text):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    f.pack(fill="x", pady=(18, 8))
    lbl(f, text, FONT_HEADING, COLOR_TEXT, anchor="w")
    ctk.CTkFrame(f, fg_color=COLOR_ACCENT, height=2, width=40).pack(anchor="w", pady=(2, 0))

def top_nav(parent, title, back_fn, right_widgets=None):
    """Blue top bar with back arrow and optional right-side buttons."""
    bar = ctk.CTkFrame(parent, fg_color=COLOR_ACCENT, height=68)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    inner = ctk.CTkFrame(bar, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=24, pady=10)

    ctk.CTkButton(inner, text="← Back", font=FONT_SUBHEADING,
                  fg_color="transparent", text_color="#fff",
                  hover_color="#1d4ed8", width=80, height=36, corner_radius=8,
                  command=back_fn).pack(side="left", padx=(0, 12))
    ctk.CTkLabel(inner, text=title, font=FONT_HEADING, text_color="#fff").pack(side="left")

    if right_widgets:
        rf = ctk.CTkFrame(inner, fg_color="transparent")
        rf.pack(side="right")
        for rw in right_widgets:
            rw(rf)
    return inner

def stat_tile(parent, icon, value, label, color=COLOR_ACCENT):
    c = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=12,
                     border_width=1, border_color=COLOR_BORDER)
    c.pack(side="left", fill="both", expand=True, padx=5)
    ctk.CTkLabel(c, text=icon, font=("Segoe UI Emoji", 26), text_color=color).pack(pady=(14, 2))
    ctk.CTkLabel(c, text=str(value), font=("Montserrat", 20, "bold"), text_color=color).pack()
    ctk.CTkLabel(c, text=label, font=FONT_SMALL, text_color=COLOR_TEXT_SEC).pack(pady=(0, 12))

# =============================================================================
# MAIN APPLICATION
# =============================================================================

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NGO Connect Hub")
        self.geometry("1380x840")
        self.minsize(1100, 660)
        self.user = None
        self.show_landing()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    # ─────────────────────────────────────────────────────────────────────────
    # LANDING PAGE
    # ─────────────────────────────────────────────────────────────────────────
    def show_landing(self):
        self.clear()
        root = ctk.CTkFrame(self, fg_color=COLOR_BG)
        root.pack(fill="both", expand=True)
        scroll = CTkScrollableFrame(root, fg_color=COLOR_BG)
        scroll.pack(fill="both", expand=True)

        # ── HERO ─────────────────────────────────────────────────────────────
        hero = ctk.CTkFrame(scroll, fg_color=COLOR_ACCENT)
        hero.pack(fill="x")
        hc = ctk.CTkFrame(hero, fg_color="transparent")
        hc.pack(expand=True, padx=80, pady=70)

        ctk.CTkLabel(hc, text="🌍", font=("Segoe UI Emoji", 80), text_color="#fff").pack()
        ctk.CTkLabel(hc, text="NGO Connect Hub", font=FONT_HERO, text_color="#fff").pack(pady=(8, 0))
        ctk.CTkLabel(hc, text="Connecting Communities. Empowering Change.",
                     font=("Inter", 15), text_color="#dbeafe").pack(pady=(4, 0))
        ctk.CTkLabel(hc, text="The one platform where passionate volunteers meet impactful organisations.",
                     font=FONT_SMALL, text_color="#bfdbfe", wraplength=700, justify="center").pack(pady=(6, 28))

        bf = ctk.CTkFrame(hc, fg_color="transparent")
        bf.pack()
        ctk.CTkButton(bf, text="🚀  Get Started — It's Free", font=FONT_SUBHEADING,
                      fg_color="#ffffff", hover_color="#e2e8f0", text_color=COLOR_ACCENT, width=200, height=44,
                      corner_radius=10, command=self.show_register_choice).pack(side="left", padx=8)
        ctk.CTkButton(bf, text="Sign In", font=FONT_SUBHEADING,
                      fg_color="transparent", text_color="#fff",
                      border_width=2, border_color="#fff",
                      width=130, height=44, corner_radius=10,
                      command=self.show_login).pack(side="left", padx=8)

        # ── LIVE STATS ────────────────────────────────────────────────────────
        stats_bg = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=0)
        stats_bg.pack(fill="x")
        sf = ctk.CTkFrame(stats_bg, fg_color="transparent")
        sf.pack(pady=28)

        def _count(q):
            r = run_select(q)
            return r[0]["c"] if r else 0

        for icon, label, val in [
            ("🏢", "NGOs Registered",  _count("SELECT COUNT(*) as c FROM ngos")),
            ("👥", "Volunteers",       _count("SELECT COUNT(*) as c FROM users WHERE role='Volunteer'")),
            ("📅", "Active Events",    _count("SELECT COUNT(*) as c FROM events WHERE cancelled=0")),
        ]:
            tf = ctk.CTkFrame(sf, fg_color="transparent")
            tf.pack(side="left", padx=50)
            ctk.CTkLabel(tf, text=icon, font=("Segoe UI Emoji", 32), text_color=COLOR_ACCENT).pack()
            ctk.CTkLabel(tf, text=str(val), font=("Montserrat", 26, "bold"), text_color=COLOR_TEXT).pack()
            ctk.CTkLabel(tf, text=label, font=FONT_SMALL, text_color=COLOR_TEXT_SEC).pack()

        # ── HOW IT WORKS ──────────────────────────────────────────────────────
        hw = ctk.CTkFrame(scroll, fg_color=COLOR_BG)
        hw.pack(fill="x", padx=70, pady=50)
        ctk.CTkLabel(hw, text="How It Works", font=FONT_TITLE, text_color=COLOR_TEXT).pack()
        ctk.CTkLabel(hw, text="Simple steps to start making a difference",
                     font=FONT_BODY, text_color=COLOR_TEXT_SEC).pack(pady=(4, 24))

        steps_f = ctk.CTkFrame(hw, fg_color="transparent")
        steps_f.pack(fill="x")
        steps = [
            ("1️⃣", "Create Account", "Sign up as a Volunteer or an NGO in under 2 minutes."),
            ("2️⃣", "Explore", "Browse NGOs near you or browse upcoming volunteer events."),
            ("3️⃣", "Connect", "Join an NGO as a member or register for an event you care about."),
            ("4️⃣", "Make Impact", "Attend events, log hours, and track your contribution over time."),
        ]
        for icon, title, desc in steps:
            c = ctk.CTkFrame(steps_f, fg_color=COLOR_CARD, corner_radius=12,
                             border_width=1, border_color=COLOR_BORDER)
            c.pack(side="left", fill="both", expand=True, padx=6)
            ctk.CTkLabel(c, text=icon, font=("Segoe UI Emoji", 30), text_color=COLOR_ACCENT).pack(pady=(16, 4))
            ctk.CTkLabel(c, text=title, font=FONT_SUBHEADING, text_color=COLOR_TEXT).pack()
            ctk.CTkLabel(c, text=desc, font=FONT_SMALL, text_color=COLOR_TEXT_SEC,
                         wraplength=190, justify="center").pack(padx=10, pady=(4, 16))

        # ── FOR VOLUNTEERS ────────────────────────────────────────────────────
        vf = ctk.CTkFrame(scroll, fg_color="#eff6ff")
        vf.pack(fill="x")
        vc = ctk.CTkFrame(vf, fg_color="transparent")
        vc.pack(fill="x", padx=70, pady=50)

        left_v = ctk.CTkFrame(vc, fg_color="transparent")
        left_v.pack(side="left", fill="both", expand=True, padx=(0, 30))
        ctk.CTkLabel(left_v, text="For Volunteers 👤", font=FONT_TITLE, text_color=COLOR_TEXT).pack(anchor="w")
        ctk.CTkLabel(left_v, text="Find meaningful ways to give back to your community.",
                     font=FONT_BODY, text_color=COLOR_TEXT_SEC).pack(anchor="w", pady=(4, 16))
        for pt in ["🔍  Search events by city, category, or keyword",
                   "🏢  Join NGOs and become a long-term member",
                   "📋  Track all your event registrations in one place",
                   "⏱️  See your total volunteer hours automatically logged",
                   "🔔  Get notified when new events match your interests"]:
            ctk.CTkLabel(left_v, text=pt, font=FONT_BODY, text_color=COLOR_TEXT).pack(anchor="w", pady=2)
        ctk.CTkButton(left_v, text="Register as Volunteer →", font=FONT_SUBHEADING,
                      fg_color=COLOR_ACCENT, text_color="#fff", width=200, height=40,
                      corner_radius=10, command=self.show_register_vol).pack(anchor="w", pady=(16, 0))

        right_v = ctk.CTkFrame(vc, fg_color=COLOR_CARD, corner_radius=14,
                               border_width=1, border_color=COLOR_BORDER, width=280)
        right_v.pack(side="right", fill="y")
        right_v.pack_propagate(False)
        rvc = ctk.CTkFrame(right_v, fg_color="transparent")
        rvc.pack(expand=True, padx=20, pady=20)
        ctk.CTkLabel(rvc, text="👤", font=("Segoe UI Emoji", 50), text_color=COLOR_ACCENT).pack(pady=(8, 4))
        ctk.CTkLabel(rvc, text="Volunteer Profile", font=FONT_SUBHEADING, text_color=COLOR_TEXT).pack()
        for line in ["✓  Skills & interests listed", "✓  City-based matching", "✓  Impact dashboard"]:
            ctk.CTkLabel(rvc, text=line, font=FONT_SMALL, text_color=COLOR_TEXT_SEC).pack(anchor="w", pady=2)

        # ── FOR NGOs ──────────────────────────────────────────────────────────
        nf = ctk.CTkFrame(scroll, fg_color=COLOR_BG)
        nf.pack(fill="x")
        nc = ctk.CTkFrame(nf, fg_color="transparent")
        nc.pack(fill="x", padx=70, pady=50)

        left_n = ctk.CTkFrame(nc, fg_color=COLOR_CARD, corner_radius=14,
                              border_width=1, border_color=COLOR_BORDER, width=280)
        left_n.pack(side="left", fill="y")
        left_n.pack_propagate(False)
        lnc = ctk.CTkFrame(left_n, fg_color="transparent")
        lnc.pack(expand=True, padx=20, pady=20)
        ctk.CTkLabel(lnc, text="🏢", font=("Segoe UI Emoji", 50), text_color=COLOR_SUCCESS).pack(pady=(8, 4))
        ctk.CTkLabel(lnc, text="NGO Dashboard", font=FONT_SUBHEADING, text_color=COLOR_TEXT).pack()
        for line in ["✓  Post & manage events", "✓  View all volunteers", "✓  Member roster"]:
            ctk.CTkLabel(lnc, text=line, font=FONT_SMALL, text_color=COLOR_TEXT_SEC).pack(anchor="w", pady=2)

        right_n = ctk.CTkFrame(nc, fg_color="transparent")
        right_n.pack(side="right", fill="both", expand=True, padx=(30, 0))
        ctk.CTkLabel(right_n, text="For NGOs 🏢", font=FONT_TITLE, text_color=COLOR_TEXT).pack(anchor="w")
        ctk.CTkLabel(right_n, text="Reach thousands of motivated volunteers and grow your impact.",
                     font=FONT_BODY, text_color=COLOR_TEXT_SEC).pack(anchor="w", pady=(4, 16))
        for pt in ["📣  Publish events with full details — date, time, location, capacity",
                   "👥  See exactly who signed up and manage check-ins",
                   "🏅  Track total volunteer hours contributed to your events",
                   "🔔  Automatically notify your members about new events",
                   "🌐  Public directory listing so volunteers can find you"]:
            ctk.CTkLabel(right_n, text=pt, font=FONT_BODY, text_color=COLOR_TEXT).pack(anchor="w", pady=2)
        ctk.CTkButton(right_n, text="Register Your NGO →", font=FONT_SUBHEADING,
                      fg_color=COLOR_SUCCESS, hover_color="#90C0B1", text_color="#fff", width=200, height=40,
                      corner_radius=10, command=self.show_register_ngo).pack(anchor="w", pady=(16, 0))

        # ── FAQ / QUICK GUIDE ─────────────────────────────────────────────────
        fq = ctk.CTkFrame(scroll, fg_color="#eff6ff")
        fq.pack(fill="x")
        fqc = ctk.CTkFrame(fq, fg_color="transparent")
        fqc.pack(fill="x", padx=70, pady=50)
        ctk.CTkLabel(fqc, text="Quick Guide", font=FONT_TITLE, text_color=COLOR_TEXT).pack()
        ctk.CTkLabel(fqc, text="Everything you need to know at a glance",
                     font=FONT_BODY, text_color=COLOR_TEXT_SEC).pack(pady=(4, 20))
        faqs = [
            ("Is it free?",
             "Yes — completely free for both volunteers and NGOs."),
            ("Do I need to be in a specific city?",
             "No. You can browse events from any city and filter by location."),
            ("How does an NGO post an event?",
             "After registering and signing in, NGOs see a '+ Post Event' button on their dashboard and in the Events page."),
            ("How do volunteers track their hours?",
             "Once an NGO marks you as 'Checked In' at an event, they can log your hours. You see the total on your dashboard."),
            ("Can a volunteer join multiple NGOs?",
             "Yes — you can join as many NGOs as you like from the NGO Directory."),
        ]
        for q, a in faqs:
            fc_row = ctk.CTkFrame(fqc, fg_color=COLOR_CARD, corner_radius=10,
                                  border_width=1, border_color=COLOR_BORDER)
            fc_row.pack(fill="x", pady=4)
            fr = ctk.CTkFrame(fc_row, fg_color="transparent")
            fr.pack(fill="x", padx=16, pady=10)
            ctk.CTkLabel(fr, text=f"❓ {q}", font=FONT_SUBHEADING, text_color=COLOR_TEXT).pack(anchor="w")
            ctk.CTkLabel(fr, text=f"   {a}", font=FONT_BODY, text_color=COLOR_TEXT_SEC,
                         wraplength=900, justify="left").pack(anchor="w", pady=(2, 0))

        # ── CTA FOOTER ───────────────────────────────────────────────────────
        cta = ctk.CTkFrame(scroll, fg_color=COLOR_ACCENT)
        cta.pack(fill="x")
        ctac = ctk.CTkFrame(cta, fg_color="transparent")
        ctac.pack(padx=80, pady=50)
        ctk.CTkLabel(ctac, text="Ready to make a difference?", font=FONT_TITLE, text_color="#fff").pack()
        ctk.CTkLabel(ctac, text="Join hundreds of volunteers and NGOs already on the platform.",
                     font=FONT_BODY, text_color="#dbeafe").pack(pady=(4, 20))
        cb = ctk.CTkFrame(ctac, fg_color="transparent")
        cb.pack()
        ctk.CTkButton(cb, text="Register as Volunteer", font=FONT_SUBHEADING,
                      fg_color="#ffffff", hover_color="#e2e8f0", text_color=COLOR_ACCENT, width=190, height=42,
                      corner_radius=10, command=self.show_register_vol).pack(side="left", padx=8)
        ctk.CTkButton(cb, text="Register as NGO", font=FONT_SUBHEADING,
                      fg_color="transparent", text_color="#fff",
                      border_width=2, border_color="#fff",
                      width=170, height=42, corner_radius=10,
                      command=self.show_register_ngo).pack(side="left", padx=8)
        ctk.CTkButton(cb, text="Sign In →", font=FONT_SUBHEADING,
                      fg_color=COLOR_LIGHT_BLUE, text_color=COLOR_ACCENT, hover_color="#99a9d4",
                      width=120, height=42, corner_radius=10,
                      command=self.show_login).pack(side="left", padx=8)

        # ── FOOTER ───────────────────────────────────────────────────────────
        foot = ctk.CTkFrame(scroll, fg_color=COLOR_SIDEBAR)
        foot.pack(fill="x")
        ctk.CTkLabel(foot, text="© 2026 NGO Connect Hub  •  Empowering communities across India",
                     font=FONT_SMALL, text_color="#94a3b8").pack(pady=22)

    # ─────────────────────────────────────────────────────────────────────────
    # LOGIN
    # ────────────────────���────────────────────────────────────────────────────
    def show_login(self):
        self.clear()
        root = ctk.CTkFrame(self, fg_color=COLOR_BG)
        root.pack(fill="both", expand=True)

        # Left panel — branding
        lp = ctk.CTkFrame(root, fg_color=COLOR_ACCENT, width=460)
        lp.pack(side="left", fill="y")
        lp.pack_propagate(False)
        lpc = ctk.CTkFrame(lp, fg_color="transparent")
        lpc.pack(expand=True, padx=40)
        ctk.CTkLabel(lpc, text="🌍", font=("Segoe UI Emoji", 70), text_color="#fff").pack(pady=(0, 10))
        ctk.CTkLabel(lpc, text="NGO Connect", font=("Montserrat", 26, "bold"), text_color="#fff").pack()
        ctk.CTkLabel(lpc, text="Connecting Communities\nEmpowering Change",
                     font=("Inter", 13), text_color="#dbeafe", justify="center").pack(pady=(8, 0))
        divider(lpc)
        for pt in ["✓  Find volunteer events near you",
                   "✓  Join NGOs you believe in",
                   "✓  Track your volunteer hours",
                   "✓  Get notified about opportunities"]:
            ctk.CTkLabel(lpc, text=pt, font=FONT_BODY, text_color="#bfdbfe").pack(anchor="w", pady=2)

        ctk.CTkButton(lpc, text="← Back to Home", font=FONT_SMALL,
                      fg_color="transparent", text_color="#93c5fd",
                      hover_color="#a5b3db", width=140, height=30,
                      corner_radius=8, command=self.show_landing).pack(pady=(24, 0))

        # Right panel — outer wrapper expands to fill space
        rp = ctk.CTkFrame(root, fg_color=COLOR_BG)
        rp.pack(side="right", fill="both", expand=True)

        # This inner frame uses pack(expand=True) so it grows to fill rp,
        # then the form card inside it is naturally centred.
        rp_inner = ctk.CTkFrame(rp, fg_color="transparent")
        rp_inner.pack(fill="both", expand=True)

        # Spacer rows above and below push the card to vertical centre
        rp_inner.rowconfigure(0, weight=1)
        rp_inner.rowconfigure(2, weight=1)
        rp_inner.columnconfigure(0, weight=1)
        rp_inner.columnconfigure(2, weight=1)

        form = ctk.CTkFrame(rp_inner, fg_color=COLOR_CARD, corner_radius=16,
                            border_width=1, border_color=COLOR_BORDER)
        form.grid(row=1, column=1, padx=40, pady=40, sticky="nsew")

        fi = ctk.CTkFrame(form, fg_color="transparent")
        fi.pack(fill="both", expand=True, padx=36, pady=36)

        ctk.CTkLabel(fi, text="Welcome Back 👋", font=FONT_TITLE, text_color=COLOR_TEXT).pack(pady=(0, 4))
        ctk.CTkLabel(fi, text="Sign in to your NGO Connect account",
                     font=FONT_SMALL, text_color=COLOR_TEXT_SEC).pack(pady=(0, 20))

        ctk.CTkLabel(fi, text="Email Address", font=FONT_SMALL, text_color=COLOR_TEXT).pack(anchor="w", pady=(0, 3))
        em_entry = ctk.CTkEntry(fi, placeholder_text="your@email.com",
                                font=FONT_BODY, height=40, corner_radius=8)
        em_entry.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(fi, text="Password", font=FONT_SMALL, text_color=COLOR_TEXT).pack(anchor="w", pady=(0, 3))
        pw_entry = ctk.CTkEntry(fi, placeholder_text="Your password",
                                show="*", font=FONT_BODY, height=40, corner_radius=8)
        pw_entry.pack(fill="x", pady=(0, 6))

        err_lbl = ctk.CTkLabel(fi, text="", font=FONT_SMALL, text_color=COLOR_DANGER)
        err_lbl.pack(pady=(0, 10))

        def do_login():
            em = em_entry.get().strip()
            pw = pw_entry.get().strip()
            if not em or not pw:
                err_lbl.configure(text="⚠  Please enter both email and password.")
                return
            users = run_select("SELECT * FROM users WHERE email=%s", (em,))
            if users and users[0]["password"] == hash_pw(pw):
                self.user = users[0]
                self.unbind("<Return>")
                self.show_dashboard()
            else:
                err_lbl.configure(text="⚠  Incorrect email or password.")

        self.bind("<Return>", lambda e: do_login())

        ctk.CTkButton(fi, text="Sign In  →", font=FONT_SUBHEADING,
                      fg_color=COLOR_ACCENT, text_color="#fff",
                      height=44, corner_radius=10,
                      command=do_login).pack(fill="x", pady=(0, 10))

        ctk.CTkFrame(fi, fg_color=COLOR_BORDER, height=1).pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(fi, text="Don't have an account yet?",
                     font=FONT_SMALL, text_color=COLOR_TEXT_SEC).pack(pady=(0, 6))

        ctk.CTkButton(fi, text="Create a Free Account", font=FONT_SUBHEADING,
                      fg_color=COLOR_LIGHT_BLUE, text_color=COLOR_ACCENT, hover_color="#a0acce",
                      height=42, corner_radius=10,
                      command=self.show_register_choice).pack(fill="x", pady=(0, 8))

        ctk.CTkButton(fi, text="← Back to Home", font=FONT_SMALL,
                      fg_color="#f1f5f9", text_color=COLOR_TEXT_SEC, hover_color="#8c9bc5",
                      height=36, corner_radius=8,
                      command=self.show_landing).pack(fill="x")

    # ─────────────────────────────────────────────────────────────────────────
    # REGISTER CHOICE
    # ─────────────────────────────────────────────────────────────────────────
    def show_register_choice(self):
        self.clear()
        root = ctk.CTkFrame(self, fg_color=COLOR_BG)
        root.pack(fill="both", expand=True)
        center = ctk.CTkFrame(root, fg_color="transparent")
        center.pack(expand=True)

        ctk.CTkLabel(center, text="Join NGO Connect", font=FONT_TITLE, text_color=COLOR_TEXT).pack(pady=(0, 6))
        ctk.CTkLabel(center, text="I want to join as a...", font=FONT_BODY, text_color=COLOR_TEXT_SEC).pack(pady=(0, 30))

        cf = ctk.CTkFrame(center, fg_color="transparent")
        cf.pack()

        def choice(parent, icon, title, bullets, color, cmd):
            c = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=16, width=310, height=340,
                             border_width=2, border_color=COLOR_BORDER)
            c.pack(side="left", padx=16)
            c.pack_propagate(False)
            ci = ctk.CTkFrame(c, fg_color="transparent")
            ci.pack(expand=True, padx=20)
            ctk.CTkLabel(ci, text=icon, font=("Segoe UI Emoji", 52), text_color=color).pack(pady=(16, 6))
            ctk.CTkLabel(ci, text=title, font=FONT_HEADING, text_color=COLOR_TEXT).pack()
            ctk.CTkFrame(ci, fg_color="transparent", height=6).pack()
            for b in bullets:
                ctk.CTkLabel(ci, text=b, font=FONT_SMALL, text_color=COLOR_TEXT_SEC).pack(anchor="w")
            ctk.CTkButton(ci, text=f"Continue as {title}", font=FONT_SUBHEADING,
                          fg_color=color, text_color="#fff", width=240, height=40,
                          corner_radius=10, command=cmd).pack(pady=(14, 20))

        choice(cf, "👤", "Volunteer",
               ["• Browse & join events", "• Join NGOs", "• Track your hours"],
               COLOR_ACCENT, self.show_register_vol)
        choice(cf, "🏢", "NGO",
               ["• Post events", "• Manage volunteers", "• Grow your network"],
               COLOR_SUCCESS, self.show_register_ngo)

        ctk.CTkFrame(center, fg_color="transparent", height=20).pack()
        ctk.CTkButton(center, text="Already have an account?  Sign In →",
                      font=FONT_SMALL, fg_color="transparent", text_color=COLOR_ACCENT,
                      hover_color=COLOR_LIGHT_BLUE, height=30, command=self.show_login).pack()
        ctk.CTkButton(center, text="← Back to Home", font=FONT_SMALL,
                      fg_color="transparent", text_color=COLOR_TEXT_SEC, hover_color="#8f9dc4",
                      height=28, command=self.show_landing).pack(pady=4)

    # ─────────────────────────────────────────────────────────────────────────
    # REGISTER VOLUNTEER
    # ─────────────────────────────────────────────────────────────────────────
    def show_register_vol(self):
        self.clear()
        root = ctk.CTkFrame(self, fg_color=COLOR_BG)
        root.pack(fill="both", expand=True)
        top_nav(root, "👤  Register as Volunteer", self.show_register_choice)

        scroll = CTkScrollableFrame(root, fg_color=COLOR_BG)
        scroll.pack(fill="both", expand=True)

        wrap = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=12,
                            border_width=1, border_color=COLOR_BORDER)
        wrap.pack(fill="both", padx=120, pady=24)
        fi = ctk.CTkFrame(wrap, fg_color="transparent")
        fi.pack(fill="both", padx=36, pady=30)

        ctk.CTkLabel(fi, text="Create Your Volunteer Account",
                     font=FONT_HEADING, text_color=COLOR_TEXT).pack(anchor="w", pady=(0, 16))

        name_e  = field(fi, "Full Name *", "e.g. Priya Sharma")
        email_e = field(fi, "Email Address *", "your@email.com")
        phone_e = field(fi, "Phone Number * (10 digits)", "9876543210")
        city_e  = field(fi, "City *", "e.g. Bengaluru")

        ctk.CTkLabel(fi, text="Skills / Interests  (comma separated, optional)",
                     font=FONT_SMALL, text_color=COLOR_TEXT).pack(anchor="w", pady=(0, 3))
        skills_e = ctk.CTkEntry(fi, placeholder_text="e.g. Teaching, First Aid, Photography",
                                font=FONT_BODY, height=38, corner_radius=8)
        skills_e.pack(fill="x", pady=(0, 10))

        pw1_e = field(fi, "Password * (min 6 characters)", "Choose a password", show="*")
        pw2_e = field(fi, "Confirm Password *", "Repeat password", show="*")

        err = ctk.CTkLabel(fi, text="", font=FONT_SMALL, text_color=COLOR_DANGER)
        err.pack(pady=(0, 6))

        def do_reg():
            n  = name_e.get().strip()
            em = email_e.get().strip()
            ph = phone_e.get().strip()
            ct = city_e.get().strip()
            sk = skills_e.get().strip()
            p1 = pw1_e.get().strip()
            p2 = pw2_e.get().strip()

            if not all([n, em, ph, ct, p1, p2]):
                err.configure(text="All fields marked * are required."); return
            if not validate_email(em):
                err.configure(text="Please enter a valid email address."); return
            if len(ph) != 10 or not ph.isdigit():
                err.configure(text="Phone must be exactly 10 digits."); return
            if len(p1) < 6:
                err.configure(text="Password must be at least 6 characters."); return
            if p1 != p2:
                err.configure(text="Passwords do not match."); return
            if run_select("SELECT id FROM users WHERE email=%s", (em,)):
                err.configure(text="This email is already registered. Try signing in."); return

            uid = run_lastid(
                "INSERT INTO users (email,name,phone,password,role,city,skills) "
                "VALUES (%s,%s,%s,%s,'Volunteer',%s,%s)",
                (em, n, ph, hash_pw(p1), ct, sk)
            )
            if uid:
                messagebox.showinfo("Account Created! 🎉",
                                    f"Welcome to NGO Connect, {n}!\n\nYou can now sign in and start exploring events and NGOs near you.")
                self.show_login()
            else:
                err.configure(text="Registration failed. Please try again.")

        bf = ctk.CTkFrame(fi, fg_color="transparent")
        bf.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(bf, text="Create My Account", font=FONT_SUBHEADING,
                      fg_color=COLOR_ACCENT, text_color="#fff",
                      width=170, height=42, corner_radius=10, command=do_reg).pack(side="left", padx=(0, 10))
        ctk.CTkButton(bf, text="← Back", font=FONT_SUBHEADING,
                      fg_color=COLOR_LIGHT_BLUE, text_color=COLOR_ACCENT, hover_color="#a6b3d6",
                      width=100, height=42, corner_radius=10,
                      command=self.show_register_choice).pack(side="left")

    # ─────────────────────────────────────────────────────────────────────────
    # REGISTER NGO ⭐ WITH DARPAN ID VERIFICATION
    # ─────────────────────────────────────────────────────────────────────────
    def show_register_ngo(self):
        self.clear()
        root = ctk.CTkFrame(self, fg_color=COLOR_BG)
        root.pack(fill="both", expand=True)
        top_nav(root, "🏢  Register Your NGO", self.show_register_choice)

        scroll = CTkScrollableFrame(root, fg_color=COLOR_BG)
        scroll.pack(fill="both", expand=True)

        wrap = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=12,
                            border_width=1, border_color=COLOR_BORDER)
        wrap.pack(fill="both", padx=120, pady=24)
        fi = ctk.CTkFrame(wrap, fg_color="transparent")
        fi.pack(fill="both", padx=36, pady=30)

        ctk.CTkLabel(fi, text="Register Your Organisation",
                     font=FONT_HEADING, text_color=COLOR_TEXT).pack(anchor="w", pady=(0, 16))

        name_e  = field(fi, "Organisation Name *", "e.g. Green Earth Foundation")

        ctk.CTkLabel(fi, text="Category *", font=FONT_SMALL, text_color=COLOR_TEXT).pack(anchor="w", pady=(0, 3))
        cat_cb = ctk.CTkComboBox(fi, values=CATEGORIES, font=FONT_BODY,
                                 height=38, corner_radius=8, state="readonly")
        cat_cb.set("Education")
        cat_cb.pack(fill="x", pady=(0, 10))

        city_e    = field(fi, "City *", "e.g. Mumbai")
        email_e   = field(fi, "Email Address *", "org@example.com")
        phone_e   = field(fi, "Contact Phone * (10 digits)", "9876543210")

        # ═══════════════════════════════════════════════════════════════════
        # 🔐 DARPAN ID FIELD (NEW)
        # ═══════════════════════════════════════════════════════════════════
        darpan_lbl = ctk.CTkFrame(fi, fg_color="transparent")
        darpan_lbl.pack(fill="x", pady=(8, 0))
        
        lbl_text = ctk.CTkFrame(darpan_lbl, fg_color="transparent")
        lbl_text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(lbl_text, text="DARPAN ID * (Government Registration)",
                     font=FONT_SMALL, text_color=COLOR_TEXT).pack(anchor="w")
        
        info_btn = ctk.CTkLabel(darpan_lbl, text="ℹ️",
                               font=("Inter", 14), text_color=COLOR_ACCENT)
        info_btn.pack(side="right", padx=(8, 0))
        
        info_tooltip = "Format: XX/YYYY/NNNNNNN\nExample: KA/2019/0234567\nThis verifies your NGO is legally registered."
        info_btn.bind("<Enter>", lambda e: messagebox.showinfo("DARPAN ID Format", info_tooltip))

        darpan_e = ctk.CTkEntry(fi, placeholder_text="Format: KA/2019/0234567",
                               font=FONT_BODY, height=38, corner_radius=8)
        darpan_e.pack(fill="x", pady=(3, 0))
        
        # Real-time validation feedback
        darpan_status = ctk.CTkLabel(fi, text="", font=FONT_SMALL, text_color=COLOR_SUCCESS)
        darpan_status.pack(anchor="w", pady=(2, 10))

        def check_darpan_format(event=None):
            """Real-time DARPAN ID format validation"""
            did = darpan_e.get().strip().upper()
            
            if not did:
                darpan_status.configure(text="", text_color=COLOR_TEXT_SEC)
                return
            
            if validate_darpan_id_format(did):
                if is_darpan_id_valid_in_registry(did):
                    darpan_status.configure(
                        text="✅ Valid DARPAN ID (Verified in Registry)",
                        text_color=COLOR_SUCCESS
                    )
                else:
                    darpan_status.configure(
                        text="⚠️ Format valid but not in registry. Verify with Government.",
                        text_color=COLOR_WARNING
                    )
            else:
                darpan_status.configure(
                    text="❌ Invalid format. Use: XX/YYYY/NNNNNNN (e.g., KA/2019/0234567)",
                    text_color=COLOR_DANGER
                )

        darpan_e.bind("<KeyRelease>", check_darpan_format)

        website_e = field(fi, "Website (optional)", "https://yoursite.org")

        ctk.CTkLabel(fi, text="Description * — Tell volunteers about your mission",
                     font=FONT_SMALL, text_color=COLOR_TEXT).pack(anchor="w", pady=(0, 3))
        desc_tb = ctk.CTkTextbox(fi, font=FONT_BODY, height=90, corner_radius=8)
        desc_tb.pack(fill="x", pady=(0, 10))

        pw1_e = field(fi, "Password * (min 6 characters)", "Choose a password", show="*")
        pw2_e = field(fi, "Confirm Password *", "Repeat password", show="*")

        err = ctk.CTkLabel(fi, text="", font=FONT_SMALL, text_color=COLOR_DANGER)
        err.pack(pady=(0, 6))

        def do_reg():
            on = name_e.get().strip()
            ct = city_e.get().strip()
            em = email_e.get().strip()
            ph = phone_e.get().strip()
            did = darpan_e.get().strip().upper()  # ← Get DARPAN ID
            ws = website_e.get().strip()
            de = desc_tb.get("1.0", "end").strip()
            p1 = pw1_e.get().strip()
            p2 = pw2_e.get().strip()

            # Validation chain
            if not all([on, ct, em, ph, did, de, p1, p2]):
                err.configure(text="All fields marked * are required."); return
            if not validate_email(em):
                err.configure(text="Please enter a valid email address."); return
            if len(ph) != 10 or not ph.isdigit():
                err.configure(text="Phone must be exactly 10 digits."); return
            
            # ═══ DARPAN ID Validation ═══
            if not validate_darpan_id_format(did):
                err.configure(text="Invalid DARPAN ID format. Use: XX/YYYY/NNNNNNN (e.g., KA/2019/0234567)"); 
                return
            
            if not is_darpan_id_unique(did):
                err.configure(text="This DARPAN ID is already registered. Each NGO must have a unique ID."); 
                return
            
            if len(p1) < 6:
                err.configure(text="Password must be at least 6 characters."); return
            if p1 != p2:
                err.configure(text="Passwords do not match."); return
            if run_select("SELECT id FROM users WHERE email=%s", (em,)):
                err.configure(text="This email is already registered. Try signing in."); return
            if run_select("SELECT id FROM ngos WHERE name=%s", (on,)):
                err.configure(text="An NGO with this name already exists."); return

            # ═══ Insert with DARPAN ID ═══
            ngo_id = run_lastid(
                "INSERT INTO ngos (name,type,city,description,email,phone,website,darpan_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (on, cat_cb.get(), ct, de, em, ph, ws, did)
            )
            uid = run_lastid(
                "INSERT INTO users (email,name,phone,password,role,city) "
                "VALUES (%s,%s,%s,%s,'NGO',%s)",
                (em, on, ph, hash_pw(p1), ct)
            )
            if ngo_id and uid:
                badge = "✅" if is_darpan_id_valid_in_registry(did) else "⏳"
                messagebox.showinfo("NGO Registered! 🎉",
                                    f"'{on}' is now live on NGO Connect!\n\n"
                                    f"{badge} DARPAN ID: {did}\n\n"
                                    f"Sign in to post your first event and start connecting with volunteers.")
                self.show_login()
            else:
                err.configure(text="Registration failed. Please try again.")

        bf = ctk.CTkFrame(fi, fg_color="transparent")
        bf.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(bf, text="Register NGO", font=FONT_SUBHEADING,
                      fg_color=COLOR_SUCCESS, text_color="#fff",
                      width=160, height=42, corner_radius=10, command=do_reg).pack(side="left", padx=(0, 10))
        ctk.CTkButton(bf, text="← Back", font=FONT_SUBHEADING,
                      fg_color=COLOR_LIGHT_BLUE, text_color=COLOR_ACCENT, hover_color="#95a2c5",
                      width=100, height=42, corner_radius=10,
                      command=self.show_register_choice).pack(side="left")

    # Placeholder methods (rest of the app structure)
    def show_dashboard(self): pass
    def show_events(self, search="", fcity="", fcat=""): pass
    def show_directory(self): pass
    def show_post_event(self): pass
    def show_my_events(self): pass
    def show_my_registrations(self): pass
    def show_my_ngos(self): pass
    def show_event_volunteers(self, ev): pass
    def show_edit_event(self, ev): pass
    def show_notifications(self): pass
    def show_profile(self): pass
    def do_logout(self): 
        self.user = None
        self.show_landing()


if __name__ == "__main__":
    app = App()
    app.mainloop()
