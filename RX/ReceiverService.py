import time
import sys
import serial
import serial.tools.list_ports
from pubsub import pub
from typing import Optional
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
from pymongo import MongoClient

was_connected = False
reconnect_attempts = 0
max_reconnect_attempts = 3
CHANNEL_INDEX = 1  # Use the index configured on your Meshtastic device

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
    if reconnect_attempts > 0:
        print(f"Reconnected after {reconnect_attempts} attempts.")
        
    print("Connection established with the device.")
    global reconnect_attempts
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

def on_receive(packet, interface):
    try:
        # Check if the incoming packet is a text message
        # if packet.get("decoded", {}).get("portnum") == "TEXT_MESSAGE_APP":
        if "decoded" in packet and "text" in packet["decoded"]:
            # Extract and decode the text payload
            message_text = packet["decoded"]["text"]
            
            sender_id = packet["from"]
            channel = packet.get("decoded", {}).get("channel", None)
            
            if channel == CHANNEL_INDEX:
                print(f"New message from Node {sender_id} on channel {channel}: {message_text}")
            
                # interface.sendText() parameters: (text, destinationId=None, wantAck=False, channelIndex=0)
                reply_text = f"ack: {message_text}"

                # Send a reply back (set wantAck=True if you want firmware-level delivery confirmation)
                interface.sendText(
                    text=reply_text,
                    destinationId=sender_id,  # Or broadcast / channel
                    wantAck=True, # Request firmware-level delivery confirmation
                    channelIndex=channel,
                )
                print(f"Sent reply to Node {sender_id} on channel {channel}: {reply_text}")
      
                # insert into MongoDB
                collection.insert_one(packet)
                print("Saved to MongoDB:", packet)
    
    except Exception as e:
        print(f"Error parsing packet: {e}")

def get_Meshtastic_firmware_version(metadata, interface):
    try:
        if metadata and hasattr(metadata, "firmware_version"):
            print(f"Firmware Version: {metadata.firmware_version}")
        else:
            # Alternative lookup if reading direct from the local node info cache
            local_node = interface.nodes.get(str(interface.myInfo.my_node_num))
            fw_ver = local_node.get('user', {}).get('firmwareVersion', 'Unknown')
            
            print(f"Firmware Version: {fw_ver}")
    except Exception as e:
        print(f"Error retrieving firmware version: {e}")
        return None


# 1. Connect to the radio (via USB/Serial)
interface = get_serial_interface(debugOut=None, noProto=False, connectNow=True, noNodes=False, timeout=300)
# interface - get_tcp_interface(hostname="192.168.X.X", debugOut=None, noProto=False, connectNow=True, portNumber=meshtastic.tcp_interface.DEFAULT_TCP_PORT, noNodes=False, timeout=300)

# 2. Give the background database a brief moment to populate mesh nodes
time.sleep(10)

# Wait for the connection to complete and populate node information
# Fetch metadata details from the local node
metadata = interface.metadata

client = MongoClient("mongodb://localhost:27017/")
db = client["meshtastic_messages"]
collection = db["responses"]

buffer = ""

# 3. Access and read node information
assert interface.localNode is not None
localNode = interface.localNode

firmware_version = get_Meshtastic_firmware_version(metadata, interface)
# assert interface.myInfo is not None
# firmware_edition = interface.myInfo.firmware_edition

# assert interface.userConfig is not None
# userConfig = interface.userConfig

pub.subscribe(on_connection_established, "meshtastic.connection.established")
pub.subscribe(on_connection_loss, "meshtastic.connection.lost")

# 3. Subscribe to the receive topic
pub.subscribe(on_receive, "meshtastic.receive")
