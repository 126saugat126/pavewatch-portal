import { Badge, Group, Stack, Text } from '@mantine/core';
import { IconCircleCheck } from '@tabler/icons-react';
import type { DataWarning, QualityWarning } from '../api/types';
import { warningMeta } from '../lib/defects';

function WarningRow({ code, message, onMap }: { code: string; message?: string | null; onMap?: boolean }) {
  const m = warningMeta(code);
  const Icon = m.icon;
  return (
    <Group gap="sm" align="flex-start" wrap="nowrap">
      <span className="pw-warn-icon" aria-hidden>
        <Icon size={17} />
      </span>
      <Stack gap={2} style={{ minWidth: 0 }}>
        <Group gap={6}>
          <Text fz="sm" fw={600}>
            {m.label}
          </Text>
          {onMap && (
            <Badge size="xs" variant="outline" color="gray" radius="sm">
              shown on map
            </Badge>
          )}
        </Group>
        {message && <Text fz="sm">{message}</Text>}
        {m.explain && (
          <Text fz="xs" c="dimmed">
            {m.explain}
          </Text>
        )}
      </Stack>
    </Group>
  );
}

export function NoIssues({ children }: { children: string }) {
  return (
    <Group gap="xs" wrap="nowrap">
      <IconCircleCheck size={18} color="var(--pw-status-good)" aria-hidden />
      <Text fz="sm" c="dimmed">
        {children}
      </Text>
    </Group>
  );
}

export function DataWarningsList({ warnings }: { warnings: DataWarning[] }) {
  if (!warnings.length) return <NoIssues>No data-quality issues were reported for this survey.</NoIssues>;
  return (
    <Stack gap="md">
      {warnings.map((w, i) => (
        <WarningRow key={i} code={w.code} message={w.message} onMap={!!w.geometry} />
      ))}
    </Stack>
  );
}

export function QualityWarningsList({ warnings }: { warnings: QualityWarning[] }) {
  if (!warnings.length) return <NoIssues>No quality warnings for this finding.</NoIssues>;
  return (
    <Stack gap="md">
      {warnings.map((w, i) => (
        <WarningRow key={i} code={w.code} message={w.message} />
      ))}
    </Stack>
  );
}
