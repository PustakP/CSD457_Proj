# Serial Message Reception Debugging Guide

## Common Issue: Port Conflict (Program Hangs or No Data)

**Symptom:** `test_serial_raw.py` connects but receives nothing, OR `live_demo.py` shows increasing recv count but stays stuck on "processing"

**Cause:** Only ONE program can read from `/dev/ttyACM0` at a time. If `screen`, another Python script, or Arduino IDE serial monitor has the port open, your program won't get data.

### Quick Fix

```bash
cd hardware/raspberry_pi

# kill all programs using serial port
chmod +x fix_serial.sh
./fix_serial.sh /dev/ttyACM0

# now run your test
python test_serial_raw.py /dev/ttyACM0 9600
```

### Manual Fix

```bash
# kill screen sessions
sudo pkill screen

# kill any python using the port
sudo fuser -k /dev/ttyACM0

# verify port is free
lsof /dev/ttyACM0  # should show nothing

# now test
python test_serial_raw.py
```

## Quick Test

Run the raw serial debugger to see exactly what's coming from the Arduino:

```bash
cd hardware/raspberry_pi
python test_serial_raw.py /dev/ttyACM0 9600
```

Then press the button on your Arduino multiple times. You should see:
- `🔘 BUTTON #1` - indicates button press was detected
- `🔐 ENC msg #1` - indicates encrypted message was sent

**Expected:** Button count = ENC msg count  
**If not:** Arduino code issue - check `button_demo.ino`

**If you see NOTHING:** Port conflict! Use `fix_serial.sh` above.

## What to Check

### 1. Port Conflict (Most Common!)

**Signs:**
- Script connects but receives NO data
- `lsof /dev/ttyACM0` shows another process
- Works when `screen` is closed

**Fix:** Kill all programs using the port (see Quick Fix above)

### 2. Verify Messages Are Being Sent

In `test_serial_raw.py` output, check:
- Do you see `ENC:` messages for every button press?
- Are there any `❓ UNKNOWN:` lines?
- Does `enc_msgs` count match `button_presses` count?

### 3. Check Arduino Code

The Arduino should send this format:
```
# BUTTON: pressed
ENC:2F3A4B5C6D...   (hex encoded data)
```

### 4. Check for Other Serial Issues

Common problems:
- **Baud rate mismatch** - verify both use 9600
- **Permission issues** - `sudo usermod -a -G dialout $USER`, then logout/login
- **Wrong port** - try `/dev/ttyACM1` or `/dev/ttyUSB0`

### 4. Live Demo Status Bar

When running `live_demo.py`, watch the status bar:

```
Status: READY  │  Proc: 5 │ Recv: 47  │  Queue: 0
```

- **Proc** = Successfully processed encrypted messages
- **Recv** = Total lines received from serial
- **Queue** = Messages waiting to be processed
- **Drop** = Messages lost (should be 0)

**If Recv > Proc:** Messages arriving but not being processed (format issue)  
**If Recv ≈ Proc:** Everything working!  
**If Recv << expected:** Serial reading issue

## How Data is Shown

The live demo now shows 4 clear stages:

1. **📱 Original Sensor Data (Before Encryption)**
   - Shows: `{"id":"ARDUINO_IOT_001","seq":5,"t":23.4,"h":58.2,"l":512}`
   - State: Plaintext JSON - readable

2. **🔒 Device Encrypted (Before Cloud Sees It)**
   - Shows: `2F3A4B5C6D7E...` (hex preview)
   - State: Kyber KEM + AES-GCM encrypted
   - Sensor data is now hidden

3. **🔐 Gateway Re-encrypted (Before Cloud Decrypts)**
   - Shows: `8A9BACDE0F1...` (hex preview)
   - State: Proxy re-encrypted for cloud
   - Gateway wrapped with cloud's key

4. **✅ Cloud Decrypted (After Processing)**
   - Shows: `{"id":"ARDUINO_IOT_001","seq":5,"t":23.4,"h":58.2,"l":512}`
   - State: Decrypted and verified ✓
   - Data matches original!

Each step stays visible for 0.3 seconds, and the final result stays on screen until the next button press.

## Changes Made

### Serial Reading (9600 baud optimized)
- ✅ Reads entire buffer at once (no data left behind)
- ✅ 0.5ms polling (was 1ms)
- ✅ Handles both `\n` and `\r\n` line endings
- ✅ 4096 byte OS buffers
- ✅ Non-blocking queue puts
- ✅ Tracks every line received

### Display
- ✅ Shows actual data at each step
- ✅ Results persist until next message
- ✅ Better event logging with emojis
- ✅ Debug info in status bar

## Troubleshooting

### "Still only 1 in 15 messages"

1. **Run test_serial_raw.py first**
   - This eliminates encryption/processing delays
   - If you see all messages here, issue is in live_demo.py
   - If you DON'T see all messages, issue is hardware/serial

2. **Check if screen is still running**
   ```bash
   ps aux | grep screen
   # kill any screen processes accessing the port
   ```

3. **Try different port**
   ```bash
   ls /dev/ttyACM* /dev/ttyUSB*
   # try each port
   ```

4. **Check Arduino Serial Monitor**
   - Open Arduino IDE
   - Tools → Serial Monitor (9600 baud)
   - Press button - do you see messages immediately?

5. **Increase buffer size on Arduino**
   In `button_demo.ino`:
   ```cpp
   Serial.begin(9600);
   Serial.setTimeout(100);  // add this
   ```

## Next Steps

1. Run `test_serial_raw.py` and press button 10 times
2. Check if all 10 messages are received
3. If yes → issue is in `live_demo.py` processing
4. If no → issue is in Arduino or serial connection

Share the output of `test_serial_raw.py` for further diagnosis!

