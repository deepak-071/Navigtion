
import os
import sqlite3

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "hospital.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates users table with doctor department"""

    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            department TEXT DEFAULT ''
        )
    """)

    # Add department column if it does not exist
    columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "department" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN department TEXT DEFAULT ''"
        )

    conn.commit()
    conn.close()


class User(UserMixin):

    def __init__(
        self,
        id,
        username,
        email,
        password_hash,
        role
    ):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role

    def get_id(self):
        return str(self.id)

    @staticmethod
    def get_by_id(user_id):

        conn = get_connection()

        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        conn.close()

        if row:
            return User(
                row["id"],
                row["username"],
                row["email"],
                row["password_hash"],
                row["role"]
            )

        return None

    @staticmethod
    def get_by_username(username):

        conn = get_connection()

        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if row:
            return User(
                row["id"],
                row["username"],
                row["email"],
                row["password_hash"],
                row["role"]
            )

        return None

    @staticmethod
    def create(
        username,
        email,
        password,
        role,
        department=""
    ):

        password_hash = generate_password_hash(password)

        conn = get_connection()

        try:

            conn.execute("""
                INSERT INTO users
                (
                    username,
                    email,
                    password_hash,
                    role,
                    created_at,
                    department
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    datetime('now'),
                    ?
                )
            """,
            (
                username,
                email,
                password_hash,
                role,
                department
            ))

            conn.commit()

            return True, "Account created successfully."

        except sqlite3.IntegrityError:

            return False, "That username or email is already registered."

        finally:

            conn.close()

    def check_password(self, password):

        return check_password_hash(
            self.password_hash,
            password
        )
