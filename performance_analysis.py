"""
performance analysis and comparison tool
evaluates suitability for iot/fog/cloud deployment
"""
import json
from full_kyber import FullKyberCrypto
from hybrid_kyber_aes import HybridKyberAES
from proxy_reencryption import ProxyReEncryption


# iot device constraints (typical values)
IOT_CONSTRAINTS = {
    'constrained_device': {
        'name': 'class 0 - very constrained (e.g., sensor node)',
        'ram_kb': 10,
        'storage_kb': 100,
        'cpu_constraint': 'very_low',
        'max_latency_ms': 1000,
        'examples': 'temp sensors, simple actuators'
    },
    'iot_device': {
        'name': 'class 1 - constrained (e.g., esp8266)',
        'ram_kb': 80,
        'storage_kb': 512,
        'cpu_constraint': 'low',
        'max_latency_ms': 500,
        'examples': 'esp8266, basic mcu'
    },
    'capable_iot': {
        'name': 'class 2 - capable (e.g., esp32, rpi zero)',
        'ram_kb': 512,
        'storage_kb': 4096,
        'cpu_constraint': 'moderate',
        'max_latency_ms': 200,
        'examples': 'esp32, raspberry pi zero, arm cortex-m4'
    },
    'fog_gateway': {
        'name': 'fog/edge gateway',
        'ram_kb': 2048,
        'storage_kb': 16384,
        'cpu_constraint': 'moderate',
        'max_latency_ms': 100,
        'examples': 'raspberry pi 4, edge gateway'
    },
    'cloud_server': {
        'name': 'cloud server',
        'ram_kb': 8192,
        'storage_kb': 102400,
        'cpu_constraint': 'high',
        'max_latency_ms': 50,
        'examples': 'server-grade hardware'
    }
}


class PerformanceAnalyzer:
    """analyze and compare crypto schemes for iot deployment"""
    
    def __init__(self):
        self.results = {}
    
    def analyze_full_kyber(self, security_levels=[512, 768, 1024], 
                          message_sizes=[64, 256, 1024, 4096]):
        """analyze full kyber performance"""
        print("analyzing full kyber crypto...")
        
        results = {}
        for sec_level in security_levels:
            crypto = FullKyberCrypto(security_level=sec_level)
            results[sec_level] = {}
            
            for msg_size in message_sizes:
                print(f"  kyber-{sec_level} with {msg_size}B message...", end='')
                metrics = crypto.measure_performance(msg_size)
                results[sec_level][msg_size] = metrics
                print(" ✓")
        
        self.results['full_kyber'] = results
        return results
    
    def analyze_hybrid(self, security_levels=[512, 768, 1024],
                      message_sizes=[64, 256, 1024, 4096],
                      aes_modes=['GCM', 'CBC']):
        """analyze hybrid kyber-aes performance"""
        print("\nanalyzing hybrid kyber-aes crypto...")
        
        results = {}
        for aes_mode in aes_modes:
            results[aes_mode] = {}
            for sec_level in security_levels:
                crypto = HybridKyberAES(security_level=sec_level, 
                                       aes_mode=aes_mode)
                results[aes_mode][sec_level] = {}
                
                for msg_size in message_sizes:
                    print(f"  kyber-{sec_level} + aes-{aes_mode} with {msg_size}B...", end='')
                    metrics = crypto.measure_performance(msg_size)
                    results[aes_mode][sec_level][msg_size] = metrics
                    print(" ✓")
        
        self.results['hybrid'] = results
        return results
    
    def analyze_proxy_reencryption(self, message_sizes=[64, 256, 1024, 4096]):
        """analyze proxy re-enc performance"""
        print("\nanalyzing proxy re-encryption...")
        
        pre = ProxyReEncryption()
        results = {}
        
        for msg_size in message_sizes:
            print(f"  proxy re-enc with {msg_size}B message...", end='')
            metrics = pre.measure_performance(msg_size)
            results[msg_size] = metrics
            print(" ✓")
        
        self.results['proxy_reencryption'] = results
        return results
    
    def check_device_suitability(self, metrics, device_type):
        """check if crypto scheme is suitable for device type"""
        constraints = IOT_CONSTRAINTS[device_type]
        
        # check memory constraints
        total_memory = (metrics.get('keygen_memory_kb', 0) +
                       max(metrics.get('encrypt_memory_kb', 
                                     metrics.get('full_encrypt_memory_kb', 0)),
                          metrics.get('decrypt_memory_kb',
                                     metrics.get('full_decrypt_memory_kb', 0))))
        
        memory_ok = total_memory < constraints['ram_kb']
        
        # check storage (key sizes)
        key_storage = (metrics.get('public_key_size_bytes', 0) +
                      metrics.get('secret_key_size_bytes', 0)) / 1024
        storage_ok = key_storage < constraints['storage_kb']
        
        # check latency
        total_latency = (metrics.get('encrypt_time_ms',
                                    metrics.get('full_encrypt_time_ms', 0)) +
                        metrics.get('decrypt_time_ms',
                                   metrics.get('full_decrypt_time_ms', 0)))
        latency_ok = total_latency < constraints['max_latency_ms']
        
        return {
            'suitable': memory_ok and storage_ok and latency_ok,
            'memory_ok': memory_ok,
            'storage_ok': storage_ok,
            'latency_ok': latency_ok,
            'memory_usage_kb': total_memory,
            'memory_limit_kb': constraints['ram_kb'],
            'storage_usage_kb': key_storage,
            'storage_limit_kb': constraints['storage_kb'],
            'latency_ms': total_latency,
            'latency_limit_ms': constraints['max_latency_ms']
        }
    
    def generate_comparison_report(self):
        """gen comprehensive comparison report"""
        print("\n" + "=" * 80)
        print("performance comparison report".upper().center(80))
        print("=" * 80)
        
        # compare full kyber vs hybrid for kyber512 with 1kb msg
        if 'full_kyber' in self.results and 'hybrid' in self.results:
            print("\n--- comparison: full kyber vs hybrid (kyber-512, 1kb message) ---")
            
            full_metrics = self.results['full_kyber'][512][1024]
            hybrid_metrics = self.results['hybrid']['GCM'][512][1024]
            
            print(f"\n{'metric':<30} {'full kyber':>15} {'hybrid':>15} {'winner':>15}")
            print("-" * 80)
            
            # encryption time
            full_enc = full_metrics['full_encrypt_time_ms']
            hybrid_enc = hybrid_metrics['encrypt_time_ms']
            winner = "hybrid" if hybrid_enc < full_enc else "full kyber"
            print(f"{'encryption time (ms)':<30} {full_enc:>15.2f} {hybrid_enc:>15.2f} {winner:>15}")
            
            # decryption time
            full_dec = full_metrics['full_decrypt_time_ms']
            hybrid_dec = hybrid_metrics['decrypt_time_ms']
            winner = "hybrid" if hybrid_dec < full_dec else "full kyber"
            print(f"{'decryption time (ms)':<30} {full_dec:>15.2f} {hybrid_dec:>15.2f} {winner:>15}")
            
            # total time
            full_total = full_enc + full_dec
            hybrid_total = hybrid_enc + hybrid_dec
            winner = "hybrid" if hybrid_total < full_total else "full kyber"
            print(f"{'total time (ms)':<30} {full_total:>15.2f} {hybrid_total:>15.2f} {winner:>15}")
            
            # memory
            full_mem = full_metrics['full_encrypt_memory_kb']
            hybrid_mem = hybrid_metrics['encrypt_memory_kb']
            winner = "hybrid" if hybrid_mem < full_mem else "full kyber"
            print(f"{'peak memory (kb)':<30} {full_mem:>15.2f} {hybrid_mem:>15.2f} {winner:>15}")
            
            # encrypted size
            full_size = full_metrics['total_encrypted_size_bytes']
            hybrid_size = hybrid_metrics['total_encrypted_size_bytes']
            winner = "hybrid" if hybrid_size < full_size else "full kyber"
            print(f"{'encrypted size (bytes)':<30} {full_size:>15} {hybrid_size:>15} {winner:>15}")
        
        # device suitability analysis
        print("\n" + "=" * 80)
        print("device suitability analysis".upper().center(80))
        print("=" * 80)
        
        if 'hybrid' in self.results:
            hybrid_512_1k = self.results['hybrid']['GCM'][512][1024]
            
            print("\n--- hybrid kyber-512 + aes-gcm (1kb message) ---\n")
            
            for device_type, constraints in IOT_CONSTRAINTS.items():
                suitability = self.check_device_suitability(hybrid_512_1k, device_type)
                
                status = "✓ suitable" if suitability['suitable'] else "✗ not suitable"
                print(f"{constraints['name']:<50} {status:>20}")
                
                if not suitability['suitable']:
                    print(f"  reasons:")
                    if not suitability['memory_ok']:
                        print(f"    - memory: {suitability['memory_usage_kb']:.1f}kb / "
                              f"{suitability['memory_limit_kb']}kb limit")
                    if not suitability['storage_ok']:
                        print(f"    - storage: {suitability['storage_usage_kb']:.1f}kb / "
                              f"{suitability['storage_limit_kb']}kb limit")
                    if not suitability['latency_ok']:
                        print(f"    - latency: {suitability['latency_ms']:.1f}ms / "
                              f"{suitability['latency_limit_ms']}ms limit")
                print()
        

        print("=" * 80)
    
    def save_results(self, filename='performance_results.json'):
        """save results to json file"""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nresults saved to {filename}")


def run_complete_analysis():
    """run complete performance analysis"""
    print("=" * 80)
    print("quantum-safe crypto for iot - performance analysis".upper().center(80))
    print("=" * 80)
    
    analyzer = PerformanceAnalyzer()
    
    # analyze all approaches
    analyzer.analyze_full_kyber(
        security_levels=[512],
        message_sizes=[64, 256, 1024]
    )
    
    analyzer.analyze_hybrid(
        security_levels=[512],
        message_sizes=[64, 256, 1024],
        aes_modes=['GCM']
    )
    
    analyzer.analyze_proxy_reencryption(
        message_sizes=[64, 256, 1024]
    )
    
    # generate report
    analyzer.generate_comparison_report()
    
    # save results
    analyzer.save_results()
    
    return analyzer


if __name__ == "__main__":
    run_complete_analysis()

