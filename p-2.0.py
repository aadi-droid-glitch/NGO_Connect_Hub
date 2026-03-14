"""
NGO Connect Hub — Full single-file implementation (tkinter-only)

Features:
- Login / Registration (NGO / Volunteer) with strict validation
- Profile with editable name, phone, password and category follows for volunteers
- Sidebar with user initials icon, persistent detected location label
- NGO Dashboard: impact stats (total volunteers, members, popular categories)
- Volunteer Manager: table to Verify / Check-in volunteers (persisted)
- Calendar popup (custom, stdlib-based) for intuitive date selection
- Saved category follows: volunteers can follow categories, highlighted events on Home
- Listings with category filter and sorting
- Events with "Participate" and "Join NGO" actions
- Data persisted to ngodata.json (users, ngos, events)
- Uses only Python standard library: tkinter, ttk, json, datetime, urllib, webbrowser, hashlib, calendar"""


import os
import math
import calendar
import urllib.request
import urllib.parse
import webbrowser
import hashlib
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timezone, timedelta
import mysql.connector

# Constants
ACCENT_COLOR = "#1a73e8"
APP_BG = "#f4f7fb"
CARD_BG = "#ffffff"

CATEGORIES = [
    "Food", "Education", "Health", "Environment", "Shelter",
    "Women & Children", "Elderly Care", "Climate Action",
    "Animal Welfare", "Skill Development", "Other"
]


# -----------------------
# Utilities
# -----------------------
def _hash_password(p: str) -> str:
    return hashlib.sha256(p.encode("utf-8")).hexdigest()


def now_iso():
    return datetime.now(timezone.utc).isoformat()

def load_users():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    return users

def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="yourpassword",
        database="ngo_connect"
    )

def detect_location_ip():
    try:
        with urllib.request.urlopen("http://ip-api.com/json", timeout=4) as r:
            data = json.loads(r.read().decode("utf-8"))
            if data.get("status") == "success":
                return {"city": data.get("city"), "region": data.get("regionName"),
                        "country": data.get("country"), "lat": data.get("lat"), "lon": data.get("lon")}
    except Exception:
        return None
    return None


def open_maps_for(query: str):
    q = urllib.parse.quote_plus(query)
    webbrowser.open(f"https://www.google.com/maps/search/?api=1&query={q}")


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# -----------------------
# Simple Calendar popup
# -----------------------
class SimpleCalendar(tk.Toplevel):
    def __init__(self, parent, callback, start_date=None):
        super().__init__(parent)
        self.title("Select Date")
        self.callback = callback
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        start = start_date if start_date else datetime.now(timezone.utc)
        self.month = start.month
        self.year = start.year
        self._build()

    def _build(self):
        header = ttk.Frame(self)
        header.pack(padx=8, pady=6)
        ttk.Button(header, text="<", width=3, command=self._prev_month).pack(side="left")
        self.title_lbl = ttk.Label(header, text=f"{calendar.month_name[self.month]} {self.year}", width=20, anchor="center")
        self.title_lbl.pack(side="left", padx=6)
        ttk.Button(header, text=">", width=3, command=self._next_month).pack(side="left")
        cal_frame = ttk.Frame(self)
        cal_frame.pack(padx=8, pady=6)
        self._draw_calendar(cal_frame)

    def _draw_calendar(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for c, d in enumerate(days):
            ttk.Label(parent, text=d, width=4, anchor="center").grid(row=0, column=c)
        m = calendar.monthcalendar(self.year, self.month)
        for r, week in enumerate(m, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    ttk.Label(parent, text="", width=4).grid(row=r, column=c, padx=2, pady=2)
                else:
                    ttk.Button(parent, text=str(day), width=4, command=lambda dd=day: self._select(dd)).grid(row=r, column=c, padx=2, pady=2)

    def _prev_month(self):
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self.title_lbl.config(text=f"{calendar.month_name[self.month]} {self.year}")
        self._draw_calendar(self.winfo_children()[1])

    def _next_month(self):
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self.title_lbl.config(text=f"{calendar.month_name[self.month]} {self.year}")
        self._draw_calendar(self.winfo_children()[1])

    def _select(self, day):
        dt = datetime(self.year, self.month, day)
        self.callback(dt)
        self.grab_release()
        self.destroy()


# -----------------------
# Main App
# -----------------------
class NGOApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NGO Connect Hub")
        self.geometry("1200x760")
        self.minsize(1000, 600)
        self.configure(bg=APP_BG)

        self.current_user = None
        self.user_location = None

        # persistent frames
        self.sidebar = ttk.Frame(self, width=300)
        self.sidebar.pack(side="left", fill="y", padx=(12, 6), pady=12)
        self.sidebar.pack_propagate(False)

        self.main_area = ttk.Frame(self)
        self.main_area.pack(side="right", fill="both", expand=True, padx=(6, 12), pady=12)

        self.content_frame = None

        # style attempt
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.sidebar_loc_label = None
        self.show_login()

    # -----------------------
    # Helpers
    # -----------------------
    def clear_content(self):
        if self.content_frame:
            try:
                self.content_frame.destroy()
            except Exception:
                pass
        self.content_frame = ttk.Frame(self.main_area)
        self.content_frame.pack(fill="both", expand=True)

    def _get_initials(self, name):
        parts = [p for p in name.split() if p]
        if not parts:
            return "U"
        if len(parts) == 1:
            return parts[0][0].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def _detect_location(self):
        loc = detect_location_ip()
        if loc:
            self.user_location = loc
            if self.sidebar_loc_label:
                city = loc.get("city") or ""
                region = loc.get("region") or ""
                country = loc.get("country") or ""
                self.sidebar_loc_label.config(text=f"Location: {city}, {region}, {country}")
            messagebox.showinfo("Location", f"Detected: {loc.get('city')}, {loc.get('country')}")
        else:
            messagebox.showerror("Location", "Could not detect location.")

    # -----------------------
    # Sidebar builders
    # -----------------------
    def build_sidebar_logged_out_ui(self):
        for c in self.sidebar.winfo_children():
            c.destroy()
        ttk.Label(self.sidebar, text="🌍 NGO Connect Hub", font=("Segoe UI", 16, "bold")).pack(pady=(12, 6))
        ttk.Label(self.sidebar, text="Connect NGOs & Volunteers", font=("Segoe UI", 10)).pack(pady=(0, 12))

    def build_sidebar_logged_in_ui(self):
        for c in self.sidebar.winfo_children():
            c.destroy()

        header = ttk.Frame(self.sidebar)
        header.pack(pady=(8, 10), anchor="w", fill="x")

        initials = self._get_initials(self.current_user.get("name", ""))
        canvas = tk.Canvas(header, width=48, height=48, highlightthickness=0, bg=APP_BG)
        canvas.pack(side="left", padx=(10, 8))
        canvas.create_oval(2, 2, 46, 46, fill=ACCENT_COLOR, outline=ACCENT_COLOR)
        canvas.create_text(24, 24, text=initials, fill="white", font=("Segoe UI", 10, "bold"))
        canvas.bind("<Button-1>", lambda e: self.show_profile())

        ttk.Label(header, text=self.current_user.get("name", ""), font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(header, text=self.current_user.get("role", ""), font=("Segoe UI", 9)).pack(anchor="w")

        # persistent location label
        self.sidebar_loc_label = ttk.Label(self.sidebar, text="Location: Unknown", font=("Segoe UI", 9), foreground="gray")
        self.sidebar_loc_label.pack(anchor="w", padx=10, pady=(6, 8))
        if self.user_location:
            city = self.user_location.get("city") or ""
            region = self.user_location.get("region") or ""
            country = self.user_location.get("country") or ""
            self.sidebar_loc_label.config(text=f"Location: {city}, {region}, {country}")

        ttk.Separator(self.sidebar).pack(fill="x", pady=6, padx=8)

        ttk.Button(self.sidebar, text="Home", command=lambda: self.show_home()).pack(fill="x", padx=8, pady=6)

        role = self.current_user.get("role")
        if role == "NGO":
            ttk.Button(self.sidebar, text="Dashboard", command=lambda: self.show_ngo_dashboard()).pack(fill="x", padx=8, pady=6)
            ttk.Button(self.sidebar, text="Post New Event", command=lambda: self.show_post_event()).pack(fill="x", padx=8, pady=6)
            ttk.Button(self.sidebar, text="My Events & Signups", command=lambda: self.show_ngo_events()).pack(fill="x", padx=8, pady=6)
            ttk.Button(self.sidebar, text="All NGOs", command=lambda: self.show_listings()).pack(fill="x", padx=8, pady=6)
        else:
            ttk.Button(self.sidebar, text="NGO Directory", command=lambda: self.show_listings()).pack(fill="x", padx=8, pady=6)
            ttk.Button(self.sidebar, text="Upcoming Events", command=lambda: self.show_events()).pack(fill="x", padx=8, pady=6)
            ttk.Button(self.sidebar, text="My NGOs", command=lambda: self.show_joined_ngos()).pack(fill="x", padx=8, pady=6)

        ttk.Separator(self.sidebar).pack(fill="x", pady=10, padx=8)
        ttk.Button(self.sidebar, text="Contact Support", command=lambda: self.show_contact()).pack(fill="x", padx=8, pady=6)
        ttk.Button(self.sidebar, text="About", command=lambda: self.show_about()).pack(fill="x", padx=8, pady=6)
        ttk.Button(self.sidebar, text="Logout", command=lambda: self.logout()).pack(side="bottom", fill="x", padx=8, pady=8)

    # -----------------------
    # Authentication / Registration
    # -----------------------
    def show_login(self):
        self.build_sidebar_logged_out_ui()
        self.clear_content()
        frame = ttk.Frame(self.content_frame, padding=14)
        frame.pack(expand=True)

        ttk.Label(frame, text="Welcome to NGO Connect Hub", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(frame, text="Sign in to continue", font=("Segoe UI", 10)).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ttk.Label(frame, text="Email:").grid(row=2, column=0, sticky="e", padx=6, pady=6)
        email_e = ttk.Entry(frame, width=44)
        email_e.grid(row=2, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(frame, text="Password:").grid(row=3, column=0, sticky="e", padx=6, pady=6)
        pw_e = ttk.Entry(frame, show="*", width=44)
        pw_e.grid(row=3, column=1, sticky="w", padx=6, pady=6)

        def try_login():
            email = email_e.get().strip().lower()
            pw = pw_e.get()
            if not email or not pw:
                messagebox.showwarning("Missing", "Please enter both email and password.")
                return
            
            conn = connect_db()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()

            if not user or user["password"] != _hash_password(pw):
                messagebox.showerror("Invalid", "Email or password incorrect.")
                return
            
            self.current_user = user
            self.build_sidebar_logged_in_ui()
            self.show_home()

        btns = ttk.Frame(frame)
        btns.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        tk.Button(btns, text="Login", bg=ACCENT_COLOR, fg="white", bd=0, padx=8, pady=6, command=try_login).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Register (NGO)", command=lambda: self.show_register_ngo()).pack(side="left", padx=4)
        ttk.Button(btns, text="Register (Volunteer)", command=lambda: self.show_register_volunteer()).pack(side="left", padx=4)

    def show_register_ngo(self):
        self.clear_content()
        ttk.Label(self.content_frame, text="Register NGO — NGO Connect Hub", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 8))
        form = ttk.Frame(self.content_frame)
        form.pack(anchor="w", pady=6)

        def field(label_text, row, width=48):
            ttk.Label(form, text=label_text).grid(row=row, column=0, sticky="e", padx=6, pady=6)
            e = ttk.Entry(form, width=width)
            e.grid(row=row, column=1, padx=6, pady=6, sticky="w")
            return e

        name_e = field("NGO Name:", 0)
        ttk.Label(form, text="Category:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        cat_cb = ttk.Combobox(form, values=CATEGORIES, state="readonly", width=36)
        cat_cb.grid(row=1, column=1, padx=6, pady=6, sticky="w")
        cat_cb.set(CATEGORIES[0])

        city_e = field("City:", 2)
        email_e = field("Contact Email:", 3)
        phone_e = field("Phone (10 digits):", 4)
        pw_e = field("Password:", 5)
        ttk.Label(form, text="Description:").grid(row=6, column=0, sticky="ne", padx=6, pady=6)
        desc_t = tk.Text(form, width=48, height=4)
        desc_t.grid(row=6, column=1, padx=6, pady=6, sticky="w")

        ttk.Label(form, text="Latitude (optional):").grid(row=7, column=0, sticky="e", padx=6, pady=6)
        lat_e = ttk.Entry(form, width=24)
        lat_e.grid(row=7, column=1, sticky="w", padx=6, pady=6)
        ttk.Label(form, text="Longitude (optional):").grid(row=8, column=0, sticky="e", padx=6, pady=6)
        lon_e = ttk.Entry(form, width=24)
        lon_e.grid(row=8, column=1, sticky="w", padx=6, pady=6)

        actions = ttk.Frame(self.content_frame)
        actions.pack(pady=8)

        def save():
            name = name_e.get().strip()
            cat = cat_cb.get().strip()
            city = city_e.get().strip()
            email = email_e.get().strip().lower()
            phone = phone_e.get().strip()
            pw = pw_e.get()
            desc = desc_t.get("1.0", "end").strip()

            if not name or not cat or not city or not email or not phone or not pw:
                messagebox.showerror("Missing", "Please fill all required fields.")
                return
            if "@" not in email or "." not in email:
                messagebox.showerror("Invalid", "Please enter a valid email.")
                return
            if not phone.isdigit() or len(phone) != 10:
                messagebox.showerror("Invalid", "Phone must be exactly 10 digits.")
                return
            if email in self.db.get("users", {}):
                messagebox.showerror("Exists", "An account with that email already exists.")
                return

            conn = connect_db()
            cursor = conn.cursor()

            cursor.execute("SELECT email FROM users WHERE email=%s",(email,))
            if cursor.fetchone():
                messagebox.showerror("Exists","Email already registered.")
                conn.close()
                return

            cursor.execute("INSERT INTO users (email,password,role,name,phone) VALUES (%s,%s,%s,%s,%s)",(email,_hash_password(pw),"NGO",name,phone))
            cursor.execute("INSERT INTO ngos (name,type,city,description,email,phone) VALUES (%s,%s,%s,%s,%s,%s)",(name,cat,city,desc,email,phone))
            conn.commit()

            messagebox.showinfo("Registered", "NGO registered successfully. Please login.")
            self.show_login()

        ttk.Button(actions, text="Register NGO", command=save).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Back", command=lambda: self.show_login()).pack(side="left")

    def show_register_volunteer(self):
        self.clear_content()
        ttk.Label(self.content_frame, text="Volunteer Sign Up — NGO Connect Hub", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 8))
        form = ttk.Frame(self.content_frame)
        form.pack(anchor="w", pady=6)

        ttk.Label(form, text="Full Name:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        name_e = ttk.Entry(form, width=48)
        name_e.grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(form, text="Email:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        email_e = ttk.Entry(form, width=48)
        email_e.grid(row=1, column=1, padx=6, pady=6)
        ttk.Label(form, text="Phone (10 digits):").grid(row=2, column=0, sticky="e", padx=6, pady=6)
        phone_e = ttk.Entry(form, width=48)
        phone_e.grid(row=2, column=1, padx=6, pady=6)
        ttk.Label(form, text="Password:").grid(row=3, column=0, sticky="e", padx=6, pady=6)
        pw_e = ttk.Entry(form, show="*", width=48)
        pw_e.grid(row=3, column=1, padx=6, pady=6)

        ttk.Label(form, text="Follow categories (ctrl-click to multi):").grid(row=4, column=0, sticky="ne", padx=6, pady=6)
        listbox = tk.Listbox(form, selectmode="multiple", height=6, exportselection=0)
        for c in CATEGORIES:
            listbox.insert("end", c)
        listbox.grid(row=4, column=1, padx=6, pady=6, sticky="w")

        actions = ttk.Frame(self.content_frame)
        actions.pack(pady=8)

        def save_vol():
            name = name_e.get().strip()
            email = email_e.get().strip().lower()
            phone = phone_e.get().strip()
            pw = pw_e.get()
            
            if not name or not email or not phone or not pw:
                messagebox.showerror("Missing", "Please fill all required fields.")
                return
            if "@" not in email or "." not in email:
                messagebox.showerror("Invalid", "Enter valid email.")
                return
            if not phone.isdigit() or len(phone) != 10:
                messagebox.showerror("Invalid", "Phone must be 10 digits.")
                return
            if email in self.db.get("users", {}):
                messagebox.showerror("Exists", "Account already exists.")
                return
            conn = connect_db()
            cursor = conn.cursor()

            cursor.execute("SELECT email FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                messagebox.showerror("Exists", "Account already exists.")
                conn.close()
                return

            cursor.execute("INSERT INTO users (email,password,role,name,phone) VALUES (%s,%s,%s,%s,%s)",(email,_hash_password(pw),"Volunteer",name,phone))
            conn.commit()

            messagebox.showinfo("Registered", "Volunteer account created. Please login.")
            self.show_login()

        ttk.Button(actions, text="Join Now", command=save_vol).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Back", command=lambda: self.show_login()).pack(side="left")

    # -----------------------
    # Home
    # -----------------------
    def show_home(self):
        if not self.current_user:
            self.show_login()
            return
        self.clear_content()
        # rebuild sidebar UI to reflect possible changes
        self.build_sidebar_logged_in_ui()

        top = ttk.Frame(self.content_frame)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text=f"Welcome, {self.current_user.get('name')}", font=("Segoe UI", 16, "bold")).pack(side="left", padx=6)
        ttk.Button(top, text="Detect Location", command=lambda: self._detect_location()).pack(side="right", padx=6)

        body = ttk.Frame(self.content_frame)
        body.pack(fill="both", expand=True, pady=(8, 0))
        if self.current_user.get("role") == "NGO":
            self.show_ngo_dashboard(parent=body)
        else:
            self._render_vol_home(parent=body)

    # -----------------------
    # Volunteer Home (follows & highlights)
    # -----------------------
    def _render_vol_home(self, parent):
        ttk.Label(parent, text="Volunteer Dashboard", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))
        follows = self.current_user.get("follows", [])
        frame = ttk.Frame(parent)
        frame.pack(fill="x")
        ttk.Label(frame, text="Followed categories: " + (", ".join(follows) if follows else "None")).pack(side="left", padx=6)
        ttk.Button(frame, text="Edit Follows", command=lambda: self.show_profile()).pack(side="left", padx=6)

        ttk.Label(parent, text="Upcoming Events", font=("Segoe UI", 12)).pack(anchor="w", pady=(6, 4))
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM events ORDER BY created_at DESC")
        evs = cursor.fetchall()
     
        if not evs:
            ttk.Label(parent, text="No upcoming events.", foreground="gray").pack(anchor="w", padx=6)
            return
        new_threshold = datetime.now(timezone.utc) - timedelta(days=3)
        for ev in evs:
            ngo = next((n for n in self.db.get("ngos", []) if n.get("name") == ev.get("ngo")), None)
            cat = ngo.get("type") if ngo else "Other"
            created_at = ev.get("created_at")
            is_new = False
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at)
                    if dt > new_threshold:
                        is_new = True
                except Exception:
                    is_new = False
            highlight = (cat in follows)
            card_bg = "#eaf6ff" if highlight else CARD_BG
            card = tk.Frame(parent, bg=card_bg, bd=1, relief="solid")
            card.pack(fill="x", padx=6, pady=6)
            left = tk.Frame(card, bg=card_bg)
            left.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            right = tk.Frame(card, bg=card_bg)
            right.pack(side="right", padx=8, pady=8)
            title = f"{ev['title']} — {ev['ngo_name']}"
            if is_new:
                title = "★ NEW  " + title
            tk.Label(left, text=title, bg=card_bg, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            tk.Label(left, text=f"{ev['date']} | {ev.get('loc','')} | {cat}", bg=card_bg, fg="gray30").pack(anchor="w")
            tk.Label(left, text=ev.get("desc", ""), bg=card_bg, wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))
            ttk.Button(right, text="Open NGO", command=lambda n=ev['ngo_name']: self.show_ngo_detail(n)).pack(fill="x", pady=4)
            tk.Button(right, text="Participate", bg=ACCENT_COLOR, fg="white", bd=0, command=lambda e=ev: self._signup_event_by_obj(e)).pack(fill="x", pady=4)

    # -----------------------
    # NGO Dashboard (impact stats)
    # -----------------------
    def show_ngo_dashboard(self, parent=None):
        if self.current_user.get("role") != "NGO":
            messagebox.showerror("Unauthorized", "Only NGOs have a dashboard.")
            return
        if parent is None:  
            self.clear_content()
            parent = ttk.Frame(self.content_frame)
            parent.pack(fill="both", expand=True)
        ttk.Label(parent, text="NGO Dashboard — Impact Stats", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 8))

        my_name = self.current_user.get("name")

        conn = connect_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM events WHERE ngo_name=%s",(my_name,))
        events = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM event_volunteers ev
            JOIN events e ON ev.event_id = e.id
            WHERE e.ngo_name=%s
            """,(my_name,))
        total_vols = cursor.fetchone()["total"]

        ngo_obj = next((n for n in self.db.get("ngos", []) if n.get("name") == my_name), None)
        total_members = len(ngo_obj.get("members", [])) if ngo_obj else 0

        category_counts = {}
        for ev in self.db.get("events", []):
            ngo = next((n for n in self.db.get("ngos", []) if n.get("name") == ev.get("ngo")), None)
            if ngo:
                cat = ngo.get("type", "Other")
                category_counts[cat] = category_counts.get(cat, 0) + len(ev.get("volunteers", []))
        popular = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        stats_frame = ttk.Frame(parent)
        stats_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(stats_frame, text=f"Total volunteers across your events: {total_vols}").pack(anchor="w", padx=6, pady=2)
        ttk.Label(stats_frame, text=f"Total registered members: {total_members}").pack(anchor="w", padx=6, pady=2)
        ttk.Label(stats_frame, text="Most popular event categories (by volunteers):").pack(anchor="w", padx=6, pady=(8, 2))
        if popular:
            for cat, cnt in popular:
                ttk.Label(stats_frame, text=f"• {cat}: {cnt} volunteer signups").pack(anchor="w", padx=14)
        else:
            ttk.Label(stats_frame, text="No activity yet.").pack(anchor="w", padx=14)

        ttk.Label(parent, text="Manage Volunteers (per event)", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(12, 4), padx=6)
        for ev in events:
            frame = ttk.Frame(parent)
            frame.pack(fill="x", padx=6, pady=6)
            ttk.Label(frame, text=f"{ev.get('title')} — {ev.get('date')} ({len(ev.get('volunteers', []))} signups)").pack(side="left")
            ttk.Button(frame, text="Manage", command=lambda e=ev: self.show_volunteer_manager(e)).pack(side="right")

    # -----------------------
    # Volunteer management (table)
    # -----------------------
    def show_volunteer_manager(self, event_obj):
        self.clear_content()
        ttk.Label(self.content_frame, text=f"Manage Volunteers — {event_obj.get('title')}", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 8))
        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True, padx=6, pady=6)
        cols = ("name", "phone", "email", "verified", "checked_in")
        tree = ttk.Treeview(container, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=140 if c in ("name", "email") else 90, anchor="center")
        tree.pack(fill="both", expand=True, side="left")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        conn = connect_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT name,phone,email,verified,checked_in
            FROM event_volunteers
            WHERE event_id=%s
            """,(event_obj["id"],))

        vols = cursor.fetchall()

        for v in vols:
            v.setdefault("verified", False)
            v.setdefault("checked_in", False)
        for v in vols:
            tree.insert("", "end", iid=v.get("email"), values=(v.get("name"), v.get("phone"), v.get("email"),
                                                               "Yes" if v.get("verified") else "No",
                                                               "Yes" if v.get("checked_in") else "No"))

        btns = ttk.Frame(self.content_frame)
        btns.pack(pady=8)

        def _set_verified(val: bool):
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Select a volunteer row.")
                return
            email = sel[0]
            for vv in vols:
                if vv.get("email") == email:
                    vv["verified"] = val
                    break
            tree.set(email, "verified", "Yes" if val else "No")


        def _set_checked(val: bool):
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Select a volunteer row.")
                return
            email = sel[0]
            for vv in vols:
                if vv.get("email") == email:
                    vv["checked_in"] = val
                    break
            tree.set(email, "checked_in", "Yes" if val else "No")

        ttk.Button(btns, text="Mark Verified", command=lambda: _set_verified(True)).pack(side="left", padx=6)
        ttk.Button(btns, text="Unverify", command=lambda: _set_verified(False)).pack(side="left", padx=6)
        ttk.Button(btns, text="Check-in", command=lambda: _set_checked(True)).pack(side="left", padx=6)
        ttk.Button(btns, text="Undo Check-in", command=lambda: _set_checked(False)).pack(side="left", padx=6)
        ttk.Button(btns, text="Back", command=lambda: self.show_ngo_dashboard()).pack(side="right", padx=6)

    # -----------------------
    # Listings with category filter & sorting
    # -----------------------
    def show_listings(self):
        self.clear_content()
        top = ttk.Frame(self.content_frame)
        top.pack(fill="x")
        ttk.Label(top, text="NGO Directory", font=("Segoe UI", 14, "bold")).pack(side="left", padx=6)

        search_var = tk.StringVar()
        search_e = ttk.Entry(top, textvariable=search_var, width=36)
        search_e.pack(side="right", padx=6)
        ttk.Button(top, text="Search", command=lambda: self._render_listings(search_var.get(), cat_var.get(), sort_var.get())).pack(side="right", padx=6)

        cat_var = tk.StringVar(value="All")
        cat_cb = ttk.Combobox(top, values=["All"] + CATEGORIES, textvariable=cat_var, state="readonly", width=20)
        cat_cb.pack(side="right", padx=6)
        cat_cb.set("All")

        sort_var = tk.StringVar(value="Name")
        sort_cb = ttk.Combobox(top, values=["Name", "City", "Category"], textvariable=sort_var, state="readonly", width=12)
        sort_cb.pack(side="right", padx=6)
        sort_cb.set("Name")

        ttk.Button(top, text="Near Me", command=lambda: self._near_me_search()).pack(side="right", padx=6)

        self._render_listings("", "All", "Name")

    def _near_me_search(self):
        loc = detect_location_ip()
        if not loc:
            messagebox.showerror("Location", "Could not detect location.")
            return
        self.user_location = loc
        city = loc.get("city", "") or ""
        self._render_listings(city, "All", "Name")

    def _render_listings(self, query: str, category: str, sort_by: str):
        children = list(self.content_frame.winfo_children())
        for w in children[1:]:
            try:
                w.destroy()
            except Exception:
                pass

        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True, pady=(8, 0))
        q = (query or "").strip().lower()
        ngos = list(self.db.get("ngos", []))

        if category and category != "All":
            ngos = [n for n in ngos if n.get("type") == category]

        if q:
            ngos = [n for n in ngos if q in (n.get("name", "") + " " + n.get("city", "") + " " + n.get("type", "")).lower()]

        if sort_by == "Name":
            ngos.sort(key=lambda x: x.get("name", "").lower())
        elif sort_by == "City":
            ngos.sort(key=lambda x: x.get("city", "").lower())
        elif sort_by == "Category":
            ngos.sort(key=lambda x: x.get("type", "").lower())

        if not ngos:
            ttk.Label(container, text="No NGOs found.", foreground="red").pack(pady=20)
            return

        for ngo in ngos:
            card = tk.Frame(container, bg=CARD_BG, bd=1, relief="solid")
            card.pack(fill="x", padx=6, pady=6)
            left = tk.Frame(card, bg=CARD_BG)
            left.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            right = tk.Frame(card, bg=CARD_BG)
            right.pack(side="right", padx=8, pady=8)
            tk.Label(left, text=f"{ngo['name']} — {ngo.get('type','')}", bg=CARD_BG, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            tk.Label(left, text=f"{ngo.get('city','')}", bg=CARD_BG, fg="gray30").pack(anchor="w")
            tk.Label(left, text=ngo.get("desc", ""), bg=CARD_BG, wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))
            ttk.Button(right, text="View Events", command=lambda n=ngo['name']: self.show_events(filter_ngo=n)).pack(fill="x", pady=4)
            ttk.Button(right, text="Open in Maps", command=lambda n=ngo['name']: open_maps_for(n)).pack(fill="x", pady=4)
            if self.current_user.get("role") == "Volunteer":
                ttk.Button(right, text="Join NGO", command=lambda n=ngo: self._join_ngo(n)).pack(fill="x", pady=4)

    # -----------------------
    # Events & Posting
    # -----------------------
    def show_events(self, filter_ngo=None):
        self.clear_content()
        header = ttk.Frame(self.content_frame)
        header.pack(fill="x")
        title = "Upcoming Opportunities" if not filter_ngo else f"Events — {filter_ngo}"
        ttk.Label(header, text=title, font=("Segoe UI", 14, "bold")).pack(side="left", padx=6)
        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True, pady=(8, 0))
        
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()

        if not events:
            ttk.Label(container, text="No events to show.", foreground="gray").pack(pady=20)
            return
        new_threshold = datetime.now(timezone.utc) - timedelta(days=3)
        for ev in events:
            card = tk.Frame(container, bg=CARD_BG, bd=1, relief="solid")
            card.pack(fill="x", padx=6, pady=6)
            left = tk.Frame(card, bg=CARD_BG)
            left.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            right = tk.Frame(card, bg=CARD_BG)

            right.pack(side="right", padx=8, pady=8)
            cursor.execute("SELECT * FROM ngos WHERE name=%s",(ev["ngo_name"],))
            ngo = cursor.fetchone()

            cat = ngo.get("type") if ngo else "Other"
            created_at = ev.get("created_at")
            is_new = False

            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at)
                    if dt > new_threshold:
                        is_new = True
                except Exception:
                    is_new = False
            title = f"{ev['title']} — {ev['ngo_name']}"
            if is_new:
                title = "★ NEW  " + title
            tk.Label(left, text=title, bg=CARD_BG, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            tk.Label(left, text=f"When: {ev['date']} | Where: {ev.get('loc','')} | Category: {cat}", bg=CARD_BG, fg="gray30").pack(anchor="w")
            tk.Label(left, text=ev.get("desc", ""), bg=CARD_BG, wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))
            ttk.Button(right, text="Open in Maps", command=lambda e=ev: open_maps_for(f"{e.get('loc','')} {e.get('title','')}")).pack(fill="x", pady=4)
            if self.current_user.get("role") == "Volunteer":
                tk.Button(right, text="Participate", bg=ACCENT_COLOR, fg="white", bd=0, command=lambda e=ev: self._signup_event_by_obj(e)).pack(fill="x", pady=4)
                ttk.Button(right, text="Join NGO", command=lambda n=ev['ngo_name']: self._join_ngo_by_name(n)).pack(fill="x", pady=4)
            else:
                ttk.Label(right, text=f"Signups: {len(ev.get('volunteers', []))}").pack(pady=6)

    def show_post_event(self):
        if self.current_user.get("role") != "NGO":
            messagebox.showerror("Unauthorized", "Only NGOs may post events.")
            return
        self.clear_content()
        ttk.Label(self.content_frame, text="Post a Volunteer Event", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))
        form = ttk.Frame(self.content_frame)
        form.pack(anchor="w", pady=6)
        ttk.Label(form, text="Title:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        title_e = ttk.Entry(form, width=54)
        title_e.grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(form, text="Location:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        loc_e = ttk.Entry(form, width=54)
        loc_e.grid(row=1, column=1, padx=6, pady=6)

        ttk.Label(form, text="Date:").grid(row=2, column=0, sticky="e", padx=6, pady=6)
        date_var = tk.StringVar()
        date_entry = ttk.Entry(form, textvariable=date_var, width=30)
        date_entry.grid(row=2, column=1, sticky="w", padx=6, pady=6)

        def pick_date():
            def cb(dt):
                date_var.set(dt.strftime("%d %b %Y"))
            SimpleCalendar(self, callback=cb)
        ttk.Button(form, text="Pick Date", command=pick_date).grid(row=2, column=1, sticky="e", padx=6, pady=6)

        ttk.Label(form, text="Description:").grid(row=3, column=0, sticky="ne", padx=6, pady=6)
        desc_t = tk.Text(form, width=56, height=6)
        desc_t.grid(row=3, column=1, padx=6, pady=6)

        def submit():
            title = title_e.get().strip()
            loc = loc_e.get().strip()
            date_str = date_var.get().strip()
            desc = desc_t.get("1.0","end").strip()

            if not title or not loc or not date_str:
                messagebox.showerror("Missing", "Title, Location and Date required.")
                return
            ev = {"ngo": self.current_user.get("name"), "title": title, "date": date_str, "loc": loc,
                  "desc": desc_t.get("1.0", "end").strip(), "volunteers": [], "created_at": now_iso()}
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO events (ngo_name,title,date,location,description,created_at) VALUES (%s,%s,%s,%s,%s,NOW())",(self.current_user["name"],title,date_str,loc,desc))
            conn.commit()

        ttk.Button(self.content_frame, text="Broadcast Event", command=submit).pack(pady=(8, 0))

    def show_ngo_events(self):
        if self.current_user.get("role") != "NGO":
            messagebox.showerror("Unauthorized", "Only NGOs may manage events.")
            return
        my_name = self.current_user.get("name")
        self.clear_content()
        ttk.Label(self.content_frame, text="Manage Your Events", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))
        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True)
        
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM events WHERE ngo_name=%s",(my_name,))
        events = cursor.fetchall()

        if not events:
            ttk.Label(container, text="No events yet.").pack(pady=8)
            return
        for ev in events:
            card = tk.Frame(container, bg=CARD_BG, bd=1, relief="solid")
            card.pack(fill="x", padx=6, pady=6)
            left = tk.Frame(card, bg=CARD_BG)
            left.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            right = tk.Frame(card, bg=CARD_BG)
            right.pack(side="right", padx=8, pady=8)
            tk.Label(left, text=f"{ev['title']} — {ev['date']}", bg=CARD_BG, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            tk.Label(left, text=f"{ev.get('loc', '')}", bg=CARD_BG, fg="gray30").pack(anchor="w")
            tk.Label(left, text=ev.get("desc", ""), bg=CARD_BG, wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))
            ttk.Button(right, text="View Volunteers", command=lambda e=ev: self.show_volunteer_manager(e)).pack(pady=4)
            ttk.Button(right, text="Open in Maps", command=lambda e=ev: open_maps_for(f"{e.get('loc','')} {e.get('title','')}")).pack(pady=4)

    # -----------------------
    # Signup and Join helpers
    # -----------------------
    def _signup_event_by_obj(self, ev_obj):
        for i, e in enumerate(self.db.get("events", [])):
            if e.get("title") == ev_obj.get("title") and e.get("ngo") == ev_obj.get("ngo"):
                self._signup_event(i)
                return
        messagebox.showerror("Error", "Event not found.")

    def _signup_event(self, event_id):
        if self.current_user.get("role") != "Volunteer":
            messagebox.showerror("Unauthorized", "Only volunteers can sign up.")
            return

        conn = connect_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("INSERT INTO event_volunteers(event_id,name,phone,email,verified,checked_in) VALUES (%s,%s,%s,%s,%s,%s)",(event_id, self.current_user["name"], self.current_user["phone"], self.current_user["email"], False, False))
        conn.commit()    

        messagebox.showinfo("Signed Up", "You have successfully joine the event!")

    def _join_ngo(self, ngo_obj):
        if self.current_user.get("role") != "Volunteer":
            messagebox.showerror("Unauthorized", "Only volunteers can join NGOs.")
            return
        email = self.current_user.get("email")
        ngo_obj.setdefault("members", [])
        if any(m.get("email") == email for m in ngo_obj.get("members", [])):
            messagebox.showinfo("Joined", "You are already a member.")
            return
        
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            INSERT INTO ngo_members (ngo_name,name,email,phone)
            VALUES (%s,%s,%s,%s)
            """, (
            ngo_obj["name"],
            self.current_user["name"],
            self.current_user["email"],
            self.current_user["phone"]
            ))        
        
        conn.commit()
        
        messagebox.showinfo("Joined", f"You joined {ngo_obj.get('name')} as a member.")

    def _join_ngo_by_name(self, name):
        ngo = next((n for n in self.db.get("ngos", []) if n.get("name") == name), None)
        if not ngo:
            messagebox.showerror("Not found", "NGO not found.")
            return
        self._join_ngo(ngo)

    # -----------------------
    # Joined NGOs
    # -----------------------
    def show_joined_ngos(self):
        self.clear_content()
        ttk.Label(self.content_frame, text="My Joined NGOs", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))
        my_email = self.current_user.get("email")
        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True)
        found = 0
        for ngo in self.db.get("ngos", []):
            if any(m.get("email") == my_email for m in ngo.get("members", [])):
                found += 1
                card = tk.Frame(container, bg=CARD_BG, bd=1, relief="solid")
                card.pack(fill="x", padx=6, pady=6)
                left = tk.Frame(card, bg=CARD_BG)
                left.pack(side="left", fill="both", expand=True, padx=8, pady=8)
                right = tk.Frame(card, bg=CARD_BG)
                right.pack(side="right", padx=8, pady=8)
                tk.Label(left, text=f"{ngo['name']} — {ngo.get('type','')}", bg=CARD_BG, font=("Segoe UI", 10, "bold")).pack(anchor="w")
                tk.Label(left, text=ngo.get("desc", ""), bg=CARD_BG, wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))
                ttk.Button(right, text="View Events", command=lambda n=ngo['name']: self.show_events(filter_ngo=n)).pack(fill="x", pady=4)
        if found == 0:
            ttk.Label(container, text="You haven't joined any NGOs yet.", foreground="gray").pack(pady=20)

    # -----------------------
    # Contact / About / Profile
    # -----------------------
    def show_contact(self):
        self.clear_content()
        ttk.Label(self.content_frame, text="Contact Support", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Subject:").pack(anchor="w")
        subj = ttk.Entry(frame, width=80)
        subj.pack(pady=6)
        ttk.Label(frame, text="Message:").pack(anchor="w")
        body = tk.Text(frame, width=80, height=12)
        body.pack(pady=6)

        def submit():
            s = subj.get().strip()
            b = body.get("1.0", "end").strip()
            if not s or not b:
                messagebox.showwarning("Missing", "Please include subject and message.")
                return
            try:
                with open("support_mail_log.txt", "a", encoding="utf-8") as lf:
                    lf.write(json.dumps({"from": self.current_user.get("email"), "subject": s, "body": b, "ts": now_iso()}) + "\n")
            except Exception:
                pass
            messagebox.showinfo("Sent", "Support request logged locally.")
            self.show_home()

        ttk.Button(self.content_frame, text="Submit Message", command=submit).pack(pady=8)

    def show_about(self):
        self.clear_content()
        ttk.Label(self.content_frame, text="About NGO Connect Hub", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(self.content_frame, text="A friendly local-first platform to connect NGOs and volunteers. Use Profile to update your account details.").pack(anchor="w")

    def show_profile(self):
        if not self.current_user:
            return
        self.clear_content()
        ttk.Label(self.content_frame, text="Profile", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 8))
        form = ttk.Frame(self.content_frame)
        form.pack(anchor="w", pady=6)
        ttk.Label(form, text="Email:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        ttk.Label(form, text=self.current_user.get("email", ""), font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="w", padx=6, pady=6)
        ttk.Label(form, text="Name:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        name_e = ttk.Entry(form, width=48)
        name_e.grid(row=1, column=1, padx=6, pady=6)
        name_e.insert(0, self.current_user.get("name", ""))
        ttk.Label(form, text="Phone (10 digits):").grid(row=2, column=0, sticky="e", padx=6, pady=6)
        phone_e = ttk.Entry(form, width=48)
        phone_e.grid(row=2, column=1, padx=6, pady=6)
        phone_e.insert(0, self.current_user.get("phone", ""))
        ttk.Label(form, text="Role:").grid(row=3, column=0, sticky="e", padx=6, pady=6)
        ttk.Label(form, text=self.current_user.get("role", "")).grid(row=3, column=1, sticky="w", padx=6, pady=6)
        ttk.Label(form, text="Change Password (leave blank to keep):").grid(row=4, column=0, sticky="e", padx=6, pady=6)
        pw_e = ttk.Entry(form, show="*", width=48)
        pw_e.grid(row=4, column=1, padx=6, pady=6)

        follows = self.current_user.get("follows", []) if self.current_user.get("role") == "Volunteer" else []
        ttk.Label(form, text="Follow categories (ctrl-click to multi):").grid(row=5, column=0, sticky="ne", padx=6, pady=6)
        listbox = tk.Listbox(form, selectmode="multiple", height=6, exportselection=0)
        for c in CATEGORIES:
            listbox.insert("end", c)
        # preselect follows
        for i, c in enumerate(CATEGORIES):
            if c in follows:
                listbox.selection_set(i)
        listbox.grid(row=5, column=1, padx=6, pady=6, sticky="w")

        actions = ttk.Frame(self.content_frame)
        actions.pack(pady=10)

        def save_profile():
            name = name_e.get().strip()
            phone = phone_e.get().strip()
            newpw = pw_e.get()
            sel = [listbox.get(i) for i in listbox.curselection()]

            if not name or not phone:
                messagebox.showerror("Missing", "Name and Phone are required.")
                return

            if not phone.isdigit() or len(phone) != 10:
                messagebox.showerror("Invalid", "Phone must be exactly 10 digits.")
                return

            email = self.current_user.get("email")

            conn = connect_db()
            cursor = conn.cursor()

            # Update password only if user entered a new one
            if newpw:
                cursor.execute(
                    "UPDATE users SET name=%s, phone=%s, password=%s WHERE email=%s",
                    (name, phone, _hash_password(newpw), email)
                )

            else:
                cursor.execute("""
                    UPDATE users
                    SET name=%s, phone=%s
                    WHERE email=%s
                """, (name, phone, email))

            conn.commit()
            conn.close()

            # Update current session user
            self.current_user.update({
                "name": name,
                "phone": phone,
                "follows": sel
            })

            self.build_sidebar_logged_in_ui()

            messagebox.showinfo("Saved", "Profile updated.")
            self.show_home()

        ttk.Button(actions, text="Save Profile", command=save_profile).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Cancel", command=lambda: self.show_home()).pack(side="left")

    def _show_vols(self, event_obj):
        cursor.execute("SELECT name,phone,email,verified,checked_in FROM event_volunteers WHERE event_id=%s", (event_obj["id"],))
        vols = cursor.fetchall()
        
        if not vols:
            messagebox.showinfo("Volunteers", "No volunteers yet.")
            return
        txt = "\n".join([f"• {v.get('name')} — {v.get('phone')} — {v.get('email')} (Verified: {v.get('verified', False)}, Checked-in: {v.get('checked_in', False)})" for v in vols])
        messagebox.showinfo(f"Volunteers for {event_obj.get('title')}", txt)

    # -----------------------
    # Logout
    # -----------------------
    def logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            self.current_user = None
            self.user_location = None
            self.build_sidebar_logged_out_ui()
            self.show_login()


# -----------------------
# Run the app
# -----------------------
if __name__ == "__main__":
    app = NGOApp()
    app.mainloop()
