from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
import psycopg
from psycopg.rows import dict_row
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import csv
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Optional PDF imports with error handling
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("PDF export disabled - reportlab not installed")

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'nemsu_ccms_secret_key_2024')

# Force template reloading and debug info
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# Debug template loading
print("=== TEMPLATE DEBUG INFO ===")
print(f"Current directory: {os.getcwd()}")
print(f"Template folder: {app.template_folder}")
print(f"Templates exist: {os.path.exists('templates')}")
print(f"Files in templates: {os.listdir('templates') if os.path.exists('templates') else 'NOT FOUND'}")
print("===========================")

# Disable caching
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# PostgreSQL Configuration for Render
def get_db_connection():
    try:
        database_url = os.environ.get('DATABASE_URL', 'postgresql://nemsu_ccms_db_user:EAl83jcPEvy8kDYKXMY05Qu8n4WxAamU@dpg-d4jun67diees73b5ld7g-a.oregon-postgres.render.com:5432/nemsu_ccms_db')
        
        # Fix for Render PostgreSQL URL format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        print(f"Connecting to database: {database_url.split('@')[1] if '@' in database_url else database_url}")
        conn = psycopg.connect(database_url, row_factory=dict_row)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_database():
    """Initialize database tables if they don't exist"""
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Cannot initialize database - no connection")
            return
            
        cur = conn.cursor()
        
        # Create users table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                student_id VARCHAR(20) UNIQUE,
                role VARCHAR(20) NOT NULL DEFAULT 'student',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create complaint_categories table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS complaint_categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create complaints table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS complaints (
                id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES users(id),
                category_id INTEGER REFERENCES complaint_categories(id),
                incident_date DATE,
                incident_time TIME,
                location VARCHAR(200),
                description TEXT NOT NULL,
                photo_path VARCHAR(255),
                status VARCHAR(20) DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create messages table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                sender_id INTEGER REFERENCES users(id),
                receiver_id INTEGER REFERENCES users(id),
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create admin_responses table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS admin_responses (
                id SERIAL PRIMARY KEY,
                complaint_id INTEGER REFERENCES complaints(id),
                admin_id INTEGER REFERENCES users(id),
                response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create feedback table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES users(id),
                complaint_id INTEGER REFERENCES complaints(id),
                rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default complaint categories
        categories = [
            ('Academic Issues', 'Problems related to courses, grades, or faculty'),
            ('Facility Problems', 'Issues with classrooms, buildings, or equipment'),
            ('Administrative Concerns', 'Problems with registration, records, or offices'),
            ('Security Issues', 'Safety and security concerns'),
            ('Other', 'Other types of complaints')
        ]
        
        for category in categories:
            cur.execute(
                "INSERT INTO complaint_categories (name, description) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
                category
            )
        
        # Create default admin user
        admin_password = generate_password_hash('admin123')
        cur.execute('''
            INSERT INTO users (username, password, email, full_name, role) 
            VALUES ('admin', %s, 'admin@nemsu.edu.ph', 'System Administrator', 'admin')
            ON CONFLICT (username) DO NOTHING
        ''', (admin_password,))
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

# Initialize database when app starts
init_database()

# File upload configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Email Configuration - UPDATE THESE WITH REAL CREDENTIALS
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nemsu.ccms@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_app_password_here'
app.config['MAIL_DEFAULT_SENDER'] = 'nemsu.ccms@gmail.com'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_logged_in():
    return 'user_id' in session

def is_admin():
    return session.get('role') == 'admin'

def is_student():
    return session.get('role') == 'student'

def send_email(to_email, subject, message):
    """Send email to student - Currently in development mode (prints to console)"""
    try:
        # For development - print the email instead of sending
        print("=" * 50)
        print("📧 EMAIL NOTIFICATION (Development Mode)")
        print("=" * 50)
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Message:\n{message}")
        print("=" * 50)
        print("💡 To enable real email sending:")
        print("   1. Update MAIL_USERNAME and MAIL_PASSWORD in app.py")
        print("   2. Uncomment the email sending code in send_email() function")
        print("=" * 50)

        return True  # Return True even in dev mode to continue flow
    except Exception as e:
        print(f"❌ Email error: {str(e)}")
        return False

# Automatic Response Templates
RESPONSE_TEMPLATES = {
    'Pending': {
        'subject': 'Complaint Received - NEMSU CCMS',
        'template': """Hello <b>{student_name}</b>,<br><br>
Your complaint regarding <b>{complaint_category}</b> has been received and is now under review.<br><br>
Our team will assess your complaint and begin processing it shortly. You will receive updates on the progress.<br><br>
Thank you for using NEMSU CCMS.<br><br>
Best regards,<br>
NEMSU Administration"""
    },
    'In Progress': {
        'subject': 'Complaint Update - NEMSU CCMS',
        'template': """Hello <b>{student_name}</b>,<br><br>
Your complaint about <b>{complaint_category}</b> is currently being processed by our team.<br><br>
We are actively working on resolving your issue and will notify you once there are further updates.<br><br>
We appreciate your patience and understanding.<br><br>
Best regards,<br>
NEMSU Administration"""
    },
    'Solved': {
        'subject': 'Complaint Resolved - NEMSU CCMS',
        'template': """Hello <b>{student_name}</b>,<br><br>
Your complaint regarding <b>{complaint_category}</b> has been successfully resolved.<br><br>
The issue has been addressed and your case is now closed. Thank you for bringing this matter to our attention.<br><br>
If you have any further concerns, please don't hesitate to contact us.<br><br>
Best regards,<br>
NEMSU Administration"""
    }
}

# Debug Routes
@app.route('/debug/db')
def debug_db():
    """Check database connection and tables"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cur.fetchall()
        
        # Check users
        cur.execute("SELECT COUNT(*) as count FROM users")
        user_count = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'tables': [table['table_name'] for table in tables],
            'user_count': user_count['count'],
            'status': 'Database connected successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/debug/users')
def debug_users():
    """Check existing users"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, email, role, student_id FROM users ORDER BY id")
        users = cur.fetchall()
        cur.close()
        conn.close()
        
        result = []
        for user in users:
            result.append({
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'student_id': user['student_id']
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)})

# Main Website Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# Student Authentication
@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if is_logged_in() and is_student():
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        if not conn:
            flash('Database connection failed. Please try again.', 'danger')
            return render_template('student_login.html')
            
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND role = 'student'", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['student_id'] = user['student_id']
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid student credentials', 'danger')
    return render_template('student_login.html')

@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if is_logged_in() and is_student():
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        full_name = request.form['full_name']
        student_id = request.form['student_id']
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        if not conn:
            flash('Database connection failed. Please try again.', 'danger')
            return render_template('student_register.html')
            
        cur = conn.cursor()
        try:
            # Check for existing username
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                flash('Username already exists. Please choose a different username.', 'danger')
                return render_template('student_register.html')
            
            # Check for existing email
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash('Email already exists. Please use a different email address.', 'danger')
                return render_template('student_register.html')
            
            # Check for existing student ID
            cur.execute("SELECT id FROM users WHERE student_id = %s", (student_id,))
            if cur.fetchone():
                flash('Student ID already exists. Please check your student ID.', 'danger')
                return render_template('student_register.html')

            # Insert new student
            cur.execute(
                "INSERT INTO users (username, password, email, full_name, student_id, role) VALUES (%s, %s, %s, %s, %s, 'student')",
                (username, hashed_password, email, full_name, student_id)
            )
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('student_login'))
            
        except Exception as e:
            conn.rollback()
            print(f"Registration error: {str(e)}")
            flash('Registration failed. Please try again with different information.', 'danger')
        finally:
            cur.close()
            conn.close()
    
    return render_template('student_register.html')

# Admin Authentication
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if is_logged_in() and is_admin():
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        if not conn:
            flash('Database connection failed. Please try again.', 'danger')
            return render_template('admin_login.html')
            
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND role = 'admin'", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'danger')
    return render_template('admin_login.html')

# Student Dashboard and Features
@app.route('/student/dashboard')
def student_dashboard():
    if not is_logged_in() or not is_student():
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('student_login'))
        
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) as total FROM complaints WHERE student_id = %s", (session['user_id'],))
    total_complaints = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as total FROM complaints WHERE student_id = %s AND status = 'Pending'",
                (session['user_id'],))
    pending_complaints = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as total FROM complaints WHERE student_id = %s AND status = 'Solved'",
                (session['user_id'],))
    solved_complaints = cur.fetchone()['total']
    
    cur.execute("""
        SELECT c.id, c.created_at, cc.name as category, c.status 
        FROM complaints c 
        JOIN complaint_categories cc ON c.category_id = cc.id 
        WHERE c.student_id = %s 
        ORDER BY c.created_at DESC 
        LIMIT 5
    """, (session['user_id'],))
    recent_complaints = cur.fetchall()

    # Get unread messages count
    cur.execute("SELECT COUNT(*) as unread_count FROM messages WHERE receiver_id = %s AND is_read = FALSE",
                (session['user_id'],))
    unread_result = cur.fetchone()
    unread_messages = unread_result['unread_count'] if unread_result else 0

    cur.close()
    conn.close()

    return render_template('student_dashboard.html',
                           total_complaints=total_complaints,
                           pending_complaints=pending_complaints,
                           solved_complaints=solved_complaints,
                           recent_complaints=recent_complaints,
                           unread_messages=unread_messages)

@app.route('/student/report-complaint', methods=['GET', 'POST'])
def report_complaint():
    if not is_logged_in() or not is_student():
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    cur = conn.cursor()
    
    if request.method == 'POST':
        category_id = request.form['category']
        incident_date = request.form['incident_date']
        incident_time = request.form['incident_time']
        location = request.form['location']
        description = request.form['description']
        photo_path = None

        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_path = filename

        cur.execute(
            "INSERT INTO complaints (student_id, category_id, incident_date, incident_time, location, description, photo_path) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (session['user_id'], category_id, incident_date, incident_time, location, description, photo_path)
        )
        conn.commit()
        
        # Get the last inserted ID (PostgreSQL way)
        cur.execute("SELECT LASTVAL()")
        complaint_id = cur.fetchone()[0]

        # Send automatic email notification
        cur.execute("SELECT email, full_name FROM users WHERE id = %s", (session['user_id'],))
        student = cur.fetchone()
        cur.execute("SELECT name FROM complaint_categories WHERE id = %s", (category_id,))
        category = cur.fetchone()

        if student and category:
            email_subject = "Complaint Submitted Successfully - NEMSU CCMS"
            email_message = f"""
            Hello <b>{student['full_name']}</b>,<br><br>
            Your complaint regarding <b>{category['name']}</b> has been successfully submitted.<br><br>
            <strong>Complaint ID:</strong> {complaint_id}<br>
            <strong>Date Submitted:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}<br>
            <strong>Status:</strong> Pending Review<br><br>
            Our team will review your complaint and you will be notified of any updates.<br><br>
            Thank you for using NEMSU CCMS.<br><br>
            Best regards,<br>
            NEMSU Administration
            """
            send_email(student['email'], email_subject, email_message)

        cur.close()
        conn.close()
        flash(f'Complaint submitted successfully! Your Complaint ID is: {complaint_id}', 'success')
        return redirect(url_for('previous_reports'))

    cur.execute("SELECT * FROM complaint_categories")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('report_complaint.html', categories=categories)

@app.route('/student/previous-reports')
def previous_reports():
    if not is_logged_in() or not is_student():
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, cc.name as category, c.status, c.created_at 
        FROM complaints c 
        JOIN complaint_categories cc ON c.category_id = cc.id 
        WHERE c.student_id = %s 
        ORDER BY c.created_at DESC
    """, (session['user_id'],))
    complaints = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('previous_reports.html', complaints=complaints)

@app.route('/student/complaint-details/<int:complaint_id>')
def complaint_details(complaint_id):
    if not is_logged_in() or not is_student():
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('previous_reports'))
        
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, cc.name as category_name, u.full_name, u.student_id
        FROM complaints c 
        JOIN complaint_categories cc ON c.category_id = cc.id 
        JOIN users u ON c.student_id = u.id 
        WHERE c.id = %s AND c.student_id = %s
    """, (complaint_id, session['user_id']))
    complaint = cur.fetchone()

    if complaint:
        cur.execute("""
            SELECT ar.*, u.full_name as admin_name 
            FROM admin_responses ar 
            JOIN users u ON ar.admin_id = u.id 
            WHERE ar.complaint_id = %s 
            ORDER BY ar.created_at
        """, (complaint_id,))
        responses = cur.fetchall()
    else:
        responses = []
    cur.close()
    conn.close()

    if not complaint:
        flash('Complaint not found or access denied', 'danger')
        return redirect(url_for('previous_reports'))
    return render_template('complaint_details.html', complaint=complaint, responses=responses)

@app.route('/student/feedback', methods=['GET', 'POST'])
def feedback():
    if not is_logged_in() or not is_student():
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    cur = conn.cursor()
    cur.execute("SELECT id FROM complaints WHERE student_id = %s AND status = 'Solved'", (session['user_id'],))
    solved_complaints = cur.fetchall()

    if not solved_complaints:
        cur.close()
        conn.close()
        return render_template('feedback.html', feedback_allowed=False)

    if request.method == 'POST':
        complaint_id = request.form['complaint_id']
        rating = request.form['rating']
        comment = request.form['comment']
        cur.execute("SELECT id FROM feedback WHERE complaint_id = %s", (complaint_id,))
        existing_feedback = cur.fetchone()

        if existing_feedback:
            flash('Feedback already submitted for this complaint', 'danger')
        else:
            cur.execute(
                "INSERT INTO feedback (student_id, complaint_id, rating, comment) VALUES (%s, %s, %s, %s)",
                (session['user_id'], complaint_id, rating, comment)
            )
            conn.commit()
            flash('Feedback submitted successfully!', 'success')
        cur.close()
        conn.close()
        return redirect(url_for('feedback'))

    cur.execute("""
        SELECT c.id, cc.name as category, c.created_at 
        FROM complaints c 
        JOIN complaint_categories cc ON c.category_id = cc.id 
        WHERE c.student_id = %s AND c.status = 'Solved'
    """, (session['user_id'],))
    solved_complaints = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('feedback.html', feedback_allowed=True, solved_complaints=solved_complaints)

# FIXED MESSAGE FUNCTIONS
@app.route('/student/private-message', methods=['GET', 'POST'])
def private_message():
    if not is_logged_in() or not is_student():
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    cur = conn.cursor()
    
    if request.method == 'POST':
        message_text = request.form['message']

        # Find admin user
        cur.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        admin = cur.fetchone()

        if admin:
            cur.execute(
                "INSERT INTO messages (sender_id, receiver_id, message) VALUES (%s, %s, %s)",
                (session['user_id'], admin['id'], message_text)
            )
            conn.commit()
            flash('Message sent successfully to administrator!', 'success')
            print(f"DEBUG: Student {session['user_id']} sent message to admin {admin['id']}")
        else:
            flash('No administrator found. Please try again later.', 'danger')
        cur.close()
        conn.close()
        return redirect(url_for('private_message'))

    # Get message history (both sent and received)
    cur.execute("""
        SELECT m.*, 
               u_sender.full_name as sender_name,
               u_receiver.full_name as receiver_name
        FROM messages m 
        JOIN users u_sender ON m.sender_id = u_sender.id 
        JOIN users u_receiver ON m.receiver_id = u_receiver.id 
        WHERE m.sender_id = %s OR m.receiver_id = %s 
        ORDER BY m.created_at DESC
    """, (session['user_id'], session['user_id']))
    messages = cur.fetchall()

    print(f"DEBUG: Message history - {len(messages)} messages found")
    for msg in messages:
        print(f"DEBUG: Message {msg['id']} - From: {msg['sender_name']}, To: {msg['receiver_name']}")

    cur.close()
    conn.close()
    return render_template('private_message.html', messages=messages)

@app.route('/student/inbox')
def student_inbox():
    if not is_logged_in() or not is_student():
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    cur = conn.cursor()

    # Get messages where student is the receiver
    cur.execute("""
        SELECT m.*, u.full_name as sender_name, u.student_id 
        FROM messages m 
        JOIN users u ON m.sender_id = u.id 
        WHERE m.receiver_id = %s 
        ORDER BY m.created_at DESC
    """, (session['user_id'],))
    messages = cur.fetchall()

    print(f"DEBUG: Student inbox - Found {len(messages)} messages for student {session['user_id']}")
    for msg in messages:
        print(f"DEBUG: Inbox Message {msg['id']} - From: {msg['sender_name']}, Content: {msg['message'][:50]}...")

    # Mark messages as read
    cur.execute("UPDATE messages SET is_read = TRUE WHERE receiver_id = %s", (session['user_id'],))
    conn.commit()
    cur.close()
    conn.close()

    return render_template('student_inbox.html', messages=messages)

# Admin Dashboard and Features
@app.route('/admin/dashboard')
def admin_dashboard():
    if not is_logged_in() or not is_admin():
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('admin_login'))
        
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) as total FROM users WHERE role = 'student'")
    total_students = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as total FROM complaints")
    total_complaints = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as total FROM complaints WHERE status = 'Pending'")
    pending_complaints = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as total FROM complaints WHERE status = 'Solved'")
    solved_complaints = cur.fetchone()['total']
    
    cur.execute("""
        SELECT c.id, c.created_at, cc.name as category, u.full_name, u.student_id 
        FROM complaints c 
        JOIN complaint_categories cc ON c.category_id = cc.id 
        JOIN users u ON c.student_id = u.id 
        ORDER BY c.created_at DESC 
        LIMIT 5
    """)
    recent_complaints = cur.fetchall()

    # Get recent messages for admin
    cur.execute("""
        SELECT m.*, u.full_name as sender_name 
        FROM messages m 
        JOIN users u ON m.sender_id = u.id 
        WHERE m.receiver_id = %s 
        ORDER BY m.created_at DESC 
        LIMIT 5
    """, (session['user_id'],))
    recent_messages = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('admin_dashboard.html',
                           total_students=total_students,
                           total_complaints=total_complaints,
                           pending_complaints=pending_complaints,
                           solved_complaints=solved_complaints,
                           recent_complaints=recent_complaints,
                           recent_messages=recent_messages)

@app.route('/admin/manage-students')
def manage_students():
    if not is_logged_in() or not is_admin():
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('admin_dashboard'))
        
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE role = 'student'")
    students = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('manage_students.html', students=students)

@app.route('/admin/manage-complaints')
def manage_complaints():
    if not is_logged_in() or not is_admin():
        return redirect(url_for('admin_login'))

    category_filter = request.args.get('category', '')
    status_filter = request.args.get('status', '')
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('admin_dashboard'))
        
    cur = conn.cursor()

    query = """
        SELECT c.*, cc.name as category_name, u.full_name, u.student_id 
        FROM complaints c 
        JOIN complaint_categories cc ON c.category_id = cc.id 
        JOIN users u ON c.student_id = u.id 
        WHERE 1=1
    """
    params = []

    if category_filter:
        query += " AND cc.id = %s"
        params.append(category_filter)
    if status_filter:
        query += " AND c.status = %s"
        params.append(status_filter)

    query += " ORDER BY c.created_at DESC"
    cur.execute(query, params)
    complaints = cur.fetchall()
    
    cur.execute("SELECT * FROM complaint_categories")
    categories = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_template('manage_complaints.html', complaints=complaints, categories=categories)

@app.route('/admin/complaint-details/<int:complaint_id>', methods=['GET', 'POST'])
def admin_complaint_details(complaint_id):
    if not is_logged_in() or not is_admin():
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('manage_complaints'))
        
    cur = conn.cursor()
    
    if request.method == 'POST':
        status = request.form['status']

        # Get complaint and student details
        cur.execute("""
            SELECT c.*, u.full_name, u.email, cc.name as category_name
            FROM complaints c 
            JOIN users u ON c.student_id = u.id 
            JOIN complaint_categories cc ON c.category_id = cc.id 
            WHERE c.id = %s
        """, (complaint_id,))
        complaint_data = cur.fetchone()

        # Update complaint status
        cur.execute("UPDATE complaints SET status = %s, updated_at = NOW() WHERE id = %s", (status, complaint_id))

        # Save automatic admin response
        automatic_response = f"Complaint status updated to: {status}"
        cur.execute(
            "INSERT INTO admin_responses (complaint_id, admin_id, response) VALUES (%s, %s, %s)",
            (complaint_id, session['user_id'], automatic_response)
        )
        conn.commit()

        # Send automatic email notification
        if complaint_data and complaint_data['email']:
            template = RESPONSE_TEMPLATES.get(status, RESPONSE_TEMPLATES['Pending'])
            email_subject = template['subject']
            email_message = template['template'].format(
                student_name=complaint_data['full_name'],
                complaint_category=complaint_data['category_name']
            )

            email_sent = send_email(complaint_data['email'], email_subject, email_message)

            if email_sent:
                flash(f'Complaint status updated to {status} and notification sent!', 'success')
            else:
                flash(f'Complaint status updated to {status} but email failed (check console).', 'warning')
        else:
            flash(f'Complaint status updated to {status}!', 'success')

    # Get complaint details
    cur.execute("""
        SELECT c.*, cc.name as category_name, u.full_name, u.student_id, u.email
        FROM complaints c 
        JOIN complaint_categories cc ON c.category_id = cc.id 
        JOIN users u ON c.student_id = u.id 
        WHERE c.id = %s
    """, (complaint_id,))
    complaint = cur.fetchone()

    # Get response history
    cur.execute("""
        SELECT ar.*, u.full_name as admin_name 
        FROM admin_responses ar 
        JOIN users u ON ar.admin_id = u.id 
        WHERE ar.complaint_id = %s 
        ORDER BY ar.created_at
    """, (complaint_id,))
    responses = cur.fetchall()
    
    cur.close()
    conn.close()

    return render_template('admin_complaint_details.html',
                           complaint=complaint,
                           responses=responses,
                           response_templates=RESPONSE_TEMPLATES)

@app.route('/admin/reports')
def admin_reports():
    if not is_logged_in() or not is_admin():
        return redirect(url_for('admin_login'))

    period = request.args.get('period', 'monthly')
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('admin_dashboard'))
        
    cur = conn.cursor()

    cur.execute("""
        SELECT cc.name, COUNT(c.id) as count 
        FROM complaint_categories cc 
        LEFT JOIN complaints c ON cc.id = c.category_id 
        GROUP BY cc.id, cc.name 
        ORDER BY count DESC
    """)
    complaint_types = cur.fetchall()

    if period == 'weekly':
        cur.execute("""
            SELECT EXTRACT(YEAR FROM created_at) as year, EXTRACT(WEEK FROM created_at) as week, COUNT(*) as count 
            FROM complaints 
            GROUP BY EXTRACT(YEAR FROM created_at), EXTRACT(WEEK FROM created_at) 
            ORDER BY year DESC, week DESC 
            LIMIT 12
        """)
    elif period == 'monthly':
        cur.execute("""
            SELECT EXTRACT(YEAR FROM created_at) as year, EXTRACT(MONTH FROM created_at) as month, COUNT(*) as count 
            FROM complaints 
            GROUP BY EXTRACT(YEAR FROM created_at), EXTRACT(MONTH FROM created_at) 
            ORDER BY year DESC, month DESC 
            LIMIT 12
        """)
    else:
        cur.execute("""
            SELECT EXTRACT(YEAR FROM created_at) as year, EXTRACT(QUARTER FROM created_at) as quarter, COUNT(*) as count 
            FROM complaints 
            GROUP BY EXTRACT(YEAR FROM created_at), EXTRACT(QUARTER FROM created_at) 
            ORDER BY year DESC, quarter DESC 
            LIMIT 12
        """)

    complaint_stats = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin_reports.html',
                           complaint_types=complaint_types,
                           complaint_stats=complaint_stats,
                           period=period)

@app.route('/admin/export/complaints/<format_type>')
def export_complaints(format_type):
    if not is_logged_in() or not is_admin():
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('admin_reports'))
        
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.created_at, cc.name as category, u.full_name, u.student_id, u.email, c.status, c.location, c.description
        FROM complaints c 
        JOIN complaint_categories cc ON c.category_id = cc.id 
        JOIN users u ON c.student_id = u.id 
        ORDER BY c.created_at DESC
    """)
    complaints = cur.fetchall()
    cur.close()
    conn.close()

    if format_type == 'csv':
        try:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                ['Complaint ID', 'Date', 'Category', 'Student Name', 'Student ID', 'Student Email', 'Status',
                 'Location', 'Description'])

            for complaint in complaints:
                writer.writerow([
                    complaint['id'],
                    complaint['created_at'].strftime('%Y-%m-%d %H:%M'),
                    complaint['category'],
                    complaint['full_name'],
                    complaint['student_id'],
                    complaint['email'],
                    complaint['status'],
                    complaint['location'],
                    complaint['description'][:100] + '...' if complaint['description'] and len(
                        complaint['description']) > 100 else complaint['description']
                ])

            response = make_response(output.getvalue())
            response.headers['Content-Disposition'] = 'attachment; filename=nemsu_complaints_export.csv'
            response.headers['Content-type'] = 'text/csv'
            return response
        except Exception as e:
            flash(f'CSV export failed: {str(e)}', 'danger')
            return redirect(url_for('admin_reports'))

    elif format_type == 'excel':
        try:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                ['Complaint ID', 'Date', 'Category', 'Student Name', 'Student ID', 'Student Email', 'Status',
                 'Location', 'Description'])

            for complaint in complaints:
                writer.writerow([
                    complaint['id'],
                    complaint['created_at'].strftime('%Y-%m-%d %H:%M'),
                    complaint['category'],
                    complaint['full_name'],
                    complaint['student_id'],
                    complaint['email'],
                    complaint['status'],
                    complaint['location'],
                    complaint['description'][:100] + '...' if complaint['description'] and len(
                        complaint['description']) > 100 else complaint['description']
                ])

            response = make_response(output.getvalue())
            response.headers['Content-Disposition'] = 'attachment; filename=nemsu_complaints_export.xls'
            response.headers['Content-type'] = 'application/vnd.ms-excel'
            return response
        except Exception as e:
            flash(f'Excel export failed: {str(e)}', 'danger')
            return redirect(url_for('admin_reports'))

    elif format_type == 'pdf':
        if PDF_SUPPORT:
            try:
                return generate_pdf_export(complaints)
            except Exception as e:
                flash(f'PDF export failed: {str(e)}', 'danger')
                return redirect(url_for('admin_reports'))
        else:
            flash('PDF export requires reportlab package. Install with: pip install reportlab', 'warning')
            return redirect(url_for('admin_reports'))

    flash('Invalid export format', 'danger')
    return redirect(url_for('admin_reports'))

def generate_pdf_export(complaints):
    """Generate PDF export using reportlab"""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        title = Paragraph("NEMSU CCMS - Complaints Report", styles['Title'])
        elements.append(title)
        date_text = Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal'])
        elements.append(date_text)
        elements.append(Paragraph("<br/>", styles['Normal']))

        total = len(complaints)
        pending = len([c for c in complaints if c['status'] == 'Pending'])
        solved = len([c for c in complaints if c['status'] == 'Solved'])
        summary_text = f"Total Complaints: {total} | Pending: {pending} | Solved: {solved}"
        summary = Paragraph(summary_text, styles['Normal'])
        elements.append(summary)
        elements.append(Paragraph("<br/>", styles['Normal']))

        data = [['ID', 'Date', 'Student', 'Category', 'Status']]
        for complaint in complaints:
            data.append([
                str(complaint['id']),
                complaint['created_at'].strftime('%m/%d/%Y'),
                f"{complaint['full_name']} ({complaint['student_id']})",
                complaint['category'],
                complaint['status']
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7'))
        ]))
        elements.append(table)

        doc.build(elements)
        response = make_response(buffer.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=nemsu_complaints_export.pdf'
        response.headers['Content-type'] = 'application/pdf'
        return response
    except Exception as e:
        raise Exception(f"PDF generation error: {str(e)}")

# FIXED ADMIN MESSAGE FUNCTIONS
@app.route('/admin/messages')
def admin_messages():
    if not is_logged_in() or not is_admin():
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('admin_dashboard'))
        
    cur = conn.cursor()

    # Get messages where admin is the receiver (messages from students)
    cur.execute("""
        SELECT m.*, u.full_name as sender_name, u.student_id 
        FROM messages m 
        JOIN users u ON m.sender_id = u.id 
        WHERE m.receiver_id = %s 
        ORDER BY m.created_at DESC
    """, (session['user_id'],))
    messages = cur.fetchall()

    print(f"DEBUG: Admin messages - Found {len(messages)} messages for admin {session['user_id']}")
    for msg in messages:
        print(f"DEBUG: Admin Message {msg['id']} - From: {msg['sender_name']}, Content: {msg['message'][:50]}...")

    # Mark messages as read
    cur.execute("UPDATE messages SET is_read = TRUE WHERE receiver_id = %s", (session['user_id'],))
    conn.commit()
    cur.close()
    conn.close()

    return render_template('admin_messages.html', messages=messages)

@app.route('/admin/send-message', methods=['GET', 'POST'])
def admin_send_message():
    if not is_logged_in() or not is_admin():
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        student_id = request.form['student_id']
        message_text = request.form['message']

        conn = get_db_connection()
        if not conn:
            flash('Database connection failed. Please try again.', 'danger')
            return redirect(url_for('admin_messages'))
            
        cur = conn.cursor()

        # Admin sends message to student (admin is sender, student is receiver)
        cur.execute(
            "INSERT INTO messages (sender_id, receiver_id, message) VALUES (%s, %s, %s)",
            (session['user_id'], student_id, message_text)
        )
        conn.commit()

        print(f"DEBUG: Admin {session['user_id']} sent message to student {student_id}")
        flash('Message sent successfully to student!', 'success')
        cur.close()
        conn.close()
        return redirect(url_for('admin_messages'))

    student_id = request.args.get('student_id')
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed. Please try again.', 'danger')
        return redirect(url_for('admin_messages'))
        
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, student_id FROM users WHERE role = 'student'")
    students = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin_send_message.html', students=students, selected_student=student_id)

@app.route('/mark_message_read/<int:message_id>', methods=['POST'])
def mark_message_read(message_id):
    if not is_logged_in():
        return jsonify({'success': False})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False})
        
    cur = conn.cursor()
    cur.execute("UPDATE messages SET is_read = TRUE WHERE id = %s", (message_id,))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Clear template cache
    app.jinja_env.cache = {}

    # Create upload folder
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Get port from environment variable or default to 5001
    port = int(os.environ.get('PORT', 5001))
    
    # Run on the appropriate host for Render
    host = '0.0.0.0' if 'RENDER' in os.environ else '127.0.0.1'
    
    print("🚀 Starting NEMSU CCMS...")
    print("🌐 Main Website: http://localhost:5001")
    print("🔧 Admin Panel: http://localhost:5001/admin/dashboard")
    print("📝 Student Login: http://localhost:5001/student/login")
    print("⚡ Admin Login: http://localhost:5001/admin/login")
    print("📧 Email System: Development Mode")
    print("💬 Message System: FIXED - Admin/Student messaging now working!")

    if not PDF_SUPPORT:
        print("⚠️  PDF export disabled - install reportlab package for PDF support")

    app.run(debug=True, port=port, host=host)
