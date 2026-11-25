import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { LogOut } from 'lucide-react';
import { createApi } from './lib/api';
import Home from './pages/Home';
import Schemes from './pages/Schemes';
import Checker from './pages/Checker';
import Profile from './pages/Profile';
import Dashboard from './pages/Dashboard';
import Auth from './pages/Auth';
import SchemeList from './components/SchemeList';
import SchemeDrawer from './components/SchemeDrawer';
import ChatWidget from './components/ChatWidget';

function readToken() { try { return sessionStorage.getItem('token') || ''; } catch { return ''; } }
function writeToken(t) { try { if (t) sessionStorage.setItem('token', t); else sessionStorage.removeItem('token'); } catch { /* ignore */ } }

function parseHash() {
  const raw = window.location.hash.replace(/^#/, '') || '/';
  const [path, qs] = raw.split('?');
  return { path: path || '/', params: new URLSearchParams(qs || '') };
}

function Logo() {
  return (
    <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true" className="logo-mark">
      <path d="M3 24 Q17 4 31 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M2 25.5h30" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M10 25V17M17 25V13M24 25V17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity=".55" />
    </svg>
  );
}

export default function App() {
  const [token, setToken] = useState(readToken);
  const [route, setRoute] = useState(parseHash);
  const [meta, setMeta] = useState(null);
  const [schemes, setSchemes] = useState([]);
  const [loadError, setLoadError] = useState('');
  const [savedIds, setSavedIds] = useState(new Set());
  const [draft, setDraft] = useState({});
  const [drawer, setDrawer] = useState(null);
  const [chatRequest, setChatRequest] = useState(null);
  const [toast, setToast] = useState('');
  const [homeState, setHomeState] = useState('');

  const signOut = useCallback(() => { writeToken(''); setToken(''); setSavedIds(new Set()); }, []);
  const api = useMemo(() => createApi(readToken, () => { signOut(); setToast('Your session has expired. Sign in again.'); }), [signOut]);

  useEffect(() => {
    const onHash = () => { setRoute(parseHash()); window.scrollTo(0, 0); };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    Promise.all([api('/meta', { auth: false }), api('/schemes', { auth: false })])
      .then(([m, s]) => { setMeta(m); setSchemes(s); })
      .catch((e) => setLoadError(e.message));
  }, [api]);

  useEffect(() => {
    if (!token) return;
    api('/saved').then((list) => setSavedIds(new Set(list.map((s) => s.id)))).catch(() => {});
    api('/profile').then((p) => {
      if (p.state) setHomeState(p.state);
      setDraft((d) => {
        if (Object.values(d).some((v) => v !== '' && v !== undefined)) return d;
        return Object.fromEntries(Object.entries(p).filter(([, v]) => v !== null && v !== '').map(([k, v]) => [k, v]));
      });
    }).catch(() => {});
  }, [token, api]);

  useEffect(() => {
    if (!toast) return undefined;
    const t = setTimeout(() => setToast(''), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const navigate = useCallback((to, { replace = false } = {}) => {
    const url = `#${to}`;
    if (replace) { window.history.replaceState(null, '', url); setRoute(parseHash()); } else window.location.hash = to;
  }, []);

  const openScheme = useCallback((s) => setDrawer(s), []);
  const openSchemeById = useCallback((id) => { const s = schemes.find((x) => x.id === id); if (s) setDrawer(s); }, [schemes]);
  const askSahayak = useCallback((text) => { setDrawer(null); setChatRequest({ text, nonce: Date.now() }); }, []);

  async function toggleSave(s) {
    if (!token) { setToast('Sign in to save schemes.'); return; }
    const saved = savedIds.has(s.id);
    try {
      if (saved) await api(`/saved/${s.id}`, { method: 'DELETE' });
      else await api('/saved', { method: 'POST', body: { scheme_id: s.id } });
      setSavedIds((prev) => { const next = new Set(prev); if (saved) next.delete(s.id); else next.add(s.id); return next; });
      setToast(saved ? 'Removed from saved schemes.' : 'Saved. Find it under Saved.');
    } catch (e) { setToast(e.message); }
  }

  function onSignedIn(newToken, isNew) {
    writeToken(newToken); setToken(newToken);
    setToast(isNew ? 'Account created. Add your details to get personal matches.' : 'Signed in.');
    navigate(isNew ? '/profile' : '/dashboard');
  }

  const draftHasAnswers = Object.values(draft).some((v) => v !== '' && v !== undefined && v !== null);
  const signedIn = Boolean(token);
  const { path, params } = route;
  const needsAuth = ['/dashboard', '/saved', '/profile'].includes(path);
  const nav = [['/schemes', 'Schemes'], ['/check', 'Check eligibility'],
    ...(signedIn ? [['/dashboard', 'Dashboard'], ['/saved', 'Saved'], ['/profile', 'Profile']] : [])];

  let page;
  if (loadError) {
    page = <section className="page"><h1>Could not load JanSetu</h1><p className="form-error">{loadError}</p></section>;
  } else if (!meta) {
    page = <section className="page"><p className="muted">Loading schemes…</p></section>;
  } else if (needsAuth && !signedIn) {
    page = <Auth api={api} onSignedIn={onSignedIn} />;
  } else if (path === '/schemes') {
    page = <Schemes schemes={schemes} meta={meta} params={params} navigate={navigate} openScheme={openScheme}
      savedIds={savedIds} onToggleSave={toggleSave} canSave={signedIn} homeState={homeState || draft.state} />;
  } else if (path === '/check') {
    page = <Checker api={api} meta={meta} draft={draft} setDraft={setDraft} openScheme={openScheme} signedIn={signedIn}
      askSahayak={askSahayak} notify={setToast} savedIds={savedIds} onToggleSave={toggleSave} />;
  } else if (path === '/profile') {
    page = <Profile api={api} meta={meta} notify={setToast} onSaved={(p) => p.state && setHomeState(p.state)} />;
  } else if (path === '/dashboard') {
    page = <Dashboard api={api} navigate={navigate} openSchemeById={openSchemeById} savedCount={savedIds.size} />;
  } else if (path === '/saved') {
    const saved = schemes.filter((s) => savedIds.has(s.id));
    page = (
      <section className="page">
        <header className="page-head"><h1>Saved schemes</h1><p>Schemes you bookmarked. Open one to tick off the documents you already have.</p></header>
        <SchemeList schemes={saved} onOpen={openScheme} savedIds={savedIds} onToggleSave={toggleSave} canSave
          emptyText="You have not saved any schemes yet. Open a scheme and choose Save to keep it here." />
      </section>
    );
  } else if (path === '/signin') {
    page = signedIn ? <section className="page"><p>You are signed in.</p></section> : <Auth api={api} onSignedIn={onSignedIn} />;
  } else {
    page = <Home api={api} meta={meta} draft={draft} setDraft={setDraft} navigate={navigate} openScheme={openScheme} askSahayak={askSahayak} />;
  }

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <a className="brand" href="#/" aria-label="JanSetu home">
          <Logo />
          <span className="brand-name">JanSetu<span className="brand-hi" lang="hi">जनसेतु</span></span>
        </a>
        <nav aria-label="Main">
          {nav.map(([to, label]) => (
            <a key={to} href={`#${to}`} className={path === to ? 'active' : ''} aria-current={path === to ? 'page' : undefined}>{label}</a>
          ))}
          {signedIn
            ? <button className="nav-btn" onClick={() => { signOut(); navigate('/'); setToast('Signed out.'); }}><LogOut size={16} aria-hidden="true" /> Sign out</button>
            : <a href="#/signin" className={`nav-cta${path === '/signin' ? ' active' : ''}`}>Sign in</a>}
        </nav>
      </header>

      <main id="main">{page}</main>

      <footer className="site-foot">
        <p><b>JanSetu</b> is an academic project, not an official government service. Results are a preliminary guide; confirm every detail on the official website before applying.</p>
      </footer>

      <SchemeDrawer scheme={drawer} onClose={() => setDrawer(null)} saved={drawer ? savedIds.has(drawer.id) : false}
        canSave={signedIn} onToggleSave={toggleSave} onAsk={askSahayak} />

      {meta && (
        <ChatWidget api={api} assistantMode={meta.assistant?.mode} profile={draftHasAnswers ? draft : null}
          signedIn={signedIn} request={chatRequest} onOpenScheme={openSchemeById} />
      )}

      <div className="toast" role="status" aria-live="polite">{toast && <p>{toast}</p>}</div>
    </>
  );
}
