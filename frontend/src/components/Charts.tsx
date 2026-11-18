import { Group, Stack, Text, Tooltip } from '@mantine/core';
import type { ReactNode } from 'react';
import { DEFECT_TYPES, SEVERITIES, defectMeta, severityMeta } from '../lib/defects';
import { Glyph } from './Badges';
import { AnimatedValue } from './Motion';

/** Severity mix as a thin segmented bar (high -> low), with the counts in the tooltip and aria-label. */
export function SeverityBar({ counts }: { counts: Record<string, number> }) {
  const parts = SEVERITIES.map((s) => ({ s, n: counts[s] ?? 0 })).filter((p) => p.n > 0);
  const total = parts.reduce((a, p) => a + p.n, 0);
  const text = total ? parts.map((p) => `${p.n} ${severityMeta(p.s).label.toLowerCase()}`).join(', ') : 'No findings';
  return (
    <Tooltip label={text} withArrow>
      <div className="pw-sevbar" data-empty={total === 0} role="img" aria-label={`Severity: ${text}`}>
        {parts.map((p) => (
          <span key={p.s} style={{ flexGrow: p.n, background: severityMeta(p.s).color }} />
        ))}
      </div>
    </Tooltip>
  );
}

/** Stat strip tile: label on top, oversized light numeral, hint anchored to the bottom. */
export function StatTile({
  label,
  value,
  icon,
  hint,
}: {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div className="pw-tile pw-stat">
      <span className="pw-stat__label">
        {icon}
        {label}
      </span>
      <span className="pw-stat-num">
        <AnimatedValue value={value} />
      </span>
      {hint && <span className="pw-stat__hint">{hint}</span>}
    </div>
  );
}

/** Key figure: numeral over an uppercase label. */
export function Figure({ label, value, icon }: { label: string; value: ReactNode; icon?: ReactNode }) {
  return (
    <div className="pw-figure">
      <span className="pw-stat-num">
        <AnimatedValue value={value} />
      </span>
      <span className="pw-figure__label pw-eyebrow pw-dim">
        {icon}
        {label}
      </span>
    </div>
  );
}

/**
 * Findings per defect type: one measure across categories -> one hue, direct labels,
 * bars anchored at the baseline. Rows double as type filters.
 */
export function TypeBarList({
  counts,
  selected,
  onToggle,
}: {
  counts: Record<string, number>;
  selected: string[];
  onToggle: (type: string) => void;
}) {
  const known = DEFECT_TYPES.filter((t) => counts[t]);
  const extra = Object.keys(counts).filter((t) => !(DEFECT_TYPES as readonly string[]).includes(t) && counts[t]);
  const rows = [...known, ...extra].map((t) => ({ t, n: counts[t] })).sort((a, b) => b.n - a.n);
  const max = Math.max(1, ...rows.map((r) => r.n));
  if (!rows.length) {
    return (
      <Text fz="sm" c="dimmed">
        No findings in this run.
      </Text>
    );
  }
  return (
    <Stack gap={0}>
      {rows.map(({ t, n }) => {
        const label = defectMeta(t).label;
        const active = selected.includes(t);
        return (
          <Tooltip key={t} label={`${label}: ${n} finding${n === 1 ? '' : 's'} - click to ${active ? 'remove' : 'apply'} filter`} withArrow openDelay={400}>
            <button
              type="button"
              className="pw-barlist-row pw-clickable"
              data-dimmed={selected.length > 0 && !active}
              aria-pressed={active}
              onClick={() => onToggle(t)}
            >
              <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
                <Glyph type={t} />
                <Text fz="sm" truncate fw={active ? 650 : 400}>
                  {label}
                </Text>
              </Group>
              <div className="pw-barlist-track">
                <div className="pw-barlist-bar" style={{ width: `${(n / max) * 100}%` }} />
              </div>
              <Text fz="sm" fw={600} ta="right" className="pw-tabular">
                {n}
              </Text>
            </button>
          </Tooltip>
        );
      })}
    </Stack>
  );
}
