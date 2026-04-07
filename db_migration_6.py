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
        
        # Create event_feedback table
        print("Creating event_feedback table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_id INT,
                username VARCHAR(255),
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)
        print("Table 'event_feedback' created successfully.")
        
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
