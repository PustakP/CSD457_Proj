"""
full kyber impl for iot - uses kyber for all encryption
"""
import time
import tracemalloc
from kyber_py.kyber import Kyber512, Kyber768, Kyber1024


class FullKyberCrypto:
    """pure kyber crypto - kem for key exch + direct msg enc"""
    
    def __init__(self, security_level=512):
        """init with sec level: 512, 768, or 1024"""
        # sel appropriate kyber variant
        if security_level == 512:
            self.kyber = Kyber512
        elif security_level == 768:
            self.kyber = Kyber768
        elif security_level == 1024:
            self.kyber = Kyber1024
        else:
            raise ValueError("sec lvl must be 512, 768, or 1024")
        
        self.security_level = security_level
        self.public_key = None
        self.secret_key = None
        self.shared_secret = None
        
    def generate_keypair(self):
        """gen kyber keypair"""
        self.public_key, self.secret_key = self.kyber.keygen()
        return self.public_key, self.secret_key
    
    def encapsulate(self, public_key=None):
        """enc shared secret using pub key"""
        if public_key is None:
            public_key = self.public_key
        
        # kyber kem - gen shared secret + ciphertext
        shared_secret, ciphertext = self.kyber.encaps(public_key)
        return ciphertext, shared_secret
    
    def decapsulate(self, ciphertext, secret_key=None):
        """dec shared secret using priv key"""
        if secret_key is None:
            secret_key = self.secret_key
        
        # kyber kem decaps
        shared_secret = self.kyber.decaps(secret_key, ciphertext)
        return shared_secret
    
    def encrypt_message(self, message, recipient_pubkey):
        """
        'encrypt' msg using kyber kem approach
        note: kyber is kem not enc scheme, so we use shared secret as key
        """
        # enc kem to get shared secret
        ct, ss = self.encapsulate(recipient_pubkey)
        
        # simple xor enc with shared secret (demo only - not secure for prod)
        # in practice, use ss as key for aes or similar
        msg_bytes = message.encode() if isinstance(message, str) else message
        
        # pad/trunc shared secret to match msg len
        key_stream = (ss * ((len(msg_bytes) // len(ss)) + 1))[:len(msg_bytes)]
        encrypted = bytes(a ^ b for a, b in zip(msg_bytes, key_stream))
        
        return ct, encrypted
    
    def decrypt_message(self, ciphertext, encrypted_msg, secret_key=None):
        """decrypt msg using kyber kem"""
        # decaps to get shared secret
        ss = self.decapsulate(ciphertext, secret_key)
        
        # xor dec with shared secret
        key_stream = (ss * ((len(encrypted_msg) // len(ss)) + 1))[:len(encrypted_msg)]
        decrypted = bytes(a ^ b for a, b in zip(encrypted_msg, key_stream))
        
        return decrypted
    
    def measure_performance(self, message_size=1024):
        """measure perf metrics for kyber ops"""
        metrics = {
            'security_level': self.security_level,
            'message_size_bytes': message_size
        }
        
        # measure keygen
        tracemalloc.start()
        start = time.perf_counter()
        pk, sk = self.generate_keypair()
        keygen_time = time.perf_counter() - start
        _, keygen_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics['keygen_time_ms'] = keygen_time * 1000
        metrics['keygen_memory_kb'] = keygen_mem / 1024
        metrics['public_key_size_bytes'] = len(pk)
        metrics['secret_key_size_bytes'] = len(sk)
        
        # measure encaps
        tracemalloc.start()
        start = time.perf_counter()
        ct, ss = self.encapsulate(pk)
        encap_time = time.perf_counter() - start
        _, encap_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics['encapsulate_time_ms'] = encap_time * 1000
        metrics['encapsulate_memory_kb'] = encap_mem / 1024
        metrics['ciphertext_size_bytes'] = len(ct)
        metrics['shared_secret_size_bytes'] = len(ss)
        
        # measure decaps
        tracemalloc.start()
        start = time.perf_counter()
        ss_dec = self.decapsulate(ct, sk)
        decap_time = time.perf_counter() - start
        _, decap_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics['decapsulate_time_ms'] = decap_time * 1000
        metrics['decapsulate_memory_kb'] = decap_mem / 1024
        
        # measure full enc/dec cycle with msg
        test_msg = b'X' * message_size
        
        tracemalloc.start()
        start = time.perf_counter()
        ct_msg, enc_msg = self.encrypt_message(test_msg, pk)
        enc_time = time.perf_counter() - start
        _, enc_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics['full_encrypt_time_ms'] = enc_time * 1000
        metrics['full_encrypt_memory_kb'] = enc_mem / 1024
        metrics['total_encrypted_size_bytes'] = len(ct_msg) + len(enc_msg)
        
        tracemalloc.start()
        start = time.perf_counter()
        dec_msg = self.decrypt_message(ct_msg, enc_msg, sk)
        dec_time = time.perf_counter() - start
        _, dec_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics['full_decrypt_time_ms'] = dec_time * 1000
        metrics['full_decrypt_memory_kb'] = dec_mem / 1024
        
        # verify correctness
        metrics['decryption_successful'] = (dec_msg == test_msg)
        
        return metrics


def demo_full_kyber():
    """demo full kyber encryption"""
    print("=" * 60)
    print("full kyber crypto demo")
    print("=" * 60)
    
    # test msg
    message = "hello from iot device! this is quantum-safe!"
    print(f"\noriginal message: {message}")
    
    # init kyber512 (lightest variant)
    crypto = FullKyberCrypto(security_level=512)
    
    # gen keys
    print("\ngenerating kyber keypair...")
    pk, sk = crypto.generate_keypair()
    print(f"public key size: {len(pk)} bytes")
    print(f"secret key size: {len(sk)} bytes")
    
    # encrypt
    print("\nencrypting message...")
    ct, enc_msg = crypto.encrypt_message(message, pk)
    print(f"ciphertext size: {len(ct)} bytes")
    print(f"encrypted msg size: {len(enc_msg)} bytes")
    print(f"total encrypted size: {len(ct) + len(enc_msg)} bytes")
    
    # decrypt
    print("\ndecrypting message...")
    dec_msg = crypto.decrypt_message(ct, enc_msg, sk)
    dec_str = dec_msg.decode()
    print(f"decrypted message: {dec_str}")
    print(f"success: {dec_str == message}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo_full_kyber()

