# Demo Day Quick Reference
## Button-Triggered Proxy Re-Encryption Demo

---

## 🚀 SUPER QUICK START

```bash
# 1. ssh into raspberry pi
ssh pi@raspberrypi.local

# 2. start demo
cd ~/iot_kyber && source venv/bin/activate && python live_demo.py

# 3. press button on arduino
# 4. watch the magic happen!
```

---

## 📋 PRE-DEMO CHECKLIST

- [ ] Arduino powered via USB to RPi
- [ ] Button connected: Pin 2 → Button → GND
- [ ] RPi connected to WiFi/Ethernet
- [ ] Know RPi IP address: `ping raspberrypi.local`
- [ ] Laptop connected to same network

---

## 🔌 WIRING (2 WIRES!)

```
Arduino Pin 2 ----[BUTTON]---- GND
Arduino USB-B ----[CABLE]----- RPi USB-A
```

**No button?** Just touch wire from Pin 2 to GND to trigger.

---

## 💻 SSH COMMANDS

```bash
# connect
ssh pi@raspberrypi.local
# password: (your password)

# run demo
cd ~/iot_kyber
source venv/bin/activate
python live_demo.py

# exit demo
Ctrl+C
```

---

## 🔧 TROUBLESHOOTING

| Problem | Fix |
|---------|-----|
| Can't SSH | `ping raspberrypi.local` - is RPi on? |
| Arduino not found | Replug USB, run `ls /dev/ttyACM*` |
| Permission denied | `sudo chmod 666 /dev/ttyACM0` |
| Import error | `source venv/bin/activate` |
| Colors broken | `export TERM=xterm-256color` |

---

## 📊 EXPECTED OUTPUT

When you press the button:
```
━━━ PROCESSING STEPS ━━━
 ✓ 1. Device Encrypt - kyber kem + aes-gcm
 ✓ 2. Gateway PRE - proxy re-encryption  
 ✓ 3. Cloud Decrypt - kyber decaps + aes
 ✓ 4. Complete - data secured!

━━━ PERFORMANCE METRICS ━━━
   Device Encryption:       4.52 ms
   Gateway PRE:             8.31 ms
   Cloud Decryption:        9.18 ms
   ─────────────────────────────
   Total Workflow:         22.01 ms
```

---

## 🎤 TALKING POINTS

1. **"CRYSTALS-Kyber"** - NIST-standardized post-quantum algorithm
2. **"Proxy Re-Encryption"** - Gateway transforms without seeing data
3. **"Fog Computing"** - Heavy crypto offloaded from constrained device
4. **"Quantum-Safe"** - Protects against future quantum attacks
5. **"Milliseconds"** - Fast enough for real-time IoT

---

## 🔢 KEY NUMBERS TO MENTION

| Metric | Value |
|--------|-------|
| Total workflow time | ~20-30 ms |
| Kyber-512 ciphertext | 768 bytes |
| NIST Security Level | Level 1 |
| Arduino RAM | 2KB (too small for Kyber!) |
| RPi handles | All heavy crypto |

---

## 🆘 EMERGENCY FIXES

```bash
# demo not starting
pip install kyber-py pycryptodome pyserial

# serial port issue
sudo chmod 666 /dev/ttyACM0

# kill stuck demo
Ctrl+C (press twice if needed)

# check arduino is sending
screen /dev/ttyACM0 9600
# Ctrl+A then K to exit
```

---

## 📝 SIMULATION MODE

No Arduino? Demo still works!
```bash
python live_demo.py
# says "arduino not found - using simulation mode"
# auto-triggers every 30 seconds
```

---

**Good luck with the demo! 🎉**
