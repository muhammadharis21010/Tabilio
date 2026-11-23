"""TABLIO - Food Ordering Management System (Flask + MySQL)."""
import csv, io, os
from functools import wraps

import pymysql
import pymysql.cursors
import qrcode
from flask import (Flask, Response, abort, flash, jsonify, redirect, render_template,
                   request, send_file, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me")
TAX = float(os.environ.get("TAX_PERCENT", "5"))
FLOW = ["placed", "preparing", "ready", "served", "billed"]
ROLE_STATUS = {"kitchen": {"preparing", "ready"}, "waiter": {"served"},
               "admin": {"preparing", "ready", "served"}}
HOME = {"admin": "/admin", "waiter": "/waiter", "kitchen": "/kitchen", "cashier": "/cashier"}


# ---------- database helpers ----------
def conn():
    return pymysql.connect(host=os.environ.get("DB_HOST", "localhost"),
                           user=os.environ.get("DB_USER", "root"),
                           password=os.environ.get("DB_PASSWORD", ""),
                           database=os.environ.get("DB_NAME", "tablio"),
                           charset="utf8mb4", autocommit=True,
                           cursorclass=pymysql.cursors.DictCursor)


def q(sql, args=(), one=False):
    con = conn()
    try:
        with con.cursor() as c:
            c.execute(sql, args)
            rows = c.fetchall()
            return (rows[0] if rows else None) if one else list(rows)
    finally:
        con.close()


def run(sql, args=()):
    con = conn()
    try:
        with con.cursor() as c:
            c.execute(sql, args)
            return c.lastrowid
    finally:
        con.close()


def login_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **k):
            if "uid" not in session:
                return redirect(url_for("login", next=request.path))
            if roles and session["role"] not in roles and session["role"] != "admin":
                abort(403)
            return f(*a, **k)
        return wrapper
    return deco


def bill_for(oid):
    items = q("SELECT oi.qty, oi.customization, m.name, m.price FROM order_items oi "
              "JOIN menu_items m ON m.id=oi.item_id WHERE oi.order_id=%s", (oid,))
    sub = sum(float(i["price"]) * i["qty"] for i in items)
    pct = float(q("SELECT COALESCE(MAX(discount_percent),0) AS p FROM deals WHERE active=1",
                  one=True)["p"])
    disc = round(sub * pct / 100, 2)
    tax = round((sub - disc) * TAX / 100, 2)
    return {"items": items, "subtotal": round(sub, 2), "discount_pct": pct, "discount": disc,
            "tax_pct": TAX, "tax": tax, "total": round(sub - disc + tax, 2)}


def refresh_table(tid):
    if q("SELECT 1 FROM waiter_calls WHERE table_id=%s AND resolved=0", (tid,), one=True):
        s = "needs_help"
    elif q("SELECT 1 FROM orders WHERE table_id=%s AND status<>'billed'", (tid,), one=True):
        s = "occupied"
    else:
        s = "free"
    run("UPDATE restaurant_tables SET status=%s WHERE id=%s", (s, tid))


# ---------- customer side ----------
@app.route("/")
def index():
    return render_template("index.html", tables=q("SELECT * FROM restaurant_tables ORDER BY id"))


@app.route("/t/<int:tid>")
def menu(tid):
    table = q("SELECT * FROM restaurant_tables WHERE id=%s", (tid,), one=True) or abort(404)
    cats = q("SELECT * FROM categories ORDER BY id")
    items = q("SELECT id,category_id,name,description,price,image_url FROM menu_items "
              "WHERE available=1 ORDER BY id")
    for i in items:
        i["price"] = float(i["price"])
    deals = q("SELECT title,description,discount_percent FROM deals WHERE active=1")
    return render_template("menu.html", table=table, cats=cats, items=items, deals=deals)


@app.post("/api/order")
def place_order():
    d = request.get_json(force=True)
    tid = int(d.get("table_id", 0))
    if not q("SELECT id FROM restaurant_tables WHERE id=%s", (tid,), one=True):
        return jsonify(error="Unknown table"), 404
    lines = [l for l in d.get("items", []) if int(l.get("qty", 0)) > 0]
    if not lines:
        return jsonify(error="Your cart is empty"), 400
    ids = [int(l["id"]) for l in lines]
    ok = {r["id"] for r in q("SELECT id FROM menu_items WHERE available=1 AND id IN (%s)"
                             % ",".join(["%s"] * len(ids)), ids)}
    if any(i not in ok for i in ids):
        return jsonify(error="An item is no longer available"), 400
    oid = run("INSERT INTO orders (table_id,notes) VALUES (%s,%s)",
              (tid, (d.get("notes") or "")[:255]))
    for l in lines:
        run("INSERT INTO order_items (order_id,item_id,qty,customization) VALUES (%s,%s,%s,%s)",
            (oid, int(l["id"]), min(int(l["qty"]), 20), (l.get("note") or "")[:200]))
    run("UPDATE restaurant_tables SET status='occupied' WHERE id=%s AND status='free'", (tid,))
    return jsonify(order_id=oid)


@app.route("/order/<int:oid>")
def order_page(oid):
    o = q("SELECT o.*, t.label FROM orders o JOIN restaurant_tables t ON t.id=o.table_id "
          "WHERE o.id=%s", (oid,), one=True) or abort(404)
    return render_template("order.html", o=o, bill=bill_for(oid), flow=FLOW[:4])


@app.get("/api/order/<int:oid>")
def order_json(oid):
    o = q("SELECT status FROM orders WHERE id=%s", (oid,), one=True) or abort(404)
    return jsonify(status=o["status"])


@app.post("/api/call")
def call_waiter():
    d = request.get_json(force=True)
    tid = int(d["table_id"])
    run("INSERT INTO waiter_calls (table_id,reason) VALUES (%s,%s)",
        (tid, (d.get("reason") or "Assistance")[:100]))
    run("UPDATE restaurant_tables SET status='needs_help' WHERE id=%s", (tid,))
    return jsonify(ok=True)


@app.post("/feedback")
def feedback():
    tid = int(request.form["table_id"])
    rating = max(1, min(5, int(request.form.get("rating", 5))))
    run("INSERT INTO feedback (table_id,rating,comment) VALUES (%s,%s,%s)",
        (tid, rating, request.form.get("comment", "")[:500]))
    flash("Thank you for your feedback!")
    return redirect(request.referrer or url_for("menu", tid=tid))


@app.route("/qr/<int:tid>.png")
def qr(tid):
    img = qrcode.make(request.host_url + "t/%d" % tid)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# ---------- authentication ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = q("SELECT * FROM users WHERE username=%s", (request.form["username"],), one=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.clear()
            session.update(uid=u["id"], role=u["role"], name=u["name"])
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//")
                            else HOME[u["role"]])
        flash("Invalid username or password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------- kitchen ----------
@app.route("/kitchen")
@login_required("kitchen")
def kitchen():
    return render_template("kitchen.html")


@app.get("/api/kitchen")
@login_required("kitchen")
def kitchen_json():
    orders = q("SELECT o.id,o.status,o.notes,o.created_at,t.label FROM orders o "
               "JOIN restaurant_tables t ON t.id=o.table_id "
               "WHERE o.status IN ('placed','preparing','ready') ORDER BY o.created_at")
    for o in orders:
        o["created_at"] = o["created_at"].strftime("%H:%M")
        o["items"] = q("SELECT oi.qty,oi.customization,m.name FROM order_items oi "
                       "JOIN menu_items m ON m.id=oi.item_id WHERE oi.order_id=%s", (o["id"],))
    return jsonify(orders)


@app.post("/api/order/<int:oid>/status")
@login_required("kitchen", "waiter")
def set_status(oid):
    new = (request.get_json(force=True) or {}).get("status")
    if new not in ROLE_STATUS.get(session["role"], ()):
        abort(403)
    cur = q("SELECT status FROM orders WHERE id=%s", (oid,), one=True) or abort(404)
    if FLOW.index(new) != FLOW.index(cur["status"]) + 1:
        return jsonify(error="Invalid status step"), 400
    run("UPDATE orders SET status=%s WHERE id=%s", (new, oid))
    return jsonify(ok=True)


# ---------- waiter / floor map ----------
@app.route("/waiter")
@login_required("waiter")
def waiter():
    return render_template("waiter.html")


@app.get("/api/floor")
@login_required("waiter")
def floor():
    tables = q("SELECT * FROM restaurant_tables ORDER BY id")
    for t in tables:
        t["calls"] = q("SELECT id,reason FROM waiter_calls WHERE table_id=%s AND resolved=0",
                       (t["id"],))
        t["ready"] = q("SELECT id FROM orders WHERE table_id=%s AND status='ready'", (t["id"],))
    return jsonify(tables)


@app.post("/api/call/<int:cid>/resolve")
@login_required("waiter")
def resolve_call(cid):
    c = q("SELECT table_id FROM waiter_calls WHERE id=%s", (cid,), one=True) or abort(404)
    run("UPDATE waiter_calls SET resolved=1 WHERE id=%s", (cid,))
    refresh_table(c["table_id"])
    return jsonify(ok=True)


# ---------- cashier / billing ----------
@app.route("/cashier")
@login_required("cashier")
def cashier():
    orders = q("SELECT o.id,o.status,o.created_at,t.label FROM orders o "
               "JOIN restaurant_tables t ON t.id=o.table_id "
               "WHERE o.status IN ('ready','served') ORDER BY o.created_at")
    for o in orders:
        o["total"] = bill_for(o["id"])["total"]
    return render_template("cashier.html", orders=orders)


@app.route("/bill/<int:oid>", methods=["GET", "POST"])
@login_required("cashier")
def bill(oid):
    o = q("SELECT o.*, t.label FROM orders o JOIN restaurant_tables t ON t.id=o.table_id "
          "WHERE o.id=%s", (oid,), one=True) or abort(404)
    if o["status"] not in ("ready", "served"):
        flash("This order is not ready for billing.")
        return redirect(url_for("cashier"))
    b = bill_for(oid)
    if request.method == "POST":
        method = request.form.get("method", "cash")
        method = method if method in ("cash", "card", "online") else "cash"
        run("INSERT INTO payments (order_id,subtotal,discount,tax,total,method) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (oid, b["subtotal"], b["discount"], b["tax"], b["total"], method))
        run("UPDATE orders SET status='billed' WHERE id=%s", (oid,))
        refresh_table(o["table_id"])
        return redirect(url_for("receipt", oid=oid))
    return render_template("bill.html", o=o, b=b)


@app.route("/receipt/<int:oid>")
def receipt(oid):
    p = q("SELECT p.*, t.label FROM payments p JOIN orders o ON o.id=p.order_id "
          "JOIN restaurant_tables t ON t.id=o.table_id WHERE p.order_id=%s", (oid,),
          one=True) or abort(404)
    return render_template("receipt.html", p=p, b=bill_for(oid), oid=oid)


# ---------- admin ----------
@app.route("/admin")
@login_required("admin")
def admin():
    stats = q("SELECT COALESCE(SUM(total),0) AS sales, COUNT(*) AS n FROM payments "
              "WHERE DATE(paid_at)=CURDATE()", one=True)
    daily = q("SELECT DATE(paid_at) AS d, SUM(total) AS s FROM payments "
              "WHERE paid_at>=CURDATE()-INTERVAL 6 DAY GROUP BY DATE(paid_at) ORDER BY d")
    top = q("SELECT m.name, SUM(oi.qty) AS n FROM order_items oi "
            "JOIN menu_items m ON m.id=oi.item_id JOIN orders o ON o.id=oi.order_id "
            "WHERE o.status='billed' GROUP BY m.id, m.name ORDER BY n DESC LIMIT 5")
    rating = q("SELECT ROUND(AVG(rating),1) AS r, COUNT(*) AS n FROM feedback", one=True)
    active = q("SELECT COUNT(*) AS n FROM orders WHERE status<>'billed'", one=True)
    recent = q("SELECT f.rating,f.comment,t.label FROM feedback f "
               "JOIN restaurant_tables t ON t.id=f.table_id ORDER BY f.id DESC LIMIT 5")
    peak = max([float(r["s"]) for r in daily] or [1])
    return render_template("admin.html", stats=stats, daily=daily, top=top, rating=rating,
                           active=active, recent=recent, peak=peak)


@app.route("/admin/manage")
@login_required("admin")
def manage():
    return render_template(
        "manage.html",
        cats=q("SELECT * FROM categories"),
        items=q("SELECT m.*, c.name AS cat FROM menu_items m JOIN categories c "
                "ON c.id=m.category_id ORDER BY m.id"),
        users=q("SELECT id,name,username,role FROM users ORDER BY id"),
        tables=q("SELECT * FROM restaurant_tables ORDER BY id"),
        deals=q("SELECT * FROM deals ORDER BY id"))


@app.post("/admin/add/<kind>")
@login_required("admin")
def add(kind):
    f = request.form
    if kind == "menu":
        run("INSERT INTO menu_items (category_id,name,description,price,image_url) "
            "VALUES (%s,%s,%s,%s,%s)",
            (int(f["category_id"]), f["name"], f.get("description", ""), float(f["price"]),
             f.get("image_url") or None))
    elif kind == "staff":
        if f["role"] not in ("admin", "waiter", "kitchen", "cashier") or len(f["password"]) < 6:
            flash("Invalid role or password too short (min 6).")
        else:
            run("INSERT INTO users (name,username,password_hash,role) VALUES (%s,%s,%s,%s)",
                (f["name"], f["username"], generate_password_hash(f["password"]), f["role"]))
    elif kind == "table":
        run("INSERT INTO restaurant_tables (label,seats) VALUES (%s,%s)",
            (f["label"], int(f["seats"])))
    elif kind == "deal":
        run("INSERT INTO deals (title,description,discount_percent) VALUES (%s,%s,%s)",
            (f["title"], f.get("description", ""), float(f["discount_percent"])))
    else:
        abort(404)
    return redirect(url_for("manage"))


@app.post("/admin/toggle/<kind>/<int:rid>")
@login_required("admin")
def toggle(kind, rid):
    sql = {"menu": "UPDATE menu_items SET available=1-available WHERE id=%s",
           "deal": "UPDATE deals SET active=1-active WHERE id=%s"}.get(kind) or abort(404)
    run(sql, (rid,))
    return redirect(url_for("manage"))


@app.post("/admin/delete/staff/<int:rid>")
@login_required("admin")
def delete_staff(rid):
    if rid != session["uid"]:
        run("DELETE FROM users WHERE id=%s", (rid,))
    return redirect(url_for("manage"))


@app.route("/admin/report.csv")
@login_required("admin")
def report_csv():
    rows = q("SELECT p.paid_at, p.order_id, t.label AS tbl, p.subtotal, p.discount, p.tax, "
             "p.total, p.method FROM payments p JOIN orders o ON o.id=p.order_id "
             "JOIN restaurant_tables t ON t.id=o.table_id ORDER BY p.paid_at DESC")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Paid at", "Order", "Table", "Subtotal", "Discount", "Tax", "Total", "Method"])
    for r in rows:
        w.writerow(list(r.values()))
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=sales_report.csv"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
