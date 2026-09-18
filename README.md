# Lights Of Liberty Postal Service

This is a project for [TheLightsOfLiberty.com](thelightsofliberty.com) event hosted by the [North Liberty Area Chamber of Commerce](https://www.northlibertychamber.org/) and serves as a community fundraiser to provide scholarships and education needs for children in the community.

This project specifically relays mail received from the Lights of Liberty Post Office and delivers it to Santa's Chalet. This will bring a more magical experience for children who are experiencing the Lights of Liberty.

The Post Office will have a [Raspberry Pi](https://www.raspberrypi.com/) (a small computer) connected to a radio (that uses [Meshtastic](https://meshtastic.org/)) to send the mail wirelessly to Santa's Chalet. A Post Office Clerk will assist in helping a child (or a parent or guardian) fill out the child's name and what they want for Christmas. The parent or guardian will also be asked to fill out one positive memory or achievement that year (such as a summer vacation, or an award). The data will be collected on the Raspberry Pi and sent to the radio. The radio will then transmit the encrypted message to a 2nd radio at Santa's Chalet. A number will be provided for each entry to keep track.

At Santa's Chalet, a 2nd radio will receive the message and store it in a 2nd Raspberry Pi. When the parent arrives, they will provide the number they were given for that child, if the number was lost or incorrect, an alternative option to search by name will also be available. The parent will confirm the information is correct and the entry will be added to a waitlist for visiting Santa's Chalet. When the child enters the Chalet to tell Santa what they want for Christmas, Santa will be able to view the mail received.

## Dev Installation

### Step 1: Open Terminal

Open Terminal window on your Raspberry Pi by clicking the terminal icon in the taskbar or by pressing `Ctrl + Alt + T`.

### Step 2: Check if Python 3 is already installed

Run the following command in the terminal to check your current version:

``` Bash
python3 --version
```

If a version number appears, then python 3 is installed.

### Step 3: Install or update Python 3

If you need to install Python 3 or just update it to the latest, make sure you have the latest system-supported packages by running the following commands in order:

1. Update your package list:

``` Bash
sudo apt update
```
2. Install Python 3

``` Bash
sudo apt install python3
```

### Step 4: Install pip and IDLE (Recommended)

To install third-party libraries using the python install package manager (pip) and get the graphical user interface code editor (IDLE), install the packages using the following command:

``` Bash
sudo apt install python3-pip idle3
```

---

### ⚠️ Note about Virtual Environments on Modern Raspberry Pi OS

on newer versions of Raspberry Pi OS, using `pip install <package name>` directly in a terminal will block with the error message "externally managed environment". This protects the OS from breaking. To work on a project, always create a virtual environment first.

``` Bash

# 1. Create a project folder and enter it
mkdir my_project && cd my_project

#2. Create the virtual environment (named 'env')
python3 -m venv env

#3. Activate it
source env/bin/activate

#4. You can now safely install packages
pip install <package_name>
```

For more information on specific packages to install, please view the [TX/README.md](./TX/README.md) for the Post Office (Transmitting) software requirements and the [RX/README.md](./RX/README.md) for Santa's Chalet (Receiving) software requirements.
