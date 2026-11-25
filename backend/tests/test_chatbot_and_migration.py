import sqlite3
import urllib.error

import pytest

from app import chatbot, create_app
from app.extensions import db
from app.schema_sync import sync_schema
from app.seeding import seed

SECRET = 'jansetu-automated-testing-secret-key-2026-only'


@pytest.fixture
def seeded_app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', 'JWT_SECRET_KEY': SECRET})
    with app.app_context():
        db.create_all()
        seed(publish=True, verbose=False)
        yield app


def test_gemini_path_is_grounded(seeded_app, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    captured = {}

    def fake_post(url, payload, headers, timeout=25):
        captured.update(url=url, payload=payload, headers=headers)
        return {'candidates': [{'content': {'parts': [{'text': 'PM-KISAN gives ₹6,000 a year.'}]}}]}

    monkeypatch.setattr(chatbot, '_post_json', fake_post)
    body = seeded_app.test_client().post('/api/chat', json={'message': 'Tell me about PM-KISAN'}).json
    assert body['mode'] == 'gemini'
    assert body['reply'] == 'PM-KISAN gives ₹6,000 a year.'
    assert 'gemini-flash-latest' in captured['url']
    assert captured['headers']['x-goog-api-key'] == 'test-key'
    system = captured['payload']['systemInstruction']['parts'][0]['text']
    assert 'SCHEME CONTEXT' in system and 'pmkisan.gov.in' in system
    assert captured['payload']['contents'][-1]['role'] == 'user'


def test_openai_compatible_path(seeded_app, monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setenv('LLM_PROVIDER', 'openai')
    monkeypatch.setenv('OPENAI_API_KEY', 'k')
    monkeypatch.setenv('OPENAI_MODEL', 'some-model')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://example.test/v1')
    seen = {}

    def fake_post(url, payload, headers, timeout=25):
        seen.update(url=url, payload=payload)
        return {'choices': [{'message': {'content': 'Hello from the model'}}]}

    monkeypatch.setattr(chatbot, '_post_json', fake_post)
    body = seeded_app.test_client().post('/api/chat', json={'message': 'pension for widow'}).json
    assert body['mode'] == 'openai' and body['reply'] == 'Hello from the model'
    assert seen['url'] == 'https://example.test/v1/chat/completions'
    assert seen['payload']['messages'][0]['role'] == 'system'


def test_llm_failure_falls_back_to_offline(seeded_app, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'bad')

    def boom(*args, **kwargs):
        raise urllib.error.URLError('network down')

    monkeypatch.setattr(chatbot, '_post_json', boom)
    body = seeded_app.test_client().post('/api/chat', json={'message': 'free ration'}).json
    assert body['mode'] == 'offline'
    assert body['notice']
    assert 'Garib Kalyan' in body['reply']


def test_hindi_query_expansion():
    assert 'house' in chatbot.expand_query('मुझे घर चाहिए')
    assert 'farmer' in chatbot.expand_query('kisan ke liye yojana')


def test_history_is_sanitised():
    history = [{'role': 'assistant', 'content': 'hi'}, {'role': 'user', 'content': 'a'},
               {'role': 'user', 'content': 'my aadhaar 1234 5678 9012'}, {'role': 'bot', 'content': 'ok'}]
    clean = chatbot._clean_history(history)
    assert clean[0]['role'] == 'user'
    assert '[redacted]' in clean[0]['content']
    assert [m['role'] for m in clean] == ['user', 'assistant']


def test_schema_sync_adds_columns_to_old_database(tmp_path):
    path = tmp_path / 'old.db'
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE user (id INTEGER PRIMARY KEY, email VARCHAR(255) NOT NULL UNIQUE,
                           password_hash VARCHAR(255) NOT NULL, is_admin BOOLEAN NOT NULL);
        CREATE TABLE citizen_profile (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE, age INTEGER,
                           state VARCHAR(100), occupation VARCHAR(100), annual_income FLOAT, interests TEXT);
        CREATE TABLE scheme (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL, description TEXT NOT NULL,
                           category VARCHAR(100) NOT NULL, official_url VARCHAR(1000) NOT NULL,
                           source_verified_at DATE, rules JSON NOT NULL, rule_version INTEGER NOT NULL,
                           active BOOLEAN NOT NULL);
        INSERT INTO scheme (name, description, category, official_url, rules, rule_version, active)
        VALUES ('Indira Gandhi National Old Age Pension Scheme (IGNOAPS)', 'old', 'Social Security',
                'https://nsap.nic.in/', '{}', 1, 1);
    """)
    con.commit()
    con.close()
    app = create_app({'SQLALCHEMY_DATABASE_URI': f'sqlite:///{path}', 'JWT_SECRET_KEY': SECRET})
    with app.app_context():
        db.create_all()
        added = sync_schema(verbose=False)
        assert 'scheme.benefits' in added and 'citizen_profile.bpl_card' in added
        assert sync_schema(verbose=False) == []  # idempotent
        stats = seed(publish=True, verbose=False)
        assert stats['updated'] >= 1  # old IGNOAPS record renamed via previous_names, not duplicated
        from app.models import Scheme
        renamed = Scheme.query.filter(Scheme.name.like('Pradhan Mantri Vridhavastha%')).one()
        assert renamed.rule_version == 2 and renamed.rules == {'age_min': 60, 'bpl': True}
        assert Scheme.query.filter(Scheme.name.like('Indira Gandhi%')).count() == 0
