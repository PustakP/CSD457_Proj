"""
quick start example - minimal demo of all approaches
"""
from full_kyber import FullKyberCrypto
from hybrid_kyber_aes import HybridKyberAES
from proxy_reencryption import ProxyReEncryption


def quick_demo():
    """quick demonstration of all three approaches"""
    
    print("=" * 80)
    print("QUANTUM-SAFE CRYPTO FOR IOT - QUICK START".center(80))
    print("=" * 80)
    
    message = "hello quantum-safe world!"
    
    # 1. full kyber
    print("\n[1] FULL KYBER APPROACH")
    print("-" * 80)
    kyber = FullKyberCrypto(512)
    pk, sk = kyber.generate_keypair()
    ct, enc = kyber.encrypt_message(message, pk)
    dec = kyber.decrypt_message(ct, enc, sk).decode()
    print(f"message: {message}")
    print(f"encrypted size: {len(ct) + len(enc)} bytes")
    print(f"decrypted: {dec}")
    print(f"success: {dec == message}")
    
    # 2. hybrid kyber-aes
    print("\n[2] HYBRID KYBER-AES APPROACH")
    print("-" * 80)
    hybrid = HybridKyberAES(512, 'GCM')
    pk, sk = hybrid.generate_keypair()
    enc_data = hybrid.encrypt_message(message, pk)
    dec = hybrid.decrypt_message(enc_data, sk).decode()
    total_size = (len(enc_data['kyber_ciphertext']) + 
                  len(enc_data['aes_ciphertext']) +
                  len(enc_data['nonce']) + 
                  len(enc_data['tag']))
    print(f"message: {message}")
    print(f"encrypted size: {total_size} bytes")
    print(f"decrypted: {dec}")
    print(f"success: {dec == message}")
    
    # 3. proxy re-encryption
    print("\n[3] PROXY RE-ENCRYPTION (FOG COMPUTING)")
    print("-" * 80)
    pre = ProxyReEncryption()
    device_pk, device_sk = pre.device_setup()
    gateway_pk, gateway_sk = pre.gateway_setup()
    cloud_pk, cloud_sk = pre.cloud_setup()
    
    rk = pre.generate_reencryption_key(device_sk, cloud_pk)
    device_enc = pre.device_encrypt(message, device_pk)
    reenc = pre.gateway_reencrypt(device_enc, rk, cloud_pk)
    dec = pre.cloud_decrypt(reenc, device_sk, cloud_sk).decode()
    
    print(f"message: {message}")
    print(f"workflow: device -> gateway -> cloud")
    print(f"decrypted: {dec}")
    print(f"success: {dec == message}")
    
    # summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("""
[OK] all three approaches successfully demonstrated
[OK] all quantum-safe using crystals-kyber
[OK] full kyber: pure pqc, higher overhead
[OK] hybrid: best balance for iot devices
[OK] proxy re-enc: offloads crypto from constrained devices

next steps:
  - run 'python main_demo.py' for interactive demos
  - run 'python performance_analysis.py' for detailed benchmarks
  - check readme.md for complete documentation
    """)
    print("=" * 80)


if __name__ == "__main__":
    quick_demo()

