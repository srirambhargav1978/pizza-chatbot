# Pizza Chatbot — FastAPI + LangGraph ordering agent.
# main.py (API + chat UI), agent.py (3-node LangGraph: parse intent ->
# apply to cart/SQLite -> generate reply), menu.py (catalog), db.py
# (SQLite — customers + completed orders). The SQLite file lives inside
# the container by default; mount a volume at /app if you want order
# history to survive rebuilds, not just restarts.

FROM python:3.12-slim

WORKDIR /app

# Install deps first so rebuilds are fast when only app code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Point your app's OpenAI-compatible client at:
#   base_url = os.environ["LITELLM_BASE_URL"]   (set by docker-compose)
#   api_key  = os.environ["LITELLM_MASTER_KEY"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
