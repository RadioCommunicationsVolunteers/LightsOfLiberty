# Lights of Liberty - Transmitter

## Overview

The Lights of Liberty event is hosted by the North Liberty Area Chamber of Commerce. It is a walking trail of lights to help raise donations for local children for their education.

This is for the transmitter portion of this system and is designed for 

## Hardware Technical Specifications

- A Raspberry Pi
- A Heltec V4 (for Meshtastic)

## Software Technical Specifications

- A web Server written in Python.
  - Flask Framework
  - GPIO-based serial communications

## Heltech V4 UART pins
  
| Heltec Pin | Raspberry Pi Pin |
| :--------- | :--------------- |
| RX         | GPIO14 (TXD)     |
| TX         | GPIO15 (RXD)     |
| GND        | GND              |

Baud Rate: **115200** (Meshtastic default)

Enable UART on Raspberry Pi:

``` Bash
sudo raspi-config
# Interface Options → Serial → Disable login shell, enable serial port hardware
```

Install Flask using Python Install Package Manager

``` Bash
pip install flask pyserial
```

## Example POST Request

Json payload:

``` JSON
{
  "id": 42,
  "first_name": "Ryan",
  "christmas_wish": "New HF antenna",
  "achievement": "Completed Skywarn training"
}
```

Post to:

``` code
http://<raspberrypi-ip>:8080/submit
```

## Meshtastic Firmware

Heltec V4 firmware should:

1) Read UART input line-by-line
2) Detect the END terminator
3) Package the message into a Meshtastic text payload
4) Transmit normally

Example pseudocode for the Heltec side:

``` Cpp
String buffer = "";
while (Serial.available()) {
    char c = Serial.read();
    buffer += c;

    if (buffer.endsWith("END\n")) {
        sendMeshtasticText(buffer);
        buffer = "";
    }
}
```