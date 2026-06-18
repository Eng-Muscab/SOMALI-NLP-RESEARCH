import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Zap, TrendingUp, Activity, Cpu } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import api, { getApiErrorMessage } from '../services/api'
import { getCategoryGroup } from '../utils/modelGroup'

interface ModelData {
  id: string
  name: string
  type: string
  accuracy: number
  f1: number
  status: string
  experiment?: string
  experimentName?: string
  path?: string
}

const Models = () => {
  const [models, setModels] = useState<ModelData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchModels = async () => {
      setError(null)
      try {
        const response = await api.get<ModelData[]>('/models')
        const rawModels = Array.isArray(response.data) ? response.data : []

        // Deduplicate by model id — keep the one with the highest accuracy
        const uniqueMap = new Map<string, ModelData>()
        rawModels.forEach((m) => {
          const existing = uniqueMap.get(m.id)
          if (!existing || m.accuracy > existing.accuracy) {
            uniqueMap.set(m.id, m)
          }
        })
        setModels(Array.from(uniqueMap.values()))
      } catch (error) {
        console.error('Failed to fetch models', error)
        setError(getApiErrorMessage(error, 'Unable to load models from the backend.'))
      } finally {
        setLoading(false)
      }
    }
    fetchModels()
  }, [])

  const getIcon = (type: string) => {
    if (type.includes('keras') || type.includes('transformers') || type.includes('deep_learning')) return <Cpu size={22} />
    if (type.includes('SVM') || type.toLowerCase().includes('svc')) return <Zap size={22} />
    if (type.includes('Ensemble') || type.toLowerCase().includes('forest')) return <Activity size={22} />
    return <TrendingUp size={22} />
  }

  // Find the model with the best accuracy
  const bestModelId = models.length > 0 
    ? models.reduce((best, current) => (current.accuracy > best.accuracy ? current : best)).id 
    : null

  if (loading) {
    return <div className="p-8 text-neutral-500">Loading models...</div>
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-extrabold tracking-tight text-neutral-900 dark:text-white mb-2">Models</h1>
        <p className="text-neutral-550 dark:text-neutral-400 font-medium">Available pre-trained models dynamically discovered from your local environment</p>
      </div>

      {error && (
        <Card className="p-4 border-red-200 bg-red-50 text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </Card>
      )}

      {models.length === 0 ? (
        <Card className="p-8 text-center text-neutral-500">
          No trained models found. Please complete the model training phase first.
        </Card>
      ) : (
        <>
          {/* Models Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {models.map((model, idx) => {
              const recommended = model.id === bestModelId
              return (
                <motion.div
                  key={model.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.08 }}
                >
                  <Card 
                    hover
                    className={`h-full flex flex-col relative overflow-hidden group ${
                      recommended 
                        ? 'border-primary-500/40 dark:border-primary-500/20 shadow-[0_12px_40px_rgba(79,70,229,0.06)]' 
                        : ''
                    }`}
                  >
                    {/* Recommended Badge */}
                    {recommended && (
                      <div className="absolute top-0 right-0 bg-gradient-to-l from-primary-600 to-primary-500 text-white px-3 py-1 rounded-bl-xl text-2xs font-extrabold tracking-wider">
                        RECOMMENDED
                      </div>
                    )}

                    <CardHeader className={recommended ? 'pb-4 pt-6 border-b-neutral-100/50 dark:border-b-neutral-800/50' : 'border-b-neutral-100/50 dark:border-b-neutral-800/50'}>
                      <div className="flex items-center space-x-3.5">
                        <div className={`p-2.5 rounded-xl ${recommended ? 'bg-primary-50 dark:bg-primary-500/10 text-primary-600 dark:text-primary-400' : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400'}`}>
                          {getIcon(model.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-bold text-neutral-900 dark:text-white truncate text-base" title={model.name}>{model.name}</h3>
                          <p className="text-3xs text-neutral-450 dark:text-neutral-500 font-extrabold uppercase tracking-widest">{model.type}</p>
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent className="flex-1 space-y-5">
                      <div className="flex items-center justify-between">
                        <Badge variant={model.status === 'active' ? 'success' : 'neutral'}>
                          {model.status === 'active' ? 'Active' : 'Inactive'}
                        </Badge>
                        <Badge variant="primary">{getCategoryGroup(model.type, model.path)}</Badge>
                      </div>

                      {/* Experiment label */}
                      {model.experimentName && (
                        <div className="rounded-xl border border-neutral-100 bg-neutral-50/50 px-3 py-2 dark:border-neutral-800/40 dark:bg-neutral-900/20">
                          <p className="text-3xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Experiment</p>
                          <p className="mt-0.5 text-xs font-bold text-neutral-800 dark:text-neutral-200 truncate" title={model.experimentName}>{model.experimentName}</p>
                        </div>
                      )}

                      {/* Metrics */}
                      <div className="space-y-3.5">
                        <div>
                          <div className="flex justify-between mb-1.5 items-end">
                            <span className="text-2xs font-semibold text-neutral-450 dark:text-neutral-550 uppercase tracking-wide">Accuracy</span>
                            <span className="text-sm font-bold text-neutral-900 dark:text-white">{model.accuracy}%</span>
                          </div>
                          <div className="h-1.5 bg-neutral-100 dark:bg-neutral-800/80 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-primary-600 to-primary-450 rounded-full"
                              style={{ width: `${Math.min(model.accuracy, 100)}%` }}
                            />
                          </div>
                        </div>

                        <div>
                          <div className="flex justify-between mb-1.5 items-end">
                            <span className="text-2xs font-semibold text-neutral-455 dark:text-neutral-550 uppercase tracking-wide">F1 Score</span>
                            <span className="text-sm font-bold text-neutral-900 dark:text-white">{model.f1}</span>
                          </div>
                          <div className="h-1.5 bg-neutral-100 dark:bg-neutral-800/80 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-accent-600 to-accent-450 rounded-full"
                              style={{ width: `${Math.min(model.f1 * 100, 100)}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </CardContent>

                    {/* Actions */}
                    <div className="px-6 py-4 border-t border-neutral-100 dark:border-neutral-800/60 bg-neutral-50/30 dark:bg-neutral-900/10">
                      <Button
                        variant={model.status === 'active' ? 'primary' : 'secondary'}
                        size="sm"
                        className="w-full text-xs"
                      >
                        {model.status === 'active' ? 'Ready for Inference' : 'Reactivate'}
                      </Button>
                    </div>
                  </Card>
                </motion.div>
              )
            })}
          </div>

          {/* Model Comparison */}
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
            <Card>
              <CardHeader>
                <h3 className="text-lg font-bold text-neutral-900 dark:text-white">Model Comparison</h3>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-neutral-150 text-neutral-500 dark:border-neutral-800/80 dark:text-neutral-400 font-semibold">
                        <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">Model</th>
                        <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">Type</th>
                        <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">Accuracy</th>
                        <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">F1 Score</th>
                        <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">Category</th>
                        <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">Experiment</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800/40">
                      {models.map((model) => (
                        <tr
                          key={model.id}
                          className="hover:bg-neutral-50/50 dark:hover:bg-neutral-800/10"
                        >
                          <td className="py-3 px-4">
                            <span className="font-bold text-neutral-900 dark:text-white">{model.name}</span>
                          </td>
                          <td className="py-3 px-4 text-neutral-500 dark:text-neutral-400 font-medium uppercase text-xs">{model.type}</td>
                          <td className="py-3 px-4">
                            <span className="font-bold text-neutral-900 dark:text-white">{model.accuracy}%</span>
                          </td>
                          <td className="py-3 px-4">
                            <span className="font-bold text-neutral-900 dark:text-white">{model.f1}</span>
                          </td>
                          <td className="py-3 px-4">
                            <Badge variant="neutral">{getCategoryGroup(model.type, model.path)}</Badge>
                          </td>
                          <td className="py-3 px-4 text-xs font-medium text-neutral-600 dark:text-neutral-400">
                            {model.experimentName ?? '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </>
      )}
    </div>
  )
}

export default Models
