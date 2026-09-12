---
title: "§3 Docker Compose : stack complète | Guide de déploiement stack IA locale"
description: "Déploiement de Qdrant, n8n et la RAG API FastAPI via Docker Compose sur VM-RAG-LAB."
---
<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2, h3 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
  code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.95em; }
  pre { background: #f4f4f4; padding: 16px; border-radius: 6px; overflow-x: auto; }
  blockquote { border-left: 4px solid #2563A8; margin: 20px 0; padding: 10px 20px; background: #f0f4ff; }
</style>

# §3 Docker Compose : stack complète

[Retour au sommaire](index.md) | [Section précédente : §2 vLLM](section-02-vllm.md)

**Statut :** validé sur VM-RAG-LAB, septembre 2026. La RAG API est un squelette de validation : elle ne fait pas de RAG à ce stade, voir l'encadré de cadrage en tête de §3.

---

> **Ce que cette section déploie et ce qu'elle ne déploie pas**
>
> Cette section déploie trois composants via Docker Compose : Qdrant (vector store), n8n (orchestration) et une RAG API FastAPI. Onyx n'est pas dans cette stack : il dispose de sa propre stack Docker Compose déployée séparément en §4.
>
> La RAG API déployée ici est un **squelette de validation**. Elle expose les bons endpoints (`/health`, `/stats`, `/query`) et vérifie la connectivité avec Qdrant et le LLM, mais elle n'interroge pas encore Qdrant et ne retourne pas de sources documentaires. Son seul rôle à ce stade est de valider que l'authentification, le routage et la connectivité fonctionnent. La RAG API complète avec indexation, recherche vectorielle et filtrage ACL fait l'objet de la Partie 2 de ce guide.

---

## §3.1 Structure des répertoires

```bash
mkdir -p ~/rag-stack/{qdrant_data,n8n_data,api}
cd ~/rag-stack
```

---

## §3.2 Fichier .env

Toutes les variables sensibles sont centralisées dans un fichier `.env` à la racine du projet. Ne jamais committer ce fichier dans Git.

```bash
cat > ~/rag-stack/.env << 'EOF'
# Endpoint d'inférence
# Mode validation VM-RAG-LAB (vLLM local) :
LLM_BASE_URL=http://172.17.0.1:8000
LLM_MODEL=Qwen/Qwen3-1.7B

# Mode production DGX Spark (changer uniquement le modèle) :
# LLM_MODEL=Qwen/Qwen3-30B-A3B
# LLM_BASE_URL reste sur 172.17.0.1:8000 si vLLM tourne sur la VM
# ou sur l'IP réseau du DGX Spark si vLLM tourne sur une machine séparée

QDRANT_HOST=http://qdrant:6333
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=changeme


API_TOKEN=changeme-api-token
EOF
```

> **Point critique :** `LLM_BASE_URL` doit utiliser l'IP de la passerelle Docker (`172.17.0.1`) et non `localhost`. Depuis l'intérieur d'un conteneur Docker, `localhost` pointe sur le conteneur lui-même, pas sur la VM hôte. vLLM tournant directement sur la VM (hors Docker), `localhost:8000` est inaccessible depuis les conteneurs. L'IP `172.17.0.1` est l'adresse de la passerelle Docker, toujours accessible depuis tous les conteneurs.

Pour vérifier l'IP de la passerelle Docker sur votre système :

```bash
ip addr show docker0 | grep "inet "
```

---

## §3.3 FastAPI RAG API

La RAG API est construite localement via Docker. Créer les trois fichiers suivants :

**api/requirements.txt**

```
fastapi
uvicorn[standard]
qdrant-client
httpx
python-dotenv
```

**api/Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**api/main.py**

> **Ce fichier est un squelette de validation.** Il expose les bons endpoints et vérifie la connectivité, mais l'endpoint `/query` appelle le LLM directement sans interroger Qdrant et retourne `"sources": []` en dur. Ce n'est pas encore une RAG API : c'est un proxy LLM avec authentification. La version complète avec indexation, recherche vectorielle et filtrage ACL est développée en Partie 2.

```python
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import httpx
import os

# SQUELETTE DE VALIDATION - voir Partie 2 pour la version complète avec RAG
app = FastAPI(title="RAG API - squelette de validation")
security = HTTPBearer()

API_TOKEN = os.getenv("API_TOKEN", "changeme-api-token")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://172.17.0.1:8000")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3-1.7B")
QDRANT_HOST = os.getenv("QDRANT_HOST", "http://qdrant:6333")

class QueryRequest(BaseModel):
    query: str
    user_id: str = "anonymous"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/stats")
async def stats():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{QDRANT_HOST}/collections")
    return {"qdrant": r.json(), "llm": LLM_BASE_URL, "model": LLM_MODEL}

@app.post("/query")
async def query(
    request: QueryRequest,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalide")

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "Tu es un assistant documentaire."},
                    {"role": "user", "content": f"/no_think {request.query}"}
                ],
                "max_tokens": 500,
                "chat_template_kwargs": {"enable_thinking": False}
            }
        )
    result = response.json()
    return {
        "answer": result["choices"][0]["message"]["content"],
        "user_id": request.user_id,
        "sources": []
    }
```

---

## §3.4 docker-compose.yml

```yaml
services:

  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    ports:
      - "6333:6333"
    volumes:
      - ./qdrant_data:/qdrant/storage
    restart: unless-stopped

  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_BASIC_AUTH_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_BASIC_AUTH_PASSWORD}
      - N8N_HOST=0.0.0.0
      - WEBHOOK_URL=http://10.100.1.15:5678
    volumes:
      - ./n8n_data:/home/node/.n8n
    restart: unless-stopped

  rag-api:
    build: ./api
    container_name: rag-api
    ports:
      - "8080:8080"
    environment:
      - QDRANT_HOST=${QDRANT_HOST}
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_MODEL=${LLM_MODEL}
      - API_TOKEN=${API_TOKEN}
    depends_on:
      - qdrant
    restart: unless-stopped
```

---

## §3.5 Lancement de la stack

```bash
# Corriger les permissions n8n avant le premier lancement
sudo chown -R 1000:1000 ~/rag-stack/n8n_data

cd ~/rag-stack
docker compose up -d

# Vérification
docker compose ps

# Logs en temps réel
docker compose logs -f

# Arrêt propre
docker compose down
```

> **Point critique :** sans `chown -R 1000:1000` sur le répertoire `n8n_data`, n8n redémarre en boucle avec `EACCES: permission denied`. Le conteneur n8n tourne avec l'utilisateur `node` (uid 1000) mais le répertoire est créé par root lors du `mkdir`.

---

## §3.6 Validation

```bash
# Qdrant opérationnel
curl http://localhost:6333/collections

# n8n health check
curl http://localhost:5678/healthz

# RAG API health
curl http://localhost:8080/health

# RAG API stats (vérifie la connectivité Qdrant et la config LLM)
curl http://localhost:8080/stats

# Test requête authentifiée
curl -X POST http://localhost:8080/query \
  -H "Authorization: Bearer changeme-api-token" \
  -H "Content-Type: application/json" \
  -d '{"query": "Test RAG", "user_id": "test"}'

# Test rejet sans token (doit retourner 403)
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "user_id": "test"}'
```

---

[Suite : §4 Configuration Onyx](section-04-onyx.md)

---

*Validé sur VM-RAG-LAB, Ubuntu 26.04 LTS (resolute), Docker 29.7.2, août 2026.*
