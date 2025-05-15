# Maui Building Code Assistant

The **Maui Building Code Assistant** is a lightweight AI micro‑service that answers Maui County building‑code questions in plain English (or light Pidgin) and always cites the relevant code section.

---

## ✨  Features
- Natural‑language Q&A over local building‑code references  
- Semantic search with Pinecone vector DB + OpenAI `text‑embedding‑ada‑002`  
- FastAPI backend served by _uvicorn_ with fully async flows  
- Built‑in rate‑limiting, structured logging, and layered config (env ▸ file ▸ CLI)  
- Runs locally with `requirements.txt`, `.env`, and a single command

---

## 🖼️  High‑level Architecture

```
User ➜ FastAPI (server/app.py) ─┬─▶ OpenAI  (chat completions & embeddings)
                                └─▶ Pinecone (vector search over code snippets)
```

1. **Client request** hits `/api` with the running chat history  
2. The last user question is embedded ➜ Pinecone returns the top‑*k* code snippets  
3. Retrieved snippets are inserted into the prompt and sent to OpenAI (`gpt‑4o‑mini` by default)  
4. The assistant returns a markdown‑formatted answer with inline citations

---

## 🚀  Quick‑start

```bash
git clone https://github.com/your-org/mauibuilder.git
cd mauibuilder/server

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Add your secrets to a .env file in the project root
echo "OPENAI_API_KEY=sk-..."    >> .env
echo "PINECONE_API_KEY=..."     >> .env
echo "ENVIRONMENT=development"  >> .env  # optional

python -m server --host 0.0.0.0 --port 8000 --reload
# Swagger UI → http://127.0.0.1:8000/docs
```

---

## 🔧  Runtime Configuration

| Source | Purpose | Example |
|--------|---------|---------|
| **Environment vars / `.env`** | Secrets & per‑host overrides | `OPENAI_API_KEY`, `PINECONE_API_KEY` |
| **`server/config.json`** | Committed defaults | `"model_name": "gpt-4o-mini"` |
| **CLI flags** | One‑off tweaks | `--pinecone_top_k 5 --temperature 0.3` |

### Common CLI flags

```text
--host 0.0.0.0                 # bind address (default 0.0.0.0)
--port 8000                    # port (default 8000)
--model_name gpt-4o-mini       # OpenAI chat model
--pinecone_top_k 3             # number of snippets to retrieve
--min_similarity_threshold 0.5 # filter low‑score matches
--reload                       # auto‑reload on code change (dev)
```

---

## 📡  API Reference

### `POST /api`

| Field | Type | Description |
|-------|------|-------------|
| `messages` | array | Chat history (`role`, `content`) |

Example:

```bash
curl -X POST http://localhost:8000/api \
     -H "Content-Type: application/json" \
     -d '{
           "messages":[
             {"role":"user","content":"Do I need fire sprinklers in a two‑storey dwelling?"}
           ]
         }'
```

### `POST /feedback`

Save a thumbs‑up / down plus conversation for future fine‑tuning.

---

## 📝  Logging

Logs are written to `server/logs/server.log` **and** STDOUT:

```
YYYY‑MM‑DD HH:MM:SS,ms - module - LEVEL - message
```

---

## 🧪  Testing

```bash
pytest -q
```

Unit tests mock external services, so no API keys required.

---

## 🗄️  Project Structure

```
server/
├── app.py             # FastAPI routes & core logic
├── __main__.py        # CLI entry‑point (uvicorn runner)
├── configmanager.py   # layered config manager
├── ratelimiter.py     # token‑bucket limiter
├── logs/
└── …
```

---

## 📦  Deploying / Updating from GitHub

Run in production without Docker:

```bash
ssh user@prod-server
git clone https://github.com/your-org/mauibuilder.git   # first time
cd mauibuilder/server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt --upgrade
cp ../.env.example .env   # add API keys
python -m server --host 0.0.0.0 --port 8000
```

For subsequent updates:

```bash
cd /opt/mauibuilder/server
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart maui-code.service   # if using systemd
```

You can also automate this with a lightweight GitHub Actions workflow that SSHes into the server and runs the same commands on each push to `main`.

---

## 📄  License

MIT — see `LICENSE` for details.
