"""
Secure API Server

FastAPI-based REST API with:
- JWT authentication
- Rate limiting
- Audit logging
- Emergency controls
"""

import os
import time
import secrets
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

# FastAPI imports (optional dependency)
try:
    from fastapi import FastAPI, HTTPException, Depends, Request, status
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from security.auth import AuthenticationManager, AuthError, TokenError
from security.access_control import AccessControl, Permission, EmergencyControls
from security.audit import get_audit_logger, AuditCategory
from security.encryption import SecretsManager
from .middleware import SecurityMiddleware, RateLimiter

logger = logging.getLogger(__name__)


# Pydantic models for API
if FASTAPI_AVAILABLE:
    class LoginRequest(BaseModel):
        username: str
        password: str
        totp_token: Optional[str] = None

    class LoginResponse(BaseModel):
        access_token: str
        refresh_token: str
        token_type: str = "bearer"
        expires_in: int
        role: str

    class RefreshRequest(BaseModel):
        refresh_token: str

    class StatusResponse(BaseModel):
        status: str
        mode: str
        emergency_stop: bool
        uptime_seconds: int
        opportunities_detected: int
        opportunities_executed: int
        total_profit: float

    class ErrorResponse(BaseModel):
        error: str
        message: str
        request_id: str


# Global instances (would be properly injected in production)
_auth_manager: Optional[AuthenticationManager] = None
_access_control: Optional[AccessControl] = None
_emergency_controls: Optional[EmergencyControls] = None
_security_middleware: Optional[SecurityMiddleware] = None
_start_time: float = time.time()


def create_app() -> 'FastAPI':
    """Create and configure FastAPI application"""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn")

    global _auth_manager, _access_control, _emergency_controls, _security_middleware

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan management"""
        global _auth_manager, _access_control, _emergency_controls, _security_middleware, _start_time

        logger.info("Starting CARBS API server...")

        # Initialize components
        _auth_manager = AuthenticationManager()
        _access_control = AccessControl()
        _emergency_controls = EmergencyControls(_access_control)
        _security_middleware = SecurityMiddleware(
            auth_manager=_auth_manager,
            access_control=_access_control,
            audit_logger=get_audit_logger()
        )
        _start_time = time.time()

        logger.info("API server started")
        yield

        logger.info("Shutting down API server...")
        audit = get_audit_logger()
        audit.shutdown()

    app = FastAPI(
        title="CARBS API",
        description="Crypto ARBitrage System - Secure Trading API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan
    )

    # CORS - restrictive by default
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv('CORS_ORIGINS', '').split(',') or [],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Security headers middleware
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Cache-Control"] = "no-store"

        return response

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = secrets.token_hex(8)
        start_time = time.time()

        # Log request
        logger.info(f"[{request_id}] {request.method} {request.url.path}")

        response = await call_next(request)

        # Log response
        duration = int((time.time() - start_time) * 1000)
        logger.info(f"[{request_id}] {response.status_code} ({duration}ms)")

        response.headers["X-Request-ID"] = request_id
        return response

    # Rate limiting middleware
    _rate_limiter = RateLimiter()

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        allowed, retry_after = _rate_limiter.check_limit(ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited", "retry_after": retry_after}
            )

        return await call_next(request)

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: 'FastAPI'):
    """Register API routes"""
    security = HTTPBearer()

    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
        """Dependency to get current authenticated user"""
        if not _auth_manager:
            raise HTTPException(status_code=503, detail="Service not ready")

        try:
            session = _auth_manager.verify_jwt(credentials.credentials)
            return session
        except TokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"}
            )

    # Health check (public)
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

    # Authentication
    @app.post("/api/v1/auth/login", response_model=LoginResponse)
    async def login(request: Request, data: LoginRequest):
        """Authenticate and get tokens"""
        if not _auth_manager:
            raise HTTPException(status_code=503, detail="Service not ready")

        ip = request.client.host if request.client else "unknown"

        try:
            session = _auth_manager.authenticate(
                username=data.username,
                password=data.password,
                totp_token=data.totp_token,
                ip_address=ip,
                user_agent=request.headers.get("user-agent", "unknown")
            )

            access_token = _auth_manager.create_jwt(session)
            expires_in = int((session.expires_at - session.created_at).total_seconds())

            return LoginResponse(
                access_token=access_token,
                refresh_token=session.refresh_token,
                expires_in=expires_in,
                role=session.role
            )

        except AuthError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )

    @app.post("/api/v1/auth/refresh", response_model=LoginResponse)
    async def refresh_token(data: RefreshRequest):
        """Refresh access token"""
        if not _auth_manager:
            raise HTTPException(status_code=503, detail="Service not ready")

        try:
            new_token, new_refresh = _auth_manager.refresh_session(data.refresh_token)

            # Get session info for response
            session = _auth_manager.verify_jwt(new_token)
            expires_in = int((session.expires_at - datetime.now(timezone.utc)).total_seconds())

            return LoginResponse(
                access_token=new_token,
                refresh_token=new_refresh,
                expires_in=expires_in,
                role=session.role
            )

        except TokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )

    @app.post("/api/v1/auth/logout")
    async def logout(session=Depends(get_current_user)):
        """Logout and revoke session"""
        _auth_manager.revoke_session(session.session_id)
        return {"message": "Logged out successfully"}

    # System status
    @app.get("/api/v1/status", response_model=StatusResponse)
    async def get_status(session=Depends(get_current_user)):
        """Get system status"""
        emergency_status = _emergency_controls.get_emergency_status() if _emergency_controls else {}

        return StatusResponse(
            status="running",
            mode="paper",
            emergency_stop=emergency_status.get('is_active', False),
            uptime_seconds=int(time.time() - _start_time),
            opportunities_detected=0,
            opportunities_executed=0,
            total_profit=0.0
        )

    # Emergency controls
    @app.post("/api/v1/emergency/stop")
    async def emergency_stop(request: Request, reason: str, session=Depends(get_current_user)):
        """Activate emergency stop"""
        if not _emergency_controls or not _access_control:
            raise HTTPException(status_code=503, detail="Service not ready")

        ip = request.client.host if request.client else "unknown"

        # Check permission
        decision = _access_control.check_permission(
            session.username,
            session.role,
            Permission.TRADE_EMERGENCY_STOP,
            ip
        )

        if not decision.allowed:
            raise HTTPException(status_code=403, detail=decision.reason)

        success = _emergency_controls.activate_emergency_stop(
            username=session.username,
            role=session.role,
            reason=reason,
            ip_address=ip
        )

        if success:
            audit = get_audit_logger()
            audit.log_security_event(
                action='emergency_stop_api',
                actor=session.username,
                resource='trading_system',
                details={'reason': reason}
            )
            return {"message": "Emergency stop activated", "reason": reason}

        raise HTTPException(status_code=403, detail="Failed to activate emergency stop")

    @app.post("/api/v1/emergency/resume")
    async def emergency_resume(request: Request, session=Depends(get_current_user)):
        """Deactivate emergency stop"""
        if not _emergency_controls or not _access_control:
            raise HTTPException(status_code=503, detail="Service not ready")

        ip = request.client.host if request.client else "unknown"

        success = _emergency_controls.deactivate_emergency_stop(
            username=session.username,
            role=session.role,
            ip_address=ip
        )

        if success:
            return {"message": "Emergency stop deactivated"}

        raise HTTPException(status_code=403, detail="Failed to deactivate emergency stop")

    @app.get("/api/v1/emergency/status")
    async def emergency_status(session=Depends(get_current_user)):
        """Get emergency stop status"""
        if not _emergency_controls:
            raise HTTPException(status_code=503, detail="Service not ready")

        return _emergency_controls.get_emergency_status()

    # Audit logs
    @app.get("/api/v1/audit")
    async def get_audit_logs(
        limit: int = 50,
        category: Optional[str] = None,
        session=Depends(get_current_user)
    ):
        """Get audit logs"""
        # Check permission
        if _access_control:
            decision = _access_control.check_permission(
                session.username,
                session.role,
                Permission.REPORT_AUDIT
            )
            if not decision.allowed:
                raise HTTPException(status_code=403, detail=decision.reason)

        audit = get_audit_logger()

        audit_category = None
        if category:
            try:
                audit_category = AuditCategory(category)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

        events = audit.query(category=audit_category, limit=limit)

        return {
            "events": [e.to_dict() for e in events],
            "total": len(events)
        }


async def run_api_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the API server"""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn")

    app = create_app()

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )

    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_api_server())
