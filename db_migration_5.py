import mysql.connector

# Database connection logic
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "Atharv",
}

def migrate_database():
    try:
        # Connect to MySQL server
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Select database
        cursor.execute("USE eventhopia")
        
        # Add username column if it doesn't exist
        print("Adding username column to notifications table...")
        try:
            cursor.execute("ALTER TABLE notifications ADD COLUMN username VARCHAR(255) DEFAULT NULL")
            print("Column 'username' added successfully.")
        except mysql.connector.Error as err:
            if err.errno == 1060: # Duplicate column name
                print("Column 'username' already exists.")
            else:
                print(f"Error adding column: {err}")
        
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    migrate_database()
