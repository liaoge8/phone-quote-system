from app.core.security import hash_password, verify_password

def test_scrypt_password_roundtrip():
    encoded = hash_password('a-strong-password')
    assert encoded.startswith('scrypt$')
    assert verify_password('a-strong-password', encoded)
    assert not verify_password('wrong-password', encoded)

def test_password_minimum_length():
    try:
        hash_password('short')
    except ValueError:
        return
    assert False, 'short passwords must be rejected'
