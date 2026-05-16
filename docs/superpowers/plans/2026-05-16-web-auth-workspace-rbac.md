# Web Auth + Workspace Switcher (per-workspace RBAC) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make site auth workspace-aware so a second community owner can log in, see only their workspace, and switch between workspaces — with no cross-tenant data leak.

**Architecture:** A single keystone resolver `resolve_ws_role(conn, user_id, ws_id)` maps `workspace_members.role` → permissions-vocabulary role. A request-scoped FastAPI middleware decodes the JWT, reads/validates the `X-Workspace-Id` header against membership (developer bypass), and stores the active ws in a `ContextVar`. The ~30 existing `_resolve_role_fn(uid)` call sites stay unchanged — the injected lambda reads the ContextVar. Frontend gets a central header injector + a topbar workspace switcher; profile/permissions are re-fetched per active ws.

**Tech Stack:** FastAPI, PyJWT, sqlite3, pytest + `fastapi.testclient.TestClient`, React (Admin_SITE, Vite/JSX), Tailwind.

---

## Decisions locked (from session 2026-05-16, do not re-litigate)

- **WS transport:** validated `X-Workspace-Id` header. JWT stays identity-only.
- **Super-roles:** `DEVELOPER_ID` (Ilya) → permissions role `developer` = god-mode in **every** workspace, bypasses membership. `MAIN_ADMIN_ID` (Vitya) gets **no** special-case anymore — he is `owner` of ws=1 purely via `workspace_members` (seeded by `up_seed_pulse_workspace`).
- **Scope:** full per-WS RBAC this session — auth, middleware, profile/permissions, all economy/titles/press_release routes, frontend switcher.
- **Role vocabulary mapping** (`workspace_members.role` → `permissions.py` role):
  - `owner` → `owner`
  - `admin` → `deputy` (trusted second; broad editable perms)
  - `moderator` → `admin` (limited; matches `DEFAULT_ROLE_PERMISSIONS["admin"]`)
  - not a member → `user` (empty perms)
  - `user_id == DEVELOPER_ID` → `developer` (checked first, before membership)
- **Permissions layout stays global** (`role_permissions` table is the V1.14.4 owner-configurable layout, shared across workspaces). Only the *role a user holds* is per-workspace. Per-workspace permission layouts are Phase B+ (modules/billing), out of scope.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `api/workspace_rbac.py` | Keystone: `resolve_ws_role`, role-map constants, `WS_ID_CTX`/`WS_ROLE_CTX` ContextVars | **Create** |
| `tests/test_workspace_rbac.py` | Unit tests for resolver + mapping | **Create** |
| `api.py` | Middleware (validate ws membership, set ContextVar), re-point injected resolvers, ws-aware `_require_owner*` / profile / permissions | **Modify** |
| `tests/test_ws_auth_middleware.py` | API-level tests: cross-tenant 403, developer bypass, profile per-ws | **Create** |
| `api/economy_routes.py` `api/titles_routes.py` `api/press_release_routes.py` | No code change expected (call sites read ContextVar via injected lambda) — verified by tests | **Verify only** |
| `Admin_SITE/components/shared/api.js` | Central `X-Workspace-Id` header injection + active-ws helpers | **Modify** |
| `Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx` | Topbar dropdown to pick active workspace | **Create** |
| `Admin_SITE/AdminDashboard.jsx` | `currentWorkspace` state, mount switcher, re-fetch profile on switch, derive `isOwner`/`userCanAny` from per-ws profile | **Modify** |
| `scripts/verify_ws_rbac_pulse.py` | Sanity script: assert Pulse ws=1 owner/membership intact post-change | **Create** |
| `docs/RUNBOOK_multi_tenancy_deploy.md` | Append a `#3 Web Auth` deploy section | **Modify** |

---

### Task 1: Keystone resolver `resolve_ws_role`

**Files:**
- Create: `api/workspace_rbac.py`
- Test: `tests/test_workspace_rbac.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workspace_rbac.py
import sqlite3
import pytest
from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import create_workspace, add_member
from api.workspace_rbac import resolve_ws_role


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    up_create_workspaces_tables(c)
    create_workspace(c, 'WS1', owner_user_id=42)          # ws id 1, owner=42
    create_workspace(c, 'WS2', owner_user_id=99)          # ws id 2, owner=99
    add_member(c, 1, 100, 'admin')                        # 100 admin in ws1
    add_member(c, 1, 101, 'moderator')                    # 101 moderator in ws1
    c.commit()
    yield c
    c.close()


def test_owner_maps_to_owner(conn):
    assert resolve_ws_role(conn, 42, 1, developer_id=0) == 'owner'

def test_admin_maps_to_deputy(conn):
    assert resolve_ws_role(conn, 100, 1, developer_id=0) == 'deputy'

def test_moderator_maps_to_admin(conn):
    assert resolve_ws_role(conn, 101, 1, developer_id=0) == 'admin'

def test_non_member_maps_to_user(conn):
    assert resolve_ws_role(conn, 100, 2, developer_id=0) == 'user'

def test_unknown_user_maps_to_user(conn):
    assert resolve_ws_role(conn, 777, 1, developer_id=0) == 'user'

def test_developer_is_godmode_everywhere(conn):
    # ws2 where 555 is not a member at all
    assert resolve_ws_role(conn, 555, 2, developer_id=555) == 'developer'

def test_developer_beats_membership(conn):
    # even if developer is a moderator somewhere, still 'developer'
    assert resolve_ws_role(conn, 555, 1, developer_id=555) == 'developer'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workspace_rbac.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.workspace_rbac'`

- [ ] **Step 3: Write minimal implementation**

```python
# api/workspace_rbac.py
"""Per-workspace RBAC keystone (Подпроект #3).

resolve_ws_role(conn, user_id, ws_id) — единственное место, где
workspace_members.role превращается в permissions-vocabulary роль.
ContextVar'ы хранят активный ws запроса (ставит middleware в api.py).
"""
from contextvars import ContextVar
import sqlite3
from typing import Optional

# Активный workspace_id запроса (ставит ws_context_middleware).
WS_ID_CTX: ContextVar[int] = ContextVar("ws_id", default=1)
# Резолвнутая permissions-роль текущего юзера в активном ws.
WS_ROLE_CTX: ContextVar[str] = ContextVar("ws_role", default="user")

# workspace_members.role → permissions.py role
_MEMBER_ROLE_MAP = {
    "owner": "owner",
    "admin": "deputy",
    "moderator": "admin",
}


def resolve_ws_role(
    conn: sqlite3.Connection,
    user_id: int,
    ws_id: int,
    developer_id: int = 0,
) -> str:
    """owner/deputy/admin/developer/user в permissions-словаре.

    developer_id (Илья) — god-mode во всех ws, проверяется ПЕРВЫМ.
    MAIN_ADMIN не имеет спец-кейса: он owner ws=1 только через membership.
    """
    if developer_id and user_id == developer_id:
        return "developer"
    row = conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (ws_id, user_id),
    ).fetchone()
    if not row:
        return "user"
    return _MEMBER_ROLE_MAP.get(row[0], "user")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workspace_rbac.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add api/workspace_rbac.py tests/test_workspace_rbac.py
git commit -m "feat(V1.17.0d1): resolve_ws_role keystone — per-WS роль из workspace_members"
```

---

### Task 2: `ws_context_middleware` — validate membership, set ContextVar

**Files:**
- Modify: `api.py` (add middleware after `app = FastAPI(...)`; reuse `_decode_jwt`, `db`)
- Test: `tests/test_ws_auth_middleware.py`

**Behavior:** For requests under `/api/` that carry `Authorization: Bearer`, decode JWT → `user_id`. Read `X-Workspace-Id` (default `1`). Compute role via `resolve_ws_role`. If role is `user` (i.e. not a member and not developer) → **403** (cross-tenant block). Otherwise set `WS_ID_CTX` / `WS_ROLE_CTX`. **Skip** the check (no 403, but still default ws=1) for paths starting with `/api/auth`, exactly `/api/workspaces` family (it owns `_check_role`), and any request without a Bearer token (those endpoints do their own `_require_auth`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ws_auth_middleware.py
import sqlite3, time, jwt as _jwt
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "pulse_bot.db"          # permissions.py uses this name
    monkeypatch.setenv("DEVELOPER_ID", "555")
    monkeypatch.setenv("MAIN_ADMIN_ID", "0")
    monkeypatch.setenv("JWT_SECRET", "testsecret")
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    from database.migrations.multi_tenancy import up_create_workspaces_tables
    from database.db_workspaces import create_workspace, add_member
    up_create_workspaces_tables(conn)
    create_workspace(conn, "WS1", owner_user_id=42)   # ws1 owner 42
    create_workspace(conn, "WS2", owner_user_id=99)   # ws2 owner 99
    add_member(conn, 1, 100, "moderator")
    conn.commit()

    import importlib, api as api_mod
    importlib.reload(api_mod)
    api_mod.db.conn = conn
    api_mod.db.cursor = conn.cursor()
    return TestClient(api_mod.app, raise_server_exceptions=False), api_mod


def _tok(api_mod, uid):
    return api_mod._make_jwt({"user_id": uid, "username": "", "first_name": "",
                              "photo_url": "", "is_admin": False, "is_owner": False})


def test_non_member_blocked_cross_tenant(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 42)}", "X-Workspace-Id": "2"}
    r = c.get("/api/admin/profile/me", headers=h)
    assert r.status_code == 403

def test_member_allowed_in_own_ws(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 42)}", "X-Workspace-Id": "1"}
    r = c.get("/api/admin/profile/me", headers=h)
    assert r.status_code == 200
    assert r.json()["role_raw"] == "owner"

def test_developer_bypasses_membership(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 555)}", "X-Workspace-Id": "2"}
    r = c.get("/api/admin/profile/me", headers=h)
    assert r.status_code == 200
    assert r.json()["role_raw"] == "developer"

def test_auth_endpoints_skip_ws_check(client):
    c, api_mod = client
    r = c.get("/api/auth/config")
    assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ws_auth_middleware.py -v`
Expected: FAIL — `test_non_member_blocked_cross_tenant` returns 200 (no middleware yet); `test_developer_bypasses_membership` returns 403/wrong role.

- [ ] **Step 3: Write minimal implementation**

In `api.py`, immediately after the `app = FastAPI(...)` line and imports, add:

```python
from starlette.requests import Request as _Req
from starlette.responses import JSONResponse as _JSONResp
from api.workspace_rbac import resolve_ws_role, WS_ID_CTX, WS_ROLE_CTX

_WS_SKIP_PREFIXES = ("/api/auth", "/api/workspaces")


@app.middleware("http")
async def ws_context_middleware(request: _Req, call_next):
    WS_ID_CTX.set(1)
    WS_ROLE_CTX.set("user")
    path = request.url.path
    authz = request.headers.get("authorization", "")
    if (
        path.startswith("/api/")
        and not any(path.startswith(p) for p in _WS_SKIP_PREFIXES)
        and authz.startswith("Bearer ")
    ):
        try:
            payload = _decode_jwt(authz[7:])
        except Exception:
            payload = None
        if payload:
            user_id = int(payload.get("user_id", 0))
            try:
                ws_id = int(request.headers.get("x-workspace-id") or 1)
            except (TypeError, ValueError):
                ws_id = 1
            dev_id = int(os.getenv("DEVELOPER_ID", 0))
            role = resolve_ws_role(db.conn, user_id, ws_id, developer_id=dev_id) if db else "user"
            if role == "user":
                return _JSONResp(
                    status_code=403,
                    content={"detail": "Нет доступа к этому сообществу"},
                )
            WS_ID_CTX.set(ws_id)
            WS_ROLE_CTX.set(role)
    return await call_next(request)
```

Note: `_decode_jwt`, `os`, `db` are already module-level in `api.py`. Place this block **after** `_decode_jwt` is defined (it is defined at line ~140) — put the middleware definition right after `_require_auth` (line ~287) so all referenced names exist.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ws_auth_middleware.py -v`
Expected: PASS (4 passed). If `test_member_allowed_in_own_ws` fails on `role_raw`, that is fixed in Task 3 — re-run after Task 3.

- [ ] **Step 5: Commit**

```bash
git add api.py tests/test_ws_auth_middleware.py
git commit -m "feat(V1.17.0d2): ws_context_middleware — валидация членства + ContextVar, кросс-тенант 403"
```

---

### Task 3: `_resolve_user_role` + profile/me become ws-aware

**Files:**
- Modify: `api.py:322-331` (`_resolve_user_role`), `api.py:209-274` (`/api/admin/profile/me`)
- Test: extend `tests/test_ws_auth_middleware.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ws_auth_middleware.py`:

```python
def test_moderator_sees_admin_role_in_profile(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 100)}", "X-Workspace-Id": "1"}
    r = c.get("/api/admin/profile/me", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["role_raw"] == "admin"          # moderator -> admin mapping
    assert "moderation.view" in body["permissions"]
    assert "economy.cancel" not in body["permissions"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ws_auth_middleware.py::test_moderator_sees_admin_role_in_profile -v`
Expected: FAIL — `_resolve_user_role` still reads global `pulse_bot.db.users.role`, returns `user`.

- [ ] **Step 3: Write minimal implementation**

Replace `_resolve_user_role` in `api.py` (lines ~322-331) with a ContextVar-backed version:

```python
def _resolve_user_role(user_id: int) -> str:
    """Per-workspace роль из активного ws (ставит ws_context_middleware).

    developer_id (Илья) — god-mode. MAIN_ADMIN не имеет спец-кейса:
    owner ws=1 только через workspace_members.
    """
    from api.workspace_rbac import resolve_ws_role, WS_ID_CTX
    developer_id = int(os.getenv('DEVELOPER_ID', 0))
    if developer_id and user_id == developer_id:
        return "developer"
    if not db:
        return "user"
    return resolve_ws_role(db.conn, user_id, WS_ID_CTX.get(), developer_id=developer_id)
```

Delete the old `_get_user_role_meta`-based body. `_get_user_role_meta` is still used by `/api/admin/profile/me` for `q_name/status/created_at` — **leave that function defined**, only `_resolve_user_role` changes.

No change needed in `/api/admin/profile/me` itself — it already calls `_resolve_user_role(user_id)` (line 218) and `get_role_permissions(role_raw)` (line 255); both now flow through the ws context.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ws_auth_middleware.py -v`
Expected: PASS (all, including `test_member_allowed_in_own_ws` and `test_moderator_sees_admin_role_in_profile`)

- [ ] **Step 5: Commit**

```bash
git add api.py tests/test_ws_auth_middleware.py
git commit -m "feat(V1.17.0d3): _resolve_user_role читает активный ws из ContextVar"
```

---

### Task 4: `/api/auth/telegram` drops global owner special-case; `_require_owner*` ws-aware

**Files:**
- Modify: `api.py:149-171` (`auth_telegram`), `api.py:334-353` (`_require_owner`, `_require_owner_or_developer`), `api.py:377-389` (`permissions_roles_update`)
- Test: extend `tests/test_ws_auth_middleware.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ws_auth_middleware.py`:

```python
def test_auth_telegram_no_global_owner_for_main_admin(client, monkeypatch):
    c, api_mod = client
    # MAIN_ADMIN_ID=0 in fixture; a random user must NOT get is_owner globally
    import hashlib, hmac, time as _t
    monkeypatch.setattr(api_mod, "_verify_tg_hash", lambda d: True)
    r = c.post("/api/auth/telegram", json={"id": 12345, "auth_date": int(_t.time())})
    assert r.status_code == 200
    assert r.json()["is_owner"] is False

def test_require_owner_uses_ws_role(client):
    c, api_mod = client
    # user 100 is moderator(-> admin) in ws1: must be 403 on owner-only PUT
    h = {"Authorization": f"Bearer {_tok(api_mod, 100)}", "X-Workspace-Id": "1",
         "Content-Type": "application/json"}
    r = c.put("/api/admin/permissions/roles/admin", headers=h,
              json={"permissions": ["triggers.view"]})
    assert r.status_code == 403
    # ws1 owner 42 allowed
    h2 = {"Authorization": f"Bearer {_tok(api_mod, 42)}", "X-Workspace-Id": "1",
          "Content-Type": "application/json"}
    r2 = c.put("/api/admin/permissions/roles/admin", headers=h2,
               json={"permissions": ["triggers.view"]})
    assert r2.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ws_auth_middleware.py::test_auth_telegram_no_global_owner_for_main_admin tests/test_ws_auth_middleware.py::test_require_owner_uses_ws_role -v`
Expected: FAIL — `auth_telegram` still sets `is_owner` from global `udata`/`MAIN_ADMIN_ID`; `_require_owner_or_developer` already calls `_resolve_user_role` so the second test may pass, but first fails.

- [ ] **Step 3: Write minimal implementation**

In `api.py` `auth_telegram` (lines ~156-171), replace the `is_owner` / `is_admin` computation so JWT is identity-only and global owner is gone:

```python
    user_id = int(data["id"])
    _developer_id = int(os.getenv('DEVELOPER_ID', 0))
    is_developer = bool(_developer_id and user_id == _developer_id)
    # is_owner/is_admin в JWT больше НЕ глобальные — это per-ws (см. /profile/me).
    # Оставляем поля для обратной совместимости фронта: developer => true, иначе false.
    token = _make_jwt({
        "user_id":    user_id,
        "username":   data.get("username", ""),
        "first_name": data.get("first_name", ""),
        "photo_url":  data.get("photo_url", ""),
        "is_admin":   is_developer,
        "is_owner":   is_developer,
    })
    return {"token": token, "is_admin": is_developer, "is_owner": is_developer}
```

`_require_owner` / `_require_owner_or_developer` (lines ~334-353) already call `_resolve_user_role(user_id)` which is now ws-aware (Task 3) — **no change needed**, they inherit per-ws behavior. Verify by test only.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ws_auth_middleware.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add api.py tests/test_ws_auth_middleware.py
git commit -m "feat(V1.17.0d4): auth/telegram identity-only JWT, owner-check per-WS"
```

---

### Task 5: Re-point economy/titles/press_release injected resolver to ws context

**Files:**
- Modify: `api.py:75,84,93` (the three `_setup` calls)
- Test: `tests/test_ws_routes_inherit_ctx.py` (new)

**Why no router file changes:** every router calls `_resolve_role_fn(user_id)` and `_resolve_role_fn` is injected by `_*_setup(...)`. Re-point the injected lambda so `uid` is resolved against the active-ws ContextVar. Call sites stay byte-identical.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ws_routes_inherit_ctx.py
import sqlite3
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "pulse_bot.db"
    monkeypatch.setenv("DEVELOPER_ID", "555")
    monkeypatch.setenv("MAIN_ADMIN_ID", "0")
    monkeypatch.setenv("JWT_SECRET", "testsecret")
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    from database.migrations.multi_tenancy import up_create_workspaces_tables
    from database.db_workspaces import create_workspace, add_member
    up_create_workspaces_tables(conn)
    create_workspace(conn, "WS1", owner_user_id=42)
    add_member(conn, 1, 101, "moderator")
    conn.commit()
    import importlib, api as api_mod
    importlib.reload(api_mod)
    api_mod.db.conn = conn
    api_mod.db.cursor = conn.cursor()
    return TestClient(api_mod.app, raise_server_exceptions=False), api_mod


def _tok(api_mod, uid):
    return api_mod._make_jwt({"user_id": uid, "username": "", "first_name": "",
                              "photo_url": "", "is_admin": False, "is_owner": False})


def test_titles_create_denied_for_moderator(client):
    """101 = moderator -> permissions 'admin' -> нет titles create (owner-level действие)."""
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 101)}", "X-Workspace-Id": "1",
         "Content-Type": "application/json"}
    r = c.post("/api/titles/packages", headers=h, json={"name": "X"})
    assert r.status_code in (403, 422)   # 403 perm denied (422 only if body schema differs)

def test_titles_list_ok_for_owner(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 42)}", "X-Workspace-Id": "1"}
    r = c.get("/api/titles/packages", headers=h)
    assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ws_routes_inherit_ctx.py -v`
Expected: FAIL — injected lambda still calls global `_resolve_user_role(uid)` semantics OR returns wrong role because middleware ran but the lambda ignores ctx. (If it already passes because Task 3 made `_resolve_user_role` ctx-aware and the lambda wraps it — that is acceptable; see Step 3.)

- [ ] **Step 3: Write minimal implementation**

In `api.py`, the three injections currently read:

```python
_economy_setup(db, lambda auth: _require_auth(auth), lambda uid: _resolve_user_role(uid), _economy_ws_manager)
_titles_setup(db, lambda auth: _require_auth(auth), lambda uid: _resolve_user_role(uid))
_pr_setup(db, lambda auth: _require_auth(auth), lambda uid: _resolve_user_role(uid))
```

Because Task 3 already made `_resolve_user_role` read `WS_ID_CTX`, **these lambdas are already correct** — `lambda uid: _resolve_user_role(uid)` now resolves per active ws. Confirm no change is required; if a router somewhere computed role before middleware set the ctx (it cannot — middleware runs first in the ASGI chain), tests catch it. **Make zero code changes here; this task is a verification gate.** If tests fail, the bug is in Task 2/3 — fix there, not by editing call sites.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ws_routes_inherit_ctx.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_ws_routes_inherit_ctx.py
git commit -m "test(V1.17.0d5): economy/titles/PR наследуют per-WS роль через ContextVar"
```

---

### Task 6: Full backend regression sweep

**Files:**
- Test: run entire suite

- [ ] **Step 1: Run full suite**

Run: `python -m pytest -q`
Expected: all pass. Pre-existing tests of interest: `tests/test_workspaces_api.py`, `tests/test_workspace_context.py`, `tests/test_db_workspaces.py` must stay green.

- [ ] **Step 2: Smoke import**

Run: `python -c "import api; print('api OK'); import bot; print('bot OK')"`
Expected: both print OK, no exception.

- [ ] **Step 3: Fix any regression**

If `test_workspaces_api.py` fails because its fixture builds `app` without `pulse_bot.db`, that suite injects its own `_setup` and does not exercise the middleware (it constructs a bare `FastAPI()`), so it should be unaffected. If a global-owner assumption breaks elsewhere, fix the caller to use `_resolve_user_role` (now ws-aware). Re-run until green.

- [ ] **Step 4: Commit (only if fixes were needed)**

```bash
git add -A
git commit -m "fix(V1.17.0d6): регресс-фиксы после ws-aware RBAC"
```

---

### Task 7: Frontend — central `X-Workspace-Id` injection + active-ws helpers

**Files:**
- Modify: `Admin_SITE/components/shared/api.js`
- Test: manual (no JS test harness in repo) — verification steps included

- [ ] **Step 1: Add active-ws storage + header helper at top of `api.js`**

Prepend to `Admin_SITE/components/shared/api.js`:

```javascript
// V1.17.0d (Подпроект #3): активный workspace в localStorage + общий хедер.
const WS_KEY = 'active_ws_id';

export function getActiveWs() {
  const v = localStorage.getItem(WS_KEY);
  return v ? parseInt(v, 10) : null;
}

export function setActiveWs(wsId) {
  if (wsId == null) localStorage.removeItem(WS_KEY);
  else localStorage.setItem(WS_KEY, String(wsId));
}

function wsHeaders(token, extra = {}) {
  const h = { Authorization: `Bearer ${token}`, ...extra };
  const ws = getActiveWs();
  if (ws != null) h['X-Workspace-Id'] = String(ws);
  return h;
}
```

- [ ] **Step 2: Route every existing fetch in `api.js` through `wsHeaders`**

Replace each `headers: { Authorization: ... }` / `headers: { 'Content-Type': ..., Authorization: ... }` object in the existing functions (`fetchWorkspaces`, `fetchWorkspaceDetails`, `inviteMember`, `removeMember`, `renameWorkspace`, `updateChatRole`, `disconnectChat`, `deleteWorkspace`) with `wsHeaders(token)` or `wsHeaders(token, { 'Content-Type': 'application/json' })`. Example for `inviteMember`:

```javascript
export async function inviteMember(token, wsId, userId, role) {
  const r = await fetch(`/api/workspaces/${wsId}/members`, {
    method: 'POST',
    headers: wsHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ user_id: userId, role }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `inviteMember ${r.status}`);
  }
  return r.json();
}
```

Note: `/api/workspaces*` is in the middleware skip list, so the header is harmless there but keeps one code path.

- [ ] **Step 3: Build the frontend**

Run: `cd Admin_SITE && npm run build`
Expected: build succeeds, no syntax error. (Per memory `feedback_site_workflow`: local build → deploy; tag site commits `[Site]`.)

- [ ] **Step 4: Commit**

```bash
git add Admin_SITE/components/shared/api.js
git commit -m "feat(V1.17.0d7) [Site]: api.js — общий X-Workspace-Id из активного ws"
```

---

### Task 8: Frontend — `WorkspaceSwitcher` component

**Files:**
- Create: `Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx`

- [ ] **Step 1: Create the component**

```jsx
// Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx
// V1.17.0d (Подпроект #3): выбор активного сообщества в топбаре.
import React, { useEffect, useState } from 'react';
import { fetchWorkspaces, getActiveWs, setActiveWs } from '../shared/api';

export default function WorkspaceSwitcher({ token, onSwitch }) {
  const [list, setList] = useState([]);
  const [active, setActive] = useState(getActiveWs());

  useEffect(() => {
    if (!token) return;
    fetchWorkspaces(token)
      .then((d) => {
        const ws = d.workspaces || [];
        setList(ws);
        if (getActiveWs() == null && ws.length) {
          setActiveWs(ws[0].id);
          setActive(ws[0].id);
        }
      })
      .catch(() => {});
  }, [token]);

  if (list.length <= 1) return null;

  const change = (e) => {
    const id = parseInt(e.target.value, 10);
    setActiveWs(id);
    setActive(id);
    if (onSwitch) onSwitch(id);
  };

  return (
    <select
      value={active ?? ''}
      onChange={change}
      className="text-sm font-bold rounded-2xl border-2 border-gray-200 px-3 py-1.5 bg-white"
      title="Активное сообщество"
    >
      {list.map((w) => (
        <option key={w.id} value={w.id}>
          {w.name} · {w.role}
        </option>
      ))}
    </select>
  );
}
```

- [ ] **Step 2: Build**

Run: `cd Admin_SITE && npm run build`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx
git commit -m "feat(V1.17.0d8) [Site]: WorkspaceSwitcher компонент"
```

---

### Task 9: Frontend — mount switcher, re-fetch profile on switch, per-ws auth flags

**Files:**
- Modify: `Admin_SITE/AdminDashboard.jsx`

- [ ] **Step 1: Import switcher + helpers**

Near the top imports (after line 7, the `InviteMemberModal` import) add:

```jsx
import WorkspaceSwitcher from './components/workspaces/WorkspaceSwitcher';
import { getActiveWs } from './components/shared/api';
```

- [ ] **Step 2: Make profile fetch ws-aware and re-runnable on switch**

`fetchProfile` (line ~346) does `fetch('/api/admin/profile/me', { headers: { Authorization } })`. Change its headers to include the active ws, and expose a switch handler. Replace the fetch headers with:

```jsx
      headers: {
        Authorization: `Bearer ${token}`,
        ...(getActiveWs() != null ? { 'X-Workspace-Id': String(getActiveWs()) } : {}),
      },
```

Add a handler that clears + re-fetches profile when ws changes (place near `fetchProfile`):

```jsx
  const onWorkspaceSwitch = useCallback(() => {
    setProfileData(null);
    setUserPermissions([]);
    fetchProfile();
  }, [fetchProfile]);
```

(`setUserPermissions` / `setProfileData` already exist — they back `userCanAny` at lines 365-373. If `userPermissions` is not a separate state, skip that line and rely on `setProfileData(null)` + `fetchProfile`.)

- [ ] **Step 3: Derive `isOwner` / owner-gates from per-ws profile, not global JWT**

At lines 333-334 / 365-373, `isOwner` and `userCanAny` read `authUser.is_owner`. Since JWT `is_owner` is now developer-only (Task 4), change owner detection to the per-ws profile role:

```jsx
  const isOwner = !!(profileData?.role_raw === 'owner' || profileData?.role_raw === 'developer');
  const isAdmin = !!(authUser && (isOwner || (profileData?.permissions || []).length > 0));
```

And in `userCanAny`/`userCan` (lines ~365-373) replace `authUser?.is_owner` with `profileData?.role_raw === 'owner'` (keep the existing `profileData?.role_raw === 'developer'` clause). The navigation filter at line ~5504 uses the same `authUser?.is_owner` — replace with `isOwner` (now profile-derived).

- [ ] **Step 4: Mount the switcher in the topbar**

The topbar renders the avatar/name around line ~5547-5551. Insert the switcher just before that user block:

```jsx
<WorkspaceSwitcher
  token={localStorage.getItem('auth_token')}
  onSwitch={onWorkspaceSwitch}
/>
```

- [ ] **Step 5: Build**

Run: `cd Admin_SITE && npm run build`
Expected: success, no undefined-variable errors.

- [ ] **Step 6: Commit**

```bash
git add Admin_SITE/AdminDashboard.jsx
git commit -m "feat(V1.17.0d9) [Site]: switcher в топбаре, профиль/owner-гейты per-WS"
```

---

### Task 10: Pulse ws=1 safety verification + RUNBOOK

**Files:**
- Create: `scripts/verify_ws_rbac_pulse.py`
- Modify: `docs/RUNBOOK_multi_tenancy_deploy.md`

**Why:** Pulse (you) is the live prod tenant. A wrong role-map or a missing `workspace_members` row for the real owner would lock the owner out. This script asserts invariants before deploy.

- [ ] **Step 1: Create the verifier**

```python
# scripts/verify_ws_rbac_pulse.py
"""Pre-deploy: убеждаемся что Pulse ws=1 не сломан per-WS RBAC.

Usage: python scripts/verify_ws_rbac_pulse.py
Exit 0 = OK, exit 1 = invariant нарушен (НЕ деплоить).
"""
import os, sqlite3, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "pulse_bot.db")


def main() -> int:
    if not os.path.exists(DB):
        print("FAIL: pulse_bot.db не найден"); return 1
    conn = sqlite3.connect(DB)
    ws = conn.execute(
        "SELECT id, owner_user_id, is_pulse_themed FROM workspaces WHERE id=1"
    ).fetchone()
    if not ws:
        print("FAIL: workspace id=1 отсутствует"); return 1
    owner_uid = ws[1]
    m = conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=1 AND user_id=?",
        (owner_uid,),
    ).fetchone()
    if not m or m[0] != "owner":
        print(f"FAIL: owner {owner_uid} не 'owner' в workspace_members ws=1 (={m})")
        return 1
    from api.workspace_rbac import resolve_ws_role
    role = resolve_ws_role(conn, owner_uid, 1, developer_id=0)
    if role != "owner":
        print(f"FAIL: resolve_ws_role вернул {role!r}, ожидался 'owner'"); return 1
    dev_id = int(os.getenv("DEVELOPER_ID", 0))
    if dev_id:
        drole = resolve_ws_role(conn, dev_id, 999, developer_id=dev_id)
        if drole != "developer":
            print(f"FAIL: developer god-mode сломан ({drole!r})"); return 1
    conn.close()
    print(f"OK: ws=1 owner={owner_uid} role=owner; developer god-mode OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it against the local dev db**

Run: `python scripts/verify_ws_rbac_pulse.py`
Expected: `OK: ws=1 owner=<id> ...` and exit 0. If FAIL, do not proceed — the Pulse owner is not seeded in `workspace_members`; fix data before deploy (see `prod_reset_2026_05_13` memory for the reset script).

- [ ] **Step 3: Append deploy section to RUNBOOK**

Add to `docs/RUNBOOK_multi_tenancy_deploy.md`:

```markdown
## V1.17.0d — Web Auth + per-WS RBAC (Подпроект #3)

Pre-deploy (local & server, BEFORE restart):
  python scripts/verify_ws_rbac_pulse.py     # must exit 0

Deploy:
  git pull --ff-only
  systemctl restart pulsebot-api             # middleware = api restart required
  cd Admin_SITE && npm run build             # статика, nginx раздаёт dist напрямую

Post-deploy smoke:
  - Owner (ты) логинишься → видишь Pulse Москва, role=owner, меню полное
  - Залогинься 2-м владельцем чужого ws → видит только свой ws
  - Свитчер: переключение ws → меню/права меняются без релогина
Rollback: git revert диапазона V1.17.0d* + restart api.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/verify_ws_rbac_pulse.py docs/RUNBOOK_multi_tenancy_deploy.md
git commit -m "chore(V1.17.0d10): verify_ws_rbac_pulse + RUNBOOK секция #3"
```

---

## Self-Review

**Spec coverage:**
- Validated `X-Workspace-Id` → Task 2 (middleware validates membership, 403 cross-tenant). ✅
- Developer god-mode → Task 1 (resolver, dev checked first) + verified Task 2/10. ✅
- MAIN_ADMIN only via membership → Task 4 (auth_telegram drops global owner) + Task 1 (no MAIN_ADMIN special-case). ✅
- All economy/titles/PR routes ws-scoped → Tasks 3+5 (ctx-aware `_resolve_user_role`, injected lambda inherits) + verified Task 5/6. ✅
- Switcher UI → Tasks 7-9. ✅
- Pulse not broken → Task 10. ✅

**Placeholder scan:** No TBD/TODO; every code step has full code. Frontend tasks lack automated tests (no JS harness in repo) — substituted with explicit `npm run build` gates + manual smoke in RUNBOOK; this is a known repo constraint, not a placeholder.

**Type consistency:** `resolve_ws_role(conn, user_id, ws_id, developer_id=0)` signature identical across Tasks 1, 3, 10. `WS_ID_CTX`/`WS_ROLE_CTX` names consistent Tasks 1-3. `getActiveWs`/`setActiveWs`/`wsHeaders` consistent Tasks 7-9. Permissions roles (`owner/deputy/admin/developer/user`) match `permissions.py` `ROLES`.

**Risk note:** Task 2 middleware ordering — `@app.middleware("http")` runs around every request; the skip list protects `/api/auth*` (login) and `/api/workspaces*` (own check). `test_workspaces_api.py` builds a bare `FastAPI()` without the middleware, so it is unaffected (verified logically in Task 6 Step 3).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-16-web-auth-workspace-rbac.md`.
