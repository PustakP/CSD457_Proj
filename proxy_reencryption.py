"""
proxy re-encryption for fog computing gateway
allows gateway to transform enc data from one key to another w/o decryption
"""
import time
import tracemalloc
from kyber_py.kyber import Kyber512
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import hashlib


class ProxyReEncryption:
    """
    simplified proxy re-enc scheme for fog computing
    iot device -> fog gateway -> cloud server
    gateway can re-encrypt w/o seeing plaintext
    """
    
    def __init__(self):
        """init proxy re-enc using kyber512"""
        self.kyber = Kyber512
        
    def device_setup(self):
        """iot device gen keys"""
        device_pk, device_sk = self.kyber.keygen()
        return device_pk, device_sk
    
    def gateway_setup(self):
        """fog gateway gen keys"""
        gateway_pk, gateway_sk = self.kyber.keygen()
        return gateway_pk, gateway_sk
    
    def cloud_setup(self):
        """cloud server gen keys"""
        cloud_pk, cloud_sk = self.kyber.keygen()
        return cloud_pk, cloud_sk
    
    def generate_reencryption_key(self, device_sk, cloud_pk):
        """
        gen re-enc key allowing gateway to transform
        device-encrypted data -> cloud-encrypted data
        simplified: use device sk + cloud pk to derive re-enc key
        """
        # in practice, this would be more sophisticated
        # here we use a simple derivation for demo purposes
        
        # derive shared secret with cloud
        cloud_ss, cloud_ct = self.kyber.encaps(cloud_pk)
        
        # combine with device info (simplified)
        # real impl would use proper key derivation
        rk = {
            'cloud_ciphertext': cloud_ct,
            'device_secret_hash': hashlib.sha256(device_sk).digest()[:32]
        }
        
        return rk
    
    def device_encrypt(self, message, device_pk):
        """iot device encrypts data"""
        # use kyber kem + aes
        shared_secret, kyber_ct = self.kyber.encaps(device_pk)
        
        # derive aes key
        aes_key = shared_secret[:32]
        
        # encrypt msg
        msg_bytes = message.encode() if isinstance(message, str) else message
        cipher = AES.new(aes_key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(msg_bytes)
        
        return {
            'kyber_ct': kyber_ct,
            'nonce': cipher.nonce,
            'tag': tag,
            'aes_ct': ciphertext
        }
    
    def gateway_reencrypt(self, device_encrypted, reencryption_key, cloud_pk):
        """
        fog gateway re-encrypts data for cloud
        transforms device-enc -> cloud-enc w/o seeing plaintext
        
        note: this is simplified proxy re-enc for demo
        real impl would use more advanced cryptographic primitives
        """
        # for demo: gateway re-wraps the data using cloud's key
        # in production, use proper pre like umbral or similar
        
        # extract encrypted aes key material
        device_kyber_ct = device_encrypted['kyber_ct']
        
        # create new encryption for cloud
        cloud_ss, cloud_kyber_ct = self.kyber.encaps(cloud_pk)
        cloud_aes_key = cloud_ss[:32]
        
        # re-wrap the aes ciphertext
        # (in real pre, this would be done via proxy key operations)
        cipher = AES.new(cloud_aes_key, AES.MODE_GCM)
        
        # for demo: re-encrypt the original aes ct + metadata
        combined_data = (device_encrypted['aes_ct'] + 
                        device_encrypted['nonce'] + 
                        device_encrypted['tag'])
        
        reenc_ct, reenc_tag = cipher.encrypt_and_digest(combined_data)
        
        return {
            'cloud_kyber_ct': cloud_kyber_ct,
            'reenc_nonce': cipher.nonce,
            'reenc_tag': reenc_tag,
            'reenc_ct': reenc_ct,
            'original_device_ct': device_kyber_ct  # kept for audit trail
        }
    
    def cloud_decrypt(self, reencrypted_data, device_sk, cloud_sk):
        """
        cloud decrypts re-encrypted data
        requires cloud sk to unwrap, then device sk to decrypt original
        """
        # first, unwrap with cloud key
        cloud_ss = self.kyber.decaps(cloud_sk, reencrypted_data['cloud_kyber_ct'])
        cloud_aes_key = cloud_ss[:32]
        
        cipher = AES.new(cloud_aes_key, AES.MODE_GCM, 
                        nonce=reencrypted_data['reenc_nonce'])
        combined_data = cipher.decrypt_and_verify(
            reencrypted_data['reenc_ct'],
            reencrypted_data['reenc_tag']
        )
        
        # extract original encryption components
        # parse back the components (this is simplified)
        aes_ct_len = len(combined_data) - 16 - 16  # minus nonce and tag
        original_aes_ct = combined_data[:aes_ct_len]
        original_nonce = combined_data[aes_ct_len:aes_ct_len+16]
        original_tag = combined_data[aes_ct_len+16:]
        
        # now decrypt original with device key
        device_ss = self.kyber.decaps(device_sk, reencrypted_data['original_device_ct'])
        device_aes_key = device_ss[:32]
        
        cipher = AES.new(device_aes_key, AES.MODE_GCM, nonce=original_nonce)
        plaintext = cipher.decrypt_and_verify(original_aes_ct, original_tag)
        
        return plaintext
    
    def measure_performance(self, message_size=1024):
        """measure perf of proxy re-enc workflow"""
        metrics = {
            'message_size_bytes': message_size
        }
        
        # setup
        device_pk, device_sk = self.device_setup()
        gateway_pk, gateway_sk = self.gateway_setup()
        cloud_pk, cloud_sk = self.cloud_setup()
        
        # gen re-enc key
        start = time.perf_counter()
        rk = self.generate_reencryption_key(device_sk, cloud_pk)
        metrics['rekey_gen_time_ms'] = (time.perf_counter() - start) * 1000
        
        # device encryption
        test_msg = b'X' * message_size
        tracemalloc.start()
        start = time.perf_counter()
        device_enc = self.device_encrypt(test_msg, device_pk)
        device_enc_time = time.perf_counter() - start
        _, device_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics['device_encrypt_time_ms'] = device_enc_time * 1000
        metrics['device_encrypt_memory_kb'] = device_mem / 1024
        metrics['device_encrypted_size_bytes'] = (
            len(device_enc['kyber_ct']) + 
            len(device_enc['aes_ct']) +
            len(device_enc['nonce']) + 
            len(device_enc['tag'])
        )
        
        # gateway re-encryption
        tracemalloc.start()
        start = time.perf_counter()
        reenc_data = self.gateway_reencrypt(device_enc, rk, cloud_pk)
        reenc_time = time.perf_counter() - start
        _, gateway_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics['gateway_reencrypt_time_ms'] = reenc_time * 1000
        metrics['gateway_reencrypt_memory_kb'] = gateway_mem / 1024
        metrics['reencrypted_size_bytes'] = (
            len(reenc_data['cloud_kyber_ct']) +
            len(reenc_data['reenc_ct']) +
            len(reenc_data['reenc_nonce']) +
            len(reenc_data['reenc_tag']) +
            len(reenc_data['original_device_ct'])
        )
        
        # cloud decryption
        tracemalloc.start()
        start = time.perf_counter()
        plaintext = self.cloud_decrypt(reenc_data, device_sk, cloud_sk)
        cloud_dec_time = time.perf_counter() - start
        _, cloud_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics['cloud_decrypt_time_ms'] = cloud_dec_time * 1000
        metrics['cloud_decrypt_memory_kb'] = cloud_mem / 1024
        metrics['decryption_successful'] = (plaintext == test_msg)
        
        # total workflow time
        metrics['total_workflow_time_ms'] = (
            metrics['device_encrypt_time_ms'] +
            metrics['gateway_reencrypt_time_ms'] +
            metrics['cloud_decrypt_time_ms']
        )
        
        return metrics


def demo_proxy_reencryption():
    """demo proxy re-enc for fog computing"""
    print("=" * 60)
    print("proxy re-encryption for fog computing demo")
    print("=" * 60)
    
    pre = ProxyReEncryption()
    
    # setup all parties
    print("\nsetting up iot device, fog gateway, and cloud server...")
    device_pk, device_sk = pre.device_setup()
    gateway_pk, gateway_sk = pre.gateway_setup()
    cloud_pk, cloud_sk = pre.cloud_setup()
    print("✓ all parties initialized")
    
    # device generates re-enc key for gateway
    print("\ngenerating re-encryption key...")
    rk = pre.generate_reencryption_key(device_sk, cloud_pk)
    print("✓ re-encryption key created")
    
    # device encrypts data
    message = "sensor data: temperature=25.3C, humidity=60%"
    print(f"\niot device encrypting: {message}")
    device_enc = pre.device_encrypt(message, device_pk)
    print(f"✓ encrypted by device ({len(device_enc['aes_ct'])} bytes)")
    
    # gateway re-encrypts for cloud
    print("\nfog gateway re-encrypting for cloud...")
    reenc_data = pre.gateway_reencrypt(device_enc, rk, cloud_pk)
    print(f"✓ re-encrypted by gateway ({len(reenc_data['reenc_ct'])} bytes)")
    
    # cloud decrypts
    print("\ncloud server decrypting...")
    plaintext = pre.cloud_decrypt(reenc_data, device_sk, cloud_sk)
    plaintext_str = plaintext.decode()
    print(f"✓ decrypted: {plaintext_str}")
    print(f"success: {plaintext_str == message}")
    
    print("\n" + "=" * 60)
    print("fog computing workflow: device -> gateway -> cloud")
    print("gateway transformed encryption w/o seeing plaintext!")
    print("=" * 60)


if __name__ == "__main__":
    demo_proxy_reencryption()

