import { Badge, Group, Text, Tooltip, type BadgeProps } from '@mantine/core';
import { IconAlertTriangle, IconCheck } from '@tabler/icons-react';
import { defectMeta, defectTitle, severityMeta } from '../lib/defects';

/** Severity: status colour on the icon, label in text ink - never colour alone. */
export function SeverityBadge({ severity, size = 'md' }: { severity: string | null; size?: BadgeProps['size'] }) {
  const m = severityMeta(severity);
  const Icon = m.icon;
  return (
    <Badge
      variant="default"
      size={size}
      radius="sm"
      leftSection={<Icon size={size === 'lg' ? 16 : 14} stroke={2.2} color={m.color} aria-hidden />}
    >
      {severity ? `${m.label} severity` : m.label}
    </Badge>
  );
}

/** Compact severity marker for dense rows: coloured icon + short label. */
export function SeverityInline({ severity }: { severity: string | null }) {
  const m = severityMeta(severity);
  const Icon = m.icon;
  return (
    <Group gap={4} wrap="nowrap">
      <Icon size={15} stroke={2.2} color={m.color} aria-hidden />
      <Text fz="xs" fw={500}>
        {m.label}
      </Text>
    </Group>
  );
}

export function RunStatus({ status }: { status: string }) {
  const complete = status === 'complete';
  const badge = (
    <Badge
      variant="default"
      radius="sm"
      leftSection={
        complete ? (
          <IconCheck size={14} stroke={2.4} color="var(--pw-status-good)" aria-hidden />
        ) : (
          <IconAlertTriangle size={14} stroke={2.2} color="var(--pw-status-warning)" aria-hidden />
        )
      }
    >
      {complete ? 'Complete' : 'Incomplete'}
    </Badge>
  );
  return complete ? (
    badge
  ) : (
    <Tooltip label="The flight or processing did not cover the whole planned area" withArrow>
      {badge}
    </Tooltip>
  );
}

export function Glyph({ type }: { type: string }) {
  return (
    <span className="pw-glyph" aria-hidden>
      {defectMeta(type).glyph}
    </span>
  );
}

export function DefectLabel({
  type,
  subtype,
  size = 'sm',
  fw = 600,
}: {
  type: string;
  subtype?: string | null;
  size?: string;
  fw?: number;
}) {
  return (
    <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
      <Glyph type={type} />
      <Text fz={size} fw={fw} truncate>
        {defectTitle(type, subtype)}
      </Text>
    </Group>
  );
}
