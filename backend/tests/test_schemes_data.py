"""Guards the quality of schemes.json so bad data never reaches citizens."""
from app.seeding import load_records


def test_schemes_json_is_valid():
    records = load_records()  # raises on unsupported rules, bad URLs, duplicates, etc.
    assert len(records) >= 40


def test_every_published_record_is_complete():
    for item in load_records():
        name = item['name']
        assert item.get('source_verified_at'), f'{name}: missing verification date'
        assert item.get('benefits'), f'{name}: missing benefits'
        assert item.get('how_to_apply'), f'{name}: missing how_to_apply'
        assert item.get('documents'), f'{name}: missing documents'
        assert item.get('tags'), f'{name}: missing search tags'


def test_state_schemes_are_restricted_to_their_state():
    for item in load_records():
        if item.get('level') == 'State':
            assert item['rules'].get('states'), item['name']
