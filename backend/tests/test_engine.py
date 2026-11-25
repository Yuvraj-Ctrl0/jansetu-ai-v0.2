from app.engine import (describe_rule, evaluate, format_inr, normalize_occupation, rank_schemes, screen_all,
                        validate_rules)
import pytest


# --- original v0.1 behaviour (kept) -------------------------------------------------------
def test_eligible():
    assert evaluate({'age': 24, 'state': 'Madhya Pradesh'}, {'age_min': 18, 'states': ['Madhya Pradesh']})['status'] == 'eligible_by_recorded_rules'


def test_ineligible():
    assert evaluate({'age': 16}, {'age_min': 18})['status'] == 'ineligible'


def test_unknown():
    assert evaluate({}, {'income_max': 100000})['status'] == 'insufficient_information'


def test_unsupported_rule_fails_closed():
    assert evaluate({'age': 22}, {'residency_certificate': True})['status'] == 'insufficient_information'


def test_rank():
    schemes = [{'name': 'Student scholarship', 'description': 'Education support'},
               {'name': 'Agriculture aid', 'description': 'Farm support'}]
    assert rank_schemes('student education', schemes)[0]['name'] == 'Student scholarship'


# --- v0.2 rules ---------------------------------------------------------------------------
def test_no_rules_is_not_eligible():
    assert evaluate({'age': 30}, {})['status'] == 'insufficient_information'


def test_boolean_rules_must_be_answered_explicitly():
    rules = {'income_tax_payer': False, 'bank_account': True}
    assert evaluate({'income_tax_payer': False, 'has_bank_account': True}, rules)['status'] == 'eligible_by_recorded_rules'
    assert evaluate({'income_tax_payer': True, 'has_bank_account': True}, rules)['status'] == 'ineligible'
    result = evaluate({'income_tax_payer': False}, rules)
    assert result['status'] == 'insufficient_information'
    assert result['missing_fields'] == ['has_bank_account']


def test_gender_and_occupation_normalisation():
    rules = {'genders': ['female'], 'occupations': ['farmer']}
    assert evaluate({'gender': 'Woman', 'occupation': 'Kisan (wheat)'}, rules)['status'] == 'eligible_by_recorded_rules'
    assert evaluate({'gender': 'Man', 'occupation': 'farmer'}, rules)['status'] == 'ineligible'
    assert evaluate({'gender': 'Prefer not to say', 'occupation': 'farmer'}, rules)['status'] == 'insufficient_information'


def test_occupations_not():
    rules = {'occupations_not': ['student', 'government_employee']}
    assert evaluate({'occupation': 'street_vendor'}, rules)['status'] == 'eligible_by_recorded_rules'
    assert evaluate({'occupation': 'student'}, rules)['status'] == 'ineligible'


def test_any_of_groups():
    rules = {'any_of': [{'genders': ['female']}, {'social_categories': ['SC', 'ST']}]}
    assert evaluate({'gender': 'Woman'}, rules)['status'] == 'eligible_by_recorded_rules'
    assert evaluate({'gender': 'Man', 'social_category': 'st'}, rules)['status'] == 'eligible_by_recorded_rules'
    assert evaluate({'gender': 'Man', 'social_category': 'General'}, rules)['status'] == 'ineligible'
    unknown = evaluate({'gender': 'Man'}, rules)
    assert unknown['status'] == 'insufficient_information'
    assert 'social_category' in unknown['missing_fields']


def test_checks_are_explained():
    result = evaluate({'annual_income': 300000}, {'income_max': 250000})
    check = result['checks'][0]
    assert check['result'] == 'fail'
    assert check['label'] == 'Annual family income up to ₹2,50,000'
    assert check['actual_display'] == '₹3,00,000'


def test_format_inr_indian_grouping():
    assert format_inr(250000) == '₹2,50,000'
    assert format_inr(12000000) == '₹1,20,00,000'
    assert format_inr(999) == '₹999'


def test_normalize_occupation_free_text():
    assert normalize_occupation('Software engineer') == 'salaried_private'
    assert normalize_occupation('street vendor') == 'street_vendor'
    assert normalize_occupation('Agricultural labourer') == 'agricultural_labourer'
    assert normalize_occupation('astronaut') == 'other'
    assert normalize_occupation('') is None


def test_validate_rules_rejects_bad_input():
    validate_rules({'age_min': 18, 'any_of': [{'genders': ['female']}]})
    with pytest.raises(ValueError):
        validate_rules({'favourite_colour': 'blue'})
    with pytest.raises(ValueError):
        validate_rules({'occupations': ['wizard']})
    with pytest.raises(ValueError):
        validate_rules({'income_tax_payer': 'no'})
    with pytest.raises(ValueError):
        validate_rules({'any_of': []})


def test_describe_any_of():
    text = describe_rule('any_of', [{'genders': ['female']}, {'social_categories': ['SC', 'ST']}])
    assert 'Women only' in text and 'SC/ST category' in text


def test_screen_all_orders_and_suggests_questions():
    schemes = [
        {'name': 'A', 'rules': {'age_min': 60}},
        {'name': 'B', 'rules': {'age_min': 18}},
        {'name': 'C', 'rules': {'age_min': 18, 'bpl': True}},
        {'name': 'D', 'rules': {'bpl': True}},
    ]
    out = screen_all({'age': 30}, schemes)
    assert [r['name'] for r in out['results']] == ['B', 'C', 'D', 'A']
    assert out['summary'] == {'eligible': 1, 'needs_information': 2, 'ineligible': 1, 'total': 4}
    assert out['suggested_questions'][0]['field'] == 'bpl_card'
    assert out['suggested_questions'][0]['schemes_affected'] == 2
