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
    ALTER TABLE registrations_new
    ADD COLUMN ticket_id VARCHAR(100),
    ADD COLUMN status VARCHAR(20) DEFAULT 'Registered',
    ADD COLUMN payment_status VARCHAR(20) DEFAULT 'Pending',
    ADD COLUMN transaction_id VARCHAR(100);
    """)
    print("Added ticket and payment columns to 'registrations_new' table successfully.")

    conn.commit()
    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print(f"Error: {err}")
