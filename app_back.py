import os
import sqlite3
import pickle
import pandas as pd

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

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

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

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = User.get_by_username(username)


        if user and user.check_password(password):

            # Replace current login with selected account
            logout_user()

            login_user(user)

            print(
                "LOGIN USER:",
                user.username
            )

            print(
                "DATABASE ROLE:",
                user.role
            )


            if user.role == "admin":

                return redirect(
                    url_for("admin_dashboard")
                )


            elif user.role == "doctor":

                return redirect(
                    url_for("doctor_dashboard")
                )


            elif user.role == "patient":

                return redirect(
                    url_for("patient_dashboard")
                )


            return redirect(
                url_for("dashboard")
            )


        flash(
            "Invalid username or password.",
            "error"
        )


    return render_template(
        "login.html"
    )


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
@login_required
def appointment():

    # Only patients can book appointments
    if current_user.role != "patient":

        flash(
            "Only patients can book appointments.",
            "error"
        )

        return redirect(
            url_for("dashboard")
        )


    department = request.args.get(
        "department",
        ""
    )

    print(
        "Appointment user:",
        current_user.username
    )

    print(
        "Appointment role:",
        current_user.role
    )

    print(
        "Department received:",
        department
    )


    return render_template(
        "appointment.html",
        username=current_user.username,
        department=department
    )


# ============================================================
# DASHBOARD ROUTER
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    if current_user.role == "patient":

        return redirect(
            url_for("patient_dashboard")
        )


    elif current_user.role == "doctor":

        return redirect(
            url_for("doctor_dashboard")
        )


    elif current_user.role == "admin":

        return redirect(
            url_for("admin_dashboard")
        )


    return redirect(
        url_for("login")
    )


# ============================================================
# PATIENT DASHBOARD
# ============================================================

@app.route("/patient-dashboard")
@login_required
def patient_dashboard():

    if current_user.role != "patient":

        return redirect(
            url_for("dashboard")
        )


    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()


    cursor.execute("""
        SELECT *
        FROM appointments
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (
        current_user.id,
    ))


    appointments = cursor.fetchall()

    conn.close()


    return render_template(
        "patient_dashboard.html",
        username=current_user.username,
        appointments=appointments
    )


# ============================================================
# DOCTOR DASHBOARD
# ============================================================

@app.route("/doctor-dashboard")
@login_required
def doctor_dashboard():

    if current_user.role != "doctor":

        return redirect(
            url_for("dashboard")
        )


    from datetime import datetime

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )


    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()


    # --------------------------------------------------------
    # Doctor appointments
    # --------------------------------------------------------

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
    """, (
        current_user.username,
    ))


    appointments = cursor.fetchall()


    # --------------------------------------------------------
    # Today's patients
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM appointments
        WHERE doctor_name = ?
        AND appointment_date = ?
    """, (
        current_user.username,
        today
    ))


    today_patients = cursor.fetchone()[0]


    # --------------------------------------------------------
    # Pending
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM appointments
        WHERE doctor_name = ?
        AND status = 'Pending'
    """, (
        current_user.username,
    ))


    pending_appointments = cursor.fetchone()[0]


    # --------------------------------------------------------
    # Completed
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM appointments
        WHERE doctor_name = ?
        AND status = 'Completed'
    """, (
        current_user.username,
    ))


    completed_appointments = cursor.fetchone()[0]


    # --------------------------------------------------------
    # Patient records
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(DISTINCT user_id)
        FROM appointments
        WHERE doctor_name = ?
    """, (
        current_user.username,
    ))


    patient_records = cursor.fetchone()[0]


    # --------------------------------------------------------
    # Recent activity
    # --------------------------------------------------------

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
    """, (
        current_user.username,
    ))


    recent_activity = cursor.fetchall()


    # --------------------------------------------------------
    # IMPORTANT:
    # Get department directly from USERS table
    # --------------------------------------------------------

    cursor.execute("""
        SELECT department
        FROM users
        WHERE username = ?
        AND role = 'doctor'
        LIMIT 1
    """, (
        current_user.username,
    ))


    department_row = cursor.fetchone()


    if (
        department_row
        and department_row["department"]
    ):

        doctor_department = (
            department_row["department"]
        )

    else:

        doctor_department = "Not Assigned"


    conn.close()


    return render_template(
        "doctor_dashboard.html",

        appointments=appointments,

        today_patients=today_patients,

        pending_appointments=pending_appointments,

        completed_appointments=completed_appointments,

        patient_records=patient_records,

        recent_activity=recent_activity,

        doctor_department=doctor_department
    )


# ============================================================
# CALL PATIENT
# ============================================================

@app.route("/call_patient/<int:id>")
@login_required
def call_patient(id):

    if current_user.role != "doctor":

        flash(
            "Only doctors can call patients.",
            "error"
        )

        return redirect(
            url_for("dashboard")
        )


    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()


    cursor.execute("""
        SELECT patient_name
        FROM appointments
        WHERE id = ?
        AND doctor_name = ?
    """, (
        id,
        current_user.username
    ))


    appointment = cursor.fetchone()


    if not appointment:

        conn.close()

        flash(
            "Appointment not found.",
            "error"
        )

        return redirect(
            url_for("doctor_dashboard")
        )


    patient_name = appointment[0]


    cursor.execute("""
        UPDATE appointments
        SET
            status = 'Called',
            notification = ?
        WHERE id = ?
        AND doctor_name = ?
    """, (
        f"Dr. {current_user.username} has called you.",
        id,
        current_user.username
    ))


    conn.commit()

    conn.close()


    flash(
        f"Patient {patient_name} has been called.",
        "success"
    )


    return redirect(
        url_for("doctor_dashboard")
    )


# ============================================================
# ADMIN
# ============================================================

@app.route("/admin")
@login_required
def admin_dashboard():

    if current_user.role != "admin":

        return redirect(
            url_for("dashboard")
        )


    return render_template(
        "admin.html",
        username=current_user.username
    )


# ============================================================
# PROFILE
# ============================================================
@app.route("/profile")
@login_required
def profile():

    print("========== PROFILE CHECK ==========")
    print("USERNAME:", current_user.username)
    print("USER ID:", current_user.id)
    print("ROLE:", current_user.role)
    print("===================================")

    if current_user.role == "patient":

        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM appointments
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (current_user.id,))

        appointments = cursor.fetchall()

        conn.close()

        return render_template(
            "profile.html",
            appointments=appointments,
            username=current_user.username
        )

    elif current_user.role == "doctor":

        return redirect(url_for("doctor_dashboard"))

    elif current_user.role == "admin":

        return redirect(url_for("admin_dashboard"))

    return redirect(url_for("login"))

# ============================================================
# PREDICTION PAGE
# ============================================================

@app.route("/predict_page")
@login_required
def predict_page():

    return render_template(
        "index.html",
        username=current_user.username
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
@login_required
def generate_token():

    try:

        # Only patients can create appointments
        if current_user.role != "patient":

            return jsonify({
                "success": False,
                "error": (
                    "Only patients can book appointments."
                )
            }), 403


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

        department = (
            data.get("department", "")
            .strip()
        )

        appointment_time = (
            data.get("appointment_time", "")
        )


        # Always create new appointments as Pending
        status = "Pending"


        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # DATABASE
        # ----------------------------------------------------

        conn = sqlite3.connect(
            DATABASE
        )

        cursor = conn.cursor()


        # ----------------------------------------------------
        # FIND DOCTOR WITH FEWEST PENDING APPOINTMENTS
        # ----------------------------------------------------

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
        """, (
            department,
        ))


        doctor = cursor.fetchone()


        # ----------------------------------------------------
        # NO DOCTOR
        # ----------------------------------------------------

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
            current_user.username
        )

        print(
            "Patient Role:",
            current_user.role
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


        # ----------------------------------------------------
        # TOKEN
        # ----------------------------------------------------

        cursor.execute("""
            SELECT MAX(token)
            FROM appointments
        """)


        last_token = cursor.fetchone()[0]


        if last_token is None:

            current_token = 1001

        else:

            current_token = (
                last_token + 1
            )


        # ----------------------------------------------------
        # INSERT APPOINTMENT
        # ----------------------------------------------------

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

            # IMPORTANT:
            # This is the logged-in PATIENT's ID
            current_user.id,

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


        print(
            "Appointment booked successfully"
        )

        print(
            "Patient:",
            name
        )

        print(
            "Patient User ID:",
            current_user.id
        )

        print(
            "Token:",
            current_token
        )

        print(
            "Department:",
            department
        )

        print(
            "Doctor:",
            doctor_name
        )

        print(
            "Date:",
            date
        )


        return jsonify({

            "success": True,

            "token": current_token,

            "doctor_name": doctor_name,

            "message": (
                "Appointment booked successfully"
            )
        })


    except Exception as e:

        print(
            "BOOKING ERROR:",
            str(e)
        )


        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )

