import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertCircle, CheckCircle2, Eye, EyeOff, Mail, Lock, LogIn, Sun, Moon } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { getApiErrorMessage } from '../services/api'
import { useToast } from '../contexts/ToastContext'
import { useTheme } from '../contexts/ThemeContext'

const BG_LIGHT = 'linear-gradient(175deg, #5ab8ea 0%, #9dd5f5 40%, #d0ecfb 72%, #e8f6ff 100%)'
const BG_DARK  = 'linear-gradient(175deg, #071521 0%, #091C30 40%, #0A2240 70%, #071521 100%)'

const Login = () => {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')
  const [success, setSuccess]   = useState('')
  const navigate                = useNavigate()
  const { login }               = useAuth()
  const { showToast }           = useToast()
  const { theme, toggleTheme }  = useTheme()
  const dk = theme === 'dark'

  const submit = async () => {
    if (!email.trim() || !password.trim()) { setError('Please fill in all fields.'); return }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError('Please enter a valid email address.'); return }
    setLoading(true); setError(''); setSuccess('')
    try {
      await login({ email: email.trim(), password })
      setSuccess('Signed in! Redirecting…')
      showToast('Signed in successfully.', 'success')
      setTimeout(() => navigate('/', { replace: true }), 800)
    } catch (e) {
      const msg = getApiErrorMessage(e, 'Login failed. Please try again.')
      setError(msg); showToast(msg, 'error')
    } finally { setLoading(false) }
  }

  const inputCls = dk
    ? 'h-[52px] w-full rounded-[14px] border border-sky-700/40 bg-[#0A2240]/80 pl-11 pr-4 text-sm text-sky-50 placeholder-sky-700 outline-none transition-all focus:border-sky-500/60 focus:ring-2 focus:ring-sky-500/20 disabled:opacity-60'
    : 'h-[52px] w-full rounded-[14px] border border-sky-200/70 bg-white/65 pl-11 pr-4 text-sm text-slate-700 placeholder-slate-400 outline-none transition-all focus:border-sky-400/60 focus:bg-white/80 focus:ring-2 focus:ring-sky-300/35 disabled:opacity-60'

  return (
    <div
      className="relative flex min-h-screen items-center justify-center overflow-hidden p-6 transition-colors duration-500"
      style={{ background: dk ? BG_DARK : BG_LIGHT }}
    >
      {/* Dark mode toggle */}
      <button
        onClick={toggleTheme}
        aria-label="Toggle dark mode"
        className="fixed right-4 top-4 z-50 flex h-10 w-10 items-center justify-center rounded-full transition-all hover:scale-105"
        style={{
          background: dk ? 'rgba(9,28,48,0.85)' : 'rgba(255,255,255,0.80)',
          border: dk ? '1px solid rgba(56,189,248,0.22)' : '1px solid rgba(255,255,255,0.85)',
          backdropFilter: 'blur(10px)',
          color: dk ? '#38BDF8' : '#475569',
          boxShadow: dk ? '0 4px 16px rgba(0,0,0,0.4)' : '0 2px 10px rgba(0,0,0,0.10)',
        }}
      >
        <AnimatePresence mode="wait" initial={false}>
          {dk ? (
            <motion.span key="sun" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.2 }}>
              <Sun size={16} />
            </motion.span>
          ) : (
            <motion.span key="moon" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.2 }}>
              <Moon size={16} />
            </motion.span>
          )}
        </AnimatePresence>
      </button>

      {/* Decorative rings */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center" style={{ paddingBottom: '12%' }}>
        <div className="h-[620px] w-[620px] rounded-full" style={{ border: dk ? '1px solid rgba(56,189,248,0.07)' : '1px solid rgba(255,255,255,0.22)' }} />
      </div>
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center" style={{ paddingBottom: '12%' }}>
        <div className="h-[880px] w-[880px] rounded-full" style={{ border: dk ? '1px solid rgba(56,189,248,0.04)' : '1px solid rgba(255,255,255,0.12)' }} />
      </div>

      {/* Blobs */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-52">
        {dk ? (
          <>
            <div style={{ position:'absolute', bottom:'-60px', left:'-8%',  width:'450px', height:'200px', borderRadius:'50%', background:'rgba(7,21,33,0.90)', filter:'blur(42px)' }} />
            <div style={{ position:'absolute', bottom:'-40px', left:'26%',  width:'380px', height:'160px', borderRadius:'50%', background:'rgba(9,28,48,0.92)', filter:'blur(34px)' }} />
            <div style={{ position:'absolute', bottom:'-55px', right:'-6%', width:'430px', height:'185px', borderRadius:'50%', background:'rgba(7,21,33,0.88)', filter:'blur(42px)' }} />
            <div style={{ position:'absolute', top:'0', left:'40%', width:'400px', height:'160px', borderRadius:'50%', background:'rgba(14,165,233,0.05)', filter:'blur(60px)' }} />
          </>
        ) : (
          <>
            <div style={{ position:'absolute', bottom:'-60px', left:'-8%',  width:'450px', height:'200px', borderRadius:'50%', background:'rgba(255,255,255,0.88)', filter:'blur(42px)' }} />
            <div style={{ position:'absolute', bottom:'-40px', left:'26%',  width:'380px', height:'160px', borderRadius:'50%', background:'rgba(255,255,255,0.92)', filter:'blur(34px)' }} />
            <div style={{ position:'absolute', bottom:'-55px', right:'-6%', width:'430px', height:'185px', borderRadius:'50%', background:'rgba(255,255,255,0.82)', filter:'blur(42px)' }} />
            <div style={{ position:'absolute', bottom:'-8px',  left:'12%',  width:'260px', height:'110px', borderRadius:'50%', background:'rgba(255,255,255,0.68)', filter:'blur(26px)' }} />
            <div style={{ position:'absolute', bottom:'-12px', right:'20%', width:'300px', height:'120px', borderRadius:'50%', background:'rgba(255,255,255,0.72)', filter:'blur(28px)' }} />
          </>
        )}
      </div>

      {/* Card */}
      <motion.div
        initial={{ opacity: 0, y: 18, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.45, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-[415px] transition-all duration-500"
        style={dk ? {
          background: 'rgba(9,28,48,0.92)',
          backdropFilter: 'blur(28px)',
          WebkitBackdropFilter: 'blur(28px)',
          borderRadius: '28px',
          border: '1.5px solid rgba(56,189,248,0.13)',
          boxShadow: '0 8px 48px rgba(4,14,28,0.55), 0 2px 12px rgba(0,0,0,0.35)',
        } : {
          background: 'linear-gradient(148deg, rgba(255,255,255,0.70) 0%, rgba(200,238,255,0.54) 100%)',
          backdropFilter: 'blur(28px)',
          WebkitBackdropFilter: 'blur(28px)',
          borderRadius: '28px',
          border: '1.5px solid rgba(255,255,255,0.86)',
          boxShadow: '0 8px 48px rgba(70,162,228,0.14), 0 2px 12px rgba(0,0,0,0.04)',
        }}
      >
        <div className="px-9 py-9">
          {/* Icon */}
          <div className="mb-5 flex justify-center">
            <div
              className="flex h-[68px] w-[68px] items-center justify-center rounded-[18px] transition-all duration-300"
              style={dk ? {
                background: 'rgba(14,165,233,0.12)',
                border: '1px solid rgba(56,189,248,0.18)',
                boxShadow: '0 2px 14px rgba(0,0,0,0.3)',
              } : {
                background: 'white',
                boxShadow: '0 2px 14px rgba(0,0,0,0.09)',
              }}
            >
              <LogIn size={27} strokeWidth={1.75} style={{ color: dk ? '#38BDF8' : '#334155' }} />
            </div>
          </div>

          {/* Heading */}
          <h1 className="text-center text-[1.5rem] font-bold tracking-tight" style={{ color: dk ? '#F0F9FF' : '#1E293B' }}>
            Sign in with email
          </h1>
          <p className="mt-1.5 mb-6 text-center text-[13.5px] leading-relaxed" style={{ color: dk ? '#38698A' : '#64748B' }}>
            Research platform for Somali NLP<br />text classification studies.
          </p>

          {/* Alerts */}
          <AnimatePresence>
            {error && (
              <motion.div key="err" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
                className={`mb-4 flex items-start gap-2.5 overflow-hidden rounded-2xl px-3.5 py-3 ${dk ? 'border border-red-700/30 bg-red-900/25' : 'border border-red-200 bg-red-50/80'}`}>
                <AlertCircle size={15} className="mt-0.5 shrink-0 text-red-400" />
                <p className={`text-sm ${dk ? 'text-red-300' : 'text-red-600'}`}>{error}</p>
              </motion.div>
            )}
            {success && (
              <motion.div key="ok" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                className={`mb-4 flex items-start gap-2.5 overflow-hidden rounded-2xl px-3.5 py-3 ${dk ? 'border border-emerald-700/30 bg-emerald-900/20' : 'border border-emerald-200 bg-emerald-50/80'}`}>
                <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-400" />
                <p className={`text-sm ${dk ? 'text-emerald-300' : 'text-emerald-700'}`}>{success}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Fields */}
          <div className="space-y-3">
            <div className="relative">
              <Mail size={15} className="pointer-events-none absolute left-[15px] top-1/2 -translate-y-1/2" style={{ color: dk ? '#1E4D6E' : '#94A3B8' }} />
              <input
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="Email" disabled={loading}
                onKeyDown={e => e.key === 'Enter' && submit()}
                autoComplete="email" className={inputCls}
              />
            </div>
            <div className="relative">
              <Lock size={15} className="pointer-events-none absolute left-[15px] top-1/2 -translate-y-1/2" style={{ color: dk ? '#1E4D6E' : '#94A3B8' }} />
              <input
                type={showPw ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Password" disabled={loading}
                onKeyDown={e => e.key === 'Enter' && submit()}
                autoComplete="current-password" className={`${inputCls} !pr-11`}
              />
              <button type="button" onClick={() => setShowPw(v => !v)}
                className="absolute right-[14px] top-1/2 -translate-y-1/2 transition-colors"
                style={{ color: dk ? '#1E4D6E' : '#94A3B8' }}>
                {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {/* Forgot password */}
          <div className="mt-2.5 mb-5 flex justify-end">
            <span className="cursor-default text-xs font-medium" style={{ color: dk ? '#1E4D6E' : '#94A3B8' }}>
              Forgot password?
            </span>
          </div>

          {/* Submit */}
          <button
            onClick={submit} disabled={loading}
            className="flex h-[52px] w-full items-center justify-center rounded-[14px] text-sm font-semibold text-white transition-all active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
            style={dk ? {
              background: 'linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%)',
              boxShadow: '0 4px 20px rgba(14,165,233,0.28)',
            } : {
              background: '#0F172A',
            }}
          >
            {loading
              ? <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              : 'Get Started'
            }
          </button>

          {/* Divider */}
          <div className="my-5 flex items-center gap-1.5">
            <span className="flex-1 text-center text-[7px] leading-none tracking-[6px]" style={{ color: dk ? '#0F3558' : '#CBD5E1' }}>• • • • • •</span>
            <span className="shrink-0 px-2 text-[11px] font-medium" style={{ color: dk ? '#1E4D6E' : '#94A3B8' }}>or</span>
            <span className="flex-1 text-center text-[7px] leading-none tracking-[6px]" style={{ color: dk ? '#0F3558' : '#CBD5E1' }}>• • • • • •</span>
          </div>

          {/* Sign up */}
          <p className="text-center text-sm" style={{ color: dk ? '#38698A' : '#64748B' }}>
            Don't have an account?{' '}
            <Link to="/register" className="font-semibold transition-colors" style={{ color: dk ? '#38BDF8' : '#0284c7' }}>
              Sign up
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  )
}

export default Login
