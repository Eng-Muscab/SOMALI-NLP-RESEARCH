import api from './api'

export interface OverviewData {
  scope: 'platform' | 'personal'
  total_predictions: number
  ai_predictions: number
  human_predictions: number
  ai_detection_rate: number
  human_detection_rate: number
  total_users: number | null
  active_users: number | null
  today_predictions: number
  month_predictions: number
  avg_confidence: number
  top_models: { model: string; count: number }[]
}

export interface DailyPrediction {
  date: string
  total: number
  ai: number
  human: number
}

export interface UserSignup {
  date: string
  signups: number
}

export interface TrendsData {
  scope: 'platform' | 'personal'
  daily_predictions: DailyPrediction[]
  user_signups: UserSignup[]
  days: number
  granularity: 'day' | 'month' | 'year'
}

export interface CategoryBreakdown {
  category: string
  total: number
  ai: number
  human: number
  avg_confidence: number
}

export interface UserUsage {
  email: string
  total: number
  ai: number
  human: number
  last_used: string | null
}

export const getAnalyticsOverview = () =>
  api.get<OverviewData>('/analytics/overview')

export const getAnalyticsTrends = (days = 30, granularity: 'day' | 'month' | 'year' = 'day') =>
  api.get<TrendsData>(`/analytics/trends?days=${days}&granularity=${granularity}`)

export const getAnalyticsByCategory = (days = 30) =>
  api.get<{ categories: CategoryBreakdown[]; days: number; scope: 'platform' | 'personal' }>(`/analytics/by-category?days=${days}`)

export const getAnalyticsByUser = (days = 30, limit = 20) =>
  api.get<{ users: UserUsage[]; days: number }>(`/analytics/by-user?days=${days}&limit=${limit}`)
