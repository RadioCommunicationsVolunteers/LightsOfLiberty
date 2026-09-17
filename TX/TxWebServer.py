from flask import Flask, render_template, request, jsonify
import serial
import time
import random

WORDS = [
    "snow", "reindeer", "holiday", "bright", "winter", "cookie", "magic",
    "joy", "storm", "radio", "signal", "mesh", "tree", "gift", "north",
    "lights", "scout", "skywarn", "weather", "calm", "wind", "cloud"
]

def random_phrase():
    return " ".join(random.sample(WORDS, random.randint(2, 3)))

# -----------------------------
# UART Setup
# -----------------------------
UART_PORT = "/dev/serial0"   # Raspberry Pi UART
BAUD_RATE = 115200

ser = serial.Serial(UART_PORT, BAUD_RATE, timeout=1)

# -----------------------------
# Flask Setup
# -----------------------------
app = Flask(__name__)

def build_message_frame(id_num, first_name, christmas_wish, achievement):
    """
    Create a compact, structured message frame.
    You can adjust this format to match your Meshtastic decoder.
    """
    return (
        f"ID:{id_num}\n"
        f"NAME:{first_name}\n"
        f"WISH:{christmas_wish}\n"
        f"ACHIEVE:{achievement}\n"
        "END\n"
    )

def send_to_heltec(message):
    """
    Send the message over UART to the Heltec V4.
    """
    ser.write(message.encode("utf-8"))
    ser.flush()
    time.sleep(0.1)

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()

    required_fields = ["id", "first_name", "christmas_wish", "achievement"]
    missing = [f for f in required_fields if f not in data]

    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    # Extract fields
    id_num = data["id"]
    first_name = data["first_name"]
    christmas_wish = data["christmas_wish"]
    achievement = data["achievement"]

    # Build message frame
    message = build_message_frame(id_num, first_name, christmas_wish, achievement)

    # Send over UART
    send_to_heltec(message)

    return jsonify({"status": "Message transmitted"}), 200

@app.route("/test")
def test_page():
    return render_template("test.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
