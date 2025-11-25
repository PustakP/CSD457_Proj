#!/usr/bin/env python3
"""
generate_report.py - create performance report and graphs
generates visual comparison of all encryption approaches
"""
import os
import sys
import json
import time
from datetime import datetime

# add parent dirs
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from full_kyber import FullKyberCrypto
from hybrid_kyber_aes import HybridKyberAES
from proxy_reencryption import ProxyReEncryption

try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = os.path.expanduser('~/iot_kyber_data')


class ReportGenerator:
    """generate performance reports and visualizations"""
    
    def __init__(self):
        self.results = {}
        self.iterations = 10  # avg over multiple runs
        
    def run_benchmarks(self, message_sizes=[64, 256, 1024, 4096]):
        """run comprehensive benchmarks"""
        print("=" * 60)
        print("RUNNING PERFORMANCE BENCHMARKS")
        print("=" * 60)
        
        results = {
            'full_kyber': {},
            'hybrid': {},
            'proxy_re': {},
            'metadata': {
                'iterations': self.iterations,
                'message_sizes': message_sizes,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        # benchmark each approach
        for msg_size in message_sizes:
            print(f"\n--- message size: {msg_size} bytes ---")
            
            # full kyber
            print(f"  full kyber-512...", end=' ')
            fk = FullKyberCrypto(512)
            fk_times = {'keygen': [], 'encrypt': [], 'decrypt': []}
            
            for _ in range(self.iterations):
                start = time.perf_counter()
                pk, sk = fk.generate_keypair()
                fk_times['keygen'].append((time.perf_counter() - start) * 1000)
                
                msg = b'X' * msg_size
                start = time.perf_counter()
                ct, enc = fk.encrypt_message(msg, pk)
                fk_times['encrypt'].append((time.perf_counter() - start) * 1000)
                
                start = time.perf_counter()
                fk.decrypt_message(ct, enc, sk)
                fk_times['decrypt'].append((time.perf_counter() - start) * 1000)
            
            results['full_kyber'][msg_size] = {
                'keygen_ms': sum(fk_times['keygen']) / len(fk_times['keygen']),
                'encrypt_ms': sum(fk_times['encrypt']) / len(fk_times['encrypt']),
                'decrypt_ms': sum(fk_times['decrypt']) / len(fk_times['decrypt']),
                'ct_size': len(ct) + len(enc)
            }
            print(f"✓ enc={results['full_kyber'][msg_size]['encrypt_ms']:.2f}ms")
            
            # hybrid
            print(f"  hybrid kyber+aes...", end=' ')
            hk = HybridKyberAES(512, 'GCM')
            hk_times = {'keygen': [], 'encrypt': [], 'decrypt': []}
            
            for _ in range(self.iterations):
                start = time.perf_counter()
                pk, sk = hk.generate_keypair()
                hk_times['keygen'].append((time.perf_counter() - start) * 1000)
                
                msg = b'X' * msg_size
                start = time.perf_counter()
                enc_data = hk.encrypt_message(msg, pk)
                hk_times['encrypt'].append((time.perf_counter() - start) * 1000)
                
                start = time.perf_counter()
                hk.decrypt_message(enc_data, sk)
                hk_times['decrypt'].append((time.perf_counter() - start) * 1000)
            
            ct_size = (len(enc_data['kyber_ciphertext']) + 
                      len(enc_data['aes_ciphertext']) +
                      len(enc_data['nonce']) + len(enc_data['tag']))
            
            results['hybrid'][msg_size] = {
                'keygen_ms': sum(hk_times['keygen']) / len(hk_times['keygen']),
                'encrypt_ms': sum(hk_times['encrypt']) / len(hk_times['encrypt']),
                'decrypt_ms': sum(hk_times['decrypt']) / len(hk_times['decrypt']),
                'ct_size': ct_size
            }
            print(f"✓ enc={results['hybrid'][msg_size]['encrypt_ms']:.2f}ms")
            
            # proxy re-encryption
            print(f"  proxy re-enc...", end=' ')
            pre = ProxyReEncryption()
            pre_times = {'device': [], 'gateway': [], 'cloud': []}
            
            for _ in range(self.iterations):
                dpk, dsk = pre.device_setup()
                gpk, gsk = pre.gateway_setup()
                cpk, csk = pre.cloud_setup()
                rk = pre.generate_reencryption_key(dsk, cpk)
                
                msg = b'X' * msg_size
                
                start = time.perf_counter()
                dev_enc = pre.device_encrypt(msg, dpk)
                pre_times['device'].append((time.perf_counter() - start) * 1000)
                
                start = time.perf_counter()
                reenc = pre.gateway_reencrypt(dev_enc, rk, cpk)
                pre_times['gateway'].append((time.perf_counter() - start) * 1000)
                
                start = time.perf_counter()
                pre.cloud_decrypt(reenc, dsk, csk)
                pre_times['cloud'].append((time.perf_counter() - start) * 1000)
            
            results['proxy_re'][msg_size] = {
                'device_enc_ms': sum(pre_times['device']) / len(pre_times['device']),
                'gateway_ms': sum(pre_times['gateway']) / len(pre_times['gateway']),
                'cloud_dec_ms': sum(pre_times['cloud']) / len(pre_times['cloud']),
                'total_ms': (sum(pre_times['device']) + sum(pre_times['gateway']) + 
                            sum(pre_times['cloud'])) / len(pre_times['device'])
            }
            print(f"✓ total={results['proxy_re'][msg_size]['total_ms']:.2f}ms")
        
        self.results = results
        return results
    
    def generate_text_report(self):
        """generate text-based report"""
        if not self.results:
            self.run_benchmarks()
        
        report = []
        report.append("=" * 80)
        report.append("QUANTUM-SAFE IOT CRYPTOGRAPHY - PERFORMANCE REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {self.results['metadata']['timestamp']}")
        report.append(f"Iterations per test: {self.results['metadata']['iterations']}")
        report.append("")
        
        # encryption time comparison
        report.append("-" * 80)
        report.append("ENCRYPTION TIME COMPARISON (milliseconds)")
        report.append("-" * 80)
        report.append(f"{'Message Size':<15} {'Full Kyber':>15} {'Hybrid':>15} {'Proxy RE':>15}")
        report.append("-" * 80)
        
        for size in self.results['metadata']['message_sizes']:
            fk = self.results['full_kyber'][size]['encrypt_ms']
            hk = self.results['hybrid'][size]['encrypt_ms']
            pr = self.results['proxy_re'][size]['total_ms']
            report.append(f"{str(size) + ' bytes':<15} {fk:>15.2f} {hk:>15.2f} {pr:>15.2f}")
        
        report.append("")
        
        # decryption time
        report.append("-" * 80)
        report.append("DECRYPTION TIME (milliseconds)")
        report.append("-" * 80)
        report.append(f"{'Message Size':<15} {'Full Kyber':>15} {'Hybrid':>15} {'Proxy Cloud':>15}")
        report.append("-" * 80)
        
        for size in self.results['metadata']['message_sizes']:
            fk = self.results['full_kyber'][size]['decrypt_ms']
            hk = self.results['hybrid'][size]['decrypt_ms']
            pr = self.results['proxy_re'][size]['cloud_dec_ms']
            report.append(f"{str(size) + ' bytes':<15} {fk:>15.2f} {hk:>15.2f} {pr:>15.2f}")
        
        report.append("")
        
        # ciphertext overhead
        report.append("-" * 80)
        report.append("CIPHERTEXT SIZE (bytes)")
        report.append("-" * 80)
        report.append(f"{'Message Size':<15} {'Full Kyber':>15} {'Hybrid':>15} {'Overhead':>15}")
        report.append("-" * 80)
        
        for size in self.results['metadata']['message_sizes']:
            fk = self.results['full_kyber'][size]['ct_size']
            hk = self.results['hybrid'][size]['ct_size']
            overhead = ((hk - size) / size * 100)
            report.append(f"{str(size) + ' bytes':<15} {fk:>15} {hk:>15} {overhead:>14.1f}%")
        
        report.append("")
        
        # recommendations
        report.append("=" * 80)
        report.append("RECOMMENDATIONS FOR IOT DEPLOYMENT")
        report.append("=" * 80)
        report.append("""
Device Class          | RAM      | Recommended Approach     | Notes
----------------------|----------|--------------------------|---------------------------
Class 0 (Sensors)     | <10 KB   | Proxy Re-Encryption     | Offload all crypto to gateway
Class 1 (ESP8266)     | ~80 KB   | Hybrid Kyber-512 + AES  | Borderline, may need optimization
Class 2 (ESP32)       | 512 KB   | Hybrid Kyber-512 + AES  | Good fit, AES-GCM for auth
Fog Gateway (RPi4)    | 8 GB     | Full Kyber-768/1024     | Handle device PRE
Cloud Server          | 8+ GB    | Full Kyber-1024         | Maximum security level
""")
        
        report.append("")
        report.append("KEY FINDINGS:")
        
        # calculate winner for 1KB
        if 1024 in self.results['metadata']['message_sizes']:
            fk_enc = self.results['full_kyber'][1024]['encrypt_ms']
            hk_enc = self.results['hybrid'][1024]['encrypt_ms']
            
            if hk_enc < fk_enc:
                savings = ((fk_enc - hk_enc) / fk_enc) * 100
                report.append(f"  • Hybrid is {savings:.1f}% faster than Full Kyber for encryption")
            
            fk_size = self.results['full_kyber'][1024]['ct_size']
            hk_size = self.results['hybrid'][1024]['ct_size']
            
            if hk_size < fk_size:
                savings = fk_size - hk_size
                report.append(f"  • Hybrid produces {savings} bytes smaller ciphertext")
        
        report.append("  • Proxy RE is ideal for Class 0/1 devices (offloads crypto)")
        report.append("  • AES-GCM provides authentication that pure Kyber lacks")
        report.append("  • Kyber-512 sufficient for most IoT (≈AES-128 security)")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def generate_ascii_chart(self):
        """generate ascii bar chart for encryption times"""
        if not self.results:
            self.run_benchmarks()
        
        chart = []
        chart.append("\nENCRYPTION TIME COMPARISON (1KB message)")
        chart.append("=" * 50)
        
        size = 1024
        if size in self.results['metadata']['message_sizes']:
            fk = self.results['full_kyber'][size]['encrypt_ms']
            hk = self.results['hybrid'][size]['encrypt_ms']
            pr = self.results['proxy_re'][size]['total_ms']
            
            max_val = max(fk, hk, pr)
            scale = 40 / max_val
            
            fk_bar = '█' * int(fk * scale)
            hk_bar = '█' * int(hk * scale)
            pr_bar = '█' * int(pr * scale)
            
            chart.append(f"\nFull Kyber:  {fk_bar} {fk:.2f}ms")
            chart.append(f"Hybrid:      {hk_bar} {hk:.2f}ms")
            chart.append(f"Proxy RE:    {pr_bar} {pr:.2f}ms")
        
        chart.append("")
        return "\n".join(chart)
    
    def save_report(self):
        """save all report data"""
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # save json results
        json_path = os.path.join(DATA_DIR, 'benchmark_results.json')
        with open(json_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"saved json: {json_path}")
        
        # save text report
        report = self.generate_text_report()
        txt_path = os.path.join(DATA_DIR, 'performance_report.txt')
        with open(txt_path, 'w') as f:
            f.write(report)
        print(f"saved report: {txt_path}")
        
        return json_path, txt_path


def main():
    """generate performance report"""
    print("=" * 60)
    print("PERFORMANCE REPORT GENERATOR")
    print("=" * 60)
    
    gen = ReportGenerator()
    gen.iterations = 5  # fewer iterations for demo
    
    gen.run_benchmarks()
    
    print("\n" + gen.generate_ascii_chart())
    print("\n" + gen.generate_text_report())
    
    json_path, txt_path = gen.save_report()
    
    print("\n" + "=" * 60)
    print("REPORT GENERATION COMPLETE")
    print(f"  JSON: {json_path}")
    print(f"  Text: {txt_path}")
    print("=" * 60)


if __name__ == '__main__':
    main()



