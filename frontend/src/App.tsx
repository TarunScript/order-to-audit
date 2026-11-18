import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { AccessDenied } from './pages/AccessDenied';

// Salesman Pages
import { NewOrder } from './pages/salesman/NewOrder';
import { MyOrders } from './pages/salesman/MyOrders';
import { CustomerSales } from './pages/salesman/CustomerSales';

// Admin Pages
import { OrdersQueue } from './pages/admin/OrdersQueue';
import { Invoices } from './pages/admin/Invoices';
import { Payments } from './pages/admin/Payments';

// Production Pages
import { NewRun } from './pages/production/NewRun';
import { RunsList } from './pages/production/RunsList';
import { RunDetail } from './pages/production/RunDetail';
import { Purchases } from './pages/production/Purchases';

// Stock Pages
import { StockSummary } from './pages/stock/StockSummary';
import { StockLedger } from './pages/stock/StockLedger';
import { StockReconcile } from './pages/stock/StockReconcile';

// Reports & Dashboard
import { Reports } from './pages/reports/Reports';
import { OwnerDashboard } from './pages/dashboard/OwnerDashboard';

import { Role } from './types';

// Protected Route Guard
const RequireAuth: React.FC<{ allowedRoles?: Role[]; children: React.ReactNode }> = ({
  allowedRoles,
  children,
}) => {
  const { isAuthenticated, isLoading, role } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 text-white text-sm">
        Authenticating session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && role && !allowedRoles.includes(role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <Layout>{children}</Layout>;
};

// Home Redirect according to role
const HomeRedirect: React.FC = () => {
  const { role, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  switch (role) {
    case 'salesman':
      return <Navigate to="/orders/new" replace />;
    case 'production':
      return <Navigate to="/production/runs" replace />;
    case 'auditor':
      return <Navigate to="/stock/summary" replace />;
    case 'admin':
    case 'owner':
    default:
      return <Navigate to="/dashboard" replace />;
  }
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/unauthorized" element={<Layout><AccessDenied /></Layout>} />

          {/* Root Redirect */}
          <Route path="/" element={<HomeRedirect />} />

          {/* 1. Salesman Routes (Mobile-first) */}
          <Route
            path="/orders/new"
            element={
              <RequireAuth allowedRoles={['salesman']}>
                <NewOrder />
              </RequireAuth>
            }
          />
          <Route
            path="/my-orders"
            element={
              <RequireAuth allowedRoles={['salesman']}>
                <MyOrders />
              </RequireAuth>
            }
          />
          <Route
            path="/customer-sales"
            element={
              <RequireAuth allowedRoles={['salesman']}>
                <CustomerSales />
              </RequireAuth>
            }
          />

          {/* 2. Admin Desk Routes */}
          <Route
            path="/admin/orders"
            element={
              <RequireAuth allowedRoles={['admin']}>
                <OrdersQueue />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/invoices"
            element={
              <RequireAuth allowedRoles={['admin']}>
                <Invoices />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/payments"
            element={
              <RequireAuth allowedRoles={['admin']}>
                <Payments />
              </RequireAuth>
            }
          />

          {/* 3. Production Floor Routes */}
          <Route
            path="/production/new-run"
            element={
              <RequireAuth allowedRoles={['production']}>
                <NewRun />
              </RequireAuth>
            }
          />
          <Route
            path="/production/runs"
            element={
              <RequireAuth allowedRoles={['production']}>
                <RunsList />
              </RequireAuth>
            }
          />
          <Route
            path="/production/runs/:id"
            element={
              <RequireAuth allowedRoles={['production']}>
                <RunDetail />
              </RequireAuth>
            }
          />
          <Route
            path="/production/purchases"
            element={
              <RequireAuth allowedRoles={['production']}>
                <Purchases />
              </RequireAuth>
            }
          />

          {/* 4. Stock & Valuation Screens */}
          <Route
            path="/stock/summary"
            element={
              <RequireAuth allowedRoles={['admin', 'production', 'auditor', 'owner']}>
                <StockSummary />
              </RequireAuth>
            }
          />
          <Route
            path="/stock/ledger"
            element={
              <RequireAuth allowedRoles={['admin', 'production', 'auditor', 'owner']}>
                <StockLedger />
              </RequireAuth>
            }
          />
          <Route
            path="/stock/reconcile"
            element={
              <RequireAuth allowedRoles={['admin', 'auditor']}>
                <StockReconcile />
              </RequireAuth>
            }
          />

          {/* 5. Reports (Multi-role with Production scoped) */}
          <Route
            path="/reports"
            element={
              <RequireAuth allowedRoles={['admin', 'production', 'auditor', 'owner']}>
                <Reports />
              </RequireAuth>
            }
          />

          {/* 6. Executive / Owner Dashboard */}
          <Route
            path="/dashboard"
            element={
              <RequireAuth allowedRoles={['owner', 'admin']}>
                <OwnerDashboard />
              </RequireAuth>
            }
          />

          {/* Catch-all fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
