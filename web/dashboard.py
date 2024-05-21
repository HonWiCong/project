import mysql.connector
import serial
import threading
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, session, current_app, Response
import os
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from picamera2 import Picamera2
import cv2
import re

app = Flask(__name__)
matplotlib.use('Agg')

app.secret_key = 'your secret key'

# Connect to MySQL database
mydb = mysql.connector.connect(host="database-1.cjjqkkvq5tm1.us-east-1.rds.amazonaws.com",
                               user="smartpetcomfort", password="swinburneaaronsarawakidauniversityjacklin", database="petcomfort_db")

with mydb.cursor() as mycursor:
    mycursor.execute("""
    CREATE TABLE IF NOT EXISTS Account_Table (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50),
        password VARCHAR(50),
        email VARCHAR(50),
        firebase_id INT UNIQUE
    )
    """)


def update_mode_table(control):
    with mydb.cursor() as cursor:
        sql = "INSERT INTO Mode_Table (control) VALUES (%s) ON DUPLICATE KEY UPDATE control = VALUES(control)"
        cursor.execute(sql, (control,))
        mydb.commit()


@app.route('/catAdjust', methods=['POST'])
def catAdjust():
    cat_adjust_data = None
    cat_control_data = None
    if request.method == 'POST':
        #  form data
        fanTemp = request.form['fanTemp']
        dustWindow = request.form['dustWindow']
        petLight = request.form['petLight']
        irDistance = request.form['irDistance']

        # Connect to MySQL and execute INSERT or UPDATE query
        with mydb.cursor() as cursor:
            # Check if a record already exists in the table
            cursor.execute("SELECT * FROM Cat_Adjust_Table")
            existing_record = cursor.fetchone()

            if existing_record:
                # Update existing record
                sql = "UPDATE Cat_Adjust_Table SET fanTemp=%s, dustWindow=%s, petLight=%s, irDistance=%s"
                val = (fanTemp, dustWindow, petLight, irDistance)
            else:
                # Insert new record
                sql = "INSERT INTO Cat_Adjust_Table (fanTemp, dustWindow, petLight, irDistance) VALUES (%s, %s, %s, %s)"
                val = (fanTemp, dustWindow, petLight, irDistance)

            cursor.execute(sql, val)
            mydb.commit()

            cursor = mydb.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM Cat_Adjust_Table WHERE catAdjustTableID = 1 LIMIT 1;")
            cat_adjust_data = cursor.fetchone()

            cursor.execute(
                "SELECT * FROM Cat_Control_Table WHERE catControlID = 1 LIMIT 1;")
            cat_control_data = cursor.fetchone()

        # Redirect to a success page or render a success message
        return render_template('index.html', cat_adjust_data=cat_adjust_data, cat_control_data=cat_control_data)


# Route to handle toggle button change
@app.route('/toggle-mode', methods=['POST'])
def toggle_mode():
    mode = request.form['mode']
    control_value = 'false' if mode == 'controllable' else 'true'
    with mydb.cursor() as cursor:
        cursor.execute("SELECT * FROM Mode_Table LIMIT 1")
        existing_record = cursor.fetchone()
        if existing_record:
            cursor.execute("UPDATE Mode_Table SET control = %s",
                           (control_value,))
        else:
            cursor.execute(
                "INSERT INTO Mode_Table (control) VALUES (%s)", (control_value,))
        mydb.commit()
    return "Mode updated successfully"


@app.route('/catControl', methods=['POST'])
def catControl():
    lightState = request.form.get('lightState') == 'true'
    fanState = request.form.get('fanState') == 'true'
    windowState = request.form.get('windowState') == 'true'

    with mydb.cursor() as cursor:
        # Check if a record already exists in the table
        cursor.execute("SELECT * FROM Cat_Control_Table LIMIT 1")
        existing_record = cursor.fetchone()

        if existing_record:
            # Construct the SQL query to update only the changed fields
            cursor.execute(
                f"UPDATE Cat_Control_Table SET lightState = {lightState} WHERE catControlID = 1")
            cursor.execute(
                f"UPDATE Cat_Control_Table SET fanState = {fanState} WHERE catControlID = 1")
            cursor.execute(
                f"UPDATE Cat_Control_Table SET windowState = {windowState} WHERE catControlID = 1")
        else:
            # Insert new record if no existing record found
            sql = "INSERT INTO Cat_Control_Table (lightState, fanState, windowState) VALUES (%s, %s, %s)"
            cursor.execute(sql, (lightState, fanState, windowState))

        mydb.commit()

    return "Data stored successfully"


# Define route for index page
@app.route('/')
def index():
    cursor = mydb.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM Cat_Adjust_Table WHERE catAdjustTableID = 1 LIMIT 1")
    cat_adjust_data = cursor.fetchone()

    cursor.execute(
        "SELECT * FROM Cat_Control_Table WHERE catControlID = 1 LIMIT 1;")
    cat_control_data = cursor.fetchone()

    cursor.execute("SELECT * FROM Mode_Table LIMIT 1")
    existing_mode = cursor.fetchone()
    if not existing_mode:
        cursor.execute("INSERT INTO Mode_Table (control) VALUES ('false')")
        mydb.commit()

    cursor.close()

    # Call function to continuously insert sensor data
    return render_template('index.html', cat_adjust_data=cat_adjust_data, cat_control_data=cat_control_data)

# Define route to render catRoom page


@app.route('/cat-room')
def catRoom():
    cursor = mydb.cursor(dictionary=True)
    cursor.execute("""
        SELECT Cat_Table.*, Cat_Dust_Table.dustLevel 
        FROM Cat_Table 
        LEFT JOIN Cat_Dust_Table ON Cat_Table.catTableID = Cat_Dust_Table.catTableId 
        WHERE Cat_Table.petCount > 0
        ORDER BY Cat_Table.catTableID DESC
    """)
    rows = cursor.fetchall()
    cats = {}

    for row in rows:
        if row['catTableID'] not in cats:
            cats[row['catTableID']] = row
            cats[row['catTableID']]['dust_levels'] = []

        if row['dustLevel'] is not None:
            cats[row['catTableID']]['dust_levels'].append(row['dustLevel'])

    cursor.close()

    cats_list = list(cats.values())
    # print(cats_list)

    try:
        for cat in cats_list:
            dust_levels_list = cat['dust_levels']
            # print(dust_levels_list)
            if dust_levels_list.__len__() > 0:
                plt.plot(np.arange(1, len(dust_levels_list) + 1),
                         dust_levels_list)
                plt.xlabel('Reading')
                plt.ylabel('Dust Levels')
                plt.title('Dust Level Readings')
                plt.grid(True)

                # Highlight min, max, and average values
                min_value = min(dust_levels_list)
                max_value = max(dust_levels_list)
                avg_value = sum(dust_levels_list) / len(dust_levels_list)

                plt.scatter(dust_levels_list.index(min_value) +
                            1, min_value, color='r', label='Min')
                plt.scatter(dust_levels_list.index(max_value) +
                            1, max_value, color='g', label='Max')

                plt.text(dust_levels_list.index(min_value) + 1, min_value,
                         f'Min: {min_value}', verticalalignment='bottom', horizontalalignment='right', color='r')
                plt.text(dust_levels_list.index(max_value) + 1, max_value,
                         f'Max: {max_value}', verticalalignment='bottom', horizontalalignment='right', color='g')

                plt.axhline(y=avg_value, color='orange', linestyle='--',
                            label=f'Average: {avg_value}')
                plt.text(len(dust_levels_list), avg_value, f'Avg: {avg_value}', color='orange',
                         verticalalignment='bottom', horizontalalignment='right')

                chart_filename = f"static/catRoom/chart/chart_{cat['catTableID']}.png"
                plt.savefig(chart_filename)
                plt.close()
    except Exception as e:
        print("Error:", e)

    return render_template('cat-room.html', data=cats_list)


# For cat_room livw streaming
camera = Picamera2()
camera.configure(camera.create_preview_configuration(
    main={"format": 'XRGB8888', "size": (640, 480)}))
camera.start()


def generate_frames():
    while True:
        frame = camera.capture_array()
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
