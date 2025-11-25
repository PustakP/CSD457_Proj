#!/usr/bin/env python3
"""
test_serial_raw.py - raw serial debugger
shows every byte/line received from arduino to diagnose msg loss

usage: python test_serial_raw.py [port] [baud]
       if port not specified, auto-detects /dev/ttyACM* or /dev/ttyUSB*
"""
import serial
import sys
import time
import glob
import os
from datetime import datetime

def auto_detect_arduino():
    """auto-detect arduino port by scanning /dev/tty* devices"""
    potential = []
    for pattern in ['/dev/ttyACM*', '/dev/ttyUSB*']:
        potential.extend(glob.glob(pattern))
    
    if not potential:
        return None
    
    # sort by mod time (most recent = active port)
    potential.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return potential[0]

# cfg - auto-detect if not specified
if len(sys.argv) > 1:
    port = sys.argv[1]
else:
    port = auto_detect_arduino()
    if not port:
        port = '/dev/ttyACM0'  # fallback
        print(f"⚠ no arduino found, trying default: {port}")
    else:
        print(f"✓ auto-detected arduino: {port}")

baud = int(sys.argv[2]) if len(sys.argv) > 2 else 9600

print(f"connecting to {port} @ {baud} baud...")
print("press ctrl+c to exit")
print("=" * 70)

try:
    # open serial w/ generous buffers, exclusive access
    ser = serial.Serial(
        port,
        baud,
        timeout=1.0,
        write_timeout=1.0,
        inter_byte_timeout=0.1,
        exclusive=True  # fail if port already open
    )
    
    # set large buffers if possible
    try:
        ser.set_buffer_size(rx_size=4096, tx_size=4096)
        print(f"✓ set buffer size to 4096 bytes")
    except:
        print(f"⚠ couldn't set buffer size (may be ok)")
    
    time.sleep(2)  # wait for arduino reset
    
    # flush old data
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    
    print(f"✓ connected to {port}")
    print(f"⚠ if no data appears, check:")
    print(f"   1. kill any 'screen' sessions: sudo pkill screen")
    print(f"   2. check port access: ls -l {port}")
    print(f"   3. verify arduino is sending (check LED/serial monitor)")
    print(f"waiting for data... (buffer check every 1ms)")
    print("=" * 70)
    
    # send ping
    ser.write(b"PING\n")
    print(f"→ sent PING, waiting for PONG...")
    
    line_count = 0
    enc_count = 0
    button_count = 0
    buffer = ""
    last_stats = time.time()
    
    while True:
        # read all available data immediately
        if ser.in_waiting > 0:
            bytes_read = ser.in_waiting
            chunk = ser.read(bytes_read).decode('utf-8', errors='ignore')
            buffer += chunk
            
            # process complete lines
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                
                if line:
                    line_count += 1
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    
                    # categorize msg
                    if line.startswith('ENC:'):
                        enc_count += 1
                        hex_len = len(line) - 4
                        print(f"[{timestamp}] 🔐 ENC msg #{enc_count} ({hex_len} hex chars)")
                        print(f"           {line[:80]}{'...' if len(line) > 80 else ''}")
                    elif line.startswith('# BUTTON'):
                        button_count += 1
                        print(f"[{timestamp}] 🔘 BUTTON #{button_count}: {line[2:]}")
                    elif line.startswith('#'):
                        print(f"[{timestamp}] 📝 DEBUG: {line[2:]}")
                    elif line.startswith('PONG'):
                        print(f"[{timestamp}] 🏓 PONG: {line[5:]}")
                    else:
                        print(f"[{timestamp}] ❓ UNKNOWN: {line[:60]}")
        
        # print stats every 5 sec
        now = time.time()
        if now - last_stats > 5.0:
            last_stats = now
            print(f"\n--- stats: total_lines={line_count}, enc_msgs={enc_count}, button_presses={button_count} ---\n")
        
        time.sleep(0.001)  # 1ms polling - same as live_demo
        
except KeyboardInterrupt:
    print(f"\n\n{'='*70}")
    print(f"summary:")
    print(f"  total lines received: {line_count}")
    print(f"  enc messages: {enc_count}")
    print(f"  button presses: {button_count}")
    print(f"{'='*70}")
except Exception as e:
    print(f"\nerror: {e}")
    sys.exit(1)
finally:
    if 'ser' in locals():
        ser.close()

