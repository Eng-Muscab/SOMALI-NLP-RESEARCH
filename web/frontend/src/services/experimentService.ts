import api from './api'
import type { Experiment } from '../types/experiment'

export const listExperiments = () => api.get<Experiment[]>('/experiments')
export const getExperimentById = (id: string) => api.get<Experiment>(`/experiments/${id}`)
