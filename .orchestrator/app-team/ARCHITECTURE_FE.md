# Frontend Architecture Guide (AI Reference)

> This document defines the frontend architecture, conventions, and patterns used across all projects.
> Any AI tool scaffolding code, generating components, or performing tasks **must** follow these rules.
> This architecture is **project-agnostic** — adapt component names, modules, and domain logic to the specific project while keeping all patterns and conventions intact.

---

## Tech Stack

| Layer              | Technology                                    |
| ------------------ | --------------------------------------------- |
| Framework          | React 18 + TypeScript 5                       |
| Build Tool         | Vite 5 (SWC plugin)                           |
| Routing            | React Router DOM v6 (`createBrowserRouter`)   |
| Server State       | TanStack React Query v5                       |
| Global State       | React Context API (AuthContext, OrgContext)    |
| Forms              | React Hook Form + Zod (via `@hookform/resolvers`) |
| Styling            | Tailwind CSS 3 (utility-first, no CSS modules)|
| HTTP Client        | Axios                                         |
| Real-time          | Socket.IO Client                              |
| Notifications      | React Toastify                                |
| Icons              | React Icons (MD, FI, IO sets)                 |
| Charts             | react-chartjs-2                               |
| Image Hosting      | Cloudinary                                    |

---

## Folder Structure

```
src/
├── api/                     # Axios service layer (one file per domain)
├── assets/                  # Static images, logos
├── components/
│   ├── common/              # Reusable UI (buttons, modals, tables, dropdowns, nav)
│   ├── shared/              # Cross-feature shared components
│   └── {module}/            # Module-specific components (adapt to your project)
├── config/
│   ├── app.tsx              # Route definitions & layout mapping
│   ├── endpoint.ts          # API endpoint constants
│   ├── config.ts            # Navigation structure, validation messages
│   └── interfaces.ts        # Shared TypeScript interfaces
├── context/                 # React Contexts (AuthContext, etc.)
├── hooks/                   # Custom hooks (queries, mutations, utilities)
├── layouts/
│   ├── MainLayout.tsx       # General pages (home, profile, admin)
│   ├── ServiceLayout.tsx    # App modules (domain-specific pages)
│   └── AuthLayout.tsx       # Login, register, invitation pages
├── lib/                     # Third-party wrappers (socket.ts)
├── mocks/                   # Mock data for development
├── pages/
│   └── {app}/{module}/      # Page components organized by app and module
├── router/                  # Router configuration & guards
├── types/                   # TypeScript type definitions
├── utils/
│   └── validators/          # Zod validation schemas
├── index.css                # Global styles + Tailwind directives
├── main.tsx                 # App entry point
└── vite-env.d.ts
```

### Rules

- **One component per file.** File name matches the component name in PascalCase.
- **Feature components** go under `components/{module}/`. Only truly reusable components go in `components/common/`.
- **Page components** go under `pages/{app}/{module}/`.
- **Never** create a `utils/index.ts` barrel file. Import utilities directly.

---

## Routing

### Pattern

Routes are dynamic and org-scoped:

```
/:org/:app/:module/:feature/:action
```

Adapt the route segments to your project's domain. Example: `/acme/crm/contacts/list`

### Configuration

All routes are defined in `src/config/app.tsx` using `createBrowserRouter`.

```tsx
// Layout groups (adapt to your project):
// 1. MainLayout    — general pages (home, profile, settings, admin)
// 2. ServiceLayout  — app modules (domain-specific feature pages)
// 3. AuthLayout     — auth pages (login, register, invitation)
```

### Route Guards

| Guard            | Purpose                                           |
| ---------------- | ------------------------------------------------- |
| `ProtectedRoute` | Requires auth + optional role array               |
| `AuthRoute`      | Redirects already-authenticated users away         |

When adding a new page:

1. Create the page component in `pages/{app}/{module}/`.
2. Add the route entry in `src/config/app.tsx` under the correct layout.
3. Wrap with `ProtectedRoute` and specify `allowedRoles` if needed.

---

## State Management

### Authentication — `AuthContext`

```tsx
const { isAuthenticated, roles, login, logout, checkLoginStatus } = useAuth();
```

- Token, roles, userId, organizationId stored in **cookies** (via `js-cookie`).
- Token expiry: 1 day.

### Organization — `useOrganization()` hook

- Stored in **localStorage**.
- Contains branding, color scheme, enabled apps/modules.
- Colors injected as CSS variables (`--color-primary`, etc.).

### Server State — React Query

All API data uses React Query. Never use `useState` + `useEffect` for API calls.

```tsx
// Read
const { data, isLoading } = useQuery({
  queryKey: ["{entities}", filters],
  queryFn: () => EntityService.getAll(filters),
});

// Write
const mutation = useMutation({
  mutationFn: (data) => EntityService.create(data),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["{entities}"] }),
});
```

Default query client options: `refetchOnWindowFocus: false`.

---

## Component Conventions

### Naming

| Thing         | Convention       | Example                     |
| ------------- | ---------------- | --------------------------- |
| Component     | PascalCase       | `CreateUserModal.tsx`       |
| Hook          | camelCase, `use` | `useEntityServices.ts`      |
| Utility       | camelCase        | `dateUtils.ts`              |
| Type/Interface| PascalCase, `I`  | `IEntityPayload`            |
| Constant      | UPPER_SNAKE_CASE | `SIDEBAR_NAVIGATION`        |

### Component Structure

```tsx
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

// 1. Types/Interfaces
interface Props {
  isOpen: boolean;
  onClose: () => void;
}

// 2. Validation schema (if form)
const schema = z.object({
  name: z.string().min(1, "Required"),
});
type FormData = z.infer<typeof schema>;

// 3. Component
const MyComponent: React.FC<Props> = ({ isOpen, onClose }) => {
  // hooks first
  // derived state
  // handlers
  // render
  return <div className="...">{/* JSX */}</div>;
};

export default MyComponent;
```

### Modal Pattern

All modals receive `isOpen` and `onClose` props:

```tsx
<CreateEntityModal isOpen={showModal} onClose={() => setShowModal(false)} />
```

### Compound Components

Used for navigation:

```tsx
<TopNavigation.HorizontalContent>
  {/* items */}
</TopNavigation.HorizontalContent>
```

---

## Styling

### Tailwind CSS Only

- Use Tailwind utility classes. No CSS modules, no styled-components.
- Use `tailwind-merge` when conditionally combining classes.
- Dynamic theme colors via CSS variables: `var(--color-primary)`.

### Custom Colors (tailwind.config.js)

```
primary, secondary, accent, light, dark, neutral, success, warning, danger
```

### Responsive

Use Tailwind breakpoints: `sm:`, `md:`, `lg:`, `xl:`.

### Scrollbar

Use the `.rounded-scrollbar` class for custom scrollbar styling.

---

## API Layer

### Service Files

Located in `src/api/`. One file per domain.

```tsx
// src/api/{entity}Api.ts
import axios from "axios";
import { getAuthHeaders } from "../utils/authUtils";

const BASE = import.meta.env.VITE_BASE_URL;

const EntityService = {
  getAll: async (filters?: object) =>
    axios.get(`${BASE}/{entities}`, { headers: getAuthHeaders(), params: filters }),

  getById: async (id: string) =>
    axios.get(`${BASE}/{entities}/${id}`, { headers: getAuthHeaders() }),

  create: async (data: IEntityPayload) =>
    axios.post(`${BASE}/{entities}`, data, { headers: getAuthHeaders() }),

  update: async (id: string, data: Partial<IEntityPayload>) =>
    axios.patch(`${BASE}/{entities}/${id}`, data, { headers: getAuthHeaders() }),

  delete: async (id: string) =>
    axios.delete(`${BASE}/{entities}/${id}`, { headers: getAuthHeaders() }),
};

export default EntityService;
```

### Endpoint Constants

Defined in `src/config/endpoint.ts`. Always reference these, never hardcode URLs.

### Auth Headers

```tsx
import Cookies from "js-cookie";

export const getAuthHeaders = () => ({
  Authorization: `Bearer ${Cookies.get("token")}`,
});
```

---

## Custom Hooks

### Query Hooks

```tsx
// src/hooks/use{Entities}.ts
export const useEntities = (filters?: object) => {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["{entities}", filters],
    queryFn: () => EntityService.getAll(filters),
    enabled: isAuthenticated,
  });
};
```

### Mutation Hooks

```tsx
export const useCreateEntity = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: IEntityPayload) => EntityService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["{entities}"] });
      toast.success("Entity created");
    },
    onError: () => toast.error("Failed to create entity"),
  });
};
```

### Common Domain Hooks

Each project should define its own domain hooks. Reuse existing hooks — never recreate them:

| Hook                     | Domain                      |
| ------------------------ | --------------------------- |
| `useAuth()`              | Authentication context      |
| `useRole()`              | Parse role from cookies     |
| `useOrganization()`      | Organization data           |
| `useOrganizationId()`    | Current org ID              |
| `useUser()` / `useUsers()` | User data                |
| `use{Module}Services()`  | Module-specific CRUD hooks  |
| `useAttachment()`        | File uploads                |
| `useEmail()`             | Email operations            |

Add project-specific hooks as needed following the same pattern.

---

## Forms

### Always Use

- `react-hook-form` for form state
- `zod` for validation schema
- `@hookform/resolvers/zod` to connect them

### Pattern

```tsx
const schema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email"),
});

type FormData = z.infer<typeof schema>;

const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
  resolver: zodResolver(schema),
  defaultValues: { name: "", email: "" },
});

const onSubmit = (data: FormData) => {
  mutation.mutate(data, {
    onSuccess: () => { onClose(); toast.success("Saved"); },
    onError: () => toast.error("Error"),
  });
};
```

### Rules

- Define Zod schemas in `src/utils/validators/` or co-located with the form.
- Derive types from schemas using `z.infer<typeof schema>`.
- Show validation errors inline below each field.
- Disable submit button while `isSubmitting`.

---

## Authentication & Authorization

### Role Format

```
{app}-{module}-{level}
```

Adapt the segments to your project's domain:

| Segment  | Values (define per project)                  |
| -------- | -------------------------------------------- |
| App      | Your project's apps (e.g., `hms`, `ecom`, `crm`, `admin`) |
| Module   | Your project's modules (e.g., `orders`, `contacts`, `inventory`) |
| Level    | `admin`, `manager`, `user`                   |

### Using Roles

```tsx
const { app, module, level } = useRole();

// Conditional rendering
{level === "admin" && <AdminPanel />}
```

### Protecting Routes

```tsx
<Route element={<ProtectedRoute allowedRoles={["{app}-{module}-admin"]} />}>
  <Route path="admin" element={<AdminPage />} />
</Route>
```

---

## Layouts

| Layout           | Use For                                         |
| ---------------- | ----------------------------------------------- |
| `MainLayout`     | Home, profile, settings, admin panel            |
| `ServiceLayout`  | App modules (domain-specific feature pages)     |
| `AuthLayout`     | Login, register, invitation                     |

`ServiceLayout` renders side navigation for admin/manager and top navigation dropdowns based on role level.

Add project-specific layouts as needed.

---

## Environment Variables

Access via `import.meta.env.VITE_*`:

```
VITE_BASE_URL=http://localhost:3000/api
```

Never hardcode API URLs. Always use endpoint constants from `src/config/endpoint.ts`.

Add project-specific env vars as needed — always document them in `.env.example`.

---

## Notifications

Use React Toastify:

```tsx
import { toast } from "react-toastify";

toast.success("Created successfully");
toast.error("Something went wrong");
toast.info("Processing...");
```

---

## Scaffolding Checklist

When creating a **new feature/module**, follow this order:

1. **Types** — Define interfaces in `src/types/` or co-located.
2. **API Service** — Create `src/api/{feature}Api.ts` with CRUD methods.
3. **Hooks** — Create `src/hooks/use{Feature}.ts` with query + mutation hooks.
4. **Validation** — Create Zod schemas in `src/utils/validators/{feature}.ts`.
5. **Components** — Build UI in `src/components/{module}/{Feature}/`.
6. **Pages** — Create page in `src/pages/{app}/{module}/`.
7. **Routes** — Register in `src/config/app.tsx` with proper guards.
8. **Navigation** — Add sidebar/dropdown entries in `src/config/config.ts`.

---

## Do NOT

- Use `useState` + `useEffect` for fetching data. Use React Query.
- Use CSS modules, styled-components, or inline `<style>` tags. Use Tailwind.
- Create barrel `index.ts` files that re-export everything.
- Use class components. All components are functional.
- Hardcode API URLs. Use `endpoint.ts` constants.
- Store auth tokens in localStorage. Use cookies via `js-cookie`.
- Skip Zod validation on forms. Every form needs a schema.
- Use `any` type. Define proper interfaces.
