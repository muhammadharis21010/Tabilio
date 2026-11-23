"""Creates the database, tables, sample menu and default staff accounts."""
import os, pymysql
from werkzeug.security import generate_password_hash

H, U, P = (os.environ.get("DB_HOST", "localhost"), os.environ.get("DB_USER", "root"),
           os.environ.get("DB_PASSWORD", ""))
NAME = os.environ.get("DB_NAME", "tablio")

con = pymysql.connect(host=H, user=U, password=P, autocommit=True)
cur = con.cursor()
cur.execute(f"CREATE DATABASE IF NOT EXISTS `{NAME}` CHARACTER SET utf8mb4")
cur.execute(f"USE `{NAME}`")
for stmt in open("schema.sql", encoding="utf-8").read().split(";"):
    if stmt.strip():
        cur.execute(stmt)
for name, user, pw, role in [("Admin", "admin", "admin123", "admin"),
                             ("Waiter", "waiter", "waiter123", "waiter"),
                             ("Chef", "kitchen", "kitchen123", "kitchen"),
                             ("Cashier", "cashier", "cashier123", "cashier")]:
    cur.execute("INSERT IGNORE INTO users (name,username,password_hash,role) VALUES (%s,%s,%s,%s)",
                (name, user, generate_password_hash(pw), role))
print("Database ready. Change the default passwords after first login!")
