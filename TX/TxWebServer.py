from flask import Flask, render_template, request, jsonify
import logging
import time
from typing import Optional
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
from meshtastic.mesh_interface import MeshInterface
from meshtastic.node import Node
from pubsub import pub

LOG_LEVEL = logging.DEBUG  # Set to logging.INFO or logging.ERROR to reduce output
CHANNEL_ID = 1  # Use the index configured on your Meshtastic device

was_connected = False
reconnect_attempts = 0
max_reconnect_attempts = 3

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

def initialize_interface(use_tcp: bool = False, use_custom_device: bool = False, meshtastic_ip: Optional[str] = None, custom_device_path: Optional[str] = None) -> meshtastic.interface.Interface:
    try:
        if use_tcp:
            interface = get_tcp_interface(meshtastic_ip, debugOut=None, noProto=False, connectNow=True, noNodes=False, timeout=300)
        elif use_custom_device:
            interface = get_serial_interface(custom_device_path, debugOut=None, noProto=False, connectNow=True, noNodes=False, timeout=300)
        else:
            interface = get_serial_interface(debugOut=None, noProto=False, connectNow=True, noNodes=False, timeout=300)
            # By default serialinterface() will try to find a meshtastic device,

        pub.subscribe(on_connection_established, "meshtastic.connection.established")
        pub.subscribe(on_connection_loss, "meshtastic.connection.lost")
        return interface
    except Exception as e:
        print(f"Error initializing interface: {e}")
        return None   

def enable_want_ack(iface: MeshInterface, channel_id: int = CHANNEL_ID):
    try:
        # Connect to the Meshtastic device
        if iface is None:
            print("Error: Interface is not initialized.")
            return

        node: Node = iface.getNode()


        # Get current channel settings
        channels = node.channels
        if channel_id >= len(channels):
            print(f"Error: Channel index {channel_id} out of range.")
            return

        # Modify the channel settings
        channel = channels[channel_id]
        print(f"Current channel settings: {channel}")

        if channel.settings.encryptionKey is None:
            print("Warning: Channel has no encryption key set. Enabling wantAck may not be effective.")
        else:
            # Enable wantAck
            channel.settings.wantAck = True
            channel.settings.wantResponse = True
            channel.settings.responseTimeout = 300
            channel.settings.responseMaxRetries = 3
            channel.settings.responseRetryInterval = 10
            channel.settings.ackTimeout = 300
            channel.settings.ackMaxRetries = 3
            channel.settings.ackRetryInterval = 10

            # Push updated settings to the device
            interface.setChannel(channel_index, channel.settings)

            print(f"✅ wantAck enabled on channel {channel_index}")

    except Exception as e:
        print(f"Error configuring channel: {e}")
        exit(1)

# 2. Define the callback function to handle new packets
def on_connection_established(interface: meshtastic.interface.Interface):
    global was_connected
    was_connected = True
    global reconnect_attempts
    if reconnect_attempts > 0:
        print(f"Reconnected after {reconnect_attempts} attempts.")
    else:
        print("Connection established with the device.")
    reconnect_attempts = 0

def on_connection_loss(interface: meshtastic.interface.Interface):
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
    
    interface = initialize_interface(use_tcp=USE_TCP, use_custom_device=USE_CUSTOM_DEVICE, meshtastic_ip=meshtastic_ip, custom_device_path=custom_device_path)

def get_connection_status(interface: meshtastic.interface.Interface):
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
            "channel": CHANNEL_ID
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}
    
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

def sendMessage(interface: meshtastic.interface.Interface, message: str, want_Ack: bool = False):
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
        channel {CHANNEL_ID}
        message content: 
        
        ------------------------------
        {message}
        ------------------------------""")
    acknowledgment = interface.sendText(message, wantAck=want_Ack, channelIndex=CHANNEL_ID)
    if not want_Ack:
        return True
    elif acknowledgment:
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
interface = initialize_interface(use_tcp=USE_TCP, use_custom_device=USE_CUSTOM_DEVICE, meshtastic_ip=meshtastic_ip, custom_device_path=custom_device_path)
if interface is None:
    app.logger.error("Failed to initialize the interface.")
    exit(1)            

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
            success = sendMessage(interface, message)
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
