# App Team Skills

Reusable recipes that follow **ARCHITECTURE_FE.md** exactly. Every skill produces code using React Query for data, React Hook Form + Zod for forms, Tailwind CSS for styling, and Axios for HTTP.

> **Before using any skill, read `ARCHITECTURE_FE.md`** — it is the source of truth.

---

## Skill: Scaffold Feature Module

**When to use**: Creating a complete new feature with list page, create/edit forms, and data management.

**Follow this exact order** (from ARCHITECTURE_FE.md scaffolding checklist):

### Step 1 — Types (`src/types/{entity}.ts`)

```typescript
export interface I{Entity} {
  id: string;
  name: string;
  description?: string;
  status: "ACTIVE" | "INACTIVE";
  isDeleted: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface I{Entity}Payload {
  name: string;
  description?: string;
  status?: "ACTIVE" | "INACTIVE";
}

export interface I{Entity}ListResponse {
  status: string;
  data: I{Entity}[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}
```

### Step 2 — API Service (`src/api/{entity}Api.ts`)

```typescript
import axios from "axios";
import { getAuthHeaders } from "../utils/authUtils";
import { I{Entity}Payload } from "../types/{entity}";

const BASE = import.meta.env.VITE_BASE_URL;

const {Entity}Service = {
  getAll: async (params?: Record<string, unknown>) =>
    axios.get(`${BASE}/{entities}`, { headers: getAuthHeaders(), params }),

  getById: async (id: string) =>
    axios.get(`${BASE}/{entities}/${id}`, { headers: getAuthHeaders() }),

  create: async (data: I{Entity}Payload) =>
    axios.post(`${BASE}/{entities}`, data, { headers: getAuthHeaders() }),

  update: async (id: string, data: Partial<I{Entity}Payload>) =>
    axios.patch(`${BASE}/{entities}/${id}`, data, { headers: getAuthHeaders() }),

  delete: async (id: string) =>
    axios.delete(`${BASE}/{entities}/${id}`, { headers: getAuthHeaders() }),
};

export default {Entity}Service;
```

### Step 3 — Query & Mutation Hooks (`src/hooks/use{Entity}.ts`)

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { useAuth } from "../context/AuthContext";
import {Entity}Service from "../api/{entity}Api";

export const use{Entities} = (filters?: Record<string, unknown>) => {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["{entities}", filters],
    queryFn: () => {Entity}Service.getAll(filters).then((res) => res.data),
    enabled: isAuthenticated,
  });
};

export const use{Entity} = (id: string | undefined) => {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["{entities}", id],
    queryFn: () => {Entity}Service.getById(id!).then((res) => res.data),
    enabled: isAuthenticated && !!id,
  });
};

export const useCreate{Entity} = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: I{Entity}Payload) => {Entity}Service.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["{entities}"] });
      toast.success("{Entity} created successfully");
    },
    onError: () => toast.error("Failed to create {entity}"),
  });
};

export const useUpdate{Entity} = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<I{Entity}Payload> }) =>
      {Entity}Service.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["{entities}"] });
      toast.success("{Entity} updated successfully");
    },
    onError: () => toast.error("Failed to update {entity}"),
  });
};

export const useDelete{Entity} = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => {Entity}Service.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["{entities}"] });
      toast.success("{Entity} deleted successfully");
    },
    onError: () => toast.error("Failed to delete {entity}"),
  });
};
```

### Step 4 — Validation Schema (`src/utils/validators/{entity}.ts`)

```typescript
import { z } from "zod";

export const create{Entity}Schema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
  status: z.enum(["ACTIVE", "INACTIVE"]).optional(),
});

export const update{Entity}Schema = create{Entity}Schema.partial();

export type Create{Entity}FormData = z.infer<typeof create{Entity}Schema>;
export type Update{Entity}FormData = z.infer<typeof update{Entity}Schema>;
```

### Step 5 — Page (`src/pages/{app}/{module}/{Entity}Page.tsx`)

```tsx
import { useState } from "react";
import { use{Entities}, useDelete{Entity} } from "../../../hooks/use{Entity}";
import {Entity}Table from "../../../components/{module}/{Entity}Table";
import Create{Entity}Modal from "../../../components/{module}/Create{Entity}Modal";

const {Entity}Page = () => {
  const [showCreate, setShowCreate] = useState(false);
  const [filters, setFilters] = useState({ page: 1, limit: 10 });
  const { data, isLoading, isError } = use{Entities}(filters);
  const deleteMutation = useDelete{Entity}();

  if (isLoading) return <div className="animate-pulse">Loading...</div>;
  if (isError) return <div className="text-danger">Failed to load {entities}</div>;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-dark">{Entities}</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
        >
          Add {Entity}
        </button>
      </div>

      <{Entity}Table
        data={data?.data || []}
        pagination={data?.pagination}
        onPageChange={(page) => setFilters({ ...filters, page })}
        onDelete={(id) => deleteMutation.mutate(id)}
      />

      <Create{Entity}Modal isOpen={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  );
};

export default {Entity}Page;
```

### Step 6 — Route & Navigation

```tsx
// src/config/app.tsx — under correct layout:
{
  path: ":org/{app}/{module}",
  element: (
    <ProtectedRoute allowedRoles={["{app}-{module}-admin", "{app}-{module}-manager"]}>
      <{Entity}Page />
    </ProtectedRoute>
  ),
}

// src/config/config.ts — add nav entry:
{ label: "{Entities}", path: "/{app}/{module}", icon: "MdList", roles: ["{app}-{module}-admin"] }
```

### Deliverables Checklist
```
✅ src/types/{entity}.ts
✅ src/api/{entity}Api.ts
✅ src/hooks/use{Entity}.ts
✅ src/utils/validators/{entity}.ts
✅ src/components/{module}/ (Table + Modal components)
✅ src/pages/{app}/{module}/{Entity}Page.tsx
✅ Route in src/config/app.tsx
✅ Nav entry in src/config/config.ts
```

---

## Skill: Build a Form (React Hook Form + Zod)

**When to use**: Creating any data input form.

### Create Modal Pattern

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCreate{Entity} } from "../../hooks/use{Entity}";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email"),
  description: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

const Create{Entity}Modal: React.FC<Props> = ({ isOpen, onClose }) => {
  const createMutation = useCreate{Entity}();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", email: "", description: "" },
  });

  const onSubmit = (data: FormData) => {
    createMutation.mutate(data, {
      onSuccess: () => { reset(); onClose(); },
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-xl font-semibold text-dark">Create {Entity}</h2>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-dark">Name</label>
            <input
              {...register("name")}
              className="w-full rounded-lg border border-neutral/30 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
            {errors.name && <p className="mt-1 text-xs text-danger">{errors.name.message}</p>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-dark">Email</label>
            <input
              {...register("email")}
              type="email"
              className="w-full rounded-lg border border-neutral/30 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
            {errors.email && <p className="mt-1 text-xs text-danger">{errors.email.message}</p>}
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-neutral/30 px-4 py-2 text-sm text-dark hover:bg-neutral/10">
              Cancel
            </button>
            <button type="submit" disabled={isSubmitting || createMutation.isPending} className="rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary/90 disabled:opacity-50">
              {createMutation.isPending ? "Creating..." : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Create{Entity}Modal;
```

### Rules
- ALWAYS use `react-hook-form` + `zod` + `@hookform/resolvers/zod`
- Derive types with `z.infer<typeof schema>`
- Disable submit while `isSubmitting` or mutation `isPending`
- Show inline errors in `text-danger` below each field
- Modals receive `isOpen` and `onClose` props

---

## Skill: Build Data Table

**When to use**: Displaying paginated data with row actions.

```tsx
interface Props {
  data: I{Entity}[];
  pagination?: { page: number; limit: number; total: number; totalPages: number };
  onPageChange: (page: number) => void;
  onDelete: (id: string) => void;
}

const {Entity}Table: React.FC<Props> = ({ data, pagination, onPageChange, onDelete }) => {
  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-neutral">
        <p className="text-lg font-medium">No {entities} found</p>
        <p className="text-sm">Create your first {entity} to get started.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-neutral/20">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-neutral/20 bg-light">
          <tr>
            <th className="px-4 py-3 font-medium text-dark">Name</th>
            <th className="px-4 py-3 font-medium text-dark">Status</th>
            <th className="px-4 py-3 font-medium text-dark">Created</th>
            <th className="px-4 py-3 font-medium text-dark">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral/10">
          {data.map((item) => (
            <tr key={item.id} className="hover:bg-light/50 transition-colors">
              <td className="px-4 py-3 font-medium text-dark">{item.name}</td>
              <td className="px-4 py-3">
                <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                  item.status === "ACTIVE" ? "bg-success/10 text-success" : "bg-neutral/10 text-neutral"
                }`}>
                  {item.status}
                </span>
              </td>
              <td className="px-4 py-3 text-neutral">{new Date(item.createdAt).toLocaleDateString()}</td>
              <td className="px-4 py-3">
                <div className="flex gap-2">
                  <button className="text-primary hover:text-primary/80 text-sm">Edit</button>
                  <button onClick={() => onDelete(item.id)} className="text-danger hover:text-danger/80 text-sm">Delete</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {pagination && pagination.totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-neutral/20 px-4 py-3">
          <span className="text-sm text-neutral">
            Showing {(pagination.page - 1) * pagination.limit + 1} to {Math.min(pagination.page * pagination.limit, pagination.total)} of {pagination.total}
          </span>
          <div className="flex gap-1">
            <button onClick={() => onPageChange(pagination.page - 1)} disabled={pagination.page <= 1} className="rounded px-3 py-1 text-sm hover:bg-light disabled:opacity-50">Previous</button>
            <button onClick={() => onPageChange(pagination.page + 1)} disabled={pagination.page >= pagination.totalPages} className="rounded px-3 py-1 text-sm hover:bg-light disabled:opacity-50">Next</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default {Entity}Table;
```

---

## Skill: Add Authentication UI

**When to use**: Building login, register, and auth flow.

### Login Page

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "../../context/AuthContext";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";

const loginSchema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});
type LoginFormData = z.infer<typeof loginSchema>;

const LoginPage = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (data: LoginFormData) => {
    try {
      await login(data.email, data.password);
      toast.success("Welcome back!");
      navigate("/");
    } catch {
      toast.error("Invalid email or password");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-light">
      <div className="w-full max-w-sm rounded-xl bg-white p-8 shadow-lg">
        <h1 className="mb-6 text-center text-2xl font-bold text-dark">Sign In</h1>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-dark">Email</label>
            <input {...register("email")} type="email" autoComplete="email"
              className="w-full rounded-lg border border-neutral/30 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary" />
            {errors.email && <p className="mt-1 text-xs text-danger">{errors.email.message}</p>}
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-dark">Password</label>
            <input {...register("password")} type="password" autoComplete="current-password"
              className="w-full rounded-lg border border-neutral/30 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary" />
            {errors.password && <p className="mt-1 text-xs text-danger">{errors.password.message}</p>}
          </div>
          <button type="submit" disabled={isSubmitting}
            className="w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50 transition-colors">
            {isSubmitting ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
```

### Rules
- Store tokens in cookies via `js-cookie` — NEVER localStorage
- Use `AuthLayout` for auth pages
- Use `ProtectedRoute` with `allowedRoles` for protected pages
- Use `useAuth()` for auth state — never access cookies directly in components

---

## Skill: Add Loading & Error States

**When to use**: Handling all data states.

```tsx
const {Entity}Page = () => {
  const { data, isLoading, isError, error } = use{Entities}();

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-16 animate-pulse rounded-lg bg-neutral/10" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-lg font-medium text-danger">Something went wrong</p>
        <p className="text-sm text-neutral">{(error as Error)?.message || "Please try again"}</p>
      </div>
    );
  }

  if (!data?.data?.length) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-lg font-medium text-dark">No {entities} yet</p>
        <p className="text-sm text-neutral">Get started by creating your first {entity}.</p>
      </div>
    );
  }

  return <{Entity}Table data={data.data} />;
};
```

### Rules
- ALWAYS handle 4 states: loading, error, empty, success
- Use skeleton screens for loading (not spinners)
- React Query provides `isLoading` / `isError` automatically

---

## Skill: Add Real-Time Updates (Socket.IO)

**When to use**: Live data updates without polling.

```typescript
// src/lib/socket.ts
import { io } from "socket.io-client";
import Cookies from "js-cookie";
const socket = io(import.meta.env.VITE_SOCKET_URL, {
  auth: { token: Cookies.get("token") },
  autoConnect: false,
});
export default socket;
```

```tsx
// src/hooks/use{Entity}Socket.ts
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import socket from "../lib/socket";

export const use{Entity}Socket = () => {
  const queryClient = useQueryClient();
  useEffect(() => {
    socket.connect();
    socket.on("{entity}:created", () => queryClient.invalidateQueries({ queryKey: ["{entities}"] }));
    socket.on("{entity}:updated", () => queryClient.invalidateQueries({ queryKey: ["{entities}"] }));
    socket.on("{entity}:deleted", () => queryClient.invalidateQueries({ queryKey: ["{entities}"] }));
    return () => {
      socket.off("{entity}:created");
      socket.off("{entity}:updated");
      socket.off("{entity}:deleted");
      socket.disconnect();
    };
  }, [queryClient]);
};
```

### Rules
- Invalidate React Query cache on socket events — don't manually set state
- Always clean up listeners in useEffect return
- Connect with auth token from cookies

---

## Skill: Build Reusable UI Components

**When to use**: Creating common components for `src/components/common/`.

### Button

```tsx
import { twMerge } from "tailwind-merge";

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
}

const Button: React.FC<Props> = ({ variant = "primary", size = "md", isLoading, className, children, disabled, ...props }) => {
  const base = "inline-flex items-center justify-center rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2";
  const variants = {
    primary: "bg-primary text-white hover:bg-primary/90 focus:ring-primary",
    secondary: "border border-neutral/30 text-dark hover:bg-light focus:ring-neutral",
    danger: "bg-danger text-white hover:bg-danger/90 focus:ring-danger",
    ghost: "text-dark hover:bg-light focus:ring-neutral",
  };
  const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm", lg: "px-5 py-2.5 text-base" };

  return (
    <button
      className={twMerge(base, variants[variant], sizes[size], (disabled || isLoading) && "opacity-50 cursor-not-allowed", className)}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? "Loading..." : children}
    </button>
  );
};

export default Button;
```

### Modal

```tsx
import { useEffect, useRef } from "react";

interface Props { isOpen: boolean; onClose: () => void; title: string; children: React.ReactNode; }

const Modal: React.FC<Props> = ({ isOpen, onClose, title, children }) => {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    if (isOpen) { document.addEventListener("keydown", handleEsc); document.body.style.overflow = "hidden"; }
    return () => { document.removeEventListener("keydown", handleEsc); document.body.style.overflow = ""; };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div ref={overlayRef} onClick={(e) => e.target === overlayRef.current && onClose()}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-dark">{title}</h2>
          <button onClick={onClose} className="rounded-lg p-1 text-neutral hover:bg-light" aria-label="Close">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
};

export default Modal;
```

### Rules
- Use `tailwind-merge` for conditional class composition
- Theme colors: `primary`, `secondary`, `accent`, `light`, `dark`, `neutral`, `success`, `warning`, `danger`
- One component per file, PascalCase filenames
- NEVER use CSS modules, styled-components, or inline styles
