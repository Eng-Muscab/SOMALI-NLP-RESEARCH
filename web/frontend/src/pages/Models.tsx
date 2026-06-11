import React from 'react'
import { motion } from 'framer-motion'
import { Zap, TrendingUp, Activity } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'

const Models = () => {
  const models = [
    {
      id: 1,
      name: 'LinearSVC',
      type: 'SVM',
      accuracy: 96.2,
      f1: 0.961,
      status: 'active',
      icon: <Zap size={28} />,
      recommended: true,
      trained: '2024-01-15',
      params: '{"kernel": "linear", "C": 1.0}',
    },
    {
      id: 2,
      name: 'Logistic Regression',
      type: 'Linear Model',
      accuracy: 94.1,
      f1: 0.941,
      status: 'active',
      icon: <TrendingUp size={28} />,
      recommended: false,
      trained: '2024-01-14',
      params: '{"solver": "lbfgs", "max_iter": 100}',
    },
    {
      id: 3,
      name: 'Random Forest',
      type: 'Ensemble',
      accuracy: 93.5,
      f1: 0.935,
      status: 'inactive',
      icon: <Activity size={28} />,
      recommended: false,
      trained: '2024-01-13',
      params: '{"n_estimators": 100, "max_depth": 15}',
    },
  ]

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-neutral-900 dark:text-white mb-2">Models</h1>
        <p className="text-neutral-600 dark:text-neutral-400">Available pre-trained models for classification</p>
      </div>

      {/* Models Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {models.map((model, idx) => (
          <motion.div
            key={model.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1 }}
          >
            <Card className="h-full flex flex-col hover:shadow-lg transition-all duration-300 relative overflow-hidden group">
              {/* Recommended Badge */}
              {model.recommended && (
                <div className="absolute top-0 right-0 bg-gradient-to-br from-accent-600 to-accent-400 text-white px-3 py-1 rounded-bl-lg text-xs font-bold">
                  BEST
                </div>
              )}

              <CardHeader className={model.recommended ? 'pb-4 pt-6' : ''}>
                <div className="flex items-center space-x-3">
                  <div className={`p-3 rounded-lg ${model.recommended ? 'bg-accent-100 dark:bg-accent-900 text-accent-600 dark:text-accent-400' : 'bg-primary-100 dark:bg-primary-900 text-primary-600 dark:text-primary-400'}`}>
                    {model.icon}
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-neutral-900 dark:text-white">{model.name}</h3>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400">{model.type}</p>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="flex-1 space-y-4">
                {/* Status */}
                <Badge variant={model.status === 'active' ? 'success' : 'neutral'}>
                  {model.status === 'active' ? 'Active' : 'Inactive'}
                </Badge>

                {/* Metrics */}
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs font-medium text-neutral-600 dark:text-neutral-400">Accuracy</span>
                      <span className="text-sm font-bold text-neutral-900 dark:text-white">{model.accuracy}%</span>
                    </div>
                    <div className="h-2 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-primary-600 to-primary-400"
                        style={{ width: `${model.accuracy}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs font-medium text-neutral-600 dark:text-neutral-400">F1 Score</span>
                      <span className="text-sm font-bold text-neutral-900 dark:text-white">{model.f1}</span>
                    </div>
                    <div className="h-2 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-accent-600 to-accent-400"
                        style={{ width: `${model.f1 * 100}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Trained Date */}
                <div className="text-xs text-neutral-500 dark:text-neutral-400">
                  Trained: {model.trained}
                </div>
              </CardContent>

              {/* Actions */}
              <div className="px-6 py-4 border-t border-neutral-200 dark:border-neutral-700">
                <Button
                  variant={model.status === 'active' ? 'primary' : 'secondary'}
                  size="sm"
                  className="w-full"
                >
                  {model.status === 'active' ? 'Use Model' : 'Reactivate'}
                </Button>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Model Comparison */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
        <Card>
          <CardHeader>
            <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">Model Comparison</h3>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-700">
                    <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">Model</th>
                    <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">Type</th>
                    <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">Accuracy</th>
                    <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">F1 Score</th>
                    <th className="text-left py-3 px-4 font-semibold text-neutral-600 dark:text-neutral-400">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((model) => (
                    <tr
                      key={model.id}
                      className="border-b border-neutral-100 dark:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-700/50"
                    >
                      <td className="py-3 px-4">
                        <span className="font-medium text-neutral-900 dark:text-white">{model.name}</span>
                      </td>
                      <td className="py-3 px-4 text-neutral-600 dark:text-neutral-400">{model.type}</td>
                      <td className="py-3 px-4">
                        <span className="font-semibold text-neutral-900 dark:text-white">{model.accuracy}%</span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="font-semibold text-neutral-900 dark:text-white">{model.f1}</span>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={model.status === 'active' ? 'success' : 'neutral'}>
                          {model.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}

export default Models
