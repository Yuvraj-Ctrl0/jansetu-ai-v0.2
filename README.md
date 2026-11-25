# JanSetu AI

**An Intelligent Government Scheme Recommendation and Eligibility Assistance System** — B.Tech CSE major project (v0.2).

JanSetu helps citizens find Indian government welfare schemes, check eligibility rule by rule, and ask questions in Hindi or English through an AI assistant ("Sahayak") that answers only from verified scheme records.

## What's new in v0.2

| Area | v0.1 | v0.2 |
|---|---|---|
| Schemes | 25 records, empty rules, 5 published | **44 schemes** (19 new) with eligibility rules, benefits, documents and how-to-apply, each checked against public sources on 25 Nov 2026 |
| Eligibility | 5 rule types, login required | **24 rule types** + `any_of` groups, plain-language reasons, public **Check eligibility** wizard, "answer these to check more schemes" (adaptive questions) |
| AI | none | **Sahayak chatbot**: retrieval over the scheme DB + Gemini (or any OpenAI-compatible API), offline fallback, Hindi/Hinglish query expansion, voice input, Aadhaar redaction, rate limiting |
| UI | single 120-line file, login wall | Component-based React app; browse without signing in; scheme drawer with document checklist; dashboard with personal matches; mobile-ready |
| Data ops | manual DB edits | Idempotent seeder with rule versioning, additive schema sync for existing databases, data-quality tests |

New schemes include: PM Internship Scheme (Round 3: ₹9,000/month), PM Viksit Bharat Rozgar Yojana, VB-G RAM G (replaced MGNREGA on 1 July 2026), Ayushman Vay Vandana (70+), Stand-Up India (extended to 2031), PM Vidyalaxmi, PM-USP scholarship, NMMSS, Post-Matric SC scholarship, e-Shram, PMGKAY, PMKVY 4.0, Sukanya Samriddhi, Jan Dhan, Kisan Credit Card, PM Parivar Labh Yojana, and state schemes (MP Ladli Behna, MP Kisan Kalyan, Maharashtra Ladki Bahin). Existing records were updated too — e.g. PMAY-Urban → **PMAY-U 2.0**, and NSAP pensions renamed in Oct 2026 (IGNOAPS → **PM Vridhavastha Pension Yojana**, IGNDPS → **PM Divyangjan Pension Yojana** with the new 40% disability threshold and ₹375/₹625 rates).

## Tech stack

- **Frontend:** React 18 + Vite, lucide-react icons, self-hosted Anek and Mukta fonts (Latin + Devanagari)
- **Backend:** Python, Flask, Flask-JWT-Extended, SQLAlchemy (MySQL / PostgreSQL / SQLite)
- **Recommendation:** TF-IDF + cosine similarity (scikit-learn), plus name/abbreviation matching
- **Eligibility:** deterministic, explainable rule engine (`backend/app/engine.py`)
- **Chatbot:** retrieval-augmented generation over the scheme table (`backend/app/chatbot.py`)

## How the AI chatbot works

```
question ──► redact Aadhaar/account numbers ──► expand Hindi/Hinglish keywords
        ──► retrieve top schemes (TF-IDF + name match)   or, for "which schemes am I eligible for?",
                                                          run the rule engine on the user's details
        ──► prompt = rules + ONLY those scheme records + preliminary screening
        ──► Gemini / OpenAI-compatible model ──► answer + source chips (open the scheme)
             └─ no key or API error ──► deterministic answer built from the same records
```

The model is instructed never to invent amounts or criteria, to reply in the user's language, never to ask for Aadhaar/OTP, and to point to the official link. Without an API key, the chatbot still answers from the database (the panel shows "Database answers").

**Get a free Gemini key:** https://aistudio.google.com/app/apikey → set `GEMINI_API_KEY`. Any OpenAI-compatible provider also works (`LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`).

## Eligibility rules

Rules live in `backend/schemes.json`. Supported keys:

`age_min, age_max, income_min, income_max, states, occupations, occupations_not, genders, social_categories, areas, marital_statuses, student_levels, disability, income_tax_payer, organised_sector_member, govt_employee_in_family, bank_account, bpl, land_owner, land_max_hectares, pucca_house, lpg_connection, pregnant_or_lactating, daughter_below_10, any_of`

Example (Stand-Up India — adult **and** (woman **or** SC/ST)):

```json
"rules": {"age_min": 18, "any_of": [{"genders": ["female"]}, {"social_categories": ["SC", "ST"]}]}
```

Outcomes: `eligible_by_recorded_rules`, `insufficient_information` (an unanswered question never counts as a pass), `ineligible`. Conditions the engine cannot check go in `additional_conditions` and are shown as "Also confirm before applying".

## Quick start (Docker)

1. `cp .env.example .env` — set `JWT_SECRET_KEY` (`python -c "import secrets;print(secrets.token_hex(32))"`), `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, and optionally `GEMINI_API_KEY`.
2. `docker compose up -d --build` — creates tables, adds new columns to an existing database, and loads/publishes the schemes (`AUTO_SEED_SCHEMES=true`).
3. `cd frontend && npm install && npm run dev`
4. Open http://localhost:5173

## Quick start (local, no Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///jansetu.db JWT_SECRET_KEY=<random> AUTO_SEED_SCHEMES=true
export GEMINI_API_KEY=<optional>
python init_db.py && python run.py
# new terminal
cd frontend && npm install && npm run dev
```

### Upgrading an existing v0.1 database (MySQL/PostgreSQL)

Back up first, then run `python init_db.py` (or restart the Docker/Render service). It only **adds** missing nullable columns. Then `python seed_schemes.py --publish` updates the 25 existing records (matched by name or `previous_names`, so renamed schemes are not duplicated), bumps `rule_version` where rules changed, and adds the new ones. Use `--dry-run` to preview.

### Render / Vercel deployment

On the Render backend service add the environment variables `AUTO_SEED_SCHEMES=true` and `GEMINI_API_KEY` (optional) and redeploy. The Vercel frontend needs no change (`/api/*` is already rewritten to Render).

## Tests

```bash
cd backend && python -m pytest -q      # 41 tests: engine, API, chatbot (mocked LLM), migration, data quality
cd frontend && npm run build
```

`tests/test_schemes_data.py` fails if a scheme has an unsupported rule, a non-HTTPS link, a missing verification date, missing documents/benefits, or a state scheme without a state rule.

## API routes

| Method | Route | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health`, `/api/meta` | – | status; form options, categories, chatbot mode |
| GET | `/api/schemes`, `/api/schemes/:id` | – | published schemes with criteria, benefits, documents |
| POST | `/api/eligibility/check` | – | screen all schemes for submitted details; returns results, summary, suggested questions |
| POST | `/api/chat` | optional | chatbot (`message`, `history`, optional `profile`) |
| POST | `/api/auth/register`, `/api/auth/login` | – | accounts |
| GET/PUT | `/api/profile` | JWT | citizen profile |
| GET | `/api/dashboard` | JWT | completion, screening summary, top matches |
| POST | `/api/recommendations` | JWT | TF-IDF ranking + eligibility |
| POST | `/api/schemes/:id/eligibility` | JWT | one scheme |
| GET/POST, DELETE | `/api/saved`, `/api/saved/:id` | JWT | saved schemes |

## Keeping scheme data current

Schemes change often (amounts, renames, deadlines). To update: edit `backend/schemes.json`, set `source_verified_at` to the date you checked the official source, run the tests, then `python seed_schemes.py --publish`. `python check_scheme_links.py` reports broken official links.

## Limitations

Academic prototype, not an official government service. Eligibility results are preliminary; many schemes have conditions that need documents or official databases (e.g. SECC lists). Some rules are simplified (e.g. PM-SYM's ₹15,000 *personal* monthly income is shown as a condition, not checked). The chatbot can still make mistakes even when grounded — the UI always links to the official source. JWT is stored in sessionStorage; add refresh tokens, persistent rate limiting, audit logs and admin review before any public launch.

See `docs/PROJECT_PLAN.md` for the research and submission roadmap.
#   j a n s e t u - a i - v 0 . 2  
 #   j a n s e t u - a i - v 0 . 2  
 j a n s e t u - a i - v 0 . 2  
 