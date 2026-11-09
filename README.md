# Asystent finansowy AI

Mobilna aplikacja do finansów osobistych z asystentem AI (praca inżynierska).
Zasady dla agentów kodujących: [CLAUDE.md](CLAUDE.md).

| Katalog | Zawartość |
| --- | --- |
| `backend/` | FastAPI + SQLAlchemy (async) + Alembic; REST dla aplikacji, później agent i SSE |
| `mobile/` | Expo (SDK 58, Expo Router, TypeScript strict) |
| `mcp_server/` | Serwer MCP `finance-tools` (FastMCP, HTTP): 9 narzędzi P1, korzysta z kodu backendu |
| `supabase/` | Konfiguracja lokalnego Supabase (Postgres + Auth) |

## Uruchomienie lokalne

Wymagania: Docker, Node 20+, [uv](https://docs.astral.sh/uv/).

```bash
# 1. Baza i logowanie (Postgres :54322, Auth/API :54321)
npx supabase start -x studio,realtime,storage-api,imgproxy,edge-runtime,logflare,vector,postgres-meta,supavisor,mailpit
npx supabase status          # adres API i klucz publiczny (anon / publishable)

# 2. Backend
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head  # schemat zarządza Alembic, nie migracje Supabase
uv run fastapi dev app/main.py --host 0.0.0.0   # dokumentacja API: http://127.0.0.1:8000/docs

# 3. Aplikacja mobilna
cd ../mobile
cp .env.example .env         # wpisz klucz anon; na telefonie użyj IP komputera zamiast 127.0.0.1
npm install
npx expo start               # zeskanuj kod QR w Expo Go
```

Pełny `npx supabase start` (bez `-x`) uruchamia też Studio na :54323, ale zużywa dużo więcej pamięci.

## Serwer MCP

```bash
cd mcp_server
uv sync
uv run uvicorn finance_tools.server:app --port 8001     # endpoint: http://127.0.0.1:8001/mcp
npx @modelcontextprotocol/inspector                       # Streamable HTTP, nagłówek Authorization: Bearer <token>
```

Token to `access_token` z logowania przez Supabase Auth (np. `POST :54321/auth/v1/token?grant_type=password`
z nagłówkiem `apikey`). Narzędzia `propose_*` tworzą tylko propozycję; zapis następuje przez
`POST /proposals/{id}/confirm` w backendzie.

Dane przykładowe dla konta testowego (ok. 3 miesiące transakcji i 4 budżety):

```bash
cd backend
uv run python scripts/seed_demo.py --email test1@example.com --reset   # --reset usuwa transakcje i budżety tego konta
```

## Czat z asystentem

Czat potrzebuje trzech procesów: Supabase, serwera MCP (`:8001`) i backendu (`:8000`), oraz klucza API
modelu w `backend/.env`:

```bash
ANTHROPIC_API_KEY=...        # z https://platform.claude.com, nigdy w repozytorium
MCP_URL=http://127.0.0.1:8001/mcp
```

`POST /chat` zwraca strumień SSE (`status`, `proposal`, `token`, `done`, `error`). Agent działa tak:
router (Claude Haiku 5.5, wyjście strukturalne) wybiera 1–2 grupy narzędzi, workery (`run_worker`)
wywołują narzędzia MCP z tokenem użytkownika, redaktor scala dwie odpowiedzi, a kod sprawdza, czy każda
liczba w odpowiedzi występuje w wynikach narzędzi (jedna poprawka, potem uczciwy komunikat). Modele,
`effort` i limity kroków są w `app/config.py`. Bez klucza czat odpowiada komunikatem o braku klucza.

## Testy i jakość

```bash
cd backend
uv run pytest                # tworzy od zera bazę TEST_DATABASE_URL (domyślnie finance_test na :54322)
uv run ruff check . && uv run mypy app tests

cd ../mcp_server
uv run pytest                # baza finance_mcp_test na :54322
uv run ruff check . && uv run mypy finance_tools tests

cd ../mobile
npx tsc --noEmit
```

## Model danych (tydzień 1)

`profiles` (id = użytkownik Supabase, zgoda RODO, waluta) → `categories` (kopiowane domyślne przy
onboardingu) → `transactions` (kwota `NUMERIC(12,2)` > 0, typ, data, notatka). Tabele `budgets` i
`proposals` istnieją już teraz, a używane będą w tygodniach 3–4. Na wszystkich tabelach jest włączone RLS
bez polityk, więc klucz publiczny Supabase nie daje dostępu do danych; dane idą wyłącznie przez backend,
a ten filtruje każde zapytanie po `user_id` z tokena JWT.
