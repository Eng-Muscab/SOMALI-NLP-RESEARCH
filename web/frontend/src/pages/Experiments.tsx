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
} from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { listExperiments } from '../services/experimentService'
import type { Experiment, ExperimentStatus } from '../types/experiment'

const statusVariants: Record<ExperimentStatus, 'success' | 'primary' | 'warning' | 'error'> = {
  completed: 'success',
  running: 'primary',
  queued: 'warning',
  failed: 'error',
}

const fallbackExperiments: Experiment[] = [
  {
    id: 'exp-1',
    name: 'Experiment 1: Stopwords Included',
    date: '2026-05-08',
    status: 'completed',
    accuracy: 94.2,
    f1: 0.921,
    models: 5,
    runtime: '2h 18m',
    dataset: 'Balanced Somali dataset',
    notes: 'Best result using stopword inclusion with TF-IDF + LightGBM.',
    params: {
      tokenizer: 'fasttext',
      stopwords: 'included',
      model: 'LightGBM',
      lr: 0.01,
      epochs: 12,
    },
  },
  {
    id: 'exp-2',
    name: 'Experiment 2: Stopwords Removed',
    date: '2026-05-05',
    status: 'completed',
    accuracy: 93.8,
    f1: 0.918,
    models: 5,
    runtime: '2h 05m',
    dataset: 'Balanced Somali dataset',
    notes: 'Reduced noise by removing stopwords and fine-tuning embeddings.',
    params: {
      tokenizer: 'word2vec',
      stopwords: 'removed',
      model: 'BiLSTM',
      lr: 0.005,
      epochs: 15,
    },
  },
  {
    id: 'exp-3',
    name: 'Experiment 3: Transformer Finetune',
    date: '2026-04-20',
    status: 'running',
    accuracy: 92.7,
    f1: 0.903,
    models: 3,
    runtime: '1h 12m',
    dataset: 'Full labeled dataset',
    notes: 'Fine-tuning transformer architecture on latest label set.',
    params: {
      model: 'SomaliBERT',
      batch_size: 16,
      lr: 2e-5,
      epochs: 6,
    },
  },
  {
    id: 'exp-4',
    name: 'Experiment 4: FastText Embeddings',
    date: '2026-04-12',
    status: 'failed',
    accuracy: 89.4,
    f1: 0.876,
    models: 4,
    runtime: '3h 05m',
    dataset: 'Small validation dataset',
    notes: 'FastText embeddings did not converge with the classifier settings.',
    params: {
      model: 'FastText',
      lr: 0.02,
      epochs: 20,
    },
  },
]

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

  useEffect(() => {
    const fetch = async () => {
      try {
        const response = await listExperiments()
        setExperiments(response.data.length ? response.data : fallbackExperiments)
      } catch (err) {
        setLoadError('Unable to load experiments from the API. Showing local sample data.')
        setExperiments(fallbackExperiments)
      }
    }
    fetch()
  }, [])

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
    return sortDirection === 'asc' ? '↑' : '↓'
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
        <h1 className="text-4xl font-bold text-neutral-900 dark:text-white mb-2">Experiments</h1>
        <p className="text-neutral-600 dark:text-neutral-400 max-w-3xl">
          Track experiment runs, compare accuracy and F1 performance, and inspect the latest model details.
        </p>
      </div>

      {loadError && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
        >
          {loadError}
        </motion.div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1.5fr_0.5fr]">
        <Card>
          <CardHeader>
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-neutral-900 dark:text-white">Experiment library</h2>
                <p className="text-sm text-neutral-600 dark:text-neutral-400">
                  Search and sort the latest experiment runs.
                </p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <Input
                  icon={<Search size={16} />}
                  placeholder="Search experiments"
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value)
                    setPage(1)
                  }}
                  className="w-full sm:w-72"
                />
                <Button variant="secondary" size="md" icon={<Download size={16} />} onClick={handleExportView}>
                  Export view
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {(['All', 'completed', 'running', 'queued', 'failed'] as const).map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={() => {
                    setStatusFilter(status === 'All' ? 'All' : status)
                    setPage(1)
                  }}
                  className={`rounded-full border px-3 py-1 text-sm transition ${
                    statusFilter === status
                      ? 'border-primary-600 bg-primary-600 text-white'
                      : 'border-neutral-300 bg-white text-neutral-700 hover:border-primary-400 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200'
                  }`}
                >
                  {status}
                </button>
              ))}
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card className="bg-neutral-50 dark:bg-neutral-900">
                <CardHeader>
                  <h3 className="text-base font-semibold text-neutral-900 dark:text-white">Accuracy Trend</h3>
                </CardHeader>
                <CardContent className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}> 
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.15)" />
                      <XAxis dataKey="name" stroke="rgba(100,116,139,0.5)" interval={0} tick={{ fontSize: 12 }} />
                      <YAxis stroke="rgba(100,116,139,0.5)" />
                      <Tooltip />
                      <Bar dataKey="accuracy" fill="#0ea5e9" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card className="bg-neutral-50 dark:bg-neutral-900">
                <CardHeader>
                  <h3 className="text-base font-semibold text-neutral-900 dark:text-white">F1 Curve</h3>
                </CardHeader>
                <CardContent className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.15)" />
                      <XAxis dataKey="name" stroke="rgba(100,116,139,0.5)" interval={0} tick={{ fontSize: 12 }} />
                      <YAxis stroke="rgba(100,116,139,0.5)" />
                      <Tooltip />
                      <Line type="monotone" dataKey="f1" stroke="#22c55e" strokeWidth={3} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">Summary</h3>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-700 dark:bg-neutral-950">
              <p className="text-sm text-neutral-500 dark:text-neutral-400">Total experiments</p>
              <p className="mt-2 text-3xl font-semibold text-neutral-900 dark:text-white">{experiments.length}</p>
            </div>
            <div className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-700 dark:bg-neutral-950">
              <p className="text-sm text-neutral-500 dark:text-neutral-400">Current filtered set</p>
              <p className="mt-2 text-3xl font-semibold text-neutral-900 dark:text-white">{sortedExperiments.length}</p>
            </div>
            <div className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-700 dark:bg-neutral-950">
              <p className="text-sm text-neutral-500 dark:text-neutral-400">Page size</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {rowsPerPageOptions.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => {
                      setPageSize(option)
                      setPage(1)
                    }}
                    className={`rounded-full border px-3 py-1 text-sm transition ${
                      pageSize === option
                        ? 'border-primary-600 bg-primary-600 text-white'
                        : 'border-neutral-300 bg-white text-neutral-700 hover:border-primary-400 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200'
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
              <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">Experiment table</h3>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">Click headers to sort or open a row for details.</p>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-600 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300">
              Sorted by {sortField} {sortDirection}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400">
                  <th className="px-4 py-3 cursor-pointer" onClick={() => toggleSort('name')}>
                    <div className="flex items-center gap-2">Name <ChevronsUpDown size={16} /> {renderSortIndicator('name')}</div>
                  </th>
                  <th className="px-4 py-3 cursor-pointer" onClick={() => toggleSort('date')}>
                    <div className="flex items-center gap-2">Date <ChevronsUpDown size={16} /> {renderSortIndicator('date')}</div>
                  </th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 cursor-pointer" onClick={() => toggleSort('accuracy')}>
                    <div className="flex items-center gap-2">Accuracy <ChevronsUpDown size={16} /> {renderSortIndicator('accuracy')}</div>
                  </th>
                  <th className="px-4 py-3 cursor-pointer" onClick={() => toggleSort('f1')}>
                    <div className="flex items-center gap-2">F1 Score <ChevronsUpDown size={16} /> {renderSortIndicator('f1')}</div>
                  </th>
                  <th className="px-4 py-3">Models</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {visibleExperiments.map((experiment) => (
                  <tr
                    key={experiment.id}
                    className="border-b border-neutral-200 dark:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                  >
                    <td className="px-4 py-4">
                      <button
                        type="button"
                        onClick={() => setSelectedExperiment(experiment)}
                        className="text-left font-medium text-neutral-900 hover:text-primary-600 dark:text-white dark:hover:text-primary-300"
                      >
                        {experiment.name}
                      </button>
                    </td>
                    <td className="px-4 py-4 text-neutral-600 dark:text-neutral-400">{experiment.date}</td>
                    <td className="px-4 py-4">
                      <Badge variant={statusVariants[experiment.status]}>{experiment.status}</Badge>
                    </td>
                    <td className="px-4 py-4 text-neutral-900 dark:text-white">{experiment.accuracy}%</td>
                    <td className="px-4 py-4 text-neutral-900 dark:text-white">{formatDecimal(experiment.f1)}</td>
                    <td className="px-4 py-4 text-neutral-600 dark:text-neutral-400">{experiment.models}</td>
                    <td className="px-4 py-4 space-x-2">
                      <Button variant="outline" size="sm" onClick={() => setSelectedExperiment(experiment)}>
                        Details
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleExportExperiment(experiment)} icon={<Download size={16} />}>
                        Export
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              Showing {visibleExperiments.length} of {sortedExperiments.length} experiments.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="text-sm text-neutral-700 dark:text-neutral-300">
                Page {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <AnimatePresence>
        {selectedExperiment && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/30"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedExperiment(null)}
            />
            <motion.aside
              className="fixed right-0 top-0 z-50 flex h-full w-full max-w-xl flex-col overflow-y-auto bg-white p-6 shadow-2xl dark:bg-neutral-950"
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'tween', duration: 0.25 }}
            >
              <div className="mb-6 flex items-center justify-between">
                <div>
                  <p className="text-sm uppercase tracking-[0.2em] text-neutral-500 dark:text-neutral-400">Experiment details</p>
                  <h2 className="mt-2 text-2xl font-semibold text-neutral-900 dark:text-white">{selectedExperiment.name}</h2>
                </div>
                <button
                  type="button"
                  aria-label="Close details drawer"
                  onClick={() => setSelectedExperiment(null)}
                  className="rounded-full border border-neutral-200 p-2 text-neutral-600 transition hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-900"
                >
                  <X size={20} />
                </button>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-700 dark:bg-neutral-900">
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">Status</p>
                  <Badge variant={statusVariants[selectedExperiment.status]} className="mt-2">{selectedExperiment.status}</Badge>
                </div>
                <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-700 dark:bg-neutral-900">
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">Dataset</p>
                  <p className="mt-2 text-base font-semibold text-neutral-900 dark:text-white">{selectedExperiment.dataset ?? 'Unknown'}</p>
                </div>
                <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-700 dark:bg-neutral-900">
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">Accuracy</p>
                  <p className="mt-2 text-base font-semibold text-neutral-900 dark:text-white">{selectedExperiment.accuracy}%</p>
                </div>
                <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-700 dark:bg-neutral-900">
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">F1 Score</p>
                  <p className="mt-2 text-base font-semibold text-neutral-900 dark:text-white">{formatDecimal(selectedExperiment.f1)}</p>
                </div>
              </div>

              <div className="mt-6 space-y-4">
                <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5 dark:border-neutral-700 dark:bg-neutral-900">
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">Run time</p>
                  <p className="mt-2 text-base font-semibold text-neutral-900 dark:text-white">{selectedExperiment.runtime ?? 'N/A'}</p>
                </div>
                <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5 dark:border-neutral-700 dark:bg-neutral-900">
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">Notes</p>
                  <p className="mt-2 text-base leading-7 text-neutral-800 dark:text-neutral-300">{selectedExperiment.notes ?? 'No notes available.'}</p>
                </div>
                <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5 dark:border-neutral-700 dark:bg-neutral-900">
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-neutral-500 dark:text-neutral-400">Parameters</p>
                    <Button size="sm" variant="secondary" onClick={() => handleExportExperiment(selectedExperiment)}>
                      Export details
                    </Button>
                  </div>
                  <div className="mt-4 space-y-2 text-sm text-neutral-800 dark:text-neutral-200">
                    {selectedExperiment.params ? (
                      Object.entries(selectedExperiment.params).map(([key, value]) => (
                        <div key={key} className="flex items-center justify-between rounded-2xl bg-white px-3 py-2 shadow-sm dark:bg-neutral-950">
                          <span className="font-medium text-neutral-700 dark:text-neutral-200">{key}</span>
                          <span className="text-neutral-500 dark:text-neutral-400">{String(value)}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-neutral-500 dark:text-neutral-400">No parameters recorded.</p>
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
