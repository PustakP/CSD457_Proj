#!/usr/bin/env python3
"""
run_demo.py - interactive demo runner for hardware prototype
orchestrates arduino, fog gateway, and cloud server

usage:
    python run_demo.py              # interactive menu
    python run_demo.py --full       # run full demo automatically
    python run_demo.py --simulate   # use simulated arduino data
"""
import sys
import os
import time
import json
import threading
from datetime import datetime

# add parent dirs to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fog_gateway import FogGateway
from cloud_server import CloudServer, DirectCloudInterface

# also import original comparison modules
try:
    from full_kyber import FullKyberCrypto
    from hybrid_kyber_aes import HybridKyberAES
    from proxy_reencryption import ProxyReEncryption
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from full_kyber import FullKyberCrypto
    from hybrid_kyber_aes import HybridKyberAES
    from proxy_reencryption import ProxyReEncryption


class DemoRunner:
    """orchestrates full hardware demo"""
    
    def __init__(self, simulate=False):
        self.simulate = simulate
        self.gateway = None
        self.cloud = None
        self.cloud_interface = None
        self.results = []
    
    def print_header(self, text):
        """print section header"""
        print("\n" + "=" * 70)
        print(f"  {text}".upper())
        print("=" * 70)
    
    def print_subheader(self, text):
        """print subsection header"""
        print(f"\n--- {text} ---")
    
    def setup_system(self):
        """initialize all components"""
        self.print_header("SYSTEM SETUP")
        
        # init cloud server
        print("\n[1/3] initializing cloud server...")
        self.cloud = CloudServer(security_level=512)
        cloud_pk = self.cloud.setup()
        
        # init fog gateway
        print("\n[2/3] initializing fog gateway...")
        self.gateway = FogGateway(security_level=512, simulate_serial=self.simulate)
        gateway_pk = self.gateway.setup()
        
        # register cloud pk with gateway
        print("\n[3/3] connecting gateway to cloud...")
        self.gateway.register_cloud(cloud_pk)
        
        # create direct interface (for demo w/o sockets)
        self.cloud_interface = DirectCloudInterface(self.cloud)
        
        print("\n✓ system initialized")
        return True
    
    def run_scenario_1_full_kyber(self):
        """demo 1: full kyber encryption (software only)"""
        self.print_header("SCENARIO 1: FULL KYBER ENCRYPTION")
        print("pure kyber kem - best for capable devices/cloud")
        
        crypto = FullKyberCrypto(security_level=512)
        
        print("\ngenerating keypair...")
        pk, sk = crypto.generate_keypair()
        print(f"  pk: {len(pk)} bytes, sk: {len(sk)} bytes")
        
        message = "sensor: temp=24.5C, humidity=55%"
        print(f"\nencrypting: '{message}'")
        
        start = time.perf_counter()
        ct, enc_msg = crypto.encrypt_message(message, pk)
        enc_time = (time.perf_counter() - start) * 1000
        
        print(f"  ciphertext: {len(ct)} bytes")
        print(f"  encrypted msg: {len(enc_msg)} bytes")
        print(f"  time: {enc_time:.2f}ms")
        
        start = time.perf_counter()
        dec_msg = crypto.decrypt_message(ct, enc_msg, sk)
        dec_time = (time.perf_counter() - start) * 1000
        
        print(f"\ndecrypted: '{dec_msg.decode()}'")
        print(f"  time: {dec_time:.2f}ms")
        print(f"\n✓ success: {dec_msg.decode() == message}")
        
        result = {
            'scenario': 'full_kyber',
            'enc_time_ms': enc_time,
            'dec_time_ms': dec_time,
            'ct_size': len(ct) + len(enc_msg)
        }
        self.results.append(result)
        return result
    
    def run_scenario_2_hybrid(self):
        """demo 2: hybrid kyber + aes"""
        self.print_header("SCENARIO 2: HYBRID KYBER-AES")
        print("kyber kem for key exchange + aes-gcm for encryption")
        print("best balance of security and performance")
        
        crypto = HybridKyberAES(security_level=512, aes_mode='GCM')
        
        print("\ngenerating keypair...")
        pk, sk = crypto.generate_keypair()
        print(f"  pk: {len(pk)} bytes, sk: {len(sk)} bytes")
        
        message = "sensor: temp=24.5C, humidity=55%, light=500lux"
        print(f"\nencrypting: '{message}'")
        
        start = time.perf_counter()
        enc_data = crypto.encrypt_message(message, pk)
        enc_time = (time.perf_counter() - start) * 1000
        
        total_size = (len(enc_data['kyber_ciphertext']) + 
                     len(enc_data['aes_ciphertext']) +
                     len(enc_data['nonce']) + 
                     len(enc_data['tag']))
        
        print(f"  kyber ct: {len(enc_data['kyber_ciphertext'])} bytes")
        print(f"  aes ct: {len(enc_data['aes_ciphertext'])} bytes")
        print(f"  total: {total_size} bytes")
        print(f"  time: {enc_time:.2f}ms")
        
        start = time.perf_counter()
        dec_msg = crypto.decrypt_message(enc_data, sk)
        dec_time = (time.perf_counter() - start) * 1000
        
        print(f"\ndecrypted: '{dec_msg.decode()}'")
        print(f"  time: {dec_time:.2f}ms")
        print(f"\n✓ success: {dec_msg.decode() == message}")
        
        result = {
            'scenario': 'hybrid_kyber_aes',
            'enc_time_ms': enc_time,
            'dec_time_ms': dec_time,
            'ct_size': total_size
        }
        self.results.append(result)
        return result
    
    def run_scenario_3_proxy(self):
        """demo 3: proxy re-encryption (fog computing)"""
        self.print_header("SCENARIO 3: PROXY RE-ENCRYPTION")
        print("iot device -> fog gateway -> cloud")
        print("gateway transforms encryption w/o seeing plaintext")
        
        pre = ProxyReEncryption()
        
        print("\nsetting up all parties...")
        device_pk, device_sk = pre.device_setup()
        gateway_pk, gateway_sk = pre.gateway_setup()
        cloud_pk, cloud_sk = pre.cloud_setup()
        print("  ✓ device, gateway, cloud keys generated")
        
        print("\ngenerating re-encryption key...")
        rk = pre.generate_reencryption_key(device_sk, cloud_pk)
        print("  ✓ re-encryption key created")
        
        message = "sensor: temp=24.5C, humidity=55%"
        print(f"\n[device] encrypting: '{message}'")
        
        start = time.perf_counter()
        device_enc = pre.device_encrypt(message, device_pk)
        device_enc_time = (time.perf_counter() - start) * 1000
        print(f"  encrypted: {len(device_enc['aes_ct'])} bytes, time: {device_enc_time:.2f}ms")
        
        print("\n[gateway] re-encrypting for cloud...")
        start = time.perf_counter()
        reenc = pre.gateway_reencrypt(device_enc, rk, cloud_pk)
        gateway_time = (time.perf_counter() - start) * 1000
        print(f"  re-encrypted: {len(reenc['reenc_ct'])} bytes, time: {gateway_time:.2f}ms")
        
        print("\n[cloud] decrypting...")
        start = time.perf_counter()
        plaintext = pre.cloud_decrypt(reenc, device_sk, cloud_sk)
        cloud_time = (time.perf_counter() - start) * 1000
        print(f"  decrypted: '{plaintext.decode()}'")
        print(f"  time: {cloud_time:.2f}ms")
        
        print(f"\n✓ success: {plaintext.decode() == message}")
        print(f"\ntotal workflow time: {device_enc_time + gateway_time + cloud_time:.2f}ms")
        
        result = {
            'scenario': 'proxy_reencryption',
            'device_enc_time_ms': device_enc_time,
            'gateway_time_ms': gateway_time,
            'cloud_dec_time_ms': cloud_time,
            'total_time_ms': device_enc_time + gateway_time + cloud_time
        }
        self.results.append(result)
        return result
    
    def run_scenario_4_hardware(self, duration=30):
        """demo 4: full hardware demo with arduino"""
        self.print_header("SCENARIO 4: HARDWARE DEMO")
        print("arduino uno -> raspberry pi gateway -> cloud")
        
        if not self.gateway or not self.cloud:
            print("\n[!] system not initialized, running setup...")
            self.setup_system()
        
        print(f"\nrunning for {duration} seconds...")
        print("data flow: arduino --[serial]--> rpi --[kyber]--> cloud")
        print("\n" + "-" * 50)
        
        messages_processed = []
        
        def callback(cloud_data):
            """callback when data reaches cloud"""
            # send to cloud for decryption
            result = self.cloud_interface.send_to_cloud(cloud_data)
            if result:
                messages_processed.append(result)
        
        # run gateway with timeout
        try:
            self.gateway.run(duration=duration, callback=callback)
        except KeyboardInterrupt:
            pass
        
        print("\n" + "-" * 50)
        print(f"\n✓ demo complete")
        print(f"  messages processed: {len(messages_processed)}")
        
        if messages_processed:
            avg_dec = sum(m.get('decryption_metrics', {}).get('total_time_ms', 0) 
                         for m in messages_processed) / len(messages_processed)
            print(f"  avg decryption time: {avg_dec:.2f}ms")
        
        result = {
            'scenario': 'hardware_demo',
            'messages': len(messages_processed),
            'duration_s': duration
        }
        self.results.append(result)
        return result
    
    def run_performance_comparison(self):
        """compare all approaches"""
        self.print_header("PERFORMANCE COMPARISON")
        
        print("\nrunning benchmarks...")
        
        # full kyber
        print("\n[1/3] full kyber-512...")
        fk = FullKyberCrypto(512)
        fk_metrics = fk.measure_performance(1024)
        
        # hybrid
        print("[2/3] hybrid kyber-512 + aes-gcm...")
        hk = HybridKyberAES(512, 'GCM')
        hk_metrics = hk.measure_performance(1024)
        
        # proxy re-enc
        print("[3/3] proxy re-encryption...")
        pre = ProxyReEncryption()
        pre_metrics = pre.measure_performance(1024)
        
        # display comparison
        self.print_subheader("results (1kb message, kyber-512)")
        
        print(f"\n{'metric':<35} {'full kyber':>12} {'hybrid':>12} {'proxy re':>12}")
        print("-" * 75)
        
        # keygen
        print(f"{'keygen (ms)':<35} "
              f"{fk_metrics['keygen_time_ms']:>12.2f} "
              f"{hk_metrics['keygen_time_ms']:>12.2f} "
              f"{'-':>12}")
        
        # encryption
        print(f"{'encryption (ms)':<35} "
              f"{fk_metrics['full_encrypt_time_ms']:>12.2f} "
              f"{hk_metrics['encrypt_time_ms']:>12.2f} "
              f"{pre_metrics['device_encrypt_time_ms']:>12.2f}")
        
        # decryption
        print(f"{'decryption (ms)':<35} "
              f"{fk_metrics['full_decrypt_time_ms']:>12.2f} "
              f"{hk_metrics['decrypt_time_ms']:>12.2f} "
              f"{pre_metrics['cloud_decrypt_time_ms']:>12.2f}")
        
        # memory
        print(f"{'enc memory (kb)':<35} "
              f"{fk_metrics['full_encrypt_memory_kb']:>12.2f} "
              f"{hk_metrics['encrypt_memory_kb']:>12.2f} "
              f"{pre_metrics['device_encrypt_memory_kb']:>12.2f}")
        
        # ciphertext size
        print(f"{'ciphertext size (bytes)':<35} "
              f"{fk_metrics['total_encrypted_size_bytes']:>12} "
              f"{hk_metrics['total_encrypted_size_bytes']:>12} "
              f"{pre_metrics['device_encrypted_size_bytes']:>12}")
        
        print("\n" + "-" * 75)
        
        # recommendations
        self.print_subheader("recommendations")
        print("""
device type                 | recommended approach
----------------------------|--------------------------------
class 0 (10kb ram)         | proxy re-encryption (offload crypto)
class 1 (80kb, esp8266)    | hybrid kyber-512 + aes (borderline)
class 2 (512kb, esp32)     | hybrid kyber-512 + aes-gcm
fog gateway (rpi4)         | full kyber-768, handle pre
cloud server               | full kyber-1024
        """)
        
        return {
            'full_kyber': fk_metrics,
            'hybrid': hk_metrics,
            'proxy_re': pre_metrics
        }
    
    def show_menu(self):
        """display interactive menu"""
        print("\n" + "=" * 70)
        print("  QUANTUM-SAFE IOT DEMO - RASPBERRY PI + ARDUINO")
        print("=" * 70)
        print("\nselect demo scenario:\n")
        print("  1. full kyber encryption")
        print("     pure kyber kem - for capable devices")
        print()
        print("  2. hybrid kyber-aes")
        print("     kyber key exchange + aes encryption")
        print()
        print("  3. proxy re-encryption")
        print("     fog computing: device -> gateway -> cloud")
        print()
        print("  4. hardware demo (arduino -> rpi -> cloud)")
        print("     full pipeline with actual/simulated hardware")
        print()
        print("  5. performance comparison")
        print("     benchmark all approaches")
        print()
        print("  6. run all demos")
        print()
        print("  0. exit")
        print()
    
    def run_interactive(self):
        """run interactive demo"""
        while True:
            self.show_menu()
            
            try:
                choice = input("enter choice (0-6): ").strip()
                
                if choice == '0':
                    print("\nexiting. stay quantum-safe!")
                    break
                elif choice == '1':
                    self.run_scenario_1_full_kyber()
                    input("\npress enter to continue...")
                elif choice == '2':
                    self.run_scenario_2_hybrid()
                    input("\npress enter to continue...")
                elif choice == '3':
                    self.run_scenario_3_proxy()
                    input("\npress enter to continue...")
                elif choice == '4':
                    self.setup_system()
                    self.run_scenario_4_hardware()
                    input("\npress enter to continue...")
                elif choice == '5':
                    self.run_performance_comparison()
                    input("\npress enter to continue...")
                elif choice == '6':
                    self.run_all()
                    input("\npress enter to continue...")
                else:
                    print("invalid choice")
                    
            except KeyboardInterrupt:
                print("\n\nexiting...")
                break
            except Exception as e:
                print(f"\nerror: {e}")
                input("press enter to continue...")
    
    def run_all(self):
        """run all demos sequentially"""
        self.print_header("RUNNING ALL DEMOS")
        
        print("\n[1/5] full kyber...")
        self.run_scenario_1_full_kyber()
        
        print("\n[2/5] hybrid kyber-aes...")
        self.run_scenario_2_hybrid()
        
        print("\n[3/5] proxy re-encryption...")
        self.run_scenario_3_proxy()
        
        print("\n[4/5] performance comparison...")
        self.run_performance_comparison()
        
        print("\n[5/5] hardware demo (20 seconds)...")
        self.setup_system()
        self.run_scenario_4_hardware(duration=20)
        
        self.print_header("ALL DEMOS COMPLETE")
        
        # summary
        print("\nresults summary:")
        for r in self.results:
            print(f"  - {r.get('scenario')}: ", end='')
            if 'enc_time_ms' in r:
                print(f"enc={r['enc_time_ms']:.2f}ms, dec={r['dec_time_ms']:.2f}ms")
            elif 'total_time_ms' in r:
                print(f"total={r['total_time_ms']:.2f}ms")
            else:
                print(f"messages={r.get('messages', 0)}")


def main():
    """main entry point"""
    simulate = '--simulate' in sys.argv or '-s' in sys.argv
    full_auto = '--full' in sys.argv or '-f' in sys.argv
    
    demo = DemoRunner(simulate=simulate)
    
    if full_auto:
        demo.run_all()
    else:
        demo.run_interactive()


if __name__ == '__main__':
    main()



