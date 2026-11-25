import React, { useEffect, useState } from 'react';
import { ArrowRight } from 'lucide-react';

const FIELD_NAMES = {
  age: 'age', state: 'state', district: 'district', occupation: 'occupation', annual_income: 'family income',
  gender: 'gender', area: 'rural or urban', social_category: 'social category', education_level: 'education',
  income_tax_payer: 'income tax', bpl_card: 'ration card type', has_bank_account: 'bank account',
};

export default function Dashboard({ api, navigate, openSchemeById, savedCount }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { api('/dashboard').then(setData).catch((e) => setError(e.message)); }, [api]);
  if (!data) return <section className="page"><p className="muted">{error || 'Loading your dashboard…'}</p></section>;
  const name = data.profile.full_name;
  const pct = data.completion_percentage;
  const s = data.screening_summary;

  return (
    <section className="page dashboard">
      <header className="page-head">
        <h1>{name ? `Namaste, ${name.split(' ')[0]}` : 'Your dashboard'}</h1>
        <p>Matches below use the details saved in your profile.</p>
      </header>

      <div className="dash-grid">
        <section className="panel">
          <h2>Profile</h2>
          <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Profile completion">
            <div style={{ width: `${pct}%` }} />
          </div>
          <p>{pct}% complete{data.missing_fields.length > 0 && <>. Still missing: {data.missing_fields.map((f) => FIELD_NAMES[f] || f).join(', ')}.</>}</p>
          <button className="btn btn-quiet" onClick={() => navigate('/profile')}>Update profile</button>
        </section>

        <section className="panel">
          <h2>Scheme check</h2>
          <p className="tally small">
            <strong>{s.eligible}</strong> may fit you, <strong>{s.needs_information}</strong> need more details,{' '}
            <strong>{s.ineligible}</strong> do not fit. You have saved {savedCount} {savedCount === 1 ? 'scheme' : 'schemes'}.
          </p>
          <button className="btn btn-primary" onClick={() => navigate('/check')}>Run a full check <ArrowRight size={18} aria-hidden="true" /></button>
        </section>
      </div>

      <section className="panel">
        <h2>Best matches for you</h2>
        {data.top_matches.length ? (
          <ul className="mini-list">
            {data.top_matches.map((m) => (
              <li key={m.id}><button onClick={() => openSchemeById(m.id)}><b>{m.name}</b><span>{m.benefits}</span></button></li>
            ))}
          </ul>
        ) : <p className="muted">No full matches yet. Add more details to your profile to see matches.</p>}
      </section>

      {data.suggested_questions.length > 0 && (
        <section className="panel">
          <h2>Questions that would unlock more schemes</h2>
          <ul className="q-list">
            {data.suggested_questions.map((q) => (
              <li key={q.field}><span>{q.question}</span><em>{q.schemes_affected} {q.schemes_affected === 1 ? 'scheme' : 'schemes'}</em></li>
            ))}
          </ul>
          <button className="text-btn" onClick={() => navigate('/profile')}>Answer in your profile</button>
        </section>
      )}
    </section>
  );
}
