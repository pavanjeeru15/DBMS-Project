import mysql.connector
import os

from fastapi import FastAPI, HTTPException, UploadFile, File
import mysql.connector

password = getpass("Enter MySQL root password: ")


from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
import mysql.connector
import uuid
import os
import bcrypt
from datetime import datetime

app = FastAPI(title="Civic Tracker Backend")

# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Database connection
def get_db():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
    return conn
def create_notification(conn, user_id, issue_id, message):

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO notifications
        (user_id, issue_id, message)
        VALUES (%s, %s, %s)
    """, (user_id, issue_id, message))

    cursor.close()    

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
class UserRegister(BaseModel):
    full_name: str
    email: str
    phone: str
    password: str
    address: str
class UserLogin(BaseModel):
    email: str
    password: str    
# Home page
@app.get("/")
def home():
    return {"message": "Welcome to Civic Tracker Backend"}
class Feedback(BaseModel):
    user_id: int
    rating: int
    comment: str




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
    "SELECT status, user_id FROM issues WHERE issue_id = %s",
    (issue_id,)
)

    row = cursor.fetchone()

    if row is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    old_status = row[0]
    user_id = row[1]

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
        "Your complaint status has been updated to " + status
)
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

    # Count SUBMITTED and ASSIGNED complaints as Pending
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
    "SELECT status, user_id FROM issues WHERE issue_id = %s",
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
    user_id = row[1]

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
# 9. User registration
@app.post("/register")
def register_user(user: UserRegister):

    conn = get_db()
    cursor = conn.cursor()

    # Check whether email already exists
    cursor.execute(
        "SELECT user_id FROM users WHERE email = %s",
        (user.email,)
    )

    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    # Hash the password
    hashed_password = bcrypt.hashpw(
        user.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # Insert user details
    cursor.execute("""
        INSERT INTO users
        (full_name, email, phone, password_hash, address)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        user.full_name,
        user.email,
        user.phone,
        hashed_password,
        user.address
    ))

    conn.commit()

    user_id = cursor.lastrowid

    cursor.close()
    conn.close()

    return {
        "message": "Registration successful",
        "user_id": user_id
    }
# 10. User login
@app.post("/login")
def login_user(user: UserLogin):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM users WHERE email = %s",
        (user.email,)
    )

    existing_user = cursor.fetchone()

    cursor.close()
    conn.close()

    if existing_user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Verify password
    if not bcrypt.checkpw(
        user.password.encode("utf-8"),
        existing_user["password_hash"].encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect password"
        )

    return {
        "message": "Login successful",
        "user_id": existing_user["user_id"],
        "full_name": existing_user["full_name"],
        "role": existing_user["role"]
    }
# 11. Upload issue image
@app.post("/issues/{issue_id}/images")
async def upload_image(
    issue_id: int,
    file: UploadFile = File(...)
):

    # Allowed image formats
    allowed_types = ["image/jpeg", "image/png", "image/webp"]

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG and WebP images are allowed"
        )

    # Check whether issue exists
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT issue_id FROM issues WHERE issue_id = %s",
        (issue_id,)
    )

    issue = cursor.fetchone()

    if issue is None:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Complaint not found"
        )

    # Read image and limit size to 5 MB
    image_data = await file.read(5 * 1024 * 1024 + 1)

    if len(image_data) > 5 * 1024 * 1024:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Image size must be below 5 MB"
        )

    # Create uploads folder
    os.makedirs("uploads", exist_ok=True)

    # Generate unique filename
    extension = file.filename.rsplit(".", 1)[-1].lower()

    if extension not in ["jpg", "jpeg", "png", "webp"]:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Invalid image extension"
        )

    filename = str(uuid.uuid4()) + "." + extension
    file_path = os.path.join("uploads", filename)

    # Save image
    with open(file_path, "wb") as image:
        image.write(image_data)

    # Store image path in database
    cursor.execute("""
        INSERT INTO issue_images
        (issue_id, image_path)
        VALUES (%s, %s)
    """, (issue_id, file_path))

    conn.commit()

    cursor.close()
    conn.close()

    return {
        "message": "Image uploaded successfully",
        "issue_id": issue_id,
        "image_path": file_path
    }
# 12. Upload resolution proof
@app.post("/issues/{issue_id}/resolution-proof")
async def upload_resolution_proof(
    issue_id: int,
    uploaded_by: int,
    description: str,
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

    # Check whether issue exists
    cursor.execute(
        "SELECT issue_id FROM issues WHERE issue_id = %s",
        (issue_id,)
    )

    issue = cursor.fetchone()

    if issue is None:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Complaint not found"
        )

    # Read image (maximum 5 MB)
    image_data = await file.read(5 * 1024 * 1024 + 1)

    if len(image_data) > 5 * 1024 * 1024:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Image size must be below 5 MB"
        )

    os.makedirs("uploads/resolution_proofs", exist_ok=True)

    extension = file.filename.rsplit(".", 1)[-1].lower()

    if extension not in ["jpg", "jpeg", "png", "webp"]:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Invalid image extension"
        )

    filename = str(uuid.uuid4()) + "." + extension
    file_path = os.path.join("uploads/resolution_proofs", filename)

    with open(file_path, "wb") as image:
        image.write(image_data)

    cursor.execute("""
        INSERT INTO resolution_proofs
        (issue_id, proof_image_path, resolution_description, uploaded_by)
        VALUES (%s, %s, %s, %s)
    """, (
        issue_id,
        file_path,
        description,
        uploaded_by
    ))

    conn.commit()

    cursor.close()
    conn.close()

    return {
        "message": "Resolution proof uploaded successfully",
        "issue_id": issue_id,
        "image_path": file_path
    }
# 13. Submit feedback
@app.post("/issues/{issue_id}/feedback")
def submit_feedback(issue_id: int, feedback: Feedback):

    # Validate rating
    if feedback.rating < 1 or feedback.rating > 5:
        raise HTTPException(
            status_code=400,
            detail="Rating must be between 1 and 5"
        )

    conn = get_db()
    cursor = conn.cursor()

    # Check whether issue exists and get its owner
    cursor.execute(
        """
        SELECT issue_id, user_id
        FROM issues
        WHERE issue_id = %s
        """,
        (issue_id,)
    )

    issue = cursor.fetchone()

    if issue is None:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Complaint not found"
        )

    # Check whether the user owns this complaint
    if issue[1] != feedback.user_id:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=403,
            detail="You can only submit feedback for your own complaint"
        )

    # Insert feedback
    try:
        cursor.execute(
            """
            INSERT INTO feedback
            (issue_id, user_id, rating, comment)
            VALUES (%s, %s, %s, %s)
            """,
            (
                issue_id,
                feedback.user_id,
                feedback.rating,
                feedback.comment
            )
        )

        conn.commit()

    except mysql.connector.IntegrityError:
        conn.rollback()
        cursor.close()
        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Feedback already submitted or invalid user"
        )

    cursor.close()
    conn.close()

    return {
        "message": "Feedback submitted successfully",
        "issue_id": issue_id,
        "rating": feedback.rating
    }
# 14. View notifications
@app.get("/users/{user_id}/notifications")
def get_notifications(user_id: int):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

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
# 15. Mark notification as read
@app.patch("/notifications/{notification_id}/read")
@app.patch("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT notification_id
        FROM notifications
        WHERE notification_id = %s
    """, (notification_id,))

    notification = cursor.fetchone()

    if notification is None:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Notification not found"
        )

    cursor.execute("""
        UPDATE notifications
        SET is_read = TRUE
        WHERE notification_id = %s
    """, (notification_id,))

    conn.commit()

    cursor.close()
    conn.close()

    return {
        "message": "Notification marked as read"
    }
