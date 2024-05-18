import threading
import mysql.connector
import serial
import time
import json
from datetime import datetime
# import matplotlib.pyplot as plt
# import numpy as np
import os
from queue import Queue

# Initialize serial communication
ser = serial.Serial('/dev/ttyUSB0', 9600)

current_cat_room_pet_number = None
previous_cat_room_pet_number = None

# Connect to MySQL database
cloudDB = mysql.connector.connect(host="database-1.cjjqkkvq5tm1.us-east-1.rds.amazonaws.com",
                                  user="smartpetcomfort", password="swinburneaaronsarawakidauniversityjacklin", database="petcomfort_db")
cloudCursor = cloudDB.cursor(dictionary=True)

localDB = mysql.connector.connect(
    host="localhost", user="pi", password="123456", database="petcomfort_db")
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

cloudCursor.execute("SET time_zone = '+08:00';")
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

# Adjust threshold
cloudCursor.execute("""
CREATE TABLE IF NOT EXISTS Cat_Adjust_Table (
    catAdjustTableID INT AUTO_INCREMENT PRIMARY KEY,
    fanTemp FLOAT,
    dustWindow INT,
    petLight VARCHAR(20),
    irDistance INT
)
""")

cloudCursor.execute("SELECT COUNT(*) FROM Cat_Adjust_Table")
count = cloudCursor.fetchone()['COUNT(*)']
if count == 0:
    cloudCursor.execute(f"INSERT INTO Cat_Adjust_Table (fanTemp, dustWindow, petLight, irDistance) VALUES (30, 180, 'ON', 100)")
    cloudDB.commit()

# Manual value
cloudCursor.execute("""
CREATE TABLE IF NOT EXISTS Cat_Control_Table (
    catControlID INT AUTO_INCREMENT PRIMARY KEY,
    lightState BOOLEAN DEFAULT FALSE,
    fanState BOOLEAN DEFAULT FALSE,
    windowState BOOLEAN DEFAULT FALSE
)
""")

cloudCursor.execute("SELECT COUNT(*) FROM Cat_Control_Table")
count = cloudCursor.fetchone()['COUNT(*)']
if count == 0:
    cloudCursor.execute(f"INSERT INTO Cat_Control_Table (lightState, fanState, windowState) VALUES (0, 0, 0)")
    cloudDB.commit()

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

cloudCursor.execute("SELECT COUNT(*) FROM Mode_Table")
count = cloudCursor.fetchone()['COUNT(*)']
if count == 0:
    cloudCursor.execute(f"INSERT INTO Mode_Table (control) VALUES ('false')")
    cloudDB.commit()

time.sleep(2)

newInsertedID = None

cache = {
    "mode_data": None,
    "row": None,
    "control_row": None
}

def fetch_data():
    while True:
        with cloudDB.cursor() as cloudCursor:
            cloudCursor.execute("SELECT control FROM Mode_Table LIMIT 1")
            cache["mode_data"] = cloudCursor.fetchone()

            cloudCursor.execute("SELECT fanTemp, dustWindow, petLight, irDistance FROM Cat_Adjust_Table")
            cache["row"] = cloudCursor.fetchone()

            cloudCursor.execute("SELECT * FROM Cat_Control_Table")
            cache["control_row"] = cloudCursor.fetchone()

        time.sleep(3)

fetch_thread = threading.Thread(target=fetch_data)
fetch_thread.daemon = True
fetch_thread.start()

while True:

    if cache["mode_data"] is not None:
        control = cache['mode_data']['control']
        control_value = 1 if control == 'true' else 0

        data = {
            'control': control_value,
            'fanTemp': cache['row']["fanTemp"],
            'dustWindow': cache['row']["dustWindow"],
            'petLight': cache['row']["petLight"],
            'irDistance': cache['row']["irDistance"],

            'light': cache['control_row']["lightState"],
            'fan': cache['control_row']["fanState"],
            'window': cache['control_row']["windowState"],
        }
        # print("Data from Adjust_Table:", data)

        try:
            ser.write(json.dumps(data).encode("utf-8"))
            ser.write(b'\n')
        except:
            print("Error in write")

        response = ser.readline()

        try:
            response = response.decode("utf-8").strip()
            print(response)
        except UnicodeDecodeError:
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
                current_cat_room_pet_number = int(
                    lines[0].rsplit("Total pets inside: ")[1])

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
                # if current_cat_room_pet_number == 0:
                #     # Search if the latest record has petCount = 0
                #     cloudCursor.execute(f"SELECT * FROM Cat_Table ORDER BY catTableID DESC LIMIT 1")
                #     latest_record = cloudCursor.fetchone()
                #     print("Latest record:", latest_record)

                #     if latest_record == None or latest_record['petCount'] != 0:
                #         sql = "INSERT INTO Cat_Table (petCount, lightState, humidity, temperature_C, temperature_F, windowState, fanState, fanSpeed) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                #         val = (0, light, None, None, None,
                #                window, fan, fan_speed)
                #         cloudCursor.execute(sql, val)
                #         cloudDB.commit()

                # elif current_cat_room_pet_number > 0:
                #     sql = "INSERT INTO Cat_Table (petCount, lightState, humidity, temperature_C, temperature_F, windowState, fanState, fanSpeed) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                #     val = (current_cat_room_pet_number, light, humidity,
                #            temperature_C, temperature_F, window, fan, fan_speed)
                #     cloudCursor.execute(sql, val)
                #     cloudDB.commit()

                if (current_cat_room_pet_number != previous_cat_room_pet_number):
                    previous_cat_room_pet_number = current_cat_room_pet_number

                    if (current_cat_room_pet_number == 0):
                        cloudCursor.execute(f"INSERT INTO Cat_Table (petCount, lightState, humidity, temperature_C, temperature_F, windowState, fanState, fanSpeed) VALUES (0, 0, 0, 0, 0, 0, 0, 0)")
                    elif (current_cat_room_pet_number > 0):
                        cloudCursor.execute(f"INSERT INTO Cat_Table (petCount, lightState, humidity, temperature_C, temperature_F, windowState, fanState, fanSpeed) VALUES ({current_cat_room_pet_number}, {light}, {humidity}, {temperature_C}, {temperature_F}, {window}, {fan}, {fan_speed})")
                        newInsertedID = cloudCursor.lastrowid
                        cloudCursor.execute(f"INSERT INTO Cat_Dust_Table (catTableId, dustLevel) VALUES ({newInsertedID}, {dust_level})")
                    
                    cloudDB.commit()
                elif current_cat_room_pet_number > 0 and current_cat_room_pet_number == previous_cat_room_pet_number:
                    cloudCursor.execute(f"INSERT INTO Cat_Dust_Table (catTableId, dustLevel) VALUES ({newInsertedID}, {dust_level})")
                    cloudDB.commit()

        else:
            print("Invalid control value:", control)
    else:
        print("No data in Mode_Table")

    cloudDB.commit()
    localDB.commit()

# Close serial connection and database connection
ser.close()
cloudCursor.close()
cloudDB.close()
