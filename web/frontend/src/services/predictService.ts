import api from '@services/api'
import type { PredictPayload, PredictProbabilities, PredictResponse } from '@/types/prediction'

interface ApiPredictResponse {
  prediction: string
  confidence?: number | null
  probabilities?: Record<string, number>
  model?: string
  history_saved?: boolean
  category?: string
  category_icon?: string
  prediction_id?: string
}

export const predict = async (payload: PredictPayload) => {
  const response = await api.post<ApiPredictResponse>('/predict', payload)
  const confidence = typeof response.data.confidence === 'number' ? response.data.confidence : 0
  const normalized: PredictResponse = {
    label: response.data.prediction,
    score: confidence,
    probabilities: response.data.probabilities as PredictProbabilities | undefined,
    model: response.data.model,
    text: payload.text,
    historySaved: response.data.history_saved,
    category: response.data.category,
    category_icon: response.data.category_icon,
    predictionId: response.data.prediction_id,
  }

  return {
    ...response,
    data: normalized,
  }
}

export interface DocumentExtract {
  filename: string
  file_type: string
  word_count: number
  char_count: number
  paragraph_count: number
  text: string
}

/** Upload a Word or PDF file and get its Somali text back for classification.
 *  The server rejects anything that is not genuinely .docx/.pdf, and anything whose
 *  text does not read as Somali, so the caller only ever receives usable input. */
export const extractDocument = (file: File) => {
  const body = new FormData()
  body.append('file', file)
  return api.post<DocumentExtract>('/extract-document', body, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const publishPrediction = (id: string, title?: string) =>
  api.patch<{ id: string; title: string; author_name: string | null; published_at: string }>(
    `/predict/${id}/publish`,
    { title: title || null },
  )

export const unpublishPrediction = (id: string) =>
  api.delete<{ id: string; is_published: boolean }>(`/predict/${id}/publish`)

export interface NewsFeedItem {
  id: string
  title: string
  text: string
  prediction: string
  confidence: number | null
  category: string | null
  category_icon: string | null
  model: string | null
  user_id: string | null
  author_name: string | null
  created_at: string | null
  published_at: string | null
}

export const getNewsFeed = (limit = 30, category = '') =>
  api.get<{ items: NewsFeedItem[] }>(`/predict/feed?limit=${limit}${category ? `&category=${encodeURIComponent(category)}` : ''}`)

/* ── Link analysis ──────────────────────────────────────────────────────────
   Fetches an article by URL rather than taking pasted text, and returns both
   the whole-article verdict and the paragraph-level proportion.            */
export interface LinkSegment {
  index: number
  words: number
  text: string
  /** null when the paragraph was too short to score. */
  verdict: string | null
  scored: boolean
  /** null when skipped, or when this model has no measured accuracy table. */
  confidence: number | null
}

export interface LinkAnalysisResult {
  url: string
  title?: string | null
  word_count: number
  prediction: string
  confidence?: number | null
  probabilities: Record<string, number>
  model: string
  category?: string | null
  category_icon?: string | null
  ai_percent: number
  human_percent: number
  ai_percent_by_words: number
  paragraphs_scored: number
  paragraphs_skipped: number
  ai_paragraphs: number
  human_paragraphs: number
  mean_paragraph_confidence: number | null
  segments: LinkSegment[]
  accuracy_measured: boolean
  // Set when the article was too short to split into paragraphs, so the proportion
  // restates the single verdict instead of counting paragraphs against each other.
  short_article: boolean
  accuracy_note: string
}

export const analyzeLink = async (url: string, model?: string) => {
  const response = await api.post<LinkAnalysisResult>('/analyze-link', { url, model })
  return response.data
}
