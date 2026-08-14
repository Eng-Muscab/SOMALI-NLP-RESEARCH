const CATEGORY_LABELS = {
  deep_learning: 'Deep Learning',
  traditional_ml: 'Traditional Model',
  transformers: 'Transformer',
} as const

const CATEGORY_KEYWORDS = {
  deep_learning: ['deep_learning', 'keras', 'lstm', 'cnn', 'gru', 'bilstm'],
  traditional_ml: ['traditional_ml', 'sklearn', 'svc', 'svm', 'linear', 'logistic', 'forest', 'xgboost', 'randomforest'],
  transformers: ['transformers', 'transformer', 'bert', 'roberta', 'afriberta', 'somberta', 'afroxlmr', 'xlm', 'mbert'],
} as const

const normalizeToken = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')

const detectCategoryFromText = (value: string | undefined): keyof typeof CATEGORY_LABELS | null => {
  if (!value) return null

  const normalized = normalizeToken(value)
  for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS) as Array<[keyof typeof CATEGORY_LABELS, readonly string[]]>) {
    if (keywords.some((keyword) => normalized.includes(keyword))) {
      return category
    }
  }

  return null
}

export const getCategoryGroup = (type: string | undefined, metadataPath?: string): string => {
  const folderCategory = detectCategoryFromText(metadataPath)
  if (folderCategory) return CATEGORY_LABELS[folderCategory]

  const typeCategory = detectCategoryFromText(type)
  if (typeCategory) return CATEGORY_LABELS[typeCategory]

  return 'Traditional Model'
}

/* ── Experiment variant grouping (stopwords included/removed) ─────────────── */
export const EXP_LABELS: Record<string, string> = {
  experiment_1_stopwords_included: 'Experiment 1 — Stopwords Included',
  experiment_2_stopwords_removed:  'Experiment 2 — Stopwords Removed',
}
export const ALL_EXPERIMENTS = 'All Experiments'

export interface ExperimentTaggedModel {
  experiment?: string
  experimentName?: string
}

export const getExpVariant = (m: ExperimentTaggedModel): string => {
  const raw = (m.experiment ?? '').toLowerCase()
  for (const [k, v] of Object.entries(EXP_LABELS)) if (raw.includes(k)) return v
  const n = (m.experimentName ?? '').toLowerCase()
  if (n.includes('included')) return EXP_LABELS['experiment_1_stopwords_included']
  if (n.includes('removed'))  return EXP_LABELS['experiment_2_stopwords_removed']
  if (m.experimentName && m.experimentName !== 'Unassigned') return m.experimentName
  return 'All Models'
}

/** Turn an experiment folder name into what the experiment actually was. The two runs
 *  differ only in whether Somali stopwords were kept, and that is the fact a reader
 *  choosing between them needs — not the directory it was written to. */
export const experimentTitle = (raw?: string | null) => {
  const v = (raw || '').toLowerCase()
  if (v.includes('2') || v.includes('removed')) return 'Experiment 2 — Stopwords Removed'
  if (v.includes('1') || v.includes('included')) return 'Experiment 1 — Stopwords Included'
  return raw || 'Unassigned'
}

/** The short form, for metric strips where the full title will not fit. */
export const experimentLabel = (m?: { experiment?: string; experimentName?: string } | null) => {
  const v = `${m?.experimentName || ''} ${m?.experiment || ''}`.toLowerCase()
  if (v.includes('2') || v.includes('removed')) return 'Exp 2 · No stopwords'
  if (v.includes('1') || v.includes('included')) return 'Exp 1 · With stopwords'
  return '—'
}
