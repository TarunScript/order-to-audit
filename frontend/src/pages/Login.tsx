import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Lock, UserCheck, AlertCircle, ShoppingBag } from 'lucide-react';

export const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('password123');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Please provide username and password');
      return;
    }
    setError(null);
    setLoading(true);

    try {
      await login(username, password);
      const from = (location.state as any)?.from?.pathname;
      if (from) {
        navigate(from, { replace: true });
      } else {
        // Route according to role
        if (username.startsWith('salesman')) {
          navigate('/orders/new', { replace: true });
        } else if (username === 'production') {
          navigate('/production/runs', { replace: true });
        } else if (username === 'auditor') {
          navigate('/stock/summary', { replace: true });
        } else {
          navigate('/dashboard', { replace: true });
        }
      }
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = (uname: string) => {
    setUsername(uname);
    setPassword('password123');
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center text-blue-500">
          <ShoppingBag className="w-12 h-12" />
        </div>
        <h2 className="mt-3 text-center text-3xl font-extrabold text-white tracking-tight">
          Order-to-Audit System
        </h2>
        <p className="mt-2 text-center text-sm text-slate-400">
          Snack Manufacturing ERP Monolith
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-slate-800 py-8 px-6 shadow-xl rounded-2xl sm:px-10 border border-slate-700">
          {error && (
            <div className="mb-4 bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded-lg flex items-center gap-2 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleLogin}>
            <div>
              <label className="block text-sm font-medium text-slate-300">
                Username
              </label>
              <div className="mt-1">
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="appearance-none block w-full px-3 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  placeholder="e.g. salesman_a, admin, production"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300">
                Password
              </label>
              <div className="mt-1">
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="appearance-none block w-full px-3 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 transition-colors"
              >
                {loading ? 'Authenticating...' : 'Sign In'}
              </button>
            </div>
          </form>

          {/* Quick Demo Logins */}
          <div className="mt-6 pt-6 border-t border-slate-700">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 text-center">
              Quick Role Presets
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleQuickLogin('salesman_a')}
                className="px-2.5 py-1.5 bg-slate-700/70 hover:bg-slate-700 text-xs text-slate-200 rounded border border-slate-600 font-medium text-left truncate"
              >
                📱 Salesman A (TN)
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('salesman_b')}
                className="px-2.5 py-1.5 bg-slate-700/70 hover:bg-slate-700 text-xs text-slate-200 rounded border border-slate-600 font-medium text-left truncate"
              >
                📱 Salesman B (KA)
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('admin')}
                className="px-2.5 py-1.5 bg-slate-700/70 hover:bg-slate-700 text-xs text-slate-200 rounded border border-slate-600 font-medium text-left truncate"
              >
                💼 Admin & Billing
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('production')}
                className="px-2.5 py-1.5 bg-slate-700/70 hover:bg-slate-700 text-xs text-slate-200 rounded border border-slate-600 font-medium text-left truncate"
              >
                🏭 Production Supervisor
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('auditor')}
                className="px-2.5 py-1.5 bg-slate-700/70 hover:bg-slate-700 text-xs text-slate-200 rounded border border-slate-600 font-medium text-left truncate"
              >
                🔍 Statutory Auditor
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('owner')}
                className="px-2.5 py-1.5 bg-slate-700/70 hover:bg-slate-700 text-xs text-slate-200 rounded border border-slate-600 font-medium text-left truncate"
              >
                👑 Managing Director
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
