export const inr = (n) => (n === null || n === undefined || n === '' ? '' : '₹' + Number(n).toLocaleString('en-IN'));

export const STATUS = {
  eligible_by_recorded_rules: { label: 'May be eligible', tone: 'ok' },
  insufficient_information: { label: 'Needs more details', tone: 'info' },
  ineligible: { label: 'Not eligible', tone: 'no' },
};

export const CATEGORY_NOTES = {
  Agriculture: 'Income support, crop insurance, farm credit',
  'Business & Livelihood': 'Loans and subsidies to start or grow work',
  Education: 'Scholarships and education loans',
  'Employment & Skills': 'Jobs, internships and free training',
  'Energy & Utilities': 'LPG connections and rooftop solar',
  'Food Security': 'Free ration under NFSA',
  Health: 'Hospital cover and maternity support',
  Housing: 'Help to build or buy a pucca house',
  'Insurance & Banking': 'Bank accounts and low-cost insurance',
  'Pensions & Social Security': 'Old-age, widow and disability pensions',
  'Women & Child': 'Support for women, mothers and girls',
};

export function schemeScope(s) {
  if (s.states && s.states.length) return `${s.states.join(', ')} only`;
  return 'All India';
}

export function matchesQuery(s, query) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const hay = [s.name, s.description, s.category, s.benefits, s.ministry, ...(s.tags || [])].join(' ').toLowerCase();
  return words.every((w) => hay.includes(w) || (w.endsWith('s') && hay.includes(w.slice(0, -1))));
}

export function readLocal(key, fallback) {
  try { const v = window.localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
}

export function writeLocal(key, value) {
  try { window.localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ }
}
