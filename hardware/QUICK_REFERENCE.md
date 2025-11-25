# Quick Reference Card

## Raspberry Pi Commands

```bash
# activate environment
cd ~/iot_kyber && source venv/bin/activate

# run demos
python run_demo.py              # interactive menu
python run_demo.py --simulate   # no arduino needed
python run_demo.py --full       # run all automatically

# run dashboard
python dashboard.py --simulate

# run individual components
python fog_gateway.py --simulate
python cloud_server.py
```

## Arduino Commands

```bash
# check serial connection
ls /dev/tty*

# test serial (exit: Ctrl+A then K)
screen /dev/ttyACM0 9600

# send commands to arduino
echo "PING" > /dev/ttyACM0
echo "STATUS" > /dev/ttyACM0
```

## File Locations

```
~/iot_kyber/           # main code
~/iot_kyber/venv/      # python environment
~/iot_kyber_data/      # metrics and data
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Serial permission denied | `sudo chmod 666 /dev/ttyACM0` |
| Arduino not found | Check USB cable, try different port |
| Import error | `source venv/bin/activate` |
| Kyber slow | Normal for pure Python, ~5-20ms |

## Key Metrics

| Approach | Enc Time | Best For |
|----------|----------|----------|
| Full Kyber | ~8-15ms | Cloud/Gateway |
| Hybrid Kyber+AES | ~5-10ms | Capable IoT |
| Proxy RE | Varies | Constrained devices |

## Network Ports (if using sockets)

- Gateway: 5000
- Cloud: 5001



