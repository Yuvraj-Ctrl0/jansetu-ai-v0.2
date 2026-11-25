import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, MessageCircle } from 'lucide-react';
import { CATEGORY_NOTES } from '../lib/format';
import { slug } from '../components/SchemeList';

const GENDER_WORDS = { Woman: 'woman', Man: 'man', Transgender: 'transgender person', 'Non-binary': 'non-binary person' };

function Inline({ label, children, width }) {
  return <label className="inline-field" style={width ? { '--w': width } : undefined}><span className="sr-only">{label}</span>{children}</label>;
}

/** Size an inline select to the text it currently shows, so the sentence reads naturally. */
const fit = (text, extra = 34) => `calc(${Math.max(String(text).length, 3) * 0.56}em + ${extra}px)`;

export default function Home({ api, meta, draft, setDraft, navigate, openScheme, askSahayak }) {
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const timer = useRef(null);
  const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  const filled = ['age', 'state', 'occupation', 'gender'].filter((k) => draft[k] !== undefined && draft[k] !== '').length;

  useEffect(() => {
    clearTimeout(timer.current);
    if (!filled) { setPreview(null); return undefined; }
    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        const body = {};
        ['age', 'state', 'occupation', 'gender'].forEach((k) => {
          if (draft[k] !== undefined && draft[k] !== '') body[k] = k === 'age' ? Number.parseInt(draft[k], 10) : draft[k];
        });
        if (body.age !== undefined && (Number.isNaN(body.age) || body.age < 0 || body.age > 120)) { setLoading(false); return; }
        setPreview(await api('/eligibility/check', { method: 'POST', body, auth: false }));
      } catch { setPreview(null); } finally { setLoading(false); }
    }, 350);
    return () => clearTimeout(timer.current);
  }, [draft.age, draft.state, draft.occupation, draft.gender]); // eslint-disable-line react-hooks/exhaustive-deps

  const eligible = preview?.results.filter((r) => r.eligibility.status === 'eligible_by_recorded_rules') || [];
  const pending = preview?.summary.needs_information ?? 0;
  const occLabel = (meta.occupations.find((o) => o.value === draft.occupation)?.label || 'choose one').toLowerCase();
  const genderLabel = GENDER_WORDS[draft.gender] || 'person';

  return (
    <>
      <section className="hero">
        <p className="hero-hindi" lang="hi">आपके लिए सरकारी योजनाएँ</p>
        <h1>Find the government schemes meant for you.</h1>
        <div className="hero-grid">
        <form className="sentence" onSubmit={(e) => { e.preventDefault(); navigate('/check'); }}>
          <p>
            I am a{' '}
            <Inline label="Gender" width={fit(genderLabel)}>
              <select value={draft.gender || ''} onChange={(e) => set('gender', e.target.value)}>
                <option value="">person</option>
                {meta.genders.filter((g) => GENDER_WORDS[g]).map((g) => <option key={g} value={g}>{GENDER_WORDS[g]}</option>)}
              </select>
            </Inline>{' '}aged{' '}
            <Inline label="Age" width="2.6em">
              <input type="number" min="0" max="120" inputMode="numeric" placeholder="__" value={draft.age || ''}
                onChange={(e) => set('age', e.target.value.slice(0, 3))} />
            </Inline>, living in{' '}
            <Inline label="State" width={fit(draft.state || 'my state')}>
              <select value={draft.state || ''} onChange={(e) => set('state', e.target.value)}>
                <option value="">my state</option>
                {meta.states.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Inline>
            . My occupation is{' '}
            <Inline label="Occupation" width={fit(occLabel)}>
              <select value={draft.occupation || ''} onChange={(e) => set('occupation', e.target.value)}>
                <option value="">choose one</option>
                {meta.occupations.map((o) => <option key={o.value} value={o.value}>{o.label.toLowerCase()}</option>)}
              </select>
            </Inline>.
          </p>
        </form>

        <div className={`hero-result${loading ? ' is-loading' : ''}`} aria-live="polite">
          {!preview && <p className="hint-line">Fill in the sentence above and matching schemes from our list of {meta.published_count} appear here.</p>}
          {preview && (
            <>
              <p className="tally">
                <strong>{eligible.length} {eligible.length === 1 ? 'scheme matches' : 'schemes match'}</strong> these details so far.
                {pending > 0 && <> {pending} more need a few answers before we can tell.</>}
              </p>
              {eligible.length > 0 && (
                <ul className="mini-list">
                  {eligible.slice(0, 4).map((s) => (
                    <li key={s.id}><button onClick={() => openScheme(s)}><b>{s.name}</b><span>{s.benefits}</span></button></li>
                  ))}
                </ul>
              )}
              <button className="btn btn-primary" onClick={() => navigate('/check')}>
                Answer a few more questions <ArrowRight size={18} aria-hidden="true" />
              </button>
            </>
          )}
        </div>
        </div>
      </section>

      <section className="home-band">
        <div className="band-head">
          <h2>Browse by need</h2>
          <button className="text-btn" onClick={() => navigate('/schemes')}>See all {meta.published_count} schemes</button>
        </div>
        <ul className="need-grid">
          {meta.categories.map((c) => (
            <li key={c.name}>
              <button onClick={() => navigate(`/schemes?category=${encodeURIComponent(c.name)}`)}>
                <span className={`cat-dot cat-${slug(c.name)}`} aria-hidden="true" />
                <span className="need-name">{c.name}</span>
                <span className="need-count">{c.count}</span>
                <span className="need-note">{CATEGORY_NOTES[c.name] || ''}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="home-band split">
        <div>
          <h2>Ask in Hindi or English</h2>
          <p>Sahayak answers questions about schemes from JanSetu's checked records, shows the official link with every answer, and never asks for your Aadhaar or bank details.</p>
          <button className="btn btn-chakra" onClick={() => askSahayak('मुझे घर बनाने के लिए कौन सी योजना है?')}>
            <MessageCircle size={18} aria-hidden="true" /> Try a question
          </button>
        </div>
        <div className="sample-chat" aria-hidden="true">
          <p className="s-user" lang="hi">विधवा पेंशन के लिए कौन से कागज़ चाहिए?</p>
          <p className="s-bot"><b>Pradhan Mantri Vidhawa Pension Yojana</b> needs your husband's death certificate, age proof, BPL card, Aadhaar and a bank account.</p>
        </div>
      </section>

      <section className="home-band principles">
        <h2>How JanSetu decides</h2>
        <dl>
          <div><dt>Rules come from official sources</dt><dd>Each scheme's conditions were checked against government and public sources, with the date shown on every scheme.</dd></div>
          <div><dt>Unknown never counts as yes</dt><dd>If you skip a question, schemes that depend on it show as "needs more details", not as a match.</dd></div>
          <div><dt>The department has the final word</dt><dd>Results are a preliminary guide. Always confirm on the official website before you apply.</dd></div>
        </dl>
      </section>
    </>
  );
}
