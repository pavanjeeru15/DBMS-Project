
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
import sqlite3
import uuid
from datetime import datetime

app = FastAPI(title="Civic Tracker Backend")

# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Database connection
def get_db():
    conn = sqlite3.connect("civic.db")
    conn.row_factory = sqlite3.Row
    return conn

# Create database tables
def create_tables():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id TEXT PRIMARY KEY,
            category TEXT,
            description TEXT,
            location TEXT,
            priority TEXT,
            status TEXT,
            department TEXT,
            created_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id TEXT,
            status TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

create_tables()


# Data received from frontend
class Issue(BaseModel):
    category: str
    description: str
    location: str
    priority: Literal["Low", "Medium", "High", "Critical"] = "Medium"


# Home page
@app.get("/")
def home():
    return {"message": "Welcome to Civic Tracker Backend"}


# 1. Report a new issue
@app.post("/issues")
def report_issue(issue: Issue):

    conn = get_db()

    complaint_id = "CT" + uuid.uuid4().hex[:8].upper()

    conn.execute("""
        INSERT INTO issues
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint_id,
        issue.category,
        issue.description,
        issue.location,
        issue.priority,
        "Pending",
        "Not Assigned",
        datetime.now().isoformat()
    ))

    conn.execute("""
        INSERT INTO status_history
        (issue_id, status, updated_at)
        VALUES (?, ?, ?)
    """, (complaint_id, "Pending", datetime.now().isoformat()))

    conn.commit()
    conn.close()

    return {
        "message": "Complaint submitted successfully",
        "complaint_id": complaint_id,
        "status": "Pending"
    }


# 2. View all complaints
@app.get("/issues")
def get_issues():

    conn = get_db()
    rows = conn.execute("SELECT * FROM issues").fetchall()
    conn.close()

    return [dict(row) for row in rows]


# 3. Search for a complaint using ID
@app.get("/issues/{issue_id}")
def get_issue(issue_id: str):

    conn = get_db()

    row = conn.execute(
        "SELECT * FROM issues WHERE id = ?",
        (issue_id,)
    ).fetchone()

    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    return dict(row)


# 4. Update complaint status
@app.patch("/issues/{issue_id}/status")
def update_status(
    issue_id: str,
    status: Literal[
        "Pending", "Assigned", "In Progress", "Resolved", "Rejected"
    ]
):

    conn = get_db()

    row = conn.execute(
        "SELECT id FROM issues WHERE id = ?",
        (issue_id,)
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    conn.execute(
        "UPDATE issues SET status = ? WHERE id = ?",
        (status, issue_id)
    )

    conn.execute("""
        INSERT INTO status_history
        (issue_id, status, updated_at)
        VALUES (?, ?, ?)
    """, (issue_id, status, datetime.now().isoformat()))

    conn.commit()
    conn.close()

    return {"message": "Status updated successfully", "status": status}


# 5. View unresolved complaints
@app.get("/unresolved")
def unresolved_issues():

    conn = get_db()

    rows = conn.execute("""
        SELECT * FROM issues
        WHERE status != 'Resolved'
        AND status != 'Rejected'
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


# 6. View status history
@app.get("/issues/{issue_id}/history")
def get_history(issue_id: str):

    conn = get_db()

    rows = conn.execute("""
        SELECT status, updated_at
        FROM status_history
        WHERE issue_id = ?
        ORDER BY id
    """, (issue_id,)).fetchall()

    conn.close()

    return [dict(row) for row in rows]


# 7. Dashboard statistics

@app.get("/dashboard")
def dashboard():

    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM issues"
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM issues WHERE status = 'Pending'"
    ).fetchone()[0]

    in_progress = conn.execute(
        "SELECT COUNT(*) FROM issues WHERE status = 'In Progress'"
    ).fetchone()[0]

    resolved = conn.execute(
        "SELECT COUNT(*) FROM issues WHERE status = 'Resolved'"
    ).fetchone()[0]

    unresolved = conn.execute("""
        SELECT COUNT(*) FROM issues
        WHERE status NOT IN ('Resolved', 'Rejected')
    """).fetchone()[0]

    conn.close()

    return {
        "total_complaints": total,
        "pending": pending,
        "in_progress": in_progress,
        "resolved": resolved,
        "unresolved": unresolved
    }


# 8. Assign complaint to a department

@app.patch("/issues/{issue_id}/department")
def assign_department(issue_id: str, department: str):

    conn = get_db()

    row = conn.execute(
        "SELECT id FROM issues WHERE id = ?",
        (issue_id,)
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Complaint not found"
        )

    conn.execute(
        "UPDATE issues SET department = ? WHERE id = ?",
        (department, issue_id)
    )

    conn.commit()
    conn.close()

    return {
        "message": "Department assigned successfully",
        "complaint_id": issue_id,
        "department": department
    }
