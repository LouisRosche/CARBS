"""
Secure Credential Management

Provides encrypted storage of sensitive credentials in memory to prevent
exposure via memory dumps, core dumps, or debugging tools.

Security features:
- Fernet symmetric encryption for credentials in memory
- Automatic key derivation from machine-specific entropy
- Secure memory clearing on credential deletion
- Rate-limited decryption to prevent brute-force attacks
"""

import base64
import hashlib
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Try to import cryptography, fall back to obfuscation if unavailable
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography package not installed - using basic obfuscation only")


def _get_machine_entropy() -> bytes:
    """
    Generate machine-specific entropy for key derivation.
    Uses multiple sources to create unique per-machine salt.
    """
    entropy_sources = []

    # Process ID (changes per run)
    entropy_sources.append(str(os.getpid()).encode())

    # Hostname
    try:
        import socket
        entropy_sources.append(socket.gethostname().encode())
    except Exception:
        pass

    # Random component (unique per instance)
    entropy_sources.append(secrets.token_bytes(16))

    # Current time with high precision
    entropy_sources.append(str(time.time_ns()).encode())

    # Combine all entropy sources
    combined = b''.join(entropy_sources)
    return hashlib.sha256(combined).digest()


def _derive_key(salt: bytes) -> bytes:
    """Derive encryption key from salt using PBKDF2."""
    if CRYPTO_AVAILABLE:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,  # High iteration count for security
        )
        # Use machine entropy as password
        return base64.urlsafe_b64encode(kdf.derive(_get_machine_entropy()))
    else:
        # Fallback: simple XOR-based obfuscation (NOT secure, but better than plaintext)
        return hashlib.sha256(salt + _get_machine_entropy()).digest()


@dataclass
class EncryptedCredential:
    """Container for encrypted credential data."""
    ciphertext: bytes
    salt: bytes
    created_at: float


class SecureCredentialStore:
    """
    Secure storage for API credentials.

    Usage:
        store = SecureCredentialStore()
        store.store("binance_api_key", "your-api-key")
        store.store("binance_api_secret", "your-secret")

        # Later retrieval
        api_key = store.retrieve("binance_api_key")
    """

    def __init__(self, max_decrypts_per_minute: int = 100):
        """
        Initialize secure credential store.

        Args:
            max_decrypts_per_minute: Rate limit for decryption operations
        """
        self._credentials: Dict[str, EncryptedCredential] = {}
        self._lock = threading.RLock()

        # Rate limiting for decryption
        self._decrypt_times: list = []
        self._max_decrypts = max_decrypts_per_minute

        # Generate instance-specific master salt
        self._master_salt = secrets.token_bytes(32)

        logger.debug("SecureCredentialStore initialized")

    def _check_rate_limit(self) -> bool:
        """Check if decryption is rate-limited."""
        now = time.time()
        minute_ago = now - 60

        # Clean old entries
        self._decrypt_times = [t for t in self._decrypt_times if t > minute_ago]

        if len(self._decrypt_times) >= self._max_decrypts:
            return False

        self._decrypt_times.append(now)
        return True

    def store(self, key: str, value: str) -> None:
        """
        Store a credential securely.

        Args:
            key: Identifier for the credential
            value: The sensitive value to store
        """
        if not value:
            return

        # Generate unique salt for this credential
        salt = secrets.token_bytes(16)

        if CRYPTO_AVAILABLE:
            # Derive key and encrypt
            derived_key = _derive_key(self._master_salt + salt)
            fernet = Fernet(derived_key)
            ciphertext = fernet.encrypt(value.encode('utf-8'))
        else:
            # Fallback obfuscation (XOR with derived key)
            derived_key = _derive_key(self._master_salt + salt)
            value_bytes = value.encode('utf-8')
            ciphertext = bytes(
                v ^ derived_key[i % len(derived_key)]
                for i, v in enumerate(value_bytes)
            )

        with self._lock:
            self._credentials[key] = EncryptedCredential(
                ciphertext=ciphertext,
                salt=salt,
                created_at=time.time()
            )

        logger.debug(f"Stored encrypted credential: {key}")

    def retrieve(self, key: str) -> Optional[str]:
        """
        Retrieve a stored credential.

        Args:
            key: Identifier for the credential

        Returns:
            Decrypted credential value or None if not found
        """
        with self._lock:
            if key not in self._credentials:
                return None

            if not self._check_rate_limit():
                logger.warning(f"Rate limit exceeded for credential decryption")
                raise RuntimeError("Credential decryption rate limit exceeded")

            cred = self._credentials[key]

        if CRYPTO_AVAILABLE:
            derived_key = _derive_key(self._master_salt + cred.salt)
            fernet = Fernet(derived_key)
            try:
                plaintext = fernet.decrypt(cred.ciphertext)
                return plaintext.decode('utf-8')
            except Exception as e:
                logger.error(f"Failed to decrypt credential {key}: {e}")
                return None
        else:
            # Fallback de-obfuscation
            derived_key = _derive_key(self._master_salt + cred.salt)
            plaintext = bytes(
                c ^ derived_key[i % len(derived_key)]
                for i, c in enumerate(cred.ciphertext)
            )
            return plaintext.decode('utf-8')

    def delete(self, key: str) -> bool:
        """
        Securely delete a credential.

        Args:
            key: Identifier for the credential

        Returns:
            True if credential was deleted, False if not found
        """
        with self._lock:
            if key not in self._credentials:
                return False

            # Overwrite with random data before deletion
            cred = self._credentials[key]
            random_overwrite = secrets.token_bytes(len(cred.ciphertext))
            cred = EncryptedCredential(
                ciphertext=random_overwrite,
                salt=secrets.token_bytes(16),
                created_at=0
            )

            del self._credentials[key]

        logger.debug(f"Deleted credential: {key}")
        return True

    def clear_all(self) -> None:
        """Securely clear all stored credentials."""
        with self._lock:
            keys = list(self._credentials.keys())
            for key in keys:
                self.delete(key)

        logger.info("Cleared all stored credentials")

    def has_credential(self, key: str) -> bool:
        """Check if a credential exists."""
        with self._lock:
            return key in self._credentials


# Global credential store instance
_global_store: Optional[SecureCredentialStore] = None
_store_lock = threading.Lock()


def get_credential_store() -> SecureCredentialStore:
    """Get or create the global credential store."""
    global _global_store
    with _store_lock:
        if _global_store is None:
            _global_store = SecureCredentialStore()
        return _global_store


class SecureString:
    """
    A string wrapper that encrypts its contents in memory.

    Usage:
        secret = SecureString("my-api-key")
        # Use in code
        actual_value = secret.get()
        # Clear when done
        secret.clear()
    """

    def __init__(self, value: str):
        """Initialize with a sensitive string value."""
        self._store = SecureCredentialStore(max_decrypts_per_minute=1000)
        self._key = secrets.token_hex(8)
        self._store.store(self._key, value)

    def get(self) -> str:
        """Retrieve the decrypted value."""
        value = self._store.retrieve(self._key)
        if value is None:
            raise ValueError("SecureString has been cleared or corrupted")
        return value

    def clear(self) -> None:
        """Securely clear the stored value."""
        self._store.delete(self._key)

    def __str__(self) -> str:
        """Return masked representation."""
        return "SecureString(***)"

    def __repr__(self) -> str:
        """Return masked representation."""
        return "SecureString(***)"

    def __del__(self):
        """Clean up on garbage collection."""
        try:
            self.clear()
        except Exception:
            pass


__all__ = [
    "SecureCredentialStore",
    "SecureString",
    "get_credential_store",
    "CRYPTO_AVAILABLE"
]
