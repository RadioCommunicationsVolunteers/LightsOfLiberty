from flask import Flask, json, render_template, request, jsonify
import logging
import time
import sys
import serial
import serial.tools.list_ports
from typing import Optional
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
from meshtastic.mesh_interface import MeshInterface
from pubsub import pub

LOG_LEVEL = logging.DEBUG  # Set to logging.INFO or logging.ERROR to reduce output
CHANNEL_INDEX = 1  # Use the index configured on your Meshtastic device

was_connected = False
reconnect_attempts = 0
max_reconnect_attempts = 3

def get_first_com_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No COM ports found.")
        return None
    
    # Grab the very first available port object
    first_port = ports[0]
    print(f"Automatically selected: {first_port.device} ({first_port.description})")
    return first_port.device

def get_serial_interface(devPath: Optional[str] = None, 
                         debugOut = None, 
                         noProto: bool = False, 
                         connectNow: bool = True, 
                         noNodes: bool = False, 
                         timeout: int = 30):
    try:
        interface = meshtastic.serial_interface.SerialInterface(devPath, debugOut, noProto, connectNow, noNodes, timeout)
        return interface
    except Exception as e:
        print(f"Error connecting to device: {e}")
        exit(1)

def get_tcp_interface(hostname: str = "192.168.X.X",
                      debugOut = None,
                      noProto: bool = False,
                      connectNow: bool = True,
                      portNumber: int = meshtastic.tcp_interface.DEFAULT_TCP_PORT,
                      noNodes: bool = False,
                      timeout: int = 300):
    # For TCP/Wi-Fi use: from meshtastic.tcp_interface import TCPInterface; interface = TCPInterface(hostname="192.168.X.X")
    try:
        interface = meshtastic.tcp_interface.TCPInterface(hostname, debugOut, noProto, connectNow, portNumber, noNodes, timeout)
        return interface
    except Exception as e:
        print(f"Error connecting to device: {e}")
        exit(1)

# 2. Define the callback function to handle new packets
def on_connection_established(interface):
    global was_connected
    was_connected = True
    global reconnect_attempts
    if reconnect_attempts > 0:
        print(f"Reconnected after {reconnect_attempts} attempts.")
    else:
        print("Connection established with the device.")
    reconnect_attempts = 0

def on_connection_loss(interface):
    print("Connection lost with the device.")
    if interface:
        interface.close()
    time.sleep(10)
    print("Retrying connection...")
    global reconnect_attempts
    reconnect_attempts += 1
    if reconnect_attempts >= max_reconnect_attempts:
        print(f"Maximum reconnect attempts of {max_reconnect_attempts} reached.")
        exit(1)
    
    interface = get_serial_interface(debugOut=None, noProto=False, connectNow=True, noNodes=False, timeout=300)

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

def sendMessage(message):
    """
    Send the message over UART to the Meshtastic device.
    """
    if isinstance(interface, meshtastic.tcp_interface.TCPInterface):
        port = interface.portNumber
    elif isinstance(interface, meshtastic.serial_interface.SerialInterface):
        port = interface.devPath
    else:
        port = "unknown"
    
    if interface is None:
        app.logger.error("Interface is not initialized.")
        return False
    
    app.logger.debug(f"""Sending message: 
        port: {port}
        name: {interface.getLongName()}({interface.getShortName()}) 
        channel {CHANNEL_INDEX}
        message content: 
        
    ------------------------------
    {message}
    ------------------------------""")
    acknowledgment = interface.sendText(message, channelIndex=CHANNEL_INDEX, wantAck=True)
    if acknowledgment:
        success = interface.waitForAckNak()
        return success
    return False

# -----------------------------
# Flask Setup
# -----------------------------
app = Flask(__name__)

# --- CONFIGURATION ---
# Set to True if using TCP/Wi-Fi connection, false if using a USB/serial cable.
USE_TCP = False
meshtastic_ip = "192.168.X.X" #only used if USE_TCP is True
USE_CUSTOM_DEVICE = False #only used if USE_TCP is False
custom_device_path = "/dev/ttyUSB0" #only used if USE_CUSTOM_DEVICE is True

# --- GLOBAL INTERFACE INITIALIZATION ---
# We initialize this globally so Flask doesn't attempt to reconnect on every HTTP request.
try:
    if USE_TCP:
        interface = get_tcp_interface(meshtastic_ip, debugOut=None, noProto=False, connectNow=True, noNodes=False, timeout=300)
    elif USE_CUSTOM_DEVICE:
        interface = get_serial_interface(custom_device_path, debugOut=None, noProto=False, connectNow=True, noNodes=False, timeout=300)
    else:
        interface = get_serial_interface(debugOut=None, noProto=False, connectNow=True, noNodes=False, timeout=300)
        # By default serialinterface() will try to find a meshtastic device,

    pub.subscribe(on_connection_established, "meshtastic.connection.established")
    pub.subscribe(on_connection_loss, "meshtastic.connection.lost")
except Exception as e:
    print(f"Error initializing interface: {e}")
    interface = None
    exit(1)
    
def get_connection_status(showDebug: bool = False):
    """Safely checks the status of the global meshtastic interface."""
    if interface is None:
        return {"status": "disconnected", "reason": "Interface failed to initialize"}
    
    # check if underlying stream/protocol layer is dead or not initialized
    if getattr(interface, "noProto", True):
        return {"status": "disconnected", "reason": "No protocol stream or link down"}
    
    if not interface.isConnected:
        return {"status": "disconnected", "reason": "Interface not connected"}
    
    try:
        # If we can safely pull local node info, the connection is alive and healthy        
        return {
            "status": "connected",
            "short_name": interface.getShortName(),
            "long_name": interface.getLongName(),
            "channel": CHANNEL_INDEX
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}
            

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
    success = False
    attempts = 0
    max_attempts = 3
    delay_between_retries = 10 # Delay in seconds between retry attempts
    while (not success) and (attempts < max_attempts):
        success = False
        try:
            success = sendMessage(message)
            if success:
                app.logger.debug(f"Message acknowledged by the device.")
            else:
                app.logger.debug("Message not acknowledged by the device.")
                time.sleep(delay_between_retries)
                attempts += 1
        except MeshInterface.MeshInterfaceError as e:
            if "Timed out waiting for an acknowledgment" in str(e) or "timeout" in str(e).lower():
                print(f"⚠️ Attempt {attempts} failed: Timed out waiting for Ack/Nak.")
                if attempts < max_attempts:
                    print(f"Retrying in {delay_between_retries} seconds...")
                    time.sleep(delay_between_retries)
                    attempts += 1
                else:
                    print("❌ Max retries reached. Message delivery failed.")
            else:
                # Re-raise other unexpected interface errors (e.g., serial disconnection)
                raise e
        finally:
            # Ensure the interface resource is properly closed
            if ('interface' in locals()) and (interface is not None):
                interface.close()

    if success:
        return jsonify({"status": "Message transmitted"}), 200
    else:
        return jsonify({"status": "Message transmission failed after max attempts"}), 500

@app.route("/test")
def test_page():
    return render_template("test.html")

@app.route('/api/status', methods=['GET'])
def status_endpoint():
    """Returns the current connection status of the Meshtastic device in JSON format."""
    return jsonify(get_connection_status())

@app.route("/")
def index():
    """Simple web view to show the connection status dynamically."""
    return render_template("index.html")

if __name__ == "__main__":
    
    # Set up logging
    app.logger.setLevel(LOG_LEVEL)
    
    # SerialInterface owns an exclusive device handle; the debug reloader can
    # import this module in multiple processes and contend for the same port.
    app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=False)
