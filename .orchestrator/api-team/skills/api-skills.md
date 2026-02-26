# API Team Skills

Reusable recipes that follow **ARCHITECTURE_BE.md** exactly. Every skill produces code that conforms to the FastAPI router pattern, SQLAlchemy models, Pydantic v2 schemas, and standard response envelopes.

> **Before using any skill, read `ARCHITECTURE_BE.md`** — it is the source of truth.

---

## Skill: Scaffold CRUD Router

**When to use**: Creating a new entity with full CRUD operations.

**Prerequisite**: The SQLAlchemy model for this entity must exist first (see Skill: Create SQLAlchemy Model).

### Step 1 — Pydantic Schemas (`app/schemas/{entity}.py`)

```python
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict


class {Entity}Base(BaseModel):
    name: str
    description: Optional[str] = None
    status: Literal["active", "inactive"] = "active"
    # Add entity-specific fields here


class {Entity}Create({Entity}Base):
    pass  # user_id / owner inferred from auth token


class {Entity}Update(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Literal["active", "inactive"]] = None
    # Mirror {Entity}Base fields, all Optional


class {Entity}Response({Entity}Base):
    id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### Step 2 — Router (`app/routers/{entities}.py`)

```python
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

### Step 3 — Register Router in `app/main.py`

```python
from app.routers import {entities}

app.include_router({entities}.router, prefix="/api")
```

### Step 4 — Register Model in `app/models/__init__.py`

```python
from app.models.{entity} import {Entity}
__all__ = [..., "{Entity}"]
```

### Deliverables Checklist
```
✅ app/models/{entity}.py         (prerequisite — SQLAlchemy model)
✅ app/schemas/{entity}.py        (Base, Create, Update, Response schemas)
✅ app/routers/{entities}.py      (CRUD router)
✅ Registration in app/main.py
✅ Model registered in app/models/__init__.py
✅ Alembic migration created and applied
```

---

## Skill: Create SQLAlchemy Model

**When to use**: Defining a new database model before building the router.

### Pattern

```python
# app/models/{entity}.py
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class {Entity}(Base):
    __tablename__ = "{entities}"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Core fields (adapt to domain)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, default="active")

    # Foreign key (if owned by a user)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Standard fields (ALWAYS include)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="{entities}")
```

### Relation Patterns

```python
# One-to-Many: Parent has many Children
class Parent(Base):
    __tablename__ = "parents"
    id = Column(Integer, primary_key=True, index=True)
    children = relationship("Child", back_populates="parent")
    created_at = Column(DateTime, default=datetime.utcnow)


class Child(Base):
    __tablename__ = "children"
    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=False)
    parent = relationship("Parent", back_populates="children")
    created_at = Column(DateTime, default=datetime.utcnow)


# Many-to-Many: via association table
from sqlalchemy import Table
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)
```

### After Creating Model

```bash
# Generate and apply migration
alembic revision --autogenerate -m "add {entity} table"
alembic upgrade head
```

### Rules
- Table names: lowercase plural (`users`, `devices`, `jobs`)
- Always include `id` (primary key, autoincrement) and `created_at`
- Foreign keys: `{entity}_id` naming convention, `ForeignKey("table.id")`
- Import the model in `app/models/__init__.py` before running Alembic

---

## Skill: Add Auth to Router

**When to use**: Protecting endpoints with JWT authentication.

### Pattern

```python
# In app/routers/{entities}.py
from app.dependencies.auth import get_current_user
from app.models.user import User

# All protected routes use Depends(get_current_user)
@router.get("/")
def list_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # <-- auth guard
):
    ...

# Public endpoint (no auth) — rare, document explicitly
@router.get("/public")
def public_list(db: Session = Depends(get_db)):
    ...
```

### Role-Based Access (Optional)

If the project requires RBAC, add a role check dependency:

```python
# app/dependencies/auth.py — add role checker
def require_role(required_role: str):
    def checker(current_user: User = Depends(get_current_user)):
        if current_user.role != required_role and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker

# Usage
@router.post("/")
def create_item(
    payload: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("manager")),
):
    ...
```

### Rules
- `get_current_user` dependency on **all** protected endpoints
- Public endpoints are the exception — document them with a comment
- Never skip auth on write operations (POST, PATCH, DELETE)

---

## Skill: Add Pagination & Filtering

**When to use**: Enhancing a list endpoint with query parameters.

### Router Pattern

```python
from fastapi import Query


@router.get("/", response_model=list[{Entity}Response])
def list_{entities}(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * limit
    query = db.query({Entity}).filter({Entity}.user_id == current_user.id)
    total = query.count()
    items = query.offset(offset).limit(limit).all()

    return {
        "data": items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        }
    }
```

### Text Search Pattern

```python
from sqlalchemy import or_

if search:
    query = query.filter(
        or_(
            {Entity}.name.ilike(f"%{search}%"),
            {Entity}.description.ilike(f"%{search}%"),
        )
    )
```

### Query Parameters Supported
| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number (≥1) |
| `limit` | int | 10 | Items per page (1-100) |
| `search` | str | — | Text search across name/description |
| `status` | str | — | Filter by status field |

---

## Skill: Add File Upload

**When to use**: Adding file upload to a router endpoint.

### Router Pattern

```python
from fastapi import File, UploadFile
from app.utils.file_handler import save_upload


@router.post("/{item_id}/upload", status_code=status.HTTP_200_OK)
def upload_file(
    item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.query({Entity}).filter(
        {Entity}.id == item_id,
        {Entity}.user_id == current_user.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="{Entity} not found")

    file_path = save_upload(file)

    item.file_path = file_path
    db.commit()
    db.refresh(item)

    return {"data": item}
```

### File Handler (`app/utils/file_handler.py`)

```python
import uuid, os
from fastapi import UploadFile, HTTPException
from app.config import settings

ALLOWED_TYPES = {"application/pdf", "text/plain", "image/jpeg", "image/png"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def save_upload(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {file.content_type}")
    content = file.file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10MB limit.")
    ext = os.path.splitext(file.filename or "")[1]
    path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)
    return path
```

### Rules
- Filename: `{uuid_hex}{original_extension}` — never use original filename
- Location: always inside `settings.UPLOAD_DIR`
- DB Storage: store the relative path string
- Max size: 10 MB — enforced by `file_handler.py`

---

## Skill: Write API Tests (pytest + TestClient)

**When to use**: Testing CRUD endpoints for a router.

### Test File Structure (`tests/test_{entities}.py`)

```python
def test_create_{entity}(client, auth_headers):
    response = client.post(
        "/api/{entities}/",
        json={"name": "Test {Entity}", "description": "Test desc"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Test {Entity}"
    assert "id" in data


def test_list_{entities}(client, auth_headers):
    # Create two items first
    for i in range(2):
        client.post("/api/{entities}/", json={"name": f"Item {i}"}, headers=auth_headers)

    response = client.get("/api/{entities}/", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


def test_get_{entity}(client, auth_headers):
    create_res = client.post("/api/{entities}/", json={"name": "Get Test"}, headers=auth_headers)
    item_id = create_res.json()["data"]["id"]

    response = client.get(f"/api/{entities}/{item_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["id"] == item_id


def test_get_{entity}_not_found(client, auth_headers):
    response = client.get("/api/{entities}/9999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "{Entity} not found"


def test_update_{entity}(client, auth_headers):
    create_res = client.post("/api/{entities}/", json={"name": "Before"}, headers=auth_headers)
    item_id = create_res.json()["data"]["id"]

    response = client.patch(
        f"/api/{entities}/{item_id}",
        json={"name": "After"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "After"


def test_delete_{entity}(client, auth_headers):
    create_res = client.post("/api/{entities}/", json={"name": "Delete Me"}, headers=auth_headers)
    item_id = create_res.json()["data"]["id"]

    response = client.delete(f"/api/{entities}/{item_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify it's gone
    get_res = client.get(f"/api/{entities}/{item_id}", headers=auth_headers)
    assert get_res.status_code == 404


def test_validation_error(client, auth_headers):
    # Missing required 'name' field
    response = client.post("/api/{entities}/", json={}, headers=auth_headers)
    assert response.status_code == 422  # Pydantic validation failure
    assert "detail" in response.json()


def test_unauthorized_access(client):
    response = client.get("/api/{entities}/")
    assert response.status_code == 403  # No token provided
```

### Test Priority
1. **Happy path** — CRUD operations succeed with valid data
2. **Validation** — Missing/invalid input returns 422 with Pydantic errors
3. **Auth** — Unauthenticated requests return 403
4. **Not found** — Non-existent IDs return 404
5. **Isolation** — Each test gets a fresh DB via `autouse` fixture

### Rules
- Use `conftest.py` fixtures: `client`, `auth_headers`, `test_user`
- Assert both status code and response body shape
- Never use the real database — always the test override
- Run with `pytest tests/ -v`

---

## Skill: External HTTP Integration (httpx)

**When to use**: Calling third-party APIs or microservices.

### Service Client Pattern

```python
# app/utils/{service}_client.py
import httpx
from app.config import settings


class {Service}Client:
    def __init__(self):
        self.base_url = settings.{SERVICE}_BASE_URL
        self.api_key = settings.{SERVICE}_API_KEY
        self.timeout = 15.0

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def send_request(self, endpoint: str, data: dict) -> dict:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/{endpoint}",
                    json=data,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise Exception("Service timeout")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise Exception("Service rate limited")
            raise Exception(f"Service error: {e.response.text}")


{service}_client = {Service}Client()
```

### Integration Rules
- API keys always from `settings` / environment variables — never hardcoded
- Set timeouts on all external calls (5-30 seconds)
- Catch and translate external errors before they reach the router
- Log all external calls and failures

---

## Skill: Database Seeding

**When to use**: Creating development/test seed data.

### Pattern (`scripts/seed.py` or `tests/conftest.py`)

```python
from app.database import SessionLocal
from app.models.user import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed_database():
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(User).filter(User.email == "admin@demo.com").first():
            print("Already seeded.")
            return

        admin = User(
            email="admin@demo.com",
            full_name="Admin User",
            hashed_password=pwd_context.hash("securepassword"),
            is_active=True,
        )
        db.add(admin)
        db.commit()

        print("Seeding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
```

### Rules
- Always check for existing records before inserting to keep seeds idempotent
- Hash passwords with passlib — never store plaintext
- Seed parent records before child records (respect foreign keys)
