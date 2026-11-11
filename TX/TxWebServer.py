from flask import Flask, render_template, request, jsonify
import logging
import time
from typing import Optional
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
from meshtastic.mesh_interface import MeshInterface
from meshtastic.serial_interface import SerialInterface
from meshtastic.tcp_interface import TCPInterface
from meshtastic.node import Node
from pubsub import pub

LOG_LEVEL = logging.DEBUG  # Set to logging.INFO or logging.ERROR to reduce output
rx_node_short_name = "LoLB"  # Set this to the short name of the receiving node you want to send messages to

was_connected = False
reconnect_attempts = 0
max_reconnect_attempts = 3

def initialize_interface(use_tcp: bool = False, use_custom_device: bool = False, meshtastic_ip: Optional[str] = None, custom_device_path: Optional[str] = None) -> MeshInterface:
    if use_tcp:
        if not meshtastic_ip:
            raise ValueError("Meshtastic IP must be provided when using TCP.")
        iface = TCPInterface(meshtastic_ip)
    elif use_custom_device:
        if not custom_device_path:
            raise ValueError("Custom device path must be provided when using a custom device.")
        iface = SerialInterface(custom_device_path)
    else:
        iface = SerialInterface()
        # By default serialinterface() will try to find a meshtastic device,

    pub.subscribe(on_connection_established, "meshtastic.connection.established")
    pub.subscribe(on_connection_loss, "meshtastic.connection.lost")
    return iface

# 2. Define the callback function to handle new packets
def on_connection_established(iface: MeshInterface):
    global was_connected
    was_connected = True
    global reconnect_attempts
    if reconnect_attempts > 0:
        print(f"Reconnected after {reconnect_attempts} attempts.")
    else:
        # Get the node ID of the receiving node by its short name
        global rx_node_id
        rx_node_info = get_node_by_short_name(iface, rx_node_short_name)
        if rx_node_info is None:
            app.logger.error(f"Receiving node with short name '{rx_node_short_name}' not found.")
            exit(1)
        rx_node_id = rx_node_info["nodeNum"]
        app.logger.debug(f"Receiving node ID for '{rx_node_short_name}': {rx_node_id}")
        print("Connection established with the device.")
    reconnect_attempts = 0

def on_connection_loss(iface: MeshInterface):
    print("Connection lost with the device.")
    if iface:
        iface.close()
    time.sleep(10)
    print("Retrying connection...")
    global reconnect_attempts
    reconnect_attempts += 1
    if reconnect_attempts >= max_reconnect_attempts:
        print(f"Maximum reconnect attempts of {max_reconnect_attempts} reached.")
        exit(1)
    
    iface = initialize_interface(use_tcp=USE_TCP, use_custom_device=USE_CUSTOM_DEVICE, meshtastic_ip=meshtastic_ip, custom_device_path=custom_device_path)

def get_connection_status(iface: MeshInterface):
    """Safely checks the status of the global meshtastic interface."""
    if iface is None:
        return {"status": "disconnected", "reason": "Interface failed to initialize"}
    
    # check if underlying stream/protocol layer is dead or not initialized
    if getattr(iface, "noProto", True):
        return {"status": "disconnected", "reason": "No protocol stream or link down"}
    
    if not iface.isConnected:
        return {"status": "disconnected", "reason": "Interface not connected"}
    
    try:
        # If we can safely pull local node info, the connection is alive and healthy        
        return {
            "status": "connected",
            "short_name": iface.getShortName(),
            "long_name": iface.getLongName(),
            "node_id": iface.localNode.nodeNum
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}
    
def get_node_by_short_name(iface: MeshInterface, short_name: str):
  if not iface.nodes:
      return None
  
  nodes: dict[str, dict[str, meshtastic.Any]] = iface.nodes or {}    
  for node_id, node_info in nodes.items():
    user: dict[str, meshtastic.Any] = node_info.get("user", {})
    if user and user.get("shortName") == short_name:
      return node_info
  return None
    
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

def sendMessage(iface: MeshInterface, node_id: str, message: str, want_Ack: bool = False):
    """
    Send the message over UART to the Meshtastic device.
    """
    if isinstance(iface, TCPInterface):
        port = iface.portNumber
    elif isinstance(iface, SerialInterface):
        port = iface.devPath
    else:
        port = "unknown"
    
    if iface is None:
        app.logger.error("Interface is not initialized.")
        return False
    
    app.logger.debug(f"""Sending message: 
        port: {port}
        name: {iface.getLongName()}({iface.getShortName()}) 
        node {node_id}
        message content: 
        
        ------------------------------
        {message}
        ------------------------------""")
    meshPacket = iface.sendText(message, destinationId=node_id, wantAck=want_Ack)
    if not want_Ack:
        return True
    elif meshPacket:
        return iface.waitForAckNak()
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
iface = initialize_interface(use_tcp=USE_TCP, use_custom_device=USE_CUSTOM_DEVICE, meshtastic_ip=meshtastic_ip, custom_device_path=custom_device_path)
if iface is None:
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
            success = sendMessage(iface, rx_node_id, message)
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
            if ('interface' in locals()) and (iface is not None):
                iface.close()

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
    return jsonify(get_connection_status(iface))

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
