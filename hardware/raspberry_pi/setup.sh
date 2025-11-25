#!/bin/bash
# setup.sh - raspberry pi 4 setup script for iot kyber demo
# run this after first boot of raspberry pi os

set -e

echo "=============================================="
echo "QUANTUM-SAFE IOT DEMO - RASPBERRY PI SETUP"
echo "=============================================="

# update system
echo "[1/6] updating system packages..."
sudo apt update && sudo apt upgrade -y

# install python and deps
echo "[2/6] installing python and dependencies..."
sudo apt install -y python3 python3-pip python3-venv git

# install serial/gpio tools
echo "[3/6] installing serial and gpio tools..."
sudo apt install -y python3-serial screen minicom

# add user to dialout group (for serial access)
echo "[4/6] configuring serial permissions..."
sudo usermod -a -G dialout $USER

# create project directory
echo "[5/6] setting up project directory..."
cd ~
if [ ! -d "iot_kyber" ]; then
    mkdir iot_kyber
fi
cd iot_kyber

# create virtual environment
echo "[6/6] creating python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# install python packages
pip install --upgrade pip
pip install kyber-py pycryptodome pyserial

# create data directory
mkdir -p ~/iot_kyber_data

echo ""
echo "=============================================="
echo "SETUP COMPLETE!"
echo "=============================================="
echo ""
echo "next steps:"
echo "  1. copy project files to ~/iot_kyber/"
echo "  2. connect arduino via usb"
echo "  3. run: source ~/iot_kyber/venv/bin/activate"
echo "  4. run: python run_demo.py"
echo ""
echo "note: you may need to reboot for serial permissions"
echo ""



