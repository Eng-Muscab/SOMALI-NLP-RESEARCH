import React, { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Upload,
  File as FileIcon,
  Trash2,
  Eye,
  Search,
  Loader2,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import {
  deleteDataset,
  listDatasets,
  previewDataset,
  uploadDataset,
} from '@services/datasetService'
import { getApiErrorMessage } from '@services/api'
import { useToast } from '../contexts/ToastContext'
import { DatasetMeta, DatasetPreview } from '../types/dataset'

const formatFileSize = (size: number) => {
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(2)} MB`
  }

  if (size >= 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }

  return `${size} B`
}

const Datasets = () => {
  const [datasets, setDatasets] = useState<DatasetMeta[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('All')
  const [preview, setPreview] = useState<DatasetPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [selectedPreviewId, setSelectedPreviewId] = useState<string | null>(null)
  const { showToast } = useToast()

  const datasetTypes = useMemo(() => {
    const types = new Set<string>()
    datasets.forEach((dataset) => {
      const normalizedType = dataset.type || dataset.filename.split('.').pop() || 'Unknown'
      types.add(normalizedType.toUpperCase())
    })
    return ['All', ...Array.from(types).sort()]
  }, [datasets])

  const filteredDatasets = useMemo(() => {
    const searchTerm = searchQuery.trim().toLowerCase()
    return datasets.filter((dataset) => {
      const filename = dataset.filename.toLowerCase()
      const datasetType = (dataset.type || dataset.filename.split('.').pop() || 'unknown').toLowerCase()
      const matchesName = !searchTerm || filename.includes(searchTerm)
      const matchesType = typeFilter === 'All' || datasetType === typeFilter.toLowerCase()
      return matchesName && matchesType
    })
  }, [datasets, searchQuery, typeFilter])

  const totalSize = useMemo(
    () => datasets.reduce((sum, dataset) => sum + (dataset.size || 0), 0),
    [datasets]
  )

  const totalRows = useMemo(
    () => datasets.reduce((sum, dataset) => sum + (dataset.rowCount || 0), 0),
    [datasets]
  )

  const uploadProgressWidthClass = useMemo(() => {
    if (uploadProgress <= 0) {
      return 'w-0'
    }
    if (uploadProgress >= 100) {
      return 'w-full'
    }
    if (uploadProgress >= 91) {
      return 'w-11/12'
    }
    if (uploadProgress >= 83) {
      return 'w-10/12'
    }
    if (uploadProgress >= 75) {
      return 'w-9/12'
    }
    if (uploadProgress >= 67) {
      return 'w-8/12'
    }
    if (uploadProgress >= 58) {
      return 'w-7/12'
    }
    if (uploadProgress >= 50) {
      return 'w-6/12'
    }
    if (uploadProgress >= 42) {
      return 'w-5/12'
    }
    if (uploadProgress >= 33) {
      return 'w-4/12'
    }
    if (uploadProgress >= 25) {
      return 'w-3/12'
    }
    if (uploadProgress >= 17) {
      return 'w-2/12'
    }
    return 'w-1/12'
  }, [uploadProgress])

  const loadDatasets = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await listDatasets()
      setDatasets(response.data)
    } catch (err) {
      const message = getApiErrorMessage(err, 'Unable to load datasets. Please try again later.')
      setError(message)
      showToast(message, 'error')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadDatasets()
  }, [])

  const handleUpload = async () => {
    if (!file) return
    setError(null)
    setSuccess(null)
    setIsUploading(true)
    setUploadProgress(0)

    try {
      await uploadDataset(file, setUploadProgress)
      setSuccess('Dataset uploaded successfully.')
      showToast('Dataset uploaded successfully.', 'success')
      setFile(null)
      await loadDatasets()
    } catch (err) {
      const message = getApiErrorMessage(err, 'Failed to upload dataset. Please check the file and try again.')
      setError(message)
      showToast(message, 'error')
    } finally {
      setIsUploading(false)
    }
  }

  const handlePreview = async (dataset: DatasetMeta) => {
    setSelectedPreviewId(dataset.id)
    setPreviewLoading(true)
    setPreview(null)
    setError(null)

    try {
      const response = await previewDataset(dataset.id)
      setPreview(response.data)
    } catch (err) {
      const message = getApiErrorMessage(err, 'Unable to load dataset preview.')
      setError(message)
      showToast(message, 'error')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleDelete = async (dataset: DatasetMeta) => {
    const confirmed = window.confirm(`Delete dataset "${dataset.filename}"?`)
    if (!confirmed) {
      return
    }

    setError(null)
    setSuccess(null)

    try {
      await deleteDataset(dataset.id)
      setSuccess('Dataset removed successfully.')
      showToast('Dataset removed successfully.', 'success')
      if (selectedPreviewId === dataset.id) {
        setPreview(null)
        setSelectedPreviewId(null)
      }
      await loadDatasets()
    } catch (err) {
      const message = getApiErrorMessage(err, 'Unable to delete dataset. Please try again.')
      setError(message)
      showToast(message, 'error')
    }
  }

  const handleDrag = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()

    if (event.type === 'dragenter' || event.type === 'dragover') {
      setDragActive(true)
    } else if (event.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    setDragActive(false)

    const droppedFile = event.dataTransfer.files?.[0]
    if (droppedFile) {
      setFile(droppedFile)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-neutral-900 dark:text-white mb-2">Datasets</h1>
        <p className="text-neutral-600 dark:text-neutral-400 max-w-2xl">
          Upload CSV or Excel dataset files, inspect dataset metadata, and preview dataset samples before training.
        </p>
      </div>

      {error && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-5 w-5 text-red-600" />
            <div>{error}</div>
          </div>
        </motion.div>
      )}

      {success && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"
        >
          <div className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" />
            <div>{success}</div>
          </div>
        </motion.div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-neutral-900 dark:text-white">Upload Dataset</h2>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">
                    Add new dataset files to your workspace for ingestion and preview.
                  </p>
                </div>
                <Badge variant="neutral" size="sm">
                  {datasets.length} uploaded
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`rounded-3xl border-2 border-dashed p-10 text-center transition-colors duration-200 ${
                  dragActive
                    ? 'border-primary-600 bg-primary-50/80 dark:bg-primary-900/20'
                    : 'border-neutral-300 bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-800'
                }`}
              >
                <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-3xl bg-white text-primary-600 shadow-sm dark:bg-neutral-900 dark:text-primary-300">
                  <Upload size={32} />
                </div>
                <div className="mt-6 space-y-2">
                  <p className="text-lg font-semibold text-neutral-900 dark:text-white">Drag and drop a file</p>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">
                    Supported formats: CSV, XLSX, XLS.
                  </p>
                </div>

                <label htmlFor="dataset-file-input" className="mt-6 inline-flex cursor-pointer items-center gap-2 rounded-full border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-900 shadow-sm transition hover:border-primary-400 hover:text-primary-600 dark:border-neutral-700 dark:bg-neutral-900 dark:text-white dark:hover:border-primary-500">
                  Select file
                </label>
                <input
                  id="dataset-file-input"
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  className="hidden"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                />
              </div>

              {file && (
                <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-3xl border border-primary-200 bg-primary-50 p-4 dark:border-primary-900/40 dark:bg-primary-900/20">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-100 text-primary-700 dark:bg-primary-900/80 dark:text-primary-300">
                        <FileIcon size={20} />
                      </div>
                      <div>
                        <p className="font-semibold text-neutral-900 dark:text-white">{file.name}</p>
                        <p className="text-sm text-neutral-600 dark:text-neutral-400">{formatFileSize(file.size)}</p>
                      </div>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => setFile(null)}>
                      Remove file
                    </Button>
                  </div>
                </motion.div>
              )}

              {isUploading && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm text-neutral-600 dark:text-neutral-400">
                    <span>Uploading dataset</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-700">
                    <div className={`h-full rounded-full bg-primary-600 transition-all ${uploadProgressWidthClass}`} />
                  </div>
                </div>
              )}

              <Button
                size="lg"
                className="w-full"
                onClick={handleUpload}
                disabled={!file || isUploading}
                isLoading={isUploading}
              >
                {file ? 'Upload Dataset' : 'Choose a file to upload'}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-neutral-900 dark:text-white">Active Dataset Library</h2>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">
                    Browse uploaded datasets and preview the first rows before using them.
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto]">
                  <Input
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    placeholder="Search datasets"
                    icon={<Search size={16} />}
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {datasetTypes.map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setTypeFilter(type)}
                    className={`rounded-full border px-3 py-1 text-sm transition ${
                      typeFilter === type
                        ? 'border-primary-600 bg-primary-600 text-white'
                        : 'border-neutral-300 bg-white text-neutral-700 hover:border-primary-400 hover:text-neutral-900 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200'
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>

              {isLoading ? (
                <div className="flex items-center justify-center rounded-3xl border border-dashed border-neutral-300 bg-neutral-50 p-10 text-neutral-500 dark:border-neutral-700 dark:bg-neutral-900">
                  <Loader2 className="mr-3 h-5 w-5 animate-spin" /> Loading datasets...
                </div>
              ) : filteredDatasets.length === 0 ? (
                <div className="rounded-3xl border border-dashed border-neutral-300 bg-neutral-50 p-10 text-center text-neutral-500 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-400">
                  <FileIcon className="mx-auto mb-3 h-10 w-10" />
                  <p className="font-semibold text-neutral-900 dark:text-white">No datasets found</p>
                  <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
                    Upload a dataset or adjust your search filters to see files.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredDatasets.map((dataset) => (
                    <motion.div
                      key={dataset.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2 }}
                      className="flex flex-col gap-3 rounded-3xl border border-neutral-200 bg-white p-4 shadow-sm transition hover:border-primary-300 dark:border-neutral-700 dark:bg-neutral-900"
                    >
                      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex items-center gap-4">
                          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-100 text-primary-700 dark:bg-primary-900/70 dark:text-primary-300">
                            <FileIcon size={20} />
                          </div>
                          <div>
                            <p className="font-semibold text-neutral-900 dark:text-white">{dataset.filename}</p>
                            <div className="flex flex-wrap items-center gap-2 text-sm text-neutral-500 dark:text-neutral-400">
                              <Badge size="sm">{dataset.type || 'CSV'}</Badge>
                              <span>{formatFileSize(dataset.size)}</span>
                              <span>{new Date(dataset.uploadedAt).toLocaleDateString()}</span>
                              {dataset.rowCount !== undefined && <span>{dataset.rowCount} rows</span>}
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            icon={<Eye size={16} />}
                            onClick={() => handlePreview(dataset)}
                          >
                            Preview
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            icon={<Trash2 size={16} />}
                            onClick={() => handleDelete(dataset)}
                          >
                            Delete
                          </Button>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}>
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-neutral-900 dark:text-white">Dataset Preview</h2>
                    <p className="text-sm text-neutral-600 dark:text-neutral-400">
                      View the first rows of the selected dataset before using it for training.
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {previewLoading ? (
                  <div className="flex items-center justify-center rounded-3xl border border-dashed border-neutral-300 bg-neutral-50 p-10 text-neutral-500 dark:border-neutral-700 dark:bg-neutral-900">
                    <Loader2 className="mr-3 h-5 w-5 animate-spin" /> Loading preview...
                  </div>
                ) : preview ? (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm text-neutral-500 dark:text-neutral-400">Previewing</p>
                        <h3 className="text-base font-semibold text-neutral-900 dark:text-white">{preview.filename}</h3>
                      </div>
                      <div className="rounded-full bg-neutral-100 px-3 py-1 text-sm text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
                        {preview.rows.length} rows shown
                      </div>
                    </div>
                    <div className="overflow-x-auto rounded-3xl border border-neutral-200 dark:border-neutral-700">
                      <table className="min-w-full divide-y divide-neutral-200 text-left text-sm dark:divide-neutral-700">
                        <thead className="bg-neutral-50 dark:bg-neutral-950">
                          <tr>
                            {preview.columns.map((column) => (
                              <th key={column} className="px-4 py-3 font-medium text-neutral-600 dark:text-neutral-300">
                                {column}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-200 bg-white dark:divide-neutral-700 dark:bg-neutral-900">
                          {preview.rows.length > 0 ? (
                            preview.rows.map((row, rowIndex) => (
                              <tr key={rowIndex} className="hover:bg-neutral-50 dark:hover:bg-neutral-800">
                                {row.map((cell, cellIndex) => (
                                  <td key={`${rowIndex}-${cellIndex}`} className="px-4 py-3 text-neutral-700 dark:text-neutral-300 whitespace-nowrap">
                                    {cell}
                                  </td>
                                ))}
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td colSpan={preview.columns.length} className="px-4 py-8 text-center text-neutral-500 dark:text-neutral-400">
                                No preview rows available.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-3xl border border-dashed border-neutral-300 bg-neutral-50 p-10 text-center text-neutral-500 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-400">
                    <FileIcon className="mx-auto mb-3 h-10 w-10" />
                    <p className="font-semibold text-neutral-900 dark:text-white">No preview selected</p>
                    <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
                      Select a dataset from the library to load a preview.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <h2 className="text-lg font-semibold text-neutral-900 dark:text-white">Dataset Insights</h2>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">
                    Quick metrics for uploaded datasets.
                  </p>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                  <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5 dark:border-neutral-700 dark:bg-neutral-900">
                    <p className="text-sm text-neutral-500 dark:text-neutral-400">Total datasets</p>
                    <p className="mt-2 text-3xl font-semibold text-neutral-900 dark:text-white">{datasets.length}</p>
                  </div>
                  <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5 dark:border-neutral-700 dark:bg-neutral-900">
                    <p className="text-sm text-neutral-500 dark:text-neutral-400">Total upload size</p>
                    <p className="mt-2 text-3xl font-semibold text-neutral-900 dark:text-white">{formatFileSize(totalSize)}</p>
                  </div>
                  <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5 dark:border-neutral-700 dark:bg-neutral-900">
                    <p className="text-sm text-neutral-500 dark:text-neutral-400">Known row count</p>
                    <p className="mt-2 text-3xl font-semibold text-neutral-900 dark:text-white">{totalRows}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

export default Datasets
