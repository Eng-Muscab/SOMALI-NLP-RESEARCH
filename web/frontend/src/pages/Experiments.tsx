import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts'
import {
  Download,
  Search,
  ChevronsUpDown,
  X,
  Sliders,
  FileSpreadsheet,
  Trophy,
} from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { listExperiments } from '../services/experimentService'
import { getApiErrorMessage } from '../services/api'
import { useToast } from '../contexts/ToastContext'
import type { Experiment, ExperimentStatus } from '../types/experiment'

const statusVariants: Record<ExperimentStatus, 'success' | 'primary' | 'warning' | 'error'> = {
  completed: 'success',
  running: 'primary',
  queued: 'warning',
  failed: 'error',
}

const sortFields = ['name', 'date', 'accuracy', 'f1'] as const
export type SortField = (typeof sortFields)[number]

const rowsPerPageOptions = [5, 8, 12]

const formatDecimal = (value: number) => value.toFixed(value < 1 ? 3 : 1)

const downloadCSV = (items: Experiment[], fileName: string) => {
  if (!items.length) return
  const headers = ['Name', 'Date', 'Status', 'Accuracy', 'F1 Score', 'Models', 'Runtime', 'Dataset', 'Notes', 'Parameters']
  const lines = items.map((item) => {
    const values = [
      item.name,
      item.date,
      item.status,
      item.accuracy.toString(),
      item.f1.toString(),
      item.models.toString(),
      item.runtime ?? '',
      item.dataset ?? '',
      item.notes ?? '',
      item.params ? JSON.stringify(item.params) : '',
    ]
    return values.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(',')
  })
  const csv = [headers.join(','), ...lines].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `${fileName}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

interface ComparisonRow {
  experiment: string; family: string; model: string
  accuracy: number; precision: number; recall: number
  f1: number; macro_f1: number; test_rows: number; train_scope: string
}

const familyMeta: Record<string, { label: string; color: string; dot: string }> = {
  traditional_ml: { label: 'Traditional ML', color: 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400',   dot: 'bg-blue-500' },
  deep_learning:  { label: 'Deep Learning',  color: 'bg-orange-50 text-orange-700 dark:bg-orange-500/10 dark:text-orange-400', dot: 'bg-orange-500' },
  transformers:   { label: 'Transformer',    color: 'bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-400', dot: 'bg-violet-500' },
}

const expMeta: Record<string, { short: string; color: string }> = {
  experiment_1_stopwords_included: { short: 'Exp 1', color: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400' },
  experiment_2_stopwords_removed:  { short: 'Exp 2', color: 'bg-teal-50 text-teal-700 dark:bg-teal-500/10 dark:text-teal-400' },
}

const Experiments = () => {
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'All' | ExperimentStatus>('All')
  const [sortField, setSortField] = useState<SortField>('date')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(8)
  const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const { showToast } = useToast()

  // Comparison leaderboard state
  const [comparison, setComparison] = useState<ComparisonRow[]>([])
  const [cmpExpFilter, setCmpExpFilter] = useState<'All' | string>('All')
  const [cmpFamFilter, setCmpFamFilter] = useState<'All' | string>('All')
  const [cmpSearch, setCmpSearch] = useState('')
  const [cmpLoading, setCmpLoading] = useState(true)

  /* ── Only show experiments matching the two allowed variants ── */
  const ALLOWED_EXPERIMENT_KEYWORDS = [
    'stopwords_included', 'stopwords included', 'included stopwords', 'experiment_1',
    'stopwords_removed', 'stopwords removed', 'removed stopwords', 'experiment_2',
  ]

  const isAllowedExperiment = (exp: Experiment) => {
    const haystack = `${exp.id} ${exp.name}`.toLowerCase()
    return ALLOWED_EXPERIMENT_KEYWORDS.some((kw) => haystack.includes(kw))
  }

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const response = await listExperiments()
        setExperiments(response.data.filter(isAllowedExperiment))
      } catch (err) {
        const message = getApiErrorMessage(err, 'Unable to load experiments from the API.')
        setLoadError(message)
        showToast(message, 'error')
        setExperiments([])
      } finally {
        setIsLoading(false)
      }
    }
    const fetchComparison = async () => {
      try {
        const { default: api } = await import('../services/api')
        const res = await api.get<ComparisonRow[]>('/experiments/comparison')
        setComparison(Array.isArray(res.data) ? res.data : [])
      } catch {
        setComparison([])
      } finally {
        setCmpLoading(false)
      }
    }
    fetchAll()
    fetchComparison()
  }, [showToast])

  const filteredExperiments = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()
    return experiments.filter((experiment) => {
      const matchesSearch =
        !normalizedSearch ||
        experiment.name.toLowerCase().includes(normalizedSearch) ||
        experiment.dataset?.toLowerCase().includes(normalizedSearch)
      const matchesStatus = statusFilter === 'All' || experiment.status === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [experiments, search, statusFilter])

  const sortedExperiments = useMemo(() => {
    return [...filteredExperiments].sort((a, b) => {
      const direction = sortDirection === 'asc' ? 1 : -1
      if (sortField === 'name') {
        return a.name.localeCompare(b.name) * direction
      }
      if (sortField === 'date') {
        return (new Date(a.date).getTime() - new Date(b.date).getTime()) * direction
      }
      if (sortField === 'accuracy') {
        return (a.accuracy - b.accuracy) * direction
      }
      return (a.f1 - b.f1) * direction
    })
  }, [filteredExperiments, sortField, sortDirection])

  const totalPages = Math.max(1, Math.ceil(sortedExperiments.length / pageSize))
  const visibleExperiments = sortedExperiments.slice((page - 1) * pageSize, page * pageSize)

  const filteredComparison = useMemo(() => {
    return comparison.filter(r => {
      const expOk  = cmpExpFilter === 'All' || r.experiment === cmpExpFilter
      const famOk  = cmpFamFilter === 'All' || r.family === cmpFamFilter
      const srchOk = !cmpSearch.trim() || r.model.toLowerCase().includes(cmpSearch.toLowerCase())
      return expOk && famOk && srchOk
    })
  }, [comparison, cmpExpFilter, cmpFamFilter, cmpSearch])

  const chartData = useMemo(
    () =>
      sortedExperiments
        .slice(0, 8)
        .map((experiment) => ({
          name: experiment.name,
          accuracy: experiment.accuracy,
          f1: experiment.f1,
        }))
        .reverse(),
    [sortedExperiments]
  )

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
    setPage(1)
  }

  const renderSortIndicator = (field: SortField) => {
    if (sortField !== field) return null
    return sortDirection === 'asc' ? ' ↑' : ' ↓'
  }

  const handleExportView = () => {
    downloadCSV(sortedExperiments, 'experiment-export')
  }

  const handleExportExperiment = (experiment: Experiment) => {
    downloadCSV([experiment], `experiment-${experiment.id}`)
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-extrabold tracking-tight text-neutral-900 dark:text-white mb-2">Experiments</h1>
        <p className="text-neutral-550 dark:text-neutral-400 font-medium">
          Track historical training runs, analyze metrics trend, and inspect hyperparameter details
        </p>
      </div>

      {loadError && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30 p-4 text-sm text-amber-900 dark:text-amber-200"
        >
          {loadError}
        </motion.div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.4fr_0.6fr]">
        <Card>
          <CardHeader>
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-bold text-neutral-900 dark:text-white">Ablation Runs</h2>
                <p className="text-xs text-neutral-450 dark:text-neutral-500 font-medium">
                  Search, filter, and compare NLP evaluation experiments.
                </p>
              </div>
              <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center">
                <Input
                  icon={<Search size={15} />}
                  placeholder="Search experiments..."
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value)
                    setPage(1)
                  }}
                  className="w-full sm:w-64"
                />
                <Button variant="outline" size="sm" icon={<Download size={14} />} onClick={handleExportView} className="text-xs py-2">
                  Export CSV
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-wrap gap-2">
              {(['All', 'completed', 'running', 'queued', 'failed'] as const).map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={() => {
                    setStatusFilter(status === 'All' ? 'All' : status)
                    setPage(1)
                  }}
                  className={`rounded-full px-4 py-1.5 text-xs font-bold transition-all duration-300 border ${
                    statusFilter === status
                      ? 'bg-primary-600 border-primary-600 text-white shadow-md shadow-primary-500/10'
                      : 'border-neutral-200 bg-white text-neutral-600 hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:border-neutral-700'
                  }`}
                >
                  {status.toUpperCase()}
                </button>
              ))}
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card className="bg-neutral-50/50 dark:bg-neutral-900/10 border-neutral-100 dark:border-neutral-800/40">
                <CardHeader className="py-4 border-b-neutral-100 dark:border-b-neutral-800/40">
                  <h3 className="text-sm font-bold text-neutral-800 dark:text-neutral-200">Accuracy Comparison</h3>
                </CardHeader>
                <CardContent className="h-64 px-2 py-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}> 
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                      <XAxis dataKey="name" stroke="rgba(148,163,184,0.4)" tick={{ fontSize: 9 }} interval={0} />
                      <YAxis stroke="rgba(148,163,184,0.4)" tick={{ fontSize: 10 }} domain={[0, 100]} />
                      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 12 }} />
                      <Bar dataKey="accuracy" fill="#6366f1" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card className="bg-neutral-50/50 dark:bg-neutral-900/10 border-neutral-100 dark:border-b-neutral-800/40">
                <CardHeader className="py-4 border-b-neutral-100 dark:border-b-neutral-800/40">
                  <h3 className="text-sm font-bold text-neutral-800 dark:text-neutral-200">F1 Curve Dynamics</h3>
                </CardHeader>
                <CardContent className="h-64 px-2 py-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                      <XAxis dataKey="name" stroke="rgba(148,163,184,0.4)" tick={{ fontSize: 9 }} interval={0} />
                      <YAxis stroke="rgba(148,163,184,0.4)" tick={{ fontSize: 10 }} domain={[0, 1.0]} />
                      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 12 }} />
                      <Line type="monotone" dataKey="f1" stroke="#14b8a6" strokeWidth={3} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <h3 className="text-lg font-bold text-neutral-900 dark:text-white">Summary Metrics</h3>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-2xl border border-neutral-100 bg-white p-5 shadow-sm dark:border-neutral-800/60 dark:bg-neutral-950/20">
              <p className="text-xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Total runs</p>
              <p className="mt-2 text-3xl font-black text-neutral-900 dark:text-white">{experiments.length}</p>
            </div>
            <div className="rounded-2xl border border-neutral-100 bg-white p-5 shadow-sm dark:border-neutral-800/60 dark:bg-neutral-950/20">
              <p className="text-xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Filtered set</p>
              <p className="mt-2 text-3xl font-black text-neutral-900 dark:text-white">{sortedExperiments.length}</p>
            </div>
            <div className="rounded-2xl border border-neutral-100 bg-white p-5 shadow-sm dark:border-neutral-800/60 dark:bg-neutral-950/20">
              <p className="text-xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Rows per page</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {rowsPerPageOptions.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => {
                      setPageSize(option)
                      setPage(1)
                    }}
                    className={`rounded-full px-3.5 py-1 text-xs font-bold transition-all duration-300 border ${
                      pageSize === option
                        ? 'bg-primary-600 border-primary-600 text-white shadow-md'
                        : 'border-neutral-200 bg-white text-neutral-600 hover:border-neutral-350 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-350 dark:hover:border-neutral-700'
                    }`}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-lg font-bold text-neutral-900 dark:text-white">Run History Table</h3>
              <p className="text-xs text-neutral-450 dark:text-neutral-500 font-medium">Click headers to sort or select a row for details.</p>
            </div>
            <div className="inline-flex items-center gap-1.5 rounded-full border border-neutral-150/80 bg-neutral-50/50 px-3.5 py-1.5 text-2xs font-extrabold uppercase tracking-wide text-neutral-500 dark:border-neutral-800/60 dark:bg-neutral-900/30 dark:text-neutral-400">
              <Sliders size={12} className="text-primary-500" />
              {isLoading ? 'Fetching data...' : `Order: ${sortField} ${sortDirection}`}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-neutral-150 text-neutral-500 dark:border-neutral-800/80 dark:text-neutral-400 font-semibold">
                  <th className="px-4 py-3.5 cursor-pointer text-xs font-bold uppercase tracking-wider" onClick={() => toggleSort('name')}>
                    <div className="flex items-center gap-1">Name <ChevronsUpDown size={13} className="text-neutral-400" />{renderSortIndicator('name')}</div>
                  </th>
                  <th className="px-4 py-3.5 cursor-pointer text-xs font-bold uppercase tracking-wider" onClick={() => toggleSort('date')}>
                    <div className="flex items-center gap-1">Date <ChevronsUpDown size={13} className="text-neutral-400" />{renderSortIndicator('date')}</div>
                  </th>
                  <th className="px-4 py-3.5 text-xs font-bold uppercase tracking-wider">Status</th>
                  <th className="px-4 py-3.5 cursor-pointer text-xs font-bold uppercase tracking-wider" onClick={() => toggleSort('accuracy')}>
                    <div className="flex items-center gap-1">Accuracy <ChevronsUpDown size={13} className="text-neutral-400" />{renderSortIndicator('accuracy')}</div>
                  </th>
                  <th className="px-4 py-3.5 cursor-pointer text-xs font-bold uppercase tracking-wider" onClick={() => toggleSort('f1')}>
                    <div className="flex items-center gap-1">F1 Score <ChevronsUpDown size={13} className="text-neutral-400" />{renderSortIndicator('f1')}</div>
                  </th>
                  <th className="px-4 py-3.5 text-xs font-bold uppercase tracking-wider">Models</th>
                  <th className="px-4 py-3.5 text-xs font-bold uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800/40">
                {isLoading ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-neutral-550 dark:text-neutral-500">
                      Loading historical runs...
                    </td>
                  </tr>
                ) : visibleExperiments.map((experiment) => (
                  <tr
                    key={experiment.id}
                    className="hover:bg-neutral-50/50 dark:hover:bg-neutral-800/10"
                  >
                    <td className="px-4 py-4">
                      <button
                        type="button"
                        onClick={() => setSelectedExperiment(experiment)}
                        className="text-left font-bold text-neutral-900 hover:text-primary-600 dark:text-white dark:hover:text-primary-450 truncate max-w-[180px]"
                      >
                        {experiment.name}
                      </button>
                    </td>
                    <td className="px-4 py-4 text-neutral-500 dark:text-neutral-400 font-medium">{experiment.date}</td>
                    <td className="px-4 py-4">
                      <Badge variant={statusVariants[experiment.status]}>{experiment.status}</Badge>
                    </td>
                    <td className="px-4 py-4 text-neutral-900 dark:text-white font-bold">{experiment.accuracy}%</td>
                    <td className="px-4 py-4 text-neutral-900 dark:text-white font-bold">{formatDecimal(experiment.f1)}</td>
                    <td className="px-4 py-4 text-neutral-500 dark:text-neutral-400 font-medium">{experiment.models}</td>
                    <td className="px-4 py-4 space-x-2">
                      <Button variant="outline" size="sm" onClick={() => setSelectedExperiment(experiment)} className="text-2xs py-1 px-2.5">
                        Details
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleExportExperiment(experiment)} icon={<Download size={13} />} className="text-2xs py-1 px-2 text-neutral-500 hover:text-neutral-800 dark:text-neutral-450 dark:hover:text-white">
                        Export
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs font-semibold text-neutral-450 dark:text-neutral-500">
              Showing {visibleExperiments.length} of {sortedExperiments.length} experiments.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                disabled={page === 1}
                className="text-xs py-1.5 px-3"
              >
                Previous
              </Button>
              <span className="text-xs font-bold text-neutral-700 dark:text-neutral-300 px-2">
                Page {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
                disabled={page === totalPages}
                className="text-xs py-1.5 px-3"
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Cross-Experiment Model Leaderboard ─────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white shadow-sm dark:border-neutral-800/60 dark:bg-neutral-900"
      >
        {/* Header */}
        <div className="flex flex-col gap-4 border-b border-neutral-100 px-6 py-5 dark:border-neutral-800 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-lg shadow-orange-500/20">
              <Trophy size={18} className="text-white" />
            </div>
            <div>
              <h2 className="text-base font-extrabold text-neutral-900 dark:text-white">Cross-Experiment Model Leaderboard</h2>
              <p className="text-[11px] font-medium text-neutral-400 dark:text-neutral-500">
                {comparison.length} models — both experiments ranked by accuracy
              </p>
            </div>
          </div>
          {/* Search */}
          <div className="relative w-full sm:w-56">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              value={cmpSearch}
              onChange={e => setCmpSearch(e.target.value)}
              placeholder="Search model…"
              className="h-9 w-full rounded-xl border border-neutral-200 bg-neutral-50 pl-8 pr-3 text-xs font-semibold text-neutral-800 placeholder-neutral-400 focus:border-primary-400 focus:bg-white focus:outline-none dark:border-neutral-700 dark:bg-neutral-800 dark:text-white"
            />
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2 border-b border-neutral-100 px-6 py-3 dark:border-neutral-800">
          {/* Experiment filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-400">Exp:</span>
            {['All', 'experiment_1_stopwords_included', 'experiment_2_stopwords_removed'].map(k => (
              <button key={k} onClick={() => setCmpExpFilter(k)}
                className={`rounded-full px-3 py-1 text-[11px] font-bold transition-all ${
                  cmpExpFilter === k
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-300'
                }`}>
                {k === 'All' ? 'All' : k.includes('1') ? 'Exp 1' : 'Exp 2'}
              </button>
            ))}
          </div>
          <div className="mx-2 h-5 w-px bg-neutral-200 dark:bg-neutral-700 self-center" />
          {/* Family filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-400">Family:</span>
            {['All', 'traditional_ml', 'deep_learning', 'transformers'].map(k => (
              <button key={k} onClick={() => setCmpFamFilter(k)}
                className={`rounded-full px-3 py-1 text-[11px] font-bold transition-all ${
                  cmpFamFilter === k
                    ? 'bg-violet-600 text-white shadow-sm'
                    : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-300'
                }`}>
                {k === 'All' ? 'All' : familyMeta[k]?.label ?? k}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b border-neutral-100 dark:border-neutral-800">
                {['#', 'Model', 'Experiment', 'Family', 'Accuracy', 'Precision', 'Recall', 'F1'].map(h => (
                  <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50 dark:divide-neutral-800/40">
              {cmpLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 8 }).map((_, j) => (
                      <td key={j} className="px-5 py-4">
                        <div className="h-4 w-full animate-pulse rounded-lg bg-neutral-100 dark:bg-neutral-800" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filteredComparison.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-5 py-12 text-center text-sm font-medium text-neutral-400">
                    No models match the current filters.
                  </td>
                </tr>
              ) : filteredComparison.map((row, idx) => {
                const globalRank = comparison.findIndex(r => r.model === row.model && r.experiment === row.experiment) + 1
                const fam  = familyMeta[row.family] ?? { label: row.family, color: 'bg-neutral-100 text-neutral-600', dot: 'bg-neutral-400' }
                const exp  = expMeta[row.experiment] ?? { short: row.experiment, color: 'bg-neutral-100 text-neutral-600' }
                const medalEl = globalRank === 1
                  ? <span className="text-base">🥇</span>
                  : globalRank === 2
                  ? <span className="text-base">🥈</span>
                  : globalRank === 3
                  ? <span className="text-base">🥉</span>
                  : <span className="text-xs font-bold text-neutral-400 dark:text-neutral-500">#{globalRank}</span>

                return (
                  <motion.tr
                    key={`${row.experiment}-${row.model}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: idx * 0.02 }}
                    className={`transition-colors hover:bg-neutral-50/80 dark:hover:bg-neutral-800/20 ${
                      globalRank <= 3 ? 'bg-amber-50/30 dark:bg-amber-500/5' : ''
                    }`}
                  >
                    {/* Rank */}
                    <td className="w-12 px-5 py-3.5 text-center">{medalEl}</td>

                    {/* Model */}
                    <td className="px-5 py-3.5">
                      <span className="font-bold text-neutral-900 dark:text-white">{row.model}</span>
                    </td>

                    {/* Experiment */}
                    <td className="px-5 py-3.5">
                      <span className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wide ${exp.color}`}>
                        {exp.short}
                      </span>
                    </td>

                    {/* Family */}
                    <td className="px-5 py-3.5">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold ${fam.color}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${fam.dot}`} />
                        {fam.label}
                      </span>
                    </td>

                    {/* Accuracy bar */}
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <span className="w-14 text-right font-mono text-xs font-black text-neutral-800 dark:text-neutral-200">
                          {row.accuracy.toFixed(2)}%
                        </span>
                        <div className="relative h-2 w-24 overflow-hidden rounded-full bg-neutral-100 dark:bg-neutral-800">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${row.accuracy}%` }}
                            transition={{ duration: 0.8, ease: 'easeOut', delay: idx * 0.03 }}
                            className={`absolute inset-y-0 left-0 rounded-full ${
                              row.accuracy >= 90 ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                              : row.accuracy >= 80 ? 'bg-gradient-to-r from-blue-500 to-indigo-400'
                              : 'bg-gradient-to-r from-amber-400 to-orange-400'
                            }`}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Precision */}
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-xs font-semibold text-neutral-600 dark:text-neutral-400">
                        {row.precision.toFixed(2)}%
                      </span>
                    </td>

                    {/* Recall */}
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-xs font-semibold text-neutral-600 dark:text-neutral-400">
                        {row.recall.toFixed(2)}%
                      </span>
                    </td>

                    {/* F1 */}
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-xs font-black text-neutral-800 dark:text-neutral-200">
                        {row.f1.toFixed(4)}
                      </span>
                    </td>
                  </motion.tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Footer count */}
        {!cmpLoading && filteredComparison.length > 0 && (
          <div className="border-t border-neutral-100 px-6 py-3 dark:border-neutral-800">
            <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500">
              Showing {filteredComparison.length} of {comparison.length} model runs · sorted by accuracy descending
            </p>
          </div>
        )}
      </motion.div>

      <AnimatePresence>
        {selectedExperiment && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedExperiment(null)}
            />
            <motion.aside
              className="fixed right-0 top-0 z-50 flex h-full w-full max-w-xl flex-col bg-white border-l border-neutral-100 dark:border-neutral-800/80 p-6 shadow-2xl dark:bg-neutral-900 overflow-y-auto"
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'tween', duration: 0.3, ease: 'easeInOut' }}
            >
              <div className="mb-6 flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800/60 pb-5">
                <div>
                  <p className="text-3xs uppercase tracking-[0.2em] font-extrabold text-neutral-400 dark:text-neutral-500">Experiment details</p>
                  <h2 className="mt-1 text-xl font-black text-neutral-900 dark:text-white leading-tight">{selectedExperiment.name}</h2>
                </div>
                <button
                  type="button"
                  aria-label="Close details drawer"
                  onClick={() => setSelectedExperiment(null)}
                  className="rounded-xl border border-neutral-200 p-2 text-neutral-500 hover:text-neutral-700 dark:border-neutral-800 dark:text-neutral-400 dark:hover:text-white hover:bg-neutral-50 dark:hover:bg-neutral-950/20 transition duration-200"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-neutral-150/60 bg-neutral-50/50 p-4 dark:border-neutral-800/40 dark:bg-neutral-900/30">
                  <p className="text-3xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Status</p>
                  <Badge variant={statusVariants[selectedExperiment.status]} className="mt-2">{selectedExperiment.status}</Badge>
                </div>
                <div className="rounded-2xl border border-neutral-150/60 bg-neutral-50/50 p-4 dark:border-neutral-800/40 dark:bg-neutral-900/30">
                  <p className="text-3xs font-semibold text-neutral-455 dark:text-neutral-500 uppercase tracking-wider">Dataset Used</p>
                  <p className="mt-2 text-sm font-bold text-neutral-900 dark:text-white truncate" title={selectedExperiment.dataset}>{selectedExperiment.dataset ?? 'Unknown'}</p>
                </div>
                <div className="rounded-2xl border border-neutral-150/60 bg-neutral-50/50 p-4 dark:border-neutral-800/40 dark:bg-neutral-900/30">
                  <p className="text-3xs font-semibold text-neutral-455 dark:text-neutral-500 uppercase tracking-wider">Accuracy</p>
                  <p className="mt-2 text-base font-black text-neutral-900 dark:text-white">{selectedExperiment.accuracy}%</p>
                </div>
                <div className="rounded-2xl border border-neutral-150/60 bg-neutral-50/50 p-4 dark:border-neutral-800/40 dark:bg-neutral-900/30">
                  <p className="text-3xs font-semibold text-neutral-455 dark:text-neutral-500 uppercase tracking-wider">F1 Score</p>
                  <p className="mt-2 text-base font-black text-neutral-900 dark:text-white">{formatDecimal(selectedExperiment.f1)}</p>
                </div>
              </div>

              <div className="mt-6 space-y-4">
                <div className="rounded-2xl border border-neutral-150/60 bg-neutral-50/50 p-5 dark:border-neutral-800/40 dark:bg-neutral-900/30">
                  <p className="text-3xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Training Runtime</p>
                  <p className="mt-2 text-sm font-bold text-neutral-900 dark:text-white">{selectedExperiment.runtime ?? 'N/A'}</p>
                </div>
                <div className="rounded-2xl border border-neutral-150/60 bg-neutral-50/50 p-5 dark:border-neutral-800/40 dark:bg-neutral-900/30">
                  <p className="text-3xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Research Notes</p>
                  <p className="mt-2 text-xs leading-6 font-medium text-neutral-600 dark:text-neutral-350">{selectedExperiment.notes ?? 'No notes available.'}</p>
                </div>
                <div className="rounded-2xl border border-neutral-150/60 bg-neutral-50/50 p-5 dark:border-neutral-800/40 dark:bg-neutral-900/30">
                  <div className="flex items-center justify-between">
                    <p className="text-3xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Hyperparameters</p>
                    <Button size="sm" variant="ghost" onClick={() => handleExportExperiment(selectedExperiment)} icon={<FileSpreadsheet size={13} />} className="text-3xs py-1 px-2 border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 font-bold">
                      Export Run
                    </Button>
                  </div>
                  <div className="mt-4 space-y-2 text-xs font-semibold text-neutral-800 dark:text-neutral-200">
                    {selectedExperiment.params ? (
                      Object.entries(selectedExperiment.params).map(([key, value]) => (
                        <div key={key} className="flex items-center justify-between rounded-xl border border-neutral-100 bg-white px-3.5 py-2.5 shadow-[0_2px_8px_rgba(0,0,0,0.01)] dark:border-neutral-800 dark:bg-neutral-950">
                          <span className="font-bold text-neutral-700 dark:text-neutral-300">{key}</span>
                          <span className="text-neutral-500 dark:text-neutral-400 font-mono text-2xs">{String(value)}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-neutral-500 dark:text-neutral-400 font-medium">No parameters recorded.</p>
                    )}
                  </div>
                </div>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

export default Experiments
