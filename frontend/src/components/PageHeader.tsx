import { Skeleton } from '@mantine/core';
import { Fragment, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

export interface Crumb {
  label: ReactNode;
  to?: string;
}

/**
 * Section opener: uppercase breadcrumb eyebrow, a light display title in columns 1–7,
 * and an aside (facts, actions) in columns 8–12 aligned to the title's baseline.
 */
export function PageHeader({
  crumbs,
  title,
  subtitle,
  right,
  loading,
}: {
  crumbs: Crumb[];
  title: ReactNode;
  /** Short factual paragraph or meta line shown in the aside. */
  subtitle?: ReactNode;
  /** Actions or key figures, shown under the subtitle in the aside. */
  right?: ReactNode;
  loading?: boolean;
}) {
  return (
    <header className="pw-opener">
      <nav className="pw-opener__crumbs pw-eyebrow" aria-label="Breadcrumb">
        {crumbs.map((c, i) => (
          <Fragment key={i}>
            {i > 0 && (
              <span className="pw-crumb-sep" aria-hidden>
                /
              </span>
            )}
            {c.to ? (
              <Link to={c.to}>{c.label}</Link>
            ) : (
              <span className="pw-crumb-here" aria-current="page">
                {c.label}
              </span>
            )}
          </Fragment>
        ))}
      </nav>
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
