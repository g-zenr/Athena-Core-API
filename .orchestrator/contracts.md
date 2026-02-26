# Shared Contracts — API ↔ App Type Synchronization

This document defines how the API team and App team share types, interfaces, and data contracts to stay in sync.

---

## The Problem

The API team produces endpoints with specific request/response shapes (defined by Zod schemas).
The App team consumes those endpoints with TypeScript interfaces.
**If these diverge, the integration breaks.**

## The Solution: Contract-First Development

Before any implementation, define the **contract** — the exact shape of data flowing between API and App.

---

## Contract Definition Format

For every entity/feature, the contract must specify:

```yaml
Entity: {EntityName}
API Base: /api/{entities}

Endpoints:
  - method: GET
    path: /api/{entities}/
    query: { page, limit, search, status }
    response: { data: [{Entity}[]] }

  - method: GET
    path: /api/{entities}/{id}
    params: { id: int }
    response: { data: {Entity} }

  - method: POST
    path: /api/{entities}/
    body: {Entity}Create payload
    response: { data: {Entity} }  # 201

  - method: PATCH
    path: /api/{entities}/{id}
    params: { id: int }
    body: {Entity}Update payload (all fields optional)
    response: { data: {Entity} }

  - method: DELETE
    path: /api/{entities}/{id}
    params: { id: int }
    response: (no body)  # 204

Error Responses:
  - 401: { detail: "Could not validate credentials" }
  - 403: { detail: "Not authenticated" }
  - 404: { detail: "{Entity} not found" }
  - 422: { detail: [{ loc, msg, type }] }  # Pydantic validation failure

Entity Shape:
  id: int
  name: string
  description?: string
  status: "active" | "inactive"
  user_id: int
  created_at: string (ISO date)

Create Payload:
  name: string (required)
  description?: string
  status?: "active" | "inactive"

Update Payload (all optional):
  name?: string
  description?: string
  status?: "active" | "inactive"
```

---

## How Contracts Map to Code

### API Side (Source of Truth)

The **Pydantic schemas** in `app/schemas/{entity}.py` are the single source of truth for validation:

```python
# app/schemas/{entity}.py
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class {Entity}Base(BaseModel):
    name: str
    description: Optional[str] = None
    status: Literal["active", "inactive"] = "active"


class {Entity}Create({Entity}Base):
    pass


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

### App Side (Mirror)

The **TypeScript interface** in `src/types/{entity}.ts` must mirror the API Pydantic schemas:

```typescript
// src/types/{entity}.ts
export interface I{Entity} {
  id: number;
  name: string;
  description?: string;
  status: "active" | "inactive";
  user_id: number;
  created_at: string;
}

// Must match {Entity}Create Pydantic schema exactly
export interface I{Entity}Payload {
  name: string;
  description?: string;
  status?: "active" | "inactive";
}

// Must match {Entity}Update Pydantic schema exactly
export interface I{Entity}UpdatePayload {
  name?: string;
  description?: string;
  status?: "active" | "inactive";
}
```

### Verification Rule

For every field in the API Pydantic schema:
- If `str` → `string` in TS interface
- If `Optional[str]` → `string?` / `string | undefined`
- If `Literal["a", "b"]` → `"a" | "b"` in TS interface
- If `int` → `number`
- If `bool` → `boolean`
- If `list[T]` → `T[]`
- If nested `BaseModel` → nested interface

---

## Standard Response Shapes

All API responses follow these standard shapes. The App team must handle ALL of them:

### Success Response (200/201)

```typescript
// Single resource
interface IDataResponse<T> {
  data: T;
}
```

### Paginated Response (200)

```typescript
interface IPaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}
```

### Validation Error (422 — Pydantic)

```typescript
interface IPydanticError {
  detail: Array<{
    loc: string[];
    msg: string;
    type: string;
  }>;
}
```

### Not Found / Auth Error

```typescript
interface IDetailError {
  detail: string;  // e.g., "{Entity} not found", "Could not validate credentials"
}
```

### Server Error (500)

```typescript
interface IDetailError {
  detail: string;  // "Internal Server Error"
}
```

---

## Auth Contract

Authentication is a cross-cutting concern that both teams must agree on:

### Token Storage
- **Where**: `Authorization: Bearer <token>` header
- **Library**: stored in memory or `localStorage` on frontend; `HTTPBearer` on backend
- **Expiry**: 24 hours (configurable via `settings.ACCESS_TOKEN_EXPIRE_HOURS`)

### JWT Payload

```typescript
interface IJWTPayload {
  sub: string;    // String-cast user ID
  email: string;
  exp: number;    // Unix timestamp
}
```

### Auth Endpoints

```
POST /api/auth/register
  Body: { email: string, password: string, full_name?: string }
  Response: { data: { access_token: string, token_type: "bearer", user: IUser } }  # 201

POST /api/auth/login
  Body: { email: string, password: string }
  Response: { data: { access_token: string, token_type: "bearer", user: IUser } }
```

### Frontend Auth Header

```typescript
// Always attach to protected requests:
headers: { Authorization: `Bearer ${accessToken}` }
```

---

## Pagination Contract

All list endpoints follow the same pagination pattern (when implemented):

### Request (App → API)

```
GET /api/{entities}/?page=1&limit=10&search=text
```

### Response (API → App)

```typescript
{
  data: [...],
  pagination: {
    page: 1,
    limit: 10,
    total: 150,
    total_pages: 15,
  }
}
```

Both teams must use the same query parameter names and response shape.
Note: field is `total_pages` (snake_case from Python), not `totalPages`.

---

## Contract Checklist

When defining a new feature contract, verify:

```
✅ Entity shape matches between Zod schema (API) and TypeScript interface (App)
✅ All required fields are required on both sides
✅ All optional fields are optional on both sides
✅ Enum values match exactly (e.g., "ACTIVE" | "INACTIVE")
✅ Entity shape matches between Pydantic Response schema (API) and TypeScript interface (App)
✅ All required fields are required on both sides
✅ All optional fields are optional on both sides
✅ Literal/enum values match exactly (e.g., "active" | "inactive")
✅ Response uses {"data": ...} envelope on success
✅ Error responses handled on frontend (401, 403, 404, 422)
✅ Pagination parameters match (page, limit, search) — response uses total_pages (snake_case)
✅ Auth token sent as Authorization: Bearer header
✅ IDs are integers (int), not strings
```

---

## When to Define Contracts

1. **Before any implementation** — Tech Lead or Chief Architect defines the contract
2. **API team implements** using Pydantic schemas that match the contract
3. **App team implements** using TypeScript interfaces that match the contract
4. **If either team needs to change the contract** — both teams must update their code
5. **Integration testing** verifies the contract is honored end-to-end
