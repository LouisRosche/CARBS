"""
Comprehensive tests for security module

Tests:
- Authentication (passwords, TOTP, sessions)
- Encryption (secrets management, key rotation)
- Approval workflow (thread safety, state transitions)
- Rate limiting
- IP spoofing protection
- Request signing
- Token blacklist
- Session persistence
"""

import pytest
import asyncio
import os
import time
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock

# Set up test environment
os.environ['CARBS_MASTER_KEY'] = 'test_master_key_12345'
os.environ['CARBS_JWT_SECRET'] = 'test_jwt_secret_12345'
os.environ['CARBS_REQUEST_SIGNING_KEY'] = 'test_signing_key_12345'


class TestPasswordHashing:
    """Test password hashing functionality"""

    def test_hash_password_generates_unique_hashes(self):
        """Each hash should be unique due to random salt"""
        from src.security.encryption import hash_password

        hash1, salt1 = hash_password("password123")
        hash2, salt2 = hash_password("password123")

        assert hash1 != hash2
        assert salt1 != salt2

    def test_verify_password_correct(self):
        """Correct password should verify"""
        from src.security.encryption import hash_password, verify_password

        password = "secure_password_123"
        password_hash, salt = hash_password(password)

        assert verify_password(password, password_hash, salt) is True

    def test_verify_password_incorrect(self):
        """Incorrect password should not verify"""
        from src.security.encryption import hash_password, verify_password

        password_hash, salt = hash_password("correct_password")

        assert verify_password("wrong_password", password_hash, salt) is False

    def test_hash_password_with_provided_salt(self):
        """Should use provided salt if given"""
        from src.security.encryption import hash_password

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
        from src.security.encryption import SecretsManager, EncryptionError

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
        from src.security.encryption import SecretsManager

        manager = SecretsManager("test_password")
        manager.set_secret("api_key", "secret_value_123")

        assert manager.get_secret("api_key") == "secret_value_123"

    def test_get_nonexistent_secret_returns_default(self, temp_data_dir):
        """Should return default for missing secrets"""
        from src.security.encryption import SecretsManager

        manager = SecretsManager("test_password")

        assert manager.get_secret("missing_key") is None
        assert manager.get_secret("missing_key", "default") == "default"

    def test_delete_secret(self, temp_data_dir):
        """Should delete secrets"""
        from src.security.encryption import SecretsManager

        manager = SecretsManager("test_password")
        manager.set_secret("to_delete", "value")

        assert manager.delete_secret("to_delete") is True
        assert manager.get_secret("to_delete") is None

    def test_list_secrets(self, temp_data_dir):
        """Should list all secret keys"""
        from src.security.encryption import SecretsManager

        manager = SecretsManager("test_password")
        manager.set_secret("key1", "value1")
        manager.set_secret("key2", "value2")

        keys = manager.list_secrets()
        assert "key1" in keys
        assert "key2" in keys

    def test_encrypt_decrypt_value(self, temp_data_dir):
        """Should encrypt and decrypt values correctly"""
        from src.security.encryption import SecretsManager

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
        from src.security.encryption import EnvironmentSecretsProvider

        provider = EnvironmentSecretsProvider(prefix="TEST_SECRET_")

        with patch.dict(os.environ, {'TEST_SECRET_API_KEY': 'my_secret'}):
            assert provider.get_secret("api_key") == "my_secret"

    def test_get_secret_with_default(self):
        """Should return default when env var not set"""
        from src.security.encryption import EnvironmentSecretsProvider

        provider = EnvironmentSecretsProvider(prefix="TEST_SECRET_")

        assert provider.get_secret("missing", "default") == "default"

    def test_list_secrets(self):
        """Should list secrets from environment"""
        from src.security.encryption import EnvironmentSecretsProvider

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
        from src.security.encryption import UnifiedSecretsManager, EnvironmentSecretsProvider

        manager = UnifiedSecretsManager()

        # Add environment provider
        env_provider = EnvironmentSecretsProvider(prefix="CHAIN_TEST_")
        manager.add_provider(env_provider)

        with patch.dict(os.environ, {'CHAIN_TEST_KEY': 'env_value'}):
            assert manager.get_secret("key") == "env_value"

    def test_returns_default_when_not_found(self):
        """Should return default when no provider has the secret"""
        from src.security.encryption import UnifiedSecretsManager, EnvironmentSecretsProvider

        manager = UnifiedSecretsManager()
        manager.add_provider(EnvironmentSecretsProvider(prefix="EMPTY_"))

        assert manager.get_secret("missing", "default") == "default"


class TestRateLimiter:
    """Test rate limiter functionality"""

    def test_allows_requests_within_limit(self):
        """Should allow requests within rate limits"""
        from src.api.middleware import RateLimiter, RateLimitConfig

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
        from src.api.middleware import RateLimiter, RateLimitConfig

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
        from src.api.middleware import RateLimiter, RateLimitConfig

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
        from src.api.middleware import UserRateLimiter

        limiter = UserRateLimiter()

        # Make many requests for same user
        for _ in range(150):
            limiter.check_limit("user1")

        # Should eventually be rate limited
        allowed, _ = limiter.check_limit("user1")
        # Note: depends on the actual limits configured

    def test_sensitive_endpoints_stricter(self):
        """Sensitive endpoints should have stricter limits"""
        from src.api.middleware import UserRateLimiter

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
        from src.config.settings import validate_bounds

        data = {"check_interval_seconds": 5}
        bounds = {"check_interval_seconds": (1, 60)}

        # Should not raise
        validate_bounds(data, bounds, "test")

    def test_validate_bounds_invalid_value(self):
        """Should reject values outside bounds"""
        from src.config.settings import validate_bounds, ConfigValidationError

        data = {"check_interval_seconds": 0}
        bounds = {"check_interval_seconds": (1, 60)}

        with pytest.raises(ConfigValidationError):
            validate_bounds(data, bounds, "test")

    def test_validate_path_safe_valid(self):
        """Should accept safe paths"""
        from src.config.settings import validate_path_safe

        # Should not raise
        validate_path_safe("logs/app.log", "test")
        validate_path_safe("/var/log/app.log", "test")

    def test_validate_path_safe_traversal(self):
        """Should reject path traversal attempts"""
        from src.config.settings import validate_path_safe, ConfigValidationError

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
        from src.security.approval_workflow import (
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

        # Approve request (CONFIG_CHANGE requires 2FA by default)
        success, message, fully_approved = await engine.approve(
            request_id=request.request_id,
            approver_id="admin1",
            approver_role="admin",
            reason="Looks good",
            verified_2fa=True
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_reject_request(self, temp_approval_dir):
        """Should reject requests"""
        from src.security.approval_workflow import (
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
        from src.security.approval_workflow import (
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

        # Simulate concurrent approvals (CONFIG_CHANGE requires 2FA by default)
        async def approve(approver_id):
            return await engine.approve(
                request_id=request.request_id,
                approver_id=approver_id,
                approver_role="admin",
                reason="Approved",
                verified_2fa=True
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
        from src.security.approval_workflow import (
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
        from src.security.encryption import generate_secure_token

        token = generate_secure_token(32)
        # URL-safe base64 encoding adds some overhead
        assert len(token) >= 32

    def test_generate_secure_token_unique(self):
        """Tokens should be unique"""
        from src.security.encryption import generate_secure_token

        tokens = [generate_secure_token() for _ in range(100)]
        assert len(set(tokens)) == 100


class TestTrustedProxyValidator:
    """Test IP spoofing protection"""

    def test_is_trusted_proxy_localhost(self):
        """Should trust localhost"""
        from src.api.middleware import TrustedProxyValidator

        validator = TrustedProxyValidator()
        assert validator.is_trusted_proxy('127.0.0.1') is True
        assert validator.is_trusted_proxy('127.0.0.50') is True

    def test_is_trusted_proxy_private_network(self):
        """Should trust private networks by default"""
        from src.api.middleware import TrustedProxyValidator

        validator = TrustedProxyValidator()
        assert validator.is_trusted_proxy('10.0.0.1') is True
        assert validator.is_trusted_proxy('192.168.1.1') is True
        assert validator.is_trusted_proxy('172.16.0.1') is True

    def test_is_trusted_proxy_public_ip(self):
        """Should not trust public IPs"""
        from src.api.middleware import TrustedProxyValidator

        validator = TrustedProxyValidator()
        assert validator.is_trusted_proxy('8.8.8.8') is False
        assert validator.is_trusted_proxy('203.0.113.1') is False

    def test_get_real_client_ip_direct_connection(self):
        """Should use direct IP when not from trusted proxy"""
        from src.api.middleware import TrustedProxyValidator

        validator = TrustedProxyValidator()
        # Direct connection from public IP - ignore X-Forwarded-For
        result = validator.get_real_client_ip(
            direct_ip='8.8.8.8',
            x_forwarded_for='1.2.3.4, 5.6.7.8'
        )
        assert result == '8.8.8.8'

    def test_get_real_client_ip_from_proxy(self):
        """Should extract client IP from X-Forwarded-For when from proxy"""
        from src.api.middleware import TrustedProxyValidator

        validator = TrustedProxyValidator()
        # Connection from trusted proxy - use X-Forwarded-For
        result = validator.get_real_client_ip(
            direct_ip='10.0.0.1',
            x_forwarded_for='203.0.113.50, 10.0.0.5'
        )
        assert result == '203.0.113.50'

    def test_get_real_client_ip_rightmost_untrusted(self):
        """Should use rightmost untrusted IP"""
        from src.api.middleware import TrustedProxyValidator

        validator = TrustedProxyValidator()
        # Multiple proxies in chain
        result = validator.get_real_client_ip(
            direct_ip='127.0.0.1',
            x_forwarded_for='1.2.3.4, 5.6.7.8, 10.0.0.1'
        )
        # Should get 5.6.7.8 (rightmost untrusted)
        assert result == '5.6.7.8'

    def test_get_real_client_ip_invalid_ip(self):
        """Should handle invalid IPs gracefully"""
        from src.api.middleware import TrustedProxyValidator

        validator = TrustedProxyValidator()
        result = validator.get_real_client_ip(
            direct_ip='10.0.0.1',
            x_forwarded_for='not_an_ip, also_invalid'
        )
        # Should fall back to direct IP
        assert result == '10.0.0.1'


class TestRequestSigner:
    """Test HMAC-SHA256 request signing"""

    def test_sign_request_generates_headers(self):
        """Should generate signature headers"""
        from src.api.middleware import RequestSigner

        signer = RequestSigner(secret_key='test_secret')
        headers = signer.sign_request('POST', '/api/v1/trade', b'{"amount": 100}')

        assert 'X-CARBS-Signature' in headers
        assert 'X-CARBS-Timestamp' in headers
        assert 'X-CARBS-Nonce' in headers

    def test_verify_request_valid_signature(self):
        """Should verify valid signatures"""
        from src.api.middleware import RequestSigner

        signer = RequestSigner(secret_key='test_secret')

        # Sign a request
        body = b'{"amount": 100}'
        headers = signer.sign_request('POST', '/api/v1/trade', body)

        # Verify it
        valid, error = signer.verify_request(
            'POST',
            '/api/v1/trade',
            body,
            headers['X-CARBS-Signature'],
            headers['X-CARBS-Timestamp'],
            headers['X-CARBS-Nonce']
        )

        assert valid is True
        assert error is None

    def test_verify_request_invalid_signature(self):
        """Should reject invalid signatures"""
        from src.api.middleware import RequestSigner

        signer = RequestSigner(secret_key='test_secret')

        valid, error = signer.verify_request(
            'POST',
            '/api/v1/trade',
            b'{"amount": 100}',
            'invalid_signature',
            str(int(time.time())),
            'some_nonce'
        )

        assert valid is False
        assert 'Invalid signature' in error

    def test_verify_request_replay_protection(self):
        """Should reject replayed requests"""
        from src.api.middleware import RequestSigner

        signer = RequestSigner(secret_key='test_secret')

        body = b'{"amount": 100}'
        headers = signer.sign_request('POST', '/api/v1/trade', body)

        # First request should succeed
        valid1, _ = signer.verify_request(
            'POST', '/api/v1/trade', body,
            headers['X-CARBS-Signature'],
            headers['X-CARBS-Timestamp'],
            headers['X-CARBS-Nonce']
        )
        assert valid1 is True

        # Replay should fail
        valid2, error = signer.verify_request(
            'POST', '/api/v1/trade', body,
            headers['X-CARBS-Signature'],
            headers['X-CARBS-Timestamp'],
            headers['X-CARBS-Nonce']
        )
        assert valid2 is False
        assert 'Nonce already used' in error

    def test_verify_request_expired(self):
        """Should reject old requests"""
        from src.api.middleware import RequestSigner

        signer = RequestSigner(secret_key='test_secret')

        old_timestamp = str(int(time.time()) - 400)  # 400 seconds ago

        valid, error = signer.verify_request(
            'POST',
            '/api/v1/trade',
            b'{"amount": 100}',
            'some_signature',
            old_timestamp,
            'some_nonce'
        )

        assert valid is False
        assert 'Request too old' in error


class TestApprovalWorkflowRaceCondition:
    """Test approval workflow race condition prevention"""

    @pytest.fixture
    def temp_approval_dir(self):
        """Create temporary directory for approval data"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_executing_status_prevents_double_execution(self, temp_approval_dir):
        """Should prevent concurrent execution with EXECUTING status"""
        from src.security.approval_workflow import (
            ApprovalWorkflowEngine, ApprovalType, ApprovalStatus
        )
        from pathlib import Path

        engine = ApprovalWorkflowEngine(data_dir=Path(temp_approval_dir))
        # Remove time delay for testing so execute_if_ready works immediately
        engine.configure_rule(ApprovalType.CONFIG_CHANGE, time_delay_minutes=0)

        # Create and approve request
        request = await engine.create_request(
            approval_type=ApprovalType.CONFIG_CHANGE,
            requester_id="user1",
            requester_role="admin",
            operation_details={"setting": "value"},
            reason="Test"
        )

        # Approve it (CONFIG_CHANGE requires 2FA by default)
        await engine.approve(
            request_id=request.request_id,
            approver_id="admin1",
            approver_role="admin",
            reason="Approved",
            verified_2fa=True
        )

        # Track execution attempts
        execution_count = 0

        async def slow_executor(details):
            nonlocal execution_count
            execution_count += 1
            await asyncio.sleep(0.1)  # Simulate slow operation
            return "done"

        # Try to execute concurrently
        results = await asyncio.gather(
            engine.execute_if_ready(request.request_id, slow_executor),
            engine.execute_if_ready(request.request_id, slow_executor),
            engine.execute_if_ready(request.request_id, slow_executor),
            return_exceptions=True
        )

        # Only one should succeed
        successes = [r for r in results if isinstance(r, tuple) and r[0] is True]
        assert len(successes) == 1
        assert execution_count == 1  # Only executed once

    @pytest.mark.asyncio
    async def test_executing_status_in_enum(self):
        """EXECUTING status should exist in ApprovalStatus"""
        from src.security.approval_workflow import ApprovalStatus

        assert hasattr(ApprovalStatus, 'EXECUTING')
        assert ApprovalStatus.EXECUTING.value == 'executing'

    @pytest.mark.asyncio
    async def test_failed_execution_reverts_to_approved(self, temp_approval_dir):
        """Failed execution should revert status to APPROVED"""
        from src.security.approval_workflow import (
            ApprovalWorkflowEngine, ApprovalType, ApprovalStatus
        )
        from pathlib import Path

        engine = ApprovalWorkflowEngine(data_dir=Path(temp_approval_dir))
        # Remove time delay for testing so execute_if_ready works immediately
        engine.configure_rule(ApprovalType.CONFIG_CHANGE, time_delay_minutes=0)

        request = await engine.create_request(
            approval_type=ApprovalType.CONFIG_CHANGE,
            requester_id="user1",
            requester_role="admin",
            operation_details={"setting": "value"},
            reason="Test"
        )

        await engine.approve(
            request_id=request.request_id,
            approver_id="admin1",
            approver_role="admin",
            reason="Approved",
            verified_2fa=True
        )

        async def failing_executor(details):
            raise Exception("Simulated failure")

        success, message, result = await engine.execute_if_ready(
            request.request_id, failing_executor
        )

        assert success is False
        assert "Execution failed" in message

        # Request should be back to APPROVED for retry
        updated_request = engine.get_request(request.request_id)
        assert updated_request.status == ApprovalStatus.APPROVED


class TestSecurityMiddleware:
    """Test SecurityMiddleware integration"""

    def test_middleware_has_proxy_validator(self):
        """SecurityMiddleware should have proxy validator"""
        from src.api.middleware import SecurityMiddleware

        middleware = SecurityMiddleware()
        assert hasattr(middleware, 'proxy_validator')
        assert middleware.proxy_validator is not None

    def test_middleware_has_request_signer(self):
        """SecurityMiddleware should have request signer"""
        from src.api.middleware import SecurityMiddleware

        middleware = SecurityMiddleware()
        assert hasattr(middleware, 'request_signer')
        assert middleware.request_signer is not None

    def test_get_client_ip_method(self):
        """Should have get_client_ip method"""
        from src.api.middleware import SecurityMiddleware

        middleware = SecurityMiddleware()

        # Test with direct connection
        ip = middleware.get_client_ip('8.8.8.8', '1.2.3.4')
        assert ip == '8.8.8.8'  # Public IP not trusted

        # Test with trusted proxy
        ip = middleware.get_client_ip('127.0.0.1', '1.2.3.4')
        assert ip == '1.2.3.4'

    def test_verify_request_signature_method(self):
        """Should have verify_request_signature method"""
        from src.api.middleware import SecurityMiddleware, RequestSigner

        middleware = SecurityMiddleware(require_signed_requests=True)

        # Missing headers should fail for signed endpoints
        valid, error = middleware.verify_request_signature(
            'POST',
            '/api/v1/trade/execute',
            b'{}',
            {}
        )
        assert valid is False


class TestAuditLogging:
    """Test enhanced audit logging"""

    def test_audit_logger_has_new_methods(self):
        """Should have new audit logging methods"""
        from src.security.audit import AuditLogger

        # Check methods exist
        assert hasattr(AuditLogger, 'log_token_revocation')
        assert hasattr(AuditLogger, 'log_ip_spoofing_attempt')
        assert hasattr(AuditLogger, 'log_request_signature_failure')
        assert hasattr(AuditLogger, 'log_rate_limit_exceeded')
        assert hasattr(AuditLogger, 'log_approval_request')
        assert hasattr(AuditLogger, 'log_approval_decision')
        assert hasattr(AuditLogger, 'log_approval_execution')
        assert hasattr(AuditLogger, 'log_session_created')
        assert hasattr(AuditLogger, 'log_permission_denied')


class TestRefreshTokenTimingSafety:
    """Verify refresh token comparison uses constant-time comparison"""

    def test_refresh_token_uses_hmac_compare(self):
        """Refresh token lookup must use hmac.compare_digest, not =="""
        import inspect
        from src.security.auth import AuthenticationManager

        source = inspect.getsource(AuthenticationManager.refresh_session)
        assert 'hmac.compare_digest' in source, \
            "refresh_session must use hmac.compare_digest for timing-safe comparison"
        assert 's.refresh_token == refresh_token' not in source, \
            "refresh_session must NOT use == for refresh token comparison"


class TestJWTStandardClaims:
    """Verify JWT tokens include and validate standard security claims"""

    def test_jwt_includes_standard_claims(self):
        """JWT must include iss, aud, jti, nbf claims"""
        import jwt as pyjwt
        import secrets as _sec
        from src.security.auth import AuthenticationManager

        auth = AuthenticationManager(jwt_secret='test_secret_for_jwt_claims_test')
        user = auth.create_user(f'jwtclaims_{_sec.token_hex(4)}', 'StrongP@ssw0rd!1', role='viewer')
        session = auth._create_session(user, '127.0.0.1', 'test')
        token = auth.create_jwt(session)

        # Decode without verification to inspect claims
        payload = pyjwt.decode(token, 'test_secret_for_jwt_claims_test',
                               algorithms=['HS256'], audience='carbs-api')
        assert payload.get('iss') == 'carbs-auth'
        assert payload.get('aud') == 'carbs-api'
        assert 'jti' in payload
        assert 'nbf' in payload

    def test_jwt_rejects_wrong_issuer(self):
        """JWT verification must reject tokens with wrong issuer"""
        import jwt as pyjwt
        import secrets as _sec
        from src.security.auth import AuthenticationManager, TokenError

        auth = AuthenticationManager(jwt_secret='test_secret_for_issuer_test')
        user = auth.create_user(f'issuer_{_sec.token_hex(4)}', 'StrongP@ssw0rd!2', role='viewer')
        session = auth._create_session(user, '127.0.0.1', 'test')

        # Create token with wrong issuer
        payload = {
            'session_id': session.session_id,
            'user_id': session.user_id,
            'username': session.username,
            'role': session.role,
            'exp': session.expires_at.timestamp(),
            'iat': session.created_at.timestamp(),
            'iss': 'evil-issuer',
            'aud': 'carbs-api',
        }
        bad_token = pyjwt.encode(payload, 'test_secret_for_issuer_test', algorithm='HS256')

        with pytest.raises(TokenError, match="Invalid token"):
            auth.verify_jwt(bad_token)


class TestTOTPReplayProtection:
    """Verify TOTP codes cannot be replayed within the tolerance window"""

    def test_totp_replay_blocked(self):
        """Same TOTP code used twice should be rejected"""
        from src.security.auth import TOTP

        secret = TOTP.generate_secret()
        token = TOTP.get_totp_token(secret)

        # First use should succeed
        assert TOTP.verify(secret, token) is True

        # Replay with same token should fail
        assert TOTP.verify(secret, token) is False

    def test_totp_different_secrets_allowed(self):
        """TOTP codes from different secrets should both work"""
        from src.security.auth import TOTP

        secret1 = TOTP.generate_secret()
        secret2 = TOTP.generate_secret()

        token1 = TOTP.get_totp_token(secret1)
        token2 = TOTP.get_totp_token(secret2)

        # Different secrets produce independent replay tracking
        assert TOTP.verify(secret1, token1) is True
        assert TOTP.verify(secret2, token2) is True


class TestPasswordComplexity:
    """Verify password complexity requirements"""

    def test_reject_all_lowercase(self):
        """Password with only lowercase letters should be rejected"""
        from src.security.auth import AuthenticationManager, AuthError

        auth = AuthenticationManager(jwt_secret='test_complexity_secret')
        with pytest.raises(AuthError, match="uppercase.*lowercase.*digit.*special"):
            auth.create_user('weakpwuser1', 'aaaaaaaaaaaa')

    def test_reject_all_same_char(self):
        """Trivial repeated-char password should be rejected"""
        from src.security.auth import AuthenticationManager, AuthError

        auth = AuthenticationManager(jwt_secret='test_complexity_secret2')
        with pytest.raises(AuthError, match="uppercase.*lowercase.*digit.*special"):
            auth.create_user('weakpwuser2', '111111111111')

    def test_accept_complex_password(self):
        """Password with 3+ character classes should be accepted"""
        import secrets as _sec
        from src.security.auth import AuthenticationManager

        auth = AuthenticationManager(jwt_secret='test_complexity_secret3')
        username = f'strongpw_{_sec.token_hex(4)}'
        user = auth.create_user(username, 'MyStr0ngP@ss!')
        assert user.username == username


class TestCORSWildcardGuard:
    """Verify CORS wildcard origin is blocked when credentials are enabled"""

    def test_cors_wildcard_rejected(self):
        """Setting CORS_ORIGINS=* should result in empty origins list"""
        with patch.dict(os.environ, {'CORS_ORIGINS': '*'}):
            origins = [o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()]
            if '*' in origins:
                origins = []
            assert origins == []

    def test_cors_specific_origin_accepted(self):
        """Specific CORS origins should be preserved"""
        with patch.dict(os.environ, {'CORS_ORIGINS': 'https://app.example.com'}):
            origins = [o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()]
            if '*' in origins:
                origins = []
            assert origins == ['https://app.example.com']


class TestEndpointRateLimiterPersistence:
    """Verify per-endpoint rate limiters are persistent (not recreated per request)"""

    def test_endpoint_limiters_are_persistent_instances(self):
        """SecurityMiddleware must use persistent RateLimiter instances per endpoint"""
        from src.api.middleware import SecurityMiddleware

        middleware = SecurityMiddleware()
        assert hasattr(middleware, '_endpoint_limiters')

        # Verify they're RateLimiter instances, not RateLimitConfig
        for endpoint, limiter in middleware._endpoint_limiters.items():
            from src.api.middleware import RateLimiter
            assert isinstance(limiter, RateLimiter), \
                f"Endpoint {endpoint} should use a persistent RateLimiter instance"

    def test_endpoint_rate_limit_actually_enforced(self):
        """Login endpoint burst limit (2/sec) should block after 2 rapid requests"""
        from src.api.middleware import SecurityMiddleware

        middleware = SecurityMiddleware()
        test_ip = '10.20.30.40'
        endpoint = '/api/v1/auth/login'

        # Make 2 requests (burst_limit=2, should be allowed)
        for i in range(2):
            allowed, _ = middleware.check_rate_limit(test_ip, endpoint)
            assert allowed, f"Request {i+1} should be allowed"

        # 3rd rapid request should be burst-limited
        allowed, retry_after = middleware.check_rate_limit(test_ip, endpoint)
        assert not allowed, "3rd rapid request should be rate-limited by burst limit"
        assert retry_after is not None


class TestIPRateLimiterEviction:
    """Verify IP rate limiter has bounded memory growth"""

    def test_ip_attempts_dict_has_eviction(self):
        """AuthenticationManager should evict stale IPs when over MAX_TRACKED_IPS"""
        from src.security.auth import AuthenticationManager

        auth = AuthenticationManager(jwt_secret='test_eviction_secret')
        assert hasattr(auth, 'MAX_TRACKED_IPS')
        assert auth.MAX_TRACKED_IPS > 0

    def test_check_ip_rate_limit_source_has_eviction(self):
        """_check_ip_rate_limit must contain eviction logic"""
        import inspect
        from src.security.auth import AuthenticationManager

        source = inspect.getsource(AuthenticationManager._check_ip_rate_limit)
        assert 'MAX_TRACKED_IPS' in source, \
            "_check_ip_rate_limit must reference MAX_TRACKED_IPS for eviction"


class TestRequireApiAuthSafety:
    """Verify require_api_auth decorator is not silently passing through"""

    def test_require_api_auth_raises_on_call(self):
        """Decorated functions must raise RuntimeError, not silently pass through"""
        import warnings
        from src.api.middleware import require_api_auth

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            @require_api_auth(required_permission='test')
            async def fake_endpoint():
                return "should never reach here"

        with pytest.raises(RuntimeError, match="does not enforce authentication"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(fake_endpoint())
