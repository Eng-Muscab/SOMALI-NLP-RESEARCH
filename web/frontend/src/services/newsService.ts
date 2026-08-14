import api from '@services/api'

export interface ExternalNewsSource {
  id: string
  name: string
}

export interface ExternalNewsItem {
  title: string
  link: string
  description: string
  published_at: string | null
  thumbnail: string | null
  source_name: string
}

export interface ExternalNewsResponse {
  source: string
  name: string
  site_url: string
  fetched_at: string | null
  error: string | null
  items: ExternalNewsItem[]
}

export const getExternalSources = () =>
  api.get<ExternalNewsSource[]>('/news/sources')

export const getExternalNews = (sourceId: string, limit = 20, force = false) =>
  api.get<ExternalNewsResponse>(
    `/news/external?source=${encodeURIComponent(sourceId)}&limit=${limit}${force ? '&force=true' : ''}`
  )
