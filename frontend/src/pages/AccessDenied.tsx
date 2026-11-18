import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

export const AccessDenied: React.FC = () => {
  const { user, role } = useAuth();

  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center px-4">
      <div className="w-16 h-16 bg-red-100 text-red-600 rounded-full flex items-center justify-center mb-4">
        <ShieldAlert className="w-10 h-10" />
      </div>
      <h1 className="text-2xl font-bold text-slate-900 tracking-tight mb-2">
        Access Denied
      </h1>
      <p className="text-slate-600 max-w-md mb-6 text-sm">
        Your role <span className="font-semibold text-slate-800">({role})</span> does
        not have permission to access this screen. Contact your administrator if you need access.
      </p>
      <Link
        to={role === 'salesman' ? '/orders/new' : role === 'production' ? '/production/runs' : '/dashboard'}
        className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-sm font-medium transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Return to Permitted Home
      </Link>
    </div>
  );
};
