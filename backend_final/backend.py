import os
import sys
import uuid
import bcrypt
from datetime import datetime
from typing import Literal, Optional, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Try importing PostgreSQL drivers (supporting either psycopg v3 or psycopg2)
try:
    import psycopg
    from psycopg.rows import dict_row
    DB_DRIVER = "psycopg"
except ImportError:
    try:
        import psycopg2
        import psycopg2.extras
        DB_DRIVER = "psycopg2"
    except ImportError:
        DB_DRIVER = None

# Load .env file manually if python-dotenv is not installed
def load_env_file():
    env_paths = [".env", os.path.join(os.path.dirname(__file__), ".env"), "../.env"]
    for path in env_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
                break
            except Exception:
                pass

load_env_file()

app = FastAPI(title="Civic Tracker (Unified Full-Stack on Render)")

# Configure CORS
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
if cors_origins_env.strip() == "*":
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uploads directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
PROOF_DIR = os.path.join(UPLOAD_DIR, "resolution_proofs")
os.makedirs(PROOF_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Frontend directory detection
FRONTEND_PATHS = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend")),
    os.path.abspath("frontend"),
    os.path.abspath("CivicTracker_Final/frontend")
]
FRONTEND_DIR = next((p for p in FRONTEND_PATHS if os.path.isdir(p) and os.path.exists(os.path.join(p, "index.html"))), None)


def get_connection_string():
    # 1. Direct DATABASE_URL (standard on Render and Supabase)
    url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if url:
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if ("supabase.co" in url or "pooler.supabase.com" in url) and "sslmode" not in url:
            sep = "&" if "?" in url else "?"
            url += f"{sep}sslmode=require"
        return url

    # 2. Individual environment variables
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "postgres")
    sslmode = os.getenv("DB_SSLMODE")

    if not sslmode:
        if "supabase.co" in host or "pooler.supabase.com" in host or "aws" in host:
            sslmode = "require"
        else:
            sslmode = "prefer"

    return f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode={sslmode}"


def get_db():
    """Establish and return a PostgreSQL connection."""
    if not DB_DRIVER:
        raise HTTPException(
            status_code=500,
            detail="No PostgreSQL driver found. Please install psycopg or psycopg2-binary: pip install psycopg2-binary"
        )

    conn_str = get_connection_string()
    try:
        if DB_DRIVER == "psycopg":
            conn = psycopg.connect(conn_str)
            return conn
        else:
            conn = psycopg2.connect(conn_str)
            return conn
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}. Please check your DATABASE_URL."
        )


def get_cursor(conn, dictionary=False):
    """Return a cursor supporting dictionary or tuple row formats across psycopg versions."""
    if DB_DRIVER == "psycopg":
        return conn.cursor(row_factory=dict_row if dictionary else None)
    elif DB_DRIVER == "psycopg2":
        if dictionary:
            return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return conn.cursor()
    raise HTTPException(status_code=500, detail="Database driver unavailable")


def create_notification(conn, user_id, issue_id, message):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO notifications (user_id, issue_id, message)
        VALUES (%s, %s, %s)
    """, (user_id, issue_id, message))
    cursor.close()


ADMIN_EMAILS = {
    "pavanjeeru15@gmail.com",
    "pavanjeerul5@gmail.com",
    "admin@civictrack.org"
}


def auto_init_database():
    """Automatically initialize tables and seed data if database is fresh, and ensure admins exist."""
    if not DB_DRIVER:
        return
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'users'
            );
        """)
        table_exists = cursor.fetchone()[0]
        if not table_exists:
            print("Database tables not found. Automatically initializing schema...")
            schema_candidates = [
                os.path.join(os.path.dirname(__file__), "..", "database", "supabase_schema.sql"),
                os.path.join(os.path.dirname(__file__), "database", "supabase_schema.sql"),
                os.path.abspath("database/supabase_schema.sql"),
                os.path.abspath("CivicTracker_Final/database/supabase_schema.sql")
            ]
            for s_path in schema_candidates:
                if os.path.exists(s_path):
                    with open(s_path, "r", encoding="utf-8") as f:
                        sql_statements = f.read()
                    cursor.execute(sql_statements)
                    conn.commit()
                    print(f"Database schema initialized successfully from {s_path}!")
                    break

        # Always ensure designated admin accounts exist and have role = 'ADMIN'
        admin_hash = "$2b$12$nnJY.tfj6Xb1VcB4afGS0urVcPOm/WwASpuB/Z5MpvlfUsjMQ4TSq"  # hash for 'pavan123'
        sys_admin_hash = "$2b$12$KTk7KZKbkQ3WdxYHp5d24uaKDV7NMG3F8hiFnC84F8mDsf5t5oYJu"  # hash for 'admin123'

        cursor.execute("""
            INSERT INTO users (full_name, email, phone, password_hash, address, role)
            VALUES 
            ('Pavan Administrator', 'pavanjeeru15@gmail.com', '9876543210', %s, 'Municipal City Center', 'ADMIN')
            ON CONFLICT (email) DO UPDATE
            SET role = 'ADMIN', password_hash = EXCLUDED.password_hash;
        """, (admin_hash,))

        cursor.execute("""
            INSERT INTO users (full_name, email, phone, password_hash, address, role)
            VALUES 
            ('CivicTrack Administrator', 'admin@civictrack.org', '9999999999', %s, 'Municipal City Center', 'ADMIN')
            ON CONFLICT (email) DO UPDATE
            SET role = 'ADMIN';
        """, (sys_admin_hash,))

        cursor.execute("""
            UPDATE users 
            SET role = 'ADMIN' 
            WHERE LOWER(email) IN ('pavanjeeru15@gmail.com', 'pavanjeerul5@gmail.com', 'admin@civictrack.org');
        """)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Database auto-init note: {e}")


@app.on_event("startup")
def on_startup():
    auto_init_database()


# Pydantic Request Models
class Issue(BaseModel):
    user_id: int
    category_id: int
    title: str
    description: str
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"


class UserRegister(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    password: str
    address: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class Feedback(BaseModel):
    user_id: int
    rating: int
    comment: Optional[str] = None


# --- ROUTES ---

@app.get("/health")
def health():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return {"status": "healthy", "database": "connected", "driver": DB_DRIVER}
    except Exception as e:
        return {"status": "unhealthy", "database_error": str(e), "driver": DB_DRIVER}


@app.get("/api/info")
def api_info():
    return {
        "title": "Civic Tracker Backend API",
        "driver": DB_DRIVER,
        "single_project_deployment": "Render",
        "frontend_served": bool(FRONTEND_DIR)
    }


@app.get("/departments")
def get_departments():
    conn = get_db()
    cursor = get_cursor(conn, dictionary=True)
    cursor.execute("""
        SELECT department_id, department_name, description, created_at
        FROM departments
        ORDER BY department_id
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.get("/categories")
def get_categories():
    conn = get_db()
    cursor = get_cursor(conn, dictionary=True)
    cursor.execute("""
        SELECT c.category_id, c.category_name, c.description, c.department_id, d.department_name
        FROM categories c
        LEFT JOIN departments d ON c.department_id = d.department_id
        ORDER BY c.category_id
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.post("/issues")
def report_issue(issue: Issue):
    conn = get_db()
    cursor = conn.cursor()

    complaint_id = "CT" + uuid.uuid4().hex[:8].upper()

    cursor.execute("""
        INSERT INTO issues
        (issue_code, user_id, category_id, title,
         description, location, latitude, longitude, priority)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING issue_id
    """, (
        complaint_id,
        issue.user_id,
        issue.category_id,
        issue.title,
        issue.description,
        issue.location,
        issue.latitude,
        issue.longitude,
        issue.priority
    ))

    result = cursor.fetchone()
    issue_id = result[0] if result else None

    cursor.execute("""
        INSERT INTO issue_status_history
        (issue_id, old_status, new_status, updated_by, remarks)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        issue_id,
        None,
        "SUBMITTED",
        issue.user_id,
        "Complaint submitted"
    ))

    create_notification(
        conn,
        issue.user_id,
        issue_id,
        f"Your complaint {complaint_id} has been submitted successfully."
    )

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "Complaint submitted successfully",
        "complaint_id": complaint_id,
        "issue_id": issue_id,
        "status": "SUBMITTED"
    }


@app.get("/issues")
def get_issues():
    conn = get_db()
    cursor = get_cursor(conn, dictionary=True)

    cursor.execute("""
        SELECT
            i.issue_id,
            i.issue_code,
            i.user_id,
            i.title,
            i.description,
            i.location,
            i.latitude,
            i.longitude,
            i.priority,
            i.status,
            i.created_at,
            i.updated_at,
            c.category_name,
            d.department_name
        FROM issues i
        JOIN categories c ON i.category_id = c.category_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        ORDER BY i.created_at DESC
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.get("/issues/{issue_id}")
def get_issue(issue_id: int):
    conn = get_db()
    cursor = get_cursor(conn, dictionary=True)

    cursor.execute("""
        SELECT
            i.issue_id,
            i.issue_code,
            i.user_id,
            i.title,
            i.description,
            i.location,
            i.latitude,
            i.longitude,
            i.priority,
            i.status,
            i.created_at,
            i.updated_at,
            c.category_name,
            d.department_name
        FROM issues i
        JOIN categories c ON i.category_id = c.category_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE i.issue_id = %s
    """, (issue_id,))

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    return row


@app.patch("/issues/{issue_id}/status")
def update_status(
    issue_id: int,
    status: Literal[
        "SUBMITTED", "UNDER_REVIEW", "ASSIGNED",
        "IN_PROGRESS", "RESOLVED", "CLOSED", "REJECTED"
    ],
    updated_by: int
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT status, user_id FROM issues WHERE issue_id = %s",
        (issue_id,)
    )
    row = cursor.fetchone()

    if row is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    old_status, user_id = row[0], row[1]

    cursor.execute(
        "UPDATE issues SET status = %s WHERE issue_id = %s",
        (status, issue_id)
    )

    cursor.execute("""
        INSERT INTO issue_status_history
        (issue_id, old_status, new_status, updated_by, remarks)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        issue_id,
        old_status,
        status,
        updated_by,
        "Status updated"
    ))

    create_notification(
        conn,
        user_id,
        issue_id,
        f"Your complaint status has been updated to {status}"
    )

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "Status updated successfully",
        "status": status
    }


@app.get("/unresolved")
def unresolved_issues():
    conn = get_db()
    cursor = get_cursor(conn, dictionary=True)

    cursor.execute("""
        SELECT
            i.issue_id,
            i.issue_code,
            i.user_id,
            i.title,
            i.description,
            i.location,
            i.priority,
            i.status,
            i.created_at,
            c.category_name,
            d.department_name
        FROM issues i
        JOIN categories c ON i.category_id = c.category_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE i.status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED')
        ORDER BY i.created_at DESC
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.get("/issues/{issue_id}/history")
def get_history(issue_id: int):
    conn = get_db()
    cursor = get_cursor(conn, dictionary=True)

    cursor.execute("""
        SELECT history_id, old_status, new_status, updated_by, remarks, updated_at
        FROM issue_status_history
        WHERE issue_id = %s
        ORDER BY history_id ASC
    """, (issue_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.get("/dashboard")
def dashboard():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM issues")
    total = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM issues
        WHERE status IN ('SUBMITTED', 'ASSIGNED')
    """)
    pending = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM issues
        WHERE status = 'IN_PROGRESS'
    """)
    in_progress = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM issues
        WHERE status = 'RESOLVED'
    """)
    resolved = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM issues
        WHERE status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED')
    """)
    unresolved = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return {
        "total_complaints": total,
        "pending": pending,
        "in_progress": in_progress,
        "resolved": resolved,
        "unresolved": unresolved
    }


@app.patch("/issues/{issue_id}/department")
def assign_department(
    issue_id: int,
    department_id: int,
    assigned_by: int
):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT status, user_id FROM issues WHERE issue_id = %s",
        (issue_id,)
    )
    row = cursor.fetchone()

    if row is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    old_status, user_id = row[0], row[1]

    cursor.execute("""
        INSERT INTO issue_assignments (issue_id, department_id, assigned_by)
        VALUES (%s, %s, %s)
    """, (issue_id, department_id, assigned_by))

    cursor.execute("""
        UPDATE issues SET status = 'ASSIGNED' WHERE issue_id = %s
    """, (issue_id,))

    cursor.execute("""
        INSERT INTO issue_status_history
        (issue_id, old_status, new_status, updated_by, remarks)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        issue_id,
        old_status,
        "ASSIGNED",
        assigned_by,
        "Department assigned"
    ))

    create_notification(
        conn,
        user_id,
        issue_id,
        "Your complaint has been assigned to a department."
    )

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "Department assigned successfully",
        "issue_id": issue_id,
        "department_id": department_id,
        "status": "ASSIGNED"
    }


@app.post("/register")
def register_user(user: UserRegister):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users WHERE LOWER(email) = LOWER(%s)",
        (user.email,)
    )
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = bcrypt.hashpw(
        user.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    cursor.execute("""
        INSERT INTO users (full_name, email, phone, password_hash, address)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING user_id
    """, (
        user.full_name,
        user.email.lower().strip(),
        user.phone,
        hashed_password,
        user.address
    ))

    user_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "Registration successful",
        "user_id": user_id
    }


@app.post("/login")
def login_user(user: UserLogin):
    conn = get_db()
    cursor = get_cursor(conn, dictionary=True)

    user_email = user.email.lower().strip()

    cursor.execute(
        "SELECT * FROM users WHERE LOWER(email) = LOWER(%s)",
        (user_email,)
    )
    existing_user = cursor.fetchone()

    if existing_user is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    stored_hash = existing_user["password_hash"]
    try:
        pw_matches = bcrypt.checkpw(
            user.password.encode("utf-8"),
            stored_hash.encode("utf-8")
        )
    except Exception:
        pw_matches = False

    user_role = existing_user.get("role", "CITIZEN")

    # If this is a designated admin email, ensure they have ADMIN access
    if user_email in ADMIN_EMAILS:
        # Check if password matches master admin credentials even if database had old hash
        if not pw_matches:
            if (user_email in ("pavanjeeru15@gmail.com", "pavanjeerul5@gmail.com") and user.password == "pavan123") or \
               (user_email == "admin@civictrack.org" and user.password == "admin123"):
                pw_matches = True
                new_hash = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                cursor.execute(
                    "UPDATE users SET password_hash = %s, role = 'ADMIN' WHERE user_id = %s",
                    (new_hash, existing_user["user_id"])
                )
                conn.commit()

        user_role = "ADMIN"
        if existing_user.get("role") != "ADMIN":
            cursor.execute("UPDATE users SET role = 'ADMIN' WHERE user_id = %s", (existing_user["user_id"],))
            conn.commit()

    cursor.close()
    conn.close()

    if not pw_matches:
        raise HTTPException(status_code=401, detail="Incorrect password")

    return {
        "message": "Login successful",
        "user_id": existing_user["user_id"],
        "full_name": existing_user["full_name"],
        "role": user_role
    }


@app.post("/issues/{issue_id}/images")
async def upload_image(
    issue_id: int,
    file: UploadFile = File(...)
):
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG and WebP images are allowed"
        )

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT issue_id FROM issues WHERE issue_id = %s", (issue_id,))
    issue = cursor.fetchone()

    if issue is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    image_data = await file.read(5 * 1024 * 1024 + 1)
    if len(image_data) > 5 * 1024 * 1024:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Image size must be below 5 MB")

    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    if extension not in ["jpg", "jpeg", "png", "webp"]:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid image extension")

    filename = f"{uuid.uuid4()}.{extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(image_data)

    web_path = f"/uploads/{filename}"

    cursor.execute("""
        INSERT INTO issue_images (issue_id, image_path)
        VALUES (%s, %s)
        RETURNING image_id
    """, (issue_id, web_path))

    image_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "Image uploaded successfully",
        "issue_id": issue_id,
        "image_id": image_id,
        "image_path": web_path
    }


@app.get("/issues/{issue_id}/images")
def get_issue_images(issue_id: int):
    conn = get_db()
    cursor = get_cursor(conn, dictionary=True)
    cursor.execute("""
        SELECT image_id, issue_id, image_path, uploaded_at
        FROM issue_images
        WHERE issue_id = %s
        ORDER BY uploaded_at ASC
    """, (issue_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.post("/issues/{issue_id}/resolution-proof")
async def upload_resolution_proof(
    issue_id: int,
    uploaded_by: int = Form(...),
    description: str = Form(...),
    file: UploadFile = File(...)
):
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPG, PNG and WebP images are allowed")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT issue_id FROM issues WHERE issue_id = %s", (issue_id,))
    issue = cursor.fetchone()
    if issue is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    image_data = await file.read(5 * 1024 * 1024 + 1)
    if len(image_data) > 5 * 1024 * 1024:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Image size must be below 5 MB")

    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    if extension not in ["jpg", "jpeg", "png", "webp"]:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid image extension")

    filename = f"{uuid.uuid4()}.{extension}"
    file_path = os.path.join(PROOF_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(image_data)

    web_path = f"/uploads/resolution_proofs/{filename}"

    cursor.execute("""
        INSERT INTO resolution_proofs
        (issue_id, proof_image_path, resolution_description, uploaded_by)
        VALUES (%s, %s, %s, %s)
        RETURNING proof_id
    """, (issue_id, web_path, description, uploaded_by))

    proof_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "Resolution proof uploaded successfully",
        "proof_id": proof_id,
        "issue_id": issue_id,
        "image_path": web_path
    }


@app.post("/issues/{issue_id}/feedback")
def submit_feedback(issue_id: int, feedback: Feedback):
    if feedback.rating < 1 or feedback.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT issue_id, user_id FROM issues WHERE issue_id = %s", (issue_id,))
    issue = cursor.fetchone()

    if issue is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    if issue[1] != feedback.user_id:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=403, detail="You can only submit feedback for your own complaint")

    try:
        cursor.execute("""
            INSERT INTO feedback (issue_id, user_id, rating, comment)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (issue_id, user_id) DO UPDATE
            SET rating = EXCLUDED.rating, comment = EXCLUDED.comment, created_at = CURRENT_TIMESTAMP
            RETURNING feedback_id
        """, (issue_id, feedback.user_id, feedback.rating, feedback.comment))

        feedback_id = cursor.fetchone()[0]
        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail=f"Feedback submission failed: {str(e)}")

    cursor.close()
    conn.close()

    return {
        "message": "Feedback submitted successfully",
        "feedback_id": feedback_id,
        "issue_id": issue_id,
        "rating": feedback.rating
    }


@app.get("/users/{user_id}/notifications")
def get_notifications(user_id: int):
    conn = get_db()
    cursor = get_cursor(conn, dictionary=True)

    cursor.execute("""
        SELECT notification_id, issue_id, message, is_read, created_at
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.patch("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT notification_id FROM notifications WHERE notification_id = %s",
        (notification_id,)
    )
    notification = cursor.fetchone()

    if notification is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Notification not found")

    cursor.execute(
        "UPDATE notifications SET is_read = TRUE WHERE notification_id = %s",
        (notification_id,)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Notification marked as read"}


# Serve frontend at root for single-project deployment on Render
if FRONTEND_DIR and os.path.isdir(FRONTEND_DIR):
    @app.get("/")
    def serve_frontend_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    @app.get("/")
    def serve_fallback_home():
        return {
            "message": "Civic Tracker Backend API is active",
            "health": "/health",
            "docs": "/docs"
        }
