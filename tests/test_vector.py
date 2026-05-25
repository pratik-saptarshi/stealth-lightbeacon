from utils.vector import hash_token, make_vector

def test_hash_token_parity():
    # Ground truth values from Node's implementation
    assert hash_token("hello") == 1335831723
    assert hash_token("😊") == 3308370758
    assert hash_token("Stealth-Lightbeacon-Vector-Parity-Validation-String") == 2055787613

def test_make_vector_parity():
    # Testing make_vector against ground truth
    vec = make_vector("hello 😊 world", 8)
    assert vec == [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
