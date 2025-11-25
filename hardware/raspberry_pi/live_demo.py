#!/usr/bin/env python3
"""
live_demo.py - ssh terminal demo with live updating display
button press -> proxy re-encryption -> crystals-kyber encryption
designed for headless rpi access via ssh

optimized for 9600 baud serial:
- aggressive serial buffering (reads all avail bytes immediately)
- persistent display (completed results stay visible)
- threaded serial reader prevents msg loss during processing
- tracks recv vs processed msg ratio for debugging
- auto-detects arduino port (/dev/ttyACM* or /dev/ttyUSB*)

usage: python live_demo.py [--768|--1024] [--debug]
  --768, --1024 : use kyber-768 or kyber-1024 (default: 512)
  --debug       : enable verbose logging (shows raw serial msgs)
"""
import serial
import time
import json
import sys
import os
import threading
import queue
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


def print_at(row, col, text, clear_line=False):
    """print text at specific position"""
    move_cursor(row, col)
    if clear_line:
        print('\033[K', end='')  # clear from cursor to end of line
    print(text, end='', flush=True)


class LiveDemo:
    """
    live ssh terminal demo - shows pre + kyber workflow
    updates screen in real-time as button is pressed
    """
    
    def __init__(self, security_level=512, debug=False):
        self.security_level = security_level
        self.kyber = Kyber512 if security_level == 512 else Kyber768 if security_level == 768 else Kyber1024
        self.debug = debug  # enable verbose logging
        
        # debug log file (so we can see what's happening even with ui updates)
        if debug:
            self.debug_log = open('/tmp/live_demo_debug.log', 'w')
            self.debug_log.write(f"=== live_demo debug log started ===\n")
            self.debug_log.flush()
        else:
            self.debug_log = None
        
        # keys
        self.device_pk = None
        self.device_sk = None
        self.gateway_pk = None
        self.gateway_sk = None
        self.cloud_pk = None
        self.cloud_sk = None
        
        # serial w/ threaded reader - prevents msg loss during processing
        self.serial = None
        self.serial_lock = threading.Lock()
        self.running = True  # set true before serial thread starts to prevent msg loss
        self.msg_queue = queue.Queue(maxsize=100)  # larger queue for burst msgs
        self.serial_thread = None
        
        # stats
        self.total_messages = 0
        self.total_enc_time = 0
        self.total_dec_time = 0
        self.last_data = None
        self.event_log = deque(maxlen=10)  # more events for demo
        self.dropped_messages = 0  # track msg loss
        self.serial_lines_received = 0  # total lines from serial (for debugging)
        
        # display state
        self.status = "initializing"
        self.step = 0
        self.last_metrics = None  # keep last result visible
        
        # content display - shows actual data at each step w/ full details for demo
        self.step_content = {
            1: {"label": "Plaintext JSON", "data": "", "size": 0, "hex": "", "desc": ""},
            2: {"label": "Kyber Ciphertext", "data": "", "size": 0, "hex": "", "desc": ""},
            3: {"label": "Re-encrypted CT", "data": "", "size": 0, "hex": "", "desc": ""},
            4: {"label": "Decrypted Result", "data": "", "size": 0, "hex": "", "desc": ""}
        }
        
        # raw plaintext for display
        self.current_plaintext = ""
        
        # display width for hex preview
        self.hex_preview_width = 64
        
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
        
    def auto_detect_arduino_port(self):
        """auto-detect active arduino port by scanning /dev/ttyACM* and /dev/ttyUSB*"""
        import glob
        
        # scan for all potential arduino ports
        potential_ports = []
        for pattern in ['/dev/ttyACM*', '/dev/ttyUSB*']:
            potential_ports.extend(glob.glob(pattern))
        
        if not potential_ports:
            return None
        
        # sort by modification time (most recent first) - active port usually changes more recently
        potential_ports.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        
        return potential_ports
    
    def connect_serial(self):
        """connect to arduino via serial w/ auto-detection"""
        # auto-detect arduino ports first
        detected_ports = self.auto_detect_arduino_port()
        if detected_ports:
            self.log_event(f"detected arduino ports: {', '.join(detected_ports)}")
            ports_to_try = detected_ports + [SERIAL_PORT]
        else:
            ports_to_try = [SERIAL_PORT, '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0']
        
        for port in ports_to_try:
            try:
                # longer timeout for 9600 baud, larger buffers to prevent msg loss
                self.serial = serial.Serial(
                    port, 
                    BAUD_RATE, 
                    timeout=1.0,  # longer timeout for reliable reads at 9600 baud
                    write_timeout=1.0,
                    inter_byte_timeout=0.1,
                    exclusive=True  # fail if port already open (e.g. by screen)
                )
                # increase os buffer sizes if possible
                try:
                    self.serial.set_buffer_size(rx_size=4096, tx_size=4096)
                except:
                    pass
                
                time.sleep(2)  # wait for arduino reset
                self.log_event(f"✓ connected to arduino on {port} @ {BAUD_RATE} baud")
                
                # flush any stale data from buffer
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()
                
                # send ping
                self.serial.write(b"PING\n")
                time.sleep(0.3)
                if self.serial.in_waiting:
                    resp = self.serial.readline().decode().strip()
                    self.log_event(f"  arduino: {resp}")
                
                # start threaded reader - prevents msg loss during processing
                self.serial_thread = threading.Thread(target=self._serial_reader, daemon=True)
                self.serial_thread.start()
                self.log_event("✓ serial reader thread started")
                return True
            except Exception as e:
                continue
        
        self.log_event("✗ arduino not found - using simulation mode")
        return False
    
    def _serial_reader(self):
        """bg thread - continuously reads serial, queues msgs - aggressive for 9600 baud"""
        buffer = ""
        error_count = 0
        while self.running:
            try:
                if self.serial:
                    # check for data without lock first (faster)
                    if self.serial.in_waiting > 0:
                        with self.serial_lock:
                            # read ALL available bytes immediately - prevents buffer overflow
                            bytes_waiting = self.serial.in_waiting
                            if bytes_waiting > 0:
                                chunk = self.serial.read(bytes_waiting).decode('utf-8', errors='ignore')
                                buffer += chunk
                                
                                # process all complete lines from buffer
                                while '\n' in buffer or '\r' in buffer:
                                    # handle both \n and \r\n line endings
                                    if '\r\n' in buffer:
                                        line, buffer = buffer.split('\r\n', 1)
                                    elif '\n' in buffer:
                                        line, buffer = buffer.split('\n', 1)
                                    else:
                                        line, buffer = buffer.split('\r', 1)
                                    
                                    line = line.strip()
                                    if line:
                                        self.serial_lines_received += 1  # count every line
                                        # immediate debug logging
                                        if self.debug:
                                            msg = f"[SERIAL_RX #{self.serial_lines_received}] {line[:80]}\n"
                                            if self.debug_log:
                                                self.debug_log.write(msg)
                                                self.debug_log.flush()
                                        try:
                                            self.msg_queue.put(line, block=False)
                                            error_count = 0  # reset error count on success
                                            if self.debug and self.debug_log:
                                                self.debug_log.write(f"  → queued (qsize={self.msg_queue.qsize()})\n")
                                                self.debug_log.flush()
                                        except queue.Full:
                                            self.dropped_messages += 1
                                            if self.debug and self.debug_log:
                                                self.debug_log.write(f"  ✗ QUEUE FULL (dropped)\n")
                                                self.debug_log.flush()
                        
                        # if buffer is getting too large, truncate it (corrupted data)
                        if len(buffer) > 512:
                            buffer = buffer[-256:]  # keep last 256 chars
            except Exception as e:
                error_count += 1
                if error_count < 5:  # only log first few errors
                    pass  # silently ignore to not spam
                time.sleep(0.01)  # back off on error
            
            time.sleep(0.0005)  # 0.5ms polling - very aggressive for 9600 baud
    
    def log_event(self, msg):
        """add event to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.event_log.append(f"[{timestamp}] {msg}")
    
    def decrypt_device_msg(self, hex_data):
        """decrypt xor-encrypted data from arduino"""
        try:
            if self.debug and self.debug_log:
                self.debug_log.write(f"[DECRYPT] hex_data={hex_data[:60]}...\n")
                self.debug_log.write(f"[DECRYPT] PSK={PSK.hex()}\n")
                self.debug_log.flush()
            encrypted = bytes.fromhex(hex_data)
            if self.debug and self.debug_log:
                self.debug_log.write(f"[DECRYPT] encrypted len={len(encrypted)}\n")
                self.debug_log.flush()
            decrypted = bytes(a ^ b for a, b in zip(encrypted, (PSK * ((len(encrypted) // len(PSK)) + 1))))
            if self.debug and self.debug_log:
                self.debug_log.write(f"[DECRYPT] decrypted={decrypted[:60]}\n")
                self.debug_log.flush()
            return decrypted[:len(encrypted)]
        except Exception as e:
            if self.debug and self.debug_log:
                self.debug_log.write(f"[DECRYPT] ✗ ERROR: {type(e).__name__}: {e}\n")
                self.debug_log.flush()
            self.log_event(f"✗ decrypt error: {type(e).__name__}: {str(e)[:30]}")
            self.draw_event_log()
            return None
    
    def truncate_hex(self, data, max_len=32):
        """truncate hex str for display w/ ellipsis"""
        hex_str = data.hex().upper() if isinstance(data, bytes) else str(data).upper()
        if len(hex_str) > max_len:
            return hex_str[:max_len] + "..."
        return hex_str
    
    def do_proxy_reencryption(self, plaintext_data):
        """
        full pre + kyber workflow:
        1. device encrypts with device key
        2. gateway re-encrypts for cloud (pre)
        3. cloud decrypts
        """
        metrics = {}
        msg_bytes = json.dumps(plaintext_data).encode() if isinstance(plaintext_data, dict) else plaintext_data.encode()
        
        # step 1: device encryption
        self.step = 1
        self.status = "processing: device encrypt"
        plaintext_str = msg_bytes.decode()
        self.step_content[1] = {
            "label": "📱 IOT Device - Original Sensor Data",
            "data": plaintext_str,
            "size": len(msg_bytes),
            "hex": self.truncate_hex(msg_bytes, 48),
            "desc": "unencrypted json from arduino"
        }
        self.draw_step_indicator()  # just update step indicator
        self.draw_step_content()     # just update content area
        self.draw_status()  # update status bar
        sys.stdout.flush()
        
        start = time.perf_counter()
        device_ss, device_ct = self.kyber.encaps(self.device_pk)
        aes_key = device_ss[:32]
        cipher = AES.new(aes_key, AES.MODE_GCM)
        device_aes_ct, device_tag = cipher.encrypt_and_digest(msg_bytes)
        device_nonce = cipher.nonce
        metrics['device_enc_ms'] = (time.perf_counter() - start) * 1000
        
        time.sleep(0.2)  # shorter visual pause for responsiveness
        
        # step 2: gateway proxy re-encryption
        self.step = 2
        self.status = "processing: gateway pre"
        combined_ct = device_ct + device_aes_ct
        self.step_content[2] = {
            "label": "🔐 Device Kyber Encrypted",
            "data": f"Kyber-{self.security_level} KEM ciphertext + AES-GCM payload",
            "size": len(combined_ct),
            "hex": self.truncate_hex(combined_ct[:24], 48),
            "desc": f"kem_ct({len(device_ct)}B) + aes_ct({len(device_aes_ct)}B)"
        }
        self.draw_step_indicator()
        self.draw_step_content()
        self.draw_status()  # update status bar
        sys.stdout.flush()
        
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
        
        time.sleep(0.2)
        
        # step 3: cloud decryption
        self.step = 3
        self.status = "processing: cloud decrypt"
        full_reenc = cloud_ct + reenc_ct
        self.step_content[3] = {
            "label": "🌐 Gateway PRE - Re-encrypted for Cloud",
            "data": f"Proxy re-encrypted with cloud's public key",
            "size": len(full_reenc),
            "hex": self.truncate_hex(full_reenc[:24], 48),
            "desc": f"cloud_kem({len(cloud_ct)}B) + wrapped({len(reenc_ct)}B)"
        }
        self.draw_step_indicator()
        self.draw_step_content()
        self.draw_status()  # update status bar
        sys.stdout.flush()
        
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
        
        time.sleep(0.15)
        
        metrics['total_ms'] = metrics['device_enc_ms'] + metrics['gateway_reenc_ms'] + metrics['cloud_dec_ms']
        metrics['kyber_ct_size'] = len(device_ct)
        metrics['reenc_ct_size'] = len(cloud_ct) + len(reenc_ct)
        
        # step 4: complete - show decrypted result (this stays visible!)
        self.step = 4
        self.status = "processing: verifying"
        decrypted_str = final_plaintext.decode()
        self.step_content[4] = {
            "label": "✅ Cloud Server - Decrypted & Verified",
            "data": decrypted_str,
            "size": len(final_plaintext),
            "hex": "✓ INTEGRITY VERIFIED",
            "desc": "data matches original plaintext"
        }
        self.draw_step_indicator()
        self.draw_step_content()
        self.draw_status()  # update status bar
        sys.stdout.flush()
        
        time.sleep(0.2)
        
        # result stays on screen until next message
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
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ DATA FLOW ━━━{c.RESET}".ljust(72), clear_line=True)
        row += 1
        
        # workflow boxes
        print_at(row, 1, f"┌────────────────┐     ┌────────────────┐     ┌────────────────┐".ljust(72), clear_line=True)
        row += 1
        print_at(row, 1, f"│{c.YELLOW}  ARDUINO/IOT   {c.RESET}│ ──▶ │{c.CYAN}  FOG GATEWAY   {c.RESET}│ ──▶ │{c.GREEN}  CLOUD SERVER  {c.RESET}│".ljust(72), clear_line=True)
        row += 1
        print_at(row, 1, f"│{c.DIM}  Button Press  {c.RESET}│     │{c.DIM}  Raspberry Pi  {c.RESET}│     │{c.DIM}  (Simulated)   {c.RESET}│".ljust(72), clear_line=True)
        row += 1
        print_at(row, 1, f"└────────────────┘     └────────────────┘     └────────────────┘".ljust(72), clear_line=True)
        row += 1
        print_at(row, 1, f"{c.DIM}   XOR + PSK enc         Kyber encaps         Kyber decaps    {c.RESET}".ljust(72), clear_line=True)
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
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ PROCESSING STEPS ━━━{c.RESET}".ljust(72), clear_line=True)
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
            
            print_at(row, 3, f"{symbol} {color}{name}{c.RESET} {c.DIM}- {desc}{c.RESET}".ljust(72), clear_line=True)
            row += 1
    
    def draw_step_content(self):
        """draw content being processed at each step - verbose for demo"""
        c = Colors
        row = 21
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ DATA TRANSFORMATION (Live View) ━━━{c.RESET}".ljust(72), clear_line=True)
        row += 1
        
        for i in range(1, 5):
            content = self.step_content.get(i, {})
            label = content.get("label", f"Step {i}")
            data = content.get("data", "")
            size = content.get("size", 0)
            hex_preview = content.get("hex", "")
            desc = content.get("desc", "")
            
            if i < self.step:
                # completed step - dim
                color = c.DIM
                indicator = "✓"
            elif i == self.step:
                # current step - highlighted
                color = c.YELLOW + c.BOLD
                indicator = "▶"
            else:
                # pending - very dim
                color = c.DIM
                indicator = "○"
                data = "waiting..."
                hex_preview = ""
                size = 0
                desc = ""
            
            # line 1: step label w/ size
            size_str = f"({size} bytes)" if size > 0 else ""
            print_at(row, 1, f"  {color}{indicator} {label} {size_str}{c.RESET}".ljust(72), clear_line=True)
            row += 1
            
            # line 2+: show data content prominently for demo
            if data and i <= self.step:
                if i == 1:
                    # plaintext json - show full readable text (before encryption)
                    display_data = data if len(data) <= 50 else data[:47] + "..."
                    print_at(row, 1, f"    {c.CYAN}📄 Raw JSON: {display_data}{c.RESET}".ljust(72), clear_line=True)
                    row += 1
                    print_at(row, 1, f"    {c.DIM}(readable plaintext before encryption){c.RESET}".ljust(72), clear_line=True)
                elif i == 2:
                    # encrypted - show hex preview and explain what's encrypted
                    print_at(row, 1, f"    {c.MAGENTA}🔒 Encrypted: {hex_preview}{c.RESET}".ljust(72), clear_line=True)
                    row += 1
                    print_at(row, 1, f"    {c.DIM}{desc} (sensor data now hidden){c.RESET}".ljust(72), clear_line=True)
                elif i == 3:
                    # re-encrypted - show hex preview
                    print_at(row, 1, f"    {c.MAGENTA}🔐 Re-encrypted: {hex_preview}{c.RESET}".ljust(72), clear_line=True)
                    row += 1
                    print_at(row, 1, f"    {c.DIM}{desc} (gateway wrapped for cloud){c.RESET}".ljust(72), clear_line=True)
                elif i == 4:
                    # final decrypted - show full readable text in green
                    display_data = data if len(data) <= 50 else data[:47] + "..."
                    print_at(row, 1, f"    {c.GREEN}✅ {hex_preview}{c.RESET}".ljust(72), clear_line=True)
                    row += 1
                    print_at(row, 1, f"    {c.GREEN}📄 Restored: {display_data}{c.RESET}".ljust(72), clear_line=True)
            else:
                print_at(row, 1, " " * 72, clear_line=True)
                row += 1
                print_at(row, 1, " " * 72, clear_line=True)
            row += 1
            
            # spacing between steps
            if i < 4:
                print_at(row, 1, f"  {c.DIM}│{c.RESET}".ljust(72), clear_line=True)
                row += 1
        
        sys.stdout.flush()
        
    def draw_metrics(self, metrics=None):
        """draw performance metrics"""
        c = Colors
        row = 40
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ PERFORMANCE METRICS ━━━{c.RESET}".ljust(72), clear_line=True)
        row += 1
        
        if metrics:
            print_at(row, 1, f"  Device Encryption:    {c.CYAN}{metrics['device_enc_ms']:>8.2f} ms{c.RESET}".ljust(72), clear_line=True)
            row += 1
            print_at(row, 1, f"  Gateway PRE:          {c.CYAN}{metrics['gateway_reenc_ms']:>8.2f} ms{c.RESET}".ljust(72), clear_line=True)
            row += 1
            print_at(row, 1, f"  Cloud Decryption:     {c.CYAN}{metrics['cloud_dec_ms']:>8.2f} ms{c.RESET}".ljust(72), clear_line=True)
            row += 1
            print_at(row, 1, f"  ─────────────────────────────".ljust(72), clear_line=True)
            row += 1
            print_at(row, 1, f"  Total Workflow:       {c.GREEN}{c.BOLD}{metrics['total_ms']:>8.2f} ms{c.RESET}".ljust(72), clear_line=True)
            row += 1
            print_at(row, 1, f"  Kyber CT Size:        {c.MAGENTA}{metrics['kyber_ct_size']:>8} bytes{c.RESET}".ljust(72), clear_line=True)
            row += 1
        else:
            print_at(row, 1, f"  {c.DIM}Waiting for button press...{c.RESET}".ljust(72), clear_line=True)
            for i in range(6):
                row += 1
                print_at(row, 1, " " * 72, clear_line=True)
    
    def draw_data(self, data=None):
        """draw sensor data"""
        c = Colors
        row = 48
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ SENSOR DATA (Decrypted) ━━━{c.RESET}".ljust(72), clear_line=True)
        row += 1
        
        if data:
            print_at(row, 1, f"  Device ID:    {c.YELLOW}{data.get('id', 'unknown')}{c.RESET}".ljust(72), clear_line=True)
            row += 1
            print_at(row, 1, f"  Temperature:  {c.RED}{data.get('t', '?'):>6.1f} °C{c.RESET}".ljust(72), clear_line=True)
            row += 1
            print_at(row, 1, f"  Humidity:     {c.BLUE}{data.get('h', '?'):>6.1f} %{c.RESET}".ljust(72), clear_line=True)
            row += 1
            print_at(row, 1, f"  Light:        {c.YELLOW}{data.get('l', '?'):>6} lux{c.RESET}".ljust(72), clear_line=True)
            row += 1
            print_at(row, 1, f"  Sequence:     {c.DIM}#{data.get('seq', 0)}{c.RESET}".ljust(72), clear_line=True)
        else:
            for i in range(5):
                print_at(row, 1, " " * 72, clear_line=True)
                row += 1
    
    def draw_event_log(self):
        """draw event log"""
        c = Colors
        row = 53
        
        print_at(row, 1, f"{c.BOLD}{c.WHITE}━━━ EVENT LOG ━━━{c.RESET}".ljust(72), clear_line=True)
        row += 1
        
        # show last 7 events for better demo visibility
        recent_events = list(self.event_log)[-7:]
        for i, event in enumerate(recent_events):
            # truncate event if too long
            event_text = event if len(event) <= 68 else event[:65] + "..."
            print_at(row, 1, f"  {c.DIM}{event_text}{c.RESET}".ljust(72), clear_line=True)
            row += 1
        
        # clear extra lines
        for _ in range(7 - len(recent_events)):
            print_at(row, 1, " " * 72, clear_line=True)
            row += 1
    
    def draw_status(self):
        """draw status bar"""
        c = Colors
        row = 62
        
        # determine status color
        if "ready" in self.status.lower():
            status_color = c.GREEN
        elif "processing" in self.status.lower():
            status_color = c.YELLOW
        else:
            status_color = c.CYAN
        
        print_at(row, 1, f"{'─' * 72}".ljust(72), clear_line=True)
        row += 1
        
        # show queue status and dropped msg warning
        queue_size = self.msg_queue.qsize()
        queue_str = f"{c.YELLOW}Queue: {queue_size}{c.RESET}" if queue_size > 5 else f"{c.DIM}Queue: {queue_size}{c.RESET}"
        
        dropped_str = ""
        if self.dropped_messages > 0:
            dropped_str = f" {c.RED}│ Drop: {self.dropped_messages}{c.RESET}"
        
        # show serial recv vs processed ratio for debugging
        recv_str = f"{c.DIM}│ Recv: {self.serial_lines_received}{c.RESET}" if self.serial else ""
        
        # truncate status if too long
        status_text = self.status[:20] if len(self.status) <= 20 else self.status[:17] + "..."
        
        status_line = (f"{c.BOLD}Status:{c.RESET} {status_color}{status_text.upper()}{c.RESET}  │  "
                      f"Proc: {c.CYAN}{self.total_messages}{c.RESET} {recv_str}  │  "
                      f"{queue_str}{dropped_str}  │  "
                      f"Avg: {c.GREEN}{self.total_enc_time / max(1, self.total_messages):.1f}ms{c.RESET}  │  "
                      f"{c.DIM}Ctrl+C{c.RESET}")
        
        print_at(row, 1, status_line[:72].ljust(72), clear_line=True)
    
    def draw_full(self, metrics=None, data=None):
        """draw full screen - complete redraw"""
        self.draw_header()
        self.draw_workflow()
        self.draw_step_indicator()
        self.draw_step_content()  # show transformation steps
        self.draw_metrics(metrics)
        self.draw_event_log()
        self.draw_status()
        sys.stdout.flush()
    
    def process_message(self, hex_data):
        """process incoming encrypted message - keeps last result visible"""
        try:
            self.status = "processing: decrypting"
            self.step = 0
            self.draw_status()  # only update status line, keep rest visible
            sys.stdout.flush()
            
            # decrypt xor layer from arduino
            self.log_event(f"decrypting {len(hex_data)} hex chars...")
            self.draw_event_log()
            decrypted = self.decrypt_device_msg(hex_data)
            if not decrypted:
                self.log_event("✗ failed to decrypt device data (check PSK)")
                self.draw_event_log()
                self.status = "ready"
                self.draw_status()
                sys.stdout.flush()
                return
            
            # log decrypted preview for debugging
            try:
                preview = decrypted.decode('utf-8', errors='replace')[:50]
                self.log_event(f"decrypted: {preview}...")
                self.draw_event_log()
            except Exception:
                pass  # ignore preview errors
            
            try:
                data = json.loads(decrypted.decode())
            except Exception as e:
                self.log_event(f"✗ invalid json: {type(e).__name__}")
                self.log_event(f"  raw: {decrypted[:60]}")
                self.draw_event_log()
                self.status = "ready"
                self.draw_status()
                sys.stdout.flush()
                return
        
            self.log_event(f"→ button pressed! device_id={data.get('id', 'unknown')}")
            self.log_event(f"  sensors: {data.get('t')}°C, {data.get('h')}%, {data.get('l')}lux")
            self.draw_event_log()  # show receipt immediately
            sys.stdout.flush()
            
            # do full pre + kyber workflow - updates display as it goes
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
            self.last_metrics = metrics  # save for persistent display
            
            # final update - result stays visible (step_content already updated)
            self.status = "ready"
            self.draw_metrics(metrics)
            self.draw_event_log()
            self.draw_status()
            sys.stdout.flush()
        except Exception as e:
            self.log_event(f"✗ processing error: {e}")
            self.draw_event_log()
            self.status = "ready"
            self.draw_status()
            sys.stdout.flush()
    
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
        
        # initial draw - show waiting state
        self.draw_full(self.last_metrics, self.last_data)
        self.log_event("system ready - press button on arduino")
        self.draw_event_log()
        self.draw_status()
        
        sim_mode = self.serial is None
        last_sim = 0
        
        try:
            while self.running:
                # process all queued msgs from threaded reader - prevents msg loss
                msgs_processed = 0
                queue_size = self.msg_queue.qsize()
                if self.debug and queue_size > 0 and self.debug_log:
                    self.debug_log.write(f"\n[MAIN_LOOP] queue_size={queue_size}, starting to process...\n")
                    self.debug_log.flush()
                
                while not self.msg_queue.empty():
                    try:
                        line = self.msg_queue.get_nowait()
                        msgs_processed += 1
                        
                        # debug: log raw line
                        if self.debug and self.debug_log:
                            self.debug_log.write(f"[PROCESSING #{msgs_processed}] line={repr(line[:80])}\n")
                            self.debug_log.flush()
                            self.log_event(f"[raw] {repr(line[:60])}")
                            self.draw_event_log()
                        
                        # log every received line for debugging
                        if line.startswith('ENC:'):
                            if self.debug and self.debug_log:
                                self.debug_log.write(f"  → matched ENC: pattern\n")
                                self.debug_log.flush()
                            hex_data = line[4:].strip()  # strip whitespace
                            if len(hex_data) > 0:
                                if self.debug and self.debug_log:
                                    self.debug_log.write(f"  → hex_data len={len(hex_data)}, calling process_message...\n")
                                    self.debug_log.flush()
                                self.log_event(f"⚡ enc msg rcvd ({len(hex_data)} hex chars)")
                                self.draw_event_log()
                                self.draw_status()
                                self.process_message(hex_data)
                            else:
                                if self.debug and self.debug_log:
                                    self.debug_log.write(f"  ✗ empty hex_data\n")
                                    self.debug_log.flush()
                                self.log_event(f"✗ empty enc data")
                                self.draw_event_log()
                                self.draw_status()
                        elif line.startswith('# BUTTON') or line.startswith('BUTTON'):
                            # handle both "# BUTTON" and "BUTTON" formats
                            btn_msg = line[2:].strip() if line.startswith('#') else line.strip()
                            self.log_event(f"🔘 {btn_msg}")
                            self.draw_event_log()
                            self.draw_status()
                        elif line.startswith('#'):
                            # filter out debug messages (too noisy for display)
                            if not line.startswith('# DEBUG:'):
                                self.log_event(f"arduino: {line[2:].strip()}")
                                self.draw_event_log()
                                self.draw_status()
                        elif line.startswith('PONG'):
                            # handle both "PONG:" and "PONG" formats
                            pong_msg = line[5:] if line.startswith('PONG:') else line[4:]
                            self.log_event(f"✓ arduino online: {pong_msg}")
                            self.draw_event_log()
                            self.draw_status()
                        elif line.startswith('STATUS:'):
                            self.log_event(f"status: {line[7:]}")
                            self.draw_event_log()
                            self.draw_status()
                        else:
                            # log ALL unknown messages for debugging
                            if line.strip():
                                self.log_event(f"??? unknown [{len(line)}]: {line[:45]}")
                                self.draw_event_log()
                                self.draw_status()
                    except queue.Empty:
                        break
                
                # simulation mode - auto-trigger for testing
                if sim_mode:
                    now = time.time()
                    if now - last_sim > 30:
                        last_sim = now
                        self.log_event("simulation: auto-trigger (every 30s)")
                        self.draw_event_log()
                        hex_data = self.simulate_button_press()
                        self.process_message(hex_data)
                
                time.sleep(0.02)  # very fast polling for button responsiveness
                
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            if self.serial:
                self.serial.close()
            
            # close debug log
            if self.debug_log:
                self.debug_log.write(f"\n=== demo ended, total_messages={self.total_messages} ===\n")
                self.debug_log.close()
            
            # cleanup
            print()
            move_cursor(65, 1)
            print(f"\n{Colors.CYAN}Demo ended. Total messages: {self.total_messages}{Colors.RESET}")
            if self.total_messages > 0:
                print(f"Average processing time: {self.total_enc_time / self.total_messages:.2f}ms")
            if self.debug:
                print(f"{Colors.YELLOW}Debug log saved to: /tmp/live_demo_debug.log{Colors.RESET}")
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
    debug = False
    if '--768' in sys.argv:
        security_level = 768
    elif '--1024' in sys.argv:
        security_level = 1024
    if '--debug' in sys.argv:
        debug = True
        print("  [DEBUG MODE ENABLED - verbose logging]\n")
    
    demo = LiveDemo(security_level=security_level, debug=debug)
    
    input("Press Enter to start demo...")
    
    demo.run()


if __name__ == '__main__':
    main()

