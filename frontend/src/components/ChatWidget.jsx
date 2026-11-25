import React, { useEffect, useRef, useState } from 'react';
import { MessageCircle, X, Send, Mic, MicOff, ShieldCheck } from 'lucide-react';
import Markdown from './Markdown';

const SpeechRecognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);

const WELCOME = {
  role: 'assistant',
  content: "Namaste! I'm **Sahayak**. Ask me about any government scheme: who can apply, what you get, which documents you need and how to apply. You can type in Hindi or English.",
};

function modeLabel(mode) {
  if (mode === 'gemini' || mode === 'openai') return { text: 'AI answers', title: 'Answers are written by an AI model using only JanSetu\'s verified scheme records.' };
  return { text: 'Database answers', title: 'No AI key is configured, so answers are assembled directly from JanSetu\'s verified scheme records.' };
}

export default function ChatWidget({ api, assistantMode, profile, signedIn, request, onOpenScheme }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([WELCOME]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [lang, setLang] = useState('en-IN');
  const listRef = useRef(null);
  const inputRef = useRef(null);
  const recRef = useRef(null);
  const lastRequest = useRef(null);

  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' }); }, [messages, busy, open]);
  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  // External "Ask Sahayak about…" requests from scheme details or results
  useEffect(() => {
    if (request && request.nonce !== lastRequest.current) {
      lastRequest.current = request.nonce;
      setOpen(true);
      send(request.text);
    }
  }, [request]); // eslint-disable-line react-hooks/exhaustive-deps

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    setInput('');
    const history = messages.filter((m) => m !== WELCOME).slice(-8).map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: 'user', content: message }]);
    setBusy(true);
    try {
      const body = { message, history };
      if (profile && Object.values(profile).some((v) => v !== '' && v !== null && v !== undefined)) body.profile = profile;
      const res = await api('/chat', { method: 'POST', body, auth: true });
      setMessages((m) => [...m, { role: 'assistant', content: res.reply, sources: res.sources, notice: res.notice, redacted: res.redacted }]);
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: e.message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  function toggleMic() {
    if (!SpeechRecognition) return;
    if (listening) { recRef.current?.stop(); return; }
    const rec = new SpeechRecognition();
    rec.lang = lang;
    rec.interimResults = true;
    rec.onresult = (e) => setInput(Array.from(e.results).map((r) => r[0].transcript).join(' '));
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  }

  const suggestions = [
    'Which schemes help farmers?',
    'What documents do I need for an Ayushman card?',
    'मुझे घर बनाने के लिए कौन सी योजना है?',
    (signedIn || profile) ? 'Which schemes am I eligible for?' : 'Scholarships for college students',
  ];
  const mode = modeLabel(assistantMode);

  return (
    <>
      {!open && (
        <button className="chat-fab" onClick={() => setOpen(true)} aria-label="Open Sahayak chat assistant">
          <MessageCircle size={22} aria-hidden="true" /><span>Ask Sahayak</span>
        </button>
      )}
      {open && (
        <section className="chat-panel" role="dialog" aria-label="Sahayak chat assistant">
          <header className="chat-head">
            <div>
              <h2>Sahayak</h2>
              <p title={mode.title}><span className={`dot ${assistantMode === 'offline' ? 'dot-db' : 'dot-ai'}`} />{mode.text}</p>
            </div>
            <button className="icon-btn on-dark" onClick={() => setOpen(false)} aria-label="Close chat"><X size={20} /></button>
          </header>

          <div className="chat-log" ref={listRef} aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={`msg msg-${m.role}${m.error ? ' msg-error' : ''}`}>
                {m.role === 'assistant' ? <Markdown text={m.content} /> : <p>{m.content}</p>}
                {m.redacted && <p className="msg-note"><ShieldCheck size={14} /> We hid a number that looked like an Aadhaar or account number. Never share these in chat.</p>}
                {m.notice && <p className="msg-note">{m.notice}</p>}
                {m.sources?.length > 0 && (
                  <div className="sources">
                    {m.sources.map((s) => (
                      <button key={s.id} onClick={() => onOpenScheme(s.id)} title="Open scheme details">{s.name}</button>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {busy && <div className="msg msg-assistant typing" aria-label="Sahayak is typing"><span /><span /><span /></div>}
            {messages.length === 1 && !busy && (
              <div className="suggestions">
                {suggestions.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}
              </div>
            )}
          </div>

          <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
            {SpeechRecognition && (
              <div className="voice">
                <button type="button" className={`icon-btn${listening ? ' live' : ''}`} onClick={toggleMic}
                  aria-label={listening ? 'Stop voice input' : 'Speak your question'} aria-pressed={listening}>
                  {listening ? <MicOff size={18} /> : <Mic size={18} />}
                </button>
                <button type="button" className="lang" onClick={() => setLang(lang === 'en-IN' ? 'hi-IN' : 'en-IN')}
                  aria-label={`Voice language: ${lang === 'en-IN' ? 'English' : 'Hindi'}. Click to switch.`}>
                  {lang === 'en-IN' ? 'EN' : 'हि'}
                </button>
              </div>
            )}
            <label htmlFor="chat-text" className="sr-only">Your question</label>
            <input id="chat-text" ref={inputRef} value={input} maxLength={1000} onChange={(e) => setInput(e.target.value)}
              placeholder={listening ? 'Listening…' : 'Type your question'} autoComplete="off" />
            <button className="send" disabled={busy || !input.trim()} aria-label="Send"><Send size={18} /></button>
          </form>
          <p className="chat-foot">Never share your Aadhaar number, bank details or OTP. Applying on official portals is free.</p>
        </section>
      )}
    </>
  );
}
