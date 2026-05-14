from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
import os
import qrcode
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "secret123"

# ✅ stabilní cesta (funguje lokálně i na Renderu)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")
QR_FOLDER = os.path.join(BASE_DIR, "static", "qrcodes")

os.makedirs(QR_FOLDER, exist_ok=True)


# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS qrcodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            data TEXT,
            file TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


def current_user():
    return session.get("user_id")


# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Vyplň vše")
            return redirect("/register")

        if len(username) < 3 or len(password) < 3:
            flash("Příliš krátké")
            return redirect("/register")

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            conn.commit()
        except:
            flash("User existuje")
            return redirect("/register")

        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if not user:
            flash("Špatný login")
            return redirect("/login")

        if not check_password_hash(user["password"], password):
            flash("Špatné heslo")
            return redirect("/login")

        session["user_id"] = user["id"]
        return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/dashboard")
def dashboard():
    if not current_user():
        return redirect("/login")

    conn = get_db()

    qrs = conn.execute(
        "SELECT * FROM qrcodes WHERE user_id=?",
        (current_user(),)
    ).fetchall()

    return render_template("dashboard.html", qrs=qrs)


# ---------------- CREATE QR ----------------
@app.route("/create", methods=["GET", "POST"])
def create():
    if not current_user():
        return redirect("/login")

    if request.method == "POST":

        name = request.form.get("name")
        data = request.form.get("data")

        if not name or not data:
            flash("Vyplň vše")
            return redirect("/create")

        # bezpečný název souboru
        safe_name = secure_filename(name)
        filename = f"{current_user()}_{safe_name}.png"
        path = os.path.join(QR_FOLDER, filename)

        # ✅ správná generace QR
        img = qrcode.make(data)
        img.save(path)

        conn = get_db()
        conn.execute(
            "INSERT INTO qrcodes (user_id, name, data, file) VALUES (?, ?, ?, ?)",
            (current_user(), name, data, filename)
        )
        conn.commit()

        return redirect("/dashboard")

    return render_template("create.html")


# ---------------- DELETE QR ----------------
@app.route("/delete/<int:id>")
def delete(id):
    if not current_user():
        return redirect("/login")

    conn = get_db()

    qr = conn.execute(
        "SELECT * FROM qrcodes WHERE id=? AND user_id=?",
        (id, current_user())
    ).fetchone()

    if qr:
        try:
            os.remove(os.path.join(QR_FOLDER, qr["file"]))
        except:
            pass

        conn.execute("DELETE FROM qrcodes WHERE id=?", (id,))
        conn.commit()

    return redirect("/dashboard")


# ---------------- DELETE ACCOUNT ----------------
@app.route("/delete_account")
def delete_account():
    if not current_user():
        return redirect("/login")

    user_id = current_user()
    conn = get_db()

    qrs = conn.execute(
        "SELECT * FROM qrcodes WHERE user_id=?",
        (user_id,)
    ).fetchall()

    for qr in qrs:
        try:
            os.remove(os.path.join(QR_FOLDER, qr["file"]))
        except:
            pass

    conn.execute("DELETE FROM qrcodes WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()

    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
