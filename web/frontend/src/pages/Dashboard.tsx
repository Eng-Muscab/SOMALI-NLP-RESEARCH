import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart, Bar, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowUpRight, BarChart3, Brain, Layers, Sparkles, TrendingUp } from 'lucide-react'
import { Badge } from '../components/ui/Badge'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { MetricCard } from '../components/dashboard/MetricCard'

interface LeaderboardRow {
  rank: number
  modelName: string
  accuracy: number
  f1: number
  status: 'active' | 'testing' | 'offline'
}

interface ActivityRow {
  title: string
  detail: string
  result: string
  time: string
}

const Dashboard = () => {
  const [loading, setLoading] = useState(true)
  const [metrics, setMetrics] = useState([
    { title: 'Total Predictions', value: '—', delta: '—', label: 'Since last week', icon: <BarChart3 size={20} />, accentClass: 'bg-gradient-to-br from-sky-500 to-cyan-500' },
    { title: 'Accuracy', value: '—', delta: '—', label: 'Classification performance', icon: <TrendingUp size={20} />, accentClass: 'bg-gradient-to-br from-emerald-500 to-teal-500' },
    { title: 'F1 Score', value: '—', delta: '—', label: 'Precision and recall', icon: <Sparkles size={20} />, accentClass: 'bg-gradient-to-br from-violet-500 to-fuchsia-500' },
    { title: 'Available Models', value: '—', delta: '—', label: 'Ready for predictions', icon: <Layers size={20} />, accentClass: 'bg-gradient-to-br from-amber-500 to-orange-500' },
    { title: 'Experiments', value: '—', delta: '—', label: 'Recent training runs', icon: <Brain size={20} />, accentClass: 'bg-gradient-to-br from-cyan-500 to-sky-500' },
  ])
  const [chartData, setChartData] = useState<Array<{ name: string; accuracy: number; f1: number }>>([])
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([])
  const [recentActivity, setRecentActivity] = useState<ActivityRow[]>([])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setMetrics([
        { title: 'Total Predictions', value: '2,847', delta: '+12.5%', label: 'Since last week', icon: <BarChart3 size={20} />, accentClass: 'bg-gradient-to-br from-sky-500 to-cyan-500' },
        { title: 'Accuracy', value: '94.2%', delta: '+2.1%', label: 'Classification performance', icon: <TrendingUp size={20} />, accentClass: 'bg-gradient-to-br from-emerald-500 to-teal-500' },
        { title: 'F1 Score', value: '0.921', delta: '+1.8%', label: 'Precision and recall', icon: <Sparkles size={20} />, accentClass: 'bg-gradient-to-br from-violet-500 to-fuchsia-500' },
        { title: 'Available Models', value: '8', delta: '+2', label: 'Ready for predictions', icon: <Layers size={20} />, accentClass: 'bg-gradient-to-br from-amber-500 to-orange-500' },
        { title: 'Experiments', value: '14', delta: '+3', label: 'Recent training runs', icon: <Brain size={20} />, accentClass: 'bg-gradient-to-br from-cyan-500 to-sky-500' },
      ])

      setChartData([
        { name: 'Mon', accuracy: 92, f1: 0.9 },
        { name: 'Tue', accuracy: 93, f1: 0.91 },
        { name: 'Wed', accuracy: 91, f1: 0.89 },
        { name: 'Thu', accuracy: 95, f1: 0.93 },
        { name: 'Fri', accuracy: 94, f1: 0.92 },
        { name: 'Sat', accuracy: 96, f1: 0.94 },
        { name: 'Sun', accuracy: 94, f1: 0.91 },
      ])

      setLeaderboard([
        { rank: 1, modelName: 'Somali-Large-V1', accuracy: 96.2, f1: 0.961, status: 'active' },
        { rank: 2, modelName: 'Logistic Regression', accuracy: 94.1, f1: 0.941, status: 'testing' },
        { rank: 3, modelName: 'Random Forest', accuracy: 93.5, f1: 0.935, status: 'active' },
      ])

      setRecentActivity([
        { title: 'Prediction deployed', detail: 'Auto-generated sentiment labels for 4,024 examples', result: '96.2% accuracy', time: 'Just now' },
        { title: 'Experiment completed', detail: 'Tuned linear pipeline on a balanced dataset', result: '+2.1% accuracy', time: '1 hr ago' },
        { title: 'Dataset imported', detail: '10,000 Somali news sentences added', result: 'Ready for training', time: '3 hrs ago' },
      ])

      setLoading(false)
    }, 900)
    return () => window.clearTimeout(timer)
  }, [])

  return (
    <div className="space-y-8">
      <div className="rounded-[2rem] border border-neutral-200 dark:border-neutral-700 bg-white/90 dark:bg-neutral-950/80 p-8 shadow-xl shadow-slate-900/5 backdrop-blur-xl">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-3 lg:max-w-2xl">
            <p className="inline-flex items-center gap-2 rounded-full border border-primary-200/70 bg-primary-50/80 px-4 py-2 text-sm font-semibold text-primary-700 dark:border-primary-500/30 dark:bg-primary-500/10 dark:text-primary-200">
              <Sparkles size={16} /> Premium analytics
            </p>
            <div>
              <h1 className="text-4xl font-semibold tracking-tight text-neutral-950 dark:text-white">Somali NLP research dashboard</h1>
              <p className="mt-3 max-w-2xl text-base text-neutral-600 dark:text-neutral-400">
                Monitor your prediction pipelines, model health, and experiment performance in one polished workspace.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-2">
            <div className="rounded-3xl bg-neutral-50 dark:bg-neutral-900 p-4 text-center">
              <p className="text-sm font-medium uppercase tracking-[0.24em] text-neutral-500 dark:text-neutral-400">Workspaces</p>
              <p className="mt-4 text-3xl font-semibold text-neutral-950 dark:text-white">3</p>
            </div>
            <div className="rounded-3xl bg-neutral-50 dark:bg-neutral-900 p-4 text-center">
              <p className="text-sm font-medium uppercase tracking-[0.24em] text-neutral-500 dark:text-neutral-400">Teams</p>
              <p className="mt-4 text-3xl font-semibold text-neutral-950 dark:text-white">7</p>
            </div>
            <div className="rounded-3xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4 text-center">
              <p className="text-sm font-medium uppercase tracking-[0.24em] text-neutral-500 dark:text-neutral-400">Live models</p>
              <p className="mt-4 text-3xl font-semibold text-neutral-950 dark:text-white">4</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <section className="space-y-6">
          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-5">
            {metrics.map((item) => (
              <MetricCard key={item.title} {...item} isLoading={loading} />
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-medium text-neutral-500 dark:text-neutral-400">Accuracy</p>
                      <h2 className="mt-2 text-xl font-semibold text-neutral-950 dark:text-white">Weekly performance</h2>
                    </div>
                    <Badge variant="success">Stable</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-6">
                  {loading ? (
                    <div className="space-y-4">
                      <Skeleton className="h-72 rounded-[1.5rem]" />
                      <div className="grid gap-3 sm:grid-cols-3">
                        <Skeleton className="h-16 rounded-3xl" />
                        <Skeleton className="h-16 rounded-3xl" />
                        <Skeleton className="h-16 rounded-3xl" />
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                            <XAxis dataKey="name" stroke="rgba(100,116,139,0.6)" />
                            <YAxis stroke="rgba(100,116,139,0.6)" />
                            <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(148,163,184,0.2)', borderRadius: 12, color: '#fff' }} />
                            <Line type="monotone" dataKey="accuracy" stroke="#0ea5e9" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-3">
                        <div className="rounded-3xl bg-neutral-100 dark:bg-neutral-900 p-4">
                          <p className="text-sm text-neutral-500 dark:text-neutral-400">This week</p>
                          <p className="mt-2 text-2xl font-semibold text-neutral-950 dark:text-white">94.2%</p>
                        </div>
                        <div className="rounded-3xl bg-neutral-100 dark:bg-neutral-900 p-4">
                          <p className="text-sm text-neutral-500 dark:text-neutral-400">Goal</p>
                          <p className="mt-2 text-2xl font-semibold text-neutral-950 dark:text-white">95.0%</p>
                        </div>
                        <div className="rounded-3xl bg-neutral-100 dark:bg-neutral-900 p-4">
                          <p className="text-sm text-neutral-500 dark:text-neutral-400">Drift</p>
                          <p className="mt-2 text-2xl font-semibold text-neutral-950 dark:text-white">0.8%</p>
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.1 }}>
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-medium text-neutral-500 dark:text-neutral-400">F1 Score</p>
                      <h2 className="mt-2 text-xl font-semibold text-neutral-950 dark:text-white">Model reliability</h2>
                    </div>
                    <Badge variant="primary">Trends</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {loading ? (
                    <Skeleton className="h-72 rounded-[1.5rem]" />
                  ) : (
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                          <XAxis dataKey="name" stroke="rgba(100,116,139,0.6)" />
                          <YAxis stroke="rgba(100,116,139,0.6)" />
                          <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(148,163,184,0.2)', borderRadius: 12, color: '#fff' }} />
                          <Bar dataKey="f1" fill="#22c55e" radius={[16, 16, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </section>

        <aside className="space-y-6">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.2 }}>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-neutral-500 dark:text-neutral-400">Performance pulse</p>
                    <h2 className="mt-2 text-xl font-semibold text-neutral-950 dark:text-white">Snapshot</h2>
                  </div>
                  <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-2 text-sm font-semibold text-neutral-700 shadow-sm dark:bg-neutral-900/80 dark:text-neutral-200">
                    <ArrowUpRight size={16} /> Live
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {loading ? (
                  <div className="space-y-4">
                    <Skeleton className="h-14 rounded-3xl" />
                    <Skeleton className="h-14 rounded-3xl" />
                    <Skeleton className="h-14 rounded-3xl" />
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="rounded-3xl bg-neutral-50 dark:bg-neutral-900 p-5">
                      <p className="text-sm text-neutral-500 dark:text-neutral-400">Operational capacity</p>
                      <p className="mt-3 text-3xl font-semibold text-neutral-950 dark:text-white">83%</p>
                    </div>
                    <div className="rounded-3xl bg-neutral-50 dark:bg-neutral-900 p-5">
                      <p className="text-sm text-neutral-500 dark:text-neutral-400">Inference latency</p>
                      <p className="mt-3 text-3xl font-semibold text-neutral-950 dark:text-white">128ms</p>
                    </div>
                    <div className="rounded-3xl bg-neutral-50 dark:bg-neutral-900 p-5">
                      <p className="text-sm text-neutral-500 dark:text-neutral-400">Data pipeline</p>
                      <p className="mt-3 text-3xl font-semibold text-neutral-950 dark:text-white">Healthy</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.25 }}>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-neutral-500 dark:text-neutral-400">Top models</p>
                    <h2 className="mt-2 text-xl font-semibold text-neutral-950 dark:text-white">Leaderboard</h2>
                  </div>
                  <Badge variant="primary">Top 3</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {loading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-16 rounded-3xl" />
                    <Skeleton className="h-16 rounded-3xl" />
                    <Skeleton className="h-16 rounded-3xl" />
                  </div>
                ) : leaderboard.length === 0 ? (
                  <div className="rounded-3xl border border-dashed border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-900 p-8 text-center">
                    <p className="text-sm font-semibold text-neutral-700 dark:text-neutral-200">No model performance available yet.</p>
                    <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">Train a new model or import one to begin comparing scores.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {leaderboard.map((row) => (
                      <div key={row.rank} className="grid gap-3 sm:grid-cols-[auto_1fr_auto] items-center rounded-3xl border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-900 p-4">
                        <div className="flex h-12 w-12 items-center justify-center rounded-3xl bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-200 font-semibold">
                          {row.rank}
                        </div>
                        <div>
                          <p className="font-semibold text-neutral-900 dark:text-white">{row.modelName}</p>
                          <p className="text-sm text-neutral-500 dark:text-neutral-400">{row.accuracy}% accuracy · F1 {row.f1.toFixed(3)}</p>
                        </div>
                        <Badge variant={row.status === 'active' ? 'success' : row.status === 'testing' ? 'primary' : 'neutral'}>
                          {row.status === 'active' ? 'Active' : row.status === 'testing' ? 'Testing' : 'Offline'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </aside>
      </div>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.3 }}>
        <Card>
          <CardHeader>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-500 dark:text-neutral-400">Recent activity</p>
                <h2 className="mt-2 text-xl font-semibold text-neutral-950 dark:text-white">Timeline</h2>
              </div>
              <Badge variant="success">Updates</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-4">
                <Skeleton className="h-24 rounded-[1.75rem]" />
                <Skeleton className="h-24 rounded-[1.75rem]" />
                <Skeleton className="h-24 rounded-[1.75rem]" />
              </div>
            ) : recentActivity.length === 0 ? (
              <div className="rounded-3xl border border-dashed border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-900 p-10 text-center">
                <p className="text-lg font-semibold text-neutral-900 dark:text-white">No activity yet</p>
                <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">Your project updates will appear here as experiments and predictions are processed.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {recentActivity.map((item, index) => (
                  <div key={index} className="grid gap-4 sm:grid-cols-[1fr_auto] rounded-3xl border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-900 p-5">
                    <div>
                      <p className="font-semibold text-neutral-900 dark:text-white">{item.title}</p>
                      <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">{item.detail}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-neutral-950 dark:text-white">{item.result}</p>
                      <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">{item.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}

export default Dashboard
