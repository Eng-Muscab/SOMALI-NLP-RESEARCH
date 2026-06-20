import { useEffect, useMemo, useState } from 'react'
import { Activity, Brain, Layers, Target, TrendingUp } from 'lucide-react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { DashboardHero } from '../components/dashboard/DashboardHero'
import { ExperimentOverview } from '../components/dashboard/ExperimentOverview'
import { ModelLeaderboard } from '../components/dashboard/ModelLeaderboard'
import { PerformanceCharts } from '../components/dashboard/PerformanceCharts'
import { PipelineStatus } from '../components/dashboard/PipelineStatus'
import { StatCard } from '../components/dashboard/StatCard'
import api, { getApiErrorMessage } from '../services/api'
import { listExperiments } from '../services/experimentService'
import type { Experiment } from '../types/experiment'

interface ModelData {
  id: string
  name: string
  type: string
  experiment?: string
  experimentName?: string
  accuracy: number
  precision: number
  recall: number
  f1: number
  status: string
  path?: string
}

const CHART_PALETTE = ['#6366f1', '#818cf8', '#14b8a6', '#2dd4bf', '#8b5cf6', '#a78bfa', '#f59e0b', '#10b981']

const shortModelName = (name: string) =>
  name.replace(/_TFIDF$/i, '').replace(/_/g, ' ').slice(0, 18)

const dedupeModels = (models: ModelData[]) => {
  const map = new Map<string, ModelData>()
  models.forEach((model) => {
    const key = model.name.toLowerCase()
    const existing = map.get(key)
    if (!existing || model.accuracy > existing.accuracy) {
      map.set(key, model)
    }
  })
  return Array.from(map.values())
}

const Dashboard = () => {
  const [models, setModels] = useState<ModelData[]>([])
  const [experiments, setExperiments] = useState<Experiment[]>([])
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
        if (modelsResult.status === 'rejected') throw modelsResult.reason
        setModels(Array.isArray(modelsResult.value.data) ? modelsResult.value.data : [])
        setExperiments(experimentsResult.status === 'fulfilled' ? experimentsResult.value.data : [])
      } catch (err) {
        setError(getApiErrorMessage(err, 'Unable to load dashboard data from the backend.'))
      } finally {
        setLoading(false)
      }
    }
    fetchDashboard()
  }, [])

  const uniqueModels = useMemo(() => dedupeModels(models), [models])
  const sortedModels = useMemo(
    () => [...uniqueModels].sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0)),
    [uniqueModels],
  )

  const bestModel = sortedModels[0]
  const averageF1 = uniqueModels.length
    ? uniqueModels.reduce((t, m) => t + Number(m.f1 || 0), 0) / uniqueModels.length
    : 0
  const averageAccuracy = uniqueModels.length
    ? uniqueModels.reduce((t, m) => t + Number(m.accuracy || 0), 0) / uniqueModels.length
    : 0

  const chartModels = useMemo(
    () =>
      sortedModels.map((model, index) => ({
        name: model.name,
        shortName: shortModelName(model.name),
        accuracy: model.accuracy,
        f1: model.f1,
        precision: model.precision ?? 0,
        recall: model.recall ?? 0,
        experiment: model.experiment ?? 'unknown',
        color: CHART_PALETTE[index % CHART_PALETTE.length],
      })),
    [sortedModels],
  )

  const leaderboardModels = useMemo(
    () =>
      sortedModels.map((model, index) => ({
        ...model,
        rank: index + 1,
        precision: model.precision ?? 0,
        recall: model.recall ?? 0,
      })),
    [sortedModels],
  )

  const connected = !error

  return (
    <div className="space-y-7 pb-6">
      {/* Hero */}
      <DashboardHero
        modelCount={uniqueModels.length}
        bestAccuracy={bestModel?.accuracy ?? 0}
        connected={connected}
      />

      {/* Error banner */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm font-medium text-red-700 dark:border-red-800/50 dark:bg-red-900/20 dark:text-red-400"
        >
          <span className="h-2 w-2 shrink-0 rounded-full bg-red-500" />
          {error}
        </motion.div>
      )}

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Active Experiments"
          value={loading ? '—' : experiments.length}
          subtitle="Ablation studies configured"
          icon={<Activity size={20} className="text-white" />}
          color="emerald"
          trend={{ label: connected ? 'API Ready' : 'Offline', positive: connected }}
          delay={0.05}
        />
        <StatCard
          title="Deployed Models"
          value={loading ? '—' : uniqueModels.length}
          subtitle="Active classifiers loaded"
          icon={<Layers size={20} className="text-white" />}
          color="primary"
          delay={0.1}
        />
        <StatCard
          title="Mean F1 Score"
          value={loading ? '—' : averageF1.toFixed(3)}
          subtitle={`Across ${uniqueModels.length} classifiers`}
          icon={<Target size={20} className="text-white" />}
          color="violet"
          delay={0.15}
        />
        <StatCard
          title="Peak Accuracy"
          value={loading ? '—' : bestModel ? `${bestModel.accuracy.toFixed(1)}%` : 'N/A'}
          subtitle={bestModel ? shortModelName(bestModel.name) : 'No models yet'}
          icon={<TrendingUp size={20} className="text-white" />}
          color="amber"
          trend={bestModel ? { label: `Avg ${averageAccuracy.toFixed(1)}%`, positive: true } : undefined}
          delay={0.2}
        />
      </div>

      {/* Charts */}
      {!loading && uniqueModels.length > 0 && (
        <PerformanceCharts models={chartModels} bestModel={chartModels[0]} />
      )}

      {/* Leaderboard + sidebar */}
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <ModelLeaderboard models={leaderboardModels} loading={loading} />

        <div className="space-y-6">
          <PipelineStatus connected={connected} modelCount={uniqueModels.length} experiments={experiments} />

          {/* CTA card */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary-600 via-primary-700 to-indigo-800 p-6 text-white shadow-xl"
          >
            <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/5 blur-2xl" />
            <div className="pointer-events-none absolute -bottom-8 left-0 h-32 w-32 rounded-full bg-accent-500/20 blur-2xl" />
            <div className="relative">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15 backdrop-blur-sm">
                <Brain size={20} className="text-white" />
              </div>
              <h3 className="mt-4 text-base font-bold leading-snug">
                Ready to classify Somali text?
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-primary-100/85">
                Compare {uniqueModels.length || 'all'} trained models with confidence
                scores and XAI token highlights — built for research.
              </p>
              <Link
                to="/predict"
                className="mt-5 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-bold text-primary-700 shadow-lg transition-all hover:bg-primary-50 hover:-translate-y-0.5"
              >
                Open Predict Playground
                <span className="text-primary-500">→</span>
              </Link>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Experiments overview */}
      <ExperimentOverview experiments={experiments} />
    </div>
  )
}

export default Dashboard
