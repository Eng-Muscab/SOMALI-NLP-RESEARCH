import React, { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { predict } from '@services/predictService'
import type { PredictResponse, PredictionHistoryItem } from '@types/prediction'

type PredictionStatus = 'AI' | 'HUMAN'

const HISTORY_KEY = 'somali_ai_predict_history'
const maxChars = 5000

const formatPercent = (value: number) => `${Math.round(value * 100)}%`

const buildProbabilities = (result: PredictResponse) => {
  if (result.probabilities) {
    return {
      AI: Number(result.probabilities.AI ?? 0),
      HUMAN: Number(result.probabilities.HUMAN ?? 0),
    }
  }

  const score = Number(result.score ?? 0)
  if (result.label === 'AI') {
    return { AI: score, HUMAN: 1 - score }
  }

  if (result.label === 'HUMAN') {
    return { AI: 1 - score, HUMAN: score }
  }

  return { AI: score, HUMAN: 1 - score }
}

const Predict = () => {
  const [text, setText] = useState('')
  const [result, setResult] = useState<PredictResponse | null>(null)
  const [history, setHistory] = useState<PredictionHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const stored = localStorage.getItem(HISTORY_KEY)
    if (stored) {
      try {
        setHistory(JSON.parse(stored))
      } catch {
        setHistory([])
      }
    }
  }, [])

  const saveHistoryItem = (item: PredictionHistoryItem) => {
    setHistory((prev) => {
      const next = [item, ...prev].slice(0, 10)
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
      return next
    })
  }

  const onSubmit = async () => {
    if (!text.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await predict({ text })
      const payload = response.data
      setResult(payload)

      const probabilities = buildProbabilities(payload)
      saveHistoryItem({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        text,
        label: payload.label,
        score: Number(payload.score ?? 0),
        probabilities,
        model: payload.model ?? 'Somali detector v1',
        createdAt: new Date().toISOString(),
      })
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Failed to make prediction')
    } finally {
      setLoading(false)
    }
  }

  const probabilities = useMemo(() => (result ? buildProbabilities(result) : { AI: 0, HUMAN: 0 }), [result])
  const charCount = text.length

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-neutral-900 dark:text-white mb-2">Somali AI Detector</h1>
        <p className="text-neutral-600 dark:text-neutral-400">Paste Somali text and detect whether it was written by AI or a human.</p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.7fr_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-neutral-950 dark:text-white">Detect Somali text</h2>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">Large text input, live counter, and fast predictions.</p>
                </div>
                <Badge variant="primary">Realtime</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <label htmlFor="somali-text" className="block text-sm font-medium text-neutral-900 dark:text-white mb-3">
                  Somali text input
                </label>
                <textarea
                  id="somali-text"
                  value={text}
                  onChange={(e) => setText(e.target.value.slice(0, maxChars))}
                  placeholder="Write or paste Somali text here. The detector supports long-form paragraphs and short sentences."
                  className="w-full min-h-[300px] rounded-3xl border border-neutral-200 bg-white px-5 py-4 text-base text-neutral-900 shadow-sm transition-all duration-200 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-neutral-700 dark:bg-neutral-950 dark:text-white dark:placeholder-neutral-500"
                />
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">{charCount} / {maxChars} characters</p>
                  <div className="h-2 w-full max-w-xs overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-700">
                    <div
                      className="h-full bg-gradient-to-r from-primary-600 to-cyan-400 transition-all duration-300"
                      style={{ width: `${Math.min((charCount / maxChars) * 100, 100)}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Button
                  onClick={onSubmit}
                  isLoading={loading}
                  disabled={!text.trim() || loading}
                  size="lg"
                  className="w-full"
                  icon={!loading && <Send size={20} />}
                >
                  {loading ? 'Analyzing text...' : 'Predict'}
                </Button>
                <Button
                  variant="secondary"
                  size="lg"
                  onClick={() => setText('')}
                  className="w-full"
                >
                  Clear input
                </Button>
              </div>
            </CardContent>
          </Card>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
              >
                <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20">
                  <CardContent className="p-4 flex items-center gap-3 text-red-700 dark:text-red-300">
                    <AlertCircle size={20} />
                    <span>{error}</span>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence mode="wait">
            {result && (
              <motion.div
                key="predict-result"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
                className="space-y-6"
              >
                <div className="grid gap-6 xl:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm text-neutral-500 dark:text-neutral-400">Result</p>
                          <h3 className="text-xl font-semibold text-neutral-950 dark:text-white">AI or Human?</h3>
                        </div>
                        <Badge variant={result.label === 'AI' ? 'error' : 'success'} size="md">
                          {result.label}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <div className="rounded-3xl bg-neutral-100 p-6 text-center dark:bg-neutral-900">
                        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-neutral-500 dark:text-neutral-400">Confidence</p>
                        <p className="mt-4 text-5xl font-semibold text-neutral-950 dark:text-white">
                          {typeof result.score === 'number' ? `${(result.score * 100).toFixed(1)}%` : 'N/A'}
                        </p>
                        <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">Confidence level for predicted label</p>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">Probability scores</h3>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      {(['AI', 'HUMAN'] as PredictionStatus[]).map((status) => {
                        const value = probabilities[status] ?? 0
                        const statusClass = status === 'AI' ? 'from-primary-600 to-primary-400' : 'from-accent-600 to-accent-400'
                        return (
                          <div key={status} className="space-y-2">
                            <div className="flex items-center justify-between text-sm font-medium text-neutral-700 dark:text-neutral-300">
                              <span>{status}</span>
                              <span>{formatPercent(value)}</span>
                            </div>
                            <div className="h-3 rounded-full bg-neutral-200 dark:bg-neutral-700 overflow-hidden">
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.min(Math.max(value * 100, 0), 100)}%` }}
                                transition={{ duration: 0.8, ease: 'easeOut' }}
                                className={`h-full rounded-full bg-gradient-to-r ${statusClass}`}
                              />
                            </div>
                          </div>
                        )
                      })}
                    </CardContent>
                  </Card>
                </div>

                <div className="grid gap-6 xl:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">Prediction details</h3>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="rounded-3xl bg-neutral-100 p-4 dark:bg-neutral-900">
                          <p className="text-sm text-neutral-500 dark:text-neutral-400">Model</p>
                          <p className="mt-2 font-semibold text-neutral-950 dark:text-white">{result.model || 'Somali detector v1'}</p>
                        </div>
                        <div className="rounded-3xl bg-neutral-100 p-4 dark:bg-neutral-900">
                          <p className="text-sm text-neutral-500 dark:text-neutral-400">Text length</p>
                          <p className="mt-2 font-semibold text-neutral-950 dark:text-white">{text.length} chars</p>
                        </div>
                      </div>
                      <div className="rounded-3xl bg-neutral-100 p-4 dark:bg-neutral-900">
                        <p className="text-sm text-neutral-500 dark:text-neutral-400">Sample</p>
                        <p className="mt-2 text-sm leading-6 text-neutral-700 dark:text-neutral-300 line-clamp-4">{text.trim() || 'Text preview unavailable'}</p>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">Prediction actions</h3>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <Button variant="secondary" size="md" className="w-full" onClick={() => setText(text)}>
                        Review text
                      </Button>
                      <Button variant="outline" size="md" className="w-full">
                        Copy label
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">Prediction history</p>
                  <h3 className="text-lg font-semibold text-neutral-950 dark:text-white">Recent runs</h3>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setHistory([])
                    localStorage.removeItem(HISTORY_KEY)
                  }}
                >
                  Clear
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {history.length === 0 ? (
                <div className="rounded-3xl border border-dashed border-neutral-200 bg-neutral-50 px-5 py-8 text-center dark:border-neutral-700 dark:bg-neutral-950">
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">No past predictions yet. Your last predictions will appear here automatically.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {history.map((item) => (
                    <div key={item.id} className="rounded-3xl border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-700 dark:bg-neutral-950">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-neutral-900 dark:text-white">{item.label}</p>
                          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">{new Date(item.createdAt).toLocaleString()}</p>
                        </div>
                        <Badge variant={item.label === 'AI' ? 'error' : 'success'}>{item.label}</Badge>
                      </div>
                      <div className="mt-4 space-y-3">
                        <div className="flex items-center justify-between text-sm text-neutral-500 dark:text-neutral-400">
                          <span>Confidence</span>
                          <span>{(item.score * 100).toFixed(1)}%</span>
                        </div>
                        <div className="h-2 rounded-full bg-neutral-200 dark:bg-neutral-700 overflow-hidden">
                          <div className="h-full w-full bg-gradient-to-r from-primary-600 to-cyan-400" style={{ width: `${Math.min(Math.max(item.score * 100, 0), 100)}%` }} />
                        </div>
                        <p className="text-sm text-neutral-500 dark:text-neutral-400 line-clamp-3">{item.text}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  )
}

export default Predict
