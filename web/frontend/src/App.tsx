import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import { AuthProvider } from './contexts/AuthContext'
import { ToastProvider } from './contexts/ToastContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { PublicRoute } from './components/PublicRoute'
import { Layout } from './components/Layout'

// Eagerly loaded (critical path)
import Login from './pages/Login'
import Register from './pages/Register'
import LandingPage from './pages/public/LandingPage'

// Lazily loaded (code-split)
const Dashboard     = lazy(() => import('./pages/Dashboard'))
const Predict       = lazy(() => import('./pages/Predict'))
const LinkAnalysis  = lazy(() => import('./pages/LinkAnalysis'))
const NewsFeed      = lazy(() => import('./pages/NewsFeed'))
const Models        = lazy(() => import('./pages/Models'))
const Experiments   = lazy(() => import('./pages/Experiments'))
const Analytics     = lazy(() => import('./pages/Analytics'))
const UserManagement = lazy(() => import('./pages/UserManagement'))
const AuditLogs     = lazy(() => import('./pages/AuditLogs'))
const XAI           = lazy(() => import('./pages/XAI'))

const PageLoader = () => (
  <div className="flex h-full min-h-[400px] items-center justify-center">
    <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-neutral-200 border-t-primary-500" />
  </div>
)

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            {/* ── Public website ─────────────────────────────────── */}
            <Route path="/" element={<LandingPage />} />

            {/* ── Auth pages ─────────────────────────────────────── */}
            <Route path="/login"    element={<PublicRoute><Login /></PublicRoute>} />
            <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />

            {/* ── Research platform (protected) ──────────────────── */}
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route path="dashboard" element={<Suspense fallback={<PageLoader />}><Dashboard /></Suspense>} />
              <Route path="predict"   element={<Suspense fallback={<PageLoader />}><Predict /></Suspense>} />
              <Route path="link"      element={<Suspense fallback={<PageLoader />}><LinkAnalysis /></Suspense>} />
              <Route path="news"      element={<Suspense fallback={<PageLoader />}><NewsFeed /></Suspense>} />
              <Route path="models"    element={<Suspense fallback={<PageLoader />}><Models /></Suspense>} />
              <Route path="experiments" element={<Suspense fallback={<PageLoader />}><Experiments /></Suspense>} />
              <Route path="analytics"   element={<Suspense fallback={<PageLoader />}><Analytics /></Suspense>} />
              <Route path="admin/users" element={<Suspense fallback={<PageLoader />}><UserManagement /></Suspense>} />
              <Route path="admin/logs"  element={<Suspense fallback={<PageLoader />}><AuditLogs /></Suspense>} />
              <Route path="xai"         element={<Suspense fallback={<PageLoader />}><XAI /></Suspense>} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Route>
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  )
}
