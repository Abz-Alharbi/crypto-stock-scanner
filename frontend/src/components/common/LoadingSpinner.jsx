import React from 'react';

export default function LoadingSpinner({ size = 'md', text = '' }) {
  const sizes = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' };

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8">
      <div className={`${sizes[size]} border-2 border-scanner-border border-t-scanner-accent rounded-full animate-spin`} />
      {text && <p className="text-scanner-text-dim text-sm animate-pulse">{text}</p>}
    </div>
  );
}

export function SkeletonRow({ cols = 5 }) {
  return (
    <div className="flex gap-4 py-3 px-4">
      {Array.from({ length: cols }).map((_, i) => (
        <div key={i} className="skeleton h-4 rounded flex-1" style={{ animationDelay: `${i * 0.1}s` }} />
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-scanner-card border border-scanner-border rounded-xl p-5 space-y-3">
      <div className="skeleton h-5 rounded w-1/3" />
      <div className="skeleton h-4 rounded w-2/3" />
      <div className="skeleton h-4 rounded w-1/2" />
      <div className="skeleton h-32 rounded w-full" />
    </div>
  );
}
