import { useEffect, useMemo, useState } from 'react'
import { Activity, Brain, Layers, Target, TrendingUp, Users, LineChart, ScrollText } from 'lucide-react'
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
import { useAuth } from '@hooks/useAuth'
import { isAdmin } from '@/types/auth'

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

  const sortedModels = useMemo(
    () => [...models].sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0)),
    [models],
  )

  const bestModel = sortedModels[0]
  const averageF1 = models.length
    ? models.reduce((t, m) => t + Number(m.f1 || 0), 0) / models.length
    : 0
  const averageAccuracy = models.length
    ? models.reduce((t, m) => t + Number(m.accuracy || 0), 0) / models.length
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

  const { user } = useAuth()
  const isAdminUser  = isAdmin(user)
  const isViewerOnly = (user?.role ?? 'viewer') === 'viewer'
  const isResearcher = !isViewerOnly

  return (
    <div className="space-y-7 pb-6">

      {/* ── Admin quick links ───────────────────────────────────────────── */}
      {isAdminUser && (
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            { to: '/admin/users', icon: <Users size={16} />, label: 'User Management', sub: 'Accounts & permissions', color: 'bg-violet-100 text-violet-600 dark:bg-violet-500/15 dark:text-violet-400' },
            { to: '/analytics',   icon: <LineChart size={16} />, label: 'Analytics', sub: 'Usage trends', color: 'bg-sky-100 text-sky-600 dark:bg-sky-500/15 dark:text-sky-400' },
            { to: '/admin/logs',  icon: <ScrollText size={16} />, label: 'Audit Logs', sub: 'Activity records', color: 'bg-amber-100 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400' },
          ].map(({ to, icon, label, sub, color }) => (
            <Link key={to} to={to}
              className="flex items-center gap-3 rounded-2xl border border-neutral-200/70 bg-white px-4 py-3.5 transition-colors hover:border-sky-200 hover:bg-sky-50/50 dark:border-white/[0.06] dark:bg-[#0D2137] dark:hover:border-sky-500/20 dark:hover:bg-sky-500/5">
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${color}`}>{icon}</div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-neutral-900 dark:text-white">{label}</p>
                <p className="text-[11px] text-neutral-400 dark:text-neutral-500">{sub}</p>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Hero */}
      <DashboardHero
        modelCount={models.length}
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
          value={loading ? '—' : models.length}
          subtitle="Experiment-model evaluations"
          icon={<Layers size={20} className="text-white" />}
          color="primary"
          delay={0.1}
        />
        <StatCard
          title="Mean F1 Score"
          value={loading ? '—' : averageF1.toFixed(3)}
          subtitle={`Across ${models.length} evaluations`}
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

      {/* ── Research content (analyst / researcher / admin / super_admin) ── */}
      {isResearcher && (
        <>
          {/* Charts */}
          {!loading && models.length > 0 && (
            <PerformanceCharts models={chartModels} bestModel={chartModels[0]} />
          )}

          {/* Leaderboard + sidebar */}
          <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
            <ModelLeaderboard models={leaderboardModels} loading={loading} />

            <div className="space-y-6">
              {isAdminUser && (
                <PipelineStatus connected={connected} modelCount={models.length} experiments={experiments} />
              )}

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
                    Compare {models.length || 'all'} trained model evaluations with confidence
                    scores and XAI explanations — built for research.
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
        </>
      )}

      {/* ── Viewer simplified CTA ───────────────────────────────────────── */}
      {isViewerOnly && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white dark:border-white/[0.06] dark:bg-[#0D2137]"
        >
          <div className="border-b border-neutral-100 px-6 py-5 dark:border-white/[0.06]">
            <h2 className="text-lg font-extrabold text-neutral-900 dark:text-white">
              Welcome to SomNLP Research Platform
            </h2>
            <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-500">
              A multilingual NLP system for classifying Somali news text as AI-generated or human-written.
            </p>
          </div>
          <div className="grid gap-4 p-6 sm:grid-cols-2">
            <Link to="/predict"
              className="flex items-center gap-4 rounded-xl border border-sky-200 bg-sky-50 p-4 transition-colors hover:bg-sky-100 dark:border-sky-500/20 dark:bg-sky-500/8 dark:hover:bg-sky-500/12">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-500 text-white">
                <Brain size={18} />
              </div>
              <div>
                <p className="text-sm font-bold text-neutral-900 dark:text-white">Predict Text</p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400">Classify Somali text with AI models</p>
              </div>
            </Link>
            <Link to="/models"
              className="flex items-center gap-4 rounded-xl border border-neutral-200 bg-neutral-50 p-4 transition-colors hover:bg-neutral-100 dark:border-white/[0.06] dark:bg-white/[0.04] dark:hover:bg-white/8">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-neutral-200 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300">
                <Layers size={18} />
              </div>
              <div>
                <p className="text-sm font-bold text-neutral-900 dark:text-white">View Models</p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400">Explore {models.length} trained evaluations</p>
              </div>
            </Link>
          </div>
        </motion.div>
      )}

    </div>
  )
}

export default Dashboard
