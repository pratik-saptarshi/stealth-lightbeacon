import struct
import re
import math

def get_utf16_code_units(text: str) -> list:
    """Converts a Python string into a list of UTF-16 code units (emulating JS behavior)."""
    encoded = text.encode("utf-16-le")
    num_shorts = len(encoded) // 2
    return list(struct.unpack(f"<{num_shorts}H", encoded))

def hash_token(token: str) -> int:
    """Custom FNV-like 32-bit token hashing with JS-compatible arithmetic."""
    hash_val = 2166136261
    units = get_utf16_code_units(token)
    for unit in units:
        hash_val ^= unit
        term1 = (hash_val << 1) & 0xFFFFFFFF
        term2 = (hash_val << 4) & 0xFFFFFFFF
        term3 = (hash_val << 7) & 0xFFFFFFFF
        term4 = (hash_val << 8) & 0xFFFFFFFF
        term5 = (hash_val << 24) & 0xFFFFFFFF
        hash_val = (hash_val + term1 + term2 + term3 + term4 + term5) & 0xFFFFFFFF
    return hash_val

def make_vector(text: str, dimensions: int) -> list:
    """Generates a normalized cosine frequency vector compatible with JS implementation."""
    vector = [0.0] * dimensions
    cleaned = text.lower()
    cleaned = re.sub(r'[^a-z0-9\s]+', ' ', cleaned)
    tokens = [t for t in cleaned.split() if t]
    
    for token in tokens:
        idx = hash_token(token) % dimensions
        vector[idx] += 1.0
        
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude == 0.0:
        return vector
        
    return [round(v / magnitude, 6) for v in vector]
