"""
comparer_vecteurs.py : les vecteurs calculés par vLLM sont-ils ceux de l'index
construit avec Ollama ? (§2.5, 2.23.0, modèle bge-m3)

Prend 50 extraits au hasard dans chaque collection de la stack (documents et
documentation), recalcule leur vecteur avec le serveur d'embedding vLLM et
compare au vecteur stocké dans Qdrant (similarité cosinus).

Lancement, depuis la VM, la clé vLLM saisie sans affichage :
  read -rs VK
  docker exec -e VLLM_API_KEY="$VK" rag-api python3 /rag-pipeline/comparer_vecteurs.py

Adresse de vLLM : celle de EMBED_BASE_URL (le serveur de modèles), port 8001.
Modèle : EMBED_MODEL du conteneur (bge-m3).
Attendu : similarité minimale d'au moins 0,999. En dessous de 0,99 : réindexer.
"""
import math
import os
import random
import re
import time
from urllib.parse import urlparse

import httpx
from qdrant_client import QdrantClient

base = urlparse(os.environ["EMBED_BASE_URL"])
url_vllm = os.environ.get("VLLM_URL") or f"{base.scheme}://{base.hostname}:8001"
modele = os.environ["EMBED_MODEL"]
prefixe = os.environ.get("EMBED_PREFIXE_DOCUMENT", "").replace("\\n", "\n")
entetes = {"Authorization": "Bearer " + os.environ["VLLM_API_KEY"]}
q = QdrantClient(url=os.environ["QDRANT_HOST"], api_key=os.environ["QDRANT_API_KEY"])


def cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


print(f"vLLM : {url_vllm}, modèle {modele}")
for collection in (os.environ["QDRANT_COLLECTION"], os.environ["DOCUMENTATION_COLLECTION"]):
    pts, _ = q.scroll(collection_name=collection, limit=2000, with_payload=["text", "embed_model"],
                      with_vectors=True)
    modeles = {p.payload.get("embed_model") for p in pts}
    random.seed(1)
    pts = random.sample(pts, min(50, len(pts)))
    res, debut = [], time.time()
    for p in pts:
        texte = prefixe + re.sub(r'[. ]{10,}', ' ', p.payload["text"]).strip()
        r = httpx.post(url_vllm + "/v1/embeddings", headers=entetes,
                       json={"model": modele, "input": texte}, timeout=60)
        r.raise_for_status()
        v = p.vector if isinstance(p.vector, list) else list(p.vector.values())[0]
        res.append(cos(v, r.json()["data"][0]["embedding"]))
    duree = (time.time() - debut) / max(1, len(res))
    print(f"{collection} : index construit avec {sorted(m for m in modeles if m)} | "
          f"extraits {len(res)} | similarité minimale {min(res):.5f} | moyenne {sum(res) / len(res):.5f} | "
          f"{duree * 1000:.0f} ms par extrait")
