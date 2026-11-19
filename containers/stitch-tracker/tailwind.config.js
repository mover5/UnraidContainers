/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#1c1618', // page — dark plum-brown, easy on the eyes in the evening
        panel: '#261e21',
        panel2: '#30262a',
        edge: '#45383d',
        wool: '#f0a77c', // primary accent — warm peach yarn
        sage: '#9cc49a',
        warn: '#f4c565',
        bad: '#ef8a80',
        muted: '#a8979c',
        cream: '#f5ece6',
      },
      fontFamily: {
        serif: ['ui-serif', 'Georgia', 'Cambria', 'serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
