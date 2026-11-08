# Serwer MCP `finance-tools` (tydzień 2)

FastMCP, transport HTTP. `user_id` pochodzi wyłącznie z tokena JWT w nagłówku `Authorization`,
nigdy z parametrów narzędzi. Zapytania do bazy mają korzystać z repozytoriów z `backend/app/repositories`
(sparametryzowany SQL, zawsze filtrowany po `user_id`).

- `tool_categories.py`: kategorie narzędzi (jedno źródło prawdy, sprawdzane testem przy starcie).
- Do zrobienia w tygodniu 2: `server.py`, narzędzia P1, testy jednostkowe, uruchomienie w MCP Inspector
  (`npx @modelcontextprotocol/inspector`).
