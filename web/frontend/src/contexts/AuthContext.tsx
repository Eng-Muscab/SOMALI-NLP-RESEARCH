import React, { createContext, useContext, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login as loginRequest, register as registerRequest } from '@services/authService'
import { getToken, parseJwt, removeToken, setToken } from '@utils/token'
import type { AuthContextValue, LoginCredentials, RegisterPayload, User } from '@types/auth'

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

const buildUserFromToken = (token: string): User | null => {
  const payload = parseJwt(token)

  if (!payload) {
    return null
  }

  return {
    id: payload.sub ?? payload.user?.id,
    email: payload.email ?? payload.user?.email,
    name: payload.name ?? payload.user?.name,
  }
}

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = getToken()

    if (token) {
      const currentUser = buildUserFromToken(token)
      if (currentUser) {
        setUser(currentUser)
        setIsAuthenticated(true)
      }
    }

    setIsLoading(false)
  }, [])

  const login = async (credentials: LoginCredentials) => {
    const response = await loginRequest(credentials)
    const token = response.data.access_token ?? response.data.token ?? response.data.accessToken

    if (!token || typeof token !== 'string') {
      throw new Error('Authentication response did not include a token.')
    }

    setToken(token)
    const currentUser = buildUserFromToken(token)
    setUser(currentUser)
    setIsAuthenticated(true)
  }

  const register = async (payload: RegisterPayload) => {
    await registerRequest(payload)
  }

  const logout = () => {
    removeToken()
    setUser(null)
    setIsAuthenticated(false)
    navigate('/login', { replace: true })
  }

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuthContext = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuthContext must be used within AuthProvider')
  }
  return context
}
