"""Create tables, add any new (nullable) columns, and optionally load verified schemes.

Set AUTO_SEED_SCHEMES=true to import schemes.json and publish records that carry a
source_verified_at date (used by the Docker/Render start command).
"""
import os

from app import create_app
from app.extensions import db
from app.schema_sync import sync_schema
from app.seeding import seed

app = create_app()
with app.app_context():
    db.create_all()
    sync_schema()
    print('Database tables are ready.')
    if os.getenv('AUTO_SEED_SCHEMES', '').strip().lower() in {'1', 'true', 'yes'}:
        stats = seed(publish=True, verbose=False)
        print(f"Schemes synced from schemes.json: {stats}")
    else:
        print('Schemes not auto-loaded. Run `python seed_schemes.py --publish` (or set AUTO_SEED_SCHEMES=true).')
