import { Skeleton } from '@mantine/core';
import type { ReactNode } from 'react';

/**
 * Section opener: an optional uppercase eyebrow, a light display title in columns 1–7,
 * and an aside (facts, actions) in columns 8–12 aligned to the title's baseline.
 * Where you are in the hierarchy is shown by the trail in the top bar, not here.
 */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
  right,
  loading,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  /** Short factual paragraph or meta line shown in the aside. */
  subtitle?: ReactNode;
  /** Actions or key figures, shown under the subtitle in the aside. */
  right?: ReactNode;
  loading?: boolean;
}) {
  return (
    <header className="pw-opener">
      {eyebrow && <div className="pw-opener__crumbs pw-eyebrow">{eyebrow}</div>}
      <div className="pw-grid">
        <div className="pw-opener__title">
          {loading ? <Skeleton h={56} w="70%" /> : <h1 className="pw-display">{title}</h1>}
        </div>
        <div className="pw-opener__aside">
          {loading ? (
            <Skeleton h={16} w={240} />
          ) : (
            subtitle && <div style={{ fontSize: 15, lineHeight: 1.5 }}>{subtitle}</div>
          )}
          {right}
        </div>
      </div>
    </header>
  );
}
