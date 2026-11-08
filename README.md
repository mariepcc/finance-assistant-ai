# Asystent finansowy AI

Mobilna aplikacja do finansów osobistych z asystentem AI (praca inżynierska).
Zasady dla agentów kodujących: [CLAUDE.md](CLAUDE.md).

| Katalog | Zawartość |
| --- | --- |
| `backend/` | FastAPI + SQLAlchemy (async) + Alembic; REST dla aplikacji, później agent i SSE |
| `mobile/` | Expo (SDK 58, Expo Router, TypeScript strict) |
| `mcp_server/` | Serwer MCP `finance-tools` (tydzień 2); na razie konfiguracja kategorii narzędzi |
| `supabase/` | Konfiguracja lokalnego Supabase (Postgres + Auth) |

## Uruchomienie lokalne

Wymagania: Docker, Node 20+, [uv](https://docs.astral.sh/uv/).

```bash
# 1. Baza i logowanie (Postgres :54322, Auth/API :54321, Studio :54323)
npx supabase start
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

## Testy i jakość

```bash
cd backend
uv run pytest                # tworzy od zera bazę TEST_DATABASE_URL (domyślnie finance_test na :54322)
uv run ruff check . && uv run mypy app tests

cd ../mobile
npx tsc --noEmit
```

## Model danych (tydzień 1)

`profiles` (id = użytkownik Supabase, zgoda RODO, waluta) → `categories` (kopiowane domyślne przy
onboardingu) → `transactions` (kwota `NUMERIC(12,2)` > 0, typ, data, notatka). Tabele `budgets` i
`proposals` istnieją już teraz, a używane będą w tygodniach 3–4. Na wszystkich tabelach jest włączone RLS
bez polityk, więc klucz publiczny Supabase nie daje dostępu do danych; dane idą wyłącznie przez backend,
a ten filtruje każde zapytanie po `user_id` z tokena JWT.
