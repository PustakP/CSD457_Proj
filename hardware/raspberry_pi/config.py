"""
config.py - shared configuration for rpi services
"""
import os

# ---- serial config (arduino connection) ----
SERIAL_PORT = os.environ.get('SERIAL_PORT', '/dev/ttyACM0')  # or /dev/ttyUSB0
BAUD_RATE = 9600
SERIAL_TIMEOUT = 1.0

# ---- pre-shared key (must match arduino) ----
PSK = bytes([
    0x4B, 0x59, 0x42, 0x45, 0x52, 0x5F, 0x49, 0x4F,  # "KYBER_IO"
    0x54, 0x5F, 0x50, 0x53, 0x4B, 0x5F, 0x30, 0x31   # "T_PSK_01"
])

# ---- kyber config ----
KYBER_SECURITY_LEVEL = 512  # 512, 768, or 1024

# ---- network config (for future tcp comms) ----
GATEWAY_HOST = '0.0.0.0'
GATEWAY_PORT = 5000
CLOUD_HOST = '127.0.0.1'
CLOUD_PORT = 5001

# ---- logging ----
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FILE = '/tmp/iot_kyber.log'

# ---- data storage ----
DATA_DIR = os.path.expanduser('~/iot_kyber_data')
os.makedirs(DATA_DIR, exist_ok=True)

# ---- performance metrics ----
COLLECT_METRICS = True
METRICS_FILE = os.path.join(DATA_DIR, 'metrics.json')

# ---- display config ----
USE_COLORS = True
CLEAR_ON_UPDATE = False



