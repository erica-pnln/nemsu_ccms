import psycopg2
from psycopg2.extras import DictCursor
import os
from werkzeug.security import generate_password_hash

def init_database():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    conn = psycopg2.connect(database_url, cursor_factory=DictCursor)
    cur = conn.cursor()
    
    # Create tables
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            full_name VARCHAR(200) NOT NULL,
            student_id VARCHAR(50),
            role VARCHAR(20) DEFAULT 'student',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaint_categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id SERIAL PRIMARY KEY,
            student_id INTEGER REFERENCES users(id),
            category_id INTEGER REFERENCES complaint_categories(id),
            incident_date DATE,
            incident_time TIME,
            location TEXT,
            description TEXT,
            photo_path VARCHAR(255),
            status VARCHAR(20) DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS admin_responses (
            id SERIAL PRIMARY KEY,
            complaint_id INTEGER REFERENCES complaints(id),
            admin_id INTEGER REFERENCES users(id),
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER REFERENCES users(id),
            receiver_id INTEGER REFERENCES users(id),
            message TEXT,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            student_id INTEGER REFERENCES users(id),
            complaint_id INTEGER REFERENCES complaints(id),
            rating INTEGER,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default categories
    categories = [
        ('Academic Concerns', 'Issues related to academics, courses, faculty'),
        ('Facilities and Infrastructure', 'Building, classroom, and facility issues'),
        ('Administrative Issues', 'Administrative and office concerns'),
        ('Technical Support', 'IT and technical support issues'),
        ('Financial Concerns', 'Tuition, fees, and financial matters'),
        ('Other', 'Other types of complaints')
    ]
    
    for name, description in categories:
        cur.execute(
            "INSERT INTO complaint_categories (name, description) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (name, description)
        )
    
    # Create default admin user
    hashed_password = generate_password_hash('admin123')
    cur.execute(
        "INSERT INTO users (username, password, email, full_name, role) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        ('admin', hashed_password, 'admin@nemsu.edu.ph', 'System Administrator', 'admin')
    )
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized successfully!")

if __name__ == '__main__':
    init_database()
