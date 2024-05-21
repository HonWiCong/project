import mysql.connector
import serial
import time
import json
from datetime import datetime
# import matplotlib.pyplot as plt
# import numpy as np
import os
import asyncio
import pymysql.cursors
import threading
from SerialInterface import SerialInterface

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
iface = SerialInterface()

def fetch_data():
    print("Fetching data")
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
            raw_data = cursor.fetchone()
            cache["control"] = raw_data["control"]
            cache["fanTemp"] = raw_data["fanTemp"] 
            cache["dustWindow"] = raw_data["dustWindow"]
            cache["petLight"] = raw_data["petLight"]
            cache["irDistance"] = raw_data["irDistance"]

            cache["light"] = raw_data["lightState"]
            cache["fan"] = raw_data["fanState"]
            cache["window"] = raw_data["windowState"]
            
            data = {
                    'control': 1 if cache['control'] == 'true' else 0,
                    'fanTemp': cache["fanTemp"],
                    'dustWindow': cache["dustWindow"],
                    'petLight': cache["petLight"],
                    'irDistance': cache["irDistance"],

                    'light': cache["light"],
                    'fan': cache["fan"],
                    'window': cache["window"],
            }
            #print("Data:", data)
            
            iface.write_msg(data)
            connection.commit()
            time.sleep(1)

arduino_petCounter = None
arduino_light = None
arduino_humidity = None
arduino_temperature_C = None
arduino_temperature_F = None
arduino_dustValue = None
arduino_window = None
arduino_fan = None
arduino_fanSpeed = None

def assign_values(response):
    global arduino_petCounter, arduino_light, arduino_humidity, arduino_temperature_C, arduino_temperature_F, arduino_dustValue, arduino_window, arduino_fan, arduino_fanSpeed
    if ('arduino_petCounter' in response):
        arduino_petCounter = response['arduino_petCounter']

    if ('arduino_light' in response):
        arduino_light = response['arduino_light']

    if ('arduino_humidity' in response):
        arduino_humidity = response['arduino_humidity']

    if ('arduino_temperature_C' in response):
        arduino_temperature_C = response['arduino_temperature_C']

    if ('arduino_temperature_F' in response):
        arduino_temperature_F = response['arduino_temperature_F']

    if ('arduino_dustValue' in response):
        arduino_dustValue = response['arduino_dustValue']

    if ('arduino_window' in response):
        arduino_window = response['arduino_window']

    if ('arduino_fan' in response):
        arduino_fan = response['arduino_fan']

    if ('arduino_fanSpeed' in response):
        arduino_fanSpeed = response['arduino_fanSpeed']

def process_data():
    print("Processing data")
    previous_cat_room_pet_number = None

    while True:
        response = iface.read_msg()

        if (response is None):
            continue
        
        print(f"Response: {response}")
        assign_values(response)

        if arduino_petCounter != previous_cat_room_pet_number:
            previous_cat_room_pet_number = arduino_petCounter

            if arduino_petCounter == 0:
                cloudCursor.execute("INSERT INTO Cat_Table (petCount, lightState, humidity, temperature_C, temperature_F, windowState, fanState, fanSpeed) VALUES (0, 0, 0, 0, 0, 0, 0, 0)")
                cloudDB.commit()
            elif arduino_petCounter > 0:
                cloudCursor.execute(
                    "INSERT INTO Cat_Table (petCount, lightState, humidity, temperature_C, temperature_F, windowState, fanState, fanSpeed) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (arduino_petCounter, arduino_light, arduino_humidity, arduino_temperature_C, arduino_temperature_F, arduino_window, arduino_fan, arduino_fanSpeed))
                newInsertedID = cloudCursor.lastrowid
                cloudCursor.execute(
                    "INSERT INTO Cat_Dust_Table (catTableId, dustLevel) VALUES (%s, %s)",
                    (newInsertedID, arduino_dustValue))
                cloudDB.commit()

        elif arduino_petCounter > 0 and arduino_petCounter == previous_cat_room_pet_number:
            cloudCursor.execute(
                "INSERT INTO Cat_Dust_Table (catTableId, dustLevel) VALUES (%s, %s)",
                (newInsertedID, arduino_dustValue))
            cloudDB.commit()

thread = threading.Thread(target=process_data)
thread.start()
second_thread = threading.Thread(target=fetch_data)
second_thread.start()
