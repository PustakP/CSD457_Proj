"""
hybrid kyber-aes impl for iot
uses kyber for key exch, aes for bulk encryption
"""
import time
import tracemalloc
from kyber_py.kyber import Kyber512, Kyber768, Kyber1024
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad


class HybridKyberAES:
    """hybrid crypto: kyber kem for key exch + aes for msg enc"""
    
    def __init__(self, security_level=512, aes_mode='GCM'):
        """
        init hybrid crypto
        security_level: 512, 768, or 1024 for kyber
        aes_mode: 'GCM' (auth enc) or 'CBC' (basic)
        """
        # sel kyber variant
        if security_level == 512:
            self.kyber = Kyber512
        elif security_level == 768:
            self.kyber = Kyber768
        elif security_level == 1024:
            self.kyber = Kyber1024
        else:
            raise ValueError("sec lvl must be 512, 768, or 1024")
        
        self.security_level = security_level
        self.aes_mode = aes_mode
        self.public_key = None
        self.secret_key = None
        
    def generate_keypair(self):
        """gen kyber keypair"""
        self.public_key, self.secret_key = self.kyber.keygen()
        return self.public_key, self.secret_key
    
    def encrypt_message(self, message, recipient_pubkey):
        """
        encrypt msg using hybrid approach
        1. use kyber kem to est shared secret
        2. derive aes key from shared secret
        3. encrypt msg with aes
        """
        # kyber encaps - get shared secret
        shared_secret, kyber_ct = self.kyber.encaps(recipient_pubkey)
        
        # derive aes key from shared secret (use first 32 bytes for aes-256)
        aes_key = shared_secret[:32]
        
        # convert msg to bytes
        msg_bytes = message.encode() if isinstance(message, str) else message
        
        # encrypt with aes
        if self.aes_mode == 'GCM':
            # aes-gcm: auth enc with associated data
            cipher = AES.new(aes_key, AES.MODE_GCM)
            ciphertext, tag = cipher.encrypt_and_digest(msg_bytes)
            nonce = cipher.nonce
            
            # return kyber ct + nonce + tag + aes ct
            return {
                'kyber_ciphertext': kyber_ct,
                'nonce': nonce,
                'tag': tag,
                'aes_ciphertext': ciphertext
            }
        else:  # cbc mode
            # aes-cbc: basic enc with padding
            iv = get_random_bytes(AES.block_size)
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            padded_msg = pad(msg_bytes, AES.block_size)
            ciphertext = cipher.encrypt(padded_msg)
            
            return {
                'kyber_ciphertext': kyber_ct,
                'iv': iv,
                'aes_ciphertext': ciphertext
            }
    
    def decrypt_message(self, encrypted_data, secret_key=None):
        """
        decrypt msg using hybrid approach
        1. use kyber kem to recover shared secret
        2. derive aes key
        3. decrypt msg with aes
        """
        if secret_key is None:
            secret_key = self.secret_key
        
        # kyber decaps - recover shared secret
        shared_secret = self.kyber.decaps(secret_key, encrypted_data['kyber_ciphertext'])
        
        # derive aes key
        aes_key = shared_secret[:32]
        
        # decrypt with aes
        if self.aes_mode == 'GCM':
            cipher = AES.new(aes_key, AES.MODE_GCM, nonce=encrypted_data['nonce'])
            plaintext = cipher.decrypt_and_verify(
                encrypted_data['aes_ciphertext'],
                encrypted_data['tag']
            )
        else:  # cbc mode
            cipher = AES.new(aes_key, AES.MODE_CBC, encrypted_data['iv'])
            padded_plaintext = cipher.decrypt(encrypted_data['aes_ciphertext'])
            plaintext = unpad(padded_plaintext, AES.block_size)
        
        return plaintext
    
    def measure_performance(self, message_size=1024):
        """measure perf metrics for hybrid ops"""
        metrics = {
            'security_level': self.security_level,
            'aes_mode': self.aes_mode,
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
        
        # test msg
        test_msg = b'X' * message_size
        
        # measure encryption
        tracemalloc.start()
        start = time.perf_counter()
        enc_data = self.encrypt_message(test_msg, pk)
        enc_time = time.perf_counter() - start
        _, enc_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics['encrypt_time_ms'] = enc_time * 1000
        metrics['encrypt_memory_kb'] = enc_mem / 1024
        
        # calc total encrypted size
        total_size = len(enc_data['kyber_ciphertext']) + len(enc_data['aes_ciphertext'])
        if 'nonce' in enc_data:
            total_size += len(enc_data['nonce']) + len(enc_data['tag'])
        else:
            total_size += len(enc_data['iv'])
        
        metrics['kyber_ciphertext_size_bytes'] = len(enc_data['kyber_ciphertext'])
        metrics['aes_ciphertext_size_bytes'] = len(enc_data['aes_ciphertext'])
        metrics['total_encrypted_size_bytes'] = total_size
        
        # measure decryption
        tracemalloc.start()
        start = time.perf_counter()
        dec_msg = self.decrypt_message(enc_data, sk)
        dec_time = time.perf_counter() - start
        _, dec_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        metrics['decrypt_time_ms'] = dec_time * 1000
        metrics['decrypt_memory_kb'] = dec_mem / 1024
        
        # verify correctness
        metrics['decryption_successful'] = (dec_msg == test_msg)
        
        return metrics


def demo_hybrid():
    """demo hybrid kyber-aes encryption"""
    print("=" * 60)
    print("hybrid kyber-aes crypto demo")
    print("=" * 60)
    
    # test msg
    message = "hello from iot device! this is quantum-safe hybrid crypto!"
    print(f"\noriginal message: {message}")
    
    # init hybrid crypto with kyber512 + aes-gcm
    crypto = HybridKyberAES(security_level=512, aes_mode='GCM')
    
    # gen keys
    print("\ngenerating kyber keypair...")
    pk, sk = crypto.generate_keypair()
    print(f"public key size: {len(pk)} bytes")
    print(f"secret key size: {len(sk)} bytes")
    
    # encrypt
    print("\nencrypting message with hybrid approach...")
    enc_data = crypto.encrypt_message(message, pk)
    print(f"kyber ciphertext size: {len(enc_data['kyber_ciphertext'])} bytes")
    print(f"aes ciphertext size: {len(enc_data['aes_ciphertext'])} bytes")
    
    total_size = (len(enc_data['kyber_ciphertext']) + 
                  len(enc_data['aes_ciphertext']) +
                  len(enc_data['nonce']) + 
                  len(enc_data['tag']))
    print(f"total encrypted size: {total_size} bytes")
    
    # decrypt
    print("\ndecrypting message...")
    dec_msg = crypto.decrypt_message(enc_data, sk)
    dec_str = dec_msg.decode()
    print(f"decrypted message: {dec_str}")
    print(f"success: {dec_str == message}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo_hybrid()

