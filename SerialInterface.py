import time
import serial
import json


class SerialInterface:
    """Creates a Serial Interface with the specified parameters and allows to read from
    and write to it."""

    def __init__(self, port="/dev/ttyUSB0", baud=9600):
        self.no_response = False
        self.timeout_timer = time.time()
        self.ser = serial.Serial(port, baudrate=baud, timeout=2)
        time.sleep(2)

    def read_msg(self):
        time.sleep(0.06)
        """Reads a line from the serial buffer,
        decodes it and returns its contents as a dict."""
        # now = time.time()
        # if (now - self.timeout_timer) > 3:
        #     # Timeout
        #     print("Timeout!")
        #     return None

        if self.ser.in_waiting == 0:
            # Nothing received
            #print("Dont listen to me!")
            print("No messagge waiting")
            self.no_response = True
            return None

        incoming = self.ser.readline()
        try:
            incoming = incoming.decode("utf-8")
        except UnicodeDecodeError:
            print("Error decoding incoming message!")
            return None
        
        resp = None
        self.no_response = False
        self.timeout_timer = time.time()

        try:
            resp = json.loads(incoming)
        except json.JSONDecodeError:
            print("Error decoding JSON message!")
            return incoming

        return resp

        # print(f"Received from Arduino: {incoming.strip()}")

        # try:
        #     resp = json.loads(incoming)
        # except json.JSONDecodeError:
        #     print("Error decoding JSON message!")

        return incoming

    def write_msg(self, message=None):
        """Sends a JSON-formatted command to the serial
        interface."""
        time.sleep(0.06)
        #if self.no_response:
            ## If no response was received last time, we don't send another request
            #return

        try:
            json_msg = json.dumps(message)
            self.ser.write(json_msg.encode("utf-8"))
            self.ser.write(b'\n')
        except TypeError:
            print("Unable to serialize message.")

    def close(self):
        """Close the Serial connection."""
        self.ser.close()

