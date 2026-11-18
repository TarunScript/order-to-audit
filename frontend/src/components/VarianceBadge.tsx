import React from 'react';

interface VarianceBadgeProps {
  variancePct: number;
  varianceBp?: number;
  flagged: boolean;
}

export const VarianceBadge: React.FC<VarianceBadgeProps> = ({
  variancePct,
  varianceBp,
  flagged,
}) => {
  const formattedPct = `${variancePct > 0 ? '+' : ''}${variancePct.toFixed(1)}%`;

  if (flagged) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-red-100 text-red-800 border border-red-300">
        ⚠️ {formattedPct} {varianceBp !== undefined ? `(${varianceBp > 0 ? '+' : ''}${varianceBp} bp)` : ''}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
      {formattedPct}
    </span>
  );
};
