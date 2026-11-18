import {
  Badge,
  Button,
  Chip,
  createTheme,
  Menu,
  Modal,
  Paper,
  Popover,
  SegmentedControl,
  TextInput,
  Tooltip,
  type MantineColorsTuple,
} from '@mantine/core';
import { MOTION } from './lib/motion';

/*
 * Design system v2 (docs/design-system.md), approved 2026-11-17.
 * Light-first: warm ivory ground, sage/mint surfaces, forest-teal actions, deep slate-teal text.
 * Blue = geography (flight path, positions). Terracotta = small highlights only.
 * Selection = forest-teal ring. Severity colours are functional tokens in global.css.
 */

const sans = '"Archivo Variable", "Archivo", "Helvetica Neue", Arial, sans-serif';
const mono = '"IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace';

// Mantine dark scale, mapped to the dark-theme tokens:
// 0 text · 2 dimmed · 4 hairline · 5 raised · 6 tile · 7 page ground.
const dark: MantineColorsTuple = [
  '#E6ECE7',
  '#C9D3CE',
  '#9DADA8',
  '#75857F',
  '#2B3735',
  '#263130',
  '#18201F',
  '#111716',
  '#0D1211',
  '#090D0C',
];

// Forest teal. Light mode uses shade 6 (#547B70); dark mode uses shade 4 so it reads on slate.
const teal: MantineColorsTuple = [
  '#EEF4F1',
  '#DCE8E3',
  '#BFD3CB',
  '#A0BDB2',
  '#82A79A',
  '#6A9285',
  '#547B70',
  '#46675E',
  '#38534C',
  '#2B403A',
];

// Sage, for quiet fills (chips, secondary buttons).
const sage: MantineColorsTuple = [
  '#F3F6F1',
  '#E8EDE5',
  '#D6DFD2',
  '#C1CEBD',
  '#A8BCA5',
  '#92A98F',
  '#7B947A',
  '#647B63',
  '#4E604D',
  '#394638',
];

const transition = { duration: MOTION.ms.base, timingFunction: MOTION.css.ease } as const;

export const theme = createTheme({
  colors: { dark, teal, sage },
  primaryColor: 'teal',
  primaryShade: { light: 6, dark: 4 },
  autoContrast: true,
  luminanceThreshold: 0.4,
  black: '#1F2D2B',
  white: '#FFFFFF',

  fontFamily: sans,
  fontFamilyMonospace: mono,
  headings: {
    fontFamily: sans,
    fontWeight: '600',
    sizes: {
      h1: { fontSize: 'clamp(28px, 2.6vw, 40px)', lineHeight: '1.1', fontWeight: '500' },
      h2: { fontSize: '20px', lineHeight: '1.25', fontWeight: '600' },
      h3: { fontSize: '16px', lineHeight: '1.35', fontWeight: '500' },
    },
  },
  fontSizes: { xs: '12px', sm: '13px', md: '15px', lg: '17px', xl: '22px' },
  lineHeights: { md: '1.5' },

  // Tiles 14px, controls 10px, small chips 6px; `xl` = full pill.
  radius: { xs: '4px', sm: '6px', md: '10px', lg: '14px', xl: '999px' },
  defaultRadius: 'md',
  spacing: { xs: '8px', sm: '12px', md: '16px', lg: '24px', xl: '40px' },
  shadows: {
    xs: '0 1px 2px rgba(31, 45, 43, 0.06)',
    sm: '0 1px 2px rgba(31, 45, 43, 0.06), 0 2px 6px -2px rgba(31, 45, 43, 0.08)',
    md: '0 10px 28px -12px rgba(31, 45, 43, 0.22)',
    lg: '0 18px 44px -16px rgba(31, 45, 43, 0.28)',
    xl: '0 24px 60px -20px rgba(31, 45, 43, 0.32)',
  },
  cursorType: 'pointer',
  focusRing: 'auto',

  components: {
    Paper: Paper.extend({ defaultProps: { radius: 'lg' } }),
    Button: Button.extend({ defaultProps: { radius: 'md' } }),
    TextInput: TextInput.extend({ defaultProps: { radius: 'md' } }),
    Badge: Badge.extend({ defaultProps: { radius: 'sm' } }),
    Chip: Chip.extend({ defaultProps: { radius: 'xl' } }),
    SegmentedControl: SegmentedControl.extend({
      defaultProps: { radius: 'xl', transitionDuration: MOTION.ms.slow, transitionTimingFunction: MOTION.css.ease },
    }),
    Tooltip: Tooltip.extend({ defaultProps: { radius: 'sm', transitionProps: { transition: 'pop', ...transition } } }),
    Popover: Popover.extend({ defaultProps: { radius: 'md', shadow: 'md', transitionProps: { transition: 'pop', ...transition } } }),
    Menu: Menu.extend({ defaultProps: { radius: 'md', shadow: 'md', transitionProps: { transition: 'pop-top-right', ...transition } } }),
    Modal: Modal.extend({
      defaultProps: { radius: 'lg', transitionProps: { transition: 'pop', duration: MOTION.ms.slow, timingFunction: MOTION.css.ease } },
    }),
  },
});
