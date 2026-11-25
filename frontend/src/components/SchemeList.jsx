import React from 'react';
import { Bookmark, BookmarkCheck, ChevronRight } from 'lucide-react';
import { STATUS, schemeScope } from '../lib/format';

export function StatusBadge({ status }) {
  const s = STATUS[status];
  if (!s) return null;
  return <span className={`badge badge-${s.tone}`}>{s.label}</span>;
}

/** Register-style list of schemes. Each row opens the detail drawer. */
export default function SchemeList({ schemes, onOpen, savedIds, onToggleSave, canSave, showStatus = false, emptyText }) {
  if (!schemes.length) return <p className="empty-line">{emptyText || 'No schemes to show.'}</p>;
  return (
    <ul className="register">
      {schemes.map((s) => {
        const saved = savedIds?.has(s.id);
        return (
          <li key={s.id} className="register-row">
            <button className="row-main" onClick={() => onOpen(s)} aria-label={`Open details for ${s.name}`}>
              <span className={`cat-dot cat-${slug(s.category)}`} aria-hidden="true" />
              <span className="row-text">
                <span className="row-meta">{s.category}<span className="row-scope">{schemeScope(s)}</span></span>
                <span className="row-name">{s.name}</span>
                <span className="row-benefit">{s.benefits || s.description}</span>
              </span>
              <span className="row-side">
                {showStatus && s.eligibility && <StatusBadge status={s.eligibility.status} />}
                <ChevronRight size={18} aria-hidden="true" />
              </span>
            </button>
            {canSave && (
              <button className={`icon-btn save-btn${saved ? ' is-saved' : ''}`} onClick={() => onToggleSave(s)}
                aria-pressed={saved} aria-label={saved ? `Remove ${s.name} from saved` : `Save ${s.name}`}
                title={saved ? 'Saved' : 'Save'}>
                {saved ? <BookmarkCheck size={18} /> : <Bookmark size={18} />}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export const slug = (text = '') => text.toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
