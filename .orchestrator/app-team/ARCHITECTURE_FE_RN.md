# OpenClaw Frontend Architecture — React Native (Expo)

> **Authoritative Reference** for all App Team agents on the OpenClaw project.
> Every agent working on the frontend MUST read and follow this document before writing any code.

---

## 1. Tech Stack

| Concern | Library / Version |
|---|---|
| Framework | React Native 0.74 + Expo SDK 51 (managed workflow) |
| Language | TypeScript 5 |
| Navigation | React Navigation v6 (Stack + Bottom Tabs) |
| Server State | TanStack React Query v5 |
| Global State | React Context API (`AuthContext`) |
| Forms | React Hook Form + Zod (via `@hookform/resolvers/zod`) |
| Styling | NativeWind v4 (Tailwind CSS for React Native) |
| HTTP Client | Axios |
| Secure Storage | Expo SecureStore (for JWT token only) |
| File Picker | Expo Document Picker + Expo Image Picker |
| Icons | `@expo/vector-icons` (MaterialIcons, Feather) |
| Notifications | `react-native-toast-message` |
| Testing | Jest + `@testing-library/react-native` |

---

## 2. Project Folder Structure

```
openclaw/app/
├── src/
│   ├── api/
│   │   ├── client.ts          # Axios instance with auth interceptor
│   │   ├── authApi.ts         # login, register endpoints
│   │   ├── devicesApi.ts      # device CRUD + claim
│   │   └── jobsApi.ts         # job submit, list, status
│   ├── components/
│   │   ├── common/            # Reusable: Button, Input, Badge, Card, LoadingSpinner, Modal
│   │   ├── DeviceCard.tsx
│   │   ├── JobCard.tsx
│   │   └── JobDetailModal.tsx
│   ├── context/
│   │   └── AuthContext.tsx     # JWT storage, login/logout, current user
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useDevices.ts
│   │   └── useJobs.ts
│   ├── navigation/
│   │   ├── AppNavigator.tsx    # Root: Auth vs App based on auth state
│   │   ├── AuthNavigator.tsx   # Login, Register stack
│   │   ├── AppTabNavigator.tsx # Bottom tabs: Marketplace, Submit Job, Kanban
│   │   └── types.ts            # TypeScript navigation param lists
│   ├── screens/
│   │   ├── auth/
│   │   │   ├── LoginScreen.tsx
│   │   │   └── RegisterScreen.tsx
│   │   ├── marketplace/
│   │   │   └── MarketplaceScreen.tsx
│   │   ├── jobs/
│   │   │   └── SubmitJobScreen.tsx
│   │   └── kanban/
│   │       └── KanbanScreen.tsx
│   ├── types/
│   │   ├── api.ts              # Shared response envelope types
│   │   ├── user.ts
│   │   ├── device.ts
│   │   └── job.ts
│   └── utils/
│       ├── validators/
│       │   ├── auth.ts         # Login + register Zod schemas
│       │   └── job.ts          # Job submit Zod schema
│       └── formatters.ts       # Date, status label helpers
├── App.tsx                     # Entry: QueryClientProvider, NavigationContainer, AuthProvider, Toast
├── app.json                    # Expo config
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── babel.config.js
├── .env                        # Local env vars (not committed)
└── .env.example                # Template for required vars
```

---

## 3. TypeScript Type Conventions

All entity types live in `src/types/{entity}.ts`. They **mirror the backend Pydantic schemas exactly** — field names, optionality, and string literal unions must match the API response payloads.

### Naming Conventions

- Interface names are prefixed with `I`: `IUser`, `IDevice`, `IJob`
- String union types use `type`: `DeviceStatus`, `JobStatus`, `JobType`
- All `id` fields are `number` (backend uses integer primary keys)
- All timestamps are `string` (ISO 8601 from backend)
- Optional fields (nullable in backend) use `?`

### `src/types/user.ts`

```typescript
export interface IUser {
  id: number
  email: string
  created_at: string
}
```

### `src/types/device.ts`

```typescript
export type DeviceStatus = "online" | "offline" | "busy"

export interface IDevice {
  id: number
  name: string
  description?: string
  ai_model: string
  status: DeviceStatus
  claimed_by?: number
  owner_id: number
  created_at: string
}
```

### `src/types/job.ts`

```typescript
export type JobStatus = "todo" | "in_progress" | "done" | "failed"
export type JobType = "text" | "file"

export interface IJob {
  id: number
  title: string
  prompt: string
  file_name?: string
  job_type: JobType
  status: JobStatus
  device_id: number
  user_id: number
  result?: string
  error_reason?: string
  created_at: string
  updated_at: string
}
```

---

## 4. API Response Types (`src/types/api.ts`)

The backend wraps all non-auth responses in a `{ "data": T }` envelope.

```typescript
import type { IUser } from "./user"

// Standard response envelope for all non-auth endpoints
export interface IDataResponse<T> {
  data: T
}

// Auth endpoints return token + user directly (no envelope)
export interface IAuthResponse {
  access_token: string
  token_type: string
  user: IUser
}

// Paginated list response (if backend supports pagination)
export interface IPaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  per_page: number
}
```

**Rule**: All API functions return the unwrapped `data` field, not the raw envelope. Unwrapping happens inside the API module (`src/api/`), not in hooks or components.

---

## 5. Axios Client (`src/api/client.ts`)

The Axios client handles base URL configuration and auth header injection transparently for all API modules.

```typescript
import axios from "axios"
import * as SecureStore from "expo-secure-store"

const TOKEN_KEY = "openclaw_token"

const client = axios.create({
  baseURL: process.env.EXPO_PUBLIC_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
})

// Request interceptor: attach JWT from SecureStore on every request
client.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: on 401, clear token and navigate to login
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await SecureStore.deleteItemAsync(TOKEN_KEY)
      // Navigation to login is handled by AuthContext listener via token state
    }
    return Promise.reject(error)
  }
)

export { TOKEN_KEY }
export default client
```

**Rules:**
- `baseURL` is ALWAYS read from `process.env.EXPO_PUBLIC_API_URL` — never hardcoded
- The interceptor reads SecureStore on every request — this is acceptable because Expo SecureStore reads are fast
- On 401, delete the stored token; the `AuthContext` observes the token state and redirects automatically
- Multipart requests (file uploads) must override `Content-Type` to `multipart/form-data` in the individual API call

---

## 6. API Modules (`src/api/`)

Each entity has its own API module. All functions use the shared `client` instance and unwrap the `data` envelope before returning.

### `src/api/authApi.ts`

```typescript
import client from "./client"
import type { IAuthResponse } from "../types/api"

export const authApi = {
  login: async (email: string, password: string): Promise<IAuthResponse> => {
    const res = await client.post<IAuthResponse>("/auth/login", { email, password })
    return res.data
  },

  register: async (email: string, password: string): Promise<IAuthResponse> => {
    const res = await client.post<IAuthResponse>("/auth/register", { email, password })
    return res.data
  },
}
```

### `src/api/devicesApi.ts`

```typescript
import client from "./client"
import type { IDataResponse } from "../types/api"
import type { IDevice } from "../types/device"

export const devicesApi = {
  getAll: async (): Promise<IDevice[]> => {
    const res = await client.get<IDataResponse<IDevice[]>>("/devices")
    return res.data.data
  },

  getById: async (id: number): Promise<IDevice> => {
    const res = await client.get<IDataResponse<IDevice>>(`/devices/${id}`)
    return res.data.data
  },

  claim: async (id: number): Promise<IDevice> => {
    const res = await client.post<IDataResponse<IDevice>>(`/devices/${id}/claim`)
    return res.data.data
  },

  release: async (id: number): Promise<IDevice> => {
    const res = await client.post<IDataResponse<IDevice>>(`/devices/${id}/release`)
    return res.data.data
  },
}
```

### `src/api/jobsApi.ts`

```typescript
import client from "./client"
import type { IDataResponse } from "../types/api"
import type { IJob } from "../types/job"

export const jobsApi = {
  getAll: async (): Promise<IJob[]> => {
    const res = await client.get<IDataResponse<IJob[]>>("/jobs")
    return res.data.data
  },

  getById: async (id: number): Promise<IJob> => {
    const res = await client.get<IDataResponse<IJob>>(`/jobs/${id}`)
    return res.data.data
  },

  submitText: async (payload: FormData): Promise<IJob> => {
    const res = await client.post<IDataResponse<IJob>>("/jobs", payload, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    return res.data.data
  },
}
```

---

## 7. AuthContext (`src/context/AuthContext.tsx`)

The `AuthContext` is the single source of truth for authentication state. It initializes on app start by checking SecureStore for a persisted token.

```typescript
interface AuthContextType {
  user: IUser | null
  token: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}
```

### Implementation Pattern

```typescript
import React, { createContext, useContext, useEffect, useState } from "react"
import * as SecureStore from "expo-secure-store"
import { authApi } from "../api/authApi"
import { TOKEN_KEY } from "../api/client"
import type { IUser } from "../types/user"

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<IUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // On mount: restore session from SecureStore
  useEffect(() => {
    const restoreSession = async () => {
      try {
        const storedToken = await SecureStore.getItemAsync(TOKEN_KEY)
        if (storedToken) {
          setToken(storedToken)
          // Optionally fetch /auth/me to validate token and get fresh user data
          // const currentUser = await authApi.me()
          // setUser(currentUser)
        }
      } catch {
        // Token invalid or SecureStore unavailable — clear state
        await SecureStore.deleteItemAsync(TOKEN_KEY)
      } finally {
        setIsLoading(false)
      }
    }
    restoreSession()
  }, [])

  const login = async (email: string, password: string) => {
    const res = await authApi.login(email, password)
    await SecureStore.setItemAsync(TOKEN_KEY, res.access_token)
    setToken(res.access_token)
    setUser(res.user)
  }

  const register = async (email: string, password: string) => {
    const res = await authApi.register(email, password)
    await SecureStore.setItemAsync(TOKEN_KEY, res.access_token)
    setToken(res.access_token)
    setUser(res.user)
  }

  const logout = async () => {
    await SecureStore.deleteItemAsync(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider")
  return ctx
}
```

**Rules:**
- Token is ALWAYS stored in Expo SecureStore with key `"openclaw_token"` — never AsyncStorage
- `isLoading: true` during session restore prevents the navigator from flickering between Auth and App screens
- `logout()` clears both SecureStore and in-memory state
- The Axios response interceptor (401 handling) pairs with this context — deleting the token from SecureStore triggers a re-render via the `token` state

---

## 8. React Query Conventions

### QueryClient Setup (in `App.tsx`)

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,       // 30 seconds
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
```

### Query Hook Pattern (`src/hooks/`)

```typescript
// src/hooks/useDevices.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { devicesApi } from "../api/devicesApi"

// List query with polling
export function useDevices() {
  return useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.getAll,
    refetchInterval: 10_000,   // Poll every 10s for live marketplace status
  })
}

// Single item query
export function useDevice(id: number) {
  return useQuery({
    queryKey: ["devices", id],
    queryFn: () => devicesApi.getById(id),
    enabled: !!id,
  })
}

// Mutation with cache invalidation
export function useClaimDevice() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: devicesApi.claim,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["devices"] })
    },
  })
}
```

```typescript
// src/hooks/useJobs.ts
export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: jobsApi.getAll,
    refetchInterval: 5_000,    // Poll every 5s for kanban status updates
  })
}

export function useSubmitJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: jobsApi.submitText,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
  })
}
```

### Query Key Conventions

| Key | Usage |
|---|---|
| `["devices"]` | All devices list |
| `["devices", id]` | Single device |
| `["jobs"]` | All jobs (kanban + history) |
| `["jobs", id]` | Single job |

### Polling Intervals

| Feature | Interval | Reason |
|---|---|---|
| Marketplace devices | 10,000ms | Device status changes infrequently |
| Kanban jobs | 5,000ms | Job status changes frequently during processing |

**Rules:**
- NEVER use `useState` + `useEffect` for API data fetching — always use React Query
- All query hooks live in `src/hooks/` — never inline `useQuery` directly in a screen
- Mutations ALWAYS invalidate the relevant query key `onSuccess`
- Use `enabled: false` to prevent a query from running until required data is available

---

## 9. Form Conventions (React Hook Form + Zod)

### Zod Schema (in `src/utils/validators/`)

Define the schema and infer the form type in the validator file:

```typescript
// src/utils/validators/auth.ts
import { z } from "zod"

export const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
})

export const registerSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
})

export type LoginFormData = z.infer<typeof loginSchema>
export type RegisterFormData = z.infer<typeof registerSchema>
```

```typescript
// src/utils/validators/job.ts
import { z } from "zod"

export const submitJobSchema = z.object({
  title: z.string().min(1, "Title is required").max(100),
  prompt: z.string().min(1, "Prompt is required"),
  device_id: z.number({ required_error: "Please select a device" }),
  job_type: z.enum(["text", "file"]),
})

export type SubmitJobFormData = z.infer<typeof submitJobSchema>
```

### Form Component Pattern

```typescript
import { useForm, Controller } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { loginSchema, type LoginFormData } from "../../utils/validators/auth"

const LoginScreen: React.FC = () => {
  const { login } = useAuth()

  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  })

  const onSubmit = async (data: LoginFormData) => {
    try {
      await login(data.email, data.password)
    } catch (err: any) {
      // Map API errors to form fields
      setError("email", { message: err.response?.data?.detail ?? "Login failed" })
    }
  }

  return (
    <View className="flex-1 p-6">
      <Controller
        control={control}
        name="email"
        render={({ field: { onChange, onBlur, value } }) => (
          <Input
            label="Email"
            onChangeText={onChange}
            onBlur={onBlur}
            value={value}
            error={errors.email?.message}
            keyboardType="email-address"
            autoCapitalize="none"
          />
        )}
      />
      <Button
        title="Login"
        onPress={handleSubmit(onSubmit)}
        disabled={isSubmitting}
        loading={isSubmitting}
      />
    </View>
  )
}
```

**Rules:**
- ALL forms use `react-hook-form` with `zodResolver` — no manual validation
- Zod schemas are defined in `src/utils/validators/` — never inline in components
- Always show inline error messages below each field using `errors.fieldName?.message`
- The submit button is ALWAYS disabled while `isSubmitting` is true
- API errors are mapped to form fields using `setError` — never use separate error state

---

## 10. Navigation Structure

### Type Definitions (`src/navigation/types.ts`)

```typescript
import type { NativeStackNavigationProp } from "@react-navigation/native-stack"
import type { BottomTabNavigationProp } from "@react-navigation/bottom-tabs"

// Auth stack
export type AuthStackParamList = {
  Login: undefined
  Register: undefined
}

// App bottom tabs
export type AppTabParamList = {
  Marketplace: undefined
  SubmitJob: undefined
  Kanban: undefined
}

// Convenience navigation prop types
export type AuthNavigationProp = NativeStackNavigationProp<AuthStackParamList>
export type AppTabNavigationProp = BottomTabNavigationProp<AppTabParamList>
```

### Root Navigator (`src/navigation/AppNavigator.tsx`)

```typescript
import { NavigationContainer } from "@react-navigation/native"
import { createNativeStackNavigator } from "@react-navigation/native-stack"
import { useAuth } from "../context/AuthContext"
import AuthNavigator from "./AuthNavigator"
import AppTabNavigator from "./AppTabNavigator"
import LoadingSpinner from "../components/common/LoadingSpinner"

const Stack = createNativeStackNavigator()

const AppNavigator: React.FC = () => {
  const { token, isLoading } = useAuth()

  if (isLoading) {
    return <LoadingSpinner fullScreen />
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {token ? (
          <Stack.Screen name="App" component={AppTabNavigator} />
        ) : (
          <Stack.Screen name="Auth" component={AuthNavigator} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  )
}
```

### Auth Stack (`src/navigation/AuthNavigator.tsx`)

```typescript
import { createNativeStackNavigator } from "@react-navigation/native-stack"
import type { AuthStackParamList } from "./types"
import LoginScreen from "../screens/auth/LoginScreen"
import RegisterScreen from "../screens/auth/RegisterScreen"

const Stack = createNativeStackNavigator<AuthStackParamList>()

const AuthNavigator: React.FC = () => (
  <Stack.Navigator initialRouteName="Login">
    <Stack.Screen name="Login" component={LoginScreen} options={{ title: "Sign In" }} />
    <Stack.Screen name="Register" component={RegisterScreen} options={{ title: "Create Account" }} />
  </Stack.Navigator>
)
```

### App Tabs (`src/navigation/AppTabNavigator.tsx`)

```typescript
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs"
import { MaterialIcons } from "@expo/vector-icons"
import type { AppTabParamList } from "./types"
import MarketplaceScreen from "../screens/marketplace/MarketplaceScreen"
import SubmitJobScreen from "../screens/jobs/SubmitJobScreen"
import KanbanScreen from "../screens/kanban/KanbanScreen"

const Tab = createBottomTabNavigator<AppTabParamList>()

const AppTabNavigator: React.FC = () => (
  <Tab.Navigator
    screenOptions={{
      tabBarActiveTintColor: "#6366f1",
      tabBarInactiveTintColor: "#94a3b8",
      headerShown: true,
    }}
  >
    <Tab.Screen
      name="Marketplace"
      component={MarketplaceScreen}
      options={{
        tabBarIcon: ({ color }) => <MaterialIcons name="storefront" color={color} size={24} />,
      }}
    />
    <Tab.Screen
      name="SubmitJob"
      component={SubmitJobScreen}
      options={{
        title: "Submit Job",
        tabBarIcon: ({ color }) => <MaterialIcons name="add-circle-outline" color={color} size={24} />,
      }}
    />
    <Tab.Screen
      name="Kanban"
      component={KanbanScreen}
      options={{
        tabBarIcon: ({ color }) => <MaterialIcons name="view-kanban" color={color} size={24} />,
      }}
    />
  </Tab.Navigator>
)
```

**Navigation Tree:**
```
AppNavigator (NavigationContainer)
├── AuthNavigator (if !token) — NativeStack
│   ├── LoginScreen
│   └── RegisterScreen
└── AppTabNavigator (if token) — BottomTabs
    ├── MarketplaceScreen
    ├── SubmitJobScreen
    └── KanbanScreen
```

---

## 11. Styling Conventions (NativeWind v4)

### Setup (`tailwind.config.js`)

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./App.{js,jsx,ts,tsx}", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#6366f1",     // Indigo
        success: "#22c55e",     // Green
        danger:  "#ef4444",     // Red
        warning: "#f59e0b",     // Amber
        "bg-dark":  "#0f172a",  // Dark background
        "bg-light": "#f8fafc",  // Light background
      },
    },
  },
  plugins: [],
}
```

### Color Palette Reference

| Token | Hex | Usage |
|---|---|---|
| `primary` | `#6366f1` | Buttons, active tabs, links |
| `success` | `#22c55e` | Online status, success toasts |
| `danger` | `#ef4444` | Offline status, error toasts, destructive actions |
| `warning` | `#f59e0b` | Busy status, warning toasts |
| `bg-dark` | `#0f172a` | Dark mode background |
| `bg-light` | `#f8fafc` | Light mode background |

### Component Class Patterns

```tsx
// Card
<View className="bg-white rounded-xl p-4 shadow-sm border border-gray-100">

// Primary button
<TouchableOpacity className="bg-indigo-500 rounded-lg px-4 py-3 items-center">
  <Text className="text-white font-semibold text-base">Action</Text>
</TouchableOpacity>

// Secondary outlined button
<TouchableOpacity className="border border-indigo-500 rounded-lg px-4 py-3 items-center">
  <Text className="text-indigo-500 font-semibold text-base">Action</Text>
</TouchableOpacity>

// Danger button
<TouchableOpacity className="bg-red-500 rounded-lg px-4 py-3 items-center">
  <Text className="text-white font-semibold text-base">Delete</Text>
</TouchableOpacity>
```

### Status Badge (`src/components/common/Badge.tsx`)

```tsx
const STATUS_STYLES: Record<DeviceStatus, string> = {
  online:  "bg-green-100 text-green-700",
  offline: "bg-red-100 text-red-700",
  busy:    "bg-yellow-100 text-yellow-700",
}

const JOB_STATUS_STYLES: Record<JobStatus, string> = {
  todo:        "bg-gray-100 text-gray-600",
  in_progress: "bg-blue-100 text-blue-700",
  done:        "bg-green-100 text-green-700",
  failed:      "bg-red-100 text-red-700",
}

interface BadgeProps {
  label: string
  variant: string   // one of the status values
  styleMap: Record<string, string>
}

const Badge: React.FC<BadgeProps> = ({ label, variant, styleMap }) => (
  <View className={`px-2 py-0.5 rounded-full ${styleMap[variant] ?? "bg-gray-100 text-gray-600"}`}>
    <Text className="text-xs font-medium">{label}</Text>
  </View>
)
```

**Rules:**
- Use NativeWind `className` prop for ALL styling
- Use `StyleSheet.create` ONLY when NativeWind cannot handle a style (e.g., complex transforms, shadow on Android)
- Never mix NativeWind and inline `style` props on the same element
- Never hardcode hex colors inline — use Tailwind tokens

---

## 12. Screen Component Template

Every screen MUST follow this structure:

```tsx
import React from "react"
import { View, Text, FlatList, RefreshControl } from "react-native"
import { useNavigation } from "@react-navigation/native"
import { useAuth } from "../../context/AuthContext"
import { useDevices, useClaimDevice } from "../../hooks/useDevices"
import LoadingSpinner from "../../components/common/LoadingSpinner"
import DeviceCard from "../../components/DeviceCard"
import type { AppTabNavigationProp } from "../../navigation/types"

// 1. Imports
// 2. Types (if any local types needed)

// 3. Component function
const MarketplaceScreen: React.FC = () => {
  // a. Hooks — in this order: auth, navigation, query/mutation, form
  const { user } = useAuth()
  const navigation = useNavigation<AppTabNavigationProp>()
  const { data: devices, isLoading, error, refetch, isFetching } = useDevices()
  const claimDevice = useClaimDevice()

  // b. Derived state / computed values
  const availableDevices = devices?.filter((d) => d.status === "online") ?? []

  // c. Handlers
  const handleClaim = (deviceId: number) => {
    claimDevice.mutate(deviceId)
  }

  // d. Loading state
  if (isLoading) {
    return <LoadingSpinner fullScreen />
  }

  // e. Error state
  if (error) {
    return (
      <View className="flex-1 items-center justify-center p-6">
        <Text className="text-red-500 text-center">{(error as Error).message}</Text>
      </View>
    )
  }

  // f. Empty state
  if (availableDevices.length === 0) {
    return (
      <View className="flex-1 items-center justify-center p-6">
        <Text className="text-gray-500 text-center">No devices available right now.</Text>
      </View>
    )
  }

  // g. Main render
  return (
    <View className="flex-1 bg-gray-50">
      <FlatList
        data={availableDevices}
        keyExtractor={(item) => String(item.id)}
        contentContainerClassName="p-4 gap-3"
        refreshControl={
          <RefreshControl refreshing={isFetching} onRefresh={refetch} />
        }
        renderItem={({ item }) => (
          <DeviceCard
            device={item}
            onClaim={() => handleClaim(item.id)}
            isOwner={item.owner_id === user?.id}
          />
        )}
      />
    </View>
  )
}

export default MarketplaceScreen
```

**Screen Checklist:**
- [ ] Always render a loading state (`isLoading`)
- [ ] Always render an error state (`error`)
- [ ] Always render an empty state when list is empty
- [ ] Use `FlatList` for lists (never `ScrollView` + `.map()` for long lists)
- [ ] Add `RefreshControl` to allow pull-to-refresh
- [ ] Hooks are called unconditionally at the top — never inside conditionals

---

## 13. File Upload Pattern

Use `expo-document-picker` for arbitrary files and `expo-image-picker` for images. Always submit files as `FormData`.

```typescript
import * as DocumentPicker from "expo-document-picker"
import { useState } from "react"

interface SelectedFile {
  uri: string
  name: string
  mimeType: string
}

const SubmitJobScreen: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<SelectedFile | null>(null)
  const submitJob = useSubmitJob()

  const pickFile = async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: ["application/pdf", "text/plain", "image/*"],
      copyToCacheDirectory: true,
    })
    if (!result.canceled && result.assets?.[0]) {
      const asset = result.assets[0]
      setSelectedFile({
        uri: asset.uri,
        name: asset.name,
        mimeType: asset.mimeType ?? "application/octet-stream",
      })
    }
  }

  const onSubmit = async (data: SubmitJobFormData) => {
    const formData = new FormData()
    formData.append("title", data.title)
    formData.append("prompt", data.prompt)
    formData.append("device_id", String(data.device_id))
    formData.append("job_type", selectedFile ? "file" : "text")

    if (selectedFile) {
      // React Native requires this exact shape for FormData file entries
      formData.append("file", {
        uri: selectedFile.uri,
        type: selectedFile.mimeType,
        name: selectedFile.name,
      } as any)
    }

    await submitJob.mutateAsync(formData)
  }

  // ... render
}
```

**Rules:**
- Always set `copyToCacheDirectory: true` so the URI remains accessible after the picker closes
- The file entry in FormData uses `{ uri, type, name }` — the `as any` cast is required because React Native's FormData accepts this shape but TypeScript doesn't know about it
- The Axios client must override `Content-Type: multipart/form-data` for file uploads (handled in `jobsApi.ts`)
- Always check `result.canceled` before accessing `result.assets`

---

## 14. Environment Variables

All environment variables are prefixed with `EXPO_PUBLIC_` to be accessible in the managed Expo workflow.

### `.env.example`

```bash
# API base URL — no trailing slash
EXPO_PUBLIC_API_URL=http://localhost:8000
```

### Usage in Code

```typescript
// Correct — always use process.env
const API_URL = process.env.EXPO_PUBLIC_API_URL

// Wrong — never hardcode
const API_URL = "http://localhost:8000"
```

**Rules:**
- `.env` is gitignored — never commit it
- `.env.example` is committed and contains all required variable names with placeholder values
- Only `EXPO_PUBLIC_*` prefixed variables are accessible in the Expo managed workflow
- Variables are read at bundle time — restart the bundler after changing `.env`

---

## 15. Toast Notifications

All user feedback for async operations uses `react-native-toast-message`.

### App.tsx Setup

```tsx
import Toast from "react-native-toast-message"

const App: React.FC = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <AppNavigator />
      {/* Toast must be the LAST child so it renders above everything */}
      <Toast />
    </AuthProvider>
  </QueryClientProvider>
)
```

### Usage in Hooks / Screens

```typescript
import Toast from "react-native-toast-message"

// Success
Toast.show({
  type: "success",
  text1: "Device claimed successfully",
})

// Error
Toast.show({
  type: "error",
  text1: "Failed to claim device",
  text2: error.message,
})

// Info
Toast.show({
  type: "info",
  text1: "Job submitted",
  text2: "Check the Kanban board for status updates",
})
```

### Mutation Pattern with Toast

```typescript
export function useClaimDevice() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: devicesApi.claim,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["devices"] })
      Toast.show({ type: "success", text1: "Device claimed!" })
    },
    onError: (error: any) => {
      Toast.show({
        type: "error",
        text1: "Could not claim device",
        text2: error.response?.data?.detail ?? error.message,
      })
    },
  })
}
```

**Rules:**
- `<Toast />` is always placed at the root in `App.tsx` as the last child
- Use `onSuccess` / `onError` in mutation hooks for toasts — not inside screen handlers
- Always include `text2` for error toasts to surface the backend error message
- Never use `Alert.alert` for routine async feedback — reserve it for destructive confirmations only

---

## 16. Testing Conventions

### Setup

Test files live at `src/__tests__/{ComponentOrHook}.test.tsx`. Every test wraps the component in both `QueryClientProvider` and `AuthProvider`.

```typescript
// src/__tests__/setup.ts
import "@testing-library/react-native/extend-expect"

// src/__tests__/utils/renderWithProviders.tsx
import React from "react"
import { render } from "@testing-library/react-native"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AuthProvider } from "../../context/AuthContext"

export function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{ui}</AuthProvider>
    </QueryClientProvider>
  )
}
```

### Component Test Pattern

```typescript
// src/__tests__/DeviceCard.test.tsx
import React from "react"
import { fireEvent, screen } from "@testing-library/react-native"
import { renderWithProviders } from "./utils/renderWithProviders"
import DeviceCard from "../components/DeviceCard"
import type { IDevice } from "../types/device"

const mockDevice: IDevice = {
  id: 1,
  name: "GPU Node A",
  ai_model: "llama3",
  status: "online",
  owner_id: 42,
  created_at: "2024-01-01T00:00:00Z",
}

describe("DeviceCard", () => {
  it("renders device name and status", () => {
    renderWithProviders(<DeviceCard device={mockDevice} onClaim={jest.fn()} isOwner={false} />)
    expect(screen.getByText("GPU Node A")).toBeTruthy()
    expect(screen.getByText("online")).toBeTruthy()
  })

  it("calls onClaim when Claim button is pressed", () => {
    const onClaim = jest.fn()
    renderWithProviders(<DeviceCard device={mockDevice} onClaim={onClaim} isOwner={false} />)
    fireEvent.press(screen.getByText("Claim"))
    expect(onClaim).toHaveBeenCalledTimes(1)
  })

  it("does not show Claim button for owner", () => {
    renderWithProviders(<DeviceCard device={mockDevice} onClaim={jest.fn()} isOwner={true} />)
    expect(screen.queryByText("Claim")).toBeNull()
  })
})
```

### Axios Mocking

```typescript
// At the top of any test file that makes API calls
jest.mock("../api/client", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  },
}))
```

### Test Types

| Type | What to Test |
|---|---|
| Snapshot | Component renders correctly given props |
| Behavior | User interactions (press, input) trigger correct handlers |
| Loading state | Shows spinner while query is loading |
| Error state | Shows error message when query fails |
| Empty state | Shows empty state when list is empty |
| Form validation | Shows inline errors for invalid inputs |

---

## 17. App Entry Point (`App.tsx`)

```tsx
import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import Toast from "react-native-toast-message"
import { AuthProvider } from "./src/context/AuthContext"
import AppNavigator from "./src/navigation/AppNavigator"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppNavigator />
        <Toast />
      </AuthProvider>
    </QueryClientProvider>
  )
}
```

**Provider Order (outermost to innermost):**
1. `QueryClientProvider` — wraps everything so all hooks can access the query cache
2. `AuthProvider` — wraps navigation so auth state is available in all screens
3. `AppNavigator` — inside providers so navigators can read context
4. `<Toast />` — last element so it renders above the navigation stack

---

## 18. Key Rules — Do NOT Violate

| Rule | Rationale |
|---|---|
| Never use `useState` + `useEffect` for API data | React Query handles caching, dedup, polling, and error states correctly |
| Never store the JWT in AsyncStorage | Expo SecureStore is encrypted; AsyncStorage is plaintext |
| Never hardcode API URLs | Use `EXPO_PUBLIC_API_URL` from environment |
| Never use inline `style` when a NativeWind class can handle it | Inconsistent styling and harder to maintain |
| Never skip Zod validation on forms | All user input must be validated before submission |
| Never use class components | Functional components + hooks only |
| Never use the `any` type | Type every variable, parameter, and return value explicitly |
| Always handle loading, error, and empty states | Screens without these states cause poor UX and crashes |
| Never inline `useQuery` directly in a screen | All query logic belongs in `src/hooks/` |
| Never chain navigation without typed params | Always use the typed param lists from `src/navigation/types.ts` |
