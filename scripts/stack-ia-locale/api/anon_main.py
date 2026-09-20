"""
RAG API - Pipeline complet avec groundedness check
Stack : Qdrant (vector store) + Ollama (LLM + embedding) + FastAPI
Validé sur VM-RAG-LAB, septembre 2026
"""

from fastapi import FastAPI, HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
import httpx
import json
import os
import hashlib
import logging
import subprocess
import asyncio
from datetime import datetime, timezone
from auth import get_user_groups, check_access
from rank_bm25 import BM25Okapi

# ─────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────

API_TOKEN    = os.getenv("API_TOKEN", "changeme-api-token")
ADMIN_TOKEN  = os.getenv("ADMIN_TOKEN", "changeme-admin-token")
SYNC_SCRIPTS_DIR = os.getenv("SYNC_SCRIPTS_DIR", "/rag-pipeline")
SMB_SHARE    = os.getenv("SMB_SHARE", "//fileserver/PartageDocuments")
SMB_MOUNT    = os.getenv("SMB_MOUNT", "/mnt/corpus-root")
SMB_USER     = os.getenv("SMB_USER", "svc-rag")
SMB_PASSWORD = os.getenv("SMB_PASSWORD", "")
SMB_DOMAIN   = os.getenv("SMB_DOMAIN", "DOMAINE")

# Verrou global : une seule synchronisation à la fois
_sync_lock = asyncio.Lock()

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://<IP-HOTE-OLLAMA>:11434")
LLM_MODEL    = os.getenv("LLM_MODEL", "qwen2.5:14b")
JUDGE_MODEL  = os.getenv("JUDGE_MODEL", "qwen3:4b")
JUDGE_KEEP_ALIVE = os.getenv("JUDGE_KEEP_ALIVE", "2h")
QDRANT_HOST  = os.getenv("QDRANT_HOST", "http://qdrant:6333")
COLLECTION   = os.getenv("QDRANT_COLLECTION", "documents")
# Collection dediee a la documentation technique (guides, procedures).
# Les dossiers racine listes dans DOCUMENTATION_PATHS sont indexes ici.
# Ces dossiers doivent etre a la racine du partage SMB uniquement.
DOCUMENTATION_COLLECTION = os.getenv("DOCUMENTATION_COLLECTION", "documentation")
DOCUMENTATION_PATHS = [
    p.strip() for p in
    os.getenv("DOCUMENTATION_PATHS", "DOIT4EVERYONE").split(",")
    if p.strip()
]
LOG_FILE     = os.getenv("LOG_FILE", "/var/log/rag/rag-queries.jsonl")
TOP_K              = int(os.getenv("TOP_K", "12"))
EMBED_MODEL        = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBED_BASE_URL     = os.getenv("EMBED_BASE_URL", "") or os.getenv("LLM_BASE_URL", "http://<IP-HOTE-OLLAMA>:11434")
CONTEXT_THRESHOLD  = float(os.getenv("CONTEXT_THRESHOLD", "0.75"))
MAX_CONTEXT_CHUNKS = int(os.getenv("MAX_CONTEXT_CHUNKS", "15"))
ORG_NAME          = os.getenv("ORG_NAME", "votre organisation")

# ─────────────────────────────────────────
# Application
# ─────────────────────────────────────────

app = FastAPI(title="RAG API - pipeline complet")
security = HTTPBearer()
qdrant = QdrantClient(url=QDRANT_HOST)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Index BM25 : chargé au démarrage depuis Qdrant
# ─────────────────────────────────────────
# L'index BM25 tient en RAM : ~1 Mo pour 1 000 chunks,
# ~200 Mo pour 50 000 chunks. Au-delà de 200 000 chunks,
# préférer Qdrant BM42 (sparse vectors, index sur disque).
_bm25_index: BM25Okapi | None = None
_bm25_chunks: list[dict] = []


def get_collection_for_source(source_name: str) -> str:
    """Retourne la collection Qdrant pour ce chemin de source."""
    for prefix in DOCUMENTATION_PATHS:
        if source_name.startswith(prefix + "/") or source_name.startswith(prefix + "\\"):
            return DOCUMENTATION_COLLECTION
    return COLLECTION


def _load_collection_chunks(collection_name: str) -> list[dict]:
    """Charge les chunks d'une collection Qdrant pour l'index BM25."""
    try:
        points, _ = qdrant.scroll(
            collection_name=collection_name,
            limit=100_000,
            with_payload=True,
        )
        return [
            {
                # Clé unique par chunk : hash du texte. Distinct du source_id
                # qui est le hash du fichier (même pour tous les chunks d'un fichier).
                "chunk_key":   hashlib.md5(p.payload.get("text", "").encode()).hexdigest(),
                "text":        p.payload.get("text", ""),
                "source":      p.payload.get("source", "inconnu"),
                "source_id":   p.payload.get("source_id", ""),
                "collection":  collection_name,
                "chunk_index": p.payload.get("chunk_index", None),
                "autorises":   p.payload.get("autorises", []),
                "interdits":   p.payload.get("interdits", []),
            }
            for p in points
        ]
    except Exception as e:
        logger.warning(f"[BM25] Impossible de charger {collection_name} : {e}")
        return []


def build_bm25_index() -> None:
    """Charge les chunks des deux collections et construit l'index BM25.
    Appelé au démarrage et après chaque synchronisation réussie.
    Si Qdrant n'est pas disponible, l'index reste None et le retrieval
    retombe sur la recherche vectorielle seule sans erreur.
    """
    global _bm25_index, _bm25_chunks
    try:
        docs     = _load_collection_chunks(COLLECTION)
        docutech = _load_collection_chunks(DOCUMENTATION_COLLECTION)
        _bm25_chunks = docs + docutech
        tokenized = [c["text"].lower().split() for c in _bm25_chunks]
        _bm25_index = BM25Okapi(tokenized)
        logger.info(
            "[BM25] Index construit : %d chunks '%s' + %d chunks '%s'",
            len(docs), COLLECTION, len(docutech), DOCUMENTATION_COLLECTION
        )
    except Exception as e:
        logger.warning(f"[BM25] Impossible de construire l'index : {e}")
        _bm25_index = None
        _bm25_chunks = []


@app.on_event("startup")
async def startup_event():
    """Construit l'index BM25 au démarrage du conteneur."""
    build_bm25_index()

# ─────────────────────────────────────────
# Modèles de données
# ─────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    user_id: str = "anonymous"
    skip_groundedness: bool = False

class QueryResponse(BaseModel):
    answer: str
    sources: list
    ancree: bool
    affirmations_non_sourcees: list
    user_id: str

# ─────────────────────────────────────────
# Prompt système strict
# ─────────────────────────────────────────

def get_system_prompt() -> str:
    return f"""Tu es un assistant documentaire expert au service des collaborateurs de {ORG_NAME}.
Tu réponds UNIQUEMENT en français à partir des documents fournis dans le contexte ci-dessous.

RÈGLES ABSOLUES :
- Si la réponse n'est pas dans les documents fournis, réponds exactement : "Cette information ne figure pas dans les documents disponibles."
- Tu ne complètes jamais avec tes connaissances générales.
- Chaque affirmation dans ta réponse doit être directement tirée d'un document du contexte.
- Cite le nom exact du fichier source entre crochets après chaque affirmation, sous la forme [nom_du_fichier.docx]. Utilise toujours le nom affiché dans l'en-tête du document, après le symbole →. Ne jamais écrire [Document X] ou numéroter les sources.
- Si les documents fournis ne contiennent pas d'information directement pertinente pour la question posée, réponds exactement : "Cette information ne figure pas dans les documents disponibles."
- Ne résume jamais le contenu d'un document si ce contenu ne répond pas directement à la question posée. Un document hors sujet doit être ignoré, pas résumé.
- Tu n'inventes rien. Tu ne fais jamais d'inférences.

/no_think"""

# ─────────────────────────────────────────
# Fonctions utilitaires
# ─────────────────────────────────────────

async def get_embedding(text: str) -> list[float]:
    """Génère un embedding via le service d'embedding."""
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{EMBED_BASE_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text}
        )
        r.raise_for_status()
        return r.json()["embedding"]


async def search_qdrant(query: str, top_k: int = TOP_K, user_groups: list[str] = None) -> list[dict]:
    """
    Recherche hybride : vectorielle (Qdrant, deux collections) + mots-clés (BM25),
    fusionnée par Reciprocal Rank Fusion (RRF, k=60).

    Clé RRF : hash du texte du chunk (chunk_key), unique par chunk.
    Contrairement au source_id (hash du fichier, identique pour tous les chunks
    d'un même fichier), le chunk_key permet à plusieurs chunks du même fichier
    d'entrer dans le classement RRF indépendamment.

    Le filtre ACL NTFS s'applique sur les deux branches.
    Si le meilleur résultat dépasse CONTEXT_THRESHOLD, récupère tous les chunks
    du même document via scroll (dans la bonne collection).
    """
    try:
        embedding = await get_embedding(query)

        # Filtre d'accès Qdrant (ALLOW)
        query_filter = None
        if user_groups:
            query_filter = Filter(must=[
                FieldCondition(
                    key="autorises",
                    match=MatchAny(any=user_groups)
                )
            ])

        # Recherche vectorielle : top_k par collection
        # Chaque collection retourne top_k candidats : total 2*top_k avant RRF.
        results = qdrant.query_points(
            collection_name=COLLECTION,
            query=embedding,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True
        ).points

        try:
            results_doc = qdrant.query_points(
                collection_name=DOCUMENTATION_COLLECTION,
                query=embedding,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True
            ).points
        except Exception:
            results_doc = []  # collection absente au premier démarrage

        # Résultats vectoriels : filtrage DENY + construction dict
        vec_results = []
        for r in list(results) + list(results_doc):
            interdits = r.payload.get("interdits", [])
            if interdits and user_groups:
                if not check_access(user_groups, r.payload.get("autorises", []), interdits):
                    continue
            text = r.payload.get("text", "")
            vec_results.append({
                "chunk_key":   hashlib.md5(text.encode()).hexdigest(),
                "score":       r.score,
                "text":        text,
                "source":      r.payload.get("source", "inconnu"),
                "source_id":   r.payload.get("source_id", ""),
                "collection":  get_collection_for_source(r.payload.get("source", "")),
                "chunk_index": r.payload.get("chunk_index", None),
                "autorises":   r.payload.get("autorises", []),
                "interdits":   r.payload.get("interdits", []),
            })

        # Résultats BM25 : recherche par mots-clés sur l'index en mémoire
        bm25_results = []
        if _bm25_index is not None and _bm25_chunks:
            tokens = query.lower().split()
            scores = _bm25_index.get_scores(tokens)
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            for idx, score in ranked[:top_k * 2]:
                if score < 0.01:
                    break
                c = _bm25_chunks[idx]
                if user_groups:
                    if not any(g in c["autorises"] for g in user_groups):
                        continue
                    if not check_access(user_groups, c["autorises"], c["interdits"]):
                        continue
                bm25_results.append({"score": score, **c})
                if len(bm25_results) >= top_k:
                    break

        # Fusion par Reciprocal Rank Fusion (RRF, k=60)
        # Clé = chunk_key (hash du texte), unique par chunk.
        # vec_results est triée par score cosinus décroissant avant l'énumération
        # pour éviter que la collection documentation soit pénalisée par un biais
        # de rang : sans tri, les rangs de documentation commencent à top_k.
        vec_results.sort(key=lambda x: x["score"], reverse=True)
        K = 60
        rrf_scores: dict[str, float] = {}
        rrf_data:   dict[str, dict]  = {}
        for rank, c in enumerate(vec_results):
            key = c["chunk_key"]
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (K + rank + 1)
            rrf_data[key] = c
        for rank, c in enumerate(bm25_results):
            key = c["chunk_key"]
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (K + rank + 1)
            rrf_data[key] = c

        chunks = [
            {**rrf_data[key], "score": score}
            for key, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        ][:top_k]

        if bm25_results:
            logger.info(
                f"[BM25] {len(bm25_results)} BM25 + {len(vec_results)} vectoriels"
                f" → {len(chunks)} chunks après RRF"
            )

        # Extension de contexte : si le meilleur chunk dépasse CONTEXT_THRESHOLD,
        # récupérer les chunks voisins du même document (par chunk_index).
        # IMPORTANT : scroll dans la bonne collection (documents ou documentation).
        if chunks and chunks[0]["score"] >= CONTEXT_THRESHOLD:
            best_source = chunks[0]["source"]
            best_collection = chunks[0].get("collection", get_collection_for_source(best_source))
            best_chunk_index = chunks[0].get("chunk_index", None)

            # Extension par chunk_index : récupérer les voisins du chunk gagnant
            # plutôt qu'un scroll aléatoire. Garantit que le chunk pertinent
            # reste dans le contexte et que les chunks sont dans l'ordre du document.
            if best_chunk_index is not None:
                radius = MAX_CONTEXT_CHUNKS // 2
                idx_min = max(0, best_chunk_index - radius)
                idx_max = best_chunk_index + radius
                scroll_filter_conditions = [
                    FieldCondition(key="source", match=MatchValue(value=best_source)),
                    FieldCondition(key="chunk_index", range={"gte": idx_min, "lte": idx_max}),
                ]
            else:
                # Fallback : scroll sans chunk_index (anciens chunks sans ce champ)
                scroll_filter_conditions = [
                    FieldCondition(key="source", match=MatchValue(value=best_source))
                ]
            if user_groups:
                scroll_filter_conditions.append(
                    FieldCondition(key="autorises", match=MatchAny(any=user_groups))
                )

            source_points = qdrant.scroll(
                collection_name=best_collection,
                scroll_filter=Filter(must=scroll_filter_conditions),
                limit=MAX_CONTEXT_CHUNKS,
                with_payload=True
            )[0]
            # Trier par chunk_index pour respecter l'ordre du document
            source_points_sorted = sorted(
                source_points,
                key=lambda r: r.payload.get("chunk_index", 0)
            )
            source_chunks = [
                {
                    "chunk_key":   hashlib.md5(r.payload.get("text", "").encode()).hexdigest(),
                    "score":       1.0,
                    "text":        r.payload.get("text", ""),
                    "source":      r.payload.get("source", "inconnu"),
                    "source_id":   r.payload.get("source_id", ""),
                    "collection":  best_collection,
                    "chunk_index": r.payload.get("chunk_index", 0),
                }
                for r in source_points_sorted
                if not user_groups or check_access(
                    user_groups,
                    r.payload.get("autorises", []),
                    r.payload.get("interdits", [])
                )
            ]
            other_chunks = [c for c in chunks if c["source"] != best_source]
            chunks = source_chunks + other_chunks[:3]
            idx_str = f"{idx_min}-{idx_max}" if best_chunk_index is not None else "?"
            logger.info(
                f"Contexte étendu : {len(source_chunks)} chunks de '{best_source}'"
                f" (idx {idx_str}) dans '{best_collection}'"
            )

        return chunks
    except Exception as e:
        logger.warning(f"Qdrant non disponible ou collection vide : {e}")
        return []


def build_context(chunks: list[dict]) -> str:
    """Construit le contexte à injecter dans le prompt."""
    if not chunks:
        return "Aucun document disponible."
    parts = []
    for i, chunk in enumerate(chunks, 1):
        filename = chunk['source'].split('/')[-1]
        parts.append(f"→ {filename}\n{chunk['text']}")
    return "\n\n".join(parts)


async def generate_answer(query: str, context: str) -> str:
    """Génère une réponse ancrée sur le contexte via Ollama."""
    prompt_user = f"""Contexte documentaire :
{context}

Question : {query}"""

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            f"{LLM_BASE_URL}/api/chat",
            json={
                "model": LLM_MODEL,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.2},
                "messages": [
                    {"role": "system", "content": get_system_prompt()},
                    {"role": "user", "content": prompt_user}
                ]
            }
        )
        r.raise_for_status()
        return r.json()["message"]["content"]


def verifier_citations(answer: str, chunks: list[dict]) -> list[str]:
    """
    Contrôle déterministe : vérifie que les sources citées existent dans les chunks.
    """
    import re
    sources_reelles = {c["source"] for c in chunks}
    prefixes_reels = {os.path.splitext(s)[0] for s in sources_reelles}
    citees = set(re.findall(r'\[([^\]]{5,100})\]', answer))

    inventees = []
    for citee in citees:
        citee_clean = re.sub(r'^Document\s+\d+\s*:\s*', '', citee).strip()
        if citee_clean in sources_reelles:
            continue
        citee_sans_ext = os.path.splitext(citee_clean)[0]
        if citee_sans_ext in prefixes_reels:
            continue
        if any(citee_clean in s or s in citee_clean for s in sources_reelles):
            continue
        if '.' not in citee_clean and '_' not in citee_clean:
            continue
        inventees.append(citee_clean)

    return sorted(inventees)


async def warmup_judge() -> None:
    """Ping du juge Ollama pour le maintenir chargé en mémoire."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{LLM_BASE_URL}/api/generate",
                json={
                    "model": JUDGE_MODEL,
                    "prompt": "",
                    "keep_alive": JUDGE_KEEP_ALIVE,
                },
            )
    except Exception:
        pass


async def groundedness_check(answer: str, chunks: list[dict]) -> dict:
    """Vérifie que chaque affirmation de la réponse est ancrée dans les chunks."""
    # Contrôle 1 : aucun chunk
    if not chunks:
        return {"ancree": False, "affirmations_non_sourcees": ["Aucun document source récupéré"]}

    # Contrôle 2 : réponse de refus standard
    if len(answer) < 200 and "ne figure pas dans les documents" in answer:
        return {"ancree": True, "affirmations_non_sourcees": []}

    # Contrôle 3 : sources citées inexistantes
    inventees = verifier_citations(answer, chunks)
    if inventees:
        return {
            "ancree": False,
            "affirmations_non_sourcees": [f"Source inexistante citée : {s}" for s in inventees]
        }

    # Contrôle 4 : réponse longue sans citation
    import re
    if len(answer) > 200 and not re.search(r'\[[^\]]+\]', answer):
        return {
            "ancree": False,
            "affirmations_non_sourcees": ["Réponse substantielle sans aucune citation de source"]
        }

    # Groundedness check par juge LLM
    sources_text = "\n".join([
        f"[{c['source']}] {c['text']}" for c in chunks
    ])

    juge_prompt = f"""Tu es un vérificateur de faits strict. Voici les sources documentaires et une réponse générée.

Sources :
{sources_text}

Réponse à vérifier :
{answer}

Instructions :
- Une affirmation est sourcée si elle est directement tirée des sources ou en est une reformulation fidèle.
- Une affirmation est NON sourcée si elle contient un chiffre, une date, un nom ou un fait précis absent des sources.
- Une affirmation est NON sourcée si elle attribue une fonctionnalité ou une action au mauvais sujet : si la source dit que A fait X, la réponse ne peut pas dire que B fait X.
- Si la source documente un outil construit autour d'un produit, la réponse ne peut pas présenter cet outil comme une fonctionnalité native du produit.
- Ne valide pas une affirmation si tu ne la trouves pas dans les sources ou si l'attribution est incorrecte.

Réponds uniquement en JSON : {{"ancree": true ou false, "affirmations_non_sourcees": ["liste des affirmations avec des faits précis absents des sources"]}}"""

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{LLM_BASE_URL}/api/chat",
                json={
                    "model": JUDGE_MODEL,
                    "stream": False,
                    "format": "json",
                    "think": False,
                    "keep_alive": JUDGE_KEEP_ALIVE,
                    "options": {"temperature": 0},
                    "messages": [{"role": "user", "content": juge_prompt}]
                }
            )
            r.raise_for_status()
            result = json.loads(r.json()["message"]["content"])
            return result
    except Exception as e:
        logger.warning(f"Groundedness check échoué : {e}")
        return {"ancree": True, "affirmations_non_sourcees": [], "juge_error": str(e)}


def log_query(user_id: str, query: str, chunks: list[dict], ancree: bool, juge_error: str = ""):
    """Journalise chaque requête pour audit nLPD."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "question_hash": hashlib.sha256(query.encode()).hexdigest()[:16],
        "sources_accessed": list(dict.fromkeys(c["source"] for c in chunks)),
        "ancree": ancree,
    }
    if juge_error:
        entry["juge_error"] = juge_error
        entry["verification"] = "non_effectuee"
    else:
        entry["verification"] = "effectuee"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"Journalisation échouée : {e}")

# ─────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "llm": LLM_BASE_URL, "model": LLM_MODEL}


@app.get("/stats")
async def stats():
    try:
        collections = qdrant.get_collections()
        col_names = [c.name for c in collections.collections]
        count = 0
        if COLLECTION in col_names:
            count = qdrant.count(COLLECTION).count
        count_doc = 0
        if DOCUMENTATION_COLLECTION in col_names:
            count_doc = qdrant.count(DOCUMENTATION_COLLECTION).count
    except Exception as e:
        col_names = []
        count = 0
        count_doc = 0
    return {
        "qdrant_collections": col_names,
        "chunks_documents": count,
        "chunks_documentation": count_doc,
        "llm": LLM_BASE_URL,
        "model": LLM_MODEL,
        "judge_model": JUDGE_MODEL
    }


@app.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalide")

    # Résolution des groupes AD depuis user_id fourni par le client.
    # /query est un endpoint machine à machine (API_TOKEN). L'identité
    # est déclarée par l'appelant : à n'utiliser que depuis des systèmes
    # de confiance internes. Pour les utilisateurs finaux, utiliser /v1.
    if "@" not in request.user_id:
        logger.warning(f"[AUTH] /query user_id '{request.user_id}' invalide (pas d'@), accès refusé")
        raise HTTPException(status_code=403, detail="user_id invalide : format email requis")
    user_groups = get_user_groups(request.user_id)
    if not user_groups:
        logger.error(f"[AUTH] /query user '{request.user_id}' : résolution LDAP échouée, accès refusé")
        raise HTTPException(status_code=403, detail="Résolution des droits impossible")
    logger.info(f"[AUTH] /query user '{request.user_id}' : {len(user_groups)} groupes AD")

    await warmup_judge()
    chunks = await search_qdrant(request.query, user_groups=user_groups)
    context = build_context(chunks)
    answer = await generate_answer(request.query, context)

    # skip_groundedness réservé à ADMIN_TOKEN uniquement.
    skip = request.skip_groundedness and credentials.credentials == ADMIN_TOKEN
    if skip:
        gc_result = {"ancree": True, "affirmations_non_sourcees": []}
    else:
        gc_result = await groundedness_check(answer, chunks)

    log_query(request.user_id, request.query, chunks, gc_result.get("ancree", True), gc_result.get("juge_error", ""))

    if not gc_result.get("ancree", True):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Réponse non ancrée dans les sources",
                "affirmations_non_sourcees": gc_result.get("affirmations_non_sourcees", []),
                "reponse_bloquee": answer
            }
        )

    return QueryResponse(
        answer=answer,
        sources=[{"source": c["source"], "score": round(c["score"], 3)} for c in chunks],
        ancree=gc_result.get("ancree", True),
        affirmations_non_sourcees=gc_result.get("affirmations_non_sourcees", []),
        user_id=request.user_id
    )


# ─────────────────────────────────────────
# Endpoint compatible OpenAI /v1/chat/completions
# ─────────────────────────────────────────

class OpenAIMessage(BaseModel):
    role: str
    content: str

class OpenAIChatRequest(BaseModel):
    model: str = "rag-api"
    messages: list[OpenAIMessage]
    stream: bool = False
    user: str = "anonymous"

class OpenAIChoice(BaseModel):
    index: int = 0
    message: OpenAIMessage
    finish_reason: str = "stop"

class OpenAIUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class OpenAIChatResponse(BaseModel):
    id: str = "rag-api-response"
    object: str = "chat.completion"
    model: str = "rag-api"
    choices: list[OpenAIChoice]
    usage: OpenAIUsage = OpenAIUsage()


@app.get("/v1/models")
async def list_models(
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalide")
    return {
        "object": "list",
        "data": [{"id": "rag-api", "object": "model", "owned_by": "doit4everyone"}]
    }


@app.post("/v1/chat/completions")
async def openai_chat_completions(
    raw_request: Request,
    request: OpenAIChatRequest,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Endpoint compatible OpenAI pour Open WebUI et autres clients.
    Extrait la dernière question utilisateur et la passe au pipeline RAG complet.
    """
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalide")

    owui_user  = raw_request.headers.get("X-Forwarded-User", "")
    owui_email = raw_request.headers.get("X-Forwarded-Email", "")
    owui_token = raw_request.headers.get("Authorization", "")
    owui_user2  = raw_request.headers.get("X-OpenWebUI-User-Name", "")
    owui_email2 = raw_request.headers.get("X-OpenWebUI-User-Email", "")
    owui_id     = raw_request.headers.get("X-OpenWebUI-User-Id", "")

    user_query = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_query = msg.content
            break

    if not user_query:
        raise HTTPException(status_code=400, detail="Aucun message utilisateur trouvé")

    owui_email2 = raw_request.headers.get("X-OpenWebUI-User-Email", "")
    if not owui_email2:
        logger.warning("[AUTH] /v1 : aucun email utilisateur, accès refusé")
        raise HTTPException(status_code=403, detail="Identité utilisateur manquante")
    user_groups = get_user_groups(owui_email2)
    if user_groups:
        logger.info(f"[AUTH] /v1 user '{owui_email2}' : {len(user_groups)} groupes AD")
    else:
        logger.error(f"[AUTH] /v1 user '{owui_email2}' : résolution LDAP échouée ou aucun groupe, accès refusé")
        raise HTTPException(status_code=403, detail="Résolution des droits impossible")

    await warmup_judge()
    chunks = await search_qdrant(user_query, user_groups=user_groups)
    context = build_context(chunks)
    answer = await generate_answer(user_query, context)
    gc_result = await groundedness_check(answer, chunks)
    log_query(owui_email2, user_query, chunks, gc_result.get("ancree", True), gc_result.get("juge_error", ""))

    return OpenAIChatResponse(
        choices=[OpenAIChoice(
            message=OpenAIMessage(role="assistant", content=answer)
        )]
    )


# ─────────────────────────────────────────
# Endpoint d'administration : synchronisation corpus
# ─────────────────────────────────────────

@app.post("/admin/sync")
async def admin_sync(
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Déclenche la synchronisation complète du corpus :
      1. indexer.py : indexe les fichiers nouveaux ou modifiés
      2. acl_resolver.py : met à jour les autorises[] dans Qdrant
    """
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin invalide")

    if _sync_lock.locked():
        raise HTTPException(
            status_code=409,
            detail="Synchronisation déjà en cours. Réessayer dans quelques minutes."
        )

    async with _sync_lock:

        rapport = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "indexer": {},
            "acl_resolver": {},
            "quarantine": [],
            "errors": []
        }

        venv_python = os.getenv("SYNC_PYTHON", "python3")

        # ── Étape 1 : indexer.py ─────────────────────────────────────────
        indexer_script = f"{SYNC_SCRIPTS_DIR}/indexer.py"
        try:
            logger.info("[SYNC] Lancement de indexer.py")
            result = await asyncio.to_thread(
                subprocess.run,
                [venv_python, indexer_script,
                 "--corpus", SMB_MOUNT,
                 "--rapport", "/var/log/rag/rapport_indexer.json"],
                capture_output=True,
                text=True,
                timeout=int(os.getenv("SYNC_TIMEOUT_INDEXER", "600")),
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": os.environ.get("HOME", ""),
                    "LANG": os.environ.get("LANG", "C.UTF-8"),
                    "PYTHONIOENCODING": "utf-8",
                    "OLLAMA_URL": EMBED_BASE_URL,
                    "EMBED_MODEL": EMBED_MODEL,
                    "QDRANT_URL": QDRANT_HOST,
                    "QDRANT_COLLECTION": COLLECTION,
                    "ORG_OWNER": ORG_NAME,
                    "CHUNK_SIZE": os.environ.get("CHUNK_SIZE", "150"),
                    "CHUNK_OVERLAP": os.environ.get("CHUNK_OVERLAP", "20"),
                    # Variables de routage des collections
                    "DOCUMENTATION_COLLECTION": DOCUMENTATION_COLLECTION,
                    "DOCUMENTATION_PATHS": ",".join(DOCUMENTATION_PATHS),
                    "MIN_CHUNK_WORDS": os.environ.get("MIN_CHUNK_WORDS", "8"),
                }
            )
            rapport["indexer"]["returncode"] = result.returncode
            if result.returncode != 0:
                rapport["errors"].append(f"indexer.py a retourné code {result.returncode}")
                logger.error(f"[SYNC] indexer.py erreur : {result.stderr[-200:]}")
            else:
                logger.info("[SYNC] indexer.py terminé avec succès")
                try:
                    with open("/var/log/rag/rapport_indexer.json", "r") as rf:
                        r_data = json.load(rf)
                    for doc in r_data.get("documents", []):
                        if doc.get("statut") == "quarantaine":
                            rapport["quarantine"].append(doc["fichier"])
                except Exception as e:
                    logger.warning(f"[SYNC] Rapport indexer illisible : {e}")

        except subprocess.TimeoutExpired:
            msg = "indexer.py timeout (>10 min)"
            rapport["errors"].append(msg)
            logger.error(f"[SYNC] {msg}")
        except Exception as e:
            msg = f"indexer.py exception : {e}"
            rapport["errors"].append(msg)
            logger.error(f"[SYNC] {msg}")

        # ── Étape 2 : acl_resolver.py ────────────────────────────────────
        resolver_script = f"{SYNC_SCRIPTS_DIR}/acl_resolver.py"
        try:
            logger.info("[SYNC] Lancement de acl_resolver.py")
            result = await asyncio.to_thread(
                subprocess.run,
                [venv_python, resolver_script,
                 "--share", SMB_SHARE,
                 "--mount", SMB_MOUNT,
                 "--rapport", "/var/log/rag/rapport_acl.json"],
                capture_output=True,
                text=True,
                timeout=int(os.getenv("SYNC_TIMEOUT_ACL", "300")),
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": os.environ.get("HOME", ""),
                    "LANG": os.environ.get("LANG", "C.UTF-8"),
                    "PYTHONIOENCODING": "utf-8",
                    "SMB_USER": SMB_USER,
                    "SMB_PASSWORD": SMB_PASSWORD,
                    "SMB_DOMAIN": SMB_DOMAIN,
                    "QDRANT_URL": QDRANT_HOST,
                    "QDRANT_COLLECTION": COLLECTION,
                    # Variables de routage des collections
                    "DOCUMENTATION_COLLECTION": DOCUMENTATION_COLLECTION,
                    "DOCUMENTATION_PATHS": ",".join(DOCUMENTATION_PATHS),
                }
            )
            rapport["acl_resolver"]["returncode"] = result.returncode
            if result.returncode != 0:
                rapport["errors"].append(f"acl_resolver.py a retourné code {result.returncode}")
                logger.error(f"[SYNC] acl_resolver.py erreur : {result.stderr[-200:]}")
            else:
                logger.info("[SYNC] acl_resolver.py terminé avec succès")
                try:
                    with open("/var/log/rag/rapport_acl.json", "r") as rf:
                        r_data = json.load(rf)
                    for doc in r_data.get("documents", []):
                        if doc.get("statut") in ("non_indexé", "acl_illisible"):
                            rapport["quarantine"].append(doc.get("fichier", doc.get("source_name", "")))
                except Exception as e:
                    logger.warning(f"[SYNC] Rapport acl_resolver illisible : {e}")

        except subprocess.TimeoutExpired:
            msg = "acl_resolver.py timeout (>5 min)"
            rapport["errors"].append(msg)
            logger.error(f"[SYNC] {msg}")
        except Exception as e:
            msg = f"acl_resolver.py exception : {e}"
            rapport["errors"].append(msg)
            logger.error(f"[SYNC] {msg}")

        # ── Résumé ────────────────────────────────────────────────────────
        rapport["success"] = len(rapport["errors"]) == 0
        rapport["quarantine_count"] = len(rapport["quarantine"])

        logger.info(
            f"[SYNC] Terminé : success={rapport['success']}, "
            f"quarantine={rapport['quarantine_count']}, "
            f"errors={len(rapport['errors'])}"
        )

        if rapport["success"]:
            build_bm25_index()

        return rapport
