import React, { useEffect, useRef, useState } from 'react';
import { X, ExternalLink, Bookmark, BookmarkCheck, MessageCircle, Check, Minus, HelpCircle } from 'lucide-react';
import { StatusBadge } from './SchemeList';
import { readLocal, writeLocal, schemeScope } from '../lib/format';

function CheckIcon({ result }) {
  if (result === 'pass') return <Check size={16} className="ck ck-pass" aria-label="Met" />;
  if (result === 'fail') return <Minus size={16} className="ck ck-fail" aria-label="Not met" />;
  return <HelpCircle size={16} className="ck ck-unknown" aria-label="Not answered" />;
}

export default function SchemeDrawer({ scheme, onClose, saved, canSave, onToggleSave, onAsk }) {
  const closeRef = useRef(null);
  const storeKey = scheme ? `jansetu-docs-${scheme.id}` : null;
  const [ticked, setTicked] = useState({});

  useEffect(() => {
    if (!scheme) return undefined;
    setTicked(readLocal(storeKey, {}));
    closeRef.current?.focus();
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    document.body.classList.add('no-scroll');
    return () => { document.removeEventListener('keydown', onKey); document.body.classList.remove('no-scroll'); };
  }, [scheme, storeKey, onClose]);

  if (!scheme) return null;
  const outcome = scheme.eligibility;
  const docs = scheme.documents || [];
  const toggleDoc = (d) => {
    const next = { ...ticked, [d]: !ticked[d] };
    setTicked(next);
    writeLocal(storeKey, next);
  };
  const readyCount = docs.filter((d) => ticked[d]).length;

  return (
    <div className="drawer-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <header className="drawer-head">
          <div>
            <p className="drawer-kicker">{scheme.category} <span>{scheme.level === 'State' ? 'State scheme' : 'Central scheme'}, {schemeScope(scheme)}</span></p>
            <h2 id="drawer-title">{scheme.name}</h2>
            {scheme.ministry && <p className="drawer-ministry">{scheme.ministry}</p>}
          </div>
          <button ref={closeRef} className="icon-btn" onClick={onClose} aria-label="Close details"><X size={20} /></button>
        </header>

        <div className="drawer-body">
          <p className="lead">{scheme.description}</p>

          {scheme.benefits && (
            <section className="d-sec benefit-box">
              <h3>What you get</h3>
              <p>{scheme.benefits}</p>
            </section>
          )}

          {outcome && (
            <section className="d-sec">
              <h3>Your check <StatusBadge status={outcome.status} /></h3>
              {outcome.checks.length ? (
                <ul className="checks">
                  {outcome.checks.map((c, i) => (
                    <li key={i} className={`check-${c.result}`}>
                      <CheckIcon result={c.result} />
                      <span>{c.label}{c.actual_display && <em> You said: {c.actual_display}</em>}
                        {c.result === 'unknown' && <em> Not answered yet</em>}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="muted">Eligibility for this scheme comes from official databases. Use the official website to check.</p>}
            </section>
          )}

          <section className="d-sec">
            <h3>Who can apply</h3>
            {scheme.eligibility_criteria?.length > 0 && (
              <>
                <p className="sub">Checked automatically by JanSetu</p>
                <ul className="plain">{scheme.eligibility_criteria.map((c) => <li key={c}>{c}</li>)}</ul>
              </>
            )}
            {scheme.additional_conditions?.length > 0 && (
              <>
                <p className="sub">Also confirm before applying</p>
                <ul className="plain">{scheme.additional_conditions.map((c) => <li key={c}>{c}</li>)}</ul>
              </>
            )}
          </section>

          {docs.length > 0 && (
            <section className="d-sec">
              <h3>Documents to keep ready <span className="count">{readyCount} of {docs.length} ready</span></h3>
              <ul className="doc-list">
                {docs.map((d) => (
                  <li key={d}>
                    <label><input type="checkbox" checked={!!ticked[d]} onChange={() => toggleDoc(d)} /> {d}</label>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {scheme.how_to_apply && (
            <section className="d-sec">
              <h3>How to apply</h3>
              <p>{scheme.how_to_apply}</p>
            </section>
          )}

          <p className="verified">
            {scheme.source_verified_at
              ? `Details checked against public sources on ${new Date(scheme.source_verified_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}. Rules can change, so confirm on the official website.`
              : 'Confirm current rules on the official website.'}
          </p>
        </div>

        <footer className="drawer-foot">
          <a className="btn btn-primary" href={scheme.official_url} target="_blank" rel="noopener noreferrer">
            Open official website <ExternalLink size={16} aria-hidden="true" />
          </a>
          <button className="btn btn-quiet" onClick={() => onAsk(`Tell me about ${scheme.name}: who can apply and how?`)}>
            <MessageCircle size={16} aria-hidden="true" /> Ask Sahayak
          </button>
          {canSave && (
            <button className="btn btn-quiet" onClick={() => onToggleSave(scheme)} aria-pressed={saved}>
              {saved ? <BookmarkCheck size={16} /> : <Bookmark size={16} />} {saved ? 'Saved' : 'Save'}
            </button>
          )}
        </footer>
      </aside>
    </div>
  );
}
