CREATE DATABASE if not exists civic_tracker;
USE civic_tracker;
CREATE TABLE if not exists users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(10),
    password_hash VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    role ENUM('CITIZEN', 'ADMIN') DEFAULT 'CITIZEN',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
DESCRIBE users;
INSERT INTO users
(full_name, email, phone, password_hash, address)
VALUES
('Test User', 'test@gmail.com', '9876543210', 'temporary_hash', 'Anantapur');
CREATE TABLE departments (
    department_id INT PRIMARY KEY AUTO_INCREMENT,
    department_name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE categories (
    category_id INT PRIMARY KEY AUTO_INCREMENT,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255),
    department_id INT,
    
    FOREIGN KEY (department_id)
        REFERENCES departments(department_id)
);
CREATE TABLE issues (
    issue_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_code VARCHAR(20) UNIQUE NOT NULL,
    
    user_id INT NOT NULL,
    category_id INT NOT NULL,
    
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    
    location VARCHAR(255) NOT NULL,
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    
    priority ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
        DEFAULT 'MEDIUM',
        
    status ENUM(
        'SUBMITTED',
        'UNDER_REVIEW',
        'ASSIGNED',
        'IN_PROGRESS',
        'RESOLVED',
        'CLOSED',
        'REJECTED'
    ) DEFAULT 'SUBMITTED',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id)
        REFERENCES users(user_id),
        
    FOREIGN KEY (category_id)
        REFERENCES categories(category_id)
);
CREATE TABLE issue_images (
    image_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_id INT NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (issue_id)
        REFERENCES issues(issue_id)
        ON DELETE CASCADE
);
CREATE TABLE issue_assignments (
    assignment_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_id INT NOT NULL,
    department_id INT NOT NULL,
    assigned_by INT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (issue_id)
        REFERENCES issues(issue_id)
        ON DELETE CASCADE,

    FOREIGN KEY (department_id)
        REFERENCES departments(department_id),

    FOREIGN KEY (assigned_by)
        REFERENCES users(user_id)
);
CREATE TABLE issue_status_history (
    history_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_id INT NOT NULL,
    old_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    updated_by INT NOT NULL,
    remarks VARCHAR(500),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (issue_id)
        REFERENCES issues(issue_id)
        ON DELETE CASCADE,

    FOREIGN KEY (updated_by)
        REFERENCES users(user_id)
);
CREATE TABLE resolution_proofs (
    proof_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_id INT NOT NULL,
    proof_image_path VARCHAR(500),
    resolution_description VARCHAR(500),
    uploaded_by INT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (issue_id)
        REFERENCES issues(issue_id)
        ON DELETE CASCADE,

    FOREIGN KEY (uploaded_by)
        REFERENCES users(user_id)
);
CREATE TABLE feedback (
    feedback_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_id INT NOT NULL,
    user_id INT NOT NULL,
    rating INT NOT NULL,
    comment VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (issue_id)
        REFERENCES issues(issue_id)
        ON DELETE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id),

    CONSTRAINT chk_rating
        CHECK (rating BETWEEN 1 AND 5),

    UNIQUE (issue_id, user_id)
);
CREATE TABLE notifications (
    notification_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    issue_id INT,
    message VARCHAR(500) NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    FOREIGN KEY (issue_id)
        REFERENCES issues(issue_id)
        ON DELETE CASCADE
);
SHOW TABLES;
SELECT * FROM users;
SELECT * FROM departments;
SELECT * FROM categories;
SELECT
    c.category_id,
    c.category_name,
    d.department_name
FROM categories c
JOIN departments d
ON c.department_id = d.department_id;
INSERT INTO departments (department_name, description)
VALUES
('Roads', 'Handles damaged roads, potholes and road maintenance'),
('Water Supply', 'Handles water supply and pipeline problems'),
('Sanitation', 'Handles garbage and sanitation complaints'),
('Street Lighting', 'Handles streetlight problems'),
('Drainage', 'Handles drainage and sewage problems'),
('Electricity', 'Handles public electricity-related issues');
INSERT INTO categories
(category_name, description, department_id)
VALUES
('Potholes', 'Damaged roads and potholes', 1),
('Road Damage', 'Road maintenance problems', 1),
('Garbage', 'Garbage collection and waste problems', 3),
('Water Supply', 'Water supply problems', 2),
('Streetlight', 'Broken or non-working streetlights', 4),
('Drainage', 'Blocked drains and drainage problems', 5),
('Electricity', 'Public electricity problems', 6);
INSERT INTO issues
(
    issue_code,
    user_id,
    category_id,
    title,
    description,
    location,
    latitude,
    longitude,
    priority
)
VALUES
(
    'CT000001',
    1,
    1,
    'Large pothole on main road',
    'There is a large pothole near the main road which is causing problems for vehicles.',
    'Main Road, Anantapur',
    14.6819,
    77.6006,
    'HIGH'
);
SELECT * FROM issues;
SELECT
    i.issue_code,
    u.full_name AS citizen,
    c.category_name,
    d.department_name,
    i.title,
    i.priority,
    i.status,
    i.location
FROM issues i
JOIN users u
    ON i.user_id = u.user_id
JOIN categories c
    ON i.category_id = c.category_id
JOIN departments d
    ON c.department_id = d.department_id;
    USE civic_tracker;

SHOW TABLES;
SELECT * FROM users;
SELECT * FROM departments;
SELECT * FROM categories;
SELECT * FROM issues;
SELECT * FROM issue_images;
SELECT * FROM issue_assignments;
SELECT * FROM issue_status_history;
SELECT * FROM resolution_proofs;
SELECT * FROM feedback;
SELECT * FROM notifications;
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    CONSTRAINT_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'civic_tracker'
AND REFERENCED_TABLE_NAME IS NOT NULL;

