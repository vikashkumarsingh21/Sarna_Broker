from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "sarna_broker_secret_key"

# ---------------- CONFIG ----------------
UPLOAD_FOLDER = "static/uploads/crops"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect(
        "database.db",
        timeout=10,
        check_same_thread=False
    )

def init_db():
    con = get_db()
    cur = con.cursor()

    # USERS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # CROPS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS crops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_id INTEGER,
        crop TEXT,
        variety TEXT,
        price INTEGER,
        quantity INTEGER,
        location TEXT,
        image TEXT,
        sold INTEGER DEFAULT 0
    )
    """)

    # DEFAULT ADMIN
    cur.execute("SELECT * FROM users WHERE role='admin'")
    if not cur.fetchone():
        cur.execute("""
        INSERT INTO users (name, email, password, role)
        VALUES ('Admin', 'admin@sarna.com', 'admin123', 'admin')
        """)

    con.commit()
    con.close()

init_db()

# ---------------- AUTH ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        con = get_db()
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        )
        user = cur.fetchone()
        con.close()

        if user:
            session["user_id"] = user[0]
            session["role"] = user[4]

            if user[4] == "farmer":
                return redirect("/my_commodity")
            elif user[4] == "buyer":
                return redirect("/market")
            else:
                return redirect("/admin")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        con = get_db()
        cur = con.cursor()
        try:
            cur.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
            """, (
                request.form["name"],
                request.form["email"],
                request.form["password"],
                request.form["role"]
            ))
            con.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            con.close()

        return redirect("/")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- FARMER ----------------
@app.route("/post_crop", methods=["GET", "POST"])
def post_crop():
    if session.get("role") != "farmer":
        return redirect("/")

    if request.method == "POST":
        image = request.files.get("image")
        filename = None

        if image and image.filename:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        con = get_db()
        cur = con.cursor()
        cur.execute("""
        INSERT INTO crops (farmer_id, crop, variety, price, quantity, location, image)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            request.form["crop"],
            request.form["variety"],
            request.form["price"],
            request.form["quantity"],
            request.form["location"],
            filename
        ))
        con.commit()
        con.close()

        return redirect("/my_commodity")

    return render_template("post_crop.html")


@app.route("/my_commodity")
def my_commodity():
    if session.get("role") != "farmer":
        return redirect("/")

    con = get_db()
    cur = con.cursor()
    cur.execute("""
    SELECT * FROM crops WHERE farmer_id=?
    """, (session["user_id"],))
    crops = cur.fetchall()
    con.close()

    return render_template("my_commodity.html", crops=crops)


@app.route("/delete_crop/<int:id>")
def delete_crop(id):
    if session.get("role") != "farmer":
        return redirect("/")

    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM crops WHERE id=?", (id,))
    con.commit()
    con.close()

    return redirect("/my_commodity")


@app.route("/mark_sold/<int:id>")
def mark_sold(id):
    if session.get("role") != "farmer":
        return redirect("/")

    con = get_db()
    cur = con.cursor()
    cur.execute("UPDATE crops SET sold=1 WHERE id=?", (id,))
    con.commit()
    con.close()

    return redirect("/my_commodity")

# ---------------- MARKET (BUYER) ----------------
@app.route("/market")
def market():
    con = get_db()
    cur = con.cursor()
    cur.execute("""
    SELECT crops.*, users.name
    FROM crops
    JOIN users ON crops.farmer_id = users.id
    WHERE sold = 0
    """)
    crops = cur.fetchall()
    con.close()

    return render_template("market.html", crops=crops)

# ---------------- PROFILE ----------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/")

    con = get_db()
    cur = con.cursor()
    cur.execute("""
    SELECT name, email, role FROM users WHERE id=?
    """, (session["user_id"],))
    user = cur.fetchone()
    con.close()

    return render_template("profile.html", user=user)

# ---------------- ADMIN ----------------
@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect("/")

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    cur.execute("SELECT * FROM crops")
    crops = cur.fetchall()
    con.close()

    return render_template("admin.html", users=users, crops=crops)

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
