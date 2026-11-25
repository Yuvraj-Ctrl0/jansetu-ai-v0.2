import os
import time
from collections import defaultdict, deque

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, verify_jwt_in_request
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from . import chatbot
from .engine import (AREAS, EDUCATION_LEVELS, EMPLOYMENT_STATUSES, GENDERS, INDIAN_STATES, MARITAL_STATUSES,
                     OCCUPATIONS, SOCIAL_CATEGORIES, STUDENT_LEVELS, evaluate, rank_schemes, screen_all)
from .extensions import db, jwt
from .models import CitizenProfile, SavedScheme, Scheme, User
from .profiles import clean_profile


class RateLimiter:
    """Tiny in-memory sliding-window limiter (per process). Good enough for a prototype."""

    def __init__(self, limit, window_seconds):
        self.limit, self.window = limit, window_seconds
        self.hits = defaultdict(deque)

    def allow(self, key):
        now = time.monotonic()
        bucket = self.hits[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True


def _client_key():
    forwarded = request.headers.get('X-Forwarded-For', '')
    return (forwarded.split(',')[0].strip() or request.remote_addr or 'unknown')


def _optional_user():
    """Return the logged-in user if a valid token is present; never raises."""
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        return db.session.get(User, int(identity)) if identity else None
    except Exception:  # expired/invalid token on a public endpoint -> treat as anonymous
        return None


def _active_schemes():
    return [s.as_dict() for s in Scheme.query.filter_by(active=True).order_by(Scheme.name).all()]


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'mysql+pymysql://jansetu:jansetu@localhost:3306/jansetu')
        .replace('postgres://', 'postgresql://', 1),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY', ''),
        CHAT_RATE_LIMIT=int(os.getenv('CHAT_RATE_LIMIT', '30')),
    )
    app.json.sort_keys = False
    if test_config:
        app.config.update(test_config)
    if not app.config['JWT_SECRET_KEY']:
        raise RuntimeError('Set JWT_SECRET_KEY to a strong random secret')
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, origins=os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173').split(','), supports_credentials=False)
    chat_limiter = RateLimiter(app.config['CHAT_RATE_LIMIT'], 600)

    @app.get('/api/health')
    def health():
        return jsonify(status='ok', service='JanSetu AI', version='0.2.0')

    @app.get('/api/meta')
    def meta():
        schemes = Scheme.query.filter_by(active=True).all()
        categories = {}
        for s in schemes:
            categories[s.category] = categories.get(s.category, 0) + 1
        return jsonify(
            states=INDIAN_STATES,
            occupations=[{'value': k, 'label': v} for k, v in OCCUPATIONS.items()],
            genders=GENDERS,
            social_categories=SOCIAL_CATEGORIES,
            areas=[{'value': k, 'label': v} for k, v in AREAS.items()],
            marital_statuses=[{'value': k, 'label': v} for k, v in MARITAL_STATUSES.items()],
            student_levels=[{'value': k, 'label': v} for k, v in STUDENT_LEVELS.items()],
            education_levels=EDUCATION_LEVELS,
            employment_statuses=EMPLOYMENT_STATUSES,
            categories=sorted(({'name': k, 'count': v} for k, v in categories.items()), key=lambda c: c['name']),
            published_count=len(schemes),
            assistant=chatbot.provider_status(),
        )

    # ---------------------------------------------------------------- auth
    @app.post('/api/auth/register')
    def register():
        body = request.get_json(silent=True) or {}
        email = str(body.get('email', '')).strip().lower()
        password = body.get('password', '')
        if not email or '@' not in email or not isinstance(password, str) or len(password) < 10:
            return jsonify(error='Valid email and password of at least 10 characters required'), 400
        user = User(email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        try:
            db.session.flush()
            db.session.add(CitizenProfile(user_id=user.id))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify(error='Email already registered'), 409
        return jsonify(message='Account created'), 201

    @app.post('/api/auth/login')
    def login():
        body = request.get_json(silent=True) or {}
        user = User.query.filter_by(email=str(body.get('email', '')).strip().lower()).first()
        if not user or not check_password_hash(user.password_hash, body.get('password', '')):
            return jsonify(error='Invalid credentials'), 401
        return jsonify(access_token=create_access_token(identity=str(user.id)))

    # ---------------------------------------------------------------- profile
    @app.route('/api/profile', methods=['GET', 'PUT'])
    @jwt_required()
    def profile():
        u = db.session.get(User, int(get_jwt_identity()))
        if not u:
            return jsonify(error='User not found'), 404
        if request.method == 'GET':
            return jsonify(u.profile.as_dict())
        clean, error = clean_profile(request.get_json(silent=True) or {})
        if error:
            return jsonify(error=error), 400
        for key, value in clean.items():
            setattr(u.profile, key, value)
        db.session.commit()
        return jsonify(u.profile.as_dict())

    @app.get('/api/dashboard')
    @jwt_required()
    def dashboard():
        u = db.session.get(User, int(get_jwt_identity()))
        if not u or not u.profile:
            return jsonify(error='User not found'), 404
        profile_data = u.profile.as_dict()
        core = ('age', 'state', 'district', 'occupation', 'annual_income', 'gender', 'area', 'social_category',
                'education_level', 'income_tax_payer', 'bpl_card', 'has_bank_account')
        complete = sum(profile_data.get(k) is not None and profile_data.get(k) != '' for k in core)
        saved_count = db.session.query(SavedScheme).join(Scheme, SavedScheme.scheme_id == Scheme.id).filter(
            SavedScheme.user_id == u.id, Scheme.active.is_(True)).count()
        screening = screen_all(profile_data, _active_schemes())
        top = [{'id': s['id'], 'name': s['name'], 'category': s['category'], 'benefits': s.get('benefits')}
               for s in screening['results'] if s['eligibility']['status'] == 'eligible_by_recorded_rules'][:4]
        return jsonify(profile=profile_data, completion_percentage=round(complete / len(core) * 100),
                       missing_fields=[k for k in core if profile_data.get(k) is None or profile_data.get(k) == ''],
                       saved_count=saved_count, published_count=Scheme.query.filter_by(active=True).count(),
                       screening_summary=screening['summary'], top_matches=top,
                       suggested_questions=screening['suggested_questions'])

    # ---------------------------------------------------------------- schemes
    @app.get('/api/schemes')
    def schemes():
        return jsonify(_active_schemes())

    @app.get('/api/schemes/<int:scheme_id>')
    def scheme_detail(scheme_id):
        s = db.session.get(Scheme, scheme_id)
        if not s or not s.active:
            return jsonify(error='Not found'), 404
        return jsonify(s.as_dict())

    @app.post('/api/recommendations')
    @jwt_required()
    def recommendations():
        u = db.session.get(User, int(get_jwt_identity()))
        body = request.get_json(silent=True) or {}
        if not u:
            return jsonify(error='User not found'), 404
        q = str(body.get('query') or u.profile.interests or u.profile.occupation or '')[:500]
        items = rank_schemes(q, _active_schemes())
        profile_data = u.profile.as_dict()
        for item in items:
            item['eligibility'] = evaluate(profile_data, item['rules'])
        return jsonify(items)

    @app.post('/api/schemes/<int:scheme_id>/eligibility')
    @jwt_required()
    def eligibility(scheme_id):
        u = db.session.get(User, int(get_jwt_identity()))
        s = db.session.get(Scheme, scheme_id)
        if not u or not s or not s.active:
            return jsonify(error='Not found'), 404
        return jsonify(evaluate(u.profile.as_dict(), s.rules), official_url=s.official_url,
                       source_verified_at=s.source_verified_at.isoformat() if s.source_verified_at else None)

    @app.post('/api/eligibility/check')
    def eligibility_check():
        """Public: screen every published scheme against details entered in the form."""
        clean, error = clean_profile(request.get_json(silent=True) or {}, allow_transient=True)
        if error:
            return jsonify(error=error), 400
        return jsonify(screen_all(clean, _active_schemes()))

    # ---------------------------------------------------------------- chatbot
    @app.post('/api/chat')
    def chat():
        if not chat_limiter.allow(_client_key()):
            return jsonify(error='Too many messages. Please wait a few minutes and try again.'), 429
        body = request.get_json(silent=True) or {}
        message = body.get('message')
        if not isinstance(message, str) or not message.strip():
            return jsonify(error='Message is required'), 400
        if len(message) > chatbot.MAX_MESSAGE_CHARS:
            return jsonify(error=f'Message is too long (max {chatbot.MAX_MESSAGE_CHARS} characters)'), 400
        history = body.get('history') if isinstance(body.get('history'), list) else []
        profile_data = None
        if isinstance(body.get('profile'), dict):  # details from the eligibility form (not stored)
            profile_data, _ = clean_profile(body['profile'], allow_transient=True, ignore_unknown=True)
        user = _optional_user()
        if profile_data is None and user and user.profile:
            profile_data = user.profile.as_dict()
        if profile_data and not any(v not in (None, '') for v in profile_data.values()):
            profile_data = None
        return jsonify(chatbot.answer(message, history, _active_schemes(), profile_data))

    # ---------------------------------------------------------------- saved
    @app.route('/api/saved', methods=['GET', 'POST'])
    @jwt_required()
    def saved():
        uid = int(get_jwt_identity())
        if request.method == 'GET':
            ids = [x.scheme_id for x in SavedScheme.query.filter_by(user_id=uid).all()]
            return jsonify([s.as_dict() for s in Scheme.query.filter(Scheme.id.in_(ids), Scheme.active.is_(True)).all()])
        body = request.get_json(silent=True) or {}
        try:
            sid = int(body.get('scheme_id'))
        except (ValueError, TypeError):
            return jsonify(error='Valid scheme_id required'), 400
        if not db.session.get(Scheme, sid):
            return jsonify(error='Scheme not found'), 404
        if not SavedScheme.query.filter_by(user_id=uid, scheme_id=sid).first():
            db.session.add(SavedScheme(user_id=uid, scheme_id=sid))
            db.session.commit()
        return jsonify(message='Saved'), 201

    @app.delete('/api/saved/<int:scheme_id>')
    @jwt_required()
    def unsave(scheme_id):
        uid = int(get_jwt_identity())
        row = SavedScheme.query.filter_by(user_id=uid, scheme_id=scheme_id).first()
        if row:
            db.session.delete(row)
            db.session.commit()
        return jsonify(message='Removed')

    @app.errorhandler(404)
    def missing(_):
        return jsonify(error='Not found'), 404

    return app
