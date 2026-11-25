import React, { useState } from 'react';

export default function Auth({ api, onSignedIn }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setMessage('');
    try {
      if (mode === 'register') {
        await api('/auth/register', { method: 'POST', body: { email, password }, auth: false });
        const r = await api('/auth/login', { method: 'POST', body: { email, password }, auth: false });
        onSignedIn(r.access_token, true);
      } else {
        const r = await api('/auth/login', { method: 'POST', body: { email, password }, auth: false });
        onSignedIn(r.access_token, false);
      }
    } catch (err) { setMessage(err.message); } finally { setBusy(false); }
  }

  return (
    <section className="page auth-page">
      <div className="auth-copy">
        <h1>{mode === 'login' ? 'Sign in' : 'Create an account'}</h1>
        <p>An account lets you save schemes, keep your answers for next time and see personal matches on your dashboard. You can check eligibility and chat with Sahayak without one.</p>
        <p className="muted">No government ID is needed. Use a password of at least 10 characters.</p>
      </div>
      <form className="panel auth-form" onSubmit={submit}>
        <div className="field">
          <label htmlFor="email">Email address</label>
          <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" minLength={10} required autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {message && <p className="form-error" role="alert">{message}</p>}
        <button className="btn btn-primary wide" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
        <p className="switch">
          {mode === 'login' ? 'New to JanSetu?' : 'Already have an account?'}{' '}
          <button type="button" className="text-btn" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setMessage(''); }}>
            {mode === 'login' ? 'Create an account' : 'Sign in'}
          </button>
        </p>
      </form>
    </section>
  );
}
