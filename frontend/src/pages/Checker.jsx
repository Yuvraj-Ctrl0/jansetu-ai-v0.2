import React, { useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, MessageCircle, Save, RotateCcw } from 'lucide-react';
import Field, { toPayload } from '../components/Field';
import SchemeList from '../components/SchemeList';
import { eligibilitySteps, TRANSIENT_KEYS, answeredCount } from '../lib/fields';

export default function Checker({ api, meta, draft, setDraft, openScheme, signedIn, askSahayak, notify, savedIds, onToggleSave }) {
  const steps = useMemo(() => eligibilitySteps(meta), [meta]);
  const [step, setStep] = useState(0);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showIneligible, setShowIneligible] = useState(false);
  const allFields = steps.flatMap((s) => s.fields);
  const total = allFields.length;

  const set = (k, v) => setDraft((d) => {
    const next = { ...d, [k]: v };
    if (k === 'owns_agri_land' && v !== true) next.land_hectares = '';
    if (k === 'gender' && v !== 'Woman') next.pregnant_or_lactating = '';
    return next;
  });

  async function runCheck() {
    setBusy(true); setError('');
    try {
      const payload = toPayload(draft);
      const allowed = new Set(allFields.map((f) => f.key));
      Object.keys(payload).forEach((k) => { if (!allowed.has(k)) delete payload[k]; });
      const res = await api('/eligibility/check', { method: 'POST', body: payload, auth: false });
      setResult(res);
      setStep(steps.length);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  async function saveToProfile() {
    try {
      const payload = toPayload(draft, { dropTransient: true, transientKeys: TRANSIENT_KEYS });
      const allowed = new Set(allFields.filter((f) => !f.transient).map((f) => f.key));
      Object.keys(payload).forEach((k) => { if (!allowed.has(k)) delete payload[k]; });
      await api('/profile', { method: 'PUT', body: payload });
      notify('Answers saved to your profile.');
    } catch (e) { notify(e.message); }
  }

  const jumpToField = (fieldKey) => {
    const idx = steps.findIndex((s) => s.fields.some((f) => f.key === fieldKey));
    if (idx >= 0) { setStep(idx); window.scrollTo({ top: 0, behavior: 'smooth' }); }
  };

  const groups = result ? {
    ok: result.results.filter((r) => r.eligibility.status === 'eligible_by_recorded_rules'),
    info: result.results.filter((r) => r.eligibility.status === 'insufficient_information'),
    no: result.results.filter((r) => r.eligibility.status === 'ineligible'),
  } : null;

  return (
    <section className="page checker">
      <header className="page-head">
        <h1>Check your eligibility</h1>
        <p>Answer what you can. Every answer is optional, and you will see exactly which rule each scheme needs.</p>
      </header>

      <ol className="stepper" aria-label="Progress">
        {[...steps.map((s) => s.title), 'Your results'].map((title, i) => (
          <li key={title} className={i === step ? 'current' : i < step ? 'done' : ''}>
            <button onClick={() => (i < steps.length ? setStep(i) : result && setStep(i))} disabled={i === steps.length && !result}
              aria-current={i === step ? 'step' : undefined}>
              <span className="step-no">{i + 1}</span>{title}
            </button>
          </li>
        ))}
      </ol>

      {step < steps.length && (
        <div className="wizard">
          <div className="wizard-head">
            <h2>{steps[step].title}</h2>
            <p>{steps[step].intro}</p>
            <p className="answered">{answeredCount(draft)} of {total} questions answered</p>
          </div>
          <div className="form-grid">
            {steps[step].fields.filter((f) => !f.showIf || f.showIf(draft)).map((f) => (
              <Field key={f.key} field={f} value={draft[f.key]} onChange={set} />
            ))}
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="wizard-nav">
            <button className="btn btn-quiet" onClick={() => setStep(step - 1)} disabled={step === 0}>
              <ArrowLeft size={18} aria-hidden="true" /> Back
            </button>
            <div className="wizard-nav-right">
              {step < steps.length - 1 && (
                <button className="text-btn" onClick={runCheck} disabled={busy}>See results now</button>
              )}
              {step < steps.length - 1 ? (
                <button className="btn btn-primary" onClick={() => setStep(step + 1)}>Next <ArrowRight size={18} aria-hidden="true" /></button>
              ) : (
                <button className="btn btn-primary" onClick={runCheck} disabled={busy}>{busy ? 'Checking…' : 'Show my schemes'}</button>
              )}
            </div>
          </div>
        </div>
      )}

      {step === steps.length && result && (
        <div className="results">
          <div className="results-summary">
            <p className="tally">
              <strong>{groups.ok.length} {groups.ok.length === 1 ? 'scheme' : 'schemes'}</strong> match every rule we can check.
              {' '}{groups.info.length} need more details and {groups.no.length} do not fit.
            </p>
            <div className="results-actions">
              <button className="btn btn-chakra" onClick={() => askSahayak('Which schemes am I eligible for, and what should I apply for first?')}>
                <MessageCircle size={18} aria-hidden="true" /> Ask Sahayak about my results
              </button>
              {signedIn && <button className="btn btn-quiet" onClick={saveToProfile}><Save size={18} aria-hidden="true" /> Save answers to profile</button>}
              <button className="btn btn-quiet" onClick={() => setStep(0)}><RotateCcw size={18} aria-hidden="true" /> Change answers</button>
            </div>
          </div>

          {result.suggested_questions.length > 0 && (
            <aside className="improve">
              <h2>Answer these to check more schemes</h2>
              <ul>
                {result.suggested_questions.map((q) => (
                  <li key={q.field}>
                    <button onClick={() => jumpToField(q.field)}>{q.question}</button>
                    <span>affects {q.schemes_affected} {q.schemes_affected === 1 ? 'scheme' : 'schemes'}</span>
                  </li>
                ))}
              </ul>
            </aside>
          )}

          <h2 className="group-title tone-ok">You may be eligible <span>{groups.ok.length}</span></h2>
          <SchemeList schemes={groups.ok} onOpen={openScheme} showStatus savedIds={savedIds} onToggleSave={onToggleSave} canSave={signedIn}
            emptyText="No scheme matches every rule yet. Answering the questions above usually helps." />

          <h2 className="group-title tone-info">Need more details <span>{groups.info.length}</span></h2>
          <SchemeList schemes={groups.info} onOpen={openScheme} showStatus savedIds={savedIds} onToggleSave={onToggleSave} canSave={signedIn}
            emptyText="Nothing pending." />

          <h2 className="group-title tone-no">
            <button className="text-btn" onClick={() => setShowIneligible(!showIneligible)} aria-expanded={showIneligible}>
              {showIneligible ? 'Hide' : 'Show'} schemes that do not fit <span>{groups.no.length}</span>
            </button>
          </h2>
          {showIneligible && <SchemeList schemes={groups.no} onOpen={openScheme} showStatus />}

          <p className="disclaimer">{result.disclaimer}</p>
        </div>
      )}
    </section>
  );
}
