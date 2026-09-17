---
title: "Scripts pipeline RAG local | DoIt4Everyone"
description: "Scripts Python du pipeline RAG local : indexation SMB avec résolution ACL NTFS, RAG API FastAPI avec authentification LDAP Active Directory, journalisation nLPD. Ubuntu Server 26.04, Docker Compose, Qdrant, Ollama."
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

# Scripts pipeline RAG local

[Retour au sommaire](../../) | [Guide de déploiement](../../docs/stack-ia-locale/)

**Statut :** validés en lab sur VM-RAG-LAB, Ubuntu Server 26.04 LTS, septembre 2026. Tests DENY, groupes imbriqués et synchronisation SMB réalisés avec corpus réel.

---

> Ces scripts constituent le pipeline RAG décrit dans le [Guide de déploiement stack IA locale](../../docs/stack-ia-locale/). Ils sont publiés à titre documentaire pour permettre la compréhension et la réimplémentation. Les valeurs sensibles (domaines, IPs, mots de passe) ont été remplacées par des placeholders.
>
> *Rédigés à titre documentaire, sans dépendance à aucun constructeur, revendeur ou intégrateur cité.*

---

## Architecture

```
Utilisateur (authentifié LDAP via Open WebUI)
    ↓
RAG API FastAPI (main.py + auth.py)
    ├→ Qdrant                     → chunks filtrés par ACL NTFS
    └→ Ollama (hôte Windows)      → génération LLM locale
    ↓
Journal nLPD (/var/log/rag/rag-queries.jsonl)
```

Les scripts `indexer.py` et `acl_resolver.py` tournent hors conteneur, sur l'hôte Ubuntu, montés en lecture seule dans le conteneur `rag-api` pour les appels via `/admin/sync`.

---

## Scripts disponibles

| Script | Rôle | Exécution |
|---|---|---|
| `main.py` | RAG API FastAPI : retrieval hybride BM25+vectoriel, génération, journalisation nLPD, endpoint `/admin/sync` | Dans le conteneur `rag-api` |
| `auth.py` | Résolution des groupes Active Directory via LDAP, filtrage des chunks par ACL | Dans le conteneur `rag-api` |
| `indexer.py` | Parcours SMB, extraction de texte, embedding, écriture Qdrant avec payload ACL | Sur l'hôte, via `/admin/sync` ou manuel |
| `acl_resolver.py` | Lecture des ACL NTFS via `smbcacls`, mise à jour `autorises[]` dans Qdrant | Sur l'hôte, via `/admin/sync` ou manuel |

---

## main.py

RAG API FastAPI. Expose quatre endpoints :

- `POST /query` : requête RAG authentifiée par token
- `POST /v1/chat/completions` : endpoint compatible OpenAI, utilisé par Open WebUI
- `GET /health` et `GET /stats` : supervision
- `POST /admin/sync` : lance `indexer.py` et `acl_resolver.py` en sous-processus

Fonctionnalités :

- Retrieval Qdrant avec filtre ACL (`autorises[]` et `interdits[]`)
- Extension de contexte par `chunk_index ± radius` sur le document le mieux classé : les chunks voisins sont récupérés dans l'ordre du document, le chunk pertinent reste dans le contexte. Contrôle ACL appliqué après le scroll
- Retrieval hybride BM25 + vectoriel fusionné par Reciprocal Rank Fusion (RRF) :
  l'index BM25 est construit en mémoire au démarrage depuis Qdrant et reconstruit
  après chaque synchronisation réussie. Chaque chunk BM25 inclut son `chunk_index` pour que l'extension de contexte fonctionne même quand BM25 gagne le RRF. BM25 capture les termes exacts (noms de fichiers,
  acronymes, commandes) là où la recherche vectorielle seule échoue sur les reformulations.
- `TOP_K` configurable (défaut 20), validé en lab pour améliorer le recall sur les gros fichiers .md
- `warmup_judge()` : ping du juge Ollama à chaque requête pour le maintenir chargé en mémoire
- `JUDGE_KEEP_ALIVE` : durée de rétention du juge après chaque appel (défaut `2h`)
- Prompt système : citation du nom exact du fichier entre crochets, jamais `[Document X]`
- Quatre contrôles d'ancrage déterministes (chunks vides, sources inexistantes, réponse sans citation, réponse longue sans citation)
- Juge LLM post-génération (`qwen3:4b`)
- Journalisation nLPD par utilisateur avec hash de la question
- Verrou `asyncio.Lock` contre les synchronisations simultanées
- Environnement restreint transmis aux sous-processus (aucun secret superflu)

**Variables d'environnement requises :**

```bash
LLM_BASE_URL=http://<IP-HOTE-OLLAMA>:11434
LLM_MODEL=qwen2.5:14b
JUDGE_MODEL=qwen3:4b
JUDGE_KEEP_ALIVE=2h       # Rétention du juge en mémoire Ollama après chaque appel.
                          # Format : "5m", "2h", "-1" (indéfiniment).
                          # Passer à -1 une fois le GPU installé.
EMBED_BASE_URL=http://<IP-HOTE-OLLAMA>:11434
EMBED_MODEL=nomic-embed-text
QDRANT_HOST=http://qdrant:6333
QDRANT_COLLECTION=documents
DOCUMENTATION_COLLECTION=documentation  # Collection pour la documentation technique
DOCUMENTATION_PATHS=DOIT4EVERYONE       # Dossiers racine routés vers DOCUMENTATION_COLLECTION
ORG_NAME=<Nom de l'organisation>
API_TOKEN=<token fort>
ADMIN_TOKEN=<token fort distinct>
LOG_FILE=/var/log/rag/rag-queries.jsonl
REPORT_DIR=/var/log/rag
LDAP_HOST=<DC-FQDN>
LDAP_PORT=636
LDAP_USE_TLS=true
LDAP_BASE_DN=DC=domaine,DC=ch
LDAP_BIND_DN=CN=svc-rag,OU=Services,DC=domaine,DC=ch
LDAP_BIND_PWD=<mot-de-passe>
LDAP_DOMAIN=DOMAINE
LDAP_CA_CERT=/etc/ssl/certs/ad-chain.pem
```

---

## auth.py

Résolution des groupes Active Directory via LDAP. Appelé par `main.py` à chaque requête.

Fonctionnalités :

- Extraction de l'identité utilisateur depuis les en-têtes Open WebUI (`X-OpenWebUI-User-Email`)
- Bind LDAP avec TLS : `CERT_REQUIRED` si le certificat CA est présent et non vide, `CERT_NONE` avec avertissement dans les logs si absent
- Résolution récursive des groupes imbriqués via `memberOf`
- Cache TTL configurable (défaut 300 secondes)
- Ajout automatique du compte nominatif dans les groupes résolus (pour les ACE directs)
- Deny par défaut en cas d'erreur LDAP

> **Validation en lab :** la résolution récursive a été testée avec un groupe `GRP-Clients-Niveau2` imbriqué dans `GRP-Clients`. `auth.py` remonte `GRP-Clients` par récursion `memberOf` malgré l'absence d'appartenance directe. Résultats documentés dans le guide §9.4.5.

---

## indexer.py

Indexeur de fichiers SMB. Parcourt un partage monté sur l'hôte et écrit les chunks dans Qdrant avec les métadonnées nécessaires au filtrage.

Fonctionnalités :

- Formats supportés : `.docx`, `.pdf`, `.pptx`, `.txt`, `.md`
  - PDF : extraction page par page via `pdfplumber`. Les PDF scannés sans couche texte produisent un avertissement et tombent en quarantaine.
  - PowerPoint : extraction slide par slide sur les zones de texte. Les tables et SmartArt ne sont pas extraits.
- Chunking par blocs de mots avec recouvrement configurable
- Embedding via Ollama (`nomic-embed-text` par défaut, configurable)
- Vérification de la dimension du modèle contre la collection existante au démarrage
- Indexation incrémentale : comparaison `content_hash` + paramètres d'indexation + `chunker_version`. Les fichiers non modifiés sont ignorés sans appel Ollama. ACL reportées sur les fichiers modifiés.
- IDs de chunks déterministes + upsert : plus de fenêtre d'indisponibilité lors d'une réindexation
- Suppression des chunks excédentaires après réindexation (document raccourci)
- Index de payload Qdrant créés automatiquement : `source` (keyword) + `chunk_index` (integer)
- Détection de l'organisation propriétaire en cinq niveaux : chemin explicite, nom de client dans l'arborescence, pattern « Client : » dans le contenu, mots-clés internes, fallback sur `ORG_OWNER`

> **Sur la détection d'organisation :** `org_name` est une donnée déduite, utile pour la navigation et les facettes de recherche. Elle ne doit pas servir de critère d'accès. Le cloisonnement repose sur `autorises[]`, lu depuis les ACL par `acl_resolver.py`.

- Patterns d'exclusion : `~$*`, `*.tmp`, `*.lnk`, `.DS_Store`, `Thumbs.db`, `desktop.ini`, `DfsrPrivate`, `System Volume Information`, `$RECYCLE.BIN`
- Rapport JSON produit à l'issue de chaque passe

**Utilisation manuelle :**

```bash
cd /root/rag-pipeline
source .venv/bin/activate
# Charger les variables d'environnement
set -a && source /root/rag-stack/.env && set +a
# Indexer
python indexer.py --corpus /mnt/fileservice-root
# Réindexer tous les fichiers en conservant les ACL
python indexer.py --corpus /mnt/fileservice-root --force
# Réindexer depuis zéro (ACL perdues, relancer acl_resolver.py)
python indexer.py --corpus /mnt/fileservice-root --reset
```

**Variables d'environnement :**

```bash
OLLAMA_URL=http://<IP-HOTE-OLLAMA>:11434
QDRANT_URL=http://localhost:6333
ORG_OWNER=<Nom de l'organisation>
EMBED_MODEL=nomic-embed-text
CHUNK_SIZE=150
CHUNK_OVERLAP=20
MIN_CHUNK_WORDS=8         # Seuil minimal en mots pour conserver un chunk (8 préserve les sections courtes des .md)
DOCUMENTATION_COLLECTION=documentation
DOCUMENTATION_PATHS=DOIT4EVERYONE
```

---

## acl_resolver.py

Résolveur d'ACL NTFS. Lit les permissions de chaque fichier via `smbcacls` et met à jour le payload Qdrant.

Fonctionnalités :

- Lecture des ACL via `smbcacls` (paquet `smbclient` requis sur l'hôte)
- Résolution des SID en identifiants `DOMAINE\groupe` exploitables par `auth.py`
- Population de `autorises[]` (ALLOW) et `interdits[]` (DENY explicites)
- Suppression des chunks dont la source a disparu du partage (orphelins)
- Rapport JSON produit à l'issue de chaque passe

> **Validation en lab (DENY explicite) :** `test-client`, membre de `GRP-Clients` (`autorises[]`) mais visé par un ACE de refus nominatif (`interdits[]`), ne voit pas le document interdit, même via le chemin d'extension de contexte. Un compte sans DENY dans le même groupe y accède normalement. Résultats documentés dans le guide §9.4.5.

**Utilisation manuelle :**

```bash
cd /root/rag-pipeline
source .venv/bin/activate
set -a && source /root/rag-stack/.env && set +a
python acl_resolver.py \
    --share //<NOM-FILESERVER>/FileService \
    --mount /mnt/fileservice-root
```

**Variables d'environnement :**

```bash
QDRANT_URL=http://localhost:6333
SMB_USER=svc-rag
SMB_PASSWORD=<mot-de-passe>
SMB_DOMAIN=DOMAINE
```

---

## Dépendances

**Dans le conteneur `rag-api` (`api/requirements.txt`) :**

```
# API
fastapi
uvicorn[standard]
python-dotenv
httpx

# Vector store
qdrant-client

# Retrieval hybride BM25
# Index en mémoire : ~1 Mo pour 1 000 chunks, ~200 Mo pour 50 000 chunks.
# Au-delà de 200 000 chunks, migrer vers Qdrant BM42 (voir §10).
rank-bm25

# Résolution LDAP
ldap3

# Extraction de texte
python-docx
pdfplumber
python-pptx
```

**Sur l'hôte (`/root/rag-pipeline/.venv`) :**

```bash
pip install qdrant-client python-docx pdfplumber python-pptx requests
```

**Paquet système (dans le `Dockerfile`) :**

```
smbclient    # fournit smbcacls pour acl_resolver.py
```

---

## Payload Qdrant

Structure du payload stocké pour chaque chunk :

```json
{
  "text": "...",
  "source": "CLIENTS/ClientA/contrat.docx",
  "source_id": "md5-tronqué",
  "org_name": "ClientA",
  "detection_niveau": 2,
  "embed_model": "nomic-embed-text",
  "chunk_index": 0,
  "chunk_size": 150,
  "chunker_version": 2,
  "content_hash": "3c7db804...",
  "autorises": ["DOMAINE\\GRP-Clients", "DOMAINE\\Admins du domaine"],
  "interdits": [],
  "acl_updated_at": "2026-09-14T10:06:02Z"
}
```

Le champ `autorises` est mis à jour par `acl_resolver.py` indépendamment du contenu. Le champ `interdits` porte les DENY explicites NTFS, prioritaires sur `autorises`.

---

## Licence

Scripts publiés sous licence MIT. Libres de réutilisation, d'adaptation et de redistribution avec attribution.

---

*Validé sur VM-RAG-LAB, Ubuntu Server 26.04 LTS (resolute), Docker 29.7.2, septembre 2026.*

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
