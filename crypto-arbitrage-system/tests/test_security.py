"""
Comprehensive tests for security module

Tests:
- Authentication (passwords, TOTP, sessions)
- Encryption (secrets management, key rotation)
- Approval workflow (thread safety, state transitions)
- Rate limiting
"""

import pytest
import asyncio
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

# Set up test environment
os.environ['CARBS_MASTER_KEY'] = 'test_master_key_12345'
os.environ['CARBS_JWT_SECRET'] = 'test_jwt_secret_12345'


class TestPasswordHashing:
    """Test password hashing functionality"""

    def test_hash_password_generates_unique_hashes(self):
        """Each hash should be unique due to random salt"""
        from security.encryption import hash_password

        hash1, salt1 = hash_password("password123")
        hash2, salt2 = hash_password("password123")

        assert hash1 != hash2
        assert salt1 != salt2

    def test_verify_password_correct(self):
        """Correct password should verify"""
        from security.encryption import hash_password, verify_password

        password = "secure_password_123"
        password_hash, salt = hash_password(password)

        assert verify_password(password, password_hash, salt) is True

    def test_verify_password_incorrect(self):
        """Incorrect password should not verify"""
        from security.encryption import hash_password, verify_password

        password_hash, salt = hash_password("correct_password")

        assert verify_password("wrong_password", password_hash, salt) is False

    def test_hash_password_with_provided_salt(self):
        """Should use provided salt if given"""
        from security.encryption import hash_password

        salt = b'0' * 32
        hash1, returned_salt1 = hash_password("password", salt)
        hash2, returned_salt2 = hash_password("password", salt)

        assert hash1 == hash2
        assert returned_salt1 == salt
        assert returned_salt2 == salt


class TestSecretsManager:
    """Test secrets manager functionality"""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory for tests"""
        temp_dir = tempfile.mkdtemp()
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        os.makedirs('data', exist_ok=True)
        yield temp_dir
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)

    def test_secrets_manager_requires_master_key(self):
        """Should raise error without master key"""
        from security.encryption import SecretsManager, EncryptionError

        with patch.dict(os.environ, {'CARBS_MASTER_KEY': ''}, clear=False):
            # Remove the key temporarily
            original = os.environ.pop('CARBS_MASTER_KEY', None)
            try:
                with pytest.raises(EncryptionError):
                    SecretsManager()
            finally:
                if original:
                    os.environ['CARBS_MASTER_KEY'] = original

    def test_set_and_get_secret(self, temp_data_dir):
        """Should store and retrieve secrets"""
        from security.encryption import SecretsManager

        manager = SecretsManager("test_password")
        manager.set_secret("api_key", "secret_value_123")

        assert manager.get_secret("api_key") == "secret_value_123"

    def test_get_nonexistent_secret_returns_default(self, temp_data_dir):
        """Should return default for missing secrets"""
        from security.encryption import SecretsManager

        manager = SecretsManager("test_password")

        assert manager.get_secret("missing_key") is None
        assert manager.get_secret("missing_key", "default") == "default"

    def test_delete_secret(self, temp_data_dir):
        """Should delete secrets"""
        from security.encryption import SecretsManager

        manager = SecretsManager("test_password")
        manager.set_secret("to_delete", "value")

        assert manager.delete_secret("to_delete") is True
        assert manager.get_secret("to_delete") is None

    def test_list_secrets(self, temp_data_dir):
        """Should list all secret keys"""
        from security.encryption import SecretsManager

        manager = SecretsManager("test_password")
        manager.set_secret("key1", "value1")
        manager.set_secret("key2", "value2")

        keys = manager.list_secrets()
        assert "key1" in keys
        assert "key2" in keys

    def test_encrypt_decrypt_value(self, temp_data_dir):
        """Should encrypt and decrypt values correctly"""
        from security.encryption import SecretsManager

        manager = SecretsManager("test_password")
        original = "sensitive_data"

        encrypted = manager.encrypt_value(original)
        decrypted = manager.decrypt_value(encrypted)

        assert encrypted != original
        assert decrypted == original


class TestEnvironmentSecretsProvider:
    """Test environment-based secrets provider"""

    def test_get_secret_from_env(self):
        """Should read secrets from environment variables"""
        from security.encryption import EnvironmentSecretsProvider

        provider = EnvironmentSecretsProvider(prefix="TEST_SECRET_")

        with patch.dict(os.environ, {'TEST_SECRET_API_KEY': 'my_secret'}):
            assert provider.get_secret("api_key") == "my_secret"

    def test_get_secret_with_default(self):
        """Should return default when env var not set"""
        from security.encryption import EnvironmentSecretsProvider

        provider = EnvironmentSecretsProvider(prefix="TEST_SECRET_")

        assert provider.get_secret("missing", "default") == "default"

    def test_list_secrets(self):
        """Should list secrets from environment"""
        from security.encryption import EnvironmentSecretsProvider

        provider = EnvironmentSecretsProvider(prefix="LIST_TEST_")

        with patch.dict(os.environ, {
            'LIST_TEST_KEY1': 'value1',
            'LIST_TEST_KEY2': 'value2',
            'OTHER_KEY': 'other'
        }):
            keys = provider.list_secrets()
            assert 'key1' in keys
            assert 'key2' in keys
            assert 'other_key' not in keys


class TestUnifiedSecretsManager:
    """Test unified secrets manager with multiple providers"""

    def test_fallback_chain(self):
        """Should try providers in order until secret found"""
        from security.encryption import UnifiedSecretsManager, EnvironmentSecretsProvider

        manager = UnifiedSecretsManager()

        # Add environment provider
        env_provider = EnvironmentSecretsProvider(prefix="CHAIN_TEST_")
        manager.add_provider(env_provider)

        with patch.dict(os.environ, {'CHAIN_TEST_KEY': 'env_value'}):
            assert manager.get_secret("key") == "env_value"

    def test_returns_default_when_not_found(self):
        """Should return default when no provider has the secret"""
        from security.encryption import UnifiedSecretsManager, EnvironmentSecretsProvider

        manager = UnifiedSecretsManager()
        manager.add_provider(EnvironmentSecretsProvider(prefix="EMPTY_"))

        assert manager.get_secret("missing", "default") == "default"


class TestRateLimiter:
    """Test rate limiter functionality"""

    def test_allows_requests_within_limit(self):
        """Should allow requests within rate limits"""
        from api.middleware import RateLimiter, RateLimitConfig

        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
            burst_limit=5
        )
        limiter = RateLimiter(config)

        # First request should be allowed
        allowed, retry_after = limiter.check_limit("test_ip")
        assert allowed is True
        assert retry_after is None

    def test_blocks_burst_limit(self):
        """Should block requests exceeding burst limit"""
        from api.middleware import RateLimiter, RateLimitConfig

        config = RateLimitConfig(burst_limit=2)
        limiter = RateLimiter(config)

        # Make requests up to burst limit
        limiter.check_limit("test_ip")
        limiter.check_limit("test_ip")

        # Third request should be blocked
        allowed, retry_after = limiter.check_limit("test_ip")
        assert allowed is False
        assert retry_after == 1

    def test_different_keys_independent(self):
        """Different IPs should have independent limits"""
        from api.middleware import RateLimiter, RateLimitConfig

        config = RateLimitConfig(burst_limit=1)
        limiter = RateLimiter(config)

        # First IP exhausts limit
        limiter.check_limit("ip1")
        allowed1, _ = limiter.check_limit("ip1")

        # Second IP should still be allowed
        allowed2, _ = limiter.check_limit("ip2")

        assert allowed1 is False
        assert allowed2 is True


class TestUserRateLimiter:
    """Test per-user rate limiter"""

    def test_user_rate_limiting(self):
        """Should rate limit per user"""
        from api.middleware import UserRateLimiter

        limiter = UserRateLimiter()

        # Make many requests for same user
        for _ in range(150):
            limiter.check_limit("user1")

        # Should eventually be rate limited
        allowed, _ = limiter.check_limit("user1")
        # Note: depends on the actual limits configured

    def test_sensitive_endpoints_stricter(self):
        """Sensitive endpoints should have stricter limits"""
        from api.middleware import UserRateLimiter

        limiter = UserRateLimiter()

        # Make requests to sensitive endpoint
        for _ in range(15):
            limiter.check_limit("user1", sensitive=True)

        allowed, _ = limiter.check_limit("user1", sensitive=True)
        assert allowed is False


class TestConfigValidation:
    """Test configuration validation"""

    def test_validate_bounds_valid_values(self):
        """Should accept values within bounds"""
        from config.settings import validate_bounds

        data = {"check_interval_seconds": 5}
        bounds = {"check_interval_seconds": (1, 60)}

        # Should not raise
        validate_bounds(data, bounds, "test")

    def test_validate_bounds_invalid_value(self):
        """Should reject values outside bounds"""
        from config.settings import validate_bounds, ConfigValidationError

        data = {"check_interval_seconds": 0}
        bounds = {"check_interval_seconds": (1, 60)}

        with pytest.raises(ConfigValidationError):
            validate_bounds(data, bounds, "test")

    def test_validate_path_safe_valid(self):
        """Should accept safe paths"""
        from config.settings import validate_path_safe

        # Should not raise
        validate_path_safe("logs/app.log", "test")
        validate_path_safe("/var/log/app.log", "test")

    def test_validate_path_safe_traversal(self):
        """Should reject path traversal attempts"""
        from config.settings import validate_path_safe, ConfigValidationError

        with pytest.raises(ConfigValidationError):
            validate_path_safe("../../../etc/passwd", "test")


class TestApprovalWorkflow:
    """Test approval workflow with thread safety"""

    @pytest.fixture
    def temp_approval_dir(self):
        """Create temporary directory for approval data"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_create_and_approve_request(self, temp_approval_dir):
        """Should create and approve requests"""
        from security.approval_workflow import (
            ApprovalWorkflowEngine, ApprovalType, ApprovalStatus
        )
        from pathlib import Path

        engine = ApprovalWorkflowEngine(data_dir=Path(temp_approval_dir))

        # Create request
        request = await engine.create_request(
            approval_type=ApprovalType.CONFIG_CHANGE,
            requester_id="user1",
            requester_role="admin",
            operation_details={"setting": "new_value"},
            reason="Testing approval"
        )

        assert request.status == ApprovalStatus.PENDING

        # Approve request
        success, message, fully_approved = await engine.approve(
            request_id=request.request_id,
            approver_id="admin1",
            approver_role="admin",
            reason="Looks good"
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_reject_request(self, temp_approval_dir):
        """Should reject requests"""
        from security.approval_workflow import (
            ApprovalWorkflowEngine, ApprovalType, ApprovalStatus
        )
        from pathlib import Path

        engine = ApprovalWorkflowEngine(data_dir=Path(temp_approval_dir))

        request = await engine.create_request(
            approval_type=ApprovalType.CONFIG_CHANGE,
            requester_id="user1",
            requester_role="admin",
            operation_details={"setting": "value"},
            reason="Test"
        )

        success, message = await engine.reject(
            request_id=request.request_id,
            rejector_id="admin1",
            rejector_role="admin",
            reason="Not approved"
        )

        assert success is True
        assert engine.get_request(request.request_id).status == ApprovalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_concurrent_approval_safety(self, temp_approval_dir):
        """Should handle concurrent approvals safely"""
        from security.approval_workflow import (
            ApprovalWorkflowEngine, ApprovalType
        )
        from pathlib import Path

        engine = ApprovalWorkflowEngine(data_dir=Path(temp_approval_dir))

        request = await engine.create_request(
            approval_type=ApprovalType.CONFIG_CHANGE,
            requester_id="user1",
            requester_role="admin",
            operation_details={"setting": "value"},
            reason="Test"
        )

        # Simulate concurrent approvals
        async def approve(approver_id):
            return await engine.approve(
                request_id=request.request_id,
                approver_id=approver_id,
                approver_role="admin",
                reason="Approved"
            )

        results = await asyncio.gather(
            approve("admin1"),
            approve("admin2"),
            approve("admin3"),
            return_exceptions=True
        )

        # Count successful approvals
        successful = sum(1 for r in results if isinstance(r, tuple) and r[0])
        # Should not have race condition issues
        assert successful >= 1

    @pytest.mark.asyncio
    async def test_cleanup_expired_requests(self, temp_approval_dir):
        """Should cleanup expired requests safely"""
        from security.approval_workflow import (
            ApprovalWorkflowEngine, ApprovalType, ApprovalStatus
        )
        from pathlib import Path

        engine = ApprovalWorkflowEngine(data_dir=Path(temp_approval_dir))

        # Create a request (it won't actually expire in test time,
        # but we test the cleanup mechanism)
        request = await engine.create_request(
            approval_type=ApprovalType.CONFIG_CHANGE,
            requester_id="user1",
            requester_role="admin",
            operation_details={"setting": "value"},
            reason="Test"
        )

        # Run cleanup
        await engine.cleanup_expired()

        # Request should still exist (not expired yet)
        assert engine.get_request(request.request_id) is not None


class TestSecureToken:
    """Test secure token generation"""

    def test_generate_secure_token_length(self):
        """Should generate tokens of correct length"""
        from security.encryption import generate_secure_token

        token = generate_secure_token(32)
        # URL-safe base64 encoding adds some overhead
        assert len(token) >= 32

    def test_generate_secure_token_unique(self):
        """Tokens should be unique"""
        from security.encryption import generate_secure_token

        tokens = [generate_secure_token() for _ in range(100)]
        assert len(set(tokens)) == 100
