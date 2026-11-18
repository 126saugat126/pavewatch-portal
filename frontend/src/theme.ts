import {
  Badge,
  Button,
  Chip,
  createTheme,
  Paper,
  SegmentedControl,
  TextInput,
  Tooltip,
  type MantineColorsTuple,
} from '@mantine/core';

/*
 * Design system v1 (docs/design-system.md).
 * Two bases (charcoal ink, warm paper) + one accent (lime = "machine annotation").
 * Severity colours are functional tokens in global.css and are not part of this palette.
 */

const sans = '"Archivo Variable", "Archivo", "Helvetica Neue", Arial, sans-serif';
const mono = '"IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace';

// Mantine dark scale, mapped to the ink tokens:
// 0 text · 2 dimmed · 4 hairline/border · 5 raised tile · 6 tile · 7 page ground.
const dark: MantineColorsTuple = [
  '#EEEAE3',
  '#D6D1C8',
  '#A39E95',
  '#7C776F',
  '#3F3B36',
  '#38342F',
  '#262422',
  '#1A1918',
  '#141312',
  '#0E0D0C',
];

// Lime accent. Dark mode uses shade 4 (#C6F432); light mode uses shade 8 (#4F6B00) so it reads on paper.
const lime: MantineColorsTuple = [
  '#F7FDE4',
  '#EEFBC6',
  '#E1F89A',
  '#D3F66A',
  '#C6F432',
  '#B3E01E',
  '#97C010',
  '#7A9C06',
  '#4F6B00',
  '#3A4F00',
];

export const theme = createTheme({
  colors: { dark, lime },
  primaryColor: 'lime',
  primaryShade: { light: 8, dark: 4 },
  autoContrast: true,
  luminanceThreshold: 0.45,
  black: '#111111',
  white: '#FFFFFF',

  fontFamily: sans,
  fontFamilyMonospace: mono,
  headings: {
    fontFamily: sans,
    fontWeight: '600',
    sizes: {
      h1: { fontSize: 'clamp(40px, 4.2vw, 64px)', lineHeight: '1', fontWeight: '300' },
      h2: { fontSize: '24px', lineHeight: '1.2', fontWeight: '600' },
      h3: { fontSize: '17px', lineHeight: '1.35', fontWeight: '500' },
    },
  },
  fontSizes: { xs: '12px', sm: '13px', md: '15px', lg: '17px', xl: '24px' },
  lineHeights: { md: '1.5' },

  // Tiles 4px, controls 0px. `xl` stays round for the segmented "pill" control only.
  radius: { xs: '2px', sm: '4px', md: '4px', lg: '4px', xl: '999px' },
  defaultRadius: 0,
  spacing: { xs: '8px', sm: '12px', md: '16px', lg: '24px', xl: '40px' },
  shadows: { xs: 'none', sm: 'none', md: 'none', lg: 'none', xl: 'none' },
  cursorType: 'pointer',
  focusRing: 'auto',

  components: {
    Paper: Paper.extend({ defaultProps: { radius: 'sm' } }),
    Button: Button.extend({ defaultProps: { radius: 0 } }),
    TextInput: TextInput.extend({ defaultProps: { radius: 0 } }),
    Badge: Badge.extend({ defaultProps: { radius: 'xs' } }),
    Chip: Chip.extend({ defaultProps: { radius: 'xs' } }),
    SegmentedControl: SegmentedControl.extend({ defaultProps: { radius: 'xl' } }),
    Tooltip: Tooltip.extend({ defaultProps: { radius: 'xs' } }),
  },
});
