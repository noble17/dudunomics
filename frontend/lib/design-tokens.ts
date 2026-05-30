export const tokens = {
  surface: {
    100: '#101013',
    body: 'rgb(23,23,28)',
    200: 'rgb(28,28,33)',
    300: '#202025',
  },
  border: {
    outer: 'rgba(214,224,239,0.09)',
    inner: 'rgba(214,224,239,0.05)',
  },
  text: {
    primary: 'rgba(242,246,255,0.9)',
    secondary: 'rgba(253,253,254,0.89)',
    tertiary: 'rgba(242,242,255,0.47)',
    staticWhite: '#FFFFFF',
  },
  brand: {
    default: '#3182f6',
    hover: '#2562b9',
    pressed: '#29518e',
    text: '#4391ff',
    textHover: '#74b1f8',
  },
  positive: {
    fill: '#dc2e47',
    hover: '#ad2136',
    pressed: '#8d222f',
    text: '#f5445a',
    textHover: '#ff7187',
    weak: 'rgba(219,81,87,0.2)',
  },
  negative: {
    fill: '#3182f6',
    text: '#4391ff',
    weak: 'rgba(67,122,223,0.2)',
  },
  radius: {
    card: 8,
    chip: 32,
  },
} as const;

export const chartTheme = {
  bg: tokens.surface[100],
  grid: tokens.border.outer,
  axisLine: tokens.border.outer,
  text: tokens.text.tertiary,
  up: tokens.positive.fill,         // KR: 빨강 = 상승
  upText: tokens.positive.text,
  down: tokens.negative.fill,        // KR: 파랑 = 하락
  downText: tokens.negative.text,
  upWeak: tokens.positive.weak,
  downWeak: tokens.negative.weak,
  brand: tokens.brand.default,
  brandAlt: tokens.brand.text,
  palette: [
    tokens.brand.default,       // #3182f6
    tokens.positive.fill,       // #dc2e47
    tokens.brand.text,          // #4391ff
    tokens.positive.text,       // #f5445a
    '#a78bfa',
    '#22d3ee',
    '#facc15',
    '#f97316',
  ] as string[],
  cash: 'rgba(214,224,239,0.4)',
} as const;
