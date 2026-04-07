import mysql.connector

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "Atharv",
    "database": "eventhopia"
}

def migrate_3():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        print("Creating competitions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                type VARCHAR(255) NOT NULL,
                description TEXT,
                competition_date DATE,
                venue VARCHAR(255),
                image VARCHAR(255)
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Migration 3 completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate_3()
