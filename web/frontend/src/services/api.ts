import axios, { AxiosError } from 'axios'
import { getToken, removeToken } from '@utils/token'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      removeToken()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const getApiErrorMessage = (error: unknown, fallback = 'Something went wrong. Please try again.') => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: unknown; message?: string }>
    const detail = axiosError.response?.data?.detail

    if (typeof detail === 'string') {
      return detail
    }

    if (Array.isArray(detail) && detail.length > 0) {
      return 'Please check the submitted values and try again.'
    }

    if (axiosError.response?.data?.message) {
      return axiosError.response.data.message
    }

    if (axiosError.message === 'Network Error') {
      return 'Unable to reach the API. Please make sure the backend is running.'
    }
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

export default api
