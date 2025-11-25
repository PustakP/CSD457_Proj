import json
import matplotlib.pyplot as plt
import os

# create graphs folder if doesn't exist
os.makedirs('graphs', exist_ok=True)

# load perf data
with open('performance_results.json', 'r') as f:
    data = json.load(f)

# msg sizes for x-axis
message_sizes = [64, 256, 1024]

# graph 1: enc time comparison
plt.figure(figsize=(10, 6))
full_kyber_enc = [data['full_kyber']['512'][str(size)]['full_encrypt_time_ms'] for size in message_sizes]
hybrid_enc = [data['hybrid']['GCM']['512'][str(size)]['encrypt_time_ms'] for size in message_sizes]
proxy_enc = [data['proxy_reencryption'][str(size)]['device_encrypt_time_ms'] for size in message_sizes]

plt.plot(message_sizes, full_kyber_enc, marker='o', label='Full Kyber', linewidth=2)
plt.plot(message_sizes, hybrid_enc, marker='s', label='Hybrid GCM', linewidth=2)
plt.plot(message_sizes, proxy_enc, marker='^', label='Proxy Re-encryption', linewidth=2)
plt.xlabel('Message Size (bytes)')
plt.ylabel('Encryption Time (ms)')
plt.title('Encryption Time vs Message Size')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('graphs/encryption_time.png', dpi=300, bbox_inches='tight')
plt.close()

# graph 2: dec time comparison
plt.figure(figsize=(10, 6))
full_kyber_dec = [data['full_kyber']['512'][str(size)]['full_decrypt_time_ms'] for size in message_sizes]
hybrid_dec = [data['hybrid']['GCM']['512'][str(size)]['decrypt_time_ms'] for size in message_sizes]
proxy_dec = [data['proxy_reencryption'][str(size)]['cloud_decrypt_time_ms'] for size in message_sizes]

plt.plot(message_sizes, full_kyber_dec, marker='o', label='Full Kyber', linewidth=2)
plt.plot(message_sizes, hybrid_dec, marker='s', label='Hybrid GCM', linewidth=2)
plt.plot(message_sizes, proxy_dec, marker='^', label='Proxy Re-encryption', linewidth=2)
plt.xlabel('Message Size (bytes)')
plt.ylabel('Decryption Time (ms)')
plt.title('Decryption Time vs Message Size')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('graphs/decryption_time.png', dpi=300, bbox_inches='tight')
plt.close()

# graph 3: total enc size comparison
plt.figure(figsize=(10, 6))
full_kyber_size = [data['full_kyber']['512'][str(size)]['total_encrypted_size_bytes'] for size in message_sizes]
hybrid_size = [data['hybrid']['GCM']['512'][str(size)]['total_encrypted_size_bytes'] for size in message_sizes]
proxy_size = [data['proxy_reencryption'][str(size)]['reencrypted_size_bytes'] for size in message_sizes]

plt.plot(message_sizes, full_kyber_size, marker='o', label='Full Kyber', linewidth=2)
plt.plot(message_sizes, hybrid_size, marker='s', label='Hybrid GCM', linewidth=2)
plt.plot(message_sizes, proxy_size, marker='^', label='Proxy Re-encryption', linewidth=2)
plt.xlabel('Message Size (bytes)')
plt.ylabel('Encrypted Size (bytes)')
plt.title('Encrypted Data Size vs Message Size')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('graphs/encrypted_size.png', dpi=300, bbox_inches='tight')
plt.close()

# graph 4: mem usage during enc
plt.figure(figsize=(10, 6))
full_kyber_mem = [data['full_kyber']['512'][str(size)]['full_encrypt_memory_kb'] for size in message_sizes]
hybrid_mem = [data['hybrid']['GCM']['512'][str(size)]['encrypt_memory_kb'] for size in message_sizes]
proxy_mem = [data['proxy_reencryption'][str(size)]['device_encrypt_memory_kb'] for size in message_sizes]

plt.plot(message_sizes, full_kyber_mem, marker='o', label='Full Kyber', linewidth=2)
plt.plot(message_sizes, hybrid_mem, marker='s', label='Hybrid GCM', linewidth=2)
plt.plot(message_sizes, proxy_mem, marker='^', label='Proxy Re-encryption', linewidth=2)
plt.xlabel('Message Size (bytes)')
plt.ylabel('Memory Usage (KB)')
plt.title('Memory Usage During Encryption')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('graphs/memory_usage.png', dpi=300, bbox_inches='tight')
plt.close()

# graph 5: keygen time comparison
plt.figure(figsize=(8, 6))
keygen_times = [
    data['full_kyber']['512']['64']['keygen_time_ms'],
    data['hybrid']['GCM']['512']['64']['keygen_time_ms']
]
methods = ['Full Kyber', 'Hybrid GCM']
colors = ['#1f77b4', '#ff7f0e']

plt.bar(methods, keygen_times, color=colors, alpha=0.7, edgecolor='black')
plt.ylabel('Key Generation Time (ms)')
plt.title('Key Generation Time Comparison')
plt.grid(True, alpha=0.3, axis='y')
plt.savefig('graphs/keygen_time.png', dpi=300, bbox_inches='tight')
plt.close()

# graph 6: proxy workflow breakdown
plt.figure(figsize=(10, 6))
msg_size = 64
workflow_data = data['proxy_reencryption'][str(msg_size)]
stages = ['ReKey Gen', 'Device Encrypt', 'Gateway Re-encrypt', 'Cloud Decrypt']
times = [
    workflow_data['rekey_gen_time_ms'],
    workflow_data['device_encrypt_time_ms'],
    workflow_data['gateway_reencrypt_time_ms'],
    workflow_data['cloud_decrypt_time_ms']
]

plt.bar(stages, times, color=['#2ca02c', '#d62728', '#9467bd', '#8c564b'], alpha=0.7, edgecolor='black')
plt.ylabel('Time (ms)')
plt.title(f'Proxy Re-encryption Workflow Breakdown ({msg_size} bytes)')
plt.xticks(rotation=15, ha='right')
plt.grid(True, alpha=0.3, axis='y')
plt.savefig('graphs/proxy_workflow.png', dpi=300, bbox_inches='tight')
plt.close()

print("All graphs saved to 'graphs/' folder:")
print("  - encryption_time.png")
print("  - decryption_time.png")
print("  - encrypted_size.png")
print("  - memory_usage.png")
print("  - keygen_time.png")
print("  - proxy_workflow.png")

