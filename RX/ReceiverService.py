import serial
import json
import time
from pymongo import MongoClient

UART_PORT = "/dev/serial0"
BAUD_RATE = 115200

ser = serial.Serial(UART_PORT, BAUD_RATE, timeout=1)

client = MongoClient("mongodb://localhost:27017/")
db = client["meshtastic_messages"]
collection = db["responses"]

buffer = ""

def parse_message(msg):
    data = {}
    for line in msg.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.lower()] = value.strip()
    return data

print("Listening for incoming messages from Heltec V4...")

while True:
    if ser.in_waiting:
        char = ser.read().decode("utf-8", errors="ignore")
        buffer += char

        if buffer.endswith("END\n"):
            print("Received message:")
            print(buffer)

            parsed = parse_message(buffer)
            collection.insert_one(parsed)

            print("Saved to MongoDB:", parsed)

            buffer = ""

    time.sleep(0.01)
