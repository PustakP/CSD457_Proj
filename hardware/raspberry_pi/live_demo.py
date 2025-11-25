#!/usr/bin/env python3
"""
live_demo.py - ssh terminal demo with live updating display
button press -> proxy re-encryption -> crystals-kyber encryption
designed for headless rpi access via ssh

usage: python live_demo.py
"""
import serial
import time
import json
import sys
import os
import threading
from datetime import datetime
from collections import deque

# add parent dirs to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from kyber_py.kyber import Kyber512, Kyber768, Kyber1024
    from Crypto.Cipher import AES
    KYBER_AVAILABLE = True
except ImportError:
    KYBER_AVAILABLE = False
    print("[!] kyber-py not installed, run: pip install kyber-py pycryptodome")

try:
    from config import SERIAL_PORT, BAUD_RATE, PSK
except ImportError:
    SERIAL_PORT = '/dev/ttyACM0'
    BAUD_RATE = 9600
    PSK = b'KYBER_IOT_PSK_01'

# ---- ansi colors for terminal ----
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    
    BG_BLACK = '\033[40m'
    BG_GREEN = '\033[42m'
    BG_BLUE = '\033[44m'
    
    @staticmethod
    def disable():
        """disable colors for non-tty output"""
        Colors.RESET = Colors.BOLD = Colors.DIM = ''
        Colors.RED = Colors.GREEN = Colors.YELLOW = ''
        Colors.BLUE = Colors.MAGENTA = Colors.CYAN = Colors.WHITE = ''
        Colors.BG_BLACK = Colors.BG_GREEN = Colors.BG_BLUE = ''


def clear_screen():
    """clear terminal screen"""
    print('\033[2J\033[H', end='')


def move_cursor(row, col):
    """move cursor to position"""
    print(f'\033[{row};{col}H', end='')


def print_at(row, col, text):
    """print text at specific position"""
    move_cursor(row, col)
    print(text, end='', flush=True)


class LiveDemo:
    """
    live ssh terminal demo - shows pre + kyber workflow
    updates screen in real-time as button is pressed
    """
    
    def __init__(self, security_level=512):
        self.security_level = security_level
        self.kyber = Kyber512 if security_level == 512 else Kyber768 if security_level == 768 else Kyber1024
        
        # keys
        self.device_pk = None
        self.device_sk = None
        self.gateway_pk = None
        self.gateway_sk = None
        self.cloud_pk = None
        self.cloud_sk = None
        
        # serial
        self.serial = None
        self.running = False
        
        # stats
        self.total_messages = 0
        self.total_enc_time = 0
        self.total_dec_time = 0
        self.last_data = None
        self.event_log = deque(maxlen=8)
        
        # display state
        self.status = "initializing"
        self.step = 0
        
    def setup(self):
        """init all crypto keys and serial"""
        self.log_event("setting up cryptographic keys...")
        
        # gen all keypairs
        self.device_pk, self.device_sk = self.kyber.keygen()
        self.gateway_pk, self.gateway_sk = self.kyber.keygen()
        self.cloud_pk, self.cloud_sk = self.kyber.keygen()
        
        self.log_event(f"✓ kyber-{self.security_level} keys generated")
        
        # connect serial
        self.connect_serial()
        
    def connect_serial(self):
        """connect to arduino via serial"""
        ports_to_try = [SERIAL_PORT, '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0']
        
        for port in ports_to_try:
            try:
                self.serial = serial.Serial(port, BAUD_RATE, timeout=0.5)
                time.sleep(2)  # wait for arduino reset
                self.log_event(f"✓ connected to arduino on {port}")
                
                # send ping
                self.serial.write(b"PING\n")
                time.sleep(0.3)
                if self.serial.in_waiting:
                    resp = self.serial.readline().decode().strip()
                    self.log_event(f"  arduino: {resp}")
                return True
            except Exception as e:
                continue
        
        self.log_event("✗ arduino not found - using simulation mode")
        return False
    
    def log_event(self, msg):
        """add event to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.event_log.append(f"[{timestamp}] {msg}")
    
    def decrypt_device_msg(self, hex_data):
        """decrypt xor-encrypted data from arduino"""
        try:
            encrypted = bytes.fromhex(hex_data)
            decrypted = bytes(a ^ b for a, b in zip(encrypted, (PSK * ((len(encrypted) // len(PSK)) + 1))))
            return decrypted[:len(encrypted)]
        except:
            return None
    
    def do_proxy_reencryption(self, plaintext_data):
        """
        full pre + kyber workflow:
        1. device encrypts with device key
        2. gateway re-encrypts for cloud (pre)
        3. cloud decrypts
        """
        metrics = {}
        
        # step 1: device encryption
        self.step = 1
        self.draw_step_indicator()
        
        start = time.perf_counter()
        device_ss, device_ct = self.kyber.encaps(self.device_pk)
        aes_key = device_ss[:32]
        cipher = AES.new(aes_key, AES.MODE_GCM)
        msg_bytes = json.dumps(plaintext_data).encode() if isinstance(plaintext_data, dict) else plaintext_data.encode()
        device_aes_ct, device_tag = cipher.encrypt_and_digest(msg_bytes)
        device_nonce = cipher.nonce
        metrics['device_enc_ms'] = (time.perf_counter() - start) * 1000
        
        time.sleep(0.3)  # visual pause
        
        # step 2: gateway proxy re-encryption
        self.step = 2
        self.draw_step_indicator()
        
        start = time.perf_counter()
        # gateway encaps for cloud
        cloud_ss, cloud_ct = self.kyber.encaps(self.cloud_pk)
        cloud_aes_key = cloud_ss[:32]
        # re-wrap the device-encrypted data
        reenc_cipher = AES.new(cloud_aes_key, AES.MODE_GCM)
        combined = device_aes_ct + device_nonce + device_tag
        reenc_ct, reenc_tag = reenc_cipher.encrypt_and_digest(combined)
        reenc_nonce = reenc_cipher.nonce
        metrics['gateway_reenc_ms'] = (time.perf_counter() - start) * 1000
        
        time.sleep(0.3)
        
        # step 3: cloud decryption
        self.step = 3
        self.draw_step_indicator()
        
        start = time.perf_counter()
        # cloud decaps
        cloud_ss_dec = self.kyber.decaps(self.cloud_sk, cloud_ct)
        cloud_aes_key_dec = cloud_ss_dec[:32]
        # unwrap gateway layer
        dec_cipher = AES.new(cloud_aes_key_dec, AES.MODE_GCM, nonce=reenc_nonce)
        combined_dec = dec_cipher.decrypt_and_verify(reenc_ct, reenc_tag)
        # extract original components
        ct_len = len(combined_dec) - 16 - 16
        orig_ct = combined_dec[:ct_len]
        orig_nonce = combined_dec[ct_len:ct_len+16]
        orig_tag = combined_dec[ct_len+16:]
        # device decaps
        device_ss_dec = self.kyber.decaps(self.device_sk, device_ct)
        device_aes_key_dec = device_ss_dec[:32]
        # final decrypt
        final_cipher = AES.new(device_aes_key_dec, AES.MODE_GCM, nonce=orig_nonce)
        final_plaintext = final_cipher.decrypt_and_verify(orig_ct, orig_tag)
        metrics['cloud_dec_ms'] = (time.perf_counter() - start) * 1000
        
        metrics['total_ms'] = metrics['device_enc_ms'] + metrics['gateway_reenc_ms'] + metrics['cloud_dec_ms']
        metrics['kyber_ct_size'] = len(device_ct)
        metrics['reenc_ct_size'] = len(cloud_ct) + len(reenc_ct)
        
        # step 4: complete
        self.step = 4
        self.draw_step_indicator()
        
        return final_plaintext, metrics
    
    def draw_header(self):
        """draw header section"""
        clear_screen()
        c = Colors
        
        # title box
        print(f"{c.BOLD}{c.CYAN}╔══════════════════════════════════════════════════════════════════════╗{c.RESET}")
        print(f"{c.BOLD}{c.CYAN}║   {c.WHITE}QUANTUM-SAFE IOT DEMO  {c.YELLOW}│  {c.GREEN}CRYSTALS-KYBER + PROXY RE-ENCRYPTION{c.CYAN}   ║{c.RESET}")
        print(f"{c.BOLD}{c.CYAN}╚══════════════════════════════════════════════════════════════════════╝{c.RESET}")
        print()
        
        # architecture
        print(f"{c.DIM}Architecture: Arduino → [USB Serial] → Raspberry Pi → [Kyber PRE] → Cloud{c.RESET}")
        print(f"{c.DIM}Security Level: CRYSTALS-Kyber-{self.security_level} (NIST PQC Standard){c.RESET}")
        print()
        
    def draw_workflow(self):
        """draw workflow diagram"""
        c = Colors
        row = 8
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ DATA FLOW ━━━{c.RESET}")
        row += 1
        
        # workflow boxes
        print_at(row, 1, f"┌────────────────┐     ┌────────────────┐     ┌────────────────┐")
        row += 1
        print_at(row, 1, f"│{c.YELLOW}  ARDUINO/IOT   {c.RESET}│ ──▶ │{c.CYAN}  FOG GATEWAY   {c.RESET}│ ──▶ │{c.GREEN}  CLOUD SERVER  {c.RESET}│")
        row += 1
        print_at(row, 1, f"│{c.DIM}  Button Press  {c.RESET}│     │{c.DIM}  Raspberry Pi  {c.RESET}│     │{c.DIM}  (Simulated)   {c.RESET}│")
        row += 1
        print_at(row, 1, f"└────────────────┘     └────────────────┘     └────────────────┘")
        row += 1
        print_at(row, 1, f"{c.DIM}   XOR + PSK enc         Kyber encaps         Kyber decaps    {c.RESET}")
        row += 2
        
    def draw_step_indicator(self):
        """draw current processing step"""
        c = Colors
        row = 16
        
        steps = [
            ("1. Device Encrypt", "kyber kem + aes-gcm"),
            ("2. Gateway PRE", "proxy re-encryption"),
            ("3. Cloud Decrypt", "kyber decaps + aes"),
            ("4. Complete", "data secured!")
        ]
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ PROCESSING STEPS ━━━{c.RESET}")
        row += 1
        
        for i, (name, desc) in enumerate(steps):
            if i + 1 < self.step:
                # completed
                symbol = f"{c.GREEN}✓{c.RESET}"
                color = c.GREEN
            elif i + 1 == self.step:
                # current
                symbol = f"{c.YELLOW}▶{c.RESET}"
                color = c.YELLOW + c.BOLD
            else:
                # pending
                symbol = f"{c.DIM}○{c.RESET}"
                color = c.DIM
            
            print_at(row, 3, f"{symbol} {color}{name}{c.RESET} {c.DIM}- {desc}{c.RESET}          ")
            row += 1
        
    def draw_metrics(self, metrics=None):
        """draw performance metrics"""
        c = Colors
        row = 22
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ PERFORMANCE METRICS ━━━{c.RESET}")
        row += 1
        
        if metrics:
            print_at(row, 3, f"Device Encryption:    {c.CYAN}{metrics['device_enc_ms']:>8.2f} ms{c.RESET}")
            row += 1
            print_at(row, 3, f"Gateway PRE:          {c.CYAN}{metrics['gateway_reenc_ms']:>8.2f} ms{c.RESET}")
            row += 1
            print_at(row, 3, f"Cloud Decryption:     {c.CYAN}{metrics['cloud_dec_ms']:>8.2f} ms{c.RESET}")
            row += 1
            print_at(row, 3, f"─────────────────────────────")
            row += 1
            print_at(row, 3, f"Total Workflow:       {c.GREEN}{c.BOLD}{metrics['total_ms']:>8.2f} ms{c.RESET}")
            row += 1
            print_at(row, 3, f"Kyber CT Size:        {c.MAGENTA}{metrics['kyber_ct_size']:>8} bytes{c.RESET}")
            row += 1
        else:
            print_at(row, 3, f"{c.DIM}Waiting for button press...{c.RESET}              ")
            for i in range(6):
                row += 1
                print_at(row, 3, "                                            ")
    
    def draw_data(self, data=None):
        """draw sensor data"""
        c = Colors
        row = 31
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ SENSOR DATA (Decrypted) ━━━{c.RESET}")
        row += 1
        
        if data:
            print_at(row, 3, f"Device ID:    {c.YELLOW}{data.get('id', 'unknown')}{c.RESET}          ")
            row += 1
            print_at(row, 3, f"Temperature:  {c.RED}{data.get('t', '?'):>6.1f} °C{c.RESET}     ")
            row += 1
            print_at(row, 3, f"Humidity:     {c.BLUE}{data.get('h', '?'):>6.1f} %{c.RESET}      ")
            row += 1
            print_at(row, 3, f"Light:        {c.YELLOW}{data.get('l', '?'):>6} lux{c.RESET}    ")
            row += 1
            print_at(row, 3, f"Sequence:     {c.DIM}#{data.get('seq', 0)}{c.RESET}              ")
        else:
            for i in range(5):
                print_at(row, 3, "                                            ")
                row += 1
    
    def draw_event_log(self):
        """draw event log"""
        c = Colors
        row = 38
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ EVENT LOG ━━━{c.RESET}")
        row += 1
        
        for i, event in enumerate(list(self.event_log)[-6:]):
            print_at(row, 3, f"{c.DIM}{event}{c.RESET}".ljust(70))
            row += 1
    
    def draw_status(self):
        """draw status bar"""
        c = Colors
        row = 45
        
        status_color = c.GREEN if self.status == "ready" else c.YELLOW if self.status == "processing" else c.CYAN
        
        print_at(row, 1, f"{'─' * 72}")
        row += 1
        print_at(row, 1, f"{c.BOLD}Status:{c.RESET} {status_color}{self.status.upper()}{c.RESET}  │  "
                        f"Messages: {c.CYAN}{self.total_messages}{c.RESET}  │  "
                        f"Avg Time: {c.GREEN}{self.total_enc_time / max(1, self.total_messages):.2f}ms{c.RESET}  │  "
                        f"{c.DIM}Press Ctrl+C to exit{c.RESET}")
    
    def draw_full(self, metrics=None, data=None):
        """draw full screen"""
        self.draw_header()
        self.draw_workflow()
        self.draw_step_indicator()
        self.draw_metrics(metrics)
        self.draw_data(data)
        self.draw_event_log()
        self.draw_status()
        sys.stdout.flush()
    
    def process_message(self, hex_data):
        """process incoming encrypted message"""
        self.status = "processing"
        self.step = 0
        self.draw_status()
        
        # decrypt xor layer from arduino
        decrypted = self.decrypt_device_msg(hex_data)
        if not decrypted:
            self.log_event("✗ failed to decrypt device data")
            return
        
        try:
            data = json.loads(decrypted.decode())
        except:
            self.log_event("✗ invalid json from device")
            return
        
        self.log_event(f"→ received: temp={data.get('t')}°C, humid={data.get('h')}%")
        
        # do full pre + kyber workflow
        final_plaintext, metrics = self.do_proxy_reencryption(data)
        
        # verify
        final_data = json.loads(final_plaintext.decode())
        if final_data == data:
            self.log_event(f"✓ proxy re-encryption successful! ({metrics['total_ms']:.1f}ms)")
        else:
            self.log_event("✗ data integrity check failed!")
        
        # update stats
        self.total_messages += 1
        self.total_enc_time += metrics['total_ms']
        self.last_data = data
        
        # update display
        self.status = "ready"
        self.draw_full(metrics, data)
    
    def simulate_button_press(self):
        """simulate a button press for testing"""
        import random
        
        data = {
            'id': 'SIM_ARDUINO_001',
            'seq': self.total_messages,
            't': round(22 + random.uniform(-3, 3), 1),
            'h': round(55 + random.uniform(-10, 10), 1),
            'l': int(500 + random.uniform(-200, 200)),
            'ts': int(time.time() * 1000)
        }
        
        # simulate xor enc
        msg_bytes = json.dumps(data).encode()
        encrypted = bytes(a ^ b for a, b in zip(msg_bytes, (PSK * ((len(msg_bytes) // len(PSK)) + 1))))
        
        return encrypted[:len(msg_bytes)].hex().upper()
    
    def run(self):
        """main loop"""
        if not KYBER_AVAILABLE:
            print("Error: kyber-py not available")
            return
        
        self.setup()
        self.status = "ready"
        self.running = True
        
        # initial draw
        self.draw_full()
        self.log_event("system ready - press button on arduino")
        self.draw_event_log()
        self.draw_status()
        
        sim_mode = self.serial is None
        last_sim = 0
        
        try:
            while self.running:
                # check serial for arduino data
                if self.serial and self.serial.in_waiting:
                    line = self.serial.readline().decode().strip()
                    
                    if line.startswith('ENC:'):
                        hex_data = line[4:]
                        self.process_message(hex_data)
                    elif line.startswith('#'):
                        self.log_event(f"arduino: {line[2:]}")
                        self.draw_event_log()
                        self.draw_status()
                    elif line.startswith('PONG:'):
                        self.log_event(f"arduino online: {line[5:]}")
                        self.draw_event_log()
                        self.draw_status()
                
                # simulation mode - press 's' to simulate
                if sim_mode:
                    # check for simulated trigger (every 10s or manual)
                    now = time.time()
                    if now - last_sim > 30:
                        last_sim = now
                        self.log_event("simulation: auto-trigger (every 30s)")
                        self.draw_event_log()
                        hex_data = self.simulate_button_press()
                        self.process_message(hex_data)
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            if self.serial:
                self.serial.close()
            
            # cleanup
            print()
            move_cursor(48, 1)
            print(f"\n{Colors.CYAN}Demo ended. Total messages: {self.total_messages}{Colors.RESET}")
            if self.total_messages > 0:
                print(f"Average processing time: {self.total_enc_time / self.total_messages:.2f}ms")
            print()


def main():
    """entry point"""
    # check if running in tty
    if not sys.stdout.isatty():
        Colors.disable()
    
    print("\n" + "=" * 60)
    print("  QUANTUM-SAFE IOT DEMO - LIVE SSH TERMINAL")
    print("  Press button on Arduino to trigger encryption workflow")
    print("=" * 60 + "\n")
    
    # check args
    security_level = 512
    if '--768' in sys.argv:
        security_level = 768
    elif '--1024' in sys.argv:
        security_level = 1024
    
    demo = LiveDemo(security_level=security_level)
    
    input("Press Enter to start demo...")
    
    demo.run()


if __name__ == '__main__':
    main()

