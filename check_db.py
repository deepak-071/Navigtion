import sqlite3

conn = sqlite3.connect("hospital.db")
cursor = conn.cursor()

print("\n========== USERS ==========")

cursor.execute("""
    SELECT id, username, email, role, department
    FROM users
""")

users = cursor.fetchall()

for user in users:
    print(user)


print("\n========== APPOINTMENTS ==========")

cursor.execute("""
    SELECT
        id,
        user_id,
        patient_name,
        appointment_date,
        token,
        department,
        doctor_name,
        status
    FROM appointments
    ORDER BY id
""")

appointments = cursor.fetchall()

for appointment in appointments:
    print(appointment)


conn.close()