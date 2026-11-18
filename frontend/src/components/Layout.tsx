import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  ShoppingBag,
  ClipboardList,
  FileText,
  DollarSign,
  Package,
  Layers,
  BarChart3,
  LogOut,
  Wifi,
  WifiOff,
  RefreshCw,
  PlusCircle,
  Truck,
  CheckCircle2,
  AlertCircle,
  LayoutDashboard
} from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { user, role, logout, isOnline, pendingSyncCount, triggerSync } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isSalesman = role === 'salesman';

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top Header */}
      <header className="bg-slate-900 text-white shadow-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            {/* Logo / App Name */}
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold tracking-tight text-blue-400">
                Order-to-Audit
              </span>
              <span className="hidden sm:inline-block px-2 py-0.5 text-xs font-semibold uppercase tracking-wider bg-slate-800 text-slate-300 rounded border border-slate-700">
                {role}
              </span>
            </div>

            {/* Offline & Outbox Sync Indicator */}
            <div className="flex items-center gap-3">
              {isOnline ? (
                <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                  <Wifi className="w-4 h-4" />
                  <span className="hidden sm:inline">Online</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 text-xs text-amber-400 font-semibold animate-pulse">
                  <WifiOff className="w-4 h-4" />
                  <span>Offline Mode</span>
                </div>
              )}

              {pendingSyncCount > 0 && (
                <button
                  onClick={triggerSync}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold bg-amber-500 hover:bg-amber-600 text-slate-950 rounded-full transition-all shadow"
                  title="Click to flush outbox"
                >
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>{pendingSyncCount} Pending Sync</span>
                </button>
              )}

              {/* User info & Logout */}
              {user && (
                <div className="flex items-center gap-2 pl-3 border-l border-slate-800">
                  <span className="text-xs text-slate-300 hidden md:inline">
                    {user.full_name}
                  </span>
                  <button
                    onClick={handleLogout}
                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                    title="Sign Out"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Navigation Bar (Desktop & Tablet) */}
        {!isSalesman && (
          <div className="bg-slate-800 border-t border-slate-700/60 overflow-x-auto">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex space-x-1 sm:space-x-3 py-1.5">
              {/* Owner / Executive Dashboard */}
              {(role === 'owner' || role === 'admin') && (
                <NavLink to="/dashboard" active={location.pathname === '/dashboard'}>
                  <LayoutDashboard className="w-4 h-4" />
                  <span>Dashboard</span>
                </NavLink>
              )}

              {/* Admin Routes */}
              {role === 'admin' && (
                <>
                  <NavLink to="/admin/orders" active={location.pathname.startsWith('/admin/orders')}>
                    <ClipboardList className="w-4 h-4" />
                    <span>Orders Queue</span>
                  </NavLink>
                  <NavLink to="/admin/invoices" active={location.pathname.startsWith('/admin/invoices')}>
                    <FileText className="w-4 h-4" />
                    <span>Invoices & Dispatch</span>
                  </NavLink>
                  <NavLink to="/admin/payments" active={location.pathname.startsWith('/admin/payments')}>
                    <DollarSign className="w-4 h-4" />
                    <span>Payments & Ageing</span>
                  </NavLink>
                </>
              )}

              {/* Production Routes */}
              {role === 'production' && (
                <>
                  <NavLink to="/production/runs" active={location.pathname.startsWith('/production/runs')}>
                    <Layers className="w-4 h-4" />
                    <span>Production Runs</span>
                  </NavLink>
                  <NavLink to="/production/new-run" active={location.pathname === '/production/new-run'}>
                    <PlusCircle className="w-4 h-4" />
                    <span>New Run</span>
                  </NavLink>
                  <NavLink to="/production/purchases" active={location.pathname.startsWith('/production/purchases')}>
                    <Truck className="w-4 h-4" />
                    <span>Purchases</span>
                  </NavLink>
                </>
              )}

              {/* Stock (Admin, Production, Auditor, Owner) */}
              {['admin', 'production', 'auditor', 'owner'].includes(role || '') && (
                <>
                  <NavLink to="/stock/summary" active={location.pathname === '/stock/summary'}>
                    <Package className="w-4 h-4" />
                    <span>Stock Summary</span>
                  </NavLink>
                  <NavLink to="/stock/ledger" active={location.pathname === '/stock/ledger'}>
                    <ClipboardList className="w-4 h-4" />
                    <span>Stock Ledger</span>
                  </NavLink>
                  {['admin', 'auditor'].includes(role || '') && (
                    <NavLink to="/stock/reconcile" active={location.pathname === '/stock/reconcile'}>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Reconcile</span>
                    </NavLink>
                  )}
                </>
              )}

              {/* Reports (Admin, Production, Auditor, Owner) */}
              {['admin', 'production', 'auditor', 'owner'].includes(role || '') && (
                <NavLink to="/reports" active={location.pathname.startsWith('/reports')}>
                  <BarChart3 className="w-4 h-4" />
                  <span>Reports</span>
                </NavLink>
              )}
            </div>
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {children}
      </main>

      {/* Mobile Bottom Navigation for Salesman (360px optimized) */}
      {isSalesman && (
        <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 z-50 flex justify-around items-center h-16 shadow-lg">
          <Link
            to="/orders/new"
            className={`flex flex-col items-center justify-center flex-1 py-1 ${
              location.pathname === '/orders/new'
                ? 'text-blue-700 font-bold'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            <PlusCircle className="w-6 h-6 mb-0.5" />
            <span className="text-xs">New Order</span>
          </Link>

          <Link
            to="/my-orders"
            className={`flex flex-col items-center justify-center flex-1 py-1 ${
              location.pathname === '/my-orders'
                ? 'text-blue-700 font-bold'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            <ClipboardList className="w-6 h-6 mb-0.5" />
            <span className="text-xs">My Orders</span>
          </Link>

          <Link
            to="/customer-sales"
            className={`flex flex-col items-center justify-center flex-1 py-1 ${
              location.pathname === '/customer-sales'
                ? 'text-blue-700 font-bold'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            <BarChart3 className="w-6 h-6 mb-0.5" />
            <span className="text-xs">Customer Sales</span>
          </Link>
        </nav>
      )}
    </div>
  );
};

const NavLink: React.FC<{ to: string; active: boolean; children: React.ReactNode }> = ({
  to,
  active,
  children,
}) => (
  <Link
    to={to}
    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs sm:text-sm font-medium rounded-md whitespace-nowrap transition-colors ${
      active
        ? 'bg-blue-600 text-white shadow-sm'
        : 'text-slate-300 hover:bg-slate-700 hover:text-white'
    }`}
  >
    {children}
  </Link>
);
