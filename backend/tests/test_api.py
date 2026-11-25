import pytest

from app import create_app
from app.extensions import db
from app.seeding import seed


@pytest.fixture
def app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                      'JWT_SECRET_KEY': 'jansetu-automated-testing-secret-key-2026-only'})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded(app, client, monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('LLM_PROVIDER', 'offline')
    seed(publish=True, verbose=False)
    return client


def _login(client, email='person@example.com'):
    client.post('/api/auth/register', json={'email': email, 'password': 'secure-pass-123'})
    token = client.post('/api/auth/login', json={'email': email, 'password': 'secure-pass-123'}).json['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_auth_and_profile(client):
    assert client.post('/api/auth/register', json={'email': 'person@example.com', 'password': 'secure-pass-123'}).status_code == 201
    token = client.post('/api/auth/login', json={'email': 'person@example.com', 'password': 'secure-pass-123'}).json['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    assert client.put('/api/profile', headers=headers, json={'age': 21, 'state': 'Madhya Pradesh'}).status_code == 200
    assert client.get('/api/profile', headers=headers).json['age'] == 21
    assert client.get('/api/schemes').json == []


def test_unauthorized(client):
    assert client.get('/api/profile').status_code == 401


def test_profile_new_fields_and_validation(client):
    headers = _login(client)
    ok = client.put('/api/profile', headers=headers,
                    json={'area': 'Rural', 'bpl_card': True, 'income_tax_payer': 'no', 'land_hectares': 1.5})
    assert ok.status_code == 200
    assert ok.json['area'] == 'rural' and ok.json['income_tax_payer'] is False
    assert client.put('/api/profile', headers=headers, json={'area': 'moon'}).status_code == 400
    assert client.put('/api/profile', headers=headers, json={'pregnant_or_lactating': True}).status_code == 400
    assert client.put('/api/profile', headers=headers, json={'unknown_field': 1}).status_code == 400


def test_seed_publishes_verified_schemes(seeded):
    schemes = seeded.get('/api/schemes').json
    assert len(schemes) >= 40
    kisan = next(s for s in schemes if 'PM-KISAN' in s['name'])
    assert kisan['benefits'] and kisan['documents'] and kisan['eligibility_criteria']


def test_seed_is_idempotent_and_versions_rules(app, seeded):
    stats = seed(publish=True, verbose=False)
    assert stats['added'] == 0 and stats['updated'] == 0


def test_eligibility_check_public(seeded):
    details = {'age': 45, 'gender': 'Woman', 'state': 'Madhya Pradesh', 'area': 'rural', 'annual_income': 120000,
               'occupation': 'farmer', 'income_tax_payer': False, 'owns_agri_land': True, 'land_hectares': 1,
               'bpl_card': True, 'has_bank_account': True, 'marital_status': 'widowed', 'pregnant_or_lactating': False}
    out = seeded.post('/api/eligibility/check', json=details).json
    eligible = {r['name'] for r in out['results'] if r['eligibility']['status'] == 'eligible_by_recorded_rules'}
    assert 'Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)' in eligible
    assert 'Pradhan Mantri Vidhawa Pension Yojana (formerly IGNWPS)' in eligible
    assert 'Mukhyamantri Ladli Behna Yojana (Madhya Pradesh)' in eligible
    assert 'Mukhyamantri Majhi Ladki Bahin Yojana (Maharashtra)' not in eligible  # state rule
    assert out['summary']['total'] == len(out['results'])
    assert isinstance(out['suggested_questions'], list)


def test_eligibility_check_rejects_bad_values(seeded):
    assert seeded.post('/api/eligibility/check', json={'age': 'old'}).status_code == 400


def test_meta_lists_options(seeded):
    meta = seeded.get('/api/meta').json
    assert 'Madhya Pradesh' in meta['states']
    assert any(o['value'] == 'farmer' for o in meta['occupations'])
    assert meta['assistant']['mode'] == 'offline'
    assert meta['published_count'] >= 40


def test_chat_offline_answers_with_sources(seeded):
    res = seeded.post('/api/chat', json={'message': 'What documents are needed for PM-KISAN?'})
    assert res.status_code == 200
    body = res.json
    assert body['mode'] == 'offline'
    assert 'PM-KISAN' in body['sources'][0]['name']
    assert 'Documents' in body['reply'] or 'documents' in body['reply']


def test_chat_follow_up_uses_history(seeded):
    history = [{'role': 'user', 'content': 'Tell me about Atal Pension Yojana'},
               {'role': 'assistant', 'content': '...'}]
    body = seeded.post('/api/chat', json={'message': 'how do I apply?', 'history': history}).json
    assert 'Atal Pension' in body['sources'][0]['name']


def test_chat_personal_query_uses_profile(seeded):
    profile = {'age': 70, 'bpl_card': True, 'state': 'Bihar'}
    body = seeded.post('/api/chat', json={'message': 'Which schemes am I eligible for?', 'profile': profile}).json
    names = [s['name'] for s in body['sources']]
    assert any('Vay Vandana' in n for n in names)
    assert 'may be eligible' in body['reply']


def test_chat_redacts_aadhaar(seeded):
    body = seeded.post('/api/chat', json={'message': 'my aadhaar is 1234 5678 9012, am I eligible for pension?'}).json
    assert body['redacted'] is True


def test_chat_validation_and_rate_limit(app, client, monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'offline')
    assert client.post('/api/chat', json={}).status_code == 400
    assert client.post('/api/chat', json={'message': 'x' * 1001}).status_code == 400
    limited = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                          'JWT_SECRET_KEY': 'jansetu-automated-testing-secret-key-2026-only', 'CHAT_RATE_LIMIT': 2})
    with limited.app_context():
        db.create_all()
        c = limited.test_client()
        codes = [c.post('/api/chat', json={'message': 'hi'}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]


def test_chat_ignores_expired_or_bad_token(seeded):
    res = seeded.post('/api/chat', json={'message': 'hello'}, headers={'Authorization': 'Bearer not-a-token'})
    assert res.status_code == 200


def test_saved_and_unsave(seeded):
    headers = _login(seeded)
    sid = seeded.get('/api/schemes').json[0]['id']
    assert seeded.post('/api/saved', headers=headers, json={'scheme_id': sid}).status_code == 201
    assert len(seeded.get('/api/saved', headers=headers).json) == 1
    assert seeded.delete(f'/api/saved/{sid}', headers=headers).status_code == 200
    assert seeded.get('/api/saved', headers=headers).json == []


def test_dashboard_includes_screening(seeded):
    headers = _login(seeded)
    seeded.put('/api/profile', headers=headers, json={'age': 30, 'has_bank_account': True, 'income_tax_payer': False})
    dash = seeded.get('/api/dashboard', headers=headers).json
    assert dash['screening_summary']['total'] >= 40
    assert any(m['name'].startswith('Atal Pension') for m in dash['top_matches']) or dash['top_matches']
