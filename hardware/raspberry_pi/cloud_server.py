#!/usr/bin/env python3
"""
cloud_server.py - simulated cloud server on raspberry pi
receives kyber-encrypted data from fog gateway, performs full decryption
stores and analyzes sensor data

in production: this would run on actual cloud infrastructure
for demo: runs on same rpi or separate machine
"""
import socket
import json
import time
import sys
import os
import threading
import tracemalloc
from datetime import datetime
from collections import deque
import struct

# add parent dirs to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from kyber_py.kyber import Kyber512, Kyber768, Kyber1024
from Crypto.Cipher import AES

try:
    from config import (
        KYBER_SECURITY_LEVEL, CLOUD_PORT, DATA_DIR
    )
except ImportError:
    KYBER_SECURITY_LEVEL = 512
    CLOUD_PORT = 5001
    DATA_DIR = '/tmp/iot_kyber_data'


class CloudServer:
    """
    cloud server - receives pqc-encrypted data, decrypts, stores
    handles full kyber decapsulation + aes decryption
    """
    
    def __init__(self, security_level=512):
        """init cloud server"""
        self.security_level = security_level
        
        # select kyber variant
        if security_level == 512:
            self.kyber = Kyber512
        elif security_level == 768:
            self.kyber = Kyber768
        else:
            self.kyber = Kyber1024
        
        # cloud keys
        self.cloud_pk = None
        self.cloud_sk = None
        
        # data storage
        self.sensor_data = []
        self.recent_data = deque(maxlen=100)
        
        # metrics
        self.metrics = {
            'messages_received': 0,
            'messages_decrypted': 0,
            'decryption_errors': 0,
            'total_decryption_time_ms': 0,
            'start_time': datetime.now().isoformat()
        }
        
        # socket for receiving data
        self.server_socket = None
        self.running = False
        
    def setup(self):
        """init cloud keys"""
        print("[cloud] generating kyber keypair...")
        tracemalloc.start()
        start = time.perf_counter()
        
        self.cloud_pk, self.cloud_sk = self.kyber.keygen()
        
        keygen_time = (time.perf_counter() - start) * 1000
        _, keygen_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"[cloud] keygen: {keygen_time:.2f}ms, {keygen_mem/1024:.2f}kb")
        print(f"[cloud] pk size: {len(self.cloud_pk)} bytes")
        print(f"[cloud] sk size: {len(self.cloud_sk)} bytes")
        
        return self.cloud_pk
    
    def get_public_key(self):
        """return cloud public key for distribution"""
        return self.cloud_pk
    
    def decrypt_message(self, encrypted_data):
        """
        decrypt kyber+aes encrypted message from gateway
        
        encrypted_data format:
        {
            'kyber_ct': hex string,
            'nonce': hex string,
            'tag': hex string,
            'aes_ct': hex string
        }
        """
        tracemalloc.start()
        start = time.perf_counter()
        
        try:
            # parse ciphertext components
            kyber_ct = bytes.fromhex(encrypted_data['kyber_ct'])
            nonce = bytes.fromhex(encrypted_data['nonce'])
            tag = bytes.fromhex(encrypted_data['tag'])
            aes_ct = bytes.fromhex(encrypted_data['aes_ct'])
            
            # kyber decapsulation
            decaps_start = time.perf_counter()
            shared_secret = self.kyber.decaps(self.cloud_sk, kyber_ct)
            decaps_time = (time.perf_counter() - decaps_start) * 1000
            
            # derive aes key
            aes_key = shared_secret[:32]
            
            # aes-gcm decryption
            aes_start = time.perf_counter()
            cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(aes_ct, tag)
            aes_time = (time.perf_counter() - aes_start) * 1000
            
            total_time = (time.perf_counter() - start) * 1000
            _, dec_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            # parse json
            data = json.loads(plaintext.decode())
            
            # add cloud metadata
            data['cloud_timestamp'] = datetime.now().isoformat()
            data['decryption_metrics'] = {
                'total_time_ms': total_time,
                'kyber_decaps_ms': decaps_time,
                'aes_decrypt_ms': aes_time,
                'memory_kb': dec_mem / 1024
            }
            
            # update metrics
            self.metrics['messages_decrypted'] += 1
            self.metrics['total_decryption_time_ms'] += total_time
            
            return data
            
        except Exception as e:
            tracemalloc.stop()
            self.metrics['decryption_errors'] += 1
            print(f"[cloud] decryption error: {e}")
            return None
    
    def store_data(self, data):
        """store decrypted sensor data"""
        self.sensor_data.append(data)
        self.recent_data.append(data)
        
        # persist to disk periodically
        if len(self.sensor_data) % 10 == 0:
            self._save_data()
    
    def _save_data(self):
        """save data to disk"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            filepath = os.path.join(DATA_DIR, 'cloud_data.json')
            with open(filepath, 'w') as f:
                json.dump({
                    'metrics': self.metrics,
                    'recent_data': list(self.recent_data)
                }, f, indent=2)
        except Exception as e:
            print(f"[cloud] save error: {e}")
    
    def process_gateway_message(self, message):
        """process message from fog gateway"""
        self.metrics['messages_received'] += 1
        
        # decrypt
        data = self.decrypt_message(message)
        
        if data:
            # store
            self.store_data(data)
            
            # display
            print(f"\n[cloud] ✓ decrypted sensor data:")
            print(f"  device: {data.get('id', 'unknown')}")
            print(f"  temp: {data.get('t', '?')}°C")
            print(f"  humidity: {data.get('h', '?')}%")
            print(f"  light: {data.get('l', '?')} lux")
            print(f"  decryption: {data['decryption_metrics']['total_time_ms']:.2f}ms")
            
            return data
        else:
            print("[cloud] ✗ decryption failed")
            return None
    
    def run_socket_server(self, host='0.0.0.0', port=None):
        """run tcp server to receive data from gateway"""
        if port is None:
            port = CLOUD_PORT
            
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        self.server_socket.settimeout(1.0)
        
        self.running = True
        print(f"[cloud] listening on {host}:{port}")
        
        try:
            while self.running:
                try:
                    client, addr = self.server_socket.accept()
                    print(f"[cloud] connection from {addr}")
                    threading.Thread(
                        target=self._handle_client,
                        args=(client,),
                        daemon=True
                    ).start()
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            print("\n[cloud] shutting down...")
        finally:
            self.running = False
            self.server_socket.close()
            self._save_data()
    
    def _handle_client(self, client):
        """handle client connection"""
        try:
            while True:
                # receive length-prefixed json
                length_bytes = client.recv(4)
                if not length_bytes:
                    break
                    
                length = struct.unpack('>I', length_bytes)[0]
                data = b''
                while len(data) < length:
                    chunk = client.recv(min(4096, length - len(data)))
                    if not chunk:
                        break
                    data += chunk
                
                if len(data) == length:
                    message = json.loads(data.decode())
                    result = self.process_gateway_message(message)
                    
                    # send ack
                    response = json.dumps({'status': 'ok' if result else 'error'}).encode()
                    client.send(struct.pack('>I', len(response)) + response)
        except Exception as e:
            print(f"[cloud] client error: {e}")
        finally:
            client.close()
    
    def get_analytics(self):
        """return data analytics"""
        if not self.sensor_data:
            return {'status': 'no data'}
        
        temps = [d.get('t', 0) for d in self.sensor_data if 't' in d]
        humids = [d.get('h', 0) for d in self.sensor_data if 'h' in d]
        lights = [d.get('l', 0) for d in self.sensor_data if 'l' in d]
        
        def stats(values):
            if not values:
                return {'min': 0, 'max': 0, 'avg': 0}
            return {
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values)
            }
        
        avg_dec_time = 0
        if self.metrics['messages_decrypted'] > 0:
            avg_dec_time = self.metrics['total_decryption_time_ms'] / self.metrics['messages_decrypted']
        
        return {
            'total_readings': len(self.sensor_data),
            'temperature': stats(temps),
            'humidity': stats(humids),
            'light': stats(lights),
            'avg_decryption_time_ms': avg_dec_time,
            'errors': self.metrics['decryption_errors']
        }
    
    def get_status(self):
        """return server status"""
        return {
            'running': self.running,
            'security_level': self.security_level,
            'messages_received': self.metrics['messages_received'],
            'messages_decrypted': self.metrics['messages_decrypted'],
            'errors': self.metrics['decryption_errors'],
            'data_points': len(self.sensor_data)
        }


class DirectCloudInterface:
    """
    direct interface for demo (no socket)
    gateway calls cloud methods directly
    """
    
    def __init__(self, cloud_server):
        self.cloud = cloud_server
    
    def send_to_cloud(self, encrypted_data):
        """directly process encrypted data"""
        return self.cloud.process_gateway_message(encrypted_data)


def main():
    """standalone cloud server"""
    print("=" * 60)
    print("CLOUD SERVER - KYBER PQC DECRYPTION")
    print("=" * 60)
    
    # check for socket mode
    use_socket = '--socket' in sys.argv or '-s' in sys.argv
    
    # init cloud
    cloud = CloudServer(security_level=KYBER_SECURITY_LEVEL)
    cloud_pk = cloud.setup()
    
    print(f"\n[cloud] public key ({len(cloud_pk)} bytes):")
    print(f"  {cloud_pk[:32].hex()}...")
    
    if use_socket:
        print("\n[cloud] starting socket server...")
        cloud.run_socket_server()
    else:
        print("\n[cloud] running in demo mode (no socket)")
        print("[cloud] use with fog_gateway.py for full demo")
        
        # demo: encrypt and decrypt test message
        print("\n[demo] self-test encryption/decryption...")
        
        # simulate gateway encryption
        test_data = {
            'id': 'TEST_DEVICE',
            't': 25.5,
            'h': 60.0,
            'l': 500
        }
        
        # encrypt as gateway would
        shared_secret, kyber_ct = cloud.kyber.encaps(cloud_pk)
        aes_key = shared_secret[:32]
        cipher = AES.new(aes_key, AES.MODE_GCM)
        ct, tag = cipher.encrypt_and_digest(json.dumps(test_data).encode())
        
        encrypted = {
            'kyber_ct': kyber_ct.hex(),
            'nonce': cipher.nonce.hex(),
            'tag': tag.hex(),
            'aes_ct': ct.hex()
        }
        
        print(f"[demo] encrypted size: {len(kyber_ct) + len(ct) + len(tag) + len(cipher.nonce)} bytes")
        
        # decrypt
        result = cloud.process_gateway_message(encrypted)
        
        if result:
            print("\n[demo] ✓ self-test passed!")
            print(f"[demo] analytics: {cloud.get_analytics()}")


if __name__ == '__main__':
    main()



