import api from '@services/api'
import type { PredictPayload, PredictResponse } from '@types/prediction'

export const predict = (payload: PredictPayload) => api.post<PredictResponse>('/predict', payload)
