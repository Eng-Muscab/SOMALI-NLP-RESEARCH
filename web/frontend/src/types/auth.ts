export type UserRole = 'super_admin' | 'admin' | 'analyst' | 'researcher' | 'viewer'

export interface User {
  id?: string
  email: string
  name?: string
  role?: UserRole
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterPayload {
  name: string
  email: string
  password: string
}

export interface AuthContextValue {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (credentials: LoginCredentials) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => void
}

export const isAdmin = (user: User | null) =>
  user?.role === 'super_admin' || user?.role === 'admin'

export const isSuperAdmin = (user: User | null) =>
  user?.role === 'super_admin'
