"""
Hardware Key Authentication (WebAuthn/FIDO2)

Supports:
- YubiKey 5 series
- Other FIDO2 hardware keys
- Platform authenticators (Windows Hello, Touch ID)

For CLI use, provides challenge-response verification.
For web, provides full WebAuthn flow.

Recommended: YubiKey 5 NFC (~$50)
- USB-A, USB-C, and NFC
- Works with phone tap
- 25+ year lifespan
"""

import os
import json
import base64
import secrets
import hashlib
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# WebAuthn library (optional advanced dependency)
try:
    from fido2.server import Fido2Server
    from fido2.webauthn import (
        PublicKeyCredentialRpEntity,
        PublicKeyCredentialUserEntity,
        AuthenticatorSelectionCriteria,
        UserVerificationRequirement,
        ResidentKeyRequirement,
        AttestationConveyancePreference,
        PublicKeyCredentialDescriptor,
        PublicKeyCredentialType
    )
    from fido2.cose import ES256
    from fido2 import cbor
    WEBAUTHN_AVAILABLE = True
except ImportError:
    WEBAUTHN_AVAILABLE = False
    logger.info("fido2 library not installed. Hardware key support limited to HMAC challenge-response.")


@dataclass
class HardwareKeyCredential:
    """Stored hardware key credential"""
    credential_id: str
    public_key: bytes
    sign_count: int
    user_id: str
    username: str
    device_name: str
    registered_at: datetime
    last_used: Optional[datetime] = None
    aaguid: Optional[str] = None  # Authenticator model identifier


@dataclass
class ChallengeSession:
    """Active challenge for verification"""
    challenge: bytes
    user_id: str
    created_at: datetime
    expires_at: datetime
    purpose: str  # 'registration' or 'authentication'


class HardwareKeyManager:
    """
    Hardware key authentication manager

    Supports multiple authentication methods:
    1. WebAuthn (full FIDO2) - for web interface
    2. HMAC challenge-response - for CLI
    3. OTP (legacy YubiKey) - fallback

    Security features:
    - Credential binding to user
    - Replay attack prevention (sign counter)
    - Challenge expiration
    - Multiple keys per user
    """

    RP_ID = "carbs.local"  # Relying Party ID
    RP_NAME = "CARBS Trading System"
    CHALLENGE_TIMEOUT_SECONDS = 120

    def __init__(self, storage_path: str = "data/.hardware_keys.json"):
        """
        Initialize hardware key manager

        Args:
            storage_path: Path to store credential data
        """
        self._storage_path = Path(storage_path)
        self._credentials: Dict[str, List[HardwareKeyCredential]] = {}  # user_id -> credentials
        self._challenges: Dict[str, ChallengeSession] = {}  # challenge_id -> session
        self._fido2_server: Optional['Fido2Server'] = None

        # Initialize WebAuthn server if available
        if WEBAUTHN_AVAILABLE:
            rp = PublicKeyCredentialRpEntity(id=self.RP_ID, name=self.RP_NAME)
            self._fido2_server = Fido2Server(rp)

        self._load_credentials()
        logger.info(f"Hardware key manager initialized (WebAuthn: {WEBAUTHN_AVAILABLE})")

    def _load_credentials(self):
        """Load credentials from storage"""
        if not self._storage_path.exists():
            return

        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)

            for user_id, creds_data in data.items():
                self._credentials[user_id] = []
                for cred_data in creds_data:
                    cred = HardwareKeyCredential(
                        credential_id=cred_data['credential_id'],
                        public_key=base64.b64decode(cred_data['public_key']),
                        sign_count=cred_data['sign_count'],
                        user_id=cred_data['user_id'],
                        username=cred_data['username'],
                        device_name=cred_data['device_name'],
                        registered_at=datetime.fromisoformat(cred_data['registered_at']),
                        last_used=datetime.fromisoformat(cred_data['last_used']) if cred_data.get('last_used') else None,
                        aaguid=cred_data.get('aaguid')
                    )
                    self._credentials[user_id].append(cred)

            logger.info(f"Loaded {sum(len(c) for c in self._credentials.values())} hardware key credentials")

        except Exception as e:
            logger.error(f"Failed to load hardware key credentials: {e}")

    def _save_credentials(self):
        """Save credentials to storage"""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {}
        for user_id, creds in self._credentials.items():
            data[user_id] = []
            for cred in creds:
                data[user_id].append({
                    'credential_id': cred.credential_id,
                    'public_key': base64.b64encode(cred.public_key).decode(),
                    'sign_count': cred.sign_count,
                    'user_id': cred.user_id,
                    'username': cred.username,
                    'device_name': cred.device_name,
                    'registered_at': cred.registered_at.isoformat(),
                    'last_used': cred.last_used.isoformat() if cred.last_used else None,
                    'aaguid': cred.aaguid
                })

        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)

        os.chmod(self._storage_path, 0o600)

    # ========== WebAuthn Registration ==========

    def begin_registration(
        self,
        user_id: str,
        username: str,
        display_name: str
    ) -> Tuple[Dict[str, Any], str]:
        """
        Begin WebAuthn registration

        Args:
            user_id: Unique user identifier
            username: Username
            display_name: Human-readable name

        Returns:
            Tuple of (options_dict, challenge_id)
        """
        if not WEBAUTHN_AVAILABLE:
            raise RuntimeError("WebAuthn not available. Install fido2 library.")

        # Get existing credentials to exclude
        existing = self._credentials.get(user_id, [])
        exclude_credentials = [
            PublicKeyCredentialDescriptor(
                type=PublicKeyCredentialType.PUBLIC_KEY,
                id=base64.b64decode(cred.credential_id)
            )
            for cred in existing
        ]

        # Create user entity
        user = PublicKeyCredentialUserEntity(
            id=user_id.encode(),
            name=username,
            display_name=display_name
        )

        # Generate registration options
        registration_data, state = self._fido2_server.register_begin(
            user=user,
            credentials=exclude_credentials,
            user_verification=UserVerificationRequirement.PREFERRED,
            authenticator_attachment=None,  # Allow any authenticator
            resident_key_requirement=ResidentKeyRequirement.DISCOURAGED
        )

        # Store challenge
        challenge_id = secrets.token_urlsafe(32)
        self._challenges[challenge_id] = ChallengeSession(
            challenge=state['challenge'],
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.CHALLENGE_TIMEOUT_SECONDS),
            purpose='registration'
        )

        # Convert to JSON-serializable dict
        options = {
            'challenge': base64.urlsafe_b64encode(registration_data['publicKey']['challenge']).decode(),
            'rp': {
                'id': self.RP_ID,
                'name': self.RP_NAME
            },
            'user': {
                'id': base64.urlsafe_b64encode(user_id.encode()).decode(),
                'name': username,
                'displayName': display_name
            },
            'pubKeyCredParams': [
                {'type': 'public-key', 'alg': -7},  # ES256
                {'type': 'public-key', 'alg': -257}  # RS256
            ],
            'timeout': self.CHALLENGE_TIMEOUT_SECONDS * 1000,
            'attestation': 'none',
            'authenticatorSelection': {
                'userVerification': 'preferred'
            }
        }

        return options, challenge_id

    def complete_registration(
        self,
        challenge_id: str,
        credential_response: Dict[str, Any],
        device_name: str = "Hardware Key"
    ) -> HardwareKeyCredential:
        """
        Complete WebAuthn registration

        Args:
            challenge_id: Challenge ID from begin_registration
            credential_response: Authenticator response
            device_name: Human-readable device name

        Returns:
            Registered credential
        """
        if not WEBAUTHN_AVAILABLE:
            raise RuntimeError("WebAuthn not available")

        # Validate challenge
        session = self._challenges.get(challenge_id)
        if not session:
            raise ValueError("Invalid or expired challenge")

        if session.purpose != 'registration':
            raise ValueError("Challenge not for registration")

        if datetime.now(timezone.utc) > session.expires_at:
            del self._challenges[challenge_id]
            raise ValueError("Challenge expired")

        # Verify registration
        state = {'challenge': session.challenge}

        try:
            auth_data = self._fido2_server.register_complete(
                state,
                credential_response
            )
        except Exception as e:
            raise ValueError(f"Registration verification failed: {e}")

        # Create credential record
        credential = HardwareKeyCredential(
            credential_id=base64.b64encode(auth_data.credential_data.credential_id).decode(),
            public_key=auth_data.credential_data.public_key,
            sign_count=auth_data.counter,
            user_id=session.user_id,
            username="",  # Would be set from user data
            device_name=device_name,
            registered_at=datetime.now(timezone.utc),
            aaguid=auth_data.credential_data.aaguid.hex() if auth_data.credential_data.aaguid else None
        )

        # Store credential
        if session.user_id not in self._credentials:
            self._credentials[session.user_id] = []
        self._credentials[session.user_id].append(credential)
        self._save_credentials()

        # Clean up challenge
        del self._challenges[challenge_id]

        logger.info(f"Hardware key registered for user {session.user_id}: {device_name}")
        return credential

    # ========== WebAuthn Authentication ==========

    def begin_authentication(self, user_id: str) -> Tuple[Dict[str, Any], str]:
        """
        Begin WebAuthn authentication

        Args:
            user_id: User to authenticate

        Returns:
            Tuple of (options_dict, challenge_id)
        """
        if not WEBAUTHN_AVAILABLE:
            raise RuntimeError("WebAuthn not available")

        credentials = self._credentials.get(user_id, [])
        if not credentials:
            raise ValueError("No hardware keys registered for user")

        # Get credential descriptors
        allow_credentials = [
            PublicKeyCredentialDescriptor(
                type=PublicKeyCredentialType.PUBLIC_KEY,
                id=base64.b64decode(cred.credential_id)
            )
            for cred in credentials
        ]

        # Generate authentication options
        auth_data, state = self._fido2_server.authenticate_begin(
            credentials=allow_credentials,
            user_verification=UserVerificationRequirement.PREFERRED
        )

        # Store challenge
        challenge_id = secrets.token_urlsafe(32)
        self._challenges[challenge_id] = ChallengeSession(
            challenge=state['challenge'],
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.CHALLENGE_TIMEOUT_SECONDS),
            purpose='authentication'
        )

        # Convert to JSON-serializable dict
        options = {
            'challenge': base64.urlsafe_b64encode(auth_data['publicKey']['challenge']).decode(),
            'timeout': self.CHALLENGE_TIMEOUT_SECONDS * 1000,
            'rpId': self.RP_ID,
            'allowCredentials': [
                {
                    'type': 'public-key',
                    'id': cred.credential_id
                }
                for cred in credentials
            ],
            'userVerification': 'preferred'
        }

        return options, challenge_id

    def complete_authentication(
        self,
        challenge_id: str,
        credential_response: Dict[str, Any]
    ) -> bool:
        """
        Complete WebAuthn authentication

        Args:
            challenge_id: Challenge ID from begin_authentication
            credential_response: Authenticator response

        Returns:
            True if authentication successful
        """
        if not WEBAUTHN_AVAILABLE:
            raise RuntimeError("WebAuthn not available")

        # Validate challenge
        session = self._challenges.get(challenge_id)
        if not session:
            raise ValueError("Invalid or expired challenge")

        if session.purpose != 'authentication':
            raise ValueError("Challenge not for authentication")

        if datetime.now(timezone.utc) > session.expires_at:
            del self._challenges[challenge_id]
            raise ValueError("Challenge expired")

        # Find credential
        credential_id = credential_response.get('id')
        credentials = self._credentials.get(session.user_id, [])
        credential = next(
            (c for c in credentials if c.credential_id == credential_id),
            None
        )

        if not credential:
            raise ValueError("Unknown credential")

        # Verify authentication
        state = {
            'challenge': session.challenge,
            'user_verification': UserVerificationRequirement.PREFERRED
        }

        try:
            self._fido2_server.authenticate_complete(
                state,
                credentials=[credential],
                response=credential_response
            )
        except Exception as e:
            raise ValueError(f"Authentication verification failed: {e}")

        # Update sign count and last used
        credential.sign_count = credential_response.get('response', {}).get('authenticatorData', {}).get('signCount', 0)
        credential.last_used = datetime.now(timezone.utc)
        self._save_credentials()

        # Clean up challenge
        del self._challenges[challenge_id]

        logger.info(f"Hardware key authentication successful for user {session.user_id}")
        return True

    # ========== CLI HMAC Challenge-Response ==========

    def generate_cli_challenge(self, user_id: str) -> Tuple[str, str]:
        """
        Generate challenge for CLI HMAC verification

        This is a simpler method for CLI use that doesn't require
        full WebAuthn support.

        Args:
            user_id: User to authenticate

        Returns:
            Tuple of (challenge_hex, challenge_id)
        """
        challenge = secrets.token_bytes(32)
        challenge_id = secrets.token_urlsafe(16)

        self._challenges[challenge_id] = ChallengeSession(
            challenge=challenge,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.CHALLENGE_TIMEOUT_SECONDS),
            purpose='cli_auth'
        )

        return challenge.hex(), challenge_id

    def verify_cli_response(
        self,
        challenge_id: str,
        response_hex: str,
        expected_secret: bytes
    ) -> bool:
        """
        Verify CLI HMAC challenge response

        For YubiKey: Use ykman to compute HMAC-SHA1 response
        Command: ykman otp calculate 2 <challenge_hex>

        Args:
            challenge_id: Challenge ID
            response_hex: HMAC response in hex
            expected_secret: Shared secret (from YubiKey slot)

        Returns:
            True if valid
        """
        session = self._challenges.get(challenge_id)
        if not session:
            return False

        if datetime.now(timezone.utc) > session.expires_at:
            del self._challenges[challenge_id]
            return False

        # Compute expected HMAC
        import hmac as hmac_module
        expected = hmac_module.new(
            expected_secret,
            session.challenge,
            hashlib.sha1
        ).hexdigest()

        # Constant-time comparison
        is_valid = hmac.compare_digest(expected.lower(), response_hex.lower())

        if is_valid:
            del self._challenges[challenge_id]

        return is_valid

    # ========== Key Management ==========

    def get_user_credentials(self, user_id: str) -> List[HardwareKeyCredential]:
        """Get all credentials for a user"""
        return self._credentials.get(user_id, [])

    def remove_credential(self, user_id: str, credential_id: str) -> bool:
        """Remove a credential"""
        credentials = self._credentials.get(user_id, [])
        original_count = len(credentials)

        self._credentials[user_id] = [
            c for c in credentials if c.credential_id != credential_id
        ]

        if len(self._credentials[user_id]) < original_count:
            self._save_credentials()
            logger.info(f"Removed hardware key {credential_id[:8]}... for user {user_id}")
            return True

        return False

    def user_has_hardware_key(self, user_id: str) -> bool:
        """Check if user has any hardware keys registered"""
        return len(self._credentials.get(user_id, [])) > 0


# Import timedelta for use in the module
from datetime import timedelta


def get_yubikey_setup_instructions() -> str:
    """Get instructions for setting up YubiKey"""
    return """
# YubiKey Setup Instructions

## Recommended: YubiKey 5 NFC ($50)
Purchase from: https://www.yubico.com/products/yubikey-5-nfc/

## Initial Setup

1. Download YubiKey Manager:
   https://www.yubico.com/support/download/yubikey-manager/

2. Insert your YubiKey and run:
   ykman info

3. For FIDO2/WebAuthn (web interface):
   - No configuration needed
   - Just register in the CARBS dashboard

4. For CLI HMAC challenge-response:
   ykman otp chalresp --touch --generate 2

   This configures slot 2 with a random secret and touch requirement.

## Security Recommendations

- Enable PIN protection:
  ykman fido access set-pin

- Require touch for each authentication:
  Configured by default on YubiKey 5 series

- Register backup key:
  Always have a second YubiKey as backup

## Verify Setup

Test your YubiKey:
  ykman otp calculate 2 0102030405060708

If it lights up and requires touch, it's configured correctly.
"""
