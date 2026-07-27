import { colorSchemeDark, themeQuartz } from 'ag-grid-community'

/**
 * Tema AG Grid allineato al design system WikiScout (verde lime su sfondo scuro).
 * Basato sulla nuova Theming API di AG Grid v33+ (niente piu' CSS importati).
 */
export const wikiscoutGridTheme = themeQuartz.withPart(colorSchemeDark).withParams({
  accentColor: '#6bec68',
  backgroundColor: '#1f1f1f',
  foregroundColor: '#ffffff',
  borderColor: '#2c2c2c',
  chromeBackgroundColor: '#1f1f1f',
  headerTextColor: '#a3a3a3',
  headerFontWeight: 500,
  oddRowBackgroundColor: 'transparent',
  rowHoverColor: '#262626',
  selectedRowBackgroundColor: '#262626',
  fontFamily: { googleFont: 'Albert Sans' },
  fontSize: 14,
  spacing: 8,
  borderRadius: 6,
  wrapperBorderRadius: 10,
  wrapperBorder: true,
  rowBorder: true,
  columnBorder: false,
})
