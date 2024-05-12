from flask import Flask, render_template, request, redirect, url_for, session
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

# Logout route
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

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
            # 未知角色处理
            return render_template('error.html', error="Unknown user role") 

@app.route('/admin_panel')
def admin_panel():
    return render_template('admin_panel.html')

@app.route('/instructor_panel')
def instructor_panel():
    return render_template('instructor_panel.html')

@app.route('/student_panel')
def student_panel():
    return render_template('student_panel.html')

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        # 检查用户名是否已经存在
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()
        if existing_user:
            return render_template('register.html', error="Username already exists")
        
        # 对密码进行哈希处理
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # 插入新用户到数据库
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", (username, hashed_password, role))
        db.commit()
        
        # 注册成功后重定向到登录页面
        return redirect(url_for('login'))
    else:
        return render_template('register.html')

if __name__ == '__main__':
    app.run(debug=True)
