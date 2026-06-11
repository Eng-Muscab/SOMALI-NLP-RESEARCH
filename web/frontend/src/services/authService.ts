import api from '@services/api'
import type { LoginCredentials, RegisterPayload } from '@types/auth'

export const login = (payload: LoginCredentials) => api.post('/auth/login', payload)
export const register = (payload: RegisterPayload) => api.post('/auth/register', payload)
