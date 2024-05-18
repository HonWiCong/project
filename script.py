import mysql.connector
import serial
import time
import json
from datetime import datetime
# import matplotlib.pyplot as plt
# import numpy as np
import os

# Initialize serial communication
ser = serial.Serial('/dev/ttyUSB0', 9600)

current_cat_room_pet_number = None
previous_cat_room_pet_number = None

# Connect to MySQL database
cloudDB = mysql.connector.connect(host="database-1.cjjqkkvq5tm1.us-east-1.rds.amazonaws.com", user="smartpetcomfort", password="swinburneaaronsarawakidauniversityjacklin", database="petcomfort_db")
cloudCursor = cloudDB.cursor(dictionary=True)

localDB = mysql.connector.connect(host="localhost", user="pi", password="123456", database="petcomfort_db")
localCursor = localDB.cursor(dictionary=True)

localCursor.execute("""
CREATE TABLE IF NOT EXISTS Cat_Raw_Data (
    rawID INT AUTO_INCREMENT PRIMARY KEY,
    petCount INT,
    humidity FLOAT,
    lightState BOOLEAN DEFAULT FALSE,
    temperature_C FLOAT,
    temperature_F FLOAT,
    fanState BOOLEAN DEFAULT FALSE,
    fanSpeed INT,
    windowState BOOLEAN DEFAULT FALSE,
    dustLevel FLOAT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cloudCursor.execute("""
CREATE TABLE IF NOT EXISTS Cat_Table (
    catTableID INT AUTO_INCREMENT PRIMARY KEY,
    time DATETIME DEFAULT CURRENT_TIMESTAMP,
    petCount INT, 
    lightState BOOLEAN DEFAULT FALSE,
    humidity FLOAT,
    temperature_C FLOAT,
    temperature_F FLOAT,
    windowState BOOLEAN DEFAULT FALSE,
    fanState BOOLEAN DEFAULT FALSE,
    fanSpeed INT
)
""")

# Adjust treshold
cloudCursor.execute("""
CREATE TABLE IF NOT EXISTS Cat_Adjust_Table (
    catAdjustTableID INT AUTO_INCREMENT PRIMARY KEY,
    fanTemp FLOAT,
    dustWindow INT,
    petLight VARCHAR(20),
    irDistance INT
)
""")

# Manual value
cloudCursor.execute("""
CREATE TABLE IF NOT EXISTS Cat_Control_Table (
    catControlID INT AUTO_INCREMENT PRIMARY KEY,
    lightState BOOLEAN DEFAULT FALSE,
    fanState BOOLEAN DEFAULT FALSE,
    windowState BOOLEAN DEFAULT FALSE
)
""")


cloudCursor.execute("""
CREATE TABLE IF NOT EXISTS Cat_Dust_Table (
    catDustID INT AUTO_INCREMENT PRIMARY KEY,
    catTableId INT,
    dustLevel FLOAT,
    time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (catTableId) REFERENCES Cat_Table(catTableID)
)
""")

cloudCursor.execute("""
CREATE TABLE IF NOT EXISTS Mode_Table (
    modeTableID INT AUTO_INCREMENT PRIMARY KEY,
    control VARCHAR(20)
)
""")

# insert a dummy data to the cat dust table
# with mydb.cursor() as mycursor:
# 	mycursor.execute("""
# 	INSERT INTO Cat_Dust_Table (catTableId, dustLevel) VALUES (1, 0.5)
# 	""")
# 	mydb.commit()

time.sleep(2)

while True:
    # Fetch control value from Mode_Table
    cloudCursor.execute("SELECT control FROM Mode_Table LIMIT 1")
    mode_data = cloudCursor.fetchone()

    cloudCursor.execute("SELECT fanTemp, dustWindow, petLight, irDistance FROM Cat_Adjust_Table")
    row = cloudCursor.fetchone()

    cloudCursor.execute("SELECT * FROM Cat_Control_Table")
    control_row = cloudCursor.fetchone()

    if mode_data is not None:
        control = mode_data['control']
        control_value = 1 if control == 'true' else 0

        data = {
            'control': control_value,
            'fanTemp': row["fanTemp"],
            'dustWindow': row["dustWindow"],
            'petLight': row["petLight"],
            'irDistance': row["irDistance"],

            'light': control_row["lightState"],
            'fan': control_row["fanState"],
            'window': control_row["windowState"],
        }
        # print("Data from Adjust_Table:", data)

        try:
            ser.write(json.dumps(data).encode("utf-8"))
            ser.write(b'\n')
        except:
            print("Error in write")

        response = ser.readline()

        try:
            # Attempt to decode the response using utf-8
            response = response.decode("utf-8").strip()
            print(response)
        except UnicodeDecodeError:
            # Handle the case where decoding fails
            print("Received undecodable bytes:", response)

        if control == 'false':
            # Send data to Arduino
            if response.startswith("Room: "):
                room = response.split("Room: ")[1].rstrip()

                # Get current date and time
                current_datetime = datetime.now()

                # Format date and time
                formatted_date = current_datetime.strftime('%d %B %Y, %A')
                formatted_time = current_datetime.strftime('%I:%M %p')

                # Read sensor data lines from serial
                lines = None
                if ser.in_waiting > 0:
                    lines = [ser.readline().decode('utf-8').strip()
                             for _ in range(10)]

                print("Total pets inside: ", lines[0])
                current_cat_room_pet_number = int(lines[0].rsplit("Total pets inside: ")[1])

                print("Light: ", lines[1])
                light = lines[1].split("Light: ")[1]
                if light == "ON":
                    light = 1
                else:
                    light = 0

                print("Humidity: ", lines[2])
                humidity = float(lines[2].split("Humidity: ")[1])

                print("Temperature (C): ", lines[3])
                temperature_C = float(lines[3].split("Temperature (C): ")[1])

                print("Temperature (F): ", lines[4])
                temperature_F = float(lines[4].split("Temperature (F): ")[1])

                print("Dust Level: ", lines[5])
                dust_level = int(lines[5].split("Dust Level: ")[1])

                print("Window: ", lines[6])
                window = lines[6].split("Window: ")[1]
                if window == "OPEN":
                    window = 1
                else:
                    window = 0

                print("Fan: ", lines[7])
                fan = lines[7].split("Fan: ")[1]
                if fan == "ON":
                    fan = 1
                else:
                    fan = 0

                print("Fan Speed: ", lines[8])
                fan_speed = int(lines[8].split("Fan Speed: ")[1])

                # Insert data into Cat_Table
                if current_cat_room_pet_number == 0:
                    with cloudDB.cursor(dictionary=True) as mycursor:
                        # Search if the latest record has petCount = 0
                        mycursor.execute(f"SELECT * FROM Cat_Table ORDER BY catTableID DESC LIMIT 1")
                        latest_record = mycursor.fetchone()
                        print("Latest record:", latest_record)
                        if latest_record == None or latest_record['petCount'] != 0:
                            sql = "INSERT INTO Cat_Table (petCount, lightState, humidity, temperature_C, temperature_F, dustLevel, windowState, fanState, fanSpeed) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                            val = (0, light, None, None, None, dust_level, window, fan, fan_speed)
                            mycursor.execute(sql, val)
                            cloudDB.commit()

                elif current_cat_room_pet_number > 0:
                    with cloudDB.cursor() as mycursor:
                        sql = "INSERT INTO Cat_Table (petCount, lightState, humidity, temperature_C, temperature_F, dustLevel, windowState, fanState, fanSpeed) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                        val = (current_cat_room_pet_number, light, humidity, temperature_C, temperature_F, dust_level, window, fan, fan_speed)
                        mycursor.execute(sql, val)
                        cloudDB.commit()

                # Get the ID of the last inserted row
                last_insert_id = mycursor.lastrowid
        # elif control == 'true':
        #     if response.startswith("Room"):
        #         room = response.split("Room: ")[1].rstrip()
        #         print("RoomName:", room)
        #         cursor.execute("SELECT * FROM Cat_Control_Table LIMIT 1")
        #         existing_record = cursor.fetchone()

        #         if existing_record:
        #             cursor.execute(f"UPDATE Cat_Control_Table SET room = '{room}'")
            print(response)
        else:
            print("Invalid control value:", control)
    else:
        print("No data in Mode_Table")

    cloudDB.commit()

# Close serial connection and database connection
ser.close()
cloudCursor.close()
cloudDB.close()
