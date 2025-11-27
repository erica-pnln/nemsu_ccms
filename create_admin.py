from werkzeug.security import generate_password_hash
import psycopg
from psycopg.rows import dict_row
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

        # Connect to PostgreSQL (Render database)
        database_url = os.environ.get('DATABASE_URL', 'postgresql://nemsu_ccms_db_user:EAl83jcPEvy8kDYKXMY05Qu8n4WxAamU@dpg-d4jun67diees73b5ld7g-a.oregon-postgres.render.com:5432/nemsu_ccms_db')
        
        # Fix for Render PostgreSQL URL format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        conn = psycopg.connect(database_url, row_factory=dict_row)
        cursor = conn.cursor()

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
        
        # Get the base URL for deployment
        base_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5001')
        print(f"   🌐 Login URL: {base_url}/admin/login")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Close connection
        if 'conn' in locals():
            cursor.close()
            conn.close()

if __name__ == '__main__':
    create_cherlyn_admin()
