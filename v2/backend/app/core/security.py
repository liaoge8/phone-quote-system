import base64, hashlib, hmac, secrets, time
import jwt
from app.core.config import settings

def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError('密码至少需要 10 位')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=settings.scrypt_n, r=settings.scrypt_r, p=settings.scrypt_p, dklen=64)
    enc = lambda b: base64.urlsafe_b64encode(b).decode().rstrip('=')
    return f'scrypt${settings.scrypt_n}${settings.scrypt_r}${settings.scrypt_p}${enc(salt)}${enc(digest)}'

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, digest_text = encoded.split('$')
        if algorithm != 'scrypt': return False
        dec = lambda s: base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))
        expected = dec(digest_text)
        actual = hashlib.scrypt(password.encode(), salt=dec(salt_text), n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def create_access_token(user_id: int, role: str, token_epoch: int) -> str:
    now = int(time.time())
    return jwt.encode({'uid': user_id, 'role': role, 'ep': token_epoch, 'iat': now, 'exp': now + settings.access_token_expire_minutes * 60}, settings.secret_key, algorithm='HS256')

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=['HS256'])
