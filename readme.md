# Quantum-Safe Cryptography for IoT Devices

A comprehensive demonstration and performance analysis of post-quantum cryptographic approaches for resource-constrained IoT devices using **CRYSTALS-Kyber** (NIST Round 3 PQC selection).

## Overview

This project explores quantum-resistant encryption for IoT environments by implementing and comparing three approaches:

1. **Full Kyber Encryption** - Pure Kyber KEM-based encryption
2. **Hybrid Kyber-AES** - Kyber for key exchange + AES for bulk encryption
3. **Proxy Re-Encryption** - Fog computing architecture for ultra-constrained devices

## Background

CRYSTALS-Kyber was selected by NIST in Round 3 for standardization as a post-quantum key encapsulation mechanism (KEM). This project evaluates its practicality for IoT deployment considering computational constraints.

**References:**
- [Official Kyber Implementation (C)](https://github.com/pq-crystals/kyber)
- [Python Implementation (kyber-py)](https://github.com/GiacomoPope/kyber-py)

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  IoT Device     │────▶│  Fog Gateway    │────▶│  Cloud Server   │
│  (Constrained)  │     │  (Re-Encrypt)   │     │  (Full Crypto)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Project Structure

```
iotproj/
├── requirements.txt              # python dependencies
├── full_kyber.py                 # pure kyber implementation
├── hybrid_kyber_aes.py           # kyber kem + aes encryption
├── proxy_reencryption.py         # fog computing proxy re-enc
├── performance_analysis.py       # benchmarking & analysis tools
├── main_demo.py                  # interactive demo
├── readme.md                     # this file
└── hardware/                     # hardware demo files
    ├── SETUP_GUIDE.md            # complete setup instructions
    ├── QUICK_REFERENCE.md        # demo day cheat sheet
    ├── arduino/
    │   └── button_demo/          # button-triggered demo sketch
    └── raspberry_pi/
        ├── live_demo.py          # ★ ssh live updating demo
        ├── fog_gateway.py        # fog gateway implementation
        └── cloud_server.py       # cloud server simulation
```

## Installation

```bash
# clone or navigate to project directory
cd iotproj

# install dependencies
pip install -r requirements.txt
```

**Dependencies:**
- `kyber-py>=0.3.0` - Pure Python Kyber implementation
- `pycryptodome>=3.19.0` - AES encryption

## Usage

### Quick Start

Run the interactive demo:

```bash
python main_demo.py
```

### Hardware Demo (Arduino + Raspberry Pi)

For a physical demonstration with button-triggered proxy re-encryption:

```bash
# ssh into raspberry pi
ssh pi@raspberrypi.local

# run the live demo
cd ~/iot_kyber && source venv/bin/activate
python live_demo.py

# press button on arduino → watch pqc encryption happen live!
```

See `hardware/SETUP_GUIDE.md` for full hardware setup instructions.
See `hardware/QUICK_REFERENCE.md` for demo day cheat sheet.

### Individual Demos

#### 1. Full Kyber Encryption
```bash
python full_kyber.py
```
- Pure Kyber KEM for encryption
- Quantum-safe but computationally intensive
- Best for: Capable IoT devices, fog gateways, cloud servers

#### 2. Hybrid Kyber-AES
```bash
python hybrid_kyber_aes.py
```
- Kyber KEM for key exchange
- AES-GCM for message encryption
- Best for: Balance of security and performance

#### 3. Proxy Re-Encryption
```bash
python proxy_reencryption.py
```
- Device → Gateway → Cloud architecture
- Gateway transforms encryption without decryption
- Best for: Very constrained devices (Class 0/1)

#### 4. Performance Analysis
```bash
python performance_analysis.py
```
- Comprehensive benchmarking
- Device suitability analysis
- Comparison reports
- Saves results to `performance_results.json`

## Features

### Full Kyber Module (`full_kyber.py`)
- Kyber-512/768/1024 support
- Key generation and encapsulation
- Performance measurement utilities
- Memory and timing profiling

### Hybrid Kyber-AES Module (`hybrid_kyber_aes.py`)
- Kyber KEM + AES-256 encryption
- Support for AES-GCM (authenticated) and AES-CBC modes
- Efficient bulk encryption
- Reduced computational overhead

### Proxy Re-Encryption Module (`proxy_reencryption.py`)
- Three-party architecture (Device → Gateway → Cloud)
- Gateway re-encryption without plaintext access
- Suitable for fog computing scenarios
- Offloads crypto operations from constrained devices

### Performance Analysis Module (`performance_analysis.py`)
- Benchmarks all approaches across multiple parameters
- Device suitability classification:
  - **Class 0**: Very constrained (10KB RAM, 100KB storage)
  - **Class 1**: Constrained (80KB RAM, 512KB storage)
  - **Class 2**: Capable (512KB RAM, 4MB storage)
  - **Fog Gateway**: Edge computing (2MB RAM)
  - **Cloud Server**: No constraints
- Generates comparison reports and recommendations

## Performance Metrics

The analysis measures:
- **Timing**: Key generation, encryption, decryption latency
- **Memory**: Peak RAM usage during operations
- **Storage**: Public/private key sizes, ciphertext overhead

## Key Findings

### Recommended Approaches by Device Class

| Device Class | RAM | Recommendation | Rationale |
|-------------|-----|----------------|-----------|
| **Class 0** (Sensors) | 10KB | Proxy Re-Encryption | Offload crypto to gateway |
| **Class 1** (ESP8266) | 80KB | Hybrid Kyber-512 + AES | Borderline feasible, optimize |
| **Class 2+** (ESP32, RPi Zero) | 512KB+ | Hybrid Kyber-512 + AES-GCM | Good balance |
| **Fog Gateway** | 2MB+ | Kyber-768 + Proxy | Handle device offloading |
| **Cloud Server** | 8GB+ | Kyber-1024 | Maximum security |

### Performance Comparison (Kyber-512, 1KB message)

| Metric | Full Kyber | Hybrid (Kyber+AES) | Winner |
|--------|------------|-------------------|---------|
| Encryption Time | ~Higher | ~Lower | Hybrid |
| Memory Usage | ~Higher | ~Lower | Hybrid |
| Ciphertext Size | Larger | Smaller | Hybrid |
| Quantum Safety | ✓ | ✓ | Tie |

## Implementation Details

### Security Levels

- **Kyber-512**: ~AES-128 security, smallest keys/ciphertext
- **Kyber-768**: ~AES-192 security, balanced
- **Kyber-1024**: ~AES-256 security, maximum security

### Cryptographic Primitives

- **KEM**: Kyber (lattice-based, quantum-resistant)
- **Symmetric**: AES-256-GCM (authenticated encryption)
- **Hash**: SHA-256 (for key derivation)

### Design Choices

1. **Hybrid Approach**: Combines quantum-safe key exchange with efficient symmetric crypto
2. **Lightweight**: Prioritizes Kyber-512 for resource-constrained devices
3. **Modular**: Separate implementations for easy comparison
4. **Measurable**: Built-in performance profiling

## Limitations & Future Work

### Current Limitations
- **Simplified Proxy Re-Encryption**: Demo implementation, not production-grade
- **Python Performance**: C implementation would be faster
- **Single-threaded**: No async/parallel processing
- **Demo Purpose**: Simplified for educational use

### Future Enhancements
- [ ] Integrate production-grade PRE (e.g., Umbral)
- [ ] Hardware acceleration (AES-NI, ARM crypto extensions)
- [ ] Power consumption measurements
- [ ] Network overhead analysis
- [ ] C/Rust implementation for embedded targets
- [ ] MQTT/CoAP protocol integration

## Contributing

This is a demonstration/research project. Suggestions and improvements welcome!

## Security Notice

⚠️ **This is a demonstration project.** For production use:
- Use audited cryptographic libraries
- Implement proper key management
- Add authentication and integrity checks
- Consider side-channel attack mitigations
- Follow NIST PQC standards as they finalize

## References

1. [NIST Post-Quantum Cryptography Standardization](https://csrc.nist.gov/projects/post-quantum-cryptography)
2. [CRYSTALS-Kyber Official Repository](https://github.com/pq-crystals/kyber)
3. [kyber-py Implementation](https://github.com/GiacomoPope/kyber-py)
4. [NIST ML-KEM (FIPS 203)](https://csrc.nist.gov/pubs/fips/203/final)

## License

This project is for educational and research purposes. Check individual library licenses:
- kyber-py: MIT License
- PyCryptodome: BSD License

---

**Author**: Pustak Pathak
**Date**: 2025  
