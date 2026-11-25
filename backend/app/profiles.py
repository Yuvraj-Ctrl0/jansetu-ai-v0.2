"""Validation for citizen profile data (saved profile and one-off eligibility checks)."""
import math

from .engine import AREAS, MARITAL_STATUSES, STUDENT_LEVELS

# field -> (type, constraint)
FIELD_SPECS = {
    'age': ('int', (0, 120)),
    'household_size': ('int', (1, 50)),
    'annual_income': ('float', (0, 1_000_000_000)),
    'land_hectares': ('float', (0, 10_000)),
    'disability_status': ('bool', None),
    'income_tax_payer': ('bool', None),
    'organised_sector_member': ('bool', None),
    'govt_employee_in_family': ('bool', None),
    'has_bank_account': ('bool', None),
    'bpl_card': ('bool', None),
    'owns_agri_land': ('bool', None),
    'owns_pucca_house': ('bool', None),
    'has_lpg_connection': ('bool', None),
    'area': ('choice', set(AREAS)),
    'marital_status': ('choice', set(MARITAL_STATUSES)),
    'student_level': ('choice', set(STUDENT_LEVELS)),
    'interests': ('str', 500),
    'full_name': ('str', 120),
    'district': ('str', 120),
    'state': ('str', 100),
    'occupation': ('str', 100),
    'gender': ('str', 40),
    'education_level': ('str', 80),
    'employment_status': ('str', 80),
    'social_category': ('str', 60),
}

# Used only for a one-off eligibility check; never persisted (sensitive / short-lived facts).
TRANSIENT_SPECS = {
    'pregnant_or_lactating': ('bool', None),
    'daughter_below_10': ('bool', None),
}

PERSISTED_FIELDS = set(FIELD_SPECS)


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {'yes', 'true'}:
        return True
    if isinstance(value, str) and value.strip().lower() in {'no', 'false'}:
        return False
    raise ValueError()


def clean_profile(body, allow_transient=False, ignore_unknown=False):
    """Return (clean_dict, error_message). Blank strings become None (= unknown)."""
    if not isinstance(body, dict):
        return None, 'Profile must be a JSON object'
    specs = dict(FIELD_SPECS)
    if allow_transient:
        specs.update(TRANSIENT_SPECS)
    unknown = [k for k in body if k not in specs]
    if unknown and not ignore_unknown:
        return None, 'Unknown profile field'
    clean = {}
    try:
        for key, value in body.items():
            if key not in specs:
                continue
            kind, constraint = specs[key]
            if value == '' or value is None:
                clean[key] = None
                continue
            if kind == 'int':
                if isinstance(value, bool):
                    raise ValueError()
                value = int(value)
                low, high = constraint
                if not low <= value <= high:
                    raise ValueError()
            elif kind == 'float':
                if isinstance(value, bool):
                    raise ValueError()
                value = float(value)
                low, high = constraint
                if not math.isfinite(value) or not low <= value <= high:
                    raise ValueError()
            elif kind == 'bool':
                value = _coerce_bool(value)
            elif kind == 'choice':
                value = str(value).strip().lower()
                if value not in constraint:
                    raise ValueError()
            else:
                if not isinstance(value, str) or len(value) > constraint:
                    raise ValueError()
                value = value.strip() or None
            clean[key] = value
    except (ValueError, TypeError, OverflowError):
        return None, 'Invalid profile values'
    return clean, None
