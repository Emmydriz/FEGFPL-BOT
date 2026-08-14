import base64
import hashlib
from cryptography.fernet import Fernet
from config.settings import settings


def _get_fernet_key() -> bytes:
    # Generate a deterministic 32-byte Fernet key from settings.SECRET_KEY
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_string(plain_text: str) -> str:
    if not plain_text:
        return ""
    f = Fernet(_get_fernet_key())
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_string(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    try:
        f = Fernet(_get_fernet_key())
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        return "[ENCRYPTION_ERROR]"


def mask_account_number(account_number: str) -> str:
    if not account_number or len(account_number) < 4:
        return "••••"
    return f"••••{account_number[-4:]}"
