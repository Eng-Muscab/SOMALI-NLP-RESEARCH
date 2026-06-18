import { useEffect, useMemo, useState } from 'react'
import { Activity, BarChart3, Brain, Layers, TrendingUp } from 'lucide-react'
import { Badge } from '../components/ui/Badge'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import api, { getApiErrorMessage } from '../services/api'
import { listExperiments } from '../services/experimentService'
import { getCategoryGroup } from '../utils/modelGroup'

interface ModelData {
  id: string
  name: string
  type: string
  experiment?: string
  experimentName?: string
  accuracy: number
  f1: number
  status: string
  path?: string
}

const formatNumber = (value: number, suffix = '') => {
  if (!Number.isFinite(value)) return 'N/A'
  return `${value.toFixed(value >= 10 ? 2 : 3)}${suffix}`
}

const Dashboard = () => {
  const [models, setModels] = useState<ModelData[]>([])
  const [experimentCount, setExperimentCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchDashboard = async () => {
      setLoading(true)
      setError(null)

      try {
        const [modelsResult, experimentsResult] = await Promise.allSettled([
          api.get<ModelData[]>('/models'),
          listExperiments(),
        ])

        if (modelsResult.status === 'rejected') {
          throw modelsResult.reason
        }

        setModels(Array.isArray(modelsResult.value.data) ? modelsResult.value.data : [])
        setExperimentCount(experimentsResult.status === 'fulfilled' ? experimentsResult.value.data.length : 0)

        if (experimentsResult.status === 'rejected') {
          console.error('Failed to load experiments', experimentsResult.reason)
        }
      } catch (error) {
        setError(getApiErrorMessage(error, 'Unable to load dashboard data from the backend.'))
      } finally {
        setLoading(false)
      }
    }

    fetchDashboard()
  }, [])

  const sortedModels = useMemo(
    () => [...models].sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0)),
    [models]
  )

  const bestModel = sortedModels[0]
  const averageF1 = models.length
    ? models.reduce((total, model) => total + Number(model.f1 || 0), 0) / models.length
    : 0

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-extrabold tracking-tight text-neutral-900 dark:text-white">Dashboard</h1>
        <p className="mt-2 text-neutral-500 dark:text-neutral-400 font-medium">
          Quick status overview and available NLP classification models.
        </p>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50 text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
          <CardContent className="p-4">{error}</CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <Card className="hover:-translate-y-0.5 hover:shadow-md transition-all duration-300">
          <CardContent className="flex items-center justify-between p-6">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-neutral-450 dark:text-neutral-400 uppercase tracking-wider">Backend Status</p>
              <p className="text-2xl font-bold text-neutral-900 dark:text-white">
                {error ? 'Check API' : 'Connected'}
              </p>
            </div>
            <div className={`p-3.5 rounded-xl ${error ? 'bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400' : 'bg-accent-50 dark:bg-accent-500/10 text-accent-600 dark:text-accent-400'}`}>
              <Activity size={22} />
            </div>
          </CardContent>
        </Card>

        <Card className="hover:-translate-y-0.5 hover:shadow-md transition-all duration-300">
          <CardContent className="flex items-center justify-between p-6">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-neutral-450 dark:text-neutral-400 uppercase tracking-wider">Trained Models</p>
              <p className="text-2xl font-bold text-neutral-900 dark:text-white">{models.length}</p>
            </div>
            <div className="p-3.5 rounded-xl bg-primary-50 dark:bg-primary-500/10 text-primary-600 dark:text-primary-400">
              <Layers size={22} />
            </div>
          </CardContent>
        </Card>

        <Card className="hover:-translate-y-0.5 hover:shadow-md transition-all duration-300">
          <CardContent className="flex items-center justify-between p-6">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-neutral-450 dark:text-neutral-400 uppercase tracking-wider">Experiments</p>
              <p className="text-2xl font-bold text-neutral-900 dark:text-white">{experimentCount}</p>
            </div>
            <div className="p-3.5 rounded-xl bg-indigo-50 dark:bg-primary-500/10 text-primary-600 dark:text-primary-400">
              <Brain size={22} />
            </div>
          </CardContent>
        </Card>

        <Card className="hover:-translate-y-0.5 hover:shadow-md transition-all duration-300">
          <CardContent className="flex items-center justify-between p-6">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-neutral-450 dark:text-neutral-400 uppercase tracking-wider">Top Performance</p>
              <p className="text-2xl font-bold text-neutral-900 dark:text-white">
                {bestModel ? formatNumber(bestModel.accuracy, '%') : 'N/A'}
              </p>
            </div>
            <div className="p-3.5 rounded-xl bg-accent-50 dark:bg-accent-500/10 text-accent-600 dark:text-accent-400">
              <TrendingUp size={22} />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">Loaded from environment</p>
                <h2 className="mt-1 text-xl font-bold text-neutral-900 dark:text-white">Model Comparison</h2>
              </div>
              <Badge variant="primary">{models.length} models</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3.5">
                <Skeleton className="h-14 rounded-2xl" />
                <Skeleton className="h-14 rounded-2xl" />
                <Skeleton className="h-14 rounded-2xl" />
              </div>
            ) : models.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 p-10 text-center text-neutral-500 dark:bg-neutral-900/10">
                No trained models are available from the backend.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-neutral-150 text-neutral-500 dark:border-neutral-800/80 dark:text-neutral-400 font-semibold">
                      <th className="px-4 py-3.5 font-semibold text-xs uppercase tracking-wider">Model</th>
                      <th className="px-4 py-3.5 font-semibold text-xs uppercase tracking-wider">Category</th>
                      <th className="px-4 py-3.5 font-semibold text-xs uppercase tracking-wider">Type</th>
                      <th className="px-4 py-3.5 font-semibold text-xs uppercase tracking-wider">Accuracy</th>
                      <th className="px-4 py-3.5 font-semibold text-xs uppercase tracking-wider">F1</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800/40">
                    {sortedModels.map((model) => (
                      <tr key={model.id} className="hover:bg-neutral-50/50 dark:hover:bg-neutral-800/10">
                        <td className="px-4 py-4 font-bold text-neutral-900 dark:text-white">{model.name}</td>
                        <td className="px-4 py-4">
                          <Badge variant="neutral">{getCategoryGroup(model.type, model.path)}</Badge>
                        </td>
                        <td className="px-4 py-4 text-neutral-500 dark:text-neutral-400 font-medium uppercase text-xs">{model.type}</td>
                        <td className="px-4 py-4 font-bold text-neutral-900 dark:text-white">{formatNumber(model.accuracy, '%')}</td>
                        <td className="px-4 py-4 font-bold text-neutral-950 dark:text-neutral-200">{formatNumber(model.f1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary-600 dark:text-primary-400" />
              <h2 className="text-lg font-bold text-neutral-900 dark:text-white">Summary Insights</h2>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-2xl border border-neutral-100 dark:border-neutral-800/60 bg-neutral-50/50 p-5 dark:bg-neutral-900/30">
              <p className="text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">Best model</p>
              <p className="mt-2 font-bold text-neutral-900 dark:text-white text-base truncate" title={bestModel?.name}>{bestModel?.name || 'N/A'}</p>
            </div>
            <div className="rounded-2xl border border-neutral-100 dark:border-neutral-800/60 bg-neutral-50/50 p-5 dark:bg-neutral-900/30">
              <p className="text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">Average F1 Score</p>
              <p className="mt-2 font-bold text-neutral-900 dark:text-white text-2xl">{models.length ? formatNumber(averageF1) : 'N/A'}</p>
            </div>
            <div className="rounded-2xl border border-neutral-100 dark:border-neutral-800/60 bg-neutral-50/50 p-5 dark:bg-neutral-900/30">
              <p className="text-xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Prediction page</p>
              <p className="mt-2 text-xs leading-5 text-neutral-500 dark:text-neutral-400">
                Compare models across traditional, deep learning, and transformer categories in the Predict playground.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default Dashboard
