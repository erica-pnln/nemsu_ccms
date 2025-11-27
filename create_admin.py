from werkzeug.security import generate_password_hash
import psycopg2
from psycopg2.extras import DictCursor
import os

def create_cherlyn_admin():
    try:
        # Your custom credentials
        username = "cherlyn"
        password = "sardovia123"
        email = "cherlyn@nemsu.edu.ph"
        full_name = "Cherlyn Sardovia"

        print("🎯 Creating Admin User: Cherlyn")
        print("=" * 40)

        # Connect to PostgreSQL using direct parameters
        conn = psycopg2.connect(
            host='dpg-d4jun67diees73b5ld7g-a.oregon-postgres.render.com',
            database='nemsu_ccms_db',
            user='nemsu_ccms_db_user',
            password='EAl83jcPEvy8kDYKXMY05Qu8n4WxAamU',
            port=5432
        )
        cursor = conn.cursor(cursor_factory=DictCursor)

        # Rest of the code remains the same...
        # Check if admin already exists
        cursor.execute("SELECT id, username FROM users WHERE username = %s AND role = 'admin'", (username,))
        existing_admin = cursor.fetchone()

        if existing_admin:
            print(f"✅ Admin user '{username}' exists! Updating...")
            admin_id = existing_admin['id']

            # Update the existing admin
            hashed_password = generate_password_hash(password)

            cursor.execute(
                "UPDATE users SET password = %s, email = %s, full_name = %s WHERE id = %s",
                (hashed_password, email, full_name, admin_id)
            )

            print("✅ Admin user updated successfully!")
        else:
            # Create new admin user
            hashed_password = generate_password_hash(password)

            cursor.execute(
                "INSERT INTO users (username, password, email, full_name, role) VALUES (%s, %s, %s, %s, %s)",
                (username, hashed_password, email, full_name, 'admin')
            )

            print("✅ Admin user created successfully!")

        conn.commit()

        print("\n📋 Admin Credentials:")
        print(f"   👤 Username: {username}")
        print(f"   🔑 Password: {password}")
        print(f"   📧 Email: {email}")
        print(f"   👩‍💼 Full Name: {full_name}")
        print(f"   🎯 Role: admin")
        
        base_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5001')
        print(f"   🌐 Login URL: {base_url}/admin/login")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

if __name__ == '__main__':
    create_cherlyn_admin()
