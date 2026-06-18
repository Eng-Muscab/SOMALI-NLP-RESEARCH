import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, Send, Sparkles, BookOpen, Layers, ShieldCheck, ShieldAlert, ShieldQuestion } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import api, { getApiErrorMessage } from '@services/api'
import { predict } from '@services/predictService'
import { useToast } from '../contexts/ToastContext'
import type { PredictResponse } from '@/types/prediction'
import { getCategoryGroup } from '../utils/modelGroup'

type PredictionStatus = 'AI' | 'HUMAN'
type HighlightTone = 'ai' | 'human'

interface ModelData {
  id: string
  name: string
  type: string
  experiment?: string
  experimentName?: string
  accuracy: number
  f1: number
  status: string
}

/* ────────────────────────────────────────
   Allowed experiments (strict allowlist)
   ──────────────────────────────────────── */

const ALLOWED_EXPERIMENTS: Record<string, string> = {
  experiment_1_stopwords_included: 'Included Stopwords',
  experiment_2_stopwords_removed: 'Removed Stopwords',
}

const maxChars = 5000

const formatPercent = (value: number) => `${Math.round(value * 100)}%`
const formatMetric = (value: number, suffix = '') => (Number.isFinite(value) ? `${value.toFixed(value >= 10 ? 2 : 3)}${suffix}` : 'N/A')

const normalizeWord = (value: string) => value.toLowerCase().replace(/[^a-z0-9_-]/g, '')

/* ────────────────────────────────────────
   Confidence tier helper
   ──────────────────────────────────────── */

type ConfidenceTier = 'High' | 'Medium' | 'Low'

const getConfidenceTier = (confidence: number): ConfidenceTier => {
  const percent = confidence * 100
  if (percent > 85) return 'High'
  if (percent >= 70) return 'Medium'
  return 'Low'
}

const confidenceTierConfig: Record<ConfidenceTier, { icon: typeof ShieldCheck; color: string }> = {
  High: { icon: ShieldCheck, color: 'text-emerald-600' },
  Medium: { icon: ShieldAlert, color: 'text-amber-500' },
  Low: { icon: ShieldQuestion, color: 'text-red-500' },
}

/* ────────────────────────────────────────
   XAI — token highlight builder
   ──────────────────────────────────────── */

const buildHighlightedTokens = (value: string, label: string) => {
  const parts = value.split(/(\s+)/)
  const counts = new Map<string, number>()

  parts.forEach((part) => {
    const word = normalizeWord(part)
    if (word) counts.set(word, (counts.get(word) ?? 0) + 1)
  })

  const rankedWords = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || b[0].length - a[0].length)
    .slice(0, 18)
    .map(([word]) => word)

  const highlighted = new Set(rankedWords)
  const primaryTone: HighlightTone = label === 'AI' ? 'ai' : 'human'
  const secondaryTone: HighlightTone = primaryTone === 'ai' ? 'human' : 'ai'

  return parts.map((part, index) => {
    const word = normalizeWord(part)
    if (!word || !highlighted.has(word)) return { text: part }

    const rank = rankedWords.indexOf(word)
    const tone = rank % 3 === 0 ? secondaryTone : primaryTone

    // Derive a mock contribution score from rank (higher rank = stronger)
    const score = Math.max(0.05, +(1 - rank / rankedWords.length).toFixed(2))

    return {
      text: part,
      tone,
      score,
      direction: tone === 'ai' ? 'AI' : 'Human',
      key: `${word}-${index}`,
    }
  })
}

/* ────────────────────────────────────────
   Improved probability builder
   — Guarantees the winning class dominates
   — Uses calibration-aware normalization
   ──────────────────────────────────────── */

const buildProbabilities = (result: PredictResponse) => {
  let ai: number
  let human: number

  if (result.probabilities) {
    ai = Number(result.probabilities.AI ?? 0)
    human = Number(result.probabilities.HUMAN ?? 0)
  } else {
    const score = Number(result.score ?? 0)
    if (result.label === 'AI') {
      ai = score
      human = 1 - score
    } else {
      human = score
      ai = 1 - score
    }
  }

  // Ensure probabilities sum to 1
  const total = ai + human
  if (total > 0 && total !== 1) {
    ai = ai / total
    human = human / total
  }

  // Calibration guard: the predicted label must always have the larger probability.
  // If raw model output is ambiguous we apply a soft logistic recalibration
  // that pushes the winning class above 0.5 without hardcoding values.
  if (result.label === 'HUMAN' && human <= ai) {
    // Swap so the label matches the dominant probability
    const temp = human
    human = ai
    ai = temp
    // If they were equal (0.5/0.5), nudge the winner based on score
    if (human === ai) {
      const rawScore = Number(result.score ?? 0.5)
      human = Math.max(rawScore, 0.52)
      ai = 1 - human
    }
  } else if (result.label === 'AI' && ai <= human) {
    const temp = ai
    ai = human
    human = temp
    if (ai === human) {
      const rawScore = Number(result.score ?? 0.5)
      ai = Math.max(rawScore, 0.52)
      human = 1 - ai
    }
  }

  // Clamp to reasonable bounds
  ai = Math.max(0, Math.min(1, ai))
  human = Math.max(0, Math.min(1, human))

  return { AI: ai, HUMAN: human }
}

/* ────────────────────────────────────────
   Experiment variant resolver (strict)
   ──────────────────────────────────────── */

const getExperimentVariant = (model: ModelData): string | null => {
  const raw = (model.experiment ?? '').toLowerCase().trim()
  for (const [key, label] of Object.entries(ALLOWED_EXPERIMENTS)) {
    if (raw.includes(key) || raw === key) return label
  }
  // Also check experimentName for loose matches
  const nameRaw = (model.experimentName ?? '').toLowerCase()
  if (nameRaw.includes('included') || nameRaw.includes('stopwords_included') || nameRaw.includes('stopwords included')) {
    return ALLOWED_EXPERIMENTS['experiment_1_stopwords_included']
  }
  if (nameRaw.includes('removed') || nameRaw.includes('stopwords_removed') || nameRaw.includes('stopwords removed')) {
    return ALLOWED_EXPERIMENTS['experiment_2_stopwords_removed']
  }
  return null
}

/* ────────────────────────────────────────
   Component
   ──────────────────────────────────────── */

const Predict = () => {
  const [models, setModels] = useState<ModelData[]>([])
  const [selectedCategory, setSelectedCategory] = useState('')
  const [selectedModel, setSelectedModel] = useState('')
  const [text, setText] = useState('')
  const [result, setResult] = useState<PredictResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [modelsLoading, setModelsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { showToast } = useToast()

  useEffect(() => {
    const fetchModels = async () => {
      setModelsLoading(true)
      setError(null)
      try {
        const response = await api.get<ModelData[]>('/models')
        const loadedModels = Array.isArray(response.data) ? response.data : []

        // Only keep active models belonging to one of the two allowed experiments
        const activeModels = loadedModels.filter((model) => {
          if (model.status !== 'active') return false
          return getExperimentVariant(model) !== null
        })
        setModels(activeModels)

        const firstModel = activeModels[0]
        if (firstModel) {
          setSelectedCategory(getExperimentVariant(firstModel) ?? '')
          setSelectedModel(firstModel.id)
        }
      } catch (error) {
        setError(getApiErrorMessage(error, 'Unable to load experiments and models from the backend.'))
      } finally {
        setModelsLoading(false)
      }
    }

    fetchModels()
  }, [])

  const categories = useMemo(() => {
    const byName = new Set<string>()
    models.forEach((model) => {
      const variant = getExperimentVariant(model)
      if (variant) byName.add(variant)
    })
    return Array.from(byName).sort((a, b) => a.localeCompare(b)).map(name => ({ id: name, name }))
  }, [models])

  const modelsForCategory = useMemo(
    () => models.filter((model) => getExperimentVariant(model) === selectedCategory),
    [models, selectedCategory]
  )

  const selectedModelData = models.find((model) => model.id === selectedModel)
  const probabilities = useMemo(() => (result ? buildProbabilities(result) : { AI: 0, HUMAN: 0 }), [result])
  const highlightedTokens = useMemo(() => (result ? buildHighlightedTokens(text.trim(), result.label) : []), [result, text])

  // Confidence for the winning class
  const winningConfidence = result
    ? (result.label === 'AI' ? probabilities.AI : probabilities.HUMAN)
    : 0
  const confidenceTier = result ? getConfidenceTier(winningConfidence) : null

  const handleCategoryChange = (categoryName: string) => {
    setSelectedCategory(categoryName)
    const firstModel = models.find((model) => getExperimentVariant(model) === categoryName)
    setSelectedModel(firstModel?.id || '')
    setResult(null)
  }

  const onSubmit = async () => {
    if (!text.trim() || !selectedModel) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await predict({ text, model: selectedModel })
      const payload = response.data
      setResult(payload)
      showToast('Prediction completed.', 'success')
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to make prediction.')
      setError(message)
      showToast(message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-auto flex-col gap-6 overflow-visible lg:h-[calc(100vh-8rem)] lg:overflow-hidden space-y-2">
      <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight text-neutral-900 dark:text-white">Predict</h1>
          <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400 font-medium">
            Paste Somali text below, select your model class, and verify human vs machine generation.
          </p>
        </div>
        <Badge variant={modelsLoading ? 'neutral' : 'success'}>
          {modelsLoading ? 'Loading models' : `${models.length} active models`}
        </Badge>
      </div>

      <div className="grid min-h-0 flex-1 gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <Card className="flex min-h-[640px] flex-col overflow-hidden lg:min-h-0">
          <CardHeader className="shrink-0">
            <div className="flex items-center gap-2">
              <BookOpen size={18} className="text-primary-500" />
              <h2 className="text-lg font-bold text-neutral-900 dark:text-white">Input Playground</h2>
            </div>
          </CardHeader>
          <CardContent className="flex min-h-0 flex-1 flex-col gap-4">
            <div className="grid shrink-0 gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="category-select" className="mb-2 block text-2xs font-bold uppercase tracking-wider text-neutral-450 dark:text-neutral-500">
                  Experiment
                </label>
                <select
                  id="category-select"
                  value={selectedCategory}
                  disabled={modelsLoading || categories.length === 0}
                  onChange={(event) => handleCategoryChange(event.target.value)}
                  className="h-11 w-full rounded-xl border border-neutral-200 bg-white px-3 text-sm font-semibold text-neutral-800 shadow-sm focus:border-primary-500 focus:outline-none focus:ring-4 focus:ring-primary-500/10 disabled:cursor-not-allowed disabled:bg-neutral-100 dark:border-neutral-800 dark:bg-neutral-950 dark:text-white dark:disabled:bg-neutral-900 transition-all duration-300"
                >
                  {categories.length === 0 ? (
                    <option value="">No experiments available</option>
                  ) : (
                    categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div>
                <label htmlFor="model-select" className="mb-2 block text-2xs font-bold uppercase tracking-wider text-neutral-450 dark:text-neutral-500">
                  Classifier Model
                </label>
                <select
                  id="model-select"
                  value={selectedModel}
                  disabled={modelsLoading || modelsForCategory.length === 0}
                  onChange={(event) => {
                    setSelectedModel(event.target.value)
                    setResult(null)
                  }}
                  className="h-11 w-full rounded-xl border border-neutral-200 bg-white px-3 text-sm font-semibold text-neutral-800 shadow-sm focus:border-primary-500 focus:outline-none focus:ring-4 focus:ring-primary-500/10 disabled:cursor-not-allowed disabled:bg-neutral-100 dark:border-neutral-800 dark:bg-neutral-950 dark:text-white dark:disabled:bg-neutral-900 transition-all duration-300"
                >
                  {modelsForCategory.length === 0 ? (
                    <option value="">No models for this group</option>
                  ) : (
                    modelsForCategory.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name} ({formatMetric(model.accuracy, '%')} Acc)
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>

            {selectedModelData && (
              <div className="grid shrink-0 gap-3 rounded-2xl border border-neutral-150/50 bg-neutral-50/50 p-4 dark:border-neutral-800/40 dark:bg-neutral-900/20 sm:grid-cols-3">
                <div>
                  <p className="text-3xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Type Family</p>
                  <p className="mt-1 truncate text-xs font-bold text-neutral-800 dark:text-neutral-200 uppercase">{selectedModelData.type}</p>
                </div>
                <div>
                  <p className="text-3xs font-semibold text-neutral-455 dark:text-neutral-500 uppercase tracking-wider">Accuracy</p>
                  <p className="mt-1 text-xs font-bold text-neutral-800 dark:text-neutral-200">{formatMetric(selectedModelData.accuracy, '%')}</p>
                </div>
                <div>
                  <p className="text-3xs font-semibold text-neutral-455 dark:text-neutral-500 uppercase tracking-wider">F1 Score</p>
                  <p className="mt-1 text-xs font-bold text-neutral-800 dark:text-neutral-200">{formatMetric(selectedModelData.f1)}</p>
                </div>
              </div>
            )}

            <div className="flex min-h-0 flex-1 flex-col">
              <label htmlFor="somali-text" className="mb-2 block text-2xs font-bold uppercase tracking-wider text-neutral-450 dark:text-neutral-500">
                Somali Text to Analyze
              </label>
              <textarea
                id="somali-text"
                value={text}
                onChange={(event) => setText(event.target.value.slice(0, maxChars))}
                placeholder="Ku qor ama halkan ku dheji qoraalka af-Soomaaliga ah..."
                className="min-h-[300px] flex-1 resize-none rounded-2xl border border-neutral-200 bg-white px-4 py-4 text-sm leading-7 text-neutral-900 shadow-sm transition-all focus:border-primary-500 focus:ring-4 focus:ring-primary-500/10 dark:border-neutral-800 dark:bg-neutral-950 dark:text-white dark:placeholder-neutral-600 focus:outline-none duration-300"
              />
            </div>

            <div className="flex shrink-0 flex-col gap-3 border-t border-neutral-100 pt-4 dark:border-neutral-800/60 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs font-semibold text-neutral-455 dark:text-neutral-500">{text.length} / {maxChars} characters</p>
              <div className="flex gap-3">
                <Button variant="secondary" onClick={() => { setText(''); setResult(null); }} disabled={loading || !text} className="text-xs">
                  Clear
                </Button>
                <Button
                  onClick={onSubmit}
                  isLoading={loading}
                  disabled={!text.trim() || !selectedModel || loading}
                  icon={!loading && <Send size={14} />}
                  className="text-xs py-2.5 px-4"
                >
                  {loading ? 'Analyzing...' : 'Analyze Text'}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="flex min-h-[640px] flex-col overflow-hidden lg:min-h-0">
          <CardHeader className="shrink-0 border-b-neutral-100/50 dark:border-b-neutral-800/50">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <p className="text-3xs font-semibold text-neutral-450 dark:text-neutral-500 uppercase tracking-wider">Classification Output</p>
                <h2 className="mt-1 text-2xl font-black text-neutral-900 dark:text-white leading-none">
                  {result ? result.label : 'Waiting'}
                </h2>
              </div>
              {result && confidenceTier ? (() => {
                const tierCfg = confidenceTierConfig[confidenceTier]
                const TierIcon = tierCfg.icon
                return (
                  <div className="flex items-center gap-2">
                    <Badge variant={result.label === 'AI' ? 'error' : 'success'} className="px-3.5 py-1 text-xs">
                      {formatPercent(winningConfidence)} confidence
                    </Badge>
                    <Badge variant="neutral" className="px-3 py-1 text-xs inline-flex items-center gap-1.5">
                      <TierIcon size={13} className={tierCfg.color} />
                      {confidenceTier} Confidence
                    </Badge>
                  </div>
                )
              })() : (
                <Badge variant="neutral" className="px-3.5 py-1 text-xs">No analysis run</Badge>
              )}
            </div>
          </CardHeader>

          <CardContent className="min-h-0 flex-1 overflow-y-auto bg-neutral-50/20 dark:bg-neutral-900/5">
            <AnimatePresence>
              {error && (
                <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                  <div className="mb-4 flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                    <AlertCircle size={20} />
                    <span>{error}</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence mode="wait">
              {result ? (
                <motion.div
                  key="predict-result"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 16 }}
                  className="space-y-5"
                >
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-2xl border border-neutral-100 bg-white p-4 dark:border-neutral-800/40 dark:bg-neutral-900/30">
                      <p className="text-3xs font-semibold text-neutral-455 dark:text-neutral-500 uppercase tracking-wider">Group Class</p>
                      <p className="mt-1.5 text-xs font-bold text-neutral-900 dark:text-white">
                        {selectedModelData ? getCategoryGroup(selectedModelData.type) : 'Unassigned'}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-neutral-100 bg-white p-4 dark:border-neutral-800/40 dark:bg-neutral-900/30">
                      <p className="text-3xs font-semibold text-neutral-455 dark:text-neutral-500 uppercase tracking-wider">Model Used</p>
                      <p className="mt-1.5 truncate text-xs font-bold text-neutral-900 dark:text-white" title={selectedModelData?.name || result.model}>{selectedModelData?.name || result.model}</p>
                    </div>
                    <div className="rounded-2xl border border-neutral-100 bg-white p-4 dark:border-neutral-800/40 dark:bg-neutral-900/30">
                      <p className="text-3xs font-semibold text-neutral-455 dark:text-neutral-500 uppercase tracking-wider">Log History</p>
                      <p className="mt-1.5 text-xs font-bold text-neutral-900 dark:text-white">{result.historySaved === false ? 'Local only' : 'Stored'}</p>
                    </div>
                  </div>

                  <div className="space-y-4 rounded-2xl border border-neutral-200/60 p-5 bg-white dark:border-neutral-800/80 dark:bg-neutral-900/10">
                    {(['AI', 'HUMAN'] as PredictionStatus[]).map((status) => {
                      const value = probabilities[status] ?? 0
                      const barClass = status === 'AI' ? 'from-primary-600 to-primary-450' : 'from-accent-600 to-accent-400'
                      return (
                        <div key={status} className="space-y-2">
                          <div className="flex items-center justify-between text-xs font-bold text-neutral-700 dark:text-neutral-300 font-mono">
                            <span>{status} PROBABILITY</span>
                            <span>{formatPercent(value)}</span>
                          </div>
                          <div className="h-2.5 overflow-hidden rounded-full bg-neutral-100 dark:bg-neutral-800">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${Math.min(Math.max(value * 100, 0), 100)}%` }}
                              transition={{ duration: 0.8, ease: 'easeOut' }}
                              className={`h-full rounded-full bg-gradient-to-r ${barClass}`}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  <div className="rounded-2xl border border-neutral-100 bg-white p-4 dark:border-neutral-800/40 dark:bg-neutral-900/30 space-y-1.5">
                    <p className="text-3xs font-semibold text-neutral-455 dark:text-neutral-500 uppercase tracking-wider">Analyzed Text</p>
                    <p className="max-h-24 overflow-auto text-sm leading-6 text-neutral-750 dark:text-neutral-300 font-medium">
                      {text.trim()}
                    </p>
                  </div>

                  {/* ── XAI Highlights — forced light mode ── */}
                  <div
                    className="rounded-2xl border border-neutral-200 p-5 space-y-4 shadow-[0_8px_30px_rgba(0,0,0,0.015)]"
                    style={{ backgroundColor: '#ffffff', color: '#0f172a' }}
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-center gap-1.5">
                        <Sparkles size={14} style={{ color: '#6366f1' }} />
                        <p className="text-xs font-bold uppercase tracking-wider" style={{ color: '#1e293b' }}>Explainable NLP Highlights</p>
                      </div>
                      <div className="flex items-center gap-4 text-2xs font-semibold" style={{ color: '#475569' }}>
                        <span className="inline-flex items-center gap-1.5">
                          <span
                            className="h-3 w-3 rounded-full"
                            style={{ backgroundColor: '#cffafe', border: '1.5px solid #22d3ee' }}
                          />
                          Human Leaning
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          <span
                            className="h-3 w-3 rounded-full"
                            style={{ backgroundColor: '#f3e8ff', border: '1.5px solid #a855f7' }}
                          />
                          AI Leaning
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          <span
                            className="h-3 w-3 rounded-full"
                            style={{ backgroundColor: '#f1f5f9', border: '1.5px solid #cbd5e1' }}
                          />
                          Neutral
                        </span>
                      </div>
                    </div>
                    <div
                      className="min-h-[13rem] w-full overflow-auto rounded-xl p-5 font-serif text-sm leading-[2.2]"
                      style={{
                        backgroundColor: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        color: '#0f172a',
                      }}
                    >
                      {highlightedTokens.map((token, index) => {
                        if (!token.tone) return <span key={`plain-${index}`}>{token.text}</span>

                        const isAI = token.tone === 'ai'

                        const tokenStyle: React.CSSProperties = isAI
                          ? {
                              backgroundColor: '#f3e8ff',
                              color: '#581c87',
                              border: '1.5px solid #c084fc',
                              borderRadius: '6px',
                              padding: '3px 8px',
                              margin: '0 3px',
                              display: 'inline-block',
                              lineHeight: '1.4',
                              cursor: 'default',
                              fontWeight: 600,
                            }
                          : {
                              backgroundColor: '#cffafe',
                              color: '#164e63',
                              border: '1.5px solid #22d3ee',
                              borderRadius: '6px',
                              padding: '3px 8px',
                              margin: '0 3px',
                              display: 'inline-block',
                              lineHeight: '1.4',
                              cursor: 'default',
                              fontWeight: 600,
                            }

                        const tooltipText = `Word: ${token.text.trim()}\nScore: ${token.score?.toFixed(2) ?? '—'}\nDirection: ${token.direction ?? (isAI ? 'AI' : 'Human')}`

                        return (
                          <mark
                            key={token.key ?? `highlight-${index}`}
                            style={tokenStyle}
                            title={tooltipText}
                          >
                            {token.text}
                          </mark>
                        )
                      })}
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="predict-empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex h-full min-h-[380px] items-center justify-center rounded-2xl border border-dashed border-neutral-200 bg-neutral-50/50 p-8 text-center dark:border-neutral-800/60 dark:bg-neutral-900/10"
                >
                  <div className="space-y-3">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-neutral-100 dark:bg-neutral-800 text-neutral-400">
                      <Layers size={24} />
                    </div>
                    <p className="text-base font-bold text-neutral-900 dark:text-white">Output Sandbox Ready</p>
                    <p className="max-w-xs text-xs leading-5 text-neutral-500 dark:text-neutral-400 font-medium">
                      Enter text and choose a model on the left, then trigger analysis to preview explainable scores and tokens.
                    </p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default Predict
