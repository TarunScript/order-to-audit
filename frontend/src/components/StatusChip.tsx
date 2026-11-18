import React from 'react';

interface StatusChipProps {
  status: string;
}

export const StatusChip: React.FC<StatusChipProps> = ({ status }) => {
  const s = status.toUpperCase();
  let colorClasses = 'bg-slate-100 text-slate-800 border-slate-200';

  switch (s) {
    case 'SUBMITTED':
      colorClasses = 'bg-blue-50 text-blue-700 border-blue-200';
      break;
    case 'APPROVED':
      colorClasses = 'bg-indigo-50 text-indigo-700 border-indigo-200';
      break;
    case 'INVOICED':
      colorClasses = 'bg-amber-50 text-amber-700 border-amber-200';
      break;
    case 'DISPATCHED':
    case 'POSTED':
      colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200';
      break;
    case 'REJECTED':
    case 'CANCELLED':
      colorClasses = 'bg-red-50 text-red-700 border-red-200';
      break;
    case 'DRAFT':
      colorClasses = 'bg-gray-100 text-gray-700 border-gray-200';
      break;
  }

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${colorClasses}`}
    >
      {s}
    </span>
  );
};
