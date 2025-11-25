# Complete Hardware Setup Guide
## Quantum-Safe IoT Demo with Arduino UNO & Raspberry Pi 4

This guide walks you through setting up a complete hardware demo of post-quantum cryptography (Kyber/ML-KEM) for IoT devices.

---

## Table of Contents

1. [Hardware Overview](#hardware-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Raspberry Pi Setup](#raspberry-pi-setup)
4. [Arduino UNO Setup](#arduino-uno-setup)
5. [Wiring Guide](#wiring-guide)
6. [Software Installation](#software-installation)
7. [Running the Demo](#running-the-demo)
8. [Troubleshooting](#troubleshooting)
9. [Understanding the Results](#understanding-the-results)

---

## Hardware Overview

### What You Have

| Component | Specs | Role in Demo |
|-----------|-------|--------------|
| **Arduino UNO** | ATmega328P, 2KB SRAM, 32KB Flash | IoT Sensor Node (constrained device) |
| **Raspberry Pi 4** | 8GB RAM, ARM Cortex-A72 | Fog Gateway + Cloud Server |
| **32GB SD Card** | Class 10+ recommended | RPi OS storage |
| **Micro HDMI to HDMI** | For initial setup | RPi display connection |
| **Your Laptop** | Any OS | Development & monitoring |

### Additional Items Needed

- USB-A to USB-B cable (Arduino programming cable)
- Power supply for Raspberry Pi 4 (USB-C, 5V 3A)
- Keyboard & mouse for initial RPi setup (or SSH)
- Optional: Breadboard, LEDs, sensors for real data

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        QUANTUM-SAFE IOT ARCHITECTURE                     │
└──────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │   ARDUINO UNO   │  USB    │ RASPBERRY PI 4  │  Local  │  CLOUD SERVER   │
    │  (IoT Sensor)   │ Serial  │  (Fog Gateway)  │  Call   │  (on same RPi)  │
    └────────┬────────┘         └────────┬────────┘         └────────┬────────┘
             │                           │                           │
             │  ┌─────────────────┐      │  ┌─────────────────┐      │
             │  │ Sensor Reading  │      │  │ Kyber-512 KEM   │      │
             │  │ + XOR Encrypt   │      │  │ Encapsulation   │      │
             │  │ (lightweight)   │      │  │ + AES-GCM       │      │
             │  └─────────────────┘      │  └─────────────────┘      │
             │                           │                           │
             ▼                           ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │  XOR-encrypted  │────────▶│ Decrypt XOR     │────────▶│ Kyber-512 KEM   │
    │  sensor data    │         │ Re-encrypt with │         │ Decapsulation   │
    │  over Serial    │         │ Kyber for Cloud │         │ + AES-GCM Dec   │
    └─────────────────┘         └─────────────────┘         └─────────────────┘
                                                                     │
                                                                     ▼
                                                            ┌─────────────────┐
                                                            │ Store & Analyze │
                                                            │ Sensor Data     │
                                                            └─────────────────┘

DATA FLOW:
1. Arduino reads sensors (or simulates data)
2. Arduino XOR-encrypts with pre-shared key
3. Sends hex-encoded data over USB serial
4. RPi Gateway receives, decrypts XOR
5. Gateway encrypts with Kyber+AES for cloud
6. Cloud decrypts and stores data
```

---

## Raspberry Pi Setup

### Step 1: Flash Raspberry Pi OS

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Insert 32GB SD card into your laptop
3. Open Raspberry Pi Imager
4. Select:
   - **OS**: Raspberry Pi OS (64-bit) - Full version recommended
   - **Storage**: Your 32GB SD card
5. Click the ⚙️ gear icon for advanced options:
   - ✅ Enable SSH
   - Set username: `pi` (or your choice)
   - Set password (remember this!)
   - Configure WiFi if needed
   - Set locale/timezone
6. Click **WRITE** and wait for completion

### Step 2: First Boot

1. Insert SD card into Raspberry Pi 4
2. Connect:
   - Micro HDMI → HDMI monitor
   - USB keyboard & mouse
   - Ethernet cable (if not using WiFi)
   - USB-C power supply
3. Power on - wait for desktop to appear (2-3 minutes first boot)

### Step 3: Enable Serial (for Arduino communication)

Open Terminal and run:

```bash
# enable hardware serial
sudo raspi-config
```

Navigate to:
- **Interface Options** → **Serial Port**
- Would you like a login shell accessible over serial? → **No**
- Would you like the serial port hardware enabled? → **Yes**

Reboot when prompted.

### Step 4: Install Software

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

### Step 5: Copy Project Files

**Option A: From USB Drive**
```bash
# mount usb
sudo mount /dev/sda1 /mnt
cp -r /mnt/hardware/raspberry_pi/* ~/iot_kyber/
cp /mnt/*.py ~/iot_kyber/
sudo umount /mnt
```

**Option B: Using SCP from Laptop**
```bash
# from your laptop terminal
scp -r hardware/raspberry_pi/* pi@<raspberry_pi_ip>:~/iot_kyber/
scp *.py pi@<raspberry_pi_ip>:~/iot_kyber/
```

**Option C: Git Clone (if repo is hosted)**
```bash
git clone <your-repo-url> ~/iot_kyber
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

### Step 3: Upload Sketch

1. Open `hardware/arduino/iot_sensor/iot_sensor.ino`
2. Click **Upload** (→ arrow button)
3. Wait for "Done uploading" message

### Step 4: Test Arduino

Open Serial Monitor (Tools → Serial Monitor):
- Set baud rate to **9600**
- You should see:
  ```
  # INIT: ARDUINO_IOT_001 online
  ENC:4B594245525F494F...  (hex encoded data every 5 seconds)
  ```

### Step 5: Move Arduino to Raspberry Pi

1. Disconnect Arduino from laptop
2. Connect Arduino to Raspberry Pi via USB
3. Arduino will auto-start sending data

---

## Wiring Guide

### Basic Demo (No External Sensors)

For the basic demo, you only need:
- Arduino UNO connected to Raspberry Pi via USB

The Arduino will generate **simulated sensor data** automatically.

### With Real Sensors (Optional)

#### Temperature Sensor (TMP36)

```
TMP36 Pinout:
  ┌─────┐
  │     │
  │  T  │
  │  M  │
  │  P  │
  │  3  │
  │  6  │
  └─┬─┬─┬─┘
    │ │ │
   VCC OUT GND

Wiring:
  TMP36 VCC  → Arduino 5V
  TMP36 OUT  → Arduino A0
  TMP36 GND  → Arduino GND
```

#### Light Sensor (Photoresistor/LDR)

```
         Arduino 5V
              │
              │
            ┌───┐
            │LDR│
            └─┬─┘
              │
              ├────── Arduino A2
              │
            [10kΩ]
              │
              │
          Arduino GND
```

#### Complete Wiring Diagram

```
    ARDUINO UNO                      OPTIONAL SENSORS
   ┌────────────┐
   │            │                    TMP36 (Temp)
   │  5V ●──────┼───────────────────→ VCC
   │            │                       │
   │  A0 ●──────┼───────────────────→ OUT
   │            │
   │  A2 ●──────┼──────┬────────────── LDR
   │            │      │
   │            │    [10kΩ]
   │            │      │
   │ GND ●──────┼──────┴──── GND ←──── GND (all sensors)
   │            │
   │  D2 ●──────┼─────────[Button]──── GND (optional trigger)
   │            │
   │ USB-B ●────┼─────────────────────→ Raspberry Pi USB-A
   │            │
   └────────────┘
```

---

## Software Installation

### Raspberry Pi

```bash
# activate virtual environment
cd ~/iot_kyber
source venv/bin/activate

# verify installation
python -c "from kyber_py.kyber import Kyber512; print('Kyber OK')"
python -c "from Crypto.Cipher import AES; print('AES OK')"
python -c "import serial; print('Serial OK')"
```

### Find Arduino Serial Port

```bash
# list serial ports
ls /dev/tty*

# usually one of:
# /dev/ttyACM0  (most common for Arduino UNO)
# /dev/ttyUSB0  (if using USB-serial adapter)

# test connection
screen /dev/ttyACM0 9600
# you should see ENC:... messages
# press Ctrl+A then K to exit screen
```

### Update Config (if needed)

Edit `config.py` if your serial port is different:

```python
SERIAL_PORT = '/dev/ttyACM0'  # change if needed
```

---

## Running the Demo

### Method 1: Interactive Demo (Recommended)

```bash
cd ~/iot_kyber
source venv/bin/activate

# run interactive demo
python run_demo.py
```

This shows a menu:
```
  1. Full Kyber encryption
  2. Hybrid Kyber-AES
  3. Proxy re-encryption
  4. Hardware demo (Arduino → RPi → Cloud)
  5. Performance comparison
  6. Run all demos
```

### Method 2: Simulation Mode (No Arduino)

```bash
# if arduino not connected, use simulation
python run_demo.py --simulate
```

### Method 3: Individual Components

```bash
# run just the fog gateway
python fog_gateway.py

# or with simulation
python fog_gateway.py --simulate

# run cloud server standalone
python cloud_server.py
```

### Method 4: Full Automated Demo

```bash
python run_demo.py --full --simulate
```

---

## Troubleshooting

### Arduino Not Detected

```bash
# check if arduino is visible
ls /dev/ttyACM*
ls /dev/ttyUSB*

# if not found:
# 1. try different usb port
# 2. check usb cable (some are charge-only)
# 3. replug arduino

# check permissions
groups $USER
# should show 'dialout'

# if not in dialout group:
sudo usermod -a -G dialout $USER
# then logout and login again
```

### Serial Permission Denied

```bash
# quick fix (temporary)
sudo chmod 666 /dev/ttyACM0

# permanent fix
sudo usermod -a -G dialout $USER
# logout and login
```

### Python Import Errors

```bash
# make sure venv is activated
source ~/iot_kyber/venv/bin/activate

# reinstall packages
pip install --force-reinstall kyber-py pycryptodome pyserial
```

### Kyber Import Error

```bash
# kyber-py requires python 3.8+
python --version

# if using older python:
sudo apt install python3.10
python3.10 -m venv venv
source venv/bin/activate
pip install kyber-py pycryptodome pyserial
```

---

## Understanding the Results

### Performance Metrics Explained

| Metric | What It Measures | Typical Value (RPi4) |
|--------|------------------|----------------------|
| **keygen_time_ms** | Time to generate Kyber keypair | 5-20ms |
| **encrypt_time_ms** | Time for Kyber encaps + AES encrypt | 2-8ms |
| **decrypt_time_ms** | Time for Kyber decaps + AES decrypt | 2-10ms |
| **memory_kb** | Peak RAM during operation | 50-200KB |
| **ciphertext_size** | Total encrypted payload size | ~800-900 bytes |

### Interpreting Device Suitability

```
Device Class      RAM      Suitability for Kyber
─────────────────────────────────────────────────
Class 0 (sensor)  10KB     ❌ Too constrained - use PRE
Class 1 (ESP8266) 80KB     ⚠️ Borderline - use Hybrid
Class 2 (ESP32)   512KB    ✅ Hybrid Kyber-512 works
Fog Gateway       2MB+     ✅ Full Kyber-768
Cloud             8GB+     ✅ Kyber-1024
```

### Expected Demo Output

```
[gateway] received encrypted data (85 bytes)
[gateway] device: ARDUINO_IOT_001, temp: 24.5°C, humidity: 58%, light: 520
[gateway] re-encrypted for cloud (kyber_ct: 768B, aes_ct: 93B)
[gateway] enc time: 6.42ms
[cloud] ✓ decrypted sensor data:
  device: ARDUINO_IOT_001
  temp: 24.5°C
  humidity: 58%
  light: 520 lux
  decryption: 7.15ms
```

---

## Demo Scenarios

### Scenario 1: Present to Audience

1. Show architecture diagram (draw on whiteboard)
2. Start with `python run_demo.py`
3. Run scenarios 1, 2, 3 to explain each approach
4. Run performance comparison (scenario 5)
5. Run hardware demo (scenario 4) - shows real data flow

### Scenario 2: Compare Security Levels

```bash
# edit config.py
KYBER_SECURITY_LEVEL = 768  # or 1024

# run demo again to see timing differences
```

### Scenario 3: Stress Test

```bash
# modify Arduino sketch
#define SENSOR_INTERVAL_MS 1000  // 1 second

# re-upload and run demo
# observe throughput and latency
```

---

## Security Notes

⚠️ **This is a demonstration project.** For production:

1. Replace XOR encryption with proper lightweight crypto (AES-CCM)
2. Implement secure key provisioning
3. Add device authentication
4. Use hardware security modules where available
5. Implement proper certificate management
6. Add replay attack protection (timestamps, nonces)

---

## File Structure After Setup

```
~/iot_kyber/
├── venv/                    # python virtual environment
├── config.py                # configuration
├── fog_gateway.py           # raspberry pi gateway
├── cloud_server.py          # cloud server simulation
├── run_demo.py              # interactive demo runner
├── full_kyber.py            # pure kyber implementation
├── hybrid_kyber_aes.py      # hybrid approach
├── proxy_reencryption.py    # pre implementation
└── ~/iot_kyber_data/        # stored metrics and data
    ├── metrics.json
    └── cloud_data.json
```

---

## Quick Reference Commands

```bash
# activate environment
source ~/iot_kyber/venv/bin/activate

# run demo
python run_demo.py

# simulation mode
python run_demo.py --simulate

# full auto demo
python run_demo.py --full

# check serial connection
screen /dev/ttyACM0 9600

# view stored data
cat ~/iot_kyber_data/cloud_data.json | python -m json.tool
```

---

**Author**: Pustak Pathak  
**Project**: Quantum-Safe Cryptography for IoT  
**Date**: 2025



