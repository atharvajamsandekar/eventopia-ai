import mysql.connector

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "Atharv",
    "database": "eventhopia"
}

def migrate_4():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Add price column to events table
        try:
            print("Adding 'price' column to 'events' table...")
            cursor.execute("ALTER TABLE events ADD COLUMN price INT DEFAULT 0;")
            print("Successfully added 'price' column.")
        except mysql.connector.Error as err:
            if "Duplicate column name" in str(err):
                print("Column 'price' already exists. Skipping.")
            else:
                print(f"Error: {err}")

        # Update department='General' to 'IT' mapping
        print("Updating events with 'General' department to 'IT'...")
        cursor.execute("UPDATE events SET department='IT' WHERE department='General'")
        print(f"Updated {cursor.rowcount} rows.")

        conn.commit()
        cursor.close()
        conn.close()
        print("Migration 4 completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate_4()
