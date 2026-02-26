# Parallel Processing & Workflow Patterns

This file defines how the Chief Architect executes work in parallel using Task subagents.

## Execution Model

The orchestrator uses **wave-based parallel execution**:

```
Wave 1: All tasks with zero dependencies → launch in parallel
Wave 2: Tasks whose dependencies completed in Wave 1 → launch in parallel
Wave 3: Tasks whose dependencies completed in Wave 2 → launch in parallel
...until all tasks complete
```

### Wave Dependency Rules
- A task cannot start until ALL its dependencies are `completed`
- Tasks with no dependencies launch immediately in Wave 1
- When a wave completes, check which new tasks are now unblocked → launch them
- Maximum **4 parallel subagents** per wave

---

## How to Invoke the Task Tool

The orchestrator launches subagents using the **Task tool**. This is the execution mechanism for all code generation.

### Task Tool Parameters
```
Task tool call:
  description: "Short 3-5 word summary"     (e.g., "Create Prisma schemas")
  subagent_type: "general-purpose"           (ALWAYS use general-purpose)
  prompt: "Full agent prompt (see template below)"
```

### CRITICAL: Parallel Execution

**To run subagents in parallel, make MULTIPLE Task tool calls in a SINGLE message.**

Claude Code processes all Task calls from one message concurrently. This is the ONLY way to achieve parallel execution.

**Parallel (correct):** In ONE message, include 3 Task tool calls → all 3 run simultaneously
**Sequential (wrong):** Send Task call 1, wait for result, send Task call 2 → runs one at a time

### Example: Launching 3 Parallel Subagents

In a single message, you make 3 Task tool calls:

**Task call 1:**
```
description: "Create Prisma user schema"
subagent_type: "general-purpose"
prompt: "You are the DatabaseEngineer on the API Team. ..."
```

**Task call 2:**
```
description: "Create user Zod schemas"
subagent_type: "general-purpose"
prompt: "You are the BackendArchitect on the API Team. ..."
```

**Task call 3:**
```
description: "Create user frontend types and hooks"
subagent_type: "general-purpose"
prompt: "You are the FrontendEngineer on the App Team. ..."
```

All three launch in parallel. Wait for all to complete before starting the next wave.

---

## How to Launch Parallel Work

Use the **Task tool** with `subagent_type: "general-purpose"` for each independent work item.

### Subagent Prompt Template

When launching a subagent, structure the prompt **exactly** like this:

```
You are the {Agent Name} on the {Team Name}.

## Architecture Reference (MUST READ FIRST)
Read the following architecture document BEFORE writing any code:
- `.orchestrator/api-team/ARCHITECTURE_BE.md` (for API agents)
  OR
- `.orchestrator/app-team/ARCHITECTURE_FE.md` (for App agents)

Follow every pattern, convention, and "Do NOT" rule in the architecture doc.

## Your Agent Instructions
Read `.orchestrator/{team}/agents/{agent}.md` for your detailed role and patterns.

## Your Skills Reference
Read `.orchestrator/{team}/skills/{team}-skills.md` for reusable code recipes.

## Shared Contract
{Paste the specific entity contract — types, endpoints, request/response shapes}
(See `.orchestrator/contracts.md` for the contract system)

## Your Task
ID: {TEAM}-{NUMBER}
Title: {title}
Description: {detailed description of what to build}

## Context
- Project root: {path}
- Existing files relevant to this task:
  {list files that already exist and should be read/reused}
- Existing hooks/utilities to reuse:
  {list any hooks, utils, services that already exist — DO NOT recreate}

## Dependencies Completed
{List what prior work items produced and where their output files are}

## Deliverables Expected
{Exact list of files this agent must create or modify}

## Constraints
- Follow the ARCHITECTURE doc patterns EXACTLY
- Use existing utilities and hooks — do not reinvent
- Keep changes focused on this work item only
- Do not modify files outside your scope unless necessary
```

### Concrete Example: DatabaseEngineer Prompt

Here's a fully filled-in prompt for a DatabaseEngineer subagent:

```
You are the **Database Engineer** on the API Team.

## Architecture Reference (MUST READ FIRST)
Read `.orchestrator/api-team/ARCHITECTURE_BE.md` before writing any code.
Follow every pattern, convention, and "Do NOT" rule in the architecture doc.

## Your Agent Instructions
Read `.orchestrator/api-team/agents/database-engineer.md` for your detailed role and patterns.

## Your Skills Reference
Read `.orchestrator/api-team/skills/api-skills.md` for reusable code recipes.

## Shared Contract
Entity: Task
Fields:
  - id: String @id @default(auto()) @map("_id") @db.ObjectId
  - title: String (required)
  - description: String? (optional)
  - status: String (TODO | IN_PROGRESS | DONE), default TODO
  - assigneeId: String? @db.ObjectId (optional, references User)
  - dueDate: DateTime? (optional)
  - isDeleted: Boolean @default(false)
  - createdAt: DateTime @default(now())
  - updatedAt: DateTime @updatedAt

Relations:
  - assignee: User? (many-to-one via assigneeId)

## Your Task
ID: API-1
Title: Create Task Prisma Schema
Description: Create the Prisma schema file for the Task entity with all fields,
relations, and indexes. Follow the prismaSchemaFolder pattern (one file per entity).

## Context
- Project root: c:\Users\Renz\Documents\orchestrator\project-api
- Existing files: prisma/schema/base.prisma (datasource + generator config), prisma/schema/user.prisma
- The project uses prismaSchemaFolder preview feature

## Deliverables Expected
- prisma/schema/task.prisma (new file)

## Constraints
- Follow ARCHITECTURE_BE.md patterns EXACTLY
- Include all standard fields (id, isDeleted, createdAt, updatedAt)
- Use @db.ObjectId for relation fields
- One model per .prisma file
```

---

## Parallel Launch Rules

1. **Maximum 4 parallel subagents** at once — more causes context thrashing
2. **Group by team** when possible — API agents together, App agents together
3. **Shared files first** — if multiple agents will read the same file, read it in the main context first and pass content to subagents
4. **Short-lived agents** — each agent does one work item and returns. Don't chain multiple tasks into one agent
5. **Include the contract** — every subagent that writes code must receive the relevant entity contract (types, response shapes)

---

## Workflow Patterns

### Pattern 1: Full-Stack Feature Build
```
┌─────────────────────────────────────────────────────────────┐
│ Wave 0: Define contract (entity shape, endpoints, types)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
Wave 1:   ┌─────────────────┐   ┌─────────────────┐
          │ API Team         │   │ App Team         │
          │ • Prisma schema  │   │ • Types/interfaces│
          │ • Zod schemas    │   │ • API service     │
          │                  │   │ • Query hooks     │
          └────────┬─────────┘   └────────┬─────────┘
                   │                      │
Wave 2:   ┌────────┴─────────┐   ┌───────┴──────────┐
          │ • Module (3 files)│   │ • UI components   │
          │ • Register routes │   │ • Form + validation│
          │                   │   │ • Page component   │
          └────────┬──────────┘   └───────┬──────────┘
                   │                      │
                   └──────────┬───────────┘
                              ▼
Wave 3:   ┌───────────────────────────────┐
          │ Integration & Verification    │
          │ • Connect frontend → real API │
          │ • Verify data flow end-to-end │
          │ • Fix any mismatches          │
          └───────────────────────────────┘
                              │
                              ▼
Wave 4:   ┌───────────────────────────────┐
          │ Testing                        │
          │ • API tests (Mocha + Chai)     │
          │ • Frontend component tests     │
          └───────────────────────────────┘
```

### Pattern 2: API-First Development
Use when the frontend depends heavily on API shape:
```
Wave 1: Prisma schema + Zod schemas + API contract
Wave 2: Module implementation (3 factory files) + Register routes
Wave 3: Frontend types + API service + hooks (parallel with API tests)
Wave 4: UI components + pages + route registration
Wave 5: Integration testing
```

### Pattern 3: UI-First Development
Use when the feature is primarily visual with minimal API needs:
```
Wave 1: Frontend types + mock data + API contract definition
Wave 2: UI components + pages (with mock data) + Prisma schema (parallel)
Wave 3: API implementation + connect frontend to real API
Wave 4: Testing
```

### Pattern 4: Scaffold / Greenfield
Use when creating a new project from scratch:
```
Wave 1: DevOps — project init, folder structure, package.json, configs, env files
Wave 2: Base API setup + Base App setup (parallel)
         • API: server entry, router, DB connection, middleware, error handling, auth
         • App: app entry, router, layouts, auth context, theme, base components
Wave 3: Shared utilities, configs, and first feature contract
Wave 4: First feature (use Pattern 1)
```

---

## Wave Execution State Machine

Every wave follows this exact state flow:

```
┌──────────┐
│   PLAN   │  Identify all tasks with zero unmet dependencies
└────┬─────┘
     │
     ▼
┌──────────┐
│  TRACK   │  Mark all wave tasks as in_progress in TodoWrite
└────┬─────┘
     │
     ▼
┌──────────┐
│  LAUNCH  │  Make multiple Task tool calls in ONE message (parallel)
└────┬─────┘
     │ (all subagents execute concurrently)
     ▼
┌──────────┐
│ COLLECT  │  Wait for all Task results to return
└────┬─────┘
     │
     ▼
┌──────────┐
│ VALIDATE │  Run the validation gate for this wave
└────┬─────┘
     │
     ├── Pass → Mark completed in TodoWrite → Identify next wave → PLAN
     │
     └── Fail → Classify error → Launch fix subagent → Re-validate
```

### State Details

| State | What You Do | Tools Used |
|---|---|---|
| PLAN | Scan todo list, find tasks with all deps completed | TodoWrite (read) |
| TRACK | Mark wave tasks as in_progress | TodoWrite (update) |
| LAUNCH | Make N Task tool calls in one message | Task (multiple, parallel) |
| COLLECT | Read Task results (automatic — they return when done) | Task results |
| VALIDATE | Check deliverables against gate criteria | Read, Grep, Glob |
| COMPLETE | Mark successful tasks as completed | TodoWrite (update) |
| FIX | Launch targeted fix subagent for failures | Task (single) |

### Between Waves

After a wave completes and passes validation:
1. Update TodoWrite — mark completed tasks
2. Check: are there NEW tasks unblocked by this wave's completion?
3. If yes → start next wave (go to PLAN)
4. If no more tasks → go to Phase 5 (Quality Gate)

---

## Token Optimization for Subagents

### Model Selection per Task

| Task Complexity | Model Parameter | Use When |
|---|---|---|
| Simple (schema, types, config) | `model: "haiku"` | 1-2 files, well-defined pattern, no custom logic |
| Medium (CRUD module, hooks, components) | `model: "sonnet"` | 3-5 files, standard pattern from architecture doc |
| Complex (auth system, plugins, custom logic) | `model: "opus"` | 6+ files, novel patterns, cross-cutting concerns |

Add `model: "haiku"` or `model: "sonnet"` to the Task tool call to use a cheaper/faster model.

### Prompt Size Optimization

1. **Inline small contracts** (≤8 fields) instead of referencing contracts.md
2. **Reference docs, don't paste them** — tell agents to `Read` files, not embed file contents in prompts
3. **Only include relevant refs** — API agents get api-skills.md, not app-skills.md
4. **Summarize prior wave outputs** — list file paths + key exports, don't paste full code
5. **Use `run_in_background: true`** for non-blocking tasks (tests, docs) to free main context
6. **Batch related micro-tasks** — if two tasks modify the same file, combine into one subagent

### Background Agents

For tasks that don't block the next wave, use `run_in_background: true`:
```
Task tool call:
  description: "Write API tests for tasks"
  subagent_type: "general-purpose"
  run_in_background: true
  prompt: "..."
```

This frees the main context to continue planning while tests/docs are written in background.

---

## Error Recovery

### When a Subagent Fails

```
1. Read the error output from the failed subagent
2. Classify the error:
   a. CODE_ERROR — syntax, import, type error → fix the specific file
   b. PATTERN_VIOLATION — didn't follow ARCHITECTURE doc → re-run with explicit correction
   c. DEPENDENCY_MISSING — needs output from another task → check if dependency is done
   d. SCOPE_CREEP — agent modified files outside its scope → revert and re-run
3. Fix strategy:
   a. For CODE_ERROR: Launch a fix subagent targeting the specific file(s)
   b. For PATTERN_VIOLATION: Re-run the same task with the violation highlighted
   c. For DEPENDENCY_MISSING: Queue this task for the next wave
   d. For SCOPE_CREEP: Revert unintended changes, re-run with stricter scope
4. Never retry more than 2 times — if it fails twice, escalate to the user
```

### When Teams Produce Incompatible Code

```
1. Identify the mismatch:
   - Response shape doesn't match frontend expectation?
   - Types don't align between Zod schema and TS interface?
   - Endpoint path or method is different?
2. The CONTRACT is the source of truth (from contracts.md)
3. Determine which team deviated from the contract
4. Fix the deviating side (don't change both — that causes churn)
5. If the contract itself is wrong, update it and fix both sides
```

### When an Agent Produces Bad Code

```
1. Check against ARCHITECTURE doc:
   - Does the module have exactly 3 files? (API)
   - Is React Query used instead of useState+useEffect? (App)
   - Is Tailwind used instead of CSS modules? (App)
   - Is Zod validation present? (Both)
2. If pattern is violated:
   - Re-run the subagent with the specific violation called out
   - Include the correct pattern from the ARCHITECTURE doc in the prompt
3. If the code has bugs:
   - Launch a targeted fix subagent with the error message
   - Don't re-run the entire task — just fix the broken file(s)
```

---

## Validation Gates

### Gate 1: Contract Validation (After Wave 0)
Before launching implementation waves, verify:
```
✅ Entity shape is defined (all fields, types, optionality)
✅ All endpoints are listed (method, path, request, response)
✅ Error responses are specified
✅ Auth requirements are clear (which roles, which endpoints)
✅ Pagination format matches standard
```
**How to verify:** Read the contract definition. Check every field has a type, every endpoint has method/path/request/response, and error responses follow contracts.md standard shapes.

### Gate 2: API Completion (After API Wave)
Before the App team connects to the real API, verify:
```
✅ All endpoints return correct response shapes
✅ Zod validation works (invalid data returns 400)
✅ Auth middleware is applied (unauthenticated returns 401)
✅ Soft delete works (DELETE sets isDeleted=true)
✅ Pagination works with page/limit params
```
**How to verify:** Read controller files — check every method uses `safeParse`, `sendSuccessResponse`/`sendErrorResponse`, and `try-catch`. Read router files — verify `verifyToken` middleware on all routes. Grep for `isDeleted` in delete methods.

### Gate 3: App Completion (After App Wave)
Before integration testing, verify:
```
✅ All 4 data states handled (loading, error, empty, success)
✅ Forms use React Hook Form + Zod (not vanilla forms)
✅ React Query used for all API data (no useState+useEffect)
✅ Tailwind CSS only (no CSS modules or inline styles)
✅ Routes guarded with ProtectedRoute + allowedRoles
```
**How to verify:** Read page/component files. Grep for `useQuery` (must exist), `useState.*fetch` (must NOT exist), `useForm` (must exist for forms), `className=` with Tailwind utilities (must exist). Search for `isLoading`, `isError` state handling.

### Gate 4: Integration (After Integration Wave)
Before declaring the feature done:
```
✅ Frontend connects to real API (not mock data)
✅ Data flows correctly: form → API → database → query → display
✅ Error responses displayed correctly to user
✅ Auth flow works end-to-end (login → token → protected route → API call)
✅ Pagination works between frontend controls and API
```
**How to verify:** Compare API endpoint paths in router files with frontend API service files — paths must match exactly. Compare controller response shapes with frontend TypeScript interfaces. Check that `getAuthHeaders()` is called in all API service methods.

---

## Progress Tracking

The Architect MUST maintain the TodoWrite list throughout execution:

```
Example todo list during execution:

✅ Define User entity contract                    [completed]
✅ API-1: Create User Prisma schema               [completed]
✅ API-2: Create User Zod schemas                 [completed]
🔄 API-3: Build User module (3 files)             [in_progress]  ← subagent running
🔄 APP-1: Create User types + API service + hooks [in_progress]  ← subagent running
⬚  APP-2: Build User table + create modal         [pending]      depends on APP-1
⬚  API-4: Write User API tests                    [pending]      depends on API-3
⬚  INT-1: Connect frontend to real API            [pending]      depends on API-3, APP-2
⬚  QA-1:  Run acceptance tests                    [pending]      depends on INT-1
```

### Update Rules
- Mark `in_progress` BEFORE launching the subagent
- Mark `completed` IMMEDIATELY when the subagent returns successfully
- If a subagent fails, keep it as `in_progress` and add a fix task
- Add new tasks when discovered during execution
- Remove tasks that become unnecessary

---

## Conflict Resolution

If two parallel agents produce conflicting code:

1. **Architect reviews both outputs** — read the files each agent produced
2. **Check the contract** — which output matches the agreed contract?
3. **Fix the non-conforming side** — modify it to match the contract
4. **If neither matches** — update both to match the contract
5. **If the contract is ambiguous** — ask the user for direction
6. **Never modify both sides to "meet in the middle"** — one source of truth

---

## Concrete Example: Building a "Tasks" Feature

Here's how a real feature flows through the waves:

### Wave 0: Contract
```yaml
Entity: Task
Endpoints: CRUD at /tasks
Fields: title (required), description (optional), status (TODO|IN_PROGRESS|DONE), assigneeId (ObjectId, optional)
Auth: All endpoints require verifyToken, write ops require verifyRole("APP", "TASKS", action)
```

### Wave 1 (Parallel — 3 subagents)
```
API-1: DatabaseEngineer → Create prisma/schema/task.prisma + run prisma-generate
API-2: BackendArchitect → Create zod/task.zod.ts
APP-1: FrontendEngineer → Create src/types/task.ts + src/api/taskApi.ts + src/hooks/useTask.ts
```

### Wave 2 (Parallel — 2 subagents)
```
API-3: BackendArchitect → Create app/task/ (index.ts, task.controller.ts, task.router.ts) + register in index.ts
APP-2: FrontendEngineer → Create TaskTable, CreateTaskModal, TaskPage + route + nav entry
```

### Wave 3 (Sequential)
```
INT-1: Architect → Verify API endpoints work, connect frontend to real API, fix any mismatches
```

### Wave 4 (Parallel — 2 subagents)
```
API-4: APITester → Write Mocha+Chai tests for /tasks endpoints
APP-3: AppTester → Write component tests for TaskTable, CreateTaskModal
```
