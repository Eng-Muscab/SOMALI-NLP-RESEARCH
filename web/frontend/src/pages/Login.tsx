import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertCircle, CheckCircle, Mail, Lock } from 'lucide-react'
import { Card, CardContent } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Button } from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'
import { getApiErrorMessage } from '../services/api'
import { useToast } from '../contexts/ToastContext'

const Login = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const navigate = useNavigate()
  const { login } = useAuth()
  const { showToast } = useToast()

  const validate = () => {
    if (!email.trim() || !password.trim()) {
      return 'Please fill in all fields.'
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return 'Please enter a valid email address.'
    }
    return ''
  }

  const submit = async () => {
    const validationMessage = validate()
    if (validationMessage) {
      setError(validationMessage)
      setSuccess('')
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      await login({ email: email.trim(), password })
      setSuccess('Logged in successfully! Redirecting...')
      showToast('Logged in successfully.', 'success')
      setTimeout(() => navigate('/', { replace: true }), 800)
    } catch (e) {
      const message = getApiErrorMessage(e, 'Login failed. Please try again.')
      setError(message)
      showToast(message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-tr from-neutral-50 via-primary-50/10 to-accent-50/10 dark:from-neutral-950 dark:via-neutral-900/40 dark:to-neutral-950 flex items-center justify-center p-4 transition-colors duration-300">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        <Card className="shadow-[0_20px_50px_rgba(79,70,229,0.06)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.3)] bg-white/80 dark:bg-neutral-900/80 backdrop-blur-md border border-neutral-200/50 dark:border-neutral-800/80">
          <CardContent className="p-8 space-y-6">
            <div className="text-center space-y-3">
              <div className="flex justify-center mb-2">
                <div className="w-14 h-14 bg-gradient-to-tr from-primary-600 to-accent-500 rounded-2xl flex items-center justify-center shadow-lg shadow-primary-500/20">
                  <span className="text-white font-black text-2xl">S</span>
                </div>
              </div>
              <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-neutral-900 to-neutral-700 dark:from-white dark:to-neutral-300 bg-clip-text text-transparent">
                Somali NLP Research
              </h1>
              <p className="text-sm text-neutral-500 dark:text-neutral-400 font-medium">Sign in to your workspace</p>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center space-x-2.5 p-3.5 bg-red-500/5 dark:bg-red-500/10 border border-red-200/50 dark:border-red-500/20 rounded-xl"
              >
                <AlertCircle className="text-red-550 dark:text-red-400 flex-shrink-0" size={18} />
                <p className="text-sm font-semibold text-red-750 dark:text-red-300 leading-none">{error}</p>
              </motion.div>
            )}

            {success && (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center space-x-2.5 p-3.5 bg-accent-500/5 dark:bg-accent-500/10 border border-accent-200/50 dark:border-accent-500/20 rounded-xl"
              >
                <CheckCircle className="text-accent-550 dark:text-accent-405 flex-shrink-0" size={18} />
                <p className="text-sm font-semibold text-accent-750 dark:text-accent-300 leading-none">{success}</p>
              </motion.div>
            )}

            <div className="space-y-4">
              <Input
                label="Email Address"
                type="email"
                icon={<Mail size={16} />}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                disabled={loading}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
              />

              <Input
                label="Password"
                type="password"
                icon={<Lock size={16} />}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                disabled={loading}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
              />
            </div>

            <Button onClick={submit} isLoading={loading} disabled={loading} size="lg" className="w-full mt-2 py-2.5">
              Sign In
            </Button>

            <div className="text-center space-y-3 text-sm border-t border-neutral-100 dark:border-neutral-800/60 pt-4">
              <p className="text-neutral-500 dark:text-neutral-400 font-medium">
                Don't have an account?{' '}
                <Link to="/register" className="text-primary-600 dark:text-primary-400 font-bold hover:underline">
                  Sign up
                </Link>
              </p>
              <p className="text-xs text-neutral-450 dark:text-neutral-500">
                This is a secure research platform for Somali NLP studies.
              </p>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}

export default Login
