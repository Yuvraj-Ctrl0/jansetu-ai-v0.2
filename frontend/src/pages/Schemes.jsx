import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import SchemeList from '../components/SchemeList';
import { matchesQuery } from '../lib/format';

export default function Schemes({ schemes, meta, params, navigate, openScheme, savedIds, onToggleSave, canSave, homeState }) {
  const [query, setQuery] = useState(params.get('q') || '');
  const category = params.get('category') || '';
  const [scope, setScope] = useState('all');

  const setCategory = (c) => {
    const next = new URLSearchParams(params);
    if (c) next.set('category', c); else next.delete('category');
    navigate(`/schemes${next.toString() ? `?${next}` : ''}`, { replace: true });
  };

  const filtered = useMemo(() => schemes.filter((s) => {
    if (category && s.category !== category) return false;
    if (scope === 'central' && s.level === 'State') return false;
    if (scope === 'state' && !(s.states || []).includes(homeState)) return false;
    return matchesQuery(s, query);
  }), [schemes, category, scope, query, homeState]);

  return (
    <section className="page">
      <header className="page-head">
        <h1>All schemes</h1>
        <p>{schemes.length} central and state schemes with checked eligibility rules. Open any scheme to see benefits, documents and how to apply.</p>
      </header>

      <div className="filters">
        <label className="search">
          <Search size={18} aria-hidden="true" />
          <span className="sr-only">Search schemes</span>
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search: pension, scholarship, loan, किसान…" />
        </label>
        <div className="chips" role="group" aria-label="Filter by category">
          <button className={!category ? 'on' : ''} onClick={() => setCategory('')}>All</button>
          {meta.categories.map((c) => (
            <button key={c.name} className={category === c.name ? 'on' : ''} onClick={() => setCategory(c.name)}>
              {c.name} <span>{c.count}</span>
            </button>
          ))}
        </div>
        <div className="chips chips-small" role="group" aria-label="Filter by level">
          <button className={scope === 'all' ? 'on' : ''} onClick={() => setScope('all')}>Central and state</button>
          <button className={scope === 'central' ? 'on' : ''} onClick={() => setScope('central')}>Central only</button>
          {homeState && <button className={scope === 'state' ? 'on' : ''} onClick={() => setScope('state')}>{homeState} schemes</button>}
        </div>
      </div>

      <p className="result-count" aria-live="polite">{filtered.length} {filtered.length === 1 ? 'scheme' : 'schemes'}</p>
      <SchemeList schemes={filtered} onOpen={openScheme} savedIds={savedIds} onToggleSave={onToggleSave} canSave={canSave}
        emptyText="No scheme matches this search. Try a shorter word, or ask Sahayak in your own words." />
    </section>
  );
}
