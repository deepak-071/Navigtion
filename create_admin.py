import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("hospital.db")
cursor = conn.cursor()

username = "Deepakkumardas"
email = "deepakkumardas001346@gmail.com"
password = "123456"

password_hash = generate_password_hash(password)

try:
    cursor.execute("""
        INSERT INTO users
        (username, email, password_hash, role, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (
        username,
        email,
        password_hash,
        "admin"
    ))

    conn.commit()

    print("Admin account created successfully!")
    print("Username:", username)
    print("Password:", password)
    print("Role: admin")

except sqlite3.IntegrityError:
    print("Admin username or email already exists.")

finally:
    conn.close()