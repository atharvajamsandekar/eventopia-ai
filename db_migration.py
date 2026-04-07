import mysql.connector

# Database connection configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "Atharv",  # This matches the user's setup in app.py
    "database": "eventhopia"
}

def migrate():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Add department column to events table
        try:
            print("Adding 'department' column to 'events' table...")
            cursor.execute("ALTER TABLE events ADD COLUMN department VARCHAR(100) DEFAULT 'General';")
            print("Successfully added 'department' column.")
        except mysql.connector.Error as err:
            if "Duplicate column name" in str(err):
                print("Column 'department' already exists. Skipping.")
            else:
                print(f"Error: {err}")

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
