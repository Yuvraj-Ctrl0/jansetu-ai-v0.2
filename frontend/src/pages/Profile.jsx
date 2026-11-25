import React, { useEffect, useMemo, useState } from 'react';
import Field, { toPayload } from '../components/Field';
import { profileSections } from '../lib/fields';

export default function Profile({ api, meta, notify, onSaved }) {
  const sections = useMemo(() => profileSections(meta), [meta]);
  const [answers, setAnswers] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/profile').then((p) => setAnswers(Object.fromEntries(Object.entries(p).map(([k, v]) => [k, v ?? ''])))).catch((e) => setError(e.message));
  }, [api]);

  const set = (k, v) => setAnswers((a) => ({ ...a, [k]: v, ...(k === 'owns_agri_land' && v !== true ? { land_hectares: '' } : {}) }));

  async function save(e) {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      const keys = new Set(sections.flatMap((s) => s.fields.map((f) => f.key)));
      const payload = toPayload(Object.fromEntries(Object.entries(answers).filter(([k]) => keys.has(k))));
      const saved = await api('/profile', { method: 'PUT', body: payload });
      setAnswers(Object.fromEntries(Object.entries(saved).map(([k, v]) => [k, v ?? ''])));
      notify('Profile saved.');
      onSaved?.(saved);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  if (!answers) return <section className="page"><p className="muted">{error || 'Loading your profile…'}</p></section>;
  return (
    <section className="page">
      <header className="page-head">
        <h1>Your profile</h1>
        <p>Saved answers are used for your dashboard matches and by Sahayak. Leave anything blank that you prefer not to share.</p>
      </header>
      <form onSubmit={save} className="profile-form">
        {sections.map((s) => (
          <fieldset key={s.id} className="profile-section">
            <legend>{s.title}</legend>
            <div className="form-grid">
              {s.fields.filter((f) => !f.showIf || f.showIf(answers)).map((f) => (
                <Field key={f.key} field={f} value={answers[f.key]} onChange={set} />
              ))}
            </div>
          </fieldset>
        ))}
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="sticky-save"><button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save profile'}</button></div>
      </form>
    </section>
  );
}
