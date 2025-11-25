#!/bin/bash
# fix_serial.sh - kill all procs using serial port
# auto-detects arduino port if not specified

# auto-detect arduino port (most recently modified = active)
if [ -z "$1" ]; then
    # find most recent arduino port
    PORT=$(ls -t /dev/ttyACM* /dev/ttyUSB* 2>/dev/null | head -n1)
    if [ -z "$PORT" ]; then
        echo "✗ no arduino ports found"
        echo "available ports:"
        ls -la /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "  none found"
        exit 1
    fi
    echo "✓ auto-detected arduino: $PORT"
else
    PORT="$1"
fi

echo "=== serial port diagnostic & fix ==="
echo "port: $PORT"
echo ""

# chk if port exists
if [ ! -e "$PORT" ]; then
    echo "✗ port $PORT not found"
    echo "available ports:"
    ls -la /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "  none found"
    exit 1
fi

echo "✓ port exists"
ls -l "$PORT"
echo ""

# chk for procs using port
echo "checking for processes using port..."
PROCS=$(lsof "$PORT" 2>/dev/null)
if [ -n "$PROCS" ]; then
    echo "⚠ found processes using port:"
    echo "$PROCS"
    echo ""
    echo "killing these processes..."
    # kill screen sessions
    sudo pkill -9 screen 2>/dev/null && echo "  ✓ killed screen sessions"
    # kill python using port
    sudo fuser -k "$PORT" 2>/dev/null && echo "  ✓ killed processes on port"
    sleep 1
else
    echo "✓ no processes found using port"
fi

echo ""
echo "final status:"
lsof "$PORT" 2>/dev/null || echo "✓ port is free"
echo ""
echo "you can now run test_serial_raw.py or live_demo.py"

