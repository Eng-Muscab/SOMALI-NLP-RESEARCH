import React, { createContext, useContext, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCurrentUser, login as loginRequest, register as registerRequest } from '@services/authService'
import { getToken, removeToken, setToken } from '@utils/token'
import type { AuthContextValue, LoginCredentials, RegisterPayload, User } from '@/types/auth'

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let isMounted = true

    const restoreSession = async () => {
      const token = getToken()

      if (!token) {
        if (isMounted) {
          setIsLoading(false)
        }
        return
      }

      try {
        const response = await getCurrentUser()
        if (isMounted) {
          setUser(response.data)
          setIsAuthenticated(true)
        }
      } catch {
        removeToken()
        if (isMounted) {
          setUser(null)
          setIsAuthenticated(false)
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    restoreSession()

    return () => {
      isMounted = false
    }
  }, [])

  const login = async (credentials: LoginCredentials) => {
    const response = await loginRequest(credentials)
    const token = response.data.access_token ?? response.data.token ?? response.data.accessToken

    if (!token || typeof token !== 'string') {
      throw new Error('Authentication response did not include a token.')
    }

    setToken(token)

    // Prefer inline user from login response (has role), fallback to /me
    const inlineUser = response.data.user
    if (inlineUser && inlineUser.email) {
      setUser(inlineUser)
      setIsAuthenticated(true)
    } else {
      const currentUser = await getCurrentUser()
      setUser(currentUser.data)
      setIsAuthenticated(true)
    }
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
