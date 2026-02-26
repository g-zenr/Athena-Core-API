# Backend Architecture Guide (AI Reference) — Python / FastAPI

> This document defines the backend architecture, conventions, and patterns used across all projects.
> Any AI tool scaffolding code, generating services, or performing tasks **must** follow these rules.
> This architecture is **project-agnostic** — adapt entity names, modules, and domain logic to the specific project while keeping all patterns and conventions intact.

---

## Tech Stack

| Layer | Technology | Version / Notes |
|---|---|---|
| **Runtime** | Python | 3.11+ |
| **Framework** | FastAPI | Latest stable |
| **Database** | SQLAlchemy | 2.0, sync (not async) for simplicity |
| **Migrations** | Alembic | Schema versioning |
| **Validation** | Pydantic | v2 |
| **Auth — Tokens** | python-jose[cryptography] | JWT creation and decoding |
| **Auth — Passwords** | passlib[bcrypt] | Password hashing |
| **File Uploads** | python-multipart | Required for `UploadFile` support in FastAPI |
| **HTTP Client** | httpx | For external API calls and testing |
| **Testing** | pytest + httpx | `TestClient` from `fastapi.testclient` |
| **CORS** | fastapi.middleware.cors | `CORSMiddleware` built into FastAPI |
| **Config** | pydantic-settings | `.env` file loading via `BaseSettings` |

### `requirements.txt`

```
fastapi
uvicorn[standard]
sqlalchemy>=2.0
alembic
pydantic>=2.0
pydantic-settings
python-jose[cryptography]
passlib[bcrypt]
python-multipart
httpx
pytest
```

---

## Folder Structure

```
{project}/api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory, middleware, router registration
│   ├── config.py            # Settings via pydantic-settings BaseSettings
│   ├── database.py          # Engine, SessionLocal, Base, get_db dependency
│   ├── models/
│   │   ├── __init__.py      # Re-exports all models for Alembic autodiscovery
│   │   └── {entity}.py      # One file per model
│   ├── schemas/             # Pydantic v2 request/response models (NOT SQLAlchemy models)
│   │   ├── __init__.py
│   │   └── {entity}.py      # One file per entity
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── {entity}.py      # One router file per entity (plural noun preferred)
│   ├── dependencies/
│   │   ├── __init__.py
│   │   └── auth.py          # get_current_user FastAPI dependency
│   └── utils/
│       ├── __init__.py
│       ├── jwt.py           # create_access_token, decode_token helpers
│       └── {project-specific}.py
├── alembic/
│   ├── env.py               # Points to app.database.Base.metadata
│   └── versions/            # Generated migration scripts
├── tests/
│   ├── conftest.py          # Fixtures: test app, client, DB, user
│   └── test_{entity}.py
├── uploads/                 # Runtime storage for uploaded files (git-ignored)
├── requirements.txt
├── alembic.ini
└── .env.example
```

### Naming Conventions

| Artifact | Convention | Example |
|---|---|---|
| Model file | `{entity}.py` (singular) | `user.py` |
| Schema file | `{entity}.py` (singular) | `device.py` |
| Router file | `{entities}.py` (plural preferred) | `devices.py` |
| Model class | `PascalCase` singular | `User`, `Device` |
| Table name | `lowercase_plural` | `users`, `devices` |
| Schema class | `{Entity}{Suffix}` | `UserCreate`, `DeviceResponse` |

### Rules

- **One model = one file** under `app/models/`.
- **One schema set = one file** under `app/schemas/` (Base, Create, Update, Response).
- **One router = one file** under `app/routers/`.
- Import all models in `app/models/__init__.py` so Alembic can discover them.
- Never put SQLAlchemy models inside `app/schemas/` — they are separate layers.

---

## SQLAlchemy Model Conventions

### Base Setup (`app/database.py`)

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite only
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

### Model Rules

- All models **inherit from `Base`** imported from `app.database`
- Every model **must** have:
  - `id`: Integer, primary key, auto-increment, indexed
  - `created_at`: DateTime, defaults to `datetime.utcnow`
- **Table names**: lowercase plural (`users`, `devices`)
- **Foreign keys**: string table references `ForeignKey("users.id")`
- **No soft delete by default** — use hard delete (`db.delete(obj)`) unless the project explicitly requires soft delete
- **Import all models** in `app/models/__init__.py` so Alembic discovers them

### Example Model (`app/models/{entity}.py`)

```python
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class {Entity}(Base):
    __tablename__ = "{entities}"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, default="active")  # active | inactive
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="{entities}")
```

### `app/models/__init__.py`

```python
# Import all models here so Alembic can discover them via Base.metadata
from app.models.user import User
from app.models.{entity} import {Entity}

__all__ = ["User", "{Entity}"]
```

---

## Pydantic v2 Schema Conventions

Schemas are **data transfer objects (DTOs)** — they are NOT SQLAlchemy models. They live in `app/schemas/`.

### Four-Schema Rule

Every entity uses this set of schemas:

| Schema | Purpose |
|---|---|
| `{Entity}Base` | Shared fields (used as base class) |
| `{Entity}Create` | Request body for POST (extends Base, excludes id/timestamps) |
| `{Entity}Update` | Request body for PATCH (all fields `Optional`) |
| `{Entity}Response` | Response shape returned to client (includes id, created_at) |

### Rules

- All response schemas **must** have `model_config = ConfigDict(from_attributes=True)` — enables serialization from SQLAlchemy ORM objects
- Use `Optional[T]` (i.e., `T | None = None`) for nullable or optional fields
- Use `Literal["val1", "val2"]` for constrained string enums
- Never include `hashed_password` in any response schema
- Import `ConfigDict` from `pydantic`

### Example Schemas (`app/schemas/{entity}.py`)

```python
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict


class {Entity}Base(BaseModel):
    name: str
    description: Optional[str] = None
    status: Literal["active", "inactive"] = "active"


class {Entity}Create({Entity}Base):
    pass  # user_id inferred from auth token


class {Entity}Update(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Literal["active", "inactive"]] = None


class {Entity}Response({Entity}Base):
    id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

---

## Router / Endpoint Conventions

### Router File Structure

```python
# app/routers/{entities}.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.{entity} import {Entity}
from app.schemas.{entity} import {Entity}Create, {Entity}Response, {Entity}Update

router = APIRouter(prefix="/{entities}", tags=["{Entities}"])


@router.get("/", response_model=list[{Entity}Response])
def list_{entities}(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = db.query({Entity}).filter({Entity}.user_id == current_user.id).all()
    return {"data": items}


@router.get("/{item_id}", response_model={Entity}Response)
def get_{entity}(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.query({Entity}).filter(
        {Entity}.id == item_id,
        {Entity}.user_id == current_user.id,
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="{Entity} not found")
    return {"data": item}


@router.post("/", response_model={Entity}Response, status_code=status.HTTP_201_CREATED)
def create_{entity}(
    payload: {Entity}Create,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = {Entity}(**payload.model_dump(), user_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"data": item}


@router.patch("/{item_id}", response_model={Entity}Response)
def update_{entity}(
    item_id: int,
    payload: {Entity}Update,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.query({Entity}).filter(
        {Entity}.id == item_id,
        {Entity}.user_id == current_user.id,
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="{Entity} not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return {"data": item}


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_{entity}(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.query({Entity}).filter(
        {Entity}.id == item_id,
        {Entity}.user_id == current_user.id,
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="{Entity} not found")
    db.delete(item)
    db.commit()
```

### HTTP Status Code Reference

| Situation | Status Code |
|---|---|
| Successful GET (list or single) | 200 |
| Successful POST (created) | 201 |
| Successful DELETE | 204 (no content) |
| Successful PATCH | 200 |
| Validation / bad input | 422 (automatic via Pydantic) |
| Unauthenticated | 401 |
| Forbidden | 403 |
| Not found | 404 |
| Server error | 500 |

### Standard Response Wrapper

All successful responses return a `{"data": ...}` envelope:

```python
# Single resource
return {"data": item}

# Collection
return {"data": items}
```

The frontend **always** unwraps `.data` from the response. This is a firm contract.

### Router Registration (`app/main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, {entities}

app = FastAPI(title="{Project} API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router({entities}.router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

All routes are prefixed with `/api` at registration. The router's own prefix adds the entity path:
- Auth router: `prefix="/auth"` → `/api/auth/...`
- Entity router: `prefix="/{entities}"` → `/api/{entities}/...`

---

## Auth Pattern (JWT)

### Token Format

```
Authorization: Bearer <jwt_token>
```

### JWT Payload

```json
{
  "sub": "42",
  "email": "user@example.com",
  "exp": 1720000000
}
```

- `sub`: string-cast user ID (`str(user.id)`)
- `email`: user's email address
- `exp`: Unix timestamp of expiry (24 hours from issue by default)

### `app/utils/jwt.py`

```python
from datetime import datetime, timedelta
from jose import JWTError, jwt
from app.config import settings


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decodes and validates a JWT token. Raises JWTError if invalid or expired."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
```

### `app/dependencies/auth.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.jwt import decode_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user
```

### Auth Router (`app/routers/auth.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.utils.jwt import create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {"data": {"access_token": token, "token_type": "bearer", "user": UserResponse.model_validate(user)}}


@router.post("/login")
def login(payload: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {"data": {"access_token": token, "token_type": "bearer", "user": UserResponse.model_validate(user)}}
```

---

## Database Session Management

### Commit Rules

- The `get_db` dependency auto-commits on clean exit — **do not** call `db.commit()` yourself unless you need an intermediate commit
- For `db.refresh(obj)` to work after `db.add()`, call `db.commit()` first, then `db.refresh(obj)`:

```python
# Correct create pattern
obj = MyModel(**data)
db.add(obj)
db.commit()        # Flush to DB, generate ID
db.refresh(obj)    # Load DB-generated fields (id, created_at)
return {"data": obj}
```

---

## Configuration (pydantic-settings)

### `app/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./app.db"

    # JWT
    SECRET_KEY: str  # No default — must be in .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # File Uploads
    UPLOAD_DIR: str = "uploads"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
```

### `.env.example`

```env
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=change-me-to-a-long-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_HOURS=24
UPLOAD_DIR=uploads
```

The `settings` object is a singleton — import it where needed. Never instantiate `Settings()` a second time.

---

## Error Response Format

FastAPI's default `HTTPException` produces:

```json
{ "detail": "Error message here" }
```

This is the **only** error format. Do not wrap errors in `{"data": ...}`.

### Examples

```json
// 400 Bad Request
{ "detail": "Email already registered" }

// 401 Unauthorized
{ "detail": "Could not validate credentials" }

// 404 Not Found
{ "detail": "{Entity} not found" }

// 422 Unprocessable Entity (automatic Pydantic validation failure)
{
  "detail": [
    { "loc": ["body", "name"], "msg": "field required", "type": "value_error.missing" }
  ]
}
```

Always use `HTTPException` — never `raise Exception(...)` in a router:

```python
from fastapi import HTTPException, status

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="{Entity} not found",
)
```

---

## File Upload Pattern

### `app/utils/file_handler.py`

```python
import uuid
import os
from fastapi import UploadFile, HTTPException, status
from app.config import settings

ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain", "image/jpeg", "image/png"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def save_upload(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"File type '{file.content_type}' is not allowed.")
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 10MB limit.")
    ext = os.path.splitext(file.filename or "")[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    relative_path = os.path.join(settings.UPLOAD_DIR, unique_name)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(relative_path, "wb") as f:
        f.write(content)
    return relative_path
```

---

## Testing Conventions

### Test Setup (`tests/conftest.py`)

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(client):
    response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
    })
    assert response.status_code == 201
    return response.json()["data"]


@pytest.fixture(scope="function")
def auth_headers(test_user):
    return {"Authorization": f"Bearer {test_user['access_token']}"}
```

### Testing Rules

| Rule | Detail |
|---|---|
| Test database | Always use isolated SQLite — never the real DB |
| DB override | Always override `get_db` via `app.dependency_overrides` |
| Isolation | Each test function gets a fresh DB (drop + recreate via `autouse` fixture) |
| File naming | `test_{router_name}.py` |
| Assertion style | Assert both status code and response body shape |
| Auth testing | Use `auth_headers` fixture; also test unauthenticated access |
| Run tests | `pytest tests/ -v` from the `api/` directory |

---

## Alembic Migrations

### Generate a Migration

```bash
alembic revision --autogenerate -m "create {entities} table"
```

### Apply Migrations

```bash
alembic upgrade head
```

### `alembic/env.py` — Key Section

```python
from app.database import Base
from app import models  # noqa: F401 — import all models for autodiscovery

target_metadata = Base.metadata
```

---

## Scaffolding Checklist

When creating a **new entity/router**, follow this order:

1. **SQLAlchemy Model** — Create `app/models/{entity}.py` with model definition.
2. **Register Model** — Add import to `app/models/__init__.py` for Alembic.
3. **Pydantic Schemas** — Create `app/schemas/{entity}.py` with Base/Create/Update/Response.
4. **Router** — Create `app/routers/{entities}.py` with CRUD endpoints.
5. **Register Router** — Add `app.include_router({entities}.router, prefix="/api")` in `main.py`.
6. **Migration** — Run `alembic revision --autogenerate` + `alembic upgrade head`.
7. **Tests** — Write `tests/test_{entities}.py`.

---

## Do NOT

- Store plain passwords. Always hash with `passlib[bcrypt]`.
- Hardcode `SECRET_KEY`. Always load from environment via `settings.SECRET_KEY`.
- Return SQLAlchemy model objects directly. Always serialize via a Pydantic `Response` schema.
- Skip `Depends(get_current_user)` on protected routes.
- Use `async def` with sync SQLAlchemy — use sync `def` for all routers.
- Return errors in `{"data": ...}` wrapper. Errors use `{"detail": "..."}` via `HTTPException`.
- Skip migration for schema changes. All model changes need an Alembic migration.
- Commit without `db.refresh(obj)` when you need the DB-generated values.
- Put business logic directly in routers — move complex logic to utils or service functions.
