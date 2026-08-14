import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Newspaper, RefreshCw, Brain, CheckCircle2, Clock, PenSquare, X, Send, Trash2, User as UserIcon,
  ExternalLink, Globe2, AlertCircle,
} from 'lucide-react'
import api, { getApiErrorMessage } from '@services/api'
import { getNewsFeed, predict, unpublishPrediction } from '@services/predictService'
import type { NewsFeedItem } from '@services/predictService'
import { getExternalNews, getExternalSources } from '@services/newsService'
import type { ExternalNewsResponse, ExternalNewsSource } from '@services/newsService'
import { useToast } from '../contexts/ToastContext'
import { useAuth } from '../hooks/useAuth'
import { getExpVariant, experimentLabel, experimentTitle, ALL_EXPERIMENTS } from '../utils/modelGroup'
import ConfirmDialog from '../components/ui/ConfirmDialog'

interface ModelOption {
  id: string; name: string; status: string; accuracy: number
  experiment?: string; experimentName?: string
}

const MIN_CHARS = 50
// Unlimited, as on the Predict page — the counter reports length rather than counting
// down to a refusal.

const fmtTime = (iso: string | null) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function NewsFeed() {
  const [items, setItems] = useState<NewsFeedItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [removing, setRemoving] = useState<Set<string>>(new Set())
  const [pendingDelete, setPendingDelete] = useState<NewsFeedItem | null>(null)

  const [composeOpen, setComposeOpen] = useState(false)
  const [models, setModels] = useState<ModelOption[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)
  const [composeTitle, setComposeTitle] = useState('')
  const [composeText, setComposeText] = useState('')
  const [composeCat, setComposeCat] = useState(ALL_EXPERIMENTS)
  const [composeModel, setComposeModel] = useState('')
  const [composeSubmitting, setComposeSubmitting] = useState(false)
  const [composeError, setComposeError] = useState<string | null>(null)

  const { showToast } = useToast()
  const { user } = useAuth()

  const [sources, setSources] = useState<ExternalNewsSource[]>([])
  const [activeTab, setActiveTab] = useState<string>('platform')
  const [externalData, setExternalData] = useState<Record<string, ExternalNewsResponse>>({})
  const [externalLoading, setExternalLoading] = useState<Record<string, boolean>>({})

  useEffect(() => {
    getExternalSources().then(res => setSources(res.data)).catch(() => {})
  }, [])

  const loadExternal = async (sourceId: string, force = false) => {
    setExternalLoading(prev => ({ ...prev, [sourceId]: true }))
    try {
      const res = await getExternalNews(sourceId, 20, force)
      setExternalData(prev => ({ ...prev, [sourceId]: res.data }))
    } catch (e) {
      showToast(getApiErrorMessage(e, 'Failed to load news source.'), 'error')
    } finally {
      setExternalLoading(prev => ({ ...prev, [sourceId]: false }))
    }
  }

  const selectTab = (tab: string) => {
    setActiveTab(tab)
    if (tab !== 'platform' && !externalData[tab]) {
      loadExternal(tab)
    }
  }

  const refreshActive = () => {
    if (activeTab === 'platform') load()
    else loadExternal(activeTab, true)
  }

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getNewsFeed(40)
      setItems(res.data.items)
    } catch (e) {
      const msg = getApiErrorMessage(e, 'Failed to load news feed.')
      setError(msg)
      showToast(msg, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    api.get<ModelOption[]>('/models').then(res => {
      const all = (Array.isArray(res.data) ? res.data : []) as ModelOption[]
      setModels(all)
      const first = all.find(m => m.status === 'active') ?? all[0]
      if (first) setComposeModel(first.id)
    }).catch(() => {}).finally(() => setModelsLoading(false))
  }, [])

  const composeCategories = useMemo(() => {
    const s = new Set<string>()
    models.forEach(m => { const v = getExpVariant(m); if (v) s.add(v) })
    return Array.from(s).sort()
  }, [models])

  const composeCatModels = useMemo(() =>
    composeCat === ALL_EXPERIMENTS ? models : models.filter(m => getExpVariant(m) === composeCat),
    [models, composeCat])

  const onComposeCatChange = (cat: string) => {
    setComposeCat(cat)
    const pool = cat === ALL_EXPERIMENTS ? models : models.filter(m => getExpVariant(m) === cat)
    const first = pool.find(m => m.status === 'active') ?? pool[0]
    setComposeModel(first?.id || '')
  }

  const openCompose = () => {
    setComposeOpen(true)
    setComposeError(null)
  }

  const closeCompose = () => {
    setComposeOpen(false)
    setComposeTitle('')
    setComposeText('')
    setComposeError(null)
  }

  const activeCount = useMemo(() => models.filter(m => m.status === 'active').length, [models])
  // Backend returns models sorted by accuracy descending, so the first loaded one is
  // the best classifier the platform can actually run.
  const bestModel = useMemo(() => models.find(m => m.status === 'active'), [models])
  const selectedComposeModel = useMemo(
    () => models.find(m => m.id === composeModel), [models, composeModel])

  const canSubmitCompose = useMemo(
    () => composeText.trim().length >= MIN_CHARS && !!composeModel && !composeSubmitting,
    [composeText, composeModel, composeSubmitting]
  )

  const onSubmitCompose = async () => {
    if (!canSubmitCompose) return
    setComposeSubmitting(true)
    setComposeError(null)
    try {
      const res = await predict({ text: composeText, model: composeModel, title: composeTitle.trim(), publish: true })
      showToast('Post published to News Feed.', 'success')
      closeCompose()
      // Prepend an optimistic entry, then refresh to pick up server-computed fields.
      if (res.data.predictionId) {
        setItems(prev => [{
          id: res.data.predictionId!,
          title: composeTitle.trim() || composeText.trim().slice(0, 70),
          text: composeText.trim(),
          prediction: res.data.label,
          confidence: res.data.score ?? null,
          category: res.data.category ?? null,
          category_icon: res.data.category_icon ?? null,
          model: res.data.model ?? null,
          user_id: user?.id ?? null,
          author_name: user?.name || user?.email || null,
          created_at: new Date().toISOString(),
          published_at: new Date().toISOString(),
        }, ...prev])
      } else {
        load()
      }
    } catch (e) {
      setComposeError(getApiErrorMessage(e, 'Failed to publish post.'))
    } finally {
      setComposeSubmitting(false)
    }
  }

  const toggleExpanded = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const onDelete = async (id: string) => {
    setRemoving(prev => new Set(prev).add(id))
    try {
      await unpublishPrediction(id)
      setItems(prev => prev.filter(i => i.id !== id))
      setPendingDelete(null)
      showToast('Post removed from News Feed.', 'success')
    } catch (e) {
      showToast(getApiErrorMessage(e, 'Failed to remove post.'), 'error')
      setRemoving(prev => { const next = new Set(prev); next.delete(id); return next })
      setPendingDelete(null)
    }
  }

  return (
    <div className="space-y-6 pb-12">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-700 px-7 py-7 text-white shadow-xl"
      >
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-white/5 blur-3xl" />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="mb-2.5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-bold uppercase tracking-widest text-emerald-100">
              <Newspaper size={12} /> Platform Feed
            </div>
            <h1 className="text-[1.75rem] font-extrabold tracking-tight leading-tight">News Feed</h1>
            <p className="mt-1 text-sm text-emerald-100/90">
              Blog posts ay users-ku ka sameeyeen qoraalladooda la baaray — dhawaan
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {activeTab === 'platform' && (
              <button
                onClick={openCompose}
                className="flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-bold text-emerald-700 shadow transition-colors hover:bg-white/90"
              >
                <PenSquare size={14} /> New Post
              </button>
            )}
            <button
              onClick={refreshActive}
              className="flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2.5 text-sm font-bold hover:bg-white/20 transition-colors"
            >
              <RefreshCw size={14} className={(activeTab === 'platform' ? loading : externalLoading[activeTab]) ? 'animate-spin' : ''} /> Refresh
            </button>
          </div>
        </div>
      </motion.div>

      {/* ── Source Tabs ───────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2 overflow-x-auto pb-1">
        <button
          onClick={() => selectTab('platform')}
          className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-bold transition-colors ${
            activeTab === 'platform'
              ? 'bg-primary-600 text-white shadow'
              : 'bg-neutral-100 text-neutral-500 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-700'
          }`}
        >
          <Newspaper size={13} /> Platform Feed
        </button>
        {sources.map(s => (
          <button
            key={s.id}
            onClick={() => selectTab(s.id)}
            className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-bold transition-colors ${
              activeTab === s.id
                ? 'bg-primary-600 text-white shadow'
                : 'bg-neutral-100 text-neutral-500 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-700'
            }`}
          >
            <Globe2 size={13} /> {s.name}
          </button>
        ))}
      </div>

      {activeTab === 'platform' ? (
      <>
      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 dark:border-red-800/50 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-2xl bg-neutral-100 dark:bg-neutral-800" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-neutral-200 bg-white/50 py-16 text-center dark:border-neutral-800 dark:bg-neutral-900/30">
          <Newspaper size={28} className="text-neutral-300 dark:text-neutral-600" />
          <p className="text-sm font-semibold text-neutral-500 dark:text-neutral-400">Weli ma jiraan blog posts.</p>
          <button
            onClick={openCompose}
            className="mt-1 flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-primary-700"
          >
            <PenSquare size={14} /> Noqo qofka ugu horeeya ee post gareeya
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item, i) => {
            const isAI = item.prediction === 'AI'
            const isOwner = !!user?.id && user.id === item.user_id
            const isExpanded = expanded.has(item.id)
            const isLong = item.text.length > 320
            return (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ delay: Math.min(i * 0.02, 0.3) }}
                className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white shadow-sm dark:border-neutral-800/60 dark:bg-neutral-900"
              >
                <div className="flex items-start gap-4 p-5">
                  <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white shadow ${
                    isAI ? 'bg-gradient-to-br from-blue-500 to-blue-700' : 'bg-gradient-to-br from-orange-500 to-amber-600'
                  }`}>
                    {isAI ? <Brain size={16} /> : <CheckCircle2 size={16} />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1.5 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${
                        isAI
                          ? 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400'
                          : 'bg-orange-50 text-orange-600 dark:bg-orange-500/10 dark:text-orange-400'
                      }`}>
                        {isAI ? 'AI Generated' : 'Human Written'}
                      </span>
                      {item.category && item.category !== 'Unknown' && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-bold text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400">
                          {item.category_icon} {item.category}
                        </span>
                      )}
                      {typeof item.confidence === 'number' && (
                        <span className="text-[11px] font-bold text-neutral-400">{Math.round(item.confidence * 100)}% confidence</span>
                      )}
                      {isOwner && (
                        <button
                          onClick={() => setPendingDelete(item)}
                          disabled={removing.has(item.id)}
                          title="Remove from News Feed"
                          className="ml-auto flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold text-neutral-400 transition-colors hover:bg-red-50 hover:text-red-500 disabled:opacity-50 dark:hover:bg-red-500/10"
                        >
                          <Trash2 size={12} /> {removing.has(item.id) ? 'Removing…' : 'Remove'}
                        </button>
                      )}
                    </div>
                    <h3 className="text-[15px] font-bold text-neutral-900 dark:text-white">{item.title}</h3>
                    <p className={`mt-1 text-[13px] leading-relaxed text-neutral-600 dark:text-neutral-400 ${isExpanded ? '' : 'line-clamp-3'}`}>
                      {item.text}
                    </p>
                    {isLong && (
                      <button
                        onClick={() => toggleExpanded(item.id)}
                        className="mt-1 text-[11px] font-bold text-primary-600 hover:underline dark:text-primary-400"
                      >
                        {isExpanded ? 'Show less' : 'Read more'}
                      </button>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] font-semibold text-neutral-400">
                      {item.author_name && (
                        <span className="inline-flex items-center gap-1"><UserIcon size={11} /> {item.author_name}</span>
                      )}
                      <span className="inline-flex items-center gap-1"><Clock size={11} /> {fmtTime(item.published_at ?? item.created_at)}</span>
                      {item.model && <span>{item.model}</span>}
                    </div>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      )}
      </>
      ) : (
        <ExternalNewsPanel
          data={externalData[activeTab]}
          loading={!!externalLoading[activeTab]}
          onRetry={() => loadExternal(activeTab, true)}
        />
      )}

      {/* ── Compose Modal ─────────────────────────────────────────────── */}
      <AnimatePresence>
        {composeOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-end justify-center overflow-y-auto bg-slate-950/60 p-0 sm:items-center sm:p-6"
            onClick={closeCompose}
          >
            <motion.div
              initial={{ y: 60, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 60, opacity: 0 }}
              transition={{ type: 'spring', damping: 26, stiffness: 300 }}
              onClick={e => e.stopPropagation()}
              className="flex w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl border border-white/10 bg-white shadow-2xl shadow-black/40 ring-1 ring-black/5 dark:bg-[#0F172A] sm:rounded-3xl"
              style={{ maxHeight: 'min(88vh, 860px)' }}
            >
              <div className="relative shrink-0 overflow-hidden border-b border-neutral-100 bg-gradient-to-br from-emerald-50 via-white to-teal-50/60 px-7 py-6 dark:border-white/[0.07] dark:from-emerald-500/10 dark:via-[#0F172A] dark:to-teal-500/5">
                <div className="pointer-events-none absolute -right-10 -top-14 h-40 w-40 rounded-full bg-emerald-400/20 blur-3xl" />
                <div className="relative flex items-start gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-500/25">
                    <PenSquare size={20} className="text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-600 dark:text-emerald-400">News Feed</p>
                    <h2 className="mt-0.5 text-xl font-black tracking-tight text-neutral-900 dark:text-white">New Post</h2>
                    <p className="mt-1 text-[12px] leading-relaxed text-neutral-500 dark:text-neutral-400">
                      Qoraalkaaga waa la kala saarayaa AI ama Human, kadibna waa la daabacayaa.
                    </p>
                  </div>
                  <button
                    onClick={closeCompose}
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-neutral-200/70 bg-white/70 transition-colors hover:bg-neutral-100 dark:border-white/10 dark:bg-white/[0.04] dark:hover:bg-white/[0.09]"
                  >
                    <X size={16} className="text-neutral-500 dark:text-neutral-400" />
                  </button>
                </div>
              </div>

              <div className="min-h-0 flex-1 space-y-6 overflow-auto px-7 py-6">
                <div className="space-y-1.5">
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-neutral-400">Title (optional)</label>
                  <input
                    value={composeTitle}
                    onChange={e => setComposeTitle(e.target.value)}
                    placeholder="Ku qor cinwaan…"
                    className="h-11 w-full rounded-xl border border-neutral-200 bg-neutral-50 px-4 text-sm font-semibold text-neutral-800 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white"
                  />
                </div>

                <div className="rounded-2xl border border-neutral-200/70 bg-neutral-50/60 p-5 dark:border-white/[0.06] dark:bg-white/[0.02]">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Brain size={14} className="text-primary-600 dark:text-primary-400" />
                      <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 dark:text-neutral-400">Classifier</p>
                    </div>
                    <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-neutral-500 shadow-sm ring-1 ring-black/5 dark:bg-white/[0.06] dark:text-neutral-400 dark:ring-white/10">
                      {modelsLoading ? 'loading…' : `${activeCount} available of ${models.length}`}
                    </span>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label className="block text-[10px] font-bold uppercase tracking-widest text-neutral-400">
                        Experiment <span className="font-medium normal-case">(stopwords?)</span>
                      </label>
                      <select
                        value={composeCat}
                        disabled={modelsLoading || composeCategories.length === 0}
                        onChange={e => onComposeCatChange(e.target.value)}
                        className="h-11 w-full rounded-xl border border-neutral-200 bg-white px-4 text-sm font-semibold text-neutral-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20 disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white"
                      >
                        {composeCategories.length === 0
                          ? <option>{modelsLoading ? 'Loading…' : 'No experiments'}</option>
                          : <>
                              <option value={ALL_EXPERIMENTS}>All Experiments ({models.length} models)</option>
                              {composeCategories.map(c => (
                                <option key={c} value={c}>
                                  {experimentTitle(c)} ({models.filter(m => getExpVariant(m) === c).length})
                                </option>
                              ))}
                            </>
                        }
                      </select>
                    </div>

                    <div className="space-y-2">
                      <label className="block text-[10px] font-bold uppercase tracking-widest text-neutral-400">
                        Model <span className="font-medium normal-case">(sorted by accuracy)</span>
                      </label>
                      <select
                        value={composeModel}
                        disabled={modelsLoading || composeCatModels.length === 0}
                        onChange={e => setComposeModel(e.target.value)}
                        className="h-11 w-full rounded-xl border border-neutral-200 bg-white px-4 text-sm font-semibold text-neutral-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20 disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white"
                      >
                        {modelsLoading
                          ? <option>Loading models…</option>
                          : composeCatModels.length === 0
                            ? <option>No models available</option>
                            : composeCatModels.map(m => (
                                <option key={m.id} value={m.id} disabled={m.status !== 'active'}>
                                  {m.id === bestModel?.id ? '⭐ ' : ''}{m.name}
                                  {typeof m.accuracy === 'number' ? ` — ${m.accuracy.toFixed(2)}%` : ''}
                                  {m.status !== 'active' ? ' — [not loaded]' : ''}
                                </option>
                              ))
                        }
                      </select>
                    </div>
                  </div>

                  {selectedComposeModel && (
                    <div className="mt-4 grid grid-cols-3 gap-2.5 border-t border-neutral-200/70 pt-4 dark:border-white/[0.06]">
                      {[
                        ['Accuracy', typeof selectedComposeModel.accuracy === 'number' ? `${selectedComposeModel.accuracy.toFixed(2)}%` : '—'],
                        ['Experiment', experimentLabel(selectedComposeModel)],
                        ['State', selectedComposeModel.status === 'active' ? 'Ready' : 'Not loaded'],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl bg-white px-3 py-2.5 text-center shadow-sm ring-1 ring-black/5 dark:bg-white/[0.04] dark:ring-white/10">
                          <div className="text-[9px] font-bold uppercase tracking-widest text-neutral-400">{label}</div>
                          <div className="mt-0.5 text-[13px] font-extrabold text-neutral-800 dark:text-white">{value}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-neutral-400">Somali Text</label>
                    <span className="text-[11px] font-semibold tabular-nums text-neutral-400">
                      {composeText.length.toLocaleString()} characters
                    </span>
                  </div>
                  <textarea
                    value={composeText}
                    onChange={e => setComposeText(e.target.value)}
                    placeholder="Ku qor qoraalka af-Soomaaliga ah ee aad rabto in la testing gareeyo oo la post gareeyo…"
                    className="w-full min-h-[180px] resize-y rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3.5 text-sm leading-6 text-neutral-900 placeholder-neutral-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white dark:placeholder-neutral-600"
                  />
                  {composeText.trim().length > 0 && composeText.trim().length < MIN_CHARS && (
                    <p className="text-[11px] font-semibold text-amber-500">
                      Fadlan geli ugu yaraan hal paragraph ({MIN_CHARS}+ xaraf).
                    </p>
                  )}
                </div>

                {composeError && (
                  <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[12px] font-semibold text-red-600 dark:border-red-800/40 dark:bg-red-900/20 dark:text-red-400">
                    {composeError}
                  </p>
                )}
              </div>

              <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t border-neutral-100 bg-neutral-50/80 px-7 py-4 dark:border-white/[0.05] dark:bg-white/[0.02]">
                <p className="text-[11px] text-neutral-400 dark:text-neutral-500">
                  Waxaa lagu daabici doonaa magacaaga iyo natiijada AI vs Human.
                </p>
                <button
                  onClick={onSubmitCompose}
                  disabled={!canSubmitCompose}
                  className="flex shrink-0 items-center gap-2 rounded-xl bg-primary-600 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary-500/25 transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {composeSubmitting
                    ? <><div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Publishing…</>
                    : <><Send size={14} /> Publish Post</>}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Confirm remove ────────────────────────────────────────────── */}
      <ConfirmDialog
        open={pendingDelete !== null}
        tone="danger"
        title="Remove this post from the News Feed?"
        confirmLabel="Yes, remove"
        cancelLabel="Keep it"
        busy={pendingDelete ? removing.has(pendingDelete.id) : false}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => { if (pendingDelete) onDelete(pendingDelete.id) }}
        message={
          <>
            “<strong>{pendingDelete?.title}</strong>” will no longer be visible to anyone on the News Feed.
            This cannot be undone — you would have to publish it again from the Predict page.
          </>
        }
      />
    </div>
  )
}

/* ── External source panel (BBC Somali, VOA Somali, etc.) ─────────────── */
function ExternalNewsPanel({
  data, loading, onRetry,
}: {
  data: ExternalNewsResponse | undefined
  loading: boolean
  onRetry: () => void
}) {
  if (loading && !data) {
    return (
      <div className="space-y-3">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-28 animate-pulse rounded-2xl bg-neutral-100 dark:bg-neutral-800" />
        ))}
      </div>
    )
  }

  if (!data || (data.error && data.items.length === 0)) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-neutral-200 bg-white/50 py-16 text-center dark:border-neutral-800 dark:bg-neutral-900/30">
        <AlertCircle size={28} className="text-neutral-300 dark:text-neutral-600" />
        <p className="text-sm font-semibold text-neutral-500 dark:text-neutral-400">
          {data?.error || 'Failed to load this news source.'}
        </p>
        <button
          onClick={onRetry}
          className="mt-1 flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-primary-700"
        >
          <RefreshCw size={14} /> Try again
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {data.error && (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-[12px] font-semibold text-amber-700 dark:border-amber-800/40 dark:bg-amber-900/20 dark:text-amber-400">
          {data.error}
        </p>
      )}
      {data.items.map((item, i) => (
        <motion.a
          key={item.link + i}
          href={item.link}
          target="_blank"
          rel="noopener noreferrer"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: Math.min(i * 0.02, 0.3) }}
          className="flex items-start gap-4 overflow-hidden rounded-2xl border border-neutral-200/70 bg-white p-5 shadow-sm transition-colors hover:border-primary-200 dark:border-neutral-800/60 dark:bg-neutral-900 dark:hover:border-primary-800"
        >
          {item.thumbnail ? (
            <img
              src={item.thumbnail}
              alt=""
              className="h-16 w-16 shrink-0 rounded-xl object-cover"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          ) : (
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-700 text-white shadow">
              <Newspaper size={20} />
            </span>
          )}
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex items-center gap-2">
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                {item.source_name}
              </span>
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-neutral-400">
                <Clock size={11} /> {fmtTime(item.published_at)}
              </span>
            </div>
            <h3 className="text-[15px] font-bold leading-snug text-neutral-900 dark:text-white">{item.title}</h3>
            {item.description && (
              <p className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-neutral-600 dark:text-neutral-400">
                {item.description}
              </p>
            )}
            <span className="mt-2 inline-flex items-center gap-1 text-[11px] font-bold text-primary-600 dark:text-primary-400">
              Read full article <ExternalLink size={11} />
            </span>
          </div>
        </motion.a>
      ))}
    </div>
  )
}
