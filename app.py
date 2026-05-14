from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import os
import qrcode
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

DB = "database.db"
QR_FOLDER = "static/qrcodes"

os.makedirs(QR_FOLDER, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS qrcodes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, data TEXT, file TEXT)")

    conn.commit()
    conn.close()

init_db()

def current_user():
    return session.get("user_id")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if len(username) < 3:
            flash("Username too short")
            return redirect("/register")

        if len(password) < 3:
            flash("Password too short")
            return redirect("/register")

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (username,password) VALUES (?,?)",
                (username, generate_password_hash(password))
            )
            conn.commit()

        except:
            flash("User already exists")
            return redirect("/register")

        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
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
            flash("Wrong username")
            return redirect("/login")

        if not check_password_hash(user["password"], password):
            flash("Wrong password")
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

@app.route("/create", methods=["GET","POST"])
def create():

    if not current_user():
        return redirect("/login")

    if request.method == "POST":

        name = request.form.get("name")
        data = request.form.get("data")

        if not name or not data:
            flash("Fill everything")
            return redirect("/create")

        filename = f"{current_user()}_{name}.png".replace(" ", "_")

        path = os.path.join(QR_FOLDER, filename)

        img = qrcode.make(data)
        img.save(path)

        conn = get_db()

        conn.execute(
            "INSERT INTO qrcodes (user_id,name,data,file) VALUES (?,?,?,?)",
            (current_user(), name, data, filename)
        )

        conn.commit()

        return redirect("/dashboard")

    return render_template("create.html")

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

if __name__ == "__main__":
    app.run(debug=True)
