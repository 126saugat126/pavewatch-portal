import { notifications } from '@mantine/notifications';
import { IconAlertTriangle, IconCheck, IconInfoCircle, IconX } from '@tabler/icons-react';
import type { ReactNode } from 'react';

type Kind = 'success' | 'info' | 'warning' | 'error';

const ICON: Record<Kind, ReactNode> = {
  success: <IconCheck size={16} stroke={2} />,
  info: <IconInfoCircle size={16} stroke={2} />,
  warning: <IconAlertTriangle size={16} stroke={2} />,
  error: <IconX size={16} stroke={2} />,
};

/** Small wrapper so every toast in the app looks and behaves the same. */
function show(kind: Kind, title: ReactNode, message?: ReactNode, id?: string) {
  notifications.show({
    id,
    title,
    message: message ?? '',
    icon: ICON[kind],
    autoClose: kind === 'error' ? 7000 : 4000,
    withBorder: true,
    radius: 'lg',
    className: `pw-toast pw-toast--${kind}`,
  });
}

/** Copy to the clipboard and confirm with a toast (or explain why it failed). */
export function copyText(text: string, title = 'Copied') {
  const fail = () => toast.warning('Could not copy', `The browser blocked the clipboard. Select the text and press Ctrl+C: ${text}`);
  if (!navigator.clipboard?.writeText) return fail();
  navigator.clipboard.writeText(text).then(() => toast.success(title, text), fail);
}

export const toast = {
  success: (title: ReactNode, message?: ReactNode, id?: string) => show('success', title, message, id),
  info: (title: ReactNode, message?: ReactNode, id?: string) => show('info', title, message, id),
  warning: (title: ReactNode, message?: ReactNode, id?: string) => show('warning', title, message, id),
  error: (title: ReactNode, message?: ReactNode, id?: string) => show('error', title, message, id),
};
