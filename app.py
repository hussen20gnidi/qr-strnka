from flask import Flask, render_template, request, redirect, session, flash, send_from_directory
import sqlite3
import os
import qrcode
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secret123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")
QR_FOLDER = os.path.join(BASE_DIR, "qrcodes")

os.makedirs(QR_FOLDER, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qrcodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            file TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


def current_user():
    return session.get("user_id")


@app.route("/")
def index():
    if current_user():
        return redirect("/dashboard")
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if len(username) < 3:
            flash("Uživatelské jméno musí mít alespoň 3 znaky.")
            return redirect("/register")

        if len(password) < 3:
            flash("Heslo musí mít alespoň 3 znaky.")
            return redirect("/register")

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            conn.commit()
        except sqlite3.IntegrityError:
            flash("Tento uživatel už existuje.")
            return redirect("/register")
        finally:
            conn.close()

        flash("Registrace proběhla úspěšně.")
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Vyplň jméno i heslo.")
            return redirect("/login")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if not user or not check_password_hash(user["password"], password):
            flash("Špatné jméno nebo heslo.")
            return redirect("/login")

        session["user_id"] = user["id"]
        session["username"] = user["username"]

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
        "SELECT * FROM qrcodes WHERE user_id=? ORDER BY id DESC",
        (current_user(),)
    ).fetchall()
    conn.close()

    return render_template("dashboard.html", qrs=qrs)


@app.route("/create", methods=["GET", "POST"])
def create():
    if not current_user():
        return redirect("/login")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        data = request.form.get("data", "").strip()

        if not name or not data:
            flash("Vyplň název i obsah QR kódu.")
            return redirect("/create")

        safe_name = secure_filename(name)
        if not safe_name:
            safe_name = "qr"

        filename = f"user_{current_user()}_{safe_name}_{os.urandom(4).hex()}.png"
        path = os.path.join(QR_FOLDER, filename)

        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=4
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img.save(path)

        conn = get_db()
        conn.execute(
            "INSERT INTO qrcodes (user_id, name, data, file) VALUES (?, ?, ?, ?)",
            (current_user(), name, data, filename)
        )
        conn.commit()
        conn.close()

        flash("QR kód byl vytvořen.")
        return redirect("/dashboard")

    return render_template("create.html")


@app.route("/qr_image/<filename>")
def qr_image(filename):
    return send_from_directory(QR_FOLDER, filename)


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
        except FileNotFoundError:
            pass

        conn.execute("DELETE FROM qrcodes WHERE id=?", (id,))
        conn.commit()

    conn.close()
    return redirect("/dashboard")


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
        except FileNotFoundError:
            pass

    conn.execute("DELETE FROM qrcodes WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
