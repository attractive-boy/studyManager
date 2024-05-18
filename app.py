import os
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
import mysql.connector
import hashlib

app = Flask(__name__)
app.secret_key = 'secret_key'

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="studymanager"
)
cursor = db.cursor()

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password = hashlib.sha256(password.encode()).hexdigest()
        
        cursor.execute("SELECT * FROM users WHERE username = %s AND password_hash = %s", (username, password))
        user = cursor.fetchone()
        
        if user:
            session['username'] = user[1]
            session['role'] = user[3]
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid credentials")
    else:
        return render_template('login.html')

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    else:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_panel'))
        elif role == 'instructor':
            return redirect(url_for('instructor_panel'))
        elif role == 'student':
            return redirect(url_for('student_panel'))
        else:
            return render_template('error.html', error="Unknown user role") 

@app.route('/admin_panel')
def admin_panel():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
     # Fetch all users
    cursor.execute('SELECT id, username, role FROM users')
    users = cursor.fetchall()
    
    # Fetch all courses
    cursor.execute('''
        SELECT courses.id, courses.name, courses.description, users.username AS teacher_name
        FROM courses
        JOIN users ON courses.teacher_id = users.id
    ''')
    courses = cursor.fetchall()

    # Fetch all lectures
    cursor.execute('''
        SELECT lectures.id, lectures.name, lectures.description, courses.name AS course_name
        FROM lectures
        JOIN courses ON lectures.course_id = courses.id
    ''')
    lectures = cursor.fetchall()

    return render_template('admin_panel.html', users=users, courses=courses, lectures=lectures)

# User management routes
@app.route('/create_user', methods=['POST'])
def create_user():
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", (username, hashed_password, role))
    db.commit()
    return redirect(url_for('admin_panel'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()
    return redirect(url_for('admin_panel'))

# Course management routes
@app.route('/create_course', methods=['POST'])
def create_course():
    name = request.form['name']
    description = request.form['description']
    teacher_id = request.form['teacher_id']
    
    cursor.execute("INSERT INTO courses (name, description, teacher_id) VALUES (%s, %s, %s)", (name, description, teacher_id))
    db.commit()
    return redirect(url_for('admin_panel'))

@app.route('/delete_course/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    cursor.execute("DELETE FROM courses WHERE id = %s", (course_id,))
    db.commit()
    return redirect(url_for('admin_panel'))

@app.route('/delete_lecture/<int:lecture_id>', methods=['POST'])
def delete_lecture(lecture_id):
    cursor.execute("DELETE FROM lectures WHERE id = %s", (lecture_id,))
    db.commit()
    return redirect(url_for('admin_panel'))

@app.route('/instructor_panel')
def instructor_panel():
    if 'username' not in session or session['role'] != 'instructor':
        return redirect(url_for('login'))
    
    instructor_id = session['username']
    
    # Fetch courses the instructor is teaching
    cursor.execute('''
        SELECT courses.id, courses.name, courses.description
        FROM courses
        JOIN users ON courses.teacher_id = users.id
        WHERE users.username = %s
    ''', (instructor_id,))
    courses = cursor.fetchall()
    
    # Fetch students for the courses the instructor is teaching
    cursor.execute('''
        SELECT users.username, courses.name
        FROM student_courses
        JOIN users ON student_courses.student_id = users.id
        JOIN courses ON student_courses.course_id = courses.id
        WHERE courses.teacher_id = %s
    ''', (instructor_id,))
    students = cursor.fetchall()

    # Fetch lectures for the courses the instructor is teaching
    cursor.execute('''
        SELECT lectures.id, lectures.name, lectures.description, courses.name AS course_name
        FROM lectures
        JOIN courses ON lectures.course_id = courses.id
        WHERE courses.teacher_id = %s
    ''', (instructor_id,))
    lectures = cursor.fetchall()

    return render_template('instructor_panel.html', courses=courses, students=students, lectures=lectures)

@app.route('/create_lecture', methods=['POST'])
def create_lecture():
    if 'username' not in session:
        return redirect(url_for('login'))
    else:
        name = request.form['name']
        description = request.form['description']
        course_id = request.form['course_id']
        cursor.execute("INSERT INTO lectures (name, description, course_id) VALUES (%s, %s, %s)", (name, description, course_id))
        db.commit()
        if session.get('role') == 'admin':
            return redirect(url_for('admin_panel')) # Redirect to admin panel after creating lecture
        else:
            return redirect(url_for('instructor_panel')) # Redirect to instructor panel after creating lecture

@app.route('/upload_resource', methods=['POST'])
def upload_resource():
    if 'username' not in session:
        return redirect(url_for('login'))
    else:
        try:
            resource_file = request.files['resource_file']
            if resource_file:
                # Save the uploaded file to a specific directory
                resource_dir = os.path.join(app.root_path, 'uploads')
                if not os.path.exists(resource_dir):
                    os.makedirs(resource_dir)
                resource_path = os.path.join(resource_dir, resource_file.filename)
                resource_file.save(resource_path)
                # Store the file path and lecture ID in the database
                cursor.execute("INSERT INTO files (file_path) VALUES (%s)", (resource_path,))
                db.commit()
                # Get the ID of the inserted file
                file_id = cursor.lastrowid
                # Return the file ID as JSON response
                return jsonify({'file_id': file_id})
            else:
                return "No file uploaded"
        except Exception as e:
            # Handle any exceptions that occur during file upload or database operation
            return jsonify({'error': str(e)})

        
@app.route('/student_panel')
def student_panel():
    if 'username' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    student_id = session['username']
    # Fetch courses the student is enrolled in
    cursor.execute('''
        SELECT courses.id, courses.name, courses.description, users.username AS teacher_name
        FROM student_courses
        JOIN courses ON student_courses.course_id = courses.id
        JOIN users ON courses.teacher_id = users.id
        WHERE student_courses.student_id = %s
    ''', (student_id,))
    courses = cursor.fetchall()

    # Fetch assignments for the courses the student is enrolled in
    cursor.execute('''
        SELECT assignments.id, assignments.name, assignments.description, assignments.deadline, courses.name AS course_name
        FROM assignments
        JOIN courses ON assignments.course_id = courses.id
        JOIN student_courses ON courses.id = student_courses.course_id
        WHERE student_courses.student_id = %s AND assignments.deadline >= NOW()
    ''', (student_id,))
    assignments = cursor.fetchall()

    # Fetch grades for the student
    cursor.execute('''
        SELECT grades.grade, grades.feedback, assignments.name AS assignment_name, courses.name AS course_name
        FROM grades
        JOIN assignments ON grades.assignment_id = assignments.id
        JOIN courses ON assignments.course_id = courses.id
        WHERE grades.student_id = %s
    ''', (student_id,))
    grades = cursor.fetchall()

    return render_template('student_panel.html', courses=courses, assignments=assignments, grades=grades)

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()
        if existing_user:
            return render_template('register.html', error="Username already exists")
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", (username, hashed_password, role))
        db.commit()

        return redirect(url_for('login'))
    else:
        return render_template('register.html')
    


if __name__ == '__main__':
    app.run(debug=True)
