
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
import mysql.connector
import uuid
import os
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
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "civic_tracker")
    )
    return conn
    

# Create database tables



# Data received from frontend
class Issue(BaseModel):
    user_id: int
    category_id: int
    title: str
    description: str
    location: str
    latitude: float | None = None
    longitude: float | None = None
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"

# Home page
@app.get("/")
def home():
    return {"message": "Welcome to Civic Tracker Backend"}





# 2. View all complaints
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

    issue_id = cursor.lastrowid

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

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "Complaint submitted successfully",
        "complaint_id": complaint_id,
        "status": "SUBMITTED"
    }

# 2. View all complaints
@app.get("/issues")
def get_issues():

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            i.issue_id,
            i.issue_code,
            i.title,
            i.description,
            i.location,
            i.priority,
            i.status,
            i.created_at,
            c.category_name
        FROM issues i
        JOIN categories c
        ON i.category_id = c.category_id
    """)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows




# 3. Search for a complaint using ID
@app.get("/issues/{issue_id}")
def get_issue(issue_id: int):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            i.issue_id,
            i.issue_code,
            i.title,
            i.description,
            i.location,
            i.priority,
            i.status,
            i.created_at,
            c.category_name
        FROM issues i
        JOIN categories c
        ON i.category_id = c.category_id
        WHERE i.issue_id = %s
    """, (issue_id,))

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found"
        )

    return row





# 4. Update complaint status
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
        "SELECT status FROM issues WHERE issue_id = %s",
        (issue_id,)
    )

    row = cursor.fetchone()

    if row is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    old_status = row[0]

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

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "Status updated successfully",
        "status": status
    }


# 5. View unresolved complaints
@app.get("/unresolved")
def unresolved_issues():

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM issues
        WHERE status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED')
    """)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows




# 6. View status history
@app.get("/issues/{issue_id}/history")
def get_history(issue_id: int):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT old_status, new_status, updated_by, remarks, updated_at
        FROM issue_status_history
        WHERE issue_id = %s
        ORDER BY history_id
    """, (issue_id,))

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows




# 7. Dashboard statistics
@app.get("/dashboard")
def dashboard():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM issues")
    total = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM issues
        WHERE status = 'SUBMITTED'
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




# 8. Assign complaint to a department
@app.patch("/issues/{issue_id}/department")
def assign_department(
    issue_id: int,
    department_id: int,
    assigned_by: int
):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT status FROM issues WHERE issue_id = %s",
        (issue_id,)
    )

    row = cursor.fetchone()

    if row is None:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Complaint not found"
        )

    old_status = row[0]

    cursor.execute("""
        INSERT INTO issue_assignments
        (issue_id, department_id, assigned_by)
        VALUES (%s, %s, %s)
    """, (issue_id, department_id, assigned_by))

    cursor.execute("""
        UPDATE issues
        SET status = 'ASSIGNED'
        WHERE issue_id = %s
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

    conn.commit()

    cursor.close()
    conn.close()

    return {
        "message": "Department assigned successfully",
        "issue_id": issue_id,
        "department_id": department_id,
        "status": "ASSIGNED"
    }
