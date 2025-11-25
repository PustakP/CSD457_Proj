#!/usr/bin/env python3
"""
fog_gateway.py - raspberry pi fog computing gateway
receives data from arduino, handles kyber proxy re-encryption
sends re-encrypted data to cloud server

architecture: arduino --[serial]--> this gateway --[pre]--> cloud
"""
import serial
import time
import json
import sys
import os
import threading
import tracemalloc
from datetime import datetime
from queue import Queue
from collections import deque

# add parent dirs to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from kyber_py.kyber import Kyber512, Kyber768, Kyber1024
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import hashlib

try:
    from config import (
        SERIAL_PORT, BAUD_RATE, SERIAL_TIMEOUT, PSK,
        KYBER_SECURITY_LEVEL, COLLECT_METRICS, DATA_DIR, METRICS_FILE
    )
except ImportError:
    # fallback defaults
    SERIAL_PORT = '/dev/ttyACM0'
    BAUD_RATE = 9600
    SERIAL_TIMEOUT = 1.0
    PSK = b'KYBER_IOT_PSK_01'
    KYBER_SECURITY_LEVEL = 512
    COLLECT_METRICS = True
    DATA_DIR = '/tmp/iot_kyber_data'
    METRICS_FILE = '/tmp/iot_kyber_data/metrics.json'


class FogGateway:
    """
    fog gateway - handles pqc operations for constrained iot devices
    transforms device-encrypted data to cloud-encrypted data w/o seeing plaintext
    """
    
    def __init__(self, security_level=512, simulate_serial=False):
        """init fog gateway"""
        self.security_level = security_level
        self.simulate_serial = simulate_serial
        
        # select kyber variant
        if security_level == 512:
            self.kyber = Kyber512
        elif security_level == 768:
            self.kyber = Kyber768
        else:
            self.kyber = Kyber1024
        
        # gateway keys (for proxy re-enc)
        self.gateway_pk = None
        self.gateway_sk = None
        
        # cloud pub key (received from cloud)
        self.cloud_pk = None
        
        # device registry
        self.devices = {}
        
        # serial connection
        self.serial = None
        
        # queues for async processing
        self.incoming_queue = Queue()
        self.outgoing_queue = Queue()
        
        # metrics
        self.metrics = {
            'messages_received': 0,
            'messages_reencrypted': 0,
            'errors': 0,
            'total_enc_time_ms': 0,
            'total_reenc_time_ms': 0,
            'device_data': []
        }
        
        # recent messages for display
        self.recent_messages = deque(maxlen=10)
        
        self.running = False
        
    def setup(self, cloud_pk=None):
        """init gateway keys and connections"""
        print("[gateway] generating kyber keypair...")
        tracemalloc.start()
        start = time.perf_counter()
        
        self.gateway_pk, self.gateway_sk = self.kyber.keygen()
        
        keygen_time = (time.perf_counter() - start) * 1000
        _, keygen_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"[gateway] keygen: {keygen_time:.2f}ms, {keygen_mem/1024:.2f}kb")
        print(f"[gateway] pk size: {len(self.gateway_pk)} bytes")
        
        # store cloud pk if provided
        if cloud_pk:
            self.cloud_pk = cloud_pk
            print("[gateway] cloud public key registered")
        
        # connect to arduino via serial
        if not self.simulate_serial:
            self._connect_serial()
        else:
            print("[gateway] running in simulation mode (no serial)")
        
        return self.gateway_pk
    
    def _connect_serial(self):
        """connect to arduino via serial"""
        try:
            self.serial = serial.Serial(
                port=SERIAL_PORT,
                baudrate=BAUD_RATE,
                timeout=SERIAL_TIMEOUT
            )
            # wait for arduino reset after serial connect
            time.sleep(2)
            print(f"[gateway] connected to arduino on {SERIAL_PORT}")
            
            # send ping
            self.serial.write(b"PING\n")
            time.sleep(0.5)
            if self.serial.in_waiting:
                resp = self.serial.readline().decode().strip()
                print(f"[gateway] arduino response: {resp}")
        except Exception as e:
            print(f"[gateway] serial error: {e}")
            print("[gateway] will use simulated data")
            self.simulate_serial = True
    
    def register_cloud(self, cloud_pk):
        """register cloud server public key"""
        self.cloud_pk = cloud_pk
        print(f"[gateway] cloud pk registered ({len(cloud_pk)} bytes)")
        
    def decrypt_device_message(self, hex_data):
        """decrypt xor-encrypted data from arduino"""
        try:
            # hex decode
            encrypted = bytes.fromhex(hex_data)
            
            # xor decrypt with psk
            decrypted = bytes(a ^ b for a, b in zip(encrypted, (PSK * ((len(encrypted) // len(PSK)) + 1))))
            
            return decrypted[:len(encrypted)]
        except Exception as e:
            print(f"[gateway] decrypt error: {e}")
            return None
    
    def process_device_data(self, data):
        """process decrypted device data, apply kyber enc"""
        try:
            # parse json from device
            msg = json.loads(data.decode())
            device_id = msg.get('id', 'unknown')
            
            # track device
            if device_id not in self.devices:
                self.devices[device_id] = {
                    'first_seen': datetime.now().isoformat(),
                    'message_count': 0
                }
            self.devices[device_id]['message_count'] += 1
            self.devices[device_id]['last_seen'] = datetime.now().isoformat()
            
            # add gateway metadata
            msg['gateway_timestamp'] = datetime.now().isoformat()
            msg['gateway_id'] = 'RPi4_FOG_GW_001'
            
            return msg
        except json.JSONDecodeError as e:
            print(f"[gateway] json parse error: {e}")
            return None
    
    def encrypt_for_cloud(self, data):
        """encrypt data using kyber kem + aes for cloud"""
        if self.cloud_pk is None:
            raise ValueError("cloud pk not registered")
        
        tracemalloc.start()
        start = time.perf_counter()
        
        # kyber encapsulate for cloud
        shared_secret, kyber_ct = self.kyber.encaps(self.cloud_pk)
        
        # derive aes key
        aes_key = shared_secret[:32]
        
        # encrypt data with aes-gcm
        msg_bytes = json.dumps(data).encode() if isinstance(data, dict) else data
        cipher = AES.new(aes_key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(msg_bytes)
        
        enc_time = (time.perf_counter() - start) * 1000
        _, enc_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # update metrics
        self.metrics['total_enc_time_ms'] += enc_time
        self.metrics['messages_reencrypted'] += 1
        
        return {
            'kyber_ct': kyber_ct.hex(),
            'nonce': cipher.nonce.hex(),
            'tag': tag.hex(),
            'aes_ct': ciphertext.hex(),
            'metrics': {
                'enc_time_ms': enc_time,
                'enc_mem_kb': enc_mem / 1024,
                'kyber_ct_size': len(kyber_ct),
                'aes_ct_size': len(ciphertext)
            }
        }
    
    def reencrypt_for_cloud(self, device_encrypted_hex, original_data=None):
        """
        proxy re-encrypt device data for cloud
        simulates pre: gateway transforms enc w/o seeing original plaintext
        
        note: this is simplified pre for demo. real pre uses more advanced math
        """
        tracemalloc.start()
        start = time.perf_counter()
        
        # in real pre, gateway would transform ciphertext mathematically
        # here we decrypt from device and re-encrypt for cloud (simplified demo)
        
        if original_data is None:
            # decrypt from device
            decrypted = self.decrypt_device_message(device_encrypted_hex)
            if decrypted is None:
                return None
            original_data = self.process_device_data(decrypted)
        
        # encrypt for cloud using kyber
        cloud_encrypted = self.encrypt_for_cloud(original_data)
        
        reenc_time = (time.perf_counter() - start) * 1000
        _, reenc_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        self.metrics['total_reenc_time_ms'] += reenc_time
        cloud_encrypted['metrics']['reenc_time_ms'] = reenc_time
        cloud_encrypted['metrics']['reenc_mem_kb'] = reenc_mem / 1024
        cloud_encrypted['original_data'] = original_data  # for demo visibility
        
        return cloud_encrypted
    
    def _serial_reader_thread(self):
        """thread to read from arduino"""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    line = self.serial.readline().decode().strip()
                    if line:
                        self.incoming_queue.put(line)
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"[gateway] serial read error: {e}")
                time.sleep(1)
    
    def _simulate_arduino_data(self):
        """generate simulated arduino data for testing"""
        import random
        
        temp = round(22 + random.uniform(-3, 3), 1)
        humidity = round(55 + random.uniform(-10, 10), 1)
        light = int(500 + random.uniform(-200, 200))
        
        msg = {
            'id': 'SIM_ARDUINO_001',
            'seq': self.metrics['messages_received'],
            't': temp,
            'h': humidity,
            'l': light,
            'ts': int(time.time() * 1000)
        }
        
        # simulate xor encryption
        msg_bytes = json.dumps(msg).encode()
        encrypted = bytes(a ^ b for a, b in zip(msg_bytes, (PSK * ((len(msg_bytes) // len(PSK)) + 1))))
        
        return 'ENC:' + encrypted[:len(msg_bytes)].hex().upper()
    
    def run(self, duration=None, callback=None):
        """main gateway loop"""
        self.running = True
        print("\n" + "=" * 60)
        print("[gateway] FOG GATEWAY RUNNING")
        print("=" * 60)
        
        # start serial reader if not simulating
        if not self.simulate_serial and self.serial:
            reader_thread = threading.Thread(target=self._serial_reader_thread, daemon=True)
            reader_thread.start()
        
        start_time = time.time()
        sim_interval = 5  # seconds between simulated msgs
        last_sim = 0
        
        try:
            while self.running:
                current_time = time.time()
                
                # check duration
                if duration and (current_time - start_time) > duration:
                    break
                
                # simulate data if needed
                if self.simulate_serial and (current_time - last_sim) >= sim_interval:
                    last_sim = current_time
                    sim_data = self._simulate_arduino_data()
                    self.incoming_queue.put(sim_data)
                
                # process incoming queue
                while not self.incoming_queue.empty():
                    line = self.incoming_queue.get()
                    self._process_line(line, callback)
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n[gateway] shutting down...")
        finally:
            self.running = False
            self._save_metrics()
    
    def _process_line(self, line, callback=None):
        """process single line from arduino"""
        self.metrics['messages_received'] += 1
        
        if line.startswith('ENC:'):
            # encrypted sensor data
            hex_data = line[4:]
            print(f"\n[gateway] received encrypted data ({len(hex_data)//2} bytes)")
            
            # decrypt and process
            decrypted = self.decrypt_device_message(hex_data)
            if decrypted:
                data = self.process_device_data(decrypted)
                if data:
                    print(f"[gateway] device: {data.get('id')}, temp: {data.get('t')}°C, "
                          f"humidity: {data.get('h')}%, light: {data.get('l')}")
                    
                    # re-encrypt for cloud
                    if self.cloud_pk:
                        cloud_data = self.reencrypt_for_cloud(None, data)
                        if cloud_data:
                            print(f"[gateway] re-encrypted for cloud "
                                  f"(kyber_ct: {cloud_data['metrics']['kyber_ct_size']}B, "
                                  f"aes_ct: {cloud_data['metrics']['aes_ct_size']}B)")
                            print(f"[gateway] enc time: {cloud_data['metrics']['enc_time_ms']:.2f}ms")
                            
                            # store for retrieval
                            self.recent_messages.append(cloud_data)
                            
                            # callback if provided
                            if callback:
                                callback(cloud_data)
                    
                    # record metrics
                    self.metrics['device_data'].append({
                        'timestamp': datetime.now().isoformat(),
                        'device': data.get('id'),
                        'temp': data.get('t'),
                        'humidity': data.get('h'),
                        'light': data.get('l')
                    })
                    
        elif line.startswith('#'):
            # status message
            print(f"[gateway] arduino: {line}")
        elif line.startswith('PONG:'):
            print(f"[gateway] arduino pong: {line[5:]}")
        else:
            print(f"[gateway] unknown: {line}")
    
    def _save_metrics(self):
        """save metrics to file"""
        if COLLECT_METRICS:
            try:
                os.makedirs(DATA_DIR, exist_ok=True)
                self.metrics['end_time'] = datetime.now().isoformat()
                with open(METRICS_FILE, 'w') as f:
                    json.dump(self.metrics, f, indent=2)
                print(f"[gateway] metrics saved to {METRICS_FILE}")
            except Exception as e:
                print(f"[gateway] failed to save metrics: {e}")
    
    def get_stats(self):
        """return current stats"""
        avg_enc = 0
        if self.metrics['messages_reencrypted'] > 0:
            avg_enc = self.metrics['total_enc_time_ms'] / self.metrics['messages_reencrypted']
        
        return {
            'messages_received': self.metrics['messages_received'],
            'messages_reencrypted': self.metrics['messages_reencrypted'],
            'devices': len(self.devices),
            'avg_encryption_time_ms': avg_enc,
            'recent_messages': len(self.recent_messages)
        }


def main():
    """standalone gateway runner"""
    print("=" * 60)
    print("RASPBERRY PI FOG GATEWAY - KYBER PQC")
    print("=" * 60)
    
    # check for simulation mode
    simulate = '--simulate' in sys.argv or '-s' in sys.argv
    
    # init gateway
    gateway = FogGateway(security_level=KYBER_SECURITY_LEVEL, simulate_serial=simulate)
    
    # setup (gen keys)
    gateway_pk = gateway.setup()
    
    # for demo: generate cloud keys too
    print("\n[demo] generating cloud keypair for testing...")
    cloud_pk, cloud_sk = gateway.kyber.keygen()
    gateway.register_cloud(cloud_pk)
    
    # callback to print cloud decryption (demo)
    def demo_callback(cloud_data):
        # decrypt as cloud would
        try:
            kyber_ct = bytes.fromhex(cloud_data['kyber_ct'])
            ss = gateway.kyber.decaps(cloud_sk, kyber_ct)
            aes_key = ss[:32]
            
            cipher = AES.new(aes_key, AES.MODE_GCM, nonce=bytes.fromhex(cloud_data['nonce']))
            plaintext = cipher.decrypt_and_verify(
                bytes.fromhex(cloud_data['aes_ct']),
                bytes.fromhex(cloud_data['tag'])
            )
            
            data = json.loads(plaintext)
            print(f"[cloud] ✓ decrypted: temp={data.get('t')}°C, "
                  f"humidity={data.get('h')}%, light={data.get('l')}")
        except Exception as e:
            print(f"[cloud] decryption error: {e}")
    
    print("\n[gateway] waiting for sensor data...")
    print("[gateway] press Ctrl+C to stop\n")
    
    # run gateway
    gateway.run(callback=demo_callback)


if __name__ == '__main__':
    main()



