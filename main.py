import mysql.connector

# Connect to MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    database="airline"
)

cursor = conn.cursor()

# Drop bookings table if it exists (safety)
cursor.execute("DROP TABLE IF EXISTS bookings")

# Create Passengers table
cursor.execute("""
CREATE TABLE IF NOT EXISTS passengers (
    passenger_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50),
    age INT,
    gender VARCHAR(10)
)
""")

# Create Bookings table with correct foreign keys
cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    booking_id INT AUTO_INCREMENT PRIMARY KEY,
    passenger_id INT,
    flight_id INT,
    seat_no VARCHAR(10),
    FOREIGN KEY (passenger_id) REFERENCES passengers(passenger_id),
    FOREIGN KEY (flight_id) REFERENCES flights(id)
)
""")

conn.commit()
print("Passengers and Bookings tables are ready!")

# Optional: fetch all flights to check
cursor.execute("SELECT * FROM flights")
for row in cursor.fetchall():
    print(row)

conn.close()