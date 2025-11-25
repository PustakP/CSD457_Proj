#!/usr/bin/env python3
"""
quick_debug.py - minimal test to see what's actually happening
"""
import serial
import time
import sys
import glob
import os

# auto-detect port
def find_arduino():
    ports = []
    for pattern in ['/dev/ttyACM*', '/dev/ttyUSB*']:
        ports.extend(glob.glob(pattern))
    if ports:
        ports.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return ports[0]
    return None

# psk from config
try:
    from config import PSK
    print(f"✓ loaded PSK from config: {PSK.hex()}")
except:
    PSK = b'KYBER_IOT_PSK_01'
    print(f"✓ using default PSK: {PSK.hex()}")

# find port
port = find_arduino()
if not port:
    print("✗ no arduino found")
    sys.exit(1)

print(f"✓ found arduino on: {port}")
print(f"connecting...")

# connect
try:
    ser = serial.Serial(port, 9600, timeout=1.0, exclusive=True)
    time.sleep(2)
    print(f"✓ connected!")
except Exception as e:
    print(f"✗ connect failed: {e}")
    sys.exit(1)

# flush
ser.reset_input_buffer()
ser.reset_output_buffer()

# ping
ser.write(b"PING\n")
print(f"\n→ sent PING")
time.sleep(0.5)
if ser.in_waiting:
    resp = ser.readline().decode().strip()
    print(f"← {resp}")

print(f"\n{'='*70}")
print(f"waiting for button press (showing EVERYTHING received)...")
print(f"press button on arduino, then ctrl+c")
print(f"{'='*70}\n")

line_num = 0
enc_count = 0

try:
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                line_num += 1
                print(f"[{line_num:3d}] {repr(line)}")
                
                # try to decrypt ENC: lines
                if line.startswith('ENC:'):
                    enc_count += 1
                    hex_data = line[4:].strip()
                    print(f"      ↳ hex_len={len(hex_data)}")
                    
                    try:
                        encrypted = bytes.fromhex(hex_data)
                        print(f"      ↳ encrypted_len={len(encrypted)}")
                        
                        # xor decrypt
                        decrypted = bytes(a ^ b for a, b in zip(encrypted, (PSK * ((len(encrypted) // len(PSK)) + 1))))
                        decrypted = decrypted[:len(encrypted)]
                        print(f"      ↳ decrypted={repr(decrypted[:80])}")
                        
                        # try parse json
                        import json
                        data = json.loads(decrypted.decode())
                        print(f"      ↳ JSON OK: {data}")
                        print(f"      ✓ SUCCESS!")
                    except Exception as e:
                        print(f"      ✗ decrypt/parse failed: {type(e).__name__}: {e}")
                print()
        
        time.sleep(0.01)
        
except KeyboardInterrupt:
    print(f"\n{'='*70}")
    print(f"summary: received {line_num} lines, {enc_count} ENC messages")
    print(f"{'='*70}")

ser.close()

