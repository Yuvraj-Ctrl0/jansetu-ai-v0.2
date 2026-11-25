from datetime import datetime, timezone

from .extensions import db
from .engine import describe_rules

PROFILE_FIELDS = (
    'age', 'state', 'occupation', 'annual_income', 'interests', 'full_name', 'district', 'gender',
    'education_level', 'employment_status', 'household_size', 'social_category', 'disability_status',
    # v0.2 eligibility fields
    'area', 'marital_status', 'student_level', 'income_tax_payer', 'organised_sector_member',
    'govt_employee_in_family', 'has_bank_account', 'bpl_card', 'owns_agri_land', 'land_hectares',
    'owns_pucca_house', 'has_lpg_connection',
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    profile = db.relationship('CitizenProfile', uselist=False, back_populates='user', cascade='all, delete-orphan')


class CitizenProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    age = db.Column(db.Integer)
    state = db.Column(db.String(100))
    occupation = db.Column(db.String(100))
    annual_income = db.Column(db.Float)
    interests = db.Column(db.Text, default='')
    full_name = db.Column(db.String(120))
    district = db.Column(db.String(120))
    gender = db.Column(db.String(40))
    education_level = db.Column(db.String(80))
    employment_status = db.Column(db.String(80))
    household_size = db.Column(db.Integer)
    social_category = db.Column(db.String(60))
    disability_status = db.Column(db.Boolean)
    # v0.2 — added by app/schema_sync.py on existing databases (additive, nullable)
    area = db.Column(db.String(20))
    marital_status = db.Column(db.String(30))
    student_level = db.Column(db.String(40))
    income_tax_payer = db.Column(db.Boolean)
    organised_sector_member = db.Column(db.Boolean)
    govt_employee_in_family = db.Column(db.Boolean)
    has_bank_account = db.Column(db.Boolean)
    bpl_card = db.Column(db.Boolean)
    owns_agri_land = db.Column(db.Boolean)
    land_hectares = db.Column(db.Float)
    owns_pucca_house = db.Column(db.Boolean)
    has_lpg_connection = db.Column(db.Boolean)
    user = db.relationship('User', back_populates='profile')

    def as_dict(self):
        return {k: getattr(self, k) for k in PROFILE_FIELDS}


class Scheme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    official_url = db.Column(db.String(1000), nullable=False)
    source_verified_at = db.Column(db.Date, nullable=True)
    rules = db.Column(db.JSON, nullable=False, default=dict)
    rule_version = db.Column(db.Integer, nullable=False, default=1)
    active = db.Column(db.Boolean, nullable=False, default=False)
    # v0.2 — richer, citizen-facing content
    level = db.Column(db.String(20))            # "Central" or "State"
    ministry = db.Column(db.String(255))
    benefits = db.Column(db.Text)
    how_to_apply = db.Column(db.Text)
    documents = db.Column(db.JSON)              # list[str]
    additional_conditions = db.Column(db.JSON)  # list[str] — conditions the rule engine cannot check
    tags = db.Column(db.JSON)                   # list[str] — search keywords incl. Hindi terms
    updated_at = db.Column(db.DateTime)

    def as_dict(self):
        rules = self.rules or {}
        return {
            "id": self.id, "name": self.name, "description": self.description, "category": self.category,
            "official_url": self.official_url,
            "source_verified_at": self.source_verified_at.isoformat() if self.source_verified_at else None,
            "rule_version": self.rule_version, "rules": rules, "active": self.active,
            "level": self.level or "Central", "ministry": self.ministry, "benefits": self.benefits,
            "how_to_apply": self.how_to_apply, "documents": self.documents or [],
            "additional_conditions": self.additional_conditions or [], "tags": self.tags or [],
            "states": rules.get("states") or [],
            "eligibility_criteria": describe_rules(rules),
        }

    def touch(self):
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)


class SavedScheme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scheme_id = db.Column(db.Integer, db.ForeignKey('scheme.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'scheme_id'),)
