import sqlite3

source = sqlite3.connect("hospital_app.db")
target = sqlite3.connect("hospital.db")

source.row_factory = sqlite3.Row

users = source.execute("""
    SELECT id, username, email, password_hash, role, created_at
    FROM users
""").fetchall()

target.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
""")

for user in users:
    target.execute("""
        INSERT OR IGNORE INTO users
        (id, username, email, password_hash, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user["id"],
        user["username"],
        user["email"],
        user["password_hash"],
        user["role"],
        user["created_at"]
    ))

target.commit()

print("Users migrated successfully.")

rows = target.execute("""
    SELECT id, username, email, role
    FROM users
""").fetchall()

for row in rows:
    print(row)

source.close()
target.close()