"""
Secrets Management and Encryption

Uses Fernet symmetric encryption (AES-128-CBC with HMAC) for:
- API keys at rest
- Configuration secrets
- Sensitive runtime data

Key derivation uses PBKDF2 with 480,000 iterations (OWASP 2023 recommendation)
"""

import os
import json
import base64
import hashlib
import secrets
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption/decryption fails"""
    pass


class SecretsManager:
    """
    Manages encrypted secrets with secure key derivation

    Security features:
    - PBKDF2 key derivation (480k iterations)
    - Fernet encryption (AES-128-CBC + HMAC)
    - Secure key storage recommendations
    - Automatic key rotation support
    """

    ITERATIONS = 480_000  # OWASP 2023 recommendation
    SALT_LENGTH = 32

    def __init__(self, master_password: Optional[str] = None):
        """
        Initialize with master password or environment variable

        Args:
            master_password: Optional master password (prefer env var)
        """
        self._master_password = master_password or os.getenv('CARBS_MASTER_KEY')

        if not self._master_password:
            raise EncryptionError(
                "Master password required. Set CARBS_MASTER_KEY environment variable "
                "or pass master_password parameter."
            )

        self._salt_file = Path('data/.salt')
        self._secrets_file = Path('data/.secrets.enc')
        self._fernet: Optional[Fernet] = None
        self._secrets_cache: Dict[str, str] = {}

        self._initialize()

    def _initialize(self):
        """Initialize encryption key from master password"""
        # Ensure data directory exists
        self._salt_file.parent.mkdir(parents=True, exist_ok=True)

        # Load or generate salt
        if self._salt_file.exists():
            salt = self._salt_file.read_bytes()
        else:
            salt = secrets.token_bytes(self.SALT_LENGTH)
            self._salt_file.write_bytes(salt)
            # Secure file permissions (owner read/write only)
            os.chmod(self._salt_file, 0o600)
            logger.info("Generated new encryption salt")

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.ITERATIONS,
            backend=default_backend()
        )

        key = base64.urlsafe_b64encode(
            kdf.derive(self._master_password.encode())
        )
        self._fernet = Fernet(key)

        # Load existing secrets if present
        self._load_secrets()

    def _load_secrets(self):
        """Load and decrypt secrets from file"""
        if not self._secrets_file.exists():
            self._secrets_cache = {}
            return

        try:
            encrypted_data = self._secrets_file.read_bytes()
            decrypted = self._fernet.decrypt(encrypted_data)
            self._secrets_cache = json.loads(decrypted.decode())
            logger.debug(f"Loaded {len(self._secrets_cache)} secrets")
        except InvalidToken:
            raise EncryptionError(
                "Failed to decrypt secrets. Wrong master password or corrupted data."
            )
        except json.JSONDecodeError:
            raise EncryptionError("Corrupted secrets file")

    def _save_secrets(self):
        """Encrypt and save secrets to file"""
        data = json.dumps(self._secrets_cache).encode()
        encrypted = self._fernet.encrypt(data)
        self._secrets_file.write_bytes(encrypted)
        os.chmod(self._secrets_file, 0o600)

    def set_secret(self, key: str, value: str):
        """
        Store an encrypted secret

        Args:
            key: Secret identifier (e.g., 'binance_api_key')
            value: Secret value to encrypt
        """
        self._secrets_cache[key] = value
        self._save_secrets()
        logger.info(f"Secret '{key}' stored securely")

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a decrypted secret

        Args:
            key: Secret identifier
            default: Default value if not found

        Returns:
            Decrypted secret value or default
        """
        return self._secrets_cache.get(key, default)

    def delete_secret(self, key: str) -> bool:
        """
        Remove a secret

        Args:
            key: Secret identifier

        Returns:
            True if deleted, False if not found
        """
        if key in self._secrets_cache:
            del self._secrets_cache[key]
            self._save_secrets()
            logger.info(f"Secret '{key}' deleted")
            return True
        return False

    def list_secrets(self) -> list:
        """List all secret keys (not values)"""
        return list(self._secrets_cache.keys())

    def encrypt_value(self, value: str) -> str:
        """
        Encrypt a single value for external storage

        Args:
            value: Plaintext value

        Returns:
            Base64-encoded encrypted value
        """
        encrypted = self._fernet.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt_value(self, encrypted_value: str) -> str:
        """
        Decrypt a single value

        Args:
            encrypted_value: Base64-encoded encrypted value

        Returns:
            Decrypted plaintext
        """
        try:
            data = base64.urlsafe_b64decode(encrypted_value.encode())
            return self._fernet.decrypt(data).decode()
        except (InvalidToken, ValueError) as e:
            raise EncryptionError(f"Decryption failed: {e}")

    def rotate_key(self, new_password: str):
        """
        Rotate encryption key with new master password

        Args:
            new_password: New master password
        """
        # Decrypt all secrets with old key
        secrets_backup = dict(self._secrets_cache)

        # Generate new salt
        new_salt = secrets.token_bytes(self.SALT_LENGTH)

        # Derive new key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=new_salt,
            iterations=self.ITERATIONS,
            backend=default_backend()
        )

        new_key = base64.urlsafe_b64encode(
            kdf.derive(new_password.encode())
        )

        # Update state
        self._master_password = new_password
        self._salt_file.write_bytes(new_salt)
        self._fernet = Fernet(new_key)
        self._secrets_cache = secrets_backup

        # Re-encrypt with new key
        self._save_secrets()
        logger.warning("Encryption key rotated successfully")


@dataclass
class EncryptedConfig:
    """
    Configuration with encrypted sensitive fields

    Automatically encrypts/decrypts API keys and passwords
    """

    secrets_manager: SecretsManager

    def load_exchange_credentials(self, exchange: str) -> Dict[str, str]:
        """
        Load encrypted exchange credentials

        Args:
            exchange: Exchange name (e.g., 'binance')

        Returns:
            Dict with api_key, secret, and optional passphrase
        """
        return {
            'api_key': self.secrets_manager.get_secret(f'{exchange}_api_key', ''),
            'secret': self.secrets_manager.get_secret(f'{exchange}_secret', ''),
            'passphrase': self.secrets_manager.get_secret(f'{exchange}_passphrase', '')
        }

    def save_exchange_credentials(
        self,
        exchange: str,
        api_key: str,
        secret: str,
        passphrase: Optional[str] = None
    ):
        """
        Save encrypted exchange credentials

        Args:
            exchange: Exchange name
            api_key: API key
            secret: API secret
            passphrase: Optional passphrase (for some exchanges)
        """
        self.secrets_manager.set_secret(f'{exchange}_api_key', api_key)
        self.secrets_manager.set_secret(f'{exchange}_secret', secret)
        if passphrase:
            self.secrets_manager.set_secret(f'{exchange}_passphrase', passphrase)

        logger.info(f"Credentials for {exchange} saved securely")

    def get_database_url(self) -> str:
        """Get database URL with encrypted password"""
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        name = os.getenv('DB_NAME', 'arbitrage')
        user = os.getenv('DB_USER', 'arbitrage_user')
        password = self.secrets_manager.get_secret('db_password', '')

        return f"postgresql://{user}:{password}@{host}:{port}/{name}"

    def get_redis_url(self) -> str:
        """Get Redis URL with encrypted password"""
        host = os.getenv('REDIS_HOST', 'localhost')
        port = os.getenv('REDIS_PORT', '6379')
        password = self.secrets_manager.get_secret('redis_password', '')

        if password:
            return f"redis://:{password}@{host}:{port}/0"
        return f"redis://{host}:{port}/0"


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token"""
    return secrets.token_urlsafe(length)


def hash_password(password: str, salt: Optional[bytes] = None) -> tuple:
    """
    Hash a password using PBKDF2

    Args:
        password: Plaintext password
        salt: Optional salt (generated if not provided)

    Returns:
        Tuple of (hash, salt) as bytes
    """
    if salt is None:
        salt = secrets.token_bytes(32)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
        backend=default_backend()
    )

    password_hash = kdf.derive(password.encode())
    return password_hash, salt


def verify_password(password: str, password_hash: bytes, salt: bytes) -> bool:
    """
    Verify a password against its hash

    Args:
        password: Plaintext password to verify
        password_hash: Stored hash
        salt: Stored salt

    Returns:
        True if password matches
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
        backend=default_backend()
    )

    try:
        kdf.verify(password.encode(), password_hash)
        return True
    except Exception:
        return False
