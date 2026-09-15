"""
indexer.py : indexation de documents locaux vers Qdrant
avec détection automatique de l'organisation propriétaire.

Cascade de détection (par ordre de priorité) :
  1. --org passé en argument CLI
  2. Pattern "Client : X" dans le contenu du document
  3. Nom du dossier parent (si structure hiérarchique par client)
  4. Absence de client détecté → document interne de ORG_OWNER
  5. Quarantaine : document non identifiable, rapport généré

Note sur le niveau 5 :
  La classification LLM a été délibérément exclue de la cascade.
  Un LLM qui hallucine peut attribuer un document à la mauvaise
  organisation, et cette erreur serait stockée comme un fait dans
  le payload, potentiellement utilisée pour le cloisonnement des
  accès. Mieux vaut une quarantaine avec décision humaine qu'une
  attribution incorrecte avec assurance.

Note sur org_name vs autorisés[] :
  org_name est une donnée DÉDUITE par heuristique. Elle est destinée
  au confort de navigation et aux facettes de recherche uniquement.
  Elle ne doit jamais servir de critère d'accès ni entrer dans une
  décision de cloisonnement.

  Le cloisonnement réel reposera sur autorisés[], lu depuis les ACL
  NTFS du système de fichiers (acl_resolver.py, à venir). C'est une
  donnée CONSTATÉE, pas inférée : elle reflète qui a réellement accès,
  indépendamment de l'organisation de l'arborescence.

  La distinction est documentée dans le champ detection_niveau :
  un niveau 1 (--org CLI) est fiable, un niveau 3 (dossier parent)
  doit être vérifié manuellement si utilisé pour de la navigation.

Usage :
  python indexer.py --corpus /chemin/vers/dossier
  python indexer.py --corpus /chemin/vers/dossier --org "Baumont SA"
  python indexer.py --corpus /chemin/vers/dossier --reset
  python indexer.py --corpus /chemin/vers/dossier --rapport /tmp/rapport.json

Variables d'environnement :
  ORG_OWNER   : nom de l'organisation qui déploie la solution
  OLLAMA_URL  : URL Ollama pour les embeddings
  EMBED_MODEL : modèle d'embedding (doit correspondre à main.py)
  QDRANT_URL  : URL Qdrant
  COLLECTION  : nom de la collection Qdrant

Validé sur VM-RAG-LAB, septembre 2026
"""

import argparse
import hashlib
import json
import os
import re
import sys
import httpx
from datetime import datetime, timezone
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)

try:
    from docx import Document as DocxDocument
    import pdfplumber
    from pptx import Presentation
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# ─────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────

OLLAMA_URL    = os.getenv("OLLAMA_URL",        "http://<IP-HOTE-OLLAMA>:11434")
EMBED_MODEL   = os.getenv("EMBED_MODEL",       "nomic-embed-text")
QDRANT_URL    = os.getenv("QDRANT_URL",        "http://localhost:6333")
COLLECTION    = os.getenv("QDRANT_COLLECTION", "documents")
ORG_OWNER     = os.getenv("ORG_OWNER",         "Organisation interne")
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE",    "150"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "20"))
# Nombre minimal de mots pour qu'un chunk soit conservé.
# 15 convient aux .docx structurés ; 8 est nécessaire pour les .md
# et les fichiers .txt à sections courtes.
MIN_CHUNK_WORDS = int(os.getenv("MIN_CHUNK_WORDS", "8"))

# Dimensions par modèle d'embedding
# Si le modèle n'est pas dans ce dictionnaire, l'indexeur s'arrête
# plutôt que de créer une collection avec les mauvaises dimensions.
MODEL_DIMS = {
    "nomic-embed-text": 768,
    "nomic-embed-text:latest": 768,
    "bge-m3": 1024,
    "bge-m3:latest": 1024,
    "multilingual-e5-base": 768,
    "multilingual-e5-large": 1024,
    "intfloat/multilingual-e5-base": 768,
}

# Patterns de détection du client dans le contenu (niveau 2)
# Contraintes appliquées après capture : voir _valider_org()
CLIENT_PATTERNS = [
    r'Client\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ][^\n,]{3,50})',
    r'client\s*:\s*([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ][^\n,]{3,50})',
    r'Entre\s+.+?et\s+([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ][^\n,]{3,50}?)\s*(?:\(client\)|,|$)',
    r'pour le compte de\s+([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ][^\n,]{3,50})',
    r'destiné à\s+([A-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ][^\n,]{3,50})',
]

# Terminaisons légales reconnues
# Une capture sans l'une d'elles ET de plus de 40 caractères est rejetée
LEGAL_SUFFIXES = {
    'sa', 'sarl', 'sàrl', 'ag', 'gmbh', 'snc', 'sas', 'inc',
    'associés', 'associes', 'industries', 'fiduciaire', 'avocats',
    'notaires', 'conseil', 'services', 'group', 'groupe',
}

# Patterns de fichiers à exclure de l'indexation (bruit)
import fnmatch
EXCLUDE_PATTERNS = [
    '~$*', '*.tmp', '*.lnk', '.DS_Store', 'Thumbs.db', 'desktop.ini',
    # Répertoires système à exclure
    'DfsrPrivate',   # Réplication DFS, métadonnées internes Windows
    'System Volume Information',
    '$RECYCLE.BIN',
]

# Mots-clés de documents internes (niveau 4)
# Attention : ces mots-clés doivent être représentatifs de l'organisation
# qui DÉPLOIE la solution, pas de ses clients. Un cabinet RH qui indexe
# des contrats de travail de ses clients ne doit pas lister
# "contrat de travail" ici.
INTERNAL_KEYWORDS = [
    'politique interne',
    'procédure interne',
    'usage interne',
    'plan stratégique',
    'budget prévisionnel',
    'procès-verbal',
    'runbook',
    'politique de sécurité informatique',
    'procédure de déploiement',
    'politique rh',
    'politique des ressources humaines',
    'registre du personnel',
    'registre de',
]

# ─────────────────────────────────────────
# Extraction de texte
# ─────────────────────────────────────────

def extract_docx_structured(path: str) -> list[str]:
    if not DOCX_AVAILABLE:
        return extract_docx_fallback(path)
    try:
        doc = DocxDocument(path)
        blocs = []
        for element in doc.element.body:
            tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            if tag == 'p':
                from docx.oxml.ns import qn
                style = element.find(f'.//{qn("w:pStyle")}')
                style_val = ''
                if style is not None:
                    for attr in style.attrib:
                        if 'val' in attr:
                            style_val = style.attrib[attr]
                            break
                text = ''.join(
                    node.text or '' for node in element.iter()
                    if node.tag.split('}')[-1] == 't'
                ).strip()
                if text:
                    if 'Heading' in style_val or 'heading' in style_val:
                        blocs.append(f"## {text}")
                    else:
                        blocs.append(text)
            elif tag == 'tbl':
                for row in element.iter():
                    if row.tag.split('}')[-1] == 'tr':
                        cells = []
                        for cell in row.iter():
                            if cell.tag.split('}')[-1] == 'tc':
                                cell_text = ''.join(
                                    node.text or '' for node in cell.iter()
                                    if node.tag.split('}')[-1] == 't'
                                ).strip()
                                if cell_text:
                                    cells.append(cell_text)
                        if cells:
                            blocs.append(' | '.join(cells))
        return blocs
    except Exception as e:
        print(f"  Erreur python-docx : {e}, fallback XML")
        return extract_docx_fallback(path)


def extract_docx_fallback(path: str) -> list[str]:
    import zipfile
    try:
        with zipfile.ZipFile(path, 'r') as z:
            with z.open('word/document.xml') as f:
                xml = f.read().decode('utf-8', errors='ignore')
        text = re.sub(r'<[^>]+>', ' ', xml)
        text = re.sub(r'\s+', ' ', text).strip()
        return [text]
    except Exception as e:
        print(f"  Erreur lecture {path} : {e}")
        return []


def extract_pdf(path: str) -> list[str]:
    """Extrait le texte d'un PDF page par page via pdfplumber."""
    blocks = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    blocks.append(text.strip())
        if not blocks:
            print(f"  PDF vide ou scanné (aucun texte extractible) : {path}")
        return blocks
    except Exception as e:
        print(f"  Erreur PDF {path} : {e}")
        return []


def extract_pptx(path: str) -> list[str]:
    """Extrait le texte d'un PowerPoint, une slide par bloc."""
    blocks = []
    try:
        prs = Presentation(path)
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            slide_texts.append(text)
            if slide_texts:
                blocks.append("\n".join(slide_texts))
        if not blocks:
            print(f"  PPTX vide (aucun texte extractible) : {path}")
        return blocks
    except Exception as e:
        print(f"  Erreur PPTX {path} : {e}")
        return []


def extract_txt(path: str) -> list[str]:
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return [p.strip() for p in content.split('\n\n') if p.strip()]
    except Exception as e:
        print(f"  Erreur lecture {path} : {e}")
        return []


def extract_blocks(path: str) -> list[str]:
    ext = os.path.splitext(path)[1].lower()
    if ext == '.docx':
        return extract_docx_structured(path)
    elif ext == '.pdf':
        return extract_pdf(path)
    elif ext == '.pptx':
        return extract_pptx(path)
    elif ext in ('.txt', '.md'):
        return extract_txt(path)
    return []

# ─────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────

def chunk_blocks(blocks: list[str], chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Regroupe les blocs en chunks de taille cohérente.
    Les blocs dépassant chunk_size sont découpés en sous-chunks.
    """
    chunks = []
    current_words = []
    current_section = ""

    for block in blocks:
        if block.startswith("## "):
            if current_words and len(current_words) >= MIN_CHUNK_WORDS:
                chunks.append(' '.join(current_words))
            current_section = block
            current_words = [block]
        else:
            words = block.split()
            # Si le bloc seul dépasse chunk_size, le découper
            if len(words) > chunk_size:
                if current_words and len(current_words) >= MIN_CHUNK_WORDS:
                    chunks.append(' '.join(current_words))
                    current_words = [current_section] if current_section else []
                for j in range(0, len(words), chunk_size - overlap):
                    sub = words[j:j + chunk_size]
                    if len(sub) >= MIN_CHUNK_WORDS:
                        chunks.append(' '.join(([current_section] if current_section else []) + sub))
            elif current_words and len(current_words) + len(words) > chunk_size:
                if len(current_words) >= MIN_CHUNK_WORDS:
                    chunks.append(' '.join(current_words))
                overlap_start = [current_section] if current_section else []
                overlap_words = current_words[-overlap:] if len(current_words) > overlap else current_words
                current_words = overlap_start + overlap_words + words
            else:
                current_words.extend(words)

    if current_words and len(current_words) >= MIN_CHUNK_WORDS:
        chunks.append(' '.join(current_words))

    return chunks

# ─────────────────────────────────────────
# Détection de l'organisation (cascade 5 niveaux, LLM exclu)
# ─────────────────────────────────────────

def detect_org_level1(org_arg: str) -> str | None:
    """Niveau 1 : --org passé en argument CLI."""
    return org_arg.strip() if org_arg and org_arg.strip() else None


def _valider_org(org: str) -> str | None:
    """
    Valide et nettoie une capture de nom d'organisation.
    Rejette les captures qui ressemblent à du bruit :
    - Trop courtes (< 6 caractères)
    - Contiennent des chiffres (ex: "CHF 3...", "2026")
    - Contiennent des termes de contrat de travail
    - Trop longues sans terminaison légale reconnue
    Retourne le nom nettoyé ou None si invalide.
    """
    # Nettoyer les suffixes parasites incluant les qualificatifs entre parenthèses
    while org and org[-1] in '.,;:()':
        org = org[:-1].strip()
    # Retirer les qualificatifs entre parenthèses restants ex: "Beraz Valérie (employée)"
    org = re.sub(r'\s*\([^)]*\)\s*$', '', org).strip()
    # Trop court
    if len(org) < 6:
        return None
    # Contient des chiffres : probablement du bruit narratif
    if re.search(r'\d', org):
        return None
    # Termes qui indiquent un contrat de travail ou du texte narratif
    TERMES_EXCLUS = {
        'durée', 'employeur', 'employée', 'employé',
        'salarié', 'salariée', 'contrat', 'période',
    }
    org_lower = org.lower().strip()
    if org_lower in TERMES_EXCLUS:
        return None
    # Vérifier la terminaison légale
    last_word = org.split()[-1].lower().rstrip('.,;:')
    has_legal_suffix = last_word in LEGAL_SUFFIXES
    # Nom court sans terminaison légale : probablement un nom de personne
    if not has_legal_suffix and len(org) < 25:
        return None
    # Trop long sans terminaison légale reconnue
    if len(org) > 40 and not has_legal_suffix:
        return None
    return org


def detect_org_level2(blocks: list[str]) -> str | None:
    """
    Niveau 2 : pattern "Client : X" dans le contenu.
    Cherche dans les 8 premiers blocs (en-tête du document).
    Priorité sur le dossier parent : le contenu est plus fiable
    que la structure du file server.
    Chaque capture est validée par _valider_org() avant d'être retournée.
    """
    search_text = ' '.join(blocks[:8])
    for pattern in CLIENT_PATTERNS:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            org = _valider_org(match.group(1).strip())
            if org:
                return org
    return None


def detect_org_level3(filepath: str, corpus_root: str) -> str | None:
    """
    Niveau 3 : nom du dossier parent.
    N'est activé que si le dossier parent n'est pas la racine du corpus.
    Attention : ne convient que si la structure est organisée par client
    (ex. /corpus/Baumont_Industries/contrat.docx).
    Si la structure est par type (ex. /corpus/Contrats/baumont.docx),
    ce niveau retournera "Contrats", ce qui est incorrect.
    Le rapport signale le niveau utilisé pour permettre une vérification.
    """
    parent = os.path.dirname(filepath)
    if os.path.abspath(parent) == os.path.abspath(corpus_root):
        return None
    folder_name = os.path.basename(parent)
    org = folder_name.replace('_', ' ').replace('-', ' ').strip()
    if len(org) >= 3:
        return org
    return None


def detect_org_level4(blocks: list[str]) -> str | None:
    """
    Niveau 4 : mots-clés de document interne.
    Si le contenu correspond à un document interne de l'organisation
    qui déploie la solution, retourne ORG_OWNER.

    IMPORTANT : adapter INTERNAL_KEYWORDS à votre contexte métier.
    Un cabinet RH ou une fiduciaire ne doit PAS mettre ici des mots-clés
    génériques comme "contrat de travail" car leurs clients ont aussi
    des contrats de travail. Seuls les documents spécifiques à
    l'organisation déployante (procédures IT, plans stratégiques,
    PV de CA internes) doivent figurer dans cette liste.
    """
    search_text = ' '.join(blocks[:10]).lower()
    for keyword in INTERNAL_KEYWORDS:
        if keyword.lower() in search_text:
            return ORG_OWNER
    return None


def detect_organisation(
    filepath: str,
    corpus_root: str,
    blocks: list[str],
    org_arg: str = ""
) -> tuple[str, str, int]:
    """
    Cascade complète de détection.
    Retourne (org_name, methode, niveau).
    Le niveau 5 (LLM) est exclu : voir note dans l'en-tête du fichier.
    """

    # Niveau 1 : argument CLI
    org = detect_org_level1(org_arg)
    if org:
        return org, "argument CLI (--org)", 1

    # Niveau 2 : pattern client dans le contenu
    org = detect_org_level2(blocks)
    if org:
        return org, "pattern 'Client :' dans le contenu", 2

    # Niveau 3 : dossier parent
    org = detect_org_level3(filepath, corpus_root)
    if org:
        return org, "nom du dossier parent", 3

    # Niveau 4 : document interne
    org = detect_org_level4(blocks)
    if org:
        return org, "mots-clés document interne", 4

    # Niveau 5 : quarantaine
    return "QUARANTAINE", "non identifiable", 5

# ─────────────────────────────────────────
# Embedding
# ─────────────────────────────────────────

def get_embedding(text: str) -> list[float]:
    with httpx.Client(timeout=60) as client:
        r = client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text}
        )
        r.raise_for_status()
        return r.json()["embedding"]

# ─────────────────────────────────────────
# Qdrant
# ─────────────────────────────────────────

def get_embed_dim() -> int:
    """Retourne les dimensions pour EMBED_MODEL, avec vérification."""
    dim = MODEL_DIMS.get(EMBED_MODEL)
    if dim is None:
        # Tenter de détecter automatiquement via un embedding test
        print(f"  Modèle '{EMBED_MODEL}' non dans MODEL_DIMS, détection automatique...")
        try:
            vec = get_embedding("test")
            dim = len(vec)
            print(f"  Dimensions détectées : {dim}")
        except Exception as e:
            print(f"  Erreur détection dimensions : {e}")
            print(f"  Ajouter '{EMBED_MODEL}' dans MODEL_DIMS dans indexer.py")
            sys.exit(1)
    return dim


def init_collection(qdrant: QdrantClient, reset: bool = False) -> int:
    """
    Crée ou vérifie la collection Qdrant.
    Retourne les dimensions de la collection.
    Arrête si la collection existante a des dimensions incompatibles.
    """
    embed_dim = get_embed_dim()
    existing = [c.name for c in qdrant.get_collections().collections]

    if reset and COLLECTION in existing:
        qdrant.delete_collection(COLLECTION)
        print(f"Collection '{COLLECTION}' supprimée.")
        existing = []

    if COLLECTION not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=embed_dim, distance=Distance.COSINE)
        )
        print(f"Collection '{COLLECTION}' créée (dim={embed_dim}, cosine, modèle={EMBED_MODEL}).")
    else:
        # Vérifier la compatibilité des dimensions
        info = qdrant.get_collection(COLLECTION)
        existing_dim = info.config.params.vectors.size
        if existing_dim != embed_dim:
            print(f"ERREUR : collection '{COLLECTION}' existante en {existing_dim} dimensions,")
            print(f"mais '{EMBED_MODEL}' produit {embed_dim} dimensions.")
            print(f"Utilisez --reset pour recréer la collection, ou changez EMBED_MODEL.")
            sys.exit(1)
        print(f"Collection '{COLLECTION}' existante conservée (dim={existing_dim}).")

    return embed_dim

# ─────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────

def delete_existing_chunks(qdrant: QdrantClient, source_name: str, content_hash: str = ""):
    """
    Supprime les chunks existants d'un document avant réindexation.
    Supprime par source_name (chemin relatif) ET par content_hash (contenu).
    Le hash permet de nettoyer les chunks d'un fichier renommé ou déplacé
    dont le contenu est identique.
    """
    try:
        qdrant.delete(
            collection_name=COLLECTION,
            points_selector=Filter(must=[
                FieldCondition(key="source", match=MatchValue(value=source_name))
            ])
        )
    except Exception as e:
        print(f"    Avertissement suppression par chemin : {e}")

    if content_hash:
        try:
            qdrant.delete(
                collection_name=COLLECTION,
                points_selector=Filter(must=[
                    FieldCondition(key="content_hash", match=MatchValue(value=content_hash))
                ])
            )
        except Exception as e:
            print(f"    Avertissement suppression par hash : {e}")


def index_file(
    qdrant: QdrantClient,
    filepath: str,
    corpus_root: str,
    source_name: str,
    org_arg: str = ""
) -> tuple[int, dict]:
    """
    Indexe un fichier. Retourne (nb_chunks, rapport_entry).
    """
    blocks = extract_blocks(filepath)
    if not blocks:
        return 0, {
            "fichier": source_name,
            "statut": "vide",
            "organisation": None,
            "niveau": None,
            "methode": None
        }

    # Hash du contenu brut : identifie le document indépendamment de son chemin
    content_hash = hashlib.sha256(''.join(blocks).encode()).hexdigest()[:32]
    total_chars = sum(len(b) for b in blocks)
    print(f"  Blocs extraits : {len(blocks)} ({total_chars} caractères) [hash: {content_hash[:8]}...]")

    # Détection de l'organisation
    org_name, methode, niveau = detect_organisation(filepath, corpus_root, blocks, org_arg)
    print(f"  Organisation : '{org_name}' (niveau {niveau} : {methode})")

    if niveau == 5:  # Quarantaine
        return 0, {
            "fichier": source_name,
            "statut": "quarantaine",
            "organisation": None,
            "niveau": niveau,
            "methode": methode,
            "action_requise": (
                "Organisation non identifiable automatiquement. "
                "Réindexer avec : python indexer.py --corpus <dossier> --org \"Nom Organisation\""
            )
        }

    # Chunking
    chunks = chunk_blocks(blocks)
    print(f"  Chunks générés : {len(chunks)}")

    # Embedding : générer tous les points avant toute modification de Qdrant
    # Si Ollama échoue en cours de route, les anciens chunks sont préservés
    points = []
    for i, chunk in enumerate(chunks):
        chunk_id = int(hashlib.md5(f"{source_name}_{i}".encode()).hexdigest()[:16], 16) % (2**63)
        print(f"    Embedding chunk {i+1}/{len(chunks)}...", end='\r')
        embedding = get_embedding(chunk)
        points.append(PointStruct(
            id=chunk_id,
            vector=embedding,
            payload={
                "text": chunk,
                "source": source_name,
                "source_id": hashlib.md5(source_name.encode()).hexdigest(),
                "content_hash": content_hash,
                "org_name": org_name,
                "detection_niveau": niveau,
                "detection_methode": methode,
                "embed_model": EMBED_MODEL,
                "chunk_index": i,
                "filepath": filepath,
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }
        ))

    # Tous les embeddings ont réussi : supprimer les anciens chunks puis insérer
    if not points:
        print(f"  → Aucun chunk valide généré après embedding, fichier ignoré.")
        return 0, {
            "fichier": source_name,
            "statut": "vide",
            "organisation": None,
            "niveau": None,
            "methode": None
        }
    delete_existing_chunks(qdrant, source_name, content_hash)
    qdrant.upsert(collection_name=COLLECTION, points=points)
    print(f"  → {len(points)} chunks indexés (org: {org_name})          ")

    return len(points), {
        "fichier": source_name,
        "statut": "indexé",
        "organisation": org_name,
        "niveau": niveau,
        "methode": methode,
        "chunks": len(points)
    }


def index_corpus(corpus_dir: str, reset: bool = False, org_arg: str = "", rapport_path: str = ""):
    if not os.path.isdir(corpus_dir):
        print(f"Erreur : dossier introuvable : {corpus_dir}")
        sys.exit(1)

    print(f"Connexion Qdrant : {QDRANT_URL}")
    qdrant_client = QdrantClient(url=QDRANT_URL)
    init_collection(qdrant_client, reset=reset)

    print(f"Vérification Ollama : {OLLAMA_URL}")
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{OLLAMA_URL}/api/tags")
            models = [m['name'] for m in r.json().get('models', [])]
            if not any(EMBED_MODEL.split(':')[0] in m for m in models):
                print(f"Erreur : modèle d'embedding '{EMBED_MODEL}' non trouvé.")
                sys.exit(1)
            print(f"Modèle d'embedding : {EMBED_MODEL} ✓")
    except Exception as e:
        print(f"Erreur connexion Ollama : {e}")
        sys.exit(1)

    if org_arg:
        print(f"Organisation forcée (niveau 1) : '{org_arg}'")
    print(f"Organisation interne par défaut (niveau 4) : '{ORG_OWNER}'")
    print(f"\nNote : org_name est indexé mais pas encore filtré (attend auth.py)")

    # Découverte récursive des fichiers avec filtrage du bruit
    supported = ('.docx', '.pdf', '.pptx', '.txt', '.md')
    all_files = []
    skipped_noise = []
    for root, dirs, files in os.walk(corpus_dir):
        for f in sorted(files):
            filepath = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            # Exclure les patterns de bruit
            if any(fnmatch.fnmatch(f, pat) for pat in EXCLUDE_PATTERNS):
                skipped_noise.append(f)
                continue
            if ext in supported:
                all_files.append(filepath)
    if skipped_noise:
        print(f"Fichiers bruit exclus : {len(skipped_noise)} ({', '.join(skipped_noise[:5])}{'...' if len(skipped_noise) > 5 else ''})")

    if not all_files:
        print(f"Aucun fichier supporté trouvé dans {corpus_dir}")
        sys.exit(1)

    print(f"\n{len(all_files)} fichiers à indexer :\n")

    rapport = []
    total_chunks = 0

    for i, filepath in enumerate(all_files, 1):
        source_name = os.path.relpath(filepath, corpus_dir)
        print(f"\n  [{i}/{len(all_files)}] {source_name}")
        nb, entry = index_file(qdrant_client, filepath, corpus_dir, source_name, org_arg)
        total_chunks += nb
        rapport.append(entry)

    # Résumé
    count = qdrant_client.count(COLLECTION).count
    indexés = [r for r in rapport if r["statut"] == "indexé"]
    quarantaine = [r for r in rapport if r["statut"] == "quarantaine"]
    vides = [r for r in rapport if r["statut"] == "vide"]

    print(f"\n{'='*60}")
    print(f"RAPPORT D'INDEXATION")
    print(f"{'='*60}")
    print(f"Fichiers traités      : {len(all_files)}")
    print(f"Indexés avec succès   : {len(indexés)}")
    print(f"Fichiers vides        : {len(vides)}")
    print(f"En quarantaine        : {len(quarantaine)}")
    print(f"Chunks indexés        : {total_chunks}")
    print(f"Total chunks Qdrant   : {count}")

    if indexés:
        print(f"\nOrganisations détectées :")
        orgs = {}
        for r in indexés:
            org = r["organisation"]
            orgs[org] = orgs.get(org, 0) + 1
        for org, nb in sorted(orgs.items()):
            print(f"  {nb:3d} fichier(s) → {org}")

        print(f"\nMéthodes de détection :")
        methodes = {}
        for r in indexés:
            m = f"Niveau {r['niveau']} : {r['methode']}"
            methodes[m] = methodes.get(m, 0) + 1
        for m, nb in sorted(methodes.items()):
            print(f"  {nb:3d} fichier(s) → {m}")

    if quarantaine:
        print(f"\n{'!'*60}")
        print(f"DOCUMENTS EN QUARANTAINE ({len(quarantaine)}) :")
        print(f"Action requise : réindexer avec --org")
        print(f"{'!'*60}")
        for r in quarantaine:
            print(f"  {r['fichier']}")

    # Sauvegarder le rapport JSON
    if not rapport_path:
        rapport_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"rapport_indexation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

    with open(rapport_path, 'w', encoding='utf-8') as f:
        json.dump({
            "date": datetime.now(timezone.utc).isoformat(),
            "corpus": corpus_dir,
            "collection": COLLECTION,
            "embed_model": EMBED_MODEL,
            "org_owner": ORG_OWNER,
            "statistiques": {
                "total_fichiers": len(all_files),
                "indexés": len(indexés),
                "quarantaine": len(quarantaine),
                "vides": len(vides),
                "total_chunks": total_chunks
            },
            "documents": rapport
        }, f, ensure_ascii=False, indent=2)
    print(f"\nRapport sauvegardé : {rapport_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Indexeur RAG avec détection automatique d'organisation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  # Corpus plat, détection automatique
  ORG_OWNER="Axonix SA" python indexer.py --corpus /serveur/documents

  # Dossier d'un client spécifique
  python indexer.py --corpus /serveur/Baumont_Industries --org "Baumont Industries SA"

  # Réindexation complète
  python indexer.py --corpus /serveur/documents --reset

  # Rapport dans un dossier dédié
  python indexer.py --corpus /serveur/documents --rapport /var/log/rag/rapport.json
        """
    )
    parser.add_argument("--corpus",   required=True, help="Dossier de documents (récursif)")
    parser.add_argument("--org",      default="",    help="Forcer l'organisation (niveau 1)")
    parser.add_argument("--reset",    action="store_true", help="Vider la collection avant indexation")
    parser.add_argument("--rapport",  default="",    help="Chemin du rapport JSON (défaut : dossier du script)")
    args = parser.parse_args()

    index_corpus(
        args.corpus,
        reset=args.reset,
        org_arg=args.org,
        rapport_path=args.rapport
    )
