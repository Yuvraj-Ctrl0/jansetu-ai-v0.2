"""Import / update government schemes from schemes.json (idempotent upsert).

* New records are inserted; existing ones (matched by name or `previous_names`) are updated.
* `rule_version` is bumped whenever a scheme's eligibility rules change (audit trail).
* A scheme is only made visible (`active=True`) when `publish=True` AND the record carries a
  `source_verified_at` date — unverified records stay as drafts.
"""
import json
from datetime import date
from pathlib import Path

from .engine import validate_rules
from .extensions import db
from .models import Scheme

DATA_FILE = Path(__file__).resolve().parent.parent / 'schemes.json'
REQUIRED = ('name', 'description', 'category', 'official_url')
LIST_FIELDS = ('documents', 'additional_conditions', 'tags', 'previous_names')


def load_records(path=DATA_FILE):
    records = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(records, list):
        raise ValueError('schemes.json must contain a JSON array')
    seen = set()
    for item in records:
        validate_record(item)
        key = item['name'].strip().lower()
        if key in seen:
            raise ValueError(f'Duplicate scheme name: {item["name"]}')
        seen.add(key)
    return records


def validate_record(item):
    if not isinstance(item, dict):
        raise ValueError('Each scheme must be an object')
    name = str(item.get('name', '')).strip() or '<unnamed>'
    for field in REQUIRED:
        if not str(item.get(field, '')).strip():
            raise ValueError(f'{name}: missing required field "{field}"')
    if not item['official_url'].startswith('https://'):
        raise ValueError(f'{name}: official HTTPS URL required')
    validate_rules(item.get('rules', {}), f'{name}.rules')
    for field in LIST_FIELDS:
        value = item.get(field, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError(f'{name}: "{field}" must be a list of strings')
    if item.get('level', 'Central') not in {'Central', 'State'}:
        raise ValueError(f'{name}: level must be "Central" or "State"')
    if item.get('level') == 'State' and not item.get('rules', {}).get('states'):
        raise ValueError(f'{name}: state schemes must declare rules.states')
    if item.get('source_verified_at'):
        date.fromisoformat(item['source_verified_at'])


def _find_existing(item):
    names = [item['name']] + list(item.get('previous_names', []))
    for candidate in names:
        scheme = Scheme.query.filter_by(name=candidate.strip()).first()
        if scheme:
            return scheme
    return None


def seed(publish=False, dry_run=False, path=DATA_FILE, verbose=True):
    records = load_records(path)
    stats = {'added': 0, 'updated': 0, 'unchanged': 0, 'published': 0}
    log = print if verbose else (lambda *a, **k: None)
    for item in records:
        verified = date.fromisoformat(item['source_verified_at']) if item.get('source_verified_at') else None
        values = {
            'name': item['name'].strip(),
            'description': item['description'].strip(),
            'category': item['category'].strip(),
            'official_url': item['official_url'].strip(),
            'rules': item.get('rules', {}),
            'level': item.get('level', 'Central'),
            'ministry': item.get('ministry'),
            'benefits': item.get('benefits'),
            'how_to_apply': item.get('how_to_apply'),
            'documents': item.get('documents', []),
            'additional_conditions': item.get('additional_conditions', []),
            'tags': item.get('tags', []),
            'source_verified_at': verified,
        }
        scheme = _find_existing(item)
        if scheme is None:
            scheme = Scheme(active=False, rule_version=1, **values)
            scheme.touch()
            db.session.add(scheme)
            stats['added'] += 1
            log(f'Added: {values["name"]}')
        else:
            changed = [k for k, v in values.items() if getattr(scheme, k) != v]
            if 'rules' in changed:
                scheme.rule_version = (scheme.rule_version or 1) + 1
            for key in changed:
                setattr(scheme, key, values[key])
            if changed:
                scheme.touch()
                stats['updated'] += 1
                log(f'Updated: {values["name"]} ({", ".join(changed)})')
            else:
                stats['unchanged'] += 1
        if publish and verified and not scheme.active:
            scheme.active = True
            stats['published'] += 1
            log(f'Published: {values["name"]}')
    if dry_run:
        db.session.rollback()
        log('Dry run: no changes saved.')
    else:
        db.session.commit()
    return stats
