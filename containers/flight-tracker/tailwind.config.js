/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0b1220',
        panel: '#111a2e',
        panel2: '#16223c',
        edge: '#243250',
        sky: '#38bdf8',
        accent: '#22d3ee',
        good: '#34d399',
        warn: '#fbbf24',
        bad: '#f87171',
        muted: '#8aa0c6',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
