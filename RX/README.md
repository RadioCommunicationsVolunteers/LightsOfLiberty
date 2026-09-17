# Lights of Liberty - Receiver

## Message Format Assumption

Assuming the Heltec V4 sends messages in the same framing format used earlier:

``` Code
ID:42
NAME:Ryan
WISH:New HF antenna
ACHIEVE:Completed Skywarn training
END
```

## Install MongoDB client

``` Bash
pip install pymongo
```

## MongoDB Setup

run MongoDB locally on the Raspberry Pi:

``` Bash
sudo apt install mongodb
sudo systemctl enable mongodb
sudo systemctl start mongodb
```

Database: meshtastic_messages
Collection: responses

## Testing Receiver

Simulate incoming UART messages using:

``` Bash
echo -e "ID:1\nNAME:Test\nWISH:Cookies\nACHIEVE:Graduated\nEND\n" > /dev/serial0
```

## Viewing Stored Data with MongoDB

``` Bash
mongo
use meshtastic_messages
db.responses.find().pretty()
```

## Python Server Setup

### Install dependencies

``` Bash
pip install flask flask-socketio pymongo eventlet

```

