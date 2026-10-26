import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "hospital.db")

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

cursor.execute("SELECT * FROM appointments")

for row in cursor.fetchall():
    print(row)

conn.close()