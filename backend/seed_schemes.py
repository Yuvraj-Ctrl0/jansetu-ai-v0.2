"""Import or update government schemes from schemes.json.

Usage (inside backend/, with DATABASE_URL and JWT_SECRET_KEY set):
    python seed_schemes.py              # add/update records as drafts (active stays unchanged)
    python seed_schemes.py --publish    # also publish records that have source_verified_at
    python seed_schemes.py --dry-run    # validate and show changes without saving

Docker:  docker compose exec api python seed_schemes.py --publish
"""
import argparse

from app import create_app
from app.seeding import seed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--publish', action='store_true', help='publish records that carry source_verified_at')
    parser.add_argument('--dry-run', action='store_true', help='validate and report without saving')
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        stats = seed(publish=args.publish, dry_run=args.dry_run)
    print()
    print('Import completed.', ', '.join(f'{k}: {v}' for k, v in stats.items()))
    if not args.publish:
        print('Tip: run with --publish to make verified schemes visible to citizens.')


if __name__ == '__main__':
    main()
