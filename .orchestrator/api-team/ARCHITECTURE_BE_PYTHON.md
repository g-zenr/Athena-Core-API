# OpenClaw Backend Architecture — Python / FastAPI

> **Status**: Authoritative Reference | **Version**: 1.0 | **Last Updated**: 2026-02-25
>
> This document is the single source of truth for all backend agents on the OpenClaw project. Every agent that writes backend code **MUST** read and comply with every section here before writing a single line.

---

## Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Project Folder Structure](#2-project-folder-structure)
3. [SQLAlchemy Model Conventions](#3-sqlalchemy-model-conventions)
4. [Pydantic v2 Schema Conventions](#4-pydantic-v2-schema-conventions)
5. [Router / Endpoint Conventions](#5-router--endpoint-conventions)
6. [Auth Pattern (JWT)](#6-auth-pattern-jwt)
7. [Database Session Management](#7-database-session-management)
8. [Redis Queue Pattern](#8-redis-queue-pattern)
9. [File Upload Pattern](#9-file-upload-pattern)
10. [Configuration (pydantic-settings)](#10-configuration-pydantic-settings)
11. [Error Response Format](#11-error-response-format)
12. [CORS Configuration](#12-cors-configuration)
13. [Testing Conventions](#13-testing-conventions)
14. [Key Rules — Do NOT Violate](#14-key-rules--do-not-violate)

---

## 1. Tech Stack

| Layer | Technology | Version / Notes |
|---|---|---|
| **Runtime** | Python | 3.11+ |
| **Framework** | FastAPI | Latest stable |
| **Database** | SQLite via SQLAlchemy | 2.0, sync (not async) for MVP simplicity |
| **Validation** | Pydantic | v2 |
| **Auth — Tokens** | python-jose[cryptography] | JWT creation and decoding |
| **Auth — Passwords** | passlib[bcrypt] | Password hashing |
| **File Uploads** | python-multipart | Required for `UploadFile` support in FastAPI |
| **Queue Client** | redis-py | Redis push/pop for job queue |
| **Testing** | pytest + httpx | `TestClient` from `fastapi.testclient` |
| **Migrations** | Alembic | Schema versioning |
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
redis
httpx
pytest
pytest-asyncio
```

---

## 2. Project Folder Structure

```
openclaw/api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory, middleware, router registration
│   ├── config.py            # Settings via pydantic-settings BaseSettings
│   ├── database.py          # Engine, SessionLocal, Base, get_db dependency
│   ├── models/
│   │   ├── __init__.py      # Re-exports all models for Alembic autodiscovery
│   │   ├── user.py
│   │   ├── device.py
│   │   └── job.py
│   ├── schemas/             # Pydantic v2 request/response models (NOT SQLAlchemy models)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── device.py
│   │   └── job.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── devices.py
│   │   └── jobs.py
│   ├── dependencies/
│   │   ├── __init__.py
│   │   └── auth.py          # get_current_user FastAPI dependency
│   └── utils/
│       ├── __init__.py
│       ├── jwt.py           # create_access_token, decode_token helpers
│       ├── redis_client.py  # Redis connection + enqueue helper
│       └── file_handler.py  # File save/read helpers
├── alembic/
│   ├── env.py               # Points to app.database.Base.metadata
│   └── versions/            # Generated migration scripts
├── tests/
│   ├── conftest.py          # Fixtures: test app, client, DB, user
│   ├── test_auth.py
│   ├── test_devices.py
│   └── test_jobs.py
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
| Router file | `{entity}.py` (plural noun preferred, singular is fine) | `devices.py` |
| Model class | `PascalCase` singular | `User`, `Device`, `Job` |
| Table name | `lowercase_plural` | `users`, `devices`, `jobs` |
| Schema class | `{Entity}{Suffix}` | `UserCreate`, `DeviceResponse` |

---

## 3. SQLAlchemy Model Conventions

### Base Setup (`app/database.py`)

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
```

### Model Rules

- All models **inherit from `Base`** imported from `app.database`
- Every model **must** have:
  - `id`: Integer, primary key, auto-increment, indexed
  - `created_at`: DateTime, defaults to `datetime.utcnow`
- **Table names**: lowercase plural (e.g., `users`, `devices`, `jobs`)
- **Foreign keys**: use string table references `ForeignKey("users.id")`
- **No soft delete** in MVP — hard delete only (`db.delete(obj)`)
- **Import all models** in `app/models/__init__.py` so Alembic discovers them

### Example: User Model (`app/models/user.py`)

```python
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Example: Device Model (`app/models/device.py`)

```python
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    model = Column(String, nullable=True)
    status = Column(String, default="active")  # active | inactive
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="devices")
```

### Example: Job Model (`app/models/job.py`)

```python
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    prompt = Column(Text, nullable=False)
    job_type = Column(String, nullable=False)           # "text" | "file"
    status = Column(String, default="queued")           # queued | processing | done | failed
    file_path = Column(String, nullable=True)
    result = Column(Text, nullable=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User")
    device = relationship("Device")
```

### `app/models/__init__.py`

```python
# Import all models here so Alembic can discover them via Base.metadata
from app.models.user import User
from app.models.device import Device
from app.models.job import Job

__all__ = ["User", "Device", "Job"]
```

---

## 4. Pydantic v2 Schema Conventions

Schemas are **data transfer objects (DTOs)** — they are NOT SQLAlchemy models. They live in `app/schemas/`.

### Pattern: Four-Schema Rule

Every entity uses this set of schemas:

| Schema | Purpose |
|---|---|
| `{Entity}Base` | Shared fields (used as base class) |
| `{Entity}Create` | Request body for POST (extends Base, excludes id/timestamps) |
| `{Entity}Update` | Request body for PATCH (all fields Optional) |
| `{Entity}Response` | Response shape returned to client (includes id, created_at) |

### Rules

- All response schemas **must** have `model_config = ConfigDict(from_attributes=True)` — this enables serialization from SQLAlchemy ORM objects
- Use `Optional[T]` (i.e., `T | None = None`) for nullable or optional fields
- Use `Literal["val1", "val2"]` for constrained string enums (avoid Python `enum.Enum` in schemas unless sharing with models)
- Never include `hashed_password` in any response schema
- Import `ConfigDict` from `pydantic`

### Example: Device Schemas (`app/schemas/device.py`)

```python
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict


class DeviceBase(BaseModel):
    name: str
    model: Optional[str] = None
    status: Literal["active", "inactive"] = "active"


class DeviceCreate(DeviceBase):
    pass  # Inherits all fields from DeviceBase; user_id inferred from auth token


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    status: Optional[Literal["active", "inactive"]] = None


class DeviceResponse(DeviceBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### Example: User Schemas (`app/schemas/user.py`)

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str  # Plain text — will be hashed in the router/service


class UserUpdate(BaseModel):
    full_name: Optional[str] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### Example: Job Schemas (`app/schemas/job.py`)

```python
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict


class JobBase(BaseModel):
    prompt: str
    job_type: Literal["text", "file"]
    device_id: Optional[int] = None


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    status: Optional[Literal["queued", "processing", "done", "failed"]] = None
    result: Optional[str] = None


class JobResponse(JobBase):
    id: int
    status: Literal["queued", "processing", "done", "failed"]
    file_path: Optional[str] = None
    result: Optional[str] = None
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

---

## 5. Router / Endpoint Conventions

### Router File Structure

Each router file follows this template:

```python
# app/routers/devices.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.get("/", response_model=list[DeviceResponse])
def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    devices = db.query(Device).filter(Device.user_id == current_user.id).all()
    return {"data": devices}


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.user_id == current_user.id,
    ).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return {"data": device}


@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = Device(**payload.model_dump(), user_id=current_user.id)
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"data": device}


@router.patch("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.user_id == current_user.id,
    ).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(device, key, value)

    db.commit()
    db.refresh(device)
    return {"data": device}


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.user_id == current_user.id,
    ).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    db.delete(device)
    db.commit()
```

### HTTP Status Code Reference

| Situation | Status Code |
|---|---|
| Successful GET (list or single) | 200 |
| Successful POST (created) | 201 |
| Successful DELETE | 204 (no content) |
| Successful PATCH / PUT | 200 |
| Validation / bad input | 400 |
| Unauthenticated | 401 |
| Forbidden (authenticated but not allowed) | 403 |
| Not found | 404 |
| Server error | 500 |

### Standard Response Wrapper

All successful responses return a `{"data": ...}` envelope:

```python
# Single resource
return {"data": device}

# Collection
return {"data": devices}
```

The frontend **always** unwraps `.data` from the response. This is a firm contract.

### Router Registration (`app/main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, devices, jobs

app = FastAPI(title="OpenClaw API", version="1.0.0")

# CORS — see Section 12
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api")
app.include_router(devices.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

All routes are prefixed with `/api` at registration. The router's own prefix adds the entity path:
- Auth router: `prefix="/auth"` → final path `/api/auth/...`
- Devices router: `prefix="/devices"` → final path `/api/devices/...`
- Jobs router: `prefix="/jobs"` → final path `/api/jobs/...`

---

## 6. Auth Pattern (JWT)

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
    """
    Decodes and validates a JWT token.
    Raises JWTError if invalid or expired.
    """
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
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")

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


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user),
        }
    }


@router.post("/login", response_model=dict)
def login(payload: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user),
        }
    }
```

---

## 7. Database Session Management

### `app/database.py` — Full File

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite only
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.
    Commits on success, rolls back on exception, always closes.
    """
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

### Usage in Routers

```python
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database import get_db

@router.get("/example")
def example_endpoint(db: Session = Depends(get_db)):
    results = db.query(SomeModel).all()
    return {"data": results}
```

### Commit Rules

- The `get_db` dependency auto-commits on clean exit — **do not** call `db.commit()` yourself unless you need an intermediate commit (e.g., to get a generated ID before the request ends, then call `db.refresh(obj)` after adding)
- For `db.refresh(obj)` to work after `db.add()`, you must call `db.commit()` first, then `db.refresh(obj)` — this is the standard create pattern

```python
# Correct create pattern
obj = MyModel(**data)
db.add(obj)
db.commit()        # Flush to DB, generate ID
db.refresh(obj)    # Load DB-generated fields (id, created_at)
return {"data": obj}
```

---

## 8. Redis Queue Pattern

### `app/utils/redis_client.py`

```python
import json
import redis
from app.config import settings

_redis_client: redis.Redis | None = None

QUEUE_NAME = "openclaw_jobs"


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def enqueue_job(job_dict: dict) -> None:
    """
    Pushes a job payload onto the left side of the Redis list.
    Worker dequeues from the right using BRPOP/BLPOP.
    """
    client = get_redis()
    client.lpush(QUEUE_NAME, json.dumps(job_dict))
```

### Job Message Format

Every message pushed to the queue must conform to this shape:

```json
{
  "job_id": 42,
  "prompt": "Analyze this document for key clauses",
  "file_path": "uploads/abc123_contract.pdf",
  "job_type": "file"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `job_id` | `int` | Yes | ID of the Job row in the database |
| `prompt` | `str` | Yes | The user's instruction |
| `file_path` | `str \| None` | Conditional | Path to uploaded file; `None` for text-only jobs |
| `job_type` | `"text" \| "file"` | Yes | Determines how the worker processes the job |

### Enqueue Pattern in Routers

```python
from app.utils.redis_client import enqueue_job

# After creating and committing the Job row:
enqueue_job({
    "job_id": job.id,
    "prompt": job.prompt,
    "file_path": job.file_path,
    "job_type": job.job_type,
})
```

### Worker Dequeue Pattern (for reference — not a FastAPI router)

```python
import json
import redis

r = redis.from_url("redis://localhost:6379", decode_responses=True)

while True:
    # BLPOP blocks until a message arrives (timeout=0 = forever)
    _, raw = r.brpop("openclaw_jobs", timeout=0)
    message = json.loads(raw)
    process_job(message)
```

---

## 9. File Upload Pattern

### Storage Directory

Files are saved to `uploads/` at the project root (i.e., `openclaw/api/uploads/`). This directory **must** be created before running the server and is **git-ignored**.

### `app/utils/file_handler.py`

```python
import uuid
import os
from fastapi import UploadFile, HTTPException, status
from app.config import settings

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "image/jpeg",
    "image/png",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def save_upload(file: UploadFile) -> str:
    """
    Validates and saves an uploaded file to the uploads directory.
    Returns the relative file path (relative to project root).
    Raises HTTPException on validation failure.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file.content_type}' is not allowed. Allowed: PDF, TXT, JPG, PNG.",
        )

    # Read content to check size
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File exceeds maximum allowed size of 10MB.",
        )

    # Generate unique filename
    ext = os.path.splitext(file.filename or "")[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    relative_path = os.path.join(settings.UPLOAD_DIR, unique_name)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    with open(relative_path, "wb") as f:
        f.write(content)

    return relative_path
```

### Usage in a Router

```python
from fastapi import APIRouter, Depends, File, UploadFile
from app.utils.file_handler import save_upload

@router.post("/jobs/file", status_code=201)
def create_file_job(
    prompt: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_path = save_upload(file)

    job = Job(
        prompt=prompt,
        job_type="file",
        file_path=file_path,
        user_id=current_user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    enqueue_job({"job_id": job.id, "prompt": prompt, "file_path": file_path, "job_type": "file"})

    return {"data": job}
```

### File Storage Rules

| Rule | Detail |
|---|---|
| Filename | `{uuid_hex}{original_extension}` — never use the original filename directly |
| Location | Always inside `settings.UPLOAD_DIR` — never anywhere else |
| DB Storage | Store the **relative path** string in the `file_path` column |
| Max size | 10 MB — enforced by `file_handler.py` |
| Allowed types | PDF, TXT, JPG, PNG — enforced by `content_type` check |
| Cleanup | Not handled in MVP — manual cleanup or future background task |

---

## 10. Configuration (pydantic-settings)

### `app/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./openclaw.db"

    # JWT
    SECRET_KEY: str  # No default — must be in .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # File Uploads
    UPLOAD_DIR: str = "uploads"

    # Internal worker authentication
    WORKER_SECRET: str  # No default — must be in .env

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
```

### `.env.example`

```env
DATABASE_URL=sqlite:///./openclaw.db
SECRET_KEY=change-me-to-a-long-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_HOURS=24
REDIS_URL=redis://localhost:6379
UPLOAD_DIR=uploads
WORKER_SECRET=change-me-worker-secret
```

### Usage

```python
from app.config import settings

print(settings.DATABASE_URL)
print(settings.SECRET_KEY)
```

The `settings` object is a singleton — import it where needed. Never instantiate `Settings()` a second time; always use the module-level `settings` import from `app.config`.

---

## 11. Error Response Format

FastAPI's default `HTTPException` produces this JSON body:

```json
{ "detail": "Error message here" }
```

This is the **only** error format used in OpenClaw. Do not wrap errors in a `{"data": ...}` envelope.

### Examples

```json
// 400 Bad Request
{ "detail": "Email already registered" }

// 401 Unauthorized
{ "detail": "Could not validate credentials" }

// 404 Not Found
{ "detail": "Device not found" }

// 422 Unprocessable Entity (automatic Pydantic validation failure)
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

### Raising Errors

Always use `HTTPException` — never `raise Exception(...)` directly in a router:

```python
from fastapi import HTTPException, status

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Job not found",
)
```

Use `status` constants (`status.HTTP_200_OK`, `status.HTTP_404_NOT_FOUND`, etc.) for readability.

---

## 12. CORS Configuration

### Development Config (`app/main.py`)

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Wildcard — restrict in production
    allow_credentials=True,
    allow_methods=["*"],          # GET, POST, PATCH, DELETE, OPTIONS
    allow_headers=["*"],          # Authorization, Content-Type, etc.
)
```

### Production Notes (not implemented in MVP)

- Replace `allow_origins=["*"]` with a specific list of frontend origins
- Example: `allow_origins=["https://openclaw.app", "https://www.openclaw.app"]`
- Credentials (`allow_credentials=True`) requires non-wildcard origins in production

---

## 13. Testing Conventions

### Test Setup (`tests/conftest.py`)

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from passlib.context import CryptContext

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///./test.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    """Creates a user and returns their auth token and user data."""
    response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
    })
    assert response.status_code == 201
    return response.json()["data"]


@pytest.fixture(scope="function")
def auth_headers(test_user):
    """Returns Authorization headers for the test user."""
    return {"Authorization": f"Bearer {test_user['access_token']}"}
```

### Example Test File (`tests/test_devices.py`)

```python
def test_create_device(client, auth_headers):
    response = client.post(
        "/api/devices/",
        json={"name": "Robot Arm 1", "model": "RA-200"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Robot Arm 1"
    assert "id" in data


def test_list_devices(client, auth_headers):
    # Create two devices
    for i in range(2):
        client.post("/api/devices/", json={"name": f"Device {i}"}, headers=auth_headers)

    response = client.get("/api/devices/", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


def test_get_device_not_found(client, auth_headers):
    response = client.get("/api/devices/9999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Device not found"


def test_unauthorized_access(client):
    response = client.get("/api/devices/")
    assert response.status_code == 403  # No token provided
```

### Testing Rules

| Rule | Detail |
|---|---|
| Test database | Always use in-memory/isolated SQLite, never the real DB |
| DB override | Always override `get_db` via `app.dependency_overrides` |
| Isolation | Each test function gets a fresh DB (drop + recreate via `autouse` fixture) |
| File naming | `test_{router_name}.py` (e.g., `test_auth.py`, `test_devices.py`) |
| Assertion style | Assert both status code and response body shape |
| Auth testing | Use `auth_headers` fixture for protected routes; test unauthenticated access too |
| Run tests | `pytest tests/ -v` from the `openclaw/api/` directory |

---

## 14. Key Rules — Do NOT Violate

These are hard constraints. No exceptions in MVP.

| Rule | Why |
|---|---|
| **Never store plain passwords** | Always hash with `passlib[bcrypt]` before writing to DB |
| **Never hardcode `SECRET_KEY`** | Always load from environment via `settings.SECRET_KEY` |
| **Never return SQLAlchemy model objects directly** | Always convert to a Pydantic `Response` schema (or use `response_model=`) |
| **Never skip `Depends(get_current_user)` on protected routes** | Every non-public endpoint must authenticate |
| **Never put business logic in routers** | Routers handle HTTP in/out; logic goes in service functions or utils |
| **Never store files outside `uploads/`** | `file_handler.py` enforces this — use it, do not bypass it |
| **Never use async SQLAlchemy** | Use sync SQLAlchemy + `SessionLocal` for MVP. Do not mix `async def` with sync DB calls |
| **Never return errors in `{"data": ...}` wrapper** | Errors use raw `{"detail": "..."}` via `HTTPException` |
| **Never commit without `db.refresh(obj)`** | After `db.commit()`, call `db.refresh(obj)` to get DB-generated values (id, created_at) |
| **Never skip migration for schema changes** | All model changes must have a corresponding Alembic migration |

---

## Appendix: Alembic Setup Reference

### Initialize Alembic (run once)

```bash
cd openclaw/api
alembic init alembic
```

### `alembic/env.py` — Key Section

```python
from app.database import Base
from app import models  # noqa: F401 — import all models for autodiscovery

target_metadata = Base.metadata
```

### Generate a Migration

```bash
alembic revision --autogenerate -m "create users devices jobs tables"
```

### Apply Migrations

```bash
alembic upgrade head
```

### Downgrade

```bash
alembic downgrade -1
```

---

*This document is maintained by the Tech Lead / DevOps Engineer and is the authoritative reference for all API Team agents on the OpenClaw project. Changes to conventions must be reflected here before implementation begins.*
