from datetime import datetime
import os
from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, session, send_file
import mysql.connector
import hashlib

app = Flask(__name__)
app.secret_key = 'my_super_secret_key'

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="studymanager"
)
cursor = db.cursor()


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
            session['user_id'] = user[0]
            return redirect(url_for('index'))
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


@app.route('/admin_panel')
def admin_panel():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    cursor.execute('SELECT id, username, role FROM users')
    users = cursor.fetchall()

    cursor.execute('''
        SELECT courses.id, courses.name, courses.description, users.username AS teacher_name
        FROM courses
        JOIN users ON courses.teacher_id = users.id
    ''')
    courses = cursor.fetchall()

    cursor.execute('''
        SELECT lectures.id, lectures.name, lectures.description, courses.name AS course_name
        FROM lectures
        JOIN courses ON lectures.course_id = courses.id
    ''')
    lectures = cursor.fetchall()

    cursor.execute("SELECT * FROM users WHERE role = 'instructor'")
    instructors = cursor.fetchall()

    cursor.execute("SELECT * FROM users WHERE role = 'student'")
    students = cursor.fetchall()

    return render_template('admin_panel.html', users=users, courses=courses, lectures=lectures, instructors=instructors, students=students)


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

    cursor.execute('''
        SELECT courses.id, courses.name, courses.description
        FROM courses
        JOIN users ON courses.teacher_id = users.id
        WHERE users.username = %s
    ''', (instructor_id,))
    courses = cursor.fetchall()

    cursor.execute('''
        SELECT users.username, courses.name
        FROM student_courses
        JOIN users ON student_courses.student_id = users.id
        JOIN courses ON student_courses.course_id = courses.id
        WHERE courses.teacher_id = %s
    ''', (session['user_id'],))
    students = cursor.fetchall()

    cursor.execute('''
        SELECT lectures.id, lectures.name, lectures.description, courses.name AS course_name
        FROM lectures
        JOIN courses ON lectures.course_id = courses.id
        WHERE courses.teacher_id = %s
    ''', (session['user_id'],))
    lectures = cursor.fetchall()

    cursor.execute('''
        SELECT assignments.id, assignments.name, assignments.description, assignments.deadline, courses.name AS course_name, username as student_name, grades.grade, assignments.file_id
        FROM assignments
        JOIN courses ON assignments.course_id = courses.id
        JOIN users ON assignments.student_id = users.id
        LEFT JOIN grades ON grades.assignment_id = assignments.id
        WHERE courses.teacher_id = %s
    ''', (session['user_id'],))
    assignments = cursor.fetchall()

    student = get_students()
    messages = get_messages(session['user_id'])

    return render_template('instructor_panel.html', courses=courses, students=students, lectures=lectures, messages=messages, student=student, assignments=assignments)


@app.route('/create_lecture', methods=['POST'])
def create_lecture():
    if 'username' not in session:
        return redirect(url_for('login'))
    else:
        try:
            name = request.form['name']
            description = request.form['description']
            course_id = request.form['course_id']

            if len(request.files) > 0:
                resource_file = request.files.get("resource_file")
                resource_dir = os.path.join(app.root_path, 'uploads')
                if not os.path.exists(resource_dir):
                    os.makedirs(resource_dir)
                resource_path = os.path.join(resource_dir, resource_file.filename)
                resource_file.save(resource_path)

                cursor.execute("INSERT INTO files (file_path) VALUES (%s)", (resource_path,))
                db.commit()

                file_id = cursor.lastrowid
                cursor.execute("INSERT INTO lectures (name, description, course_id, file_id) VALUES (%s, %s, %s, %s)", (name, description, course_id, file_id))
            else:
                cursor.execute("INSERT INTO lectures (name, description, course_id) VALUES (%s, %s, %s)", (name, description, course_id))
            db.commit
            if session.get('role') == 'admin':
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('instructor_panel'))
        except Exception as e:
            return jsonify({'error': str(e)})


@app.route('/download_file/<file_id>', methods=['GET'])
def download_file(file_id):
    cursor.execute("SELECT file_path FROM files WHERE id = %s", (file_id,))
    file_path = cursor.fetchone()
    if file_path:
        file_path = file_path[0]

        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'})


@app.route('/register_course', methods=['POST'])
def register_course():
    if 'username' not in session:
        return redirect(url_for('login'))

    course_id = request.form['course_id']
    student_id = session['user_id']

    try:

        cursor.execute("INSERT INTO student_courses_request (student_id, course_id) VALUES (%s, %s)", (student_id, course_id))
        db.commit()
        flash('Successfully registered for the course!')
    except Exception as e:
        db.rollback()
        flash('Failed to register for the course. Please try again.')

    return redirect(url_for('student_panel'))


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


@app.route('/search', methods=['GET'])
def search():
    if 'username' not in session:
        return redirect(url_for('login'))

    query = request.args.get('query')
    search_query = f"%{query}%"

    cursor.execute("""
        SELECT c.id, c.name, c.description, u.username AS teacher_name 
        FROM courses c 
        JOIN users u ON c.teacher_id = u.id 
        WHERE c.name LIKE %s OR c.description LIKE %s
    """, (search_query, search_query))
    courses = cursor.fetchall()

    cursor.execute("""
        SELECT l.id, l.name, l.description, c.name AS course_name 
        FROM lectures l 
        JOIN courses c ON l.course_id = c.id 
        WHERE l.name LIKE %s OR l.description LIKE %s
    """, (search_query, search_query))
    lectures = cursor.fetchall()

    cursor.execute("""
        SELECT id, username 
        FROM users 
        WHERE username LIKE %s
    """, (search_query,))
    users = cursor.fetchall()

    return render_template('search_results.html', query=query, courses=courses, lectures=lectures, users=users)


def get_student_info(student_id):

    cursor.execute('''
        SELECT courses.id, courses.name, courses.description, users.username AS teacher_name
        FROM student_courses
        JOIN courses ON student_courses.course_id = courses.id
        JOIN users ON courses.teacher_id = users.id
        WHERE student_courses.student_id = %s
    ''', (student_id,))
    courses = cursor.fetchall()

    cursor.execute('''
        SELECT assignments.id, assignments.name, assignments.description, assignments.deadline, courses.name AS course_name
        FROM assignments
        JOIN courses ON assignments.course_id = courses.id
        JOIN student_courses ON courses.id = student_courses.course_id
        WHERE student_courses.student_id = %s AND assignments.deadline >= NOW()
    ''', (student_id,))
    assignments = cursor.fetchall()

    cursor.execute('''
        SELECT grades.grade, grades.feedback, assignments.name AS assignment_name, courses.name AS course_name
        FROM grades
        JOIN assignments ON grades.assignment_id = assignments.id
        JOIN courses ON assignments.course_id = courses.id
        WHERE grades.student_id = %s
    ''', (student_id,))
    grades = cursor.fetchall()

    return courses, assignments, grades


def get_courses_with_registration_status(student_id):
    cursor.execute('''
        SELECT c.id, c.name, c.description, u.username AS teacher_name,
               CASE WHEN sc.student_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_registered
        FROM courses c
        LEFT JOIN student_courses sc ON c.id = sc.course_id AND sc.student_id = %s
        JOIN users u ON c.teacher_id = u.id
    ''', (student_id,))
    courses = cursor.fetchall()

    return courses


def get_teachers():
    cursor.execute("SELECT * FROM users WHERE role = 'instructor'")
    teachers = cursor.fetchall()

    return teachers


def get_students():
    cursor.execute("SELECT * FROM users WHERE role = 'student'")
    students = cursor.fetchall()

    return students


def get_messages(user_id):

    query = """
        SELECT messages.*, users.username AS sender_name
        FROM messages
        JOIN users ON messages.sender_id = users.id
        WHERE messages.recipient_id = %s
    """
    cursor.execute(query, (user_id,))
    messages = cursor.fetchall()

    return messages


@app.route('/send_message', methods=['POST'])
def send_message():
    if 'username' not in session:
        return redirect(url_for('login'))

    sender_id = session['user_id']
    recipient_id = request.form['recipient']
    message_content = request.form['message']
    timestamp = datetime.now()

    cursor.execute("SELECT role FROM users WHERE id = %s", (sender_id,))
    sender_role = cursor.fetchone()[0]

    cursor.execute("INSERT INTO messages (sender_id, recipient_id, content, timestamp) VALUES (%s, %s, %s, %s)",
                   (sender_id, recipient_id, message_content, timestamp))
    db.commit()

    if sender_role == 'instructor':
        return redirect(url_for('instructor_panel'))
    else:
        return redirect(url_for('student_panel'))


@app.route('/student_panel')
def student_panel():
    if 'username' not in session:
        return redirect(url_for('login'))

    student_id = session['user_id']
    courses, assignments, grades = get_student_info(student_id)
    available_courses = get_courses_with_registration_status(student_id)
    teachers = get_teachers()
    messages = get_messages(student_id)

    return render_template('student_panel.html', courses=courses, assignments=assignments, grades=grades,
                           available_courses=available_courses, teachers=teachers, messages=messages)


@app.route('/assign_course_to_instructor', methods=['POST'])
def assign_course_to_instructor():
    instructor_id = request.form['instructor_id']
    course_id = request.form['course_id']

    cursor.execute("UPDATE courses SET teacher_id = %s WHERE id = %s", (instructor_id, course_id))
    db.commit()

    return redirect(url_for('admin_panel'))


@app.route('/register_student_for_course', methods=['POST'])
def register_student_for_course():
    student_id = request.form['student_id']
    course_id =  request.form['course_id']

    cursor.execute("INSERT INTO student_courses (student_id, course_id) VALUES (%s, %s)", (student_id, course_id))
    db.commit()

    return redirect(url_for('admin_panel'))


@app.route('/create_assignment', methods=['POST'])
def create_assignment():
    if 'username' not in session:
        return redirect(url_for('login'))
    else:
        try:
            name = request.form['name']
            description = request.form['description']
            deadline = request.form['deadline']
            course_id = request.form['course_id']

            cursor.execute("SELECT student_id FROM student_courses WHERE course_id = %s", (course_id,))
            students = cursor.fetchall()

            for student in students:
                cursor.execute(
                    "INSERT INTO assignments (name, description, deadline, course_id, student_id, status) VALUES (%s, %s, %s, %s, %s, %s)",
                    (name, description, deadline, course_id, student[0], 'pending')
                )
            db.commit()

            if session.get('role') == 'admin':
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('instructor_panel'))
        except Exception as e:
            return jsonify({'error': str(e)})


@app.route('/grade_submission', methods=['POST'])
def grade_submission():
    if 'username' not in session:
        return redirect(url_for('login'))
    else:
        try:
            student_id = request.form['student_id']
            assignment_id = request.form['assignment_id']
            grade = request.form['grade']
            feedback = request.form['feedback']

            cursor.execute("INSERT INTO grades (student_id, assignment_id, grade, feedback) VALUES (%s, %s, %s, %s)", (student_id, assignment_id, grade, feedback))
            db.commit()

            if session.get('role') == 'admin':
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('instructor_panel'))
        except Exception as e:
            return jsonify({'error': str(e)})


@app.route('/upload_file/<assignment_id>', methods=['POST'])
def upload_file(assignment_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    if file:
        filename = file.filename
        upload_folder = os.path.join(app.root_path, 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        cursor.execute("INSERT INTO files (file_path) VALUES (%s)", (file_path,))
        db.commit()

        file_id = cursor.lastrowid
        cursor.execute("UPDATE assignments SET file_id = %s WHERE id = %s", (file_id, assignment_id))
        db.commit()

        return redirect(url_for('student_panel'))

    return jsonify({'error': 'File upload failed'})


if __name__ == '__main__':
    app.run(debug=True)

