import hashlib
import hmac
import base64
from typing import Tuple

def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def _b64u_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))

def sign_download_token(file_id: int, exp_unix: int, secret: str) -> str:
    """
    token = base64url("file_id:exp").base64url(hmac_sha256(payload))
    """
    payload = f"{file_id}:{exp_unix}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{_b64u_encode(payload)}.{_b64u_encode(sig)}"

def verify_download_token(token: str, secret: str) -> Tuple[int, int]:
    """
    return (file_id, exp_unix) if valid, else raise ValueError
    """
    if "." not in token:
        raise ValueError("bad token")
    p1, p2 = token.split(".", 1)
    payload = _b64u_decode(p1)
    sig = _b64u_decode(p2)

    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("bad signature")

    text = payload.decode("utf-8")
    fid_s, exp_s = text.split(":", 1)
    return int(fid_s), int(exp_s)

