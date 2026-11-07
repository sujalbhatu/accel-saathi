// Screen labels, one JSON file per language in ./locales. Advisor conversation text comes translated from the server.
// English is the source; missing keys fall back to English, so a new language can never break a screen.
const files = import.meta.glob('./locales/*.json', { eager: true })
const L = Object.fromEntries(Object.entries(files).map(([path, mod]) => [path.match(/(\w+)\.json$/)[1], mod.default || mod]))

// Order shown in the picker: by share of leads in the data (Hindi 43%, English 23%, Marathi 10%, ...).
const ORDER = ['en', 'hi', 'mr', 'kn', 'gu', 'te', 'ta', 'bn', 'pa', 'ml']
export const LANGS = ORDER.filter((l) => L[l]).map((l) => ({ code: l, name: L[l].name, label: L[l].label }))
export const SPEECH_LANG = Object.fromEntries(ORDER.filter((l) => L[l]).map((l) => [l, L[l].speech]))

export function tr(lang, key, vars = {}) {
  const v = (L[lang] && L[lang].ui[key]) ?? L.en.ui[key] ?? key
  return typeof v === 'string' ? v.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '') : v
}
