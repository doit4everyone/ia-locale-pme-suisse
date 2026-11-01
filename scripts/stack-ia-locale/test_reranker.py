"""
test_reranker.py : tests unitaires du reclassement (reclasser, 2.23.0), sans service.

Vérifie les deux formats de service : Text Embeddings Inference (« tei », conteneur
reranker du Compose) et llama-server --reranking (« llamacpp », sur la carte du
serveur de modèles), l'envoi de la clé, et le repli sur l'ordre de la recherche en
cas d'échec ou de réponse incomplète.

Lancement, depuis la VM, dans le conteneur de la RAG API :
  docker exec -w /app rag-api python3 /rag-pipeline/test_reranker.py

Attendu : « 6 tests OK », code de sortie 0.
"""

import asyncio
import sys

sys.path.insert(0, "/app")
try:
    import main  # code de la RAG API, dans le conteneur
except ImportError:  # hors conteneur : fichier du dépôt
    import importlib.util
    import os
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api", "anon_main.py")
    spec = importlib.util.spec_from_file_location("main", chemin)
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)

APPELS = []


class Reponse:
    def __init__(self, donnees, code=200):
        self.donnees, self.code = donnees, code

    def raise_for_status(self):
        if self.code >= 400:
            raise RuntimeError(f"HTTP {self.code}")

    def json(self):
        return self.donnees


def faux_client(reponse):
    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            APPELS.append({"url": url, "json": json, "headers": headers or {}})
            return reponse
    return Client


def extraits():
    return [{"source": f"doc{i}.docx", "text": f"texte {i}", "chunk_key": f"k{i}"} for i in range(3)]


def reclasser(reponse, api, cle="", mode="remplacement"):
    APPELS.clear()
    main.RERANKER_URL, main.RERANKER_API, main.RERANKER_API_KEY = "http://reranker", api, cle
    main.RERANK_MODE, main.RERANK_MAX = mode, 20
    main.httpx.AsyncClient = faux_client(reponse)
    return asyncio.run(main.reclasser("question", extraits()))


def verifier(nom, condition, detail=""):
    print(f"{'OK    ' if condition else 'ECHEC '} {nom}")
    if not condition:
        print(f"       {detail}")
    return condition


ordre = lambda res: [c["source"] for c in res]  # noqa: E731
resultats = []

# 1. TEI : corps « texts », liste [{index, score}], pas de clé
res = reclasser(Reponse([{"index": 0, "score": 0.1}, {"index": 1, "score": 0.9}, {"index": 2, "score": 0.5}]), "tei")
resultats.append(verifier("TEI : format et ordre",
                          ordre(res) == ["doc1.docx", "doc2.docx", "doc0.docx"] and "texts" in APPELS[0]["json"]
                          and "Authorization" not in APPELS[0]["headers"], f"{ordre(res)} {APPELS}"))

# 2. llama-server : corps « documents », {results: [{index, relevance_score}]}
res = reclasser(Reponse({"results": [{"index": 2, "relevance_score": 3.2}, {"index": 0, "relevance_score": -1.0},
                                     {"index": 1, "relevance_score": 0.4}]}), "llamacpp", cle="secret")
resultats.append(verifier("llama-server : format et ordre",
                          ordre(res) == ["doc2.docx", "doc1.docx", "doc0.docx"] and "documents" in APPELS[0]["json"],
                          f"{ordre(res)} {APPELS}"))

# 3. Clé envoyée en Bearer quand elle est renseignée
resultats.append(verifier("clé envoyée", APPELS[0]["headers"].get("Authorization") == "Bearer secret", f"{APPELS}"))

# 4. Échec HTTP : ordre de la recherche conservé
res = reclasser(Reponse({}, code=401), "llamacpp")
resultats.append(verifier("échec HTTP : ordre conservé", ordre(res) == ["doc0.docx", "doc1.docx", "doc2.docx"],
                          f"{ordre(res)}"))

# 5. Réponse incomplète (moins de scores que d'extraits) : ordre conservé
res = reclasser(Reponse({"results": [{"index": 1, "relevance_score": 5.0}]}), "llamacpp")
resultats.append(verifier("réponse incomplète : ordre conservé", ordre(res) == ["doc0.docx", "doc1.docx", "doc2.docx"],
                          f"{ordre(res)}"))

# 6. Fusion : le premier de la recherche, second du reranker, reste devant
res = reclasser(Reponse([{"index": 0, "score": 0.5}, {"index": 1, "score": 0.9}, {"index": 2, "score": 0.1}]),
                "tei", mode="fusion")
resultats.append(verifier("fusion des rangs", ordre(res)[0] in ("doc0.docx", "doc1.docx") and ordre(res)[-1] == "doc2.docx",
                          f"{ordre(res)}"))

if all(resultats):
    print(f"{len(resultats)} tests OK")
    sys.exit(0)
print(f"{resultats.count(False)} test(s) en échec")
sys.exit(1)
