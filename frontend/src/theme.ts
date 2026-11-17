import { createTheme } from '@mantine/core';

const font = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

export const theme = createTheme({
  primaryColor: 'blue',
  fontFamily: font,
  headings: { fontFamily: font, fontWeight: '650' },
  defaultRadius: 'md',
  cursorType: 'pointer',
});
