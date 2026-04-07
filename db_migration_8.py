import mysql.connector

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "Atharv",
}

def migrate_database():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("USE eventhopia")

        print("Adding 'show_on_home' column to 'tech_fests' table...")
        try:
            cursor.execute("ALTER TABLE tech_fests ADD COLUMN show_on_home BOOLEAN DEFAULT FALSE;")
            print("Successfully added 'show_on_home' column.")
        except mysql.connector.Error as err:
            if "Duplicate column name" in str(err):
                print("Column 'show_on_home' already exists. Skipping.")
            else:
                print(f"Error altering table: {err}")

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
