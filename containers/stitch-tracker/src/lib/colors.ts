// Starting hexes for common yarn color words, so "8 Purple" gets a sensible
// swatch without fiddling. Users can tweak any color afterward.
export const COLOR_WORDS: Record<string, string> = {
  purple: '#6e3f8f',
  plum: '#6b2d5c',
  lavender: '#b39ddb',
  lilac: '#c8a2c8',
  violet: '#7f4fc9',
  camel: '#c19a6b',
  tan: '#d2b48c',
  beige: '#d9c7a7',
  oatmeal: '#d8ccb4',
  cream: '#f3e9d2',
  ivory: '#f6f0e1',
  white: '#f4f4f2',
  bronze: '#a0662c',
  copper: '#b87333',
  gold: '#d4a537',
  mustard: '#d1a10f',
  yellow: '#efd04a',
  ochre: '#c88a1e',
  orange: '#e57c2c',
  rust: '#a8461c',
  terracotta: '#c5643f',
  brick: '#9b3b2c',
  red: '#c23b33',
  burgundy: '#7a1f2b',
  maroon: '#6d2030',
  wine: '#6f2a3b',
  pink: '#e48fae',
  rose: '#d07a8c',
  coral: '#ea7a63',
  peach: '#f2b28c',
  green: '#4d7d45',
  olive: '#7a7a33',
  sage: '#9cb08a',
  moss: '#6b7d3a',
  forest: '#2f5233',
  emerald: '#2e8b57',
  mint: '#a6d8b8',
  teal: '#2a7f7a',
  turquoise: '#3cb5b0',
  aqua: '#6fcfd0',
  blue: '#3b6fb6',
  navy: '#1f2f56',
  denim: '#4f6d8f',
  sky: '#8ec1e6',
  royal: '#2f4fb5',
  brown: '#6b4428',
  chocolate: '#4e2f1c',
  chestnut: '#7b3f22',
  grey: '#8a8b8d',
  gray: '#8a8b8d',
  charcoal: '#3f4144',
  silver: '#b8babd',
  black: '#222224',
};

// Fallbacks for names we don't recognize — distinct, yarn-ish tones.
const FALLBACK = ['#c97b63', '#7b9e89', '#d6b25e', '#8b6aa8', '#5d8aa8', '#b56576', '#8c7a5b', '#6d9c5a'];

/** Guess a hex for a color name ("Heather Grey" -> grey), or a fallback by index. */
export function guessHex(name: string, fallbackIndex = 0): string {
  const words = name.toLowerCase().split(/[^a-z]+/).filter(Boolean);
  for (let i = words.length - 1; i >= 0; i--) {
    const hit = COLOR_WORDS[words[i]];
    if (hit) return hit;
  }
  return FALLBACK[fallbackIndex % FALLBACK.length];
}

/** True when a phrase reads like a yarn color name rather than an instruction. */
export function looksLikeColor(phrase: string): boolean {
  const words = phrase.toLowerCase().split(/[^a-z]+/).filter(Boolean);
  if (words.length === 0 || words.length > 3) return false;
  if (!/^[a-z][a-z\s'-]*$/i.test(phrase.trim())) return false;
  return words.some((w) => w in COLOR_WORDS);
}
