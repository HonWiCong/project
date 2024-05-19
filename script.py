import mysql.connector
import serial
import time
import json
from datetime import datetime
# import matplotlib.pyplot as plt
# import numpy as np
import os
import asyncio
import aiomysql
import pymysql.cursors
import threading

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
    petLight INT,
    irDistance INT
)
""")

cloudCursor.execute("SELECT COUNT(*) FROM Cat_Adjust_Table")
count = cloudCursor.fetchone()['COUNT(*)']
if count == 0:
    cloudCursor.execute(
        f"INSERT INTO Cat_Adjust_Table (fanTemp, dustWindow, petLight, irDistance) VALUES (28, 500, 1, 10)")
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
    cloudCursor.execute(
        f"INSERT INTO Cat_Control_Table (lightState, fanState, windowState) VALUES (0, 0, 0)")
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
    'control': None,
    'fanTemp': None,
    'dustWindow': None,
    'petLight': None,
    'irDistance': None,
    'light': None,
    'fan': None,
    'window': None
}
result_lock = threading.Lock()


def fetch_data():
    connection = pymysql.connect(host='database-1.cjjqkkvq5tm1.us-east-1.rds.amazonaws.com',
                                 user='smartpetcomfort',
                                 password='swinburneaaronsarawakidauniversityjacklin',
                                 db='petcomfort_db',
                                 cursorclass=pymysql.cursors.DictCursor)

    while True:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT Mode_Table.control, 
                    Cat_Adjust_Table.fanTemp, Cat_Adjust_Table.dustWindow, Cat_Adjust_Table.petLight, Cat_Adjust_Table.irDistance, 
                    Cat_Control_Table.* 
                FROM Mode_Table 
                LEFT JOIN Cat_Adjust_Table ON 1=1
                LEFT JOIN Cat_Control_Table ON 1=1 
                LIMIT 1
            """)
            with result_lock:
                cache.update(cursor.fetchone())
            print("Data from Mode_Table:", cache)
            time.sleep(2)


def process_data():
    previous_cat_room_pet_number = None

    while True:
        with result_lock:
            if cache['control'] is not None:
                control = cache['control']
                control_value = 1 if control == 'true' else 0

                data = {
                    'control': control_value,
                    'fanTemp': cache["fanTemp"],
                    'dustWindow': cache["dustWindow"],
                    'petLight': cache["petLight"],
                    'irDistance': cache["irDistance"],

                    'light': cache["lightState"],
                    'fan': cache["fanState"],
                    'window': cache["windowState"],
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
                        formatted_date = current_datetime.strftime(
                            '%d %B %Y, %A')
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
                        temperature_C = float(
                            lines[3].split("Temperature (C): ")[1])

                        print("Temperature (F): ", lines[4])
                        temperature_F = float(
                            lines[4].split("Temperature (F): ")[1])

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

                        if (current_cat_room_pet_number != previous_cat_room_pet_number):
                            previous_cat_room_pet_number = current_cat_room_pet_number

                            if (current_cat_room_pet_number == 0):
                                cloudCursor.execute(
                                    f"INSERT INTO Cat_Table (petCount, lightState, humidity, temperature_C, temperature_F, windowState, fanState, fanSpeed) VALUES (0, 0, 0, 0, 0, 0, 0, 0)")
                            elif (current_cat_room_pet_number > 0):
                                cloudCursor.execute(
                                    f"INSERT INTO Cat_Table (petCount, lightState, humidity, temperature_C, temperature_F, windowState, fanState, fanSpeed) VALUES ({current_cat_room_pet_number}, {light}, {humidity}, {temperature_C}, {temperature_F}, {window}, {fan}, {fan_speed})")
                                newInsertedID = cloudCursor.lastrowid
                                cloudCursor.execute(
                                    f"INSERT INTO Cat_Dust_Table (catTableId, dustLevel) VALUES ({newInsertedID}, {dust_level})")

                            cloudDB.commit()
                        elif current_cat_room_pet_number > 0 and current_cat_room_pet_number == previous_cat_room_pet_number:
                            cloudCursor.execute(
                                f"INSERT INTO Cat_Dust_Table (catTableId, dustLevel) VALUES ({newInsertedID}, {dust_level})")
                            cloudDB.commit()

                else:
                    print("Invalid control value:", control)
            else:
                print("No data in Mode_Table")

            cloudDB.commit()
            localDB.commit()


thread = threading.Thread(target=process_data)
thread.start()
second_thread = threading.Thread(target=fetch_data)
second_thread.start()
