# CARBS Security Architecture Audit Report

**Date:** 2026-03-21
**Auditor:** Adversarial Principal Architect / Red Team
**Scope:** Full codebase — `crypto-arbitrage-system/src/`, `tests/`, `config/`
**Method:** Static analysis, control flow tracing, adversarial logic scrutiny

---

## Executive Summary

This audit identified **3 Critical**, **5 High**, and **4 Medium** severity findings across concurrency safety, trust boundaries, financial calculation integrity, and API security. The system has solid fundamentals (circuit breakers, encrypted credentials, balance locking) but contains several exploitable design flaws that could cause **capital loss**, **orphaned positions**, or **unauthorized system manipulation** under adversarial or high-concurrency conditions.

---

## CRITICAL Findings

### C1: TOCTOU Race in Balance Lock Acquisition

**Severity:** Critical
**Location:** `src/core/balance_manager.py:493-502`

**Architectural Root Cause:**
`get_available_balance()` is called *outside* the `async with self._lock:` block. Between the balance check (line 494) and the lock acquisition (line 502), another coroutine can acquire the same balance, leading to double-spend.

**Code:**
```python
# Line 494: CHECK happens here — NO LOCK
available = self.get_available_balance(exchange, asset)
if available < amount:
    return None

# Line 502: USE happens here — LOCK acquired too late
async with self._lock:
    self._lock_counter += 1
    lock_id = f"lock_{exchange}_{asset}_{self._lock_counter}"
    ...
    self._locks[lock_id] = lock
```

**Exploit/Failure Trace:**
1. Coroutine A calls `lock_balance("binance", "USDT", 50000)` — checks available = 50000, passes
2. Coroutine B calls `lock_balance("binance", "USDT", 50000)` — checks available = 50000, passes (A hasn't locked yet)
3. Coroutine A acquires `self._lock`, creates lock, deducts 50000
4. Coroutine B acquires `self._lock`, creates lock, deducts 50000
5. **Result:** 100000 USDT locked against 50000 available. Both trades execute, one will fail at the exchange, leaving an orphaned position.

**Structural Remediation:**
```python
async def lock_balance(self, exchange: str, asset: str, amount: Decimal,
                       trade_id: str = None) -> Optional[str]:
    async with self._lock:  # Move lock to encompass the check
        available = self.get_available_balance(exchange, asset)
        if available < amount:
            logger.warning(
                f"Cannot lock {amount} {asset} on {exchange}: "
                f"only {available} available"
            )
            return None

        self._lock_counter += 1
        lock_id = f"lock_{exchange}_{asset}_{self._lock_counter}"
        now = datetime.now(timezone.utc)
        lock = BalanceLock(
            lock_id=lock_id, exchange=exchange, asset=asset,
            amount=amount, created_at=now,
            expires_at=now + timedelta(seconds=self.lock_timeout),
            trade_id=trade_id
        )
        self._locks[lock_id] = lock
        return lock_id
```

---

### C2: TOCTOU Race in Balance Update Guard

**Severity:** Critical
**Location:** `src/core/balance_manager.py:246-250, 312`

**Architectural Root Cause:**
`update_in_progress` is a plain boolean used as a mutex. The check (line 246) and set (line 250) are not atomic — they happen outside any lock. The `self._lock` is only acquired later at line 265 for the actual balance write.

**Code:**
```python
if exchange_balances.update_in_progress:       # Line 246: CHECK
    return False

exchange_balances.update_in_progress = True    # Line 250: SET (not atomic with check)

try:
    raw_balances = await exchange.fetch_balance()  # Long async operation
    async with self._lock:                         # Line 265: Lock only here
        for asset, balance in raw_balances.items():
            ...
finally:
    exchange_balances.update_in_progress = False    # Line 312: RESET
```

**Exploit/Failure Trace:**
1. Coroutine A: reads `update_in_progress=False`, yields at await point before line 250
2. Coroutine B: reads `update_in_progress=False`, sets it to `True`, starts fetching
3. Coroutine A: resumes, sets `update_in_progress=True`, starts second fetch
4. Both coroutines write overlapping balance snapshots — last write wins
5. **Result:** Stale/inconsistent balance data drives trade decisions

**Structural Remediation:**
Replace boolean with per-exchange `asyncio.Lock()`:
```python
# In __init__:
self._update_locks = {name: asyncio.Lock() for name in exchanges}

# In _refresh_exchange_balances:
async with self._update_locks[exchange_name]:
    raw_balances = await exchange.fetch_balance()
    async with self._lock:
        # ... update self._balances ...
```

---

### C3: Silent Execution Without Balance Validation

**Severity:** Critical
**Location:** `src/core/execution_engine.py:659-662`

**Architectural Root Cause:**
When `balance_manager` is `None`, the engine logs a warning but proceeds to execute real trades without any balance check. This bypasses the entire capital safety system.

**Code:**
```python
else:
    quote_lock = None
    base_lock = None
    logger.warning("No balance manager - executing without balance validation!")
```

**Exploit/Failure Trace:**
1. `ExecutionEngine` initialized without `balance_manager` (possible via config error or test leak)
2. System detects arbitrage opportunity for 10 BTC
3. No balance check — orders placed against insufficient funds
4. Buy order rejected by exchange (insufficient USDT)
5. Sell order fills (exchange had BTC from prior trades)
6. **Result:** Net short 10 BTC on sell exchange with no buy to match. Catastrophic loss.

**Structural Remediation:**
```python
if not self.balance_manager:
    raise RuntimeError(
        "Cannot execute arbitrage without BalanceManager. "
        "Configure balance_manager or use paper trading mode."
    )
```

---

## HIGH Findings

### H1: Antifragile State Transitions Without Lock

**Severity:** High
**Location:** `src/core/antifragile.py:228-233`

**Architectural Root Cause:**
`self.state` and `self.params` are mutated without any synchronization primitive. These are read concurrently by risk management and execution code paths.

**Code:**
```python
if self.conditions.volatility > 0.05:
    self.params.position_size_multiplier = 0.5    # NO LOCK
    self.params.stop_loss_percent = 0.04           # NO LOCK
    if self.state != SystemState.HALTED:
        self.state = SystemState.DEFENSIVE          # NO LOCK
```

**Exploit/Failure Trace:**
1. Antifragile detects high volatility, begins writing `params.position_size_multiplier = 0.5`
2. Risk manager reads `state = NORMAL` (not yet updated to DEFENSIVE)
3. Risk manager approves full-size position based on NORMAL state
4. Antifragile finishes: state = DEFENSIVE, but position already approved at 1.0x
5. **Result:** Oversized position during high volatility — exactly when reduced sizing is most critical.

**Structural Remediation:**
Add `asyncio.Lock()` protecting all state/params mutations in `AntifragileCore`, and read params only under lock.

---

### H2: Missing Permission Check on Emergency Resume

**Severity:** High
**Location:** `src/api/server.py:436-453`

**Architectural Root Cause:**
The `emergency_stop` endpoint (line 398) correctly checks `Permission.TRADE_EMERGENCY_STOP` via `_access_control.check_permission()`. But the `emergency_resume` endpoint (line 436) has **no permission check** — any authenticated user can resume trading after an emergency stop.

**Code (emergency_stop — correct):**
```python
decision = _access_control.check_permission(
    session.username, session.role,
    Permission.TRADE_EMERGENCY_STOP, ip
)
if not decision.allowed:
    raise HTTPException(status_code=403, detail=decision.reason)
```

**Code (emergency_resume — missing):**
```python
async def emergency_resume(request: Request, session=Depends(get_current_user)):
    # NO permission check!
    success = _emergency_controls.deactivate_emergency_stop(...)
```

**Exploit/Failure Trace:**
1. Admin triggers emergency stop due to suspected market manipulation
2. Low-privilege `viewer` user (authenticated) calls `POST /api/v1/emergency/resume`
3. No permission check — `deactivate_emergency_stop()` called directly
4. Trading resumes during hostile market conditions
5. **Result:** Unauthorized override of safety controls.

**Structural Remediation:**
```python
@app.post("/api/v1/emergency/resume")
async def emergency_resume(request: Request, session=Depends(get_current_user)):
    if not _emergency_controls or not _access_control:
        raise HTTPException(status_code=503, detail="Service not ready")

    ip = request.client.host if request.client else "unknown"
    decision = _access_control.check_permission(
        session.username, session.role,
        Permission.TRADE_EMERGENCY_STOP, ip
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)
    # ... rest of handler
```

---

### H3: Credential Key Derivation Non-Deterministic — Cannot Decrypt After Restart

**Severity:** High
**Location:** `src/utils/secure_credentials.py:37-62, 65-78`

**Architectural Root Cause:**
`_get_machine_entropy()` uses `os.getpid()`, `secrets.token_bytes(16)`, and `time.time_ns()` — all of which change between invocations. The derived key used for encryption will never be the same across two calls. While this makes individual `SecureString` instances work within a single process lifetime, it means:

1. `_derive_key()` is called on both `store()` and `retrieve()` paths
2. Each call to `_derive_key()` internally calls `_get_machine_entropy()` which generates **new** random bytes
3. **The derived key on `retrieve()` will NEVER match the key used during `store()`**

**Wait — re-examination:** Looking more carefully, `_derive_key` is called with `self._master_salt + cred.salt` as input, and uses `_get_machine_entropy()` as the PBKDF2 *password*. Since entropy changes every call, retrieval should fail with `InvalidToken` from Fernet.

**However**, the `SecureCredentialStore` stores credentials in-memory within a single process. If `_get_machine_entropy()` returns different values on each call, decryption would consistently fail. This suggests either: (a) the code is broken and tests don't cover it, or (b) PBKDF2 somehow absorbs this (it doesn't — different password = different key).

**Structural Impact:** This is a latent bug. If `CRYPTO_AVAILABLE=True`, every `retrieve()` call after `store()` will fail with a Fernet `InvalidToken` exception, which is caught and returns `None` (line 200). The system then falls back to `SecureString` raising `ValueError("SecureString has been cleared or corrupted")`.

**The fallback XOR path has the same bug** — different entropy = different key = garbled plaintext.

**Practical Impact:** If this code path is actually exercised, no credential can be retrieved. The system likely works because credentials are loaded from `.env` directly, bypassing `SecureCredentialStore` in practice. This makes the entire secure credential subsystem **dead code** or **silently broken**.

**Structural Remediation:**
Cache the machine entropy at instance creation time:
```python
class SecureCredentialStore:
    def __init__(self, ...):
        self._entropy = _get_machine_entropy()  # Cache once

# Then in _derive_key, accept entropy as parameter:
def _derive_key(salt: bytes, entropy: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    return base64.urlsafe_b64encode(kdf.derive(entropy))
```

---

### H4: Default Taker Fee Masks Real Trading Costs

**Severity:** High
**Location:** `src/core/engine.py:303-304`, `src/advanced_main.py:470-471`

**Architectural Root Cause:**
Fee lookup uses `.get('taker_fee', 0.001)` — defaulting to 0.1% if not configured. Real exchange fees vary from 0.04% to 0.6%. A missing config entry silently uses the wrong fee, causing the system to calculate false profits and execute losing trades.

**Code:**
```python
buy_fee = Decimal(str(self.config.exchanges[buy_ob.exchange].get('taker_fee', 0.001)))
sell_fee = Decimal(str(self.config.exchanges[sell_ob.exchange].get('taker_fee', 0.001)))
```

**Exploit/Failure Trace:**
1. Operator adds Coinbase exchange (taker fee = 0.6%) but forgets to set `taker_fee` in config
2. System defaults to 0.1% fee
3. Detected spread: 0.5% → Net spread calc: 0.5% - 0.1% - 0.1% = 0.3% profit
4. Reality: 0.5% - 0.6% - 0.6% = **-0.7% loss**
5. System executes losing trades until daily loss limit triggers

**Structural Remediation:**
```python
try:
    buy_fee = Decimal(str(self.config.exchanges[buy_ob.exchange]['taker_fee']))
except KeyError:
    raise ConfigurationError(
        f"taker_fee not configured for '{buy_ob.exchange}'. "
        f"Set exchanges.{buy_ob.exchange}.taker_fee in config.yaml"
    )
```

---

### H5: Circuit Breaker Half-Open Window Contamination

**Severity:** High
**Location:** `src/utils/resilience.py:278-283`

**Architectural Root Cause:**
When transitioning to HALF_OPEN, the sliding window still contains failure outcomes from the CLOSED state. The success check counts all successes in the entire window, not just those accumulated since entering HALF_OPEN.

**Code:**
```python
if self._state == CircuitState.HALF_OPEN:
    self._half_open_calls -= 1
    success_count = sum(1 for o in self._window._outcomes if o)  # Counts ALL history
    if success_count >= self.config.success_threshold:
        await self._transition_to(CircuitState.CLOSED)
```

**Exploit/Failure Trace:**
1. Window = [FAIL, FAIL, FAIL, FAIL, FAIL, SUCCESS, SUCCESS, SUCCESS, SUCCESS, SUCCESS]
2. Circuit opens after failures
3. Timeout expires → HALF_OPEN
4. First probe call succeeds → window now has old successes + 1 new
5. `success_count = 6 >= success_threshold(3)` → immediately CLOSES
6. But 50% of window is failures → next failure immediately reopens
7. **Result:** Circuit thrashes between HALF_OPEN and OPEN, never stabilizing

**Structural Remediation:**
Reset or segment the window on state transitions:
```python
async def _transition_to(self, new_state: CircuitState):
    if new_state == CircuitState.HALF_OPEN:
        self._window.reset()  # Clear contaminated history
        self._half_open_successes = 0
    # ...

async def _on_success(self, duration: float):
    if self._state == CircuitState.HALF_OPEN:
        self._half_open_successes += 1
        if self._half_open_successes >= self.config.success_threshold:
            await self._transition_to(CircuitState.CLOSED)
```

---

## MEDIUM Findings

### M1: Partial Fill Rebalancing Can Cascade Failures

**Severity:** Medium
**Location:** `src/core/execution_engine.py:1009-1054`

**Architectural Root Cause:**
`_rebalance_partial_fills()` exists but attempts to sell/buy the imbalance on the *same exchange* as the partially-filled leg. If the exchange is experiencing issues (which likely caused the partial fill), the rebalance order will also fail, potentially leaving the position worse.

Additionally, the rebalance order uses the *original order's price* — not the current market price — meaning it may never fill if the market has moved.

**Structural Remediation:**
Use current market price for rebalancing, add a timeout, and fall back to market orders if limit orders don't fill within a threshold.

---

### M2: Unwind Orders Use Stale Prices

**Severity:** Medium
**Location:** `src/core/execution_engine.py:707, 716`

**Code:**
```python
# If sell succeeded, need to unwind
await self._execute_order(sell_exchange, symbol, 'buy',
    sell_order.filled_amount, sell_order.avg_fill_price)  # Stale price
```

**Architectural Root Cause:**
When unwinding a position after one leg fails, the code uses `sell_order.avg_fill_price` as the limit price. In a fast-moving market, this price may no longer be available, causing the unwind order to sit unfilled while the position bleeds.

**Structural Remediation:**
Use a market order or aggressive limit price (e.g., mid_price ± 0.5%) for unwind orders, since speed of exit trumps price optimization during error recovery.

---

### M3: Prometheus Metrics Server Binds Without Auth

**Severity:** Medium
**Location:** `src/api/health.py:698`

**Code:**
```python
start_http_server(port)  # prometheus_client default server — no auth
```

**Architectural Root Cause:**
Prometheus metrics are exposed on an unauthenticated HTTP port. While metrics themselves aren't secrets, they leak:
- Trading volume, profit/loss, active positions per exchange
- Exchange latency patterns (useful for timing attacks)
- Circuit breaker states (reveals which exchanges are degraded)
- Balance information per exchange/currency

**Structural Remediation:**
Either bind to localhost only, or proxy through the authenticated FastAPI server.

---

### M4: Secure Credential Delete Is Ineffective

**Severity:** Medium
**Location:** `src/utils/secure_credentials.py:220-233`

**Code:**
```python
def delete(self, key: str) -> bool:
    cred = self._credentials[key]
    random_overwrite = secrets.token_bytes(len(cred.ciphertext))
    cred = EncryptedCredential(        # Creates NEW object
        ciphertext=random_overwrite,
        salt=secrets.token_bytes(16),
        created_at=0
    )
    del self._credentials[key]          # Deletes reference to ORIGINAL
```

**Architectural Root Cause:**
The "secure overwrite" creates a *new* `EncryptedCredential` and assigns it to the local variable `cred`, but never writes it back to `self._credentials[key]`. The original ciphertext remains in memory until Python's garbage collector reclaims it. In CPython, `bytes` objects are immutable — you cannot overwrite their contents in place.

This is security theater — the overwrite has no effect on the original data.

**Structural Remediation:**
In Python, truly secure memory clearing is difficult with immutable types. The honest approach:
```python
def delete(self, key: str) -> bool:
    with self._lock:
        if key not in self._credentials:
            return False
        # Cannot securely clear immutable bytes in Python.
        # Best effort: remove reference and force GC.
        del self._credentials[key]
        import gc
        gc.collect()
    return True
```

---

## Summary Table

| ID | Severity | Component | Issue | File:Lines |
|----|----------|-----------|-------|------------|
| C1 | **Critical** | balance_manager | TOCTOU race in lock acquisition | balance_manager.py:493-502 |
| C2 | **Critical** | balance_manager | Boolean mutex — not atomic | balance_manager.py:246-312 |
| C3 | **Critical** | execution_engine | Trades without balance validation | execution_engine.py:659-662 |
| H1 | **High** | antifragile | State mutation without lock | antifragile.py:228-233 |
| H2 | **High** | API server | Missing permission on emergency resume | server.py:436-453 |
| H3 | **High** | secure_credentials | Key derivation non-deterministic | secure_credentials.py:37-78 |
| H4 | **High** | engine | Default fee masks real costs | engine.py:303-304 |
| H5 | **High** | resilience | Circuit breaker window contamination | resilience.py:278-283 |
| M1 | **Medium** | execution_engine | Rebalance uses same failing exchange | execution_engine.py:1009-1054 |
| M2 | **Medium** | execution_engine | Unwind uses stale prices | execution_engine.py:707,716 |
| M3 | **Medium** | health/metrics | Prometheus exposed without auth | health.py:698 |
| M4 | **Medium** | secure_credentials | Secure delete is no-op | secure_credentials.py:220-233 |

---

## Recommendations (Priority Order)

### Immediate (Block Live Trading)
1. Fix C1: Move balance availability check inside `async with self._lock`
2. Fix C2: Replace `update_in_progress` boolean with `asyncio.Lock()` per exchange
3. Fix C3: Raise `RuntimeError` if `balance_manager` is `None` during execution

### Before Production
4. Fix H2: Add `check_permission(Permission.TRADE_EMERGENCY_STOP)` to resume endpoint
5. Fix H3: Cache machine entropy at `SecureCredentialStore` instantiation
6. Fix H4: Remove default fee — require explicit config or fail fast
7. Fix H5: Reset sliding window on circuit breaker state transitions

### Hardening
8. Fix H1: Add state transition lock to `AntifragileCore`
9. Fix M2: Use aggressive limit/market orders for unwind scenarios
10. Fix M3: Bind Prometheus to localhost or proxy through authed API
11. Fix M4: Remove false "secure overwrite" — document Python's limitations honestly

---

## Appendix: Security Module Findings

The following additional findings were identified in the security subsystem (`src/security/`).

### S1: Hostname-Based Fallback Key Derivation (Critical)

**Location:** `src/security/auth.py:34-48`

**Issue:** When `CARBS_MASTER_KEY` and `CARBS_JWT_SECRET` are unset, the user data encryption key is derived from the machine hostname with a hardcoded salt. Hostnames are publicly discoverable — an attacker knowing the hostname can derive the encryption key and decrypt all user data.

```python
machine_id = f"carbs-{socket.gethostname()}-user-data"
master_key = machine_id  # Predictable!
salt = b'CARBS_USER_DATA_ENCRYPTION_SALT_'  # Hardcoded!
```

**Remediation:** Fail startup if `CARBS_MASTER_KEY` is not set. Never fall back to deterministic machine-based keys.

---

### S2: Unsafe Dynamic Approval Rule Modification (Critical)

**Location:** `src/security/approval_workflow.py:280-286`

**Issue:** `configure_rule()` uses `hasattr()`/`setattr()` to modify approval rules with no type or value validation:

```python
for key, value in kwargs.items():
    if hasattr(rule, key):
        setattr(rule, key, value)  # No validation
```

**Exploit:** An attacker (or misconfigured code) can set `required_approvers=0` to bypass quorum requirements, or `allow_self_approval=True` to self-approve mode switches from paper to live trading.

**Remediation:** Whitelist allowed parameters and validate types/ranges.

---

### S3: TOCTOU in Trade Approval Check (High)

**Location:** `src/security/approval_workflow.py:700-724`

**Issue:** `check_trade_approval()` checks `self._approved_trade_ids[trade_id]` without synchronization. Between the dict lookup and the trade execution, another coroutine can expire or remove the approval via `mark_trade_approved()`.

**Remediation:** Use `asyncio.Lock()` around check-and-consume, and atomically remove the approval on use.

---

### S4: JWT Payload Type Confusion (High)

**Location:** `src/security/auth.py:666+`

**Issue:** JWT payload fields (`session_id`, `username`, `role`) are read via `.get()` without type validation. A crafted JWT with `session_id: {"key": "value"}` or `role: ["admin"]` could cause authorization logic to behave unexpectedly.

**Remediation:** Validate all JWT claim types after decode:
```python
if not isinstance(session_id, str) or not session_id:
    raise TokenError("Invalid session_id in token")
```

---

### S5: IP Spoofing via Broad Trusted Proxy Networks (Medium)

**Location:** `src/api/middleware.py:36-41`

**Issue:** Trusted proxy networks include the entire `172.16.0.0/12` range (1M+ IPs). In shared hosting or multi-tenant environments, this could trust unintended proxies, allowing `X-Forwarded-For` spoofing to bypass IP-based rate limiting and access controls.

**Remediation:** Restrict to actual deployment network (e.g., `172.17.0.0/16` for Docker default bridge).

---

### S6: Race Condition in IP Rate Limiting (Medium)

**Location:** `src/security/auth.py:412-431`

**Issue:** `_check_ip_rate_limit()` performs a non-atomic read-modify-write on `self._ip_attempts`. Concurrent login attempts can bypass the rate limit because the check and append are not synchronized.

**Remediation:** Wrap the entire check-and-add in a lock, or use an atomic counter.

---

### S7: Floating-Point Precision Loss in Risk Calculations (High)

**Location:** `src/core/risk_manager.py:463, 492, 550`

**Issue:** Financial calculations convert `Decimal` to `float()` for Sharpe ratio, position sizing, and VaR, then convert back via `Decimal(str(float_val))`. This introduces rounding errors that accumulate across many trades. In a high-frequency arbitrage system, sub-basis-point errors in position sizing can compound into material P&L discrepancies.

**Remediation:** Keep all financial math in `Decimal`; only convert to `float` for display/logging.

---

## Addendum — Deep Audit Pass (2026-03-21)

A second-pass adversarial review identified and resolved the following additional findings:

### A1: Authorization Bypass in Approval Cancellation (Critical — FIXED)

**Location:** `src/security/approval_workflow.py:676-679`

**Issue:** `cancel_request()` docstring stated "Only the requester or admin can cancel" but the implementation had a `pass` placeholder — any user could cancel any approval request. This allowed an attacker to cancel pending mode-switch approvals (which require 2 admins), bypassing multi-signature requirements.

**Fix:** Added `canceller_role` parameter; non-requesters must have a role in the operation's `required_roles` list.

### A2: Notification Callback Crash Aborts Approval Workflow (High — FIXED)

**Location:** `src/security/approval_workflow.py` — `create_request()`, `approve()`, `reject()`

**Issue:** All three methods called `self.notification_callback()` without try/except. A failed notification (network timeout, misconfigured webhook) would propagate as an unhandled exception, crashing the operation mid-lock — potentially leaving state inconsistent (e.g., approval recorded in memory but notification throws before `_save_state()`).

**Fix:** Wrapped all notification callbacks in try/except with error logging.

### A3: Race Condition in Trade Approval Cleanup (Medium — FIXED)

**Location:** `src/security/approval_workflow.py:779-783` — `mark_trade_approved()`

**Issue:** Dict cleanup (`self._approved_trade_ids = {...}`) ran outside the `_approval_lock`, creating a race where `check_trade_approval()` could read a partially-replaced dict.

**Fix:** Moved cleanup inside the lock.

### A4: Stale Balance Data Silently Passes Trade Validation (Critical — FIXED)

**Location:** `src/core/balance_manager.py:403-408`

**Issue:** When balance data exceeded `stale_threshold` (60s), the code logged a warning but continued to validate the trade as OK. This means trades could execute against stale balances — causing overdrafts, failed orders, or cascading losses from rejected fills.

**Fix:** Changed to return `(False, "Stale balance data...")` to reject trades with stale data.

### A5: TOCTOU in Balance Lock Acquisition (Critical — FIXED)

**Location:** `src/core/balance_manager.py:493-502`

**Issue:** `get_available_balance()` was called outside the `async with self._lock:` block. Between the check and the lock acquisition, another coroutine could acquire the same balance, leading to double-allocation of funds.

**Fix:** Moved the availability check inside the lock so check-and-lock is atomic.

### A6: Non-Numeric Balance Crashes Graceful Shutdown (Medium — FIXED)

**Location:** `src/core/graceful_shutdown.py:384-387`

**Issue:** `Decimal(free_balance)` could throw `InvalidOperation` on non-numeric strings returned by exchanges, crashing the position-closing loop during shutdown and leaving positions orphaned.

**Fix:** Added try/except around the conversion with a continue to skip un-parseable balances.

### A7: CORS Allows Empty-String Origin (Medium — FIXED)

**Location:** `src/api/server.py:143`

**Issue:** `''.split(',')` produces `['']` (a list with one empty string), which is truthy so `or []` never triggers. An empty-string origin in the allowed list could match requests with no `Origin` header on some CORS implementations.

**Fix:** Changed to list comprehension that strips and filters empty strings.

### A8: TOTP Token Comparison is Timing-Vulnerable (High — FIXED)

**Location:** `src/security/auth.py:189`

**Issue:** TOTP verification compared tokens with `==`, which short-circuits on first mismatched character. An attacker with precise timing could determine the correct TOTP token character-by-character (6-digit TOTP × ~10 possibilities = ~60 timing measurements instead of 10^6 brute force).

**Fix:** Replaced `==` with `hmac.compare_digest()` for constant-time comparison.
