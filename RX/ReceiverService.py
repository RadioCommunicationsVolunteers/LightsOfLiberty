import time
from pubsub import pub
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
import meshtastic.node
from pymongo import MongoClient

def get_serial_interface(devPath: str | None = None, 
                         debugOut = None, 
                         noProto: bool = False, 
                         connectNow: bool = True, 
                         noNodes: bool = False, 
                         timeout: int = 300):
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
def on_receive(packet, interface):
    try:
        # Check if the incoming packet is a text message
        if packet.get("decoded", {}).get("portnum") == "TEXT_MESSAGE_APP":
            # Extract and decode the text payload
            message_text = packet["decoded"]["text"]
            sender_id = packet["from"]
            print(f"New message from Node {sender_id}: {message_text}")
            
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
interface = get_serial_interface(devPath="/dev/ttyUSB0", debugOut=None, noProto=False, connectNow=True, noNodes=False, timeout=300)
# interface - get_tcp_interface(hostname="192.168.X.X", debugOut=None, noProto=False, connectNow=True, portNumber=meshtastic.tcp_interface.DEFAULT_TCP_PORT, noNodes=False, timeout=300)

# 2. Give the background database a brief moment to populate mesh nodes
time.sleep(2)

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

# 3. Subscribe to the receive topic
pub.subscribe(on_receive, "meshtastic.receive")

# Keep the script running to continue listening
try:
    print("Listening for new messages... Press Ctrl+C to exit.")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Closing connection...")
    interface.close()
