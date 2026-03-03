import tkinter as tk
from tkinter import messagebox
import geocoder

class NGOApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NGO Connect Hub - Pro Edition")
        self.root.geometry("550x800")
        self.root.configure(bg="#f0f2f5")

        # Database: {email: [password, name, role, detail, type, [members]]}
        self.user_db = {
            "a@ngo.com": ["123", "Helping Hands", "NGO", "LIC-99", "Health", ["Aadi"]],
            "b@vol.com": ["123", "Aadi", "Volunteer", "9876543210", "N/A", []]
        }
        # Events: [Title, City, Date, Description, NGO_Name, [Volunteers]]
        self.events = [
            ["Winter Food Drive", "Mumbai", "15 Jan", "Providing hot meals to 200+ people.", "Helping Hands", ["Aadi"]],
            ["Clean City Drive", "Delhi", "22 Feb", "Planting trees and cleaning parks.", "Green Earth", []]
        ]
        
        self.current_user_email = None
        self.detected_city = "Unknown"
        self.main_menu()

    def clear(self):
        for widget in self.root.winfo_children(): widget.destroy()

    # --- LANDING PAGE ---
    def main_menu(self):
        self.clear()
        banner = tk.Frame(self.root, bg="#1a73e8", height=250); banner.pack(fill="x")
        tk.Label(banner, text="🌍\nNGO CONNECT", font=("Helvetica", 32, "bold"), fg="white", bg="#1a73e8").pack(pady=50)
        
        tk.Label(self.root, text="Empowering Change through Technology", font=("Arial", 10), bg="#f0f2f5", fg="#555").pack(pady=10)
        
        tk.Button(self.root, text="USER LOGIN", font=("Arial", 12, "bold"), width=25, height=2, bg="white", bd=2, command=self.login_page).pack(pady=15)
        tk.Button(self.root, text="CREATE NEW ACCOUNT", font=("Arial", 12, "bold"), width=25, height=2, bg="white", bd=2, command=self.reg_page).pack(pady=5)

    # --- REGISTRATION ---
    def reg_page(self):
        self.clear()
        tk.Label(self.root, text="SELECT ACCOUNT TYPE", font=("Arial", 18, "bold"), bg="#f0f2f5").pack(pady=50)
        tk.Button(self.root, text="I am a Volunteer", width=30, height=2, font=("Arial", 11), command=lambda: self.reg_form("Volunteer")).pack(pady=10)
        tk.Button(self.root, text="I am an NGO", width=30, height=2, font=("Arial", 11), command=lambda: self.reg_form("NGO")).pack(pady=10)
        tk.Button(self.root, text="← Back to Home", bg="#ccc", width=15, command=self.main_menu).pack(pady=40)

    def reg_form(self, role):
        self.clear()
        tk.Label(self.root, text=f"REGISTER AS {role.upper()}", font=("Arial", 16, "bold"), bg="#f0f2f5").pack(pady=20)
        
        form = tk.Frame(self.root, bg="#f0f2f5"); form.pack(pady=10)
        tk.Label(form, text="Email Address:", bg="#f0f2f5").grid(row=0, column=0, pady=8, sticky="w")
        e = tk.Entry(form, width=30); e.grid(row=0, column=1)
        
        tk.Label(form, text="Full Name/NGO Name:", bg="#f0f2f5").grid(row=1, column=0, pady=8, sticky="w")
        n = tk.Entry(form, width=30); n.grid(row=1, column=1)
        
        tk.Label(form, text="Set Password:", bg="#f0f2f5").grid(row=2, column=0, pady=8, sticky="w")
        p = tk.Entry(form, show="*", width=30); p.grid(row=2, column=1)

        cat_v = tk.StringVar(value="Education")
        if role == "Volunteer":
            tk.Label(form, text="Phone Number:", bg="#f0f2f5").grid(row=3, column=0, pady=8, sticky="w")
            ex = tk.Entry(form, width=30); ex.grid(row=3, column=1)
        else:
            tk.Label(form, text="License Number:", bg="#f0f2f5").grid(row=3, column=0, pady=8, sticky="w")
            ex = tk.Entry(form, width=30); ex.grid(row=3, column=1)
            tk.Label(form, text="NGO Category:", bg="#f0f2f5").grid(row=4, column=0, pady=8, sticky="w")
            tk.OptionMenu(form, cat_v, "Food", "Health", "Education", "Environment").grid(row=4, column=1, sticky="w")

        def submit():
            if "@" not in e.get() or len(p.get()) < 3:
                messagebox.showerror("Error", "Invalid Email or Password too short!")
            elif role == "Volunteer" and len(ex.get()) != 10:
                messagebox.showerror("Error", "Phone must be 10 digits!")
            else:
                self.user_db[e.get()] = [p.get(), n.get(), role, ex.get(), cat_v.get(), []]
                messagebox.showinfo("Success", "Registration Complete!"); self.main_menu()

        tk.Button(self.root, text="COMPLETE SIGNUP", bg="#1a73e8", fg="white", font=("Arial", 11, "bold"), width=25, height=2, command=submit).pack(pady=30)
        tk.Button(self.root, text="Back", command=self.reg_page).pack()

    # --- LOGIN ---
    def login_page(self):
        self.clear()
        tk.Label(self.root, text="LOGIN TO YOUR ACCOUNT", font=("Arial", 20, "bold"), bg="#f0f2f5").pack(pady=60)
        tk.Label(self.root, text="Email:").pack(); e_e = tk.Entry(self.root, width=35); e_e.pack(pady=5)
        tk.Label(self.root, text="Password:").pack(); p_e = tk.Entry(self.root, show="*", width=35); p_e.pack(pady=5)
        
        def handle():
            user = self.user_db.get(e_e.get())
            if user and user[0] == p_e.get():
                self.current_user_email = e_e.get(); self.dashboard()
            else: messagebox.showerror("Error", "Access Denied: Wrong Email/Pass")
            
        tk.Button(self.root, text="LOGIN NOW", bg="#28a745", fg="white", width=25, height=2, font=("Arial", 12, "bold"), command=handle).pack(pady=30)
        tk.Button(self.root, text="← Return to Home", command=self.main_menu).pack()

    # --- DASHBOARD ---
    def dashboard(self):
        self.clear()
        u = self.user_db[self.current_user_email]
        name, role = u[1], u[2]
        
        head = tk.Frame(self.root, bg="white", pady=25); head.pack(fill="x")
        tk.Label(head, text=f"Welcome, {name}", font=("Arial", 22, "bold"), bg="white").pack()
        tk.Label(head, text=f"Signed in as: {role} | {u[3]}", font=("Arial", 10), bg="white", fg="#666").pack()
        
        # Navigation Hub
        nav = tk.Frame(self.root, bg="#f0f2f5"); nav.pack(pady=25)
        tk.Button(nav, text="📅 EVENTS HUB", font=("Arial", 11, "bold"), width=20, height=2, command=self.view_events).pack(side="left", padx=10)
        tk.Button(nav, text="🏢 NGO DIRECTORY", font=("Arial", 11, "bold"), width=20, height=2, command=self.view_ngos).pack(side="left", padx=10)

        def locate():
            g = geocoder.ip('me'); self.detected_city = g.city if g.city else "Mumbai"; self.dashboard()
        tk.Button(self.root, text="📍 DETECT MY CITY", font=("Arial", 10), command=locate, bg="#e1e8f0").pack(pady=10)
        tk.Label(self.root, text=f"Currently browsing in: {self.detected_city}", font=("Arial", 11, "bold"), fg="#1a73e8", bg="#f0f2f5").pack()

        if role == "NGO":
            p_box = tk.LabelFrame(self.root, text="POST NEW EVENT", bg="white", padx=20, pady=20); p_box.pack(pady=30, fill="x", padx=40)
            tk.Label(p_box, text="Title:").grid(row=0, column=0); t_ent = tk.Entry(p_box, width=25); t_ent.grid(row=0, column=1)
            tk.Label(p_box, text="Desc:").grid(row=1, column=0); d_ent = tk.Entry(p_box, width=25); d_ent.grid(row=1, column=1)
            tk.Label(p_box, text="Date:").grid(row=2, column=0); dt_ent = tk.Entry(p_box, width=25); dt_ent.grid(row=2, column=1); dt_ent.insert(0, "30 Jan")
            def post():
                if t_ent.get(): self.events.append([t_ent.get(), self.detected_city, dt_ent.get(), d_ent.get(), name, []]); self.dashboard()
            tk.Button(p_box, text="POST TO FEED", bg="#28a745", fg="white", command=post).grid(row=3, columnspan=2, pady=10)
            tk.Label(self.root, text=f"NGO Members: {len(u[5])}", font=("Arial", 11, "bold"), bg="#f0f2f5").pack()

        tk.Button(self.root, text="LOGOUT", bg="#dc3545", fg="white", font=("Arial", 10, "bold"), width=20, command=self.main_menu).pack(side="bottom", pady=25)

    # --- EVENT FEED ---
    def view_events(self):
        self.clear()
        tk.Label(self.root, text="UPCOMING OPPORTUNITIES", font=("Arial", 18, "bold"), bg="#f0f2f5").pack(pady=30)
        for i, ev in enumerate(self.events):
            if self.detected_city == "Unknown" or ev[1] == self.detected_city:
                card = tk.Frame(self.root, bg="white", bd=1, relief="ridge", padx=15, pady=15); card.pack(fill="x", padx=40, pady=10)
                tk.Label(card, text=f"⭐ {ev[0]}\n📅 {ev[2]} | 📍 {ev[1]}\nNGO: {ev[4]}\nDetails: {ev[3]}", bg="white", justify="left", font=("Arial", 10)).pack(side="left")
                if self.user_db[self.current_user_email][2] == "Volunteer":
                    tk.Button(card, text="Join Event", bg="#1a73e8", fg="white", command=lambda idx=i: self.join_e(idx)).pack(side="right")
                else:
                    tk.Button(card, text=f"View Vols ({len(ev[5])})", command=lambda idx=i: messagebox.showinfo("Volunteers", "Joined:\n"+"\n".join(self.events[idx][5]) if self.events[idx][5] else "Empty")).pack(side="right")
        tk.Button(self.root, text="Back to Dashboard", font=("Arial", 10), command=self.dashboard).pack(pady=30)

    def join_e(self, idx):
        nm = self.user_db[self.current_user_email][1]
        if nm not in self.events[idx][5]: self.events[idx][5].append(nm); messagebox.showinfo("Success", "Registered for event!")
        self.view_events()

    # --- NGO LIST ---
    def view_ngos(self):
        self.clear()
        tk.Label(self.root, text="REGISTERED NGOs", font=("Arial", 18, "bold"), bg="#f0f2f5").pack(pady=30)
        for em, d in self.user_db.items():
            if d[2] == "NGO":
                card = tk.Frame(self.root, bg="white", bd=1, relief="ridge", padx=15, pady=15); card.pack(fill="x", padx=40, pady=10)
                tk.Label(card, text=f"🏢 {d[1]}\nSector: {d[4]}", bg="white", font=("Arial", 11, "bold")).pack(side="left")
                if self.user_db[self.current_user_email][2] == "Volunteer":
                    tk.Button(card, text="Become Member", bg="#28a745", fg="white", command=lambda ngo_e=em: self.join_n(ngo_e)).pack(side="right")
                else:
                    tk.Button(card, text="View Members", command=lambda n_list=d[5]: messagebox.showinfo("Members", "\n".join(n_list) if n_list else "No members")).pack(side="right")
        tk.Button(self.root, text="Back to Dashboard", font=("Arial", 10), command=self.dashboard).pack(pady=30)

    def join_n(self, ngo_e):
        nm = self.user_db[self.current_user_email][1]
        if nm not in self.user_db[ngo_e][5]: self.user_db[ngo_e][5].append(nm); messagebox.showinfo("Success", "Welcome to the NGO!")
        self.view_ngos()

if __name__ == "__main__":
    r = tk.Tk(); app = NGOApp(r); r.mainloop()
