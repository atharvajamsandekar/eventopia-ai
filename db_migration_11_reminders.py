import mysql.connector

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Atharv",
        database="eventhopia"
    )
    cursor = conn.cursor()

    cursor.execute("""
    ALTER TABLE events
    ADD COLUMN reminder_1h_sent BOOLEAN DEFAULT FALSE;
    """)
    print("Added 'reminder_1h_sent' column to 'events' table successfully.")

    conn.commit()
    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print(f"Error: {err}")
