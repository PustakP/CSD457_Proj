#!/usr/bin/env python3
"""
dashboard.py - real-time terminal dashboard for iot demo
displays sensor data, encryption metrics, and system status
"""
import os
import sys
import time
import json
from datetime import datetime
from collections import deque

# add parent dirs
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fog_gateway import FogGateway
from cloud_server import CloudServer, DirectCloudInterface

try:
    from config import KYBER_SECURITY_LEVEL, DATA_DIR
except ImportError:
    KYBER_SECURITY_LEVEL = 512
    DATA_DIR = '/tmp/iot_kyber_data'


class TerminalDashboard:
    """
    live terminal dashboard for monitoring iot demo
    shows real-time data, metrics, and status
    """
    
    def __init__(self, simulate=False):
        self.simulate = simulate
        self.gateway = None
        self.cloud = None
        self.cloud_interface = None
        
        # data storage
        self.sensor_history = deque(maxlen=20)
        self.metric_history = deque(maxlen=50)
        
        # stats
        self.stats = {
            'total_messages': 0,
            'total_enc_time': 0,
            'total_dec_time': 0,
            'errors': 0,
            'start_time': time.time()
        }
        
        self.running = False
    
    def clear_screen(self):
        """clear terminal"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def setup(self):
        """initialize system"""
        print("initializing quantum-safe iot system...")
        
        # init cloud
        self.cloud = CloudServer(security_level=KYBER_SECURITY_LEVEL)
        cloud_pk = self.cloud.setup()
        
        # init gateway
        self.gateway = FogGateway(
            security_level=KYBER_SECURITY_LEVEL,
            simulate_serial=self.simulate
        )
        self.gateway.setup()
        self.gateway.register_cloud(cloud_pk)
        
        # direct interface
        self.cloud_interface = DirectCloudInterface(self.cloud)
        
        print("system ready!")
        time.sleep(1)
    
    def format_bar(self, value, max_val, width=20, char='█'):
        """create progress bar"""
        filled = int((value / max_val) * width) if max_val > 0 else 0
        return char * filled + '░' * (width - filled)
    
    def draw_dashboard(self):
        """draw dashboard frame"""
        self.clear_screen()
        
        now = datetime.now().strftime('%H:%M:%S')
        uptime = int(time.time() - self.stats['start_time'])
        uptime_str = f"{uptime//60}m {uptime%60}s"
        
        # header
        print("╔" + "═" * 78 + "╗")
        print(f"║{'QUANTUM-SAFE IOT DASHBOARD':^78}║")
        print(f"║{'─' * 78}║")
        print(f"║  Time: {now}  │  Uptime: {uptime_str}  │  Mode: {'SIMULATION' if self.simulate else 'HARDWARE':^10}  │  Kyber-{KYBER_SECURITY_LEVEL}  ║")
        print("╠" + "═" * 78 + "╣")
        
        # system status
        print("║  SYSTEM STATUS                                                               ║")
        print("║  ───────────────────────────────────────────────────────────────────────── ║")
        
        gw_status = "● ONLINE" if self.gateway else "○ OFFLINE"
        cloud_status = "● ONLINE" if self.cloud else "○ OFFLINE"
        
        print(f"║  Gateway: {gw_status:12}  │  Cloud: {cloud_status:12}  │  Messages: {self.stats['total_messages']:>6}    ║")
        print("╠" + "═" * 78 + "╣")
        
        # sensor data
        print("║  LATEST SENSOR READINGS                                                      ║")
        print("║  ───────────────────────────────────────────────────────────────────────── ║")
        
        if self.sensor_history:
            latest = self.sensor_history[-1]
            temp = latest.get('t', 0)
            humid = latest.get('h', 0)
            light = latest.get('l', 0)
            
            temp_bar = self.format_bar(temp, 50, 15)
            humid_bar = self.format_bar(humid, 100, 15)
            light_bar = self.format_bar(light, 1000, 15)
            
            print(f"║  Temperature: {temp:>5.1f}°C  [{temp_bar}]                              ║")
            print(f"║  Humidity:    {humid:>5.1f}%   [{humid_bar}]                              ║")
            print(f"║  Light:       {light:>5} lux [{light_bar}]                              ║")
        else:
            print("║  Waiting for sensor data...                                                  ║")
            print("║                                                                              ║")
            print("║                                                                              ║")
        
        print("╠" + "═" * 78 + "╣")
        
        # encryption metrics
        print("║  ENCRYPTION METRICS                                                          ║")
        print("║  ───────────────────────────────────────────────────────────────────────── ║")
        
        if self.stats['total_messages'] > 0:
            avg_enc = self.stats['total_enc_time'] / self.stats['total_messages']
            avg_dec = self.stats['total_dec_time'] / self.stats['total_messages']
            
            enc_bar = self.format_bar(avg_enc, 20, 20)
            dec_bar = self.format_bar(avg_dec, 20, 20)
            
            print(f"║  Avg Encryption: {avg_enc:>6.2f}ms  [{enc_bar}]                      ║")
            print(f"║  Avg Decryption: {avg_dec:>6.2f}ms  [{dec_bar}]                      ║")
        else:
            print("║  No encryption metrics yet...                                                ║")
            print("║                                                                              ║")
        
        print("╠" + "═" * 78 + "╣")
        
        # recent messages
        print("║  RECENT MESSAGES                                                             ║")
        print("║  ───────────────────────────────────────────────────────────────────────── ║")
        
        recent = list(self.sensor_history)[-5:]
        for data in recent:
            device = data.get('id', 'unknown')[:15]
            temp = data.get('t', 0)
            ts = data.get('gateway_timestamp', '')[:19]
            print(f"║  [{ts}] {device:<15} temp={temp:>5.1f}°C                           ║")
        
        # pad if less than 5
        for _ in range(5 - len(recent)):
            print("║                                                                              ║")
        
        print("╠" + "═" * 78 + "╣")
        print("║  Press Ctrl+C to stop                                                        ║")
        print("╚" + "═" * 78 + "╝")
    
    def process_message(self, cloud_data):
        """process incoming message"""
        # send to cloud
        result = self.cloud_interface.send_to_cloud(cloud_data)
        
        if result:
            self.stats['total_messages'] += 1
            
            # extract metrics
            metrics = cloud_data.get('metrics', {})
            enc_time = metrics.get('enc_time_ms', 0)
            
            dec_metrics = result.get('decryption_metrics', {})
            dec_time = dec_metrics.get('total_time_ms', 0)
            
            self.stats['total_enc_time'] += enc_time
            self.stats['total_dec_time'] += dec_time
            
            # store sensor data
            self.sensor_history.append(result)
            
            # store metrics
            self.metric_history.append({
                'timestamp': time.time(),
                'enc_time': enc_time,
                'dec_time': dec_time
            })
    
    def run(self):
        """run dashboard"""
        self.setup()
        self.running = True
        
        # start gateway in thread
        import threading
        
        def gateway_runner():
            self.gateway.run(callback=self.process_message)
        
        gateway_thread = threading.Thread(target=gateway_runner, daemon=True)
        gateway_thread.start()
        
        try:
            while self.running:
                self.draw_dashboard()
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            self.gateway.running = False
            print("\n\nshutting down dashboard...")
            self.save_session()
    
    def save_session(self):
        """save session data"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            filepath = os.path.join(DATA_DIR, 'dashboard_session.json')
            
            session = {
                'end_time': datetime.now().isoformat(),
                'stats': self.stats,
                'sensor_data': list(self.sensor_history),
                'metrics': list(self.metric_history)
            }
            
            with open(filepath, 'w') as f:
                json.dump(session, f, indent=2)
            
            print(f"session saved to {filepath}")
        except Exception as e:
            print(f"failed to save session: {e}")


def main():
    """run dashboard"""
    simulate = '--simulate' in sys.argv or '-s' in sys.argv
    
    print("=" * 60)
    print("QUANTUM-SAFE IOT DASHBOARD")
    print("=" * 60)
    print(f"mode: {'simulation' if simulate else 'hardware'}")
    print()
    
    dashboard = TerminalDashboard(simulate=simulate)
    dashboard.run()


if __name__ == '__main__':
    main()



