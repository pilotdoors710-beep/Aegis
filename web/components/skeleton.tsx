import type { CSSProperties } from "react";

// Placeholder shapes for loading states. Decorative: the surrounding region announces the status.
export function Skeleton({ className = "", style }: { className?: string; style?: CSSProperties }) {
  return <span className={`skeleton ${className}`} style={style} aria-hidden="true" />;
}

/** Wraps placeholders in one polite status region so assistive tech hears a single "Loading …". */
export function SkeletonGroup({ label, className = "", children }: { label: string; className?: string; children: React.ReactNode }) {
  return <div className={`skeleton-group ${className}`} role="status" aria-live="polite" aria-busy="true"><span className="visually-hidden">{label}</span>{children}</div>;
}

export const SkeletonLines = ({ n = 3 }: { n?: number }) => <>{Array.from({ length: n }, (_, i) => <Skeleton key={i} className={`skeleton-line${i === n - 1 ? " is-short" : ""}`} />)}</>;

export const SkeletonRows = ({ n = 4 }: { n?: number }) => <>{Array.from({ length: n }, (_, i) => <Skeleton key={i} className="skeleton-row" />)}</>;

export const SkeletonCards = ({ n = 3 }: { n?: number }) => <div className="skeleton-grid">{Array.from({ length: n }, (_, i) => <Skeleton key={i} className="skeleton-block" />)}</div>;
