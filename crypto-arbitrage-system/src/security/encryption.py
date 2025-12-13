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


class SecretsProvider:
    """
    Abstract base class for secrets providers.

    Allows integration with external secrets management systems
    like HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, etc.
    """

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret by key"""
        raise NotImplementedError

    def set_secret(self, key: str, value: str) -> None:
        """Set a secret"""
        raise NotImplementedError

    def delete_secret(self, key: str) -> bool:
        """Delete a secret"""
        raise NotImplementedError

    def list_secrets(self) -> list:
        """List all secret keys"""
        raise NotImplementedError


class EnvironmentSecretsProvider(SecretsProvider):
    """
    Secrets provider that reads from environment variables.

    Useful for container deployments where secrets are injected via env vars.
    """

    def __init__(self, prefix: str = "CARBS_SECRET_"):
        self.prefix = prefix

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        env_key = f"{self.prefix}{key.upper()}"
        return os.getenv(env_key, default)

    def set_secret(self, key: str, value: str) -> None:
        # Environment variables are read-only at runtime
        logger.warning(f"Cannot set environment variable {key} at runtime")

    def delete_secret(self, key: str) -> bool:
        logger.warning(f"Cannot delete environment variable {key} at runtime")
        return False

    def list_secrets(self) -> list:
        return [
            k[len(self.prefix):].lower()
            for k in os.environ
            if k.startswith(self.prefix)
        ]


class VaultSecretsProvider(SecretsProvider):
    """
    HashiCorp Vault secrets provider.

    Requires: pip install hvac

    Configuration via environment variables:
    - VAULT_ADDR: Vault server address
    - VAULT_TOKEN: Authentication token
    - VAULT_SECRET_PATH: Path to secrets (default: secret/data/carbs)
    """

    def __init__(
        self,
        vault_addr: Optional[str] = None,
        vault_token: Optional[str] = None,
        secret_path: str = "secret/data/carbs"
    ):
        self.vault_addr = vault_addr or os.getenv('VAULT_ADDR', 'http://127.0.0.1:8200')
        self.vault_token = vault_token or os.getenv('VAULT_TOKEN')
        self.secret_path = os.getenv('VAULT_SECRET_PATH', secret_path)
        self._client = None

    def _get_client(self):
        """Get or create Vault client"""
        if self._client:
            return self._client

        try:
            import hvac
            self._client = hvac.Client(url=self.vault_addr, token=self.vault_token)
            if not self._client.is_authenticated():
                raise EncryptionError("Vault authentication failed")
            logger.info(f"Connected to Vault at {self.vault_addr}")
            return self._client
        except ImportError:
            raise EncryptionError("hvac package required for Vault integration. Install with: pip install hvac")

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            client = self._get_client()
            result = client.secrets.kv.v2.read_secret_version(path=self.secret_path)
            return result['data']['data'].get(key, default)
        except Exception as e:
            logger.warning(f"Failed to get secret {key} from Vault: {e}")
            return default

    def set_secret(self, key: str, value: str) -> None:
        try:
            client = self._get_client()
            # Read existing secrets
            try:
                result = client.secrets.kv.v2.read_secret_version(path=self.secret_path)
                data = result['data']['data']
            except Exception:
                data = {}

            data[key] = value
            client.secrets.kv.v2.create_or_update_secret(path=self.secret_path, secret=data)
            logger.info(f"Secret {key} stored in Vault")
        except Exception as e:
            raise EncryptionError(f"Failed to set secret in Vault: {e}")

    def delete_secret(self, key: str) -> bool:
        try:
            client = self._get_client()
            result = client.secrets.kv.v2.read_secret_version(path=self.secret_path)
            data = result['data']['data']
            if key in data:
                del data[key]
                client.secrets.kv.v2.create_or_update_secret(path=self.secret_path, secret=data)
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to delete secret {key} from Vault: {e}")
            return False

    def list_secrets(self) -> list:
        try:
            client = self._get_client()
            result = client.secrets.kv.v2.read_secret_version(path=self.secret_path)
            return list(result['data']['data'].keys())
        except Exception:
            return []


class AWSSecretsProvider(SecretsProvider):
    """
    AWS Secrets Manager provider.

    Requires: pip install boto3

    Configuration via environment variables:
    - AWS_REGION: AWS region
    - AWS_SECRET_NAME: Name of the secret in AWS Secrets Manager
    """

    def __init__(
        self,
        region: Optional[str] = None,
        secret_name: str = "carbs/secrets"
    ):
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        self.secret_name = os.getenv('AWS_SECRET_NAME', secret_name)
        self._client = None
        self._cache: Dict[str, str] = {}

    def _get_client(self):
        """Get or create AWS Secrets Manager client"""
        if self._client:
            return self._client

        try:
            import boto3
            self._client = boto3.client('secretsmanager', region_name=self.region)
            logger.info(f"Connected to AWS Secrets Manager in {self.region}")
            return self._client
        except ImportError:
            raise EncryptionError("boto3 package required for AWS integration. Install with: pip install boto3")

    def _load_secrets(self) -> Dict[str, str]:
        """Load all secrets from AWS"""
        if self._cache:
            return self._cache

        try:
            client = self._get_client()
            response = client.get_secret_value(SecretId=self.secret_name)
            self._cache = json.loads(response['SecretString'])
            return self._cache
        except Exception as e:
            logger.warning(f"Failed to load secrets from AWS: {e}")
            return {}

    def _save_secrets(self, data: Dict[str, str]) -> None:
        """Save secrets to AWS"""
        try:
            client = self._get_client()
            client.put_secret_value(
                SecretId=self.secret_name,
                SecretString=json.dumps(data)
            )
            self._cache = data
        except Exception as e:
            raise EncryptionError(f"Failed to save secrets to AWS: {e}")

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        secrets = self._load_secrets()
        return secrets.get(key, default)

    def set_secret(self, key: str, value: str) -> None:
        secrets = self._load_secrets()
        secrets[key] = value
        self._save_secrets(secrets)
        logger.info(f"Secret {key} stored in AWS Secrets Manager")

    def delete_secret(self, key: str) -> bool:
        secrets = self._load_secrets()
        if key in secrets:
            del secrets[key]
            self._save_secrets(secrets)
            return True
        return False

    def list_secrets(self) -> list:
        return list(self._load_secrets().keys())


class UnifiedSecretsManager:
    """
    Unified secrets manager that can use multiple backends.

    Supports fallback chain: tries providers in order until secret is found.

    Usage:
        manager = UnifiedSecretsManager()
        manager.add_provider(VaultSecretsProvider())
        manager.add_provider(EnvironmentSecretsProvider())
        manager.add_provider(SecretsManager())  # Local encrypted fallback

        secret = manager.get_secret('api_key')
    """

    def __init__(self):
        self._providers: list = []
        self._primary_provider: Optional[SecretsProvider] = None

    def add_provider(self, provider: SecretsProvider, primary: bool = False):
        """
        Add a secrets provider to the chain.

        Args:
            provider: The secrets provider to add
            primary: If True, this provider is used for writes
        """
        self._providers.append(provider)
        if primary or self._primary_provider is None:
            self._primary_provider = provider

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret, trying each provider in order.
        """
        for provider in self._providers:
            try:
                value = provider.get_secret(key)
                if value is not None:
                    return value
            except Exception as e:
                logger.debug(f"Provider {type(provider).__name__} failed: {e}")
                continue
        return default

    def set_secret(self, key: str, value: str) -> None:
        """
        Set a secret using the primary provider.
        """
        if self._primary_provider:
            self._primary_provider.set_secret(key, value)
        else:
            raise EncryptionError("No primary secrets provider configured")

    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret from the primary provider.
        """
        if self._primary_provider:
            return self._primary_provider.delete_secret(key)
        return False

    def list_secrets(self) -> list:
        """
        List all secrets from all providers (deduplicated).
        """
        all_keys = set()
        for provider in self._providers:
            try:
                all_keys.update(provider.list_secrets())
            except Exception:
                continue
        return list(all_keys)

    @classmethod
    def from_environment(cls) -> 'UnifiedSecretsManager':
        """
        Create a secrets manager based on environment configuration.

        Checks for:
        - VAULT_ADDR: Use HashiCorp Vault
        - AWS_SECRET_NAME: Use AWS Secrets Manager
        - CARBS_MASTER_KEY: Use local encrypted storage
        - Falls back to environment variables
        """
        manager = cls()

        # Try Vault first
        if os.getenv('VAULT_ADDR'):
            try:
                manager.add_provider(VaultSecretsProvider(), primary=True)
                logger.info("Using HashiCorp Vault for secrets")
            except Exception as e:
                logger.warning(f"Vault not available: {e}")

        # Try AWS Secrets Manager
        if os.getenv('AWS_SECRET_NAME'):
            try:
                manager.add_provider(AWSSecretsProvider(), primary=not manager._providers)
                logger.info("Using AWS Secrets Manager for secrets")
            except Exception as e:
                logger.warning(f"AWS Secrets Manager not available: {e}")

        # Try local encrypted storage
        if os.getenv('CARBS_MASTER_KEY'):
            try:
                manager.add_provider(SecretsManager(), primary=not manager._providers)
                logger.info("Using local encrypted storage for secrets")
            except Exception as e:
                logger.warning(f"Local secrets manager not available: {e}")

        # Always add environment variables as fallback
        manager.add_provider(EnvironmentSecretsProvider())

        return manager


# Global instance for convenience
_secrets_manager: Optional[UnifiedSecretsManager] = None


def get_secrets_manager() -> UnifiedSecretsManager:
    """Get or create the global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = UnifiedSecretsManager.from_environment()
    return _secrets_manager
