import os
import sqlite3
import pickle
import pandas as pd
import secrets

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash

from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)

from graph.hospital_graph import (
    get_shortest_path_to_department,
    HOSPITAL_GRAPH
)

from model.symptom_utils import (
    load_symptom_columns,
    extract_symptoms_from_text
)

from auth.models import User, init_db


# ============================================================
# APP SETUP
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "hospital.db")

app = Flask(__name__)
# ============================================================
# TAB SESSION STORAGE
# ============================================================

TAB_SESSIONS = {}
def create_tab_session(user):
    tab_id = secrets.token_urlsafe(32)

    TAB_SESSIONS[tab_id] = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role
    }

    return tab_id

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "dev-secret-key-change-me"
)


# ============================================================
# MODEL PATHS
# ============================================================

MODEL_PATH = os.path.join(
    BASE_DIR,
    "model",
    "department_model.pkl"
)

FEATURES_PATH = os.path.join(
    BASE_DIR,
    "model",
    "feature_columns.pkl"
)


# ============================================================
# APPOINTMENT DATABASE
# ============================================================

def init_appointment_db():

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            patient_name TEXT,
            phone TEXT,
            appointment_date TEXT,
            age INTEGER,
            weight REAL,
            token INTEGER UNIQUE,
            department TEXT,
            doctor_name TEXT,
            appointment_time TEXT,
            status TEXT DEFAULT 'Pending',
            notification TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("PRAGMA table_info(appointments)")

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "department" not in columns:
        cursor.execute("""
            ALTER TABLE appointments
            ADD COLUMN department TEXT
        """)

    if "doctor_name" not in columns:
        cursor.execute("""
            ALTER TABLE appointments
            ADD COLUMN doctor_name TEXT
        """)

    if "appointment_time" not in columns:
        cursor.execute("""
            ALTER TABLE appointments
            ADD COLUMN appointment_time TEXT
        """)

    if "notification" not in columns:
        cursor.execute("""
            ALTER TABLE appointments
            ADD COLUMN notification TEXT DEFAULT ''
        """)

    if "status" not in columns:
        cursor.execute("""
            ALTER TABLE appointments
            ADD COLUMN status TEXT DEFAULT 'Pending'
        """)

    conn.commit()
    conn.close()

    print("Appointment database initialized successfully")


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()
init_appointment_db()


# ============================================================
# LOGIN MANAGER
# ============================================================

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = "login"

login_manager.login_message = (
    "Please log in to use the hospital navigator."
)


@login_manager.user_loader
def load_user(user_id):

    return User.get_by_id(user_id)


# ============================================================
# LOAD ML MODEL
# ============================================================

model = None
feature_columns = []
model_load_error = None

try:

    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    with open(FEATURES_PATH, "rb") as f:
        feature_columns = pickle.load(f)

    print(
        f"ML model loaded successfully! "
        f"({len(feature_columns)} symptom features)"
    )

except FileNotFoundError:

    model_load_error = (
        "Model files not found. Please run "
        "'python model/train_model.py' first."
    )

    print(model_load_error)


raw_symptom_columns, display_symptom_names = (
    load_symptom_columns()
)


# ============================================================
# REGISTER
# ============================================================



@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        role = request.form.get(
            "role",
            ""
        )

        department = request.form.get(
            "department",
            ""
        ).strip()

        if not username or not email or not password or not role:

            flash(
                "Please fill in every field.",
                "error"
            )

        elif len(password) < 6:

            flash(
                "Password must be at least 6 characters.",
                "error"
            )

        elif role == "doctor" and not department:

            flash(
                "Please select a department for the doctor.",
                "error"
            )

        else:

            success, message = User.create(
                username,
                email,
                password,
                role,
                department
            )

            if success:

                flash(
                    "Account created! Please log in.",
                    "success"
                )

                return redirect(
                    url_for("login")
                )

            flash(
                message,
                "error"
            )

    return render_template(
        "register.html"
    )




# ============================================================
# LOGIN
# ============================================================


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.get_by_username(username)

        if user and user.check_password(password):

            login_user(user)

            print("LOGIN USER:", user.username)
            print("DATABASE ROLE:", user.role)

            tab_id = create_tab_session(user)

            print("TAB ID:", tab_id)

            # DIRECT ROLE-BASED REDIRECT
            if user.role == "patient":
                return redirect(
                    url_for(
                        "patient_dashboard",
                        tab_id=tab_id
                    )
                )

            elif user.role == "doctor":
                return redirect(
                    url_for(
                        "doctor_dashboard",
                        tab_id=tab_id
                    )
                )

            elif user.role == "admin":
                return redirect(
                    url_for(
                        "admin_dashboard",
                        tab_id=tab_id
                    )
                )

            return redirect(url_for("login"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("login")
    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return redirect(
        url_for("login")
    )


# ============================================================
# APPOINTMENT PAGE
# ============================================================


@app.route("/appointment")
def appointment():

    tab_id = request.args.get("tab_id")

    print("========== APPOINTMENT CHECK ==========")
    print("Appointment tab ID:", tab_id)

    # Check tab session
    if not tab_id:
        print("ERROR: No tab_id received")
        return redirect(url_for("login"))

    if tab_id not in TAB_SESSIONS:
        print("ERROR: tab_id not found in TAB_SESSIONS")
        print("Available TAB IDs:", list(TAB_SESSIONS.keys()))
        return redirect(url_for("login"))

    # Get user from this tab
    tab_user = TAB_SESSIONS[tab_id]

    print("Appointment username:", tab_user["username"])
    print("Appointment user ID:", tab_user["user_id"])
    print("Appointment role:", tab_user["role"])

    # Only patient can book
    if tab_user["role"] != "patient":

        print("ERROR: This tab is not a patient tab")

        return redirect(
            url_for(
                "doctor_dashboard",
                tab_id=tab_id
            )
            if tab_user["role"] == "doctor"
            else url_for("login")
        )

    department = request.args.get("department", "")

    print("Department received:", department)
    print("=======================================")

    return render_template(
        "appointment.html",
        username=tab_user["username"],
        department=department,
        tab_id=tab_id
    )


# ============================================================
# PATIENT DASHBOARD
# ============================================================


@app.route("/patient-dashboard")
def patient_dashboard():

    tab_id = request.args.get("tab_id")

    if not tab_id or tab_id not in TAB_SESSIONS:
        return redirect(url_for("login"))

    tab_user = TAB_SESSIONS[tab_id]

    if tab_user["role"] != "patient":
        return redirect(url_for("login"))

    user_id = tab_user["user_id"]

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM appointments
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))

    appointments = cursor.fetchall()

    conn.close()

    return render_template(
        "patient_dashboard.html",
        username=tab_user["username"],
        appointments=appointments,
        tab_id=tab_id
    )




@app.route("/call_patient/<int:id>")
def call_patient(id):

    tab_id = request.args.get("tab_id")

    print("========== CALL PATIENT ==========")
    print("TAB ID:", tab_id)
    print("APPOINTMENT ID:", id)

    if not tab_id or tab_id not in TAB_SESSIONS:
        return redirect(url_for("login"))

    tab_user = TAB_SESSIONS[tab_id]

    if tab_user["role"] != "doctor":
        return redirect(url_for("login"))

    doctor_username = tab_user["username"]

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM appointments
        WHERE id = ?
        AND doctor_name = ?
    """, (id, doctor_username))

    appointment = cursor.fetchone()

    conn.close()

    if not appointment:
        flash("Appointment not found.", "error")
        return redirect(
            url_for(
                "doctor_dashboard",
                tab_id=tab_id
            )
        )

    return redirect(
        url_for(
            "doctor_dashboard",
            tab_id=tab_id
        )
    )




# ============================================================
# DOCTOR DASHBOARD
# ============================================================

@app.route("/doctor-dashboard")
def doctor_dashboard():

    tab_id = request.args.get("tab_id")

    print("========== DOCTOR DASHBOARD ==========")
    print("TAB ID:", tab_id)

    # ------------------------------------------------
    # CHECK TAB SESSION
    # ------------------------------------------------
    if not tab_id or tab_id not in TAB_SESSIONS:

        print("ERROR: Invalid or missing doctor tab")

        return redirect(url_for("login"))

    tab_user = TAB_SESSIONS[tab_id]

    print("TAB SESSION FOUND")
    print("USERNAME:", tab_user["username"])
    print("ROLE:", tab_user["role"])

    # ------------------------------------------------
    # ONLY DOCTOR CAN ACCESS
    # ------------------------------------------------
    if tab_user["role"] != "doctor":

        print("ERROR: This is not a doctor tab")

        return redirect(url_for("login"))

    doctor_username = tab_user["username"]

    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ------------------------------------------------
    # ALL APPOINTMENTS
    # ------------------------------------------------
    cursor.execute("""
        SELECT
            id,
            user_id,
            patient_name,
            phone,
            appointment_date,
            age,
            weight,
            token,
            department,
            doctor_name,
            appointment_time,
            status,
            notification,
            created_at
        FROM appointments
        WHERE doctor_name = ?
        ORDER BY appointment_date DESC, token ASC
    """, (doctor_username,))

    appointments = cursor.fetchall()

    # ------------------------------------------------
    # TODAY PATIENTS
    # ------------------------------------------------
    cursor.execute("""
        SELECT COUNT(*)
        FROM appointments
        WHERE doctor_name = ?
        AND appointment_date = ?
    """, (doctor_username, today))

    today_patients = cursor.fetchone()[0]

    # ------------------------------------------------
    # PENDING
    # ------------------------------------------------
    cursor.execute("""
        SELECT COUNT(*)
        FROM appointments
        WHERE doctor_name = ?
        AND status = 'Pending'
    """, (doctor_username,))

    pending_appointments = cursor.fetchone()[0]

    # ------------------------------------------------
    # COMPLETED
    # ------------------------------------------------
    cursor.execute("""
        SELECT COUNT(*)
        FROM appointments
        WHERE doctor_name = ?
        AND status = 'Completed'
    """, (doctor_username,))

    completed_appointments = cursor.fetchone()[0]

    # ------------------------------------------------
    # PATIENT RECORDS
    # ------------------------------------------------
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id)
        FROM appointments
        WHERE doctor_name = ?
    """, (doctor_username,))

    patient_records = cursor.fetchone()[0]

    # ------------------------------------------------
    # RECENT ACTIVITY
    # ------------------------------------------------
    cursor.execute("""
        SELECT
            patient_name,
            appointment_date,
            appointment_time,
            status,
            department,
            created_at
        FROM appointments
        WHERE doctor_name = ?
        ORDER BY created_at DESC
        LIMIT 5
    """, (doctor_username,))

    recent_activity = cursor.fetchall()

    # ------------------------------------------------
    # DOCTOR DEPARTMENT
    # ------------------------------------------------
    cursor.execute("""
        SELECT department
        FROM users
        WHERE username = ?
        AND role = 'doctor'
        LIMIT 1
    """, (doctor_username,))

    department_row = cursor.fetchone()

    if department_row and department_row["department"]:
        doctor_department = department_row["department"]
    else:
        doctor_department = "Not Assigned"

    conn.close()

    print("Doctor dashboard loaded successfully")
    print("====================================")

    return render_template(
        "doctor_dashboard.html",
        appointments=appointments,
        today_patients=today_patients,
        pending_appointments=pending_appointments,
        completed_appointments=completed_appointments,
        patient_records=patient_records,
        recent_activity=recent_activity,
        doctor_department=doctor_department,
        tab_id=tab_id,
        username=tab_user["username"],
        role=tab_user["role"]
    )


@app.route("/approve_appointment/<int:id>", methods=["POST"])
def approve_appointment(id):

    tab_id = request.args.get("tab_id")

    print("========== APPROVE APPOINTMENT ==========")
    print("TAB ID:", tab_id)
    print("APPOINTMENT ID:", id)

    # -----------------------------------------
    # CHECK TAB
    # -----------------------------------------

    if not tab_id or tab_id not in TAB_SESSIONS:
        return redirect(url_for("login"))

    tab_user = TAB_SESSIONS[tab_id]

    # -----------------------------------------
    # ONLY DOCTOR
    # -----------------------------------------

    if tab_user["role"] != "doctor":
        return redirect(url_for("login"))

    doctor_username = tab_user["username"]

    # -----------------------------------------
    # GET TIME
    # -----------------------------------------

    appointment_time = request.form.get(
        "appointment_time",
        ""
    ).strip()

    if not appointment_time:

        flash(
            "Please select appointment time.",
            "error"
        )

        return redirect(
            url_for(
                "doctor_dashboard",
                tab_id=tab_id
            )
        )

    # -----------------------------------------
    # FORMAT TIME
    # -----------------------------------------

    from datetime import datetime

    try:

        formatted_time = datetime.strptime(
            appointment_time,
            "%H:%M"
        ).strftime("%I:%M %p")

    except ValueError:

        formatted_time = appointment_time

    # -----------------------------------------
    # DATABASE
    # -----------------------------------------

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # -----------------------------------------
    # FIND APPOINTMENT
    # -----------------------------------------

    cursor.execute("""
        SELECT
            id,
            patient_name,
            appointment_date,
            department,
            status
        FROM appointments
        WHERE id = ?
        AND doctor_name = ?
    """, (
        id,
        doctor_username
    ))

    appointment = cursor.fetchone()

    if not appointment:

        conn.close()

        flash(
            "Appointment not found.",
            "error"
        )

        return redirect(
            url_for(
                "doctor_dashboard",
                tab_id=tab_id
            )
        )

    # -----------------------------------------
    # NOTIFICATION
    # -----------------------------------------

    notification = (
        f"Dr. {doctor_username} approved your appointment. "
        f"Your appointment time is {formatted_time} "
        f"on {appointment['appointment_date']}."
    )

    # -----------------------------------------
    # UPDATE
    # -----------------------------------------

    cursor.execute("""
        UPDATE appointments
        SET
            appointment_time = ?,
            status = 'Approved',
            notification = ?
        WHERE id = ?
        AND doctor_name = ?
    """, (
        formatted_time,
        notification,
        id,
        doctor_username
    ))

    conn.commit()
    conn.close()

    print("Appointment approved successfully")
    print("Patient:", appointment["patient_name"])
    print("Time:", formatted_time)

    flash(
        f"Appointment approved for {formatted_time}.",
        "success"
    )

    return redirect(
        url_for(
            "doctor_dashboard",
            tab_id=tab_id
        )
    )




# ============================================================
# ADMIN
# ============================================================

@app.route("/admin")
def admin_dashboard():

    tab_id = request.args.get("tab_id")

    if not tab_id or tab_id not in TAB_SESSIONS:
        return redirect(url_for("login"))

    tab_user = TAB_SESSIONS[tab_id]

    if tab_user["role"] != "admin":
        return redirect(url_for("dashboard", tab_id=tab_id))

    return render_template(
        "admin.html",
        username=tab_user["username"],
        tab_id=tab_id
    )


# ============================================================
# PROFILE
# ============================================================


@app.route("/profile")
def profile():

    tab_id = request.args.get("tab_id")

    print("========== PROFILE CHECK ==========")
    print("TAB ID:", tab_id)

    if not tab_id:
        print("ERROR: No tab_id")
        return redirect(url_for("login"))

    # -----------------------------------------
    # TAB SESSION FOUND
    # -----------------------------------------
    if tab_id in TAB_SESSIONS:

        tab_user = TAB_SESSIONS[tab_id]

        print("TAB SESSION FOUND")
        print("USERNAME:", tab_user["username"])
        print("USER ID:", tab_user["user_id"])
        print("ROLE:", tab_user["role"])

    # -----------------------------------------
    # TAB SESSION LOST → RESTORE
    # -----------------------------------------
    else:

        print("TAB SESSION NOT FOUND")

        if not current_user.is_authenticated:
            print("USER NOT AUTHENTICATED")
            return redirect(url_for("login"))

        tab_user = {
            "user_id": current_user.id,
            "username": current_user.username,
            "role": current_user.role
        }

        TAB_SESSIONS[tab_id] = tab_user

        print("TAB SESSION RESTORED")
        print("USERNAME:", tab_user["username"])
        print("ROLE:", tab_user["role"])

    # -----------------------------------------
    # DATABASE
    # -----------------------------------------
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (tab_user["user_id"],))

    user_row = cursor.fetchone()

    if not user_row:
        conn.close()
        return redirect(url_for("login"))

    # -----------------------------------------
    # EMAIL
    # -----------------------------------------
    email = ""

    if "email" in user_row.keys():
        email = user_row["email"]

    # -----------------------------------------
    # PATIENT PROFILE
    # -----------------------------------------
    if tab_user["role"] == "patient":

        cursor.execute("""
            SELECT *
            FROM appointments
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (tab_user["user_id"],))

        appointments = cursor.fetchall()

        conn.close()

        return render_template(
            "profile.html",
            appointments=appointments,
            username=tab_user["username"],
            role=tab_user["role"],
            email=email,
            tab_id=tab_id
        )

    # -----------------------------------------
    # DOCTOR PROFILE
    # -----------------------------------------
    elif tab_user["role"] == "doctor":

        conn.close()

        return render_template(
            "profile.html",
            appointments=[],
            username=tab_user["username"],
            role=tab_user["role"],
            email=email,
            tab_id=tab_id
        )

    # -----------------------------------------
    # ADMIN PROFILE
    # -----------------------------------------
    elif tab_user["role"] == "admin":

        conn.close()

        return render_template(
            "profile.html",
            appointments=[],
            username=tab_user["username"],
            role=tab_user["role"],
            email=email,
            tab_id=tab_id
        )

    conn.close()

    return redirect(url_for("login"))


# ============================================================
# PREDICTION PAGE
# ============================================================


@app.route("/predict_page")
def predict_page():

    tab_id = request.args.get("tab_id")

    print("========== PREDICT PAGE ==========")
    print("TAB ID:", tab_id)

    if not tab_id or tab_id not in TAB_SESSIONS:
        return redirect(url_for("login"))

    tab_user = TAB_SESSIONS[tab_id]

    print("USERNAME:", tab_user["username"])
    print("ROLE:", tab_user["role"])
    print("=================================")

    if tab_user["role"] != "patient":
        return redirect(
            url_for(
                "dashboard",
                tab_id=tab_id
            )
        )

    return render_template(
        "index.html",
        username=tab_user["username"],
        tab_id=tab_id
    )


# ============================================================
# SYMPTOMS
# ============================================================

@app.route("/symptoms", methods=["GET"])
@login_required
def get_symptoms():

    symptoms = [
        {
            "id": raw,
            "label": display.title()
        }
        for raw, display in zip(
            raw_symptom_columns,
            display_symptom_names
        )
    ]


    return jsonify({
        "success": True,
        "symptoms": symptoms
    })


# ============================================================
# PREDICT
# ============================================================

@app.route("/predict", methods=["POST"])
@login_required
def predict():

    if model is None:

        return jsonify({
            "success": False,
            "error": model_load_error or "Model not loaded."
        }), 500


    data = request.get_json(
        silent=True
    ) or {}


    symptoms_list = (
        data.get("symptoms_list")
        or []
    )


    symptoms_text = (
        data.get("symptoms_text")
        or ""
    ).strip()


    matched_raw_symptoms = []


    if symptoms_list:

        valid_set = set(
            raw_symptom_columns
        )

        matched_raw_symptoms = [
            s
            for s in symptoms_list
            if s in valid_set
        ]


    elif symptoms_text:

        if len(symptoms_text) < 3:

            return jsonify({
                "success": False,
                "error": (
                    "Please describe your symptoms "
                    "in a bit more detail."
                )
            }), 400


        matched_raw_symptoms = (
            extract_symptoms_from_text(
                symptoms_text,
                raw_symptom_columns,
                display_symptom_names
            )
        )


    else:

        return jsonify({
            "success": False,
            "error": (
                "Please enter your symptoms "
                "or pick them from the list."
            )
        }), 400


    if not matched_raw_symptoms:

        return jsonify({
            "success": False,
            "error": (
                "We couldn't recognize any known "
                "symptoms in that description."
            )
        }), 400


    try:

        feature_row = {
            col: (
                1
                if col in matched_raw_symptoms
                else 0
            )
            for col in feature_columns
        }


        feature_df = pd.DataFrame(
            [feature_row],
            columns=feature_columns
        )


        predicted_department = (
            model.predict(feature_df)[0]
        )


        confidence = None


        if hasattr(model, "predict_proba"):

            probabilities = (
                model.predict_proba(
                    feature_df
                )[0]
            )

            confidence = round(
                max(probabilities) * 100,
                2
            )


        path_result = (
            get_shortest_path_to_department(
                predicted_department,
                start="Entrance"
            )
        )


        if "error" in path_result:

            return jsonify({
                "success": False,
                "error": path_result["error"]
            }), 404


        matched_display = [
            display_symptom_names[
                raw_symptom_columns.index(s)
            ].title()
            for s in matched_raw_symptoms
        ]


        return jsonify({
            "success": True,
            "department": predicted_department,
            "confidence": confidence,
            "matched_symptoms": matched_display,
            "path": path_result["path"],
            "distance_meters": path_result[
                "distance_meters"
            ]
        })


    except Exception as e:

        return jsonify({
            "success": False,
            "error": (
                f"Something went wrong while "
                f"predicting: {str(e)}"
            )
        }), 500


# ============================================================
# MAP
# ============================================================

@app.route("/map", methods=["GET"])
@login_required
def get_map():

    return jsonify({
        "success": True,
        "graph": HOSPITAL_GRAPH
    })


# ============================================================
# GENERATE TOKEN
# ============================================================

@app.route("/generate_token", methods=["POST"])
def generate_token():

    tab_id = request.args.get("tab_id")

    if not tab_id or tab_id not in TAB_SESSIONS:
        return jsonify({
            "success": False,
            "error": "Invalid or missing tab session."
        }), 401

    tab_user = TAB_SESSIONS[tab_id]

    print("Generate Token Tab ID:", tab_id)
    print("Generate Token User:", tab_user["username"])
    print("Generate Token Role:", tab_user["role"])

    if tab_user["role"] != "patient":
        return jsonify({
            "success": False,
            "error": "Only patients can book appointments."
        }), 403

    try:

        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Request must be JSON"
            }), 400

        data = request.get_json()

        name = data.get("name")
        phone = data.get("phone")
        date = data.get("date")
        age = data.get("age")
        weight = data.get("weight")

        department = data.get(
            "department",
            ""
        ).strip()

        appointment_time = data.get(
            "appointment_time",
            ""
        )

        status = "Pending"

        # ---------------- VALIDATION ----------------

        if not name:
            return jsonify({
                "success": False,
                "error": "Patient name is required"
            }), 400

        if not phone:
            return jsonify({
                "success": False,
                "error": "Phone number is required"
            }), 400

        if not date:
            return jsonify({
                "success": False,
                "error": "Appointment date is required"
            }), 400

        if not department:
            return jsonify({
                "success": False,
                "error": "Please select a department."
            }), 400

        # ---------------- DATABASE ----------------

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Find doctor with fewest pending appointments
        cursor.execute("""
            SELECT
                u.id,
                u.username,
                COUNT(a.id) AS pending_count

            FROM users u

            LEFT JOIN appointments a
                ON a.doctor_name = u.username
                AND a.status = 'Pending'

            WHERE u.role = 'doctor'
            AND u.department = ?

            GROUP BY
                u.id,
                u.username

            ORDER BY
                pending_count ASC,
                u.id ASC

            LIMIT 1
        """, (department,))

        doctor = cursor.fetchone()

        # ---------------- NO DOCTOR ----------------

        if not doctor:

            conn.close()

            return jsonify({
                "success": False,
                "error": (
                    f"No doctor is currently available "
                    f"in {department}. "
                    f"Please select another department."
                )
            }), 400

        doctor_id = doctor[0]
        doctor_name = doctor[1]
        pending_count = doctor[2]

        print(
            "Booking Patient:",
            tab_user["username"]
        )

        print(
            "Patient Role:",
            tab_user["role"]
        )

        print(
            "Patient User ID:",
            tab_user["user_id"]
        )

        print(
            "Selected Department:",
            department
        )

        print(
            "Assigned Doctor:",
            doctor_name
        )

        print(
            "Pending Appointments:",
            pending_count
        )

        # ---------------- TOKEN ----------------

        cursor.execute("""
            SELECT MAX(token)
            FROM appointments
        """)

        last_token = cursor.fetchone()[0]

        if last_token is None:
            current_token = 1001
        else:
            current_token = last_token + 1

        # ---------------- INSERT ----------------

        cursor.execute("""
            INSERT INTO appointments
            (
                user_id,
                patient_name,
                phone,
                appointment_date,
                age,
                weight,
                token,
                department,
                doctor_name,
                appointment_time,
                status,
                notification
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tab_user["user_id"],
            name,
            phone,
            date,
            age,
            weight,
            current_token,
            department,
            doctor_name,
            appointment_time,
            status,
            ""
        ))

        conn.commit()
        conn.close()

        print("Appointment booked successfully")
        print("Patient:", name)
        print(
            "Patient User ID:",
            tab_user["user_id"]
        )
        print("Token:", current_token)
        print("Department:", department)
        print("Doctor:", doctor_name)
        print("Date:", date)

        return jsonify({
            "success": True,
            "token": current_token,
            "doctor_name": doctor_name,
            "message": "Appointment booked successfully"
        })

    except Exception as e:

        print("BOOKING ERROR:", str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    except Exception as e:

        print("BOOKING ERROR:", str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    print("STARTING FLASK SERVER...")

    app.run(
        debug=True,
        port=5000,
        use_reloader=False
    )