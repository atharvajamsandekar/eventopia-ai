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
        
        # Create tech_fests table
        print("Creating tech_fests table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tech_fests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                department VARCHAR(100) NOT NULL,
                description TEXT,
                fest_date DATE,
                venue VARCHAR(255),
                image VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Table 'tech_fests' created successfully.")

        # Update events table
        try:
            print("Adding 'tech_fest_id' column to 'events' table...")
            cursor.execute("ALTER TABLE events ADD COLUMN tech_fest_id INT NULL;")
            cursor.execute("""
                ALTER TABLE events 
                ADD CONSTRAINT fk_tech_fest 
                FOREIGN KEY (tech_fest_id) REFERENCES tech_fests(id) ON DELETE SET NULL;
            """)
            print("Successfully added 'tech_fest_id' column and foreign key.")
        except mysql.connector.Error as err:
            if "Duplicate column name" in str(err) or "Duplicate key name" in str(err):
                print("Column 'tech_fest_id' or foreign key already exists. Skipping.")
            else:
                print(f"Error altering events table: {err}")
        
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
