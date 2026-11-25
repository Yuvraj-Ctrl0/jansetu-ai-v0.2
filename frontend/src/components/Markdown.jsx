import React from 'react';

/** Minimal, safe markdown renderer for chatbot replies (no HTML injection). */
const INLINE = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|\[[^\]]+\]\(https?:\/\/[^\s)]+\)|https?:\/\/[^\s)<>"]+)/g;

function inline(text, keyBase) {
  const parts = text.split(INLINE).filter((p) => p !== '');
  return parts.map((part, i) => {
    const key = `${keyBase}-${i}`;
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={key}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return <em key={key}>{part.slice(1, -1)}</em>;
    const link = part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (link) return <a key={key} href={link[2]} target="_blank" rel="noopener noreferrer">{link[1]}</a>;
    if (/^https?:\/\//.test(part)) {
      const clean = part.replace(/[.,;:!?]+$/, '');
      const trail = part.slice(clean.length);
      return <React.Fragment key={key}><a href={clean} target="_blank" rel="noopener noreferrer">{clean.replace(/^https?:\/\//, '').replace(/\/$/, '')}</a>{trail}</React.Fragment>;
    }
    return <React.Fragment key={key}>{part}</React.Fragment>;
  });
}

export default function Markdown({ text }) {
  const blocks = [];
  let list = null;
  const lines = String(text || '').replace(/\r/g, '').split('\n');
  const flush = () => { if (list) { blocks.push(list); list = null; } };
  lines.forEach((raw) => {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (bullet || numbered) {
      const type = bullet ? 'ul' : 'ol';
      if (!list || list.type !== type) { flush(); list = { type, items: [] }; }
      list.items.push((bullet || numbered)[1]);
      return;
    }
    flush();
    if (!line.trim()) { blocks.push({ type: 'gap' }); return; }
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    blocks.push({ type: heading ? 'h' : 'p', text: heading ? heading[1] : line });
  });
  flush();
  return (
    <div className="md">
      {blocks.map((b, i) => {
        if (b.type === 'gap') return null;
        if (b.type === 'ul' || b.type === 'ol') {
          const Tag = b.type;
          return <Tag key={i}>{b.items.map((it, j) => <li key={j}>{inline(it, `${i}-${j}`)}</li>)}</Tag>;
        }
        if (b.type === 'h') return <p key={i} className="md-h">{inline(b.text, i)}</p>;
        return <p key={i}>{inline(b.text, i)}</p>;
      })}
    </div>
  );
}
