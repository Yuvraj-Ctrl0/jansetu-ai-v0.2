import React from 'react';

/** Renders one question. Empty string means "not answered" (treated as unknown by the rule engine). */
export default function Field({ field, value, onChange }) {
  const id = `f-${field.key}`;
  const hintId = field.hint ? `${id}-hint` : undefined;
  const v = value ?? '';

  if (field.type === 'yesno') {
    const current = v === true ? 'yes' : v === false ? 'no' : '';
    return (
      <fieldset className={`field field-yesno${field.wide ? ' wide' : ''}`} aria-describedby={hintId}>
        <legend>{field.label}</legend>
        <div className="segmented" role="radiogroup">
          {[['yes', 'Yes', true], ['no', 'No', false], ['', 'Not sure', '']].map(([key, label, val]) => (
            <button key={key || 'skip'} type="button" role="radio" aria-checked={current === key}
              className={current === key ? 'on' : ''} onClick={() => onChange(field.key, val)}>{label}</button>
          ))}
        </div>
        {field.hint && <small id={hintId}>{field.hint}</small>}
      </fieldset>
    );
  }

  if (field.type === 'choice') {
    return (
      <fieldset className="field" aria-describedby={hintId}>
        <legend>{field.label}</legend>
        <div className="segmented" role="radiogroup">
          {field.options.map((o) => (
            <button key={o.value} type="button" role="radio" aria-checked={v === o.value}
              className={v === o.value ? 'on' : ''} onClick={() => onChange(field.key, v === o.value ? '' : o.value)}>
              {o.label}
            </button>
          ))}
        </div>
        {field.hint && <small id={hintId}>{field.hint}</small>}
      </fieldset>
    );
  }

  let control;
  if (field.type === 'select') {
    const known = field.options.some((o) => o.value === v);
    control = (
      <select id={id} value={v} aria-describedby={hintId} onChange={(e) => onChange(field.key, e.target.value)}>
        <option value="">Choose…</option>
        {!known && v !== '' && <option value={v}>{String(v)}</option>}
        {field.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    );
  } else {
    control = (
      <div className="affix">
        {field.prefix && <span className="prefix">{field.prefix}</span>}
        <input id={id} type={field.type === 'number' ? 'number' : 'text'} inputMode={field.type === 'number' ? 'decimal' : undefined}
          min={field.min} max={field.max && field.type === 'number' ? field.max : undefined}
          maxLength={field.type === 'text' ? field.max : undefined} step={field.step}
          placeholder={field.placeholder} value={v} aria-describedby={hintId}
          onChange={(e) => onChange(field.key, e.target.value)} />
        {field.suffix && <span className="suffix">{field.suffix}</span>}
      </div>
    );
  }
  return (
    <div className={`field${field.wide ? ' wide' : ''}`}>
      <label htmlFor={id}>{field.label}</label>
      {control}
      {field.hint && <small id={hintId}>{field.hint}</small>}
    </div>
  );
}

/** Convert form answers to API payload: numbers parsed, blanks become null. */
export function toPayload(answers, { dropTransient = false, transientKeys = [] } = {}) {
  const out = {};
  for (const [k, v] of Object.entries(answers)) {
    if (dropTransient && transientKeys.includes(k)) continue;
    if (v === '' || v === undefined) { out[k] = null; continue; }
    if (['age', 'household_size'].includes(k)) out[k] = Number.parseInt(v, 10);
    else if (['annual_income', 'land_hectares'].includes(k)) out[k] = Number(v);
    else out[k] = v;
  }
  return out;
}
