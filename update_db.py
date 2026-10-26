import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "hospital.db")

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

try:
    cursor.execute("""
        ALTER TABLE appointments
        ADD COLUMN notification TEXT;
    """)

    conn.commit()
    print("✅ notification column added successfully!")

except sqlite3.OperationalError as e:
    print("⚠️ Error:", e)

finally:
    conn.close()