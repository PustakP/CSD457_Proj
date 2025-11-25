# Complete Hardware Setup Guide
## Quantum-Safe IoT Demo with Arduino UNO & Raspberry Pi 4

This guide walks you through setting up a complete hardware demo of post-quantum cryptography (Kyber/ML-KEM) for IoT devices.

---

## Table of Contents

1. [Quick Start (Demo Day)](#quick-start-demo-day)
2. [Hardware Overview](#hardware-overview)
3. [Architecture Diagram](#architecture-diagram)
4. [Raspberry Pi Setup](#raspberry-pi-setup)
5. [Arduino UNO Setup](#arduino-uno-setup)
6. [Wiring Guide](#wiring-guide)
7. [Running the Demo](#running-the-demo)
8. [Troubleshooting](#troubleshooting)
9. [Understanding the Results](#understanding-the-results)

---

## Quick Start (Demo Day)

**For the button-triggered demo via SSH:**

### On Your Laptop (SSH into RPi):

```bash
# ssh into raspberry pi
ssh pi@<raspberry_pi_ip>

# go to project dir and activate venv
cd ~/iot_kyber
source venv/bin/activate

# run the live demo script
python live_demo.py
```

### What Happens:
1. Press **button on Arduino** → LED blinks
2. Arduino sends XOR-encrypted "sensor" data over USB serial
3. Raspberry Pi receives and decrypts
4. **Proxy Re-Encryption** transforms data using CRYSTALS-Kyber
5. Simulated cloud decrypts and displays results
6. All steps shown **live in SSH terminal** with timing metrics

### Hardware Needed:
- Arduino UNO + push button (between pin 2 and GND)
- Raspberry Pi 4 (SSH access configured)
- USB cable connecting Arduino to RPi

That's it! No sensors, no monitor needed.

---

## Hardware Overview

### What You Have

| Component | Specs | Role in Demo |
|-----------|-------|--------------|
| **Arduino UNO** | ATmega328P, 2KB SRAM, 32KB Flash | IoT Sensor Node (constrained device) |
| **Raspberry Pi 4** | 8GB RAM, ARM Cortex-A72 | Fog Gateway + Cloud Server |
| **32GB SD Card** | Class 10+ recommended | RPi OS storage |
| **Push Button** | Momentary switch | Demo trigger |
| **Your Laptop** | Any OS | SSH terminal for demo |

### Minimal Demo Setup

For the button-triggered demo, you only need:
- Arduino UNO
- One push button (or just wire between pin 2 and GND to trigger)
- USB cable to Raspberry Pi
- SSH access to Raspberry Pi

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     QUANTUM-SAFE IOT DEMO ARCHITECTURE                   │
│                         (Button-Triggered Demo)                          │
└──────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │   ARDUINO UNO   │  USB    │ RASPBERRY PI 4  │  Local  │  CLOUD SERVER   │
    │  (IoT Sensor)   │ Serial  │  (Fog Gateway)  │  Call   │  (on same RPi)  │
    └────────┬────────┘         └────────┬────────┘         └────────┬────────┘
             │                           │                           │
             │  ┌─────────────────┐      │  ┌─────────────────┐      │
             │  │ Button Press    │      │  │ Kyber-512 KEM   │      │
             │  │ → Simulated     │      │  │ Encapsulation   │      │
             │  │   Sensor Data   │      │  │ + Proxy RE      │      │
             │  │ → XOR Encrypt   │      │  │ + AES-GCM       │      │
             │  └─────────────────┘      │  └─────────────────┘      │
             │                           │                           │
             ▼                           ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │  ENC:4B594...   │────────▶│ 1. Decrypt XOR  │────────▶│ Kyber-512 KEM   │
    │  (hex over USB) │         │ 2. Kyber encaps │         │ Decapsulation   │
    │                 │         │ 3. Proxy RE     │         │ + AES-GCM Dec   │
    └─────────────────┘         └─────────────────┘         └─────────────────┘
                                                                     │
                                                                     ▼
                                                            ┌─────────────────┐
                                                            │ Display Data in │
                                                            │ SSH Terminal    │
                                                            └─────────────────┘

DEMO WORKFLOW:
1. Press button on Arduino
2. Arduino generates simulated temp/humidity/light data
3. Arduino XOR-encrypts with pre-shared key (lightweight for constrained device)
4. Sends hex-encoded data over USB serial to RPi
5. RPi Gateway receives, decrypts XOR layer
6. Gateway performs CRYSTALS-Kyber encapsulation (device key)
7. Gateway does Proxy Re-Encryption (transforms to cloud key)
8. Cloud decapsulates and decrypts
9. All displayed live in SSH terminal with timing
```

---

## Raspberry Pi Setup

### Step 1: Flash Raspberry Pi OS

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Insert 32GB SD card into your laptop
3. Open Raspberry Pi Imager
4. Select:
   - **OS**: Raspberry Pi OS (64-bit) - Lite version OK for headless
   - **Storage**: Your 32GB SD card
5. Click the ⚙️ gear icon for advanced options:
   - ✅ **Enable SSH** (important!)
   - Set username: `pi` (or your choice)
   - Set password (remember this!)
   - Configure WiFi (network name and password)
   - Set locale/timezone
6. Click **WRITE** and wait for completion

### Step 2: First Boot (Headless)

1. Insert SD card into Raspberry Pi 4
2. Connect:
   - Ethernet cable OR WiFi will auto-connect
   - USB-C power supply
3. Wait 2-3 minutes for first boot
4. Find RPi IP address:
   ```bash
   # from your laptop (same network)
   ping raspberrypi.local
   # or check your router's DHCP leases
   ```
5. SSH in:
   ```bash
   ssh pi@<raspberry_pi_ip>
   # or
   ssh pi@raspberrypi.local
   ```

### Step 3: Install Software

```bash
# update system
sudo apt update && sudo apt upgrade -y

# install dependencies
sudo apt install -y python3-pip python3-venv git python3-serial

# add user to dialout group (for serial access)
sudo usermod -a -G dialout $USER

# create project directory
mkdir -p ~/iot_kyber
cd ~/iot_kyber

# create virtual environment
python3 -m venv venv
source venv/bin/activate

# install python packages
pip install kyber-py pycryptodome pyserial

# create data directory
mkdir -p ~/iot_kyber_data
```

### Step 4: Copy Project Files

**Option A: Using SCP from Laptop (recommended)**
```bash
# from your laptop terminal (in project directory)
scp -r hardware/raspberry_pi/* pi@<raspberry_pi_ip>:~/iot_kyber/
scp *.py pi@<raspberry_pi_ip>:~/iot_kyber/
```

**Option B: From USB Drive**
```bash
# on raspberry pi
sudo mount /dev/sda1 /mnt
cp -r /mnt/hardware/raspberry_pi/* ~/iot_kyber/
cp /mnt/*.py ~/iot_kyber/
sudo umount /mnt
```

### Step 5: Verify Installation

```bash
cd ~/iot_kyber
source venv/bin/activate

# test imports
python -c "from kyber_py.kyber import Kyber512; print('✓ Kyber OK')"
python -c "from Crypto.Cipher import AES; print('✓ AES OK')"
python -c "import serial; print('✓ Serial OK')"
```

---

## Arduino UNO Setup

### Step 1: Install Arduino IDE

On your **laptop**:
1. Download [Arduino IDE](https://www.arduino.cc/en/software)
2. Install and open Arduino IDE

### Step 2: Connect Arduino

1. Connect Arduino UNO to laptop via USB-B cable
2. In Arduino IDE:
   - **Tools** → **Board** → **Arduino UNO**
   - **Tools** → **Port** → Select the COM port (Windows) or `/dev/ttyACM0` (Linux/Mac)

### Step 3: Upload Button Demo Sketch

1. Open `hardware/arduino/button_demo/button_demo.ino`
2. Click **Upload** (→ arrow button)
3. Wait for "Done uploading" message

### Step 4: Test Arduino

1. Open Serial Monitor (Tools → Serial Monitor)
2. Set baud rate to **9600**
3. You should see:
   ```
   # INIT: ARDUINO_SENSOR_001 ready
   # MODE: button-triggered demo
   # WAITING: press button to send sensor data
   ```
4. Connect a wire from Pin 2 to GND briefly (or press button)
5. You should see:
   ```
   # BUTTON: pressed
   ENC:4B594245525F...
   ```

### Step 5: Move Arduino to Raspberry Pi

1. Disconnect Arduino from laptop
2. Connect Arduino to Raspberry Pi via USB
3. Arduino will auto-start sending data when button pressed

---

## Wiring Guide

### Button Demo Wiring (Minimal)

```
    ARDUINO UNO
   ┌────────────┐
   │            │
   │  D2  ●─────┼────[BUTTON]────┐
   │            │                │
   │  GND ●─────┼────────────────┘
   │            │
   │ USB-B ●────┼────────────────→ Raspberry Pi USB-A
   │            │
   └────────────┘

NOTES:
- Button is a simple momentary push button
- Uses Arduino's internal pullup resistor (no external resistor needed)
- Can also just touch a wire between D2 and GND to trigger

ALTERNATIVE (No Button):
- Just use a jumper wire
- Touch one end to Pin 2, other to GND
- Release to complete trigger
```

### LED Indicator

The Arduino's built-in LED (Pin 13) blinks when data is sent.

---

## Running the Demo

### Primary Method: Live SSH Demo

```bash
# ssh into raspberry pi
ssh pi@raspberrypi.local  # or pi@<ip_address>

# navigate and activate
cd ~/iot_kyber
source venv/bin/activate

# run live demo
python live_demo.py
```

**During Demo:**
1. Terminal shows live updating display
2. Press button on Arduino
3. Watch the workflow steps execute:
   - Device Encryption (Kyber KEM + AES)
   - Gateway Proxy Re-Encryption
   - Cloud Decryption
4. See timing metrics and decrypted sensor data
5. Press Ctrl+C to exit

### Alternative: Simulation Mode (No Arduino)

```bash
# runs with auto-simulated data (every 30 seconds)
python live_demo.py
# will show "arduino not found - using simulation mode"
```

### Alternative: Original Demo Runner

```bash
# interactive menu with all scenarios
python run_demo.py

# with arduino simulation
python run_demo.py --simulate

# full automated demo
python run_demo.py --full
```

---

## Troubleshooting

### Arduino Not Detected on RPi

```bash
# check if arduino is visible
ls /dev/ttyACM*
ls /dev/ttyUSB*

# if not found:
# 1. unplug and replug arduino
# 2. try different usb port on rpi
# 3. check usb cable (some are charge-only)

# check permissions
groups $USER  # should show 'dialout'

# if not in dialout group:
sudo usermod -a -G dialout $USER
# then logout and login (or reboot)
```

### Serial Permission Denied

```bash
# quick fix (temporary)
sudo chmod 666 /dev/ttyACM0

# permanent fix
sudo usermod -a -G dialout $USER
# logout and login
```

### SSH Connection Issues

```bash
# make sure ssh is enabled on rpi
# if you can access rpi directly:
sudo raspi-config
# Interface Options → SSH → Enable

# check rpi is on network
ping raspberrypi.local

# check ssh service
sudo systemctl status ssh
```

### Python Import Errors

```bash
# make sure venv is activated
source ~/iot_kyber/venv/bin/activate

# reinstall packages
pip install --force-reinstall kyber-py pycryptodome pyserial
```

### Display Issues in SSH

```bash
# if colors don't show, terminal might not support ANSI
export TERM=xterm-256color

# resize terminal if display is cut off
# (make terminal window taller - at least 50 lines)
```

---

## Understanding the Results

### Performance Metrics Explained

| Metric | What It Measures | Typical Value (RPi4) |
|--------|------------------|----------------------|
| **Device Encrypt** | Kyber encaps + AES encrypt | 3-8 ms |
| **Gateway PRE** | Proxy re-encryption transform | 5-12 ms |
| **Cloud Decrypt** | Kyber decaps + AES decrypt | 5-15 ms |
| **Total Workflow** | End-to-end time | 15-35 ms |
| **Kyber CT Size** | Ciphertext size | ~768 bytes (Kyber-512) |

### Security Levels

| Level | Security | Key Size | CT Size | Use Case |
|-------|----------|----------|---------|----------|
| Kyber-512 | NIST Level 1 | 800 B | 768 B | IoT, constrained |
| Kyber-768 | NIST Level 3 | 1184 B | 1088 B | General purpose |
| Kyber-1024 | NIST Level 5 | 1568 B | 1568 B | High security |

### What the Demo Proves

1. **Post-Quantum Security**: CRYSTALS-Kyber protects against quantum attacks
2. **Fog Computing**: Gateway handles heavy crypto for constrained devices
3. **Proxy Re-Encryption**: Data transformed without gateway seeing plaintext
4. **Real-Time Performance**: Encryption/decryption in milliseconds

---

## Demo Script for Presentation

### Opening (30 seconds)
"This demo shows how we can protect IoT sensor data using post-quantum cryptography. The Arduino represents a constrained IoT sensor, and the Raspberry Pi acts as a fog computing gateway."

### Button Press Demo (2 minutes)
1. Show the SSH terminal with live_demo.py running
2. Press button: "When the sensor detects data..."
3. Point out each step as it lights up
4. Show the timing metrics
5. Show the decrypted sensor values

### Key Points to Mention
- "CRYSTALS-Kyber is a NIST-standardized post-quantum algorithm"
- "Proxy re-encryption lets the gateway transform the encryption without seeing the data"
- "Total processing time is only X milliseconds"
- "This approach offloads heavy crypto from constrained devices"

### Closing (30 seconds)
"This architecture is practical for real IoT deployments where quantum computers may become a threat in the device's lifetime."

---

## File Structure

```
~/iot_kyber/
├── venv/                    # python virtual environment
├── config.py                # configuration
├── fog_gateway.py           # raspberry pi gateway
├── cloud_server.py          # cloud server simulation
├── run_demo.py              # interactive demo runner
├── live_demo.py             # ★ SSH live updating demo
├── full_kyber.py            # pure kyber implementation
├── hybrid_kyber_aes.py      # hybrid approach
├── proxy_reencryption.py    # pre implementation
└── ~/iot_kyber_data/        # stored metrics and data
```

---

## Quick Reference Commands

```bash
# ssh into raspberry pi
ssh pi@raspberrypi.local

# activate environment
cd ~/iot_kyber && source venv/bin/activate

# run live demo (main script for demo)
python live_demo.py

# with higher security level
python live_demo.py --768
python live_demo.py --1024

# check serial connection
ls /dev/ttyACM*

# test arduino directly
screen /dev/ttyACM0 9600
# type PING and press Enter to test
# press Ctrl+A then K to exit screen
```

---

**Author**: Pustak Pathak  
**Project**: Quantum-Safe Cryptography for IoT  
**Date**: 2025
