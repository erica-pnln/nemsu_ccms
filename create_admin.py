from werkzeug.security import generate_password_hash
import pymysql


def create_cherlyn_admin():
    try:
        # Your custom credentials
        username = "cherlyn"
        password = "sardovia123"
        email = "cherlyn@nemsu.edu.ph"
        full_name = "Cherlyn Sardovia"

        print("🎯 Creating Admin User: Cherlyn")
        print("=" * 40)

        # Connect to MySQL
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password='erica2123',
            database='nemsu_ccms',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

        with conn.cursor() as cursor:
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
            print(f"   🌐 Login URL: http://localhost:5001/admin/login")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == '__main__':
    create_cherlyn_admin()