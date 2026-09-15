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
# Si une passe est déjà en cours, la requête suivante retourne 409
_sync_lock = asyncio.Lock()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://<IP-HOTE-OLLAMA>:11434")
LLM_MODEL    = os.getenv("LLM_MODEL", "qwen2.5:14b")
JUDGE_MODEL  = os.getenv("JUDGE_MODEL", "qwen3:4b")
# Durée de rétention du juge en mémoire Ollama après chaque appel.
# Format Ollama : "5m", "10m", "1h", "-1" (indéfiniment).
# -1 exige assez de RAM/VRAM pour deux modèles simultanés.
# 2h couvre une session de travail typique sans rechargement entre
# deux questions espacées. qwen3:4b pèse ~2,5 Go, le cumul avec
# qwen2.5:14b (~9 Go) tient en RAM système sur LABO-G9.
JUDGE_KEEP_ALIVE = os.getenv("JUDGE_KEEP_ALIVE", "2h")
QDRANT_HOST  = os.getenv("QDRANT_HOST", "http://qdrant:6333")
COLLECTION   = os.getenv("QDRANT_COLLECTION", "documents")
LOG_FILE     = os.getenv("LOG_FILE", "/var/log/rag/rag-queries.jsonl")
TOP_K              = int(os.getenv("TOP_K", "12"))
EMBED_MODEL        = os.getenv("EMBED_MODEL", "nomic-embed-text")
# URL du service d'embedding. Distincte de LLM_BASE_URL car la génération peut
# être servie par vLLM (port 8000) alors que les embeddings restent sur Ollama
# (port 11434). Si EMBED_BASE_URL n'est pas défini, on retombe sur LLM_BASE_URL.
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
# Modèles de données
# ─────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    user_id: str = "anonymous"
    skip_groundedness: bool = False  # Désactiver le check sur CPU si trop lent

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
    """Génère un embedding via le service d'embedding (EMBED_BASE_URL, modèle EMBED_MODEL)."""
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{EMBED_BASE_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text}
        )
        r.raise_for_status()
        return r.json()["embedding"]


async def search_qdrant(query: str, top_k: int = TOP_K, user_groups: list[str] = None) -> list[dict]:
    """
    Recherche les chunks les plus proches dans Qdrant.

    Si user_groups est fourni, filtre sur le champ autorisés[] :
    seuls les chunks accessibles à l'utilisateur sont retournés.
    C'est le cloisonnement réel basé sur les ACL NTFS.

    Si user_groups est None ou vide, aucun filtre d'accès n'est appliqué
    (mode dégradé, à éviter en production).

    Si le meilleur résultat dépasse CONTEXT_THRESHOLD, récupère tous les chunks
    du même document pour garantir un contexte complet.
    """
    try:
        embedding = await get_embedding(query)

        # Construire le filtre d'accès si des groupes sont fournis
        query_filter = None
        if user_groups:
            query_filter = Filter(must=[
                FieldCondition(
                    key="autorises",
                    match=MatchAny(any=user_groups)
                )
            ])

        results = qdrant.query_points(
            collection_name=COLLECTION,
            query=embedding,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True
        ).points

        chunks = []
        for r in results:
            # Vérifier les interdits (DENY NTFS prioritaires sur ALLOW)
            interdits = r.payload.get("interdits", [])
            if interdits and user_groups:
                if not check_access(user_groups, r.payload.get("autorises", []), interdits):
                    continue
            chunks.append({
                "score": r.score,
                "text": r.payload.get("text", ""),
                "source": r.payload.get("source", "inconnu"),
                "source_id": r.payload.get("source_id", ""),
            })

        # Si le meilleur chunk dépasse le seuil, récupérer TOUS les chunks
        # du même document via scroll (avec le même filtre d'accès)
        if chunks and chunks[0]["score"] >= CONTEXT_THRESHOLD:
            best_source = chunks[0]["source"]

            scroll_filter_conditions = [
                FieldCondition(key="source", match=MatchValue(value=best_source))
            ]
            if user_groups:
                scroll_filter_conditions.append(
                    FieldCondition(key="autorises", match=MatchAny(any=user_groups))
                )

            source_points = qdrant.scroll(
                collection_name=COLLECTION,
                scroll_filter=Filter(must=scroll_filter_conditions),
                limit=MAX_CONTEXT_CHUNKS,
                with_payload=True
            )[0]
            source_chunks = [
                {
                    "score": 1.0,
                    "text": r.payload.get("text", ""),
                    "source": r.payload.get("source", "inconnu"),
                    "source_id": r.payload.get("source_id", ""),
                }
                for r in source_points
                # Appliquer check_access sur chaque chunk du scroll :
                # le filtre Qdrant couvre les ALLOW mais pas les DENY explicites.
                # Sans ce contrôle, un utilisateur visé par un DENY verrait
                # le document dès que son score dépasse CONTEXT_THRESHOLD.
                if not user_groups or check_access(
                    user_groups,
                    r.payload.get("autorises", []),
                    r.payload.get("interdits", [])
                )
            ]
            other_chunks = [c for c in chunks if c["source"] != best_source]
            chunks = source_chunks + other_chunks[:3]
            logger.info(f"Contexte étendu : {len(source_chunks)} chunks de '{best_source}' (scroll)")

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
        # Le symbole → introduit le nom du fichier à citer entre crochets
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
                "options": {"temperature": 0.1},
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

    Le modèle peut citer de deux façons :
    - Avec extension complète : [21_Contrat_Maintenance_Baumont_Industries.docx]
    - Sans extension (troncature) : [21_Contrat_Maintenance_Baumont_Industries]

    Pour chaque citation détectée, on vérifie qu'elle correspond à au moins
    une source réelle (par correspondance exacte ou par préfixe sans extension).
    Seules les citations qui ne correspondent à aucune source réelle sont retournées.
    """
    import re
    sources_reelles = {c["source"] for c in chunks}
    # Préfixes sans extension pour la correspondance souple
    prefixes_reels = {os.path.splitext(s)[0] for s in sources_reelles}

    # Capturer tout ce qui est entre crochets (format large)
    citees = set(re.findall(r'\[([^\]]{5,100})\]', answer))

    inventees = []
    for citee in citees:
        # Nettoyer les préfixes "Document N :" résiduels (format obsolète).
        # Le format actuel de build_context() est "→ filename" ; la regex
        # est conservée pour rétrocompatibilité avec d'anciens chunks indexés.
        citee_clean = re.sub(r'^Document\s+\d+\s*:\s*', '', citee).strip()
        # Correspondance exacte
        if citee_clean in sources_reelles:
            continue
        # Correspondance sans extension
        citee_sans_ext = os.path.splitext(citee_clean)[0]
        if citee_sans_ext in prefixes_reels:
            continue
        # Correspondance partielle : la citation est un sous-ensemble d'une source réelle
        if any(citee_clean in s or s in citee_clean for s in sources_reelles):
            continue
        # Vérifier que ça ressemble à un nom de fichier (contient un point ou underscore)
        # pour éviter de signaler des crochets de mise en forme normaux
        if '.' not in citee_clean and '_' not in citee_clean:
            continue
        inventees.append(citee_clean)

    return sorted(inventees)



async def warmup_judge() -> None:
    """Ping du juge Ollama avec 0 token pour le maintenir chargé en mémoire.
    Appelé au début de chaque requête RAG, avant la génération, pour que le
    rechargement éventuel se fasse en parallèle plutôt qu'à la fin.
    L'échec est ignoré silencieusement : si le ping échoue, le vrai appel
    du juge tentera quand même de charger le modèle."""
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
        pass  # ignoré : le vrai appel du juge gère ses propres erreurs


async def groundedness_check(answer: str, chunks: list[dict]) -> dict:
    """
    Vérifie que chaque affirmation de la réponse est ancrée dans les chunks.
    Retourne {"ancree": bool, "affirmations_non_sourcees": list}
    """
    # Contrôle déterministe 1 : aucun chunk récupéré
    if not chunks:
        return {"ancree": False, "affirmations_non_sourcees": ["Aucun document source récupéré"]}

    # Contrôle déterministe 2 : réponse de refus standard (courte, < 200 caractères)
    # Un refus réel est une réponse courte. Une réponse longue qui contient
    # cette phrase quelque part n'est pas un refus : on continue les contrôles.
    if len(answer) < 200 and "ne figure pas dans les documents" in answer:
        return {"ancree": True, "affirmations_non_sourcees": []}

    # Contrôle déterministe 3 : sources citées inexistantes (cas Baumont)
    import re
    inventees = verifier_citations(answer, chunks)
    if inventees:
        return {
            "ancree": False,
            "affirmations_non_sourcees": [f"Source inexistante citée : {s}" for s in inventees]
        }

    # Contrôle déterministe 4 : réponse longue sans aucune citation
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
        # En cas d'échec du juge, on laisse passer pour ne pas bloquer le service.
        # L'échec est journalisé dans log_query via juge_error pour audit ultérieur.
        return {"ancree": True, "affirmations_non_sourcees": [], "juge_error": str(e)}


def log_query(user_id: str, query: str, chunks: list[dict], ancree: bool, juge_error: str = ""):
    """Journalise chaque requête pour audit nLPD."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "question_hash": hashlib.sha256(query.encode()).hexdigest()[:16],
        "sources_accessed": [c["source"] for c in chunks],
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
    except Exception as e:
        col_names = []
        count = 0
    return {
        "qdrant_collections": col_names,
        "chunks_indexed": count,
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

    # 1. Résoudre les groupes AD de l'utilisateur (cloisonnement ACL)
    # Pour /query, l'identité vient du champ user_id de la requête
    user_groups = get_user_groups(request.user_id) if "@" in request.user_id else []
    if user_groups:
        logger.info(f"[AUTH] /query user '{request.user_id}' : {len(user_groups)} groupes AD")
    else:
        logger.warning(f"[AUTH] /query user '{request.user_id}' : aucun groupe AD, accès non filtré")

    # 2. Recherche documentaire avec filtre d'accès
    # Ping du juge en amont pour qu'il soit chargé quand on en a besoin
    await warmup_judge()
    chunks = await search_qdrant(request.query, user_groups=user_groups)

    # 2. Construction du contexte
    context = build_context(chunks)

    # 3. Génération de la réponse
    answer = await generate_answer(request.query, context)

    # 4. Groundedness check
    if request.skip_groundedness:
        gc_result = {"ancree": True, "affirmations_non_sourcees": []}
    else:
        gc_result = await groundedness_check(answer, chunks)

    # 5. Journalisation nLPD
    log_query(request.user_id, request.query, chunks, gc_result.get("ancree", True), gc_result.get("juge_error", ""))

    # 6. Si hallucination détectée : bloquer la réponse
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
# Permet à Open WebUI et tout client OpenAI de consommer la RAG API
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
    """Endpoint compatible OpenAI : liste des modèles disponibles."""
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

    # Log des headers pour identifier l'utilisateur Open WebUI
    # Temporaire : permet de comprendre ce qu'Open WebUI transmet
    owui_user = raw_request.headers.get("X-Forwarded-User", "")
    owui_email = raw_request.headers.get("X-Forwarded-Email", "")
    owui_token = raw_request.headers.get("Authorization", "")
    owui_user2 = raw_request.headers.get("X-OpenWebUI-User-Name", "")
    owui_email2 = raw_request.headers.get("X-OpenWebUI-User-Email", "")
    owui_id = raw_request.headers.get("X-OpenWebUI-User-Id", "")
    logger.info(f"[AUTH] X-Forwarded-User: '{owui_user}' | X-Forwarded-Email: '{owui_email}'")
    logger.info(f"[AUTH] X-OpenWebUI-User-Name: '{owui_user2}' | X-OpenWebUI-User-Email: '{owui_email2}' | Id: '{owui_id}'")
    logger.info(f"[AUTH] Authorization: '{owui_token[:80]}...' " if len(owui_token) > 80 else f"[AUTH] Authorization: '{owui_token}'")
    logger.info(f"[AUTH] request.user: '{request.user}'")
    # Log de tous les headers pour analyse complète
    all_headers = dict(raw_request.headers)
    logger.info(f"[HEADERS] {json.dumps({k: v for k, v in all_headers.items() if k.lower() != 'authorization'})}")

    # Extraire la dernière question utilisateur
    user_query = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_query = msg.content
            break

    if not user_query:
        raise HTTPException(status_code=400, detail="Aucun message utilisateur trouvé")

    # Résoudre les groupes AD depuis l'email Open WebUI (cloisonnement ACL)
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

    # Passer par le pipeline RAG complet avec filtre d'accès
    # Ping du juge en amont pour qu'il soit chargé quand on en a besoin
    await warmup_judge()
    chunks = await search_qdrant(user_query, user_groups=user_groups)
    context = build_context(chunks)
    answer = await generate_answer(user_query, context)
    gc_result = await groundedness_check(answer, chunks)
    log_query(owui_email2, user_query, chunks, gc_result.get("ancree", True), gc_result.get("juge_error", ""))

    # Le résultat ancree: false est journalisé pour audit nLPD.
    # On n'injecte pas d'avertissement dans le texte : Open WebUI duplique
    # le contenu si on modifie la réponse après génération.
    # Le groundedness check dans /query bloque la réponse (HTTP 422).
    # Ici on laisse passer proprement pour l'interface utilisateur.
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

    Sécurité :
      - Authentifié par ADMIN_TOKEN (distinct de API_TOKEN)
      - Tous les paramètres (chemins, partage, credentials) viennent
        du fichier .env, jamais du corps de la requête : pas d'injection
        de commande possible via l'appelant
      - Un verrou global empêche deux synchronisations simultanées :
        si une passe est déjà en cours, retourne HTTP 409

    Retourne un rapport JSON exploitable par n8n pour décider
    si une notification doit être envoyée.
    """
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin invalide")

    # Refuser si une synchronisation est déjà en cours
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

        # Utiliser python3 du conteneur : les dépendances sont dans l'image rag-api.
        # Le venv de l'hôte n'est pas utilisable depuis le conteneur
        # (symlinks cassés vers /usr/bin/python3 absent de l'image slim).
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
                timeout=int(os.getenv("SYNC_TIMEOUT_INDEXER", "600")),  # configurable via SYNC_TIMEOUT_INDEXER
                env={
                    # Environnement restreint : seules les variables nécessaires
                    # à indexer.py sont transmises. Les secrets LDAP, ADMIN_TOKEN
                    # et API_TOKEN ne sont pas propagés aux sous-processus.
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
                }
            )
            rapport["indexer"]["returncode"] = result.returncode
            # stdout/stderr non retournés dans la réponse HTTP : une trace d'exception
            # peut contenir des chemins ou des URLs de connexion. La quarantaine est lue
            # depuis le rapport JSON produit par indexer.py dans /var/log/rag/.
            # Ce parsing sur chaîne fixe est robuste : toute modification cosmétique
            # dans indexer.py ne casse pas la détection.
            if result.returncode != 0:
                rapport["errors"].append(f"indexer.py a retourné code {result.returncode}")
                logger.error(f"[SYNC] indexer.py erreur : {result.stderr[-200:]}")
            else:
                logger.info("[SYNC] indexer.py terminé avec succès")
                # Lire la quarantaine depuis le rapport JSON produit par indexer.py
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
                timeout=int(os.getenv("SYNC_TIMEOUT_ACL", "300")),  # configurable via SYNC_TIMEOUT_ACL
                env={
                    # Environnement restreint : seules les variables nécessaires
                    # à acl_resolver.py sont transmises.
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": os.environ.get("HOME", ""),
                    "LANG": os.environ.get("LANG", "C.UTF-8"),
                    "PYTHONIOENCODING": "utf-8",
                    "SMB_USER": SMB_USER,
                    "SMB_PASSWORD": SMB_PASSWORD,
                    "SMB_DOMAIN": SMB_DOMAIN,
                    "QDRANT_URL": QDRANT_HOST,
                    "QDRANT_COLLECTION": COLLECTION,
                }
            )
            rapport["acl_resolver"]["returncode"] = result.returncode
            # stdout/stderr non retournés (même principe que pour indexer.py).
            if result.returncode != 0:
                rapport["errors"].append(f"acl_resolver.py a retourné code {result.returncode}")
                logger.error(f"[SYNC] acl_resolver.py erreur : {result.stderr[-200:]}")
            else:
                logger.info("[SYNC] acl_resolver.py terminé avec succès")
                # Lire les fichiers non indexés depuis le rapport JSON d'acl_resolver.py
                # (fichiers présents sur le partage mais absents de Qdrant)
                try:
                    with open("/var/log/rag/rapport_acl.json", "r") as rf:
                        r_data = json.load(rf)
                    for doc in r_data.get("documents", []):
                        # non_indexé : ACL lue mais aucun chunk dans Qdrant
                        # acl_illisible : smbcacls a échoué, le chunk garde ses
                        #   anciens autorisés[] et peut donc rester visible à tort
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

        return rapport
