import mysql.connector

# Database connection logic
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "Atharv",
    "database": "eventhopia"
}

try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    # We will update older "New Event Registration" messages to have the correct username.
    # The message looks like "pratik just registered for..."
    # The query below extracts the name and sets it.
    
    update_query = """
        UPDATE notifications 
        SET username = SUBSTRING_INDEX(message, ' just registered for', 1) 
        WHERE title LIKE '%New Event Registration%' AND username IS NULL
    """
    cursor.execute(update_query)
    conn.commit()

    print(cursor.rowcount, "old registration notifications were fixed.")
    
except mysql.connector.Error as err:
    print(f"Database error: {err}")
finally:
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'conn' in locals() and conn:
        conn.close()
