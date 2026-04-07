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

        print("Adding 'team_name' column to 'registrations_new' table...")
        try:
            cursor.execute("ALTER TABLE registrations_new ADD COLUMN team_name VARCHAR(255) NULL;")
            print("Successfully added 'team_name' column.")
        except mysql.connector.Error as err:
            if "Duplicate column name" in str(err):
                print("Column 'team_name' already exists. Skipping.")
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
