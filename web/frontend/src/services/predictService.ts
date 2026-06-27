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
  }

  return {
    ...response,
    data: normalized,
  }
}
