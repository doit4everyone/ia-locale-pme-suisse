---
title: "§3 Docker Compose : stack complète | Guide de déploiement stack IA locale"
description: "Déploiement de Qdrant, n8n, la RAG API FastAPI et Open WebUI via Docker Compose sur VM-RAG-LAB."
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

[Retour au sommaire](index.md) | [Section précédente : §2 Le serveur de modèles : Ollama ou vLLM](section-02-vllm.md) | [Section suivante : §4 Interfaces utilisateur : Onyx CE et Open WebUI](section-04-onyx.md)

**Statut :** validé sur VM-RAG-LAB, septembre 2026. Ce guide déploie la stack complète avec authentification LDAP AD et filtrage ACL NTFS. La Partie 3 (§11 et suivantes) documente les connecteurs Microsoft 365.

---

> **Ce que cette section déploie**
>
> Quatre composants via Docker Compose : Qdrant (vector store), n8n (orchestration des pipelines), la RAG API FastAPI (retrieval, génération, journalisation nLPD) et Open WebUI (interface utilisateur). Onyx CE est déployé séparément en §4 uniquement pour valider le backend Ollama, puis remplacé par cette stack.
>
> La RAG API est le composant central de la stack. Elle reçoit les requêtes utilisateurs via Open WebUI, résout l'identité AD via LDAP, interroge Qdrant avec filtrage ACL NTFS, appelle le LLM et journalise chaque échange pour l'audit nLPD.
>


---

## §3.1 Structure des répertoires

```bash
mkdir -p ~/rag-stack/{qdrant_data,n8n_data,openwebui_data,api,nginx}
mkdir -p /var/log/rag
chmod 750 /var/log/rag
cd ~/rag-stack
```

`/var/log/rag` accueille le journal nLPD et les rapports de synchronisation. Ce répertoire doit exister avant le premier lancement, sinon le montage Docker échoue silencieusement. `nginx` reçoit la configuration du frontal (`rag.conf`, §9.8) ; le certificat et sa clé vont dans `/etc/rag-tls`.

---

## §3.2 Fichier .env

Toutes les variables sensibles sont centralisées dans `.env`. Ne jamais committer ce fichier dans Git : il contient les mots de passe du compte de service et le secret API.

Le fichier complet est fourni en téléchargement dans ce dépôt sous le nom `env.example`. Voici les variables clés à adapter à votre environnement :

```bash
# Serveur de modèles (§2) : bloc A, Ollama (port 11434).
# Avec vLLM : bloc B de env.example (ports 8000 et 8001, LLM_API=openai).
LLM_API=ollama
EMBED_API=ollama
LLM_BASE_URL=http://<IP-SERVEUR-MODELES>:11434
EMBED_BASE_URL=http://<IP-SERVEUR-MODELES>:11434
LLM_MODEL=qwen3:14b
JUDGE_MODEL=qwen3:4b-instruct
EMBED_MODEL=nomic-embed-text
# Le modèle d'embedding doit rester celui qui a servi à indexer :
# en cas de changement de modèle, réindexer avec indexer.py --reset

# Qdrant
QDRANT_HOST=http://qdrant:6333
QDRANT_COLLECTION=documents
# Clé d'API obligatoire (section 15) : openssl rand -hex 32
# Les commandes curl vers Qdrant doivent envoyer l'en-tête « api-key: <clé> ».
QDRANT_API_KEY=changeme-qdrant-api-key
# Deux collections Qdrant : corpus entreprise (documents) et documentation technique (documentation).
# Les dossiers racine listés dans DOCUMENTATION_PATHS vont dans DOCUMENTATION_COLLECTION.
# Ces dossiers doivent être à la racine du partage SMB uniquement.
# Modifier DOCUMENTATION_PATHS exige --reset + resync ACL (voir §5).
DOCUMENTATION_COLLECTION=documentation
DOCUMENTATION_PATHS=DOIT4EVERYONE

# Identité affichée dans le prompt système
ORG_NAME=Axonix SA

# Authentification API (générer avec openssl rand -hex 32)
# Valeur d'exemple, vide, trop courte (< 32 caractères) ou jetons identiques :
# la RAG API refuse de démarrer (§16.6).
API_TOKEN=changeme-api-token
ADMIN_TOKEN=changeme-admin-token
# Identité signée par Open WebUI, vérifiée par la RAG API (§5.6.1)
OWUI_JWT_SECRET=changeme-owui-jwt-secret
# Empreintes HMAC des questions dans le journal (§16.6)
LOG_HMAC_KEY=changeme-log-hmac-key

# Nom de la stack (§9.8) : https://<RAG_FQDN> pour Open WebUI, :5678 pour n8n
RAG_FQDN=<rag.votre-domaine.ch>

# Journalisation et rapports de synchronisation
LOG_FILE=/var/log/rag/rag-queries.jsonl
REPORT_DIR=/var/log/rag

# Annuaire AD (authentification LDAP par les scripts de synchronisation)
LDAP_HOST=DC01.votre-domaine.ch
LDAP_PORT=636
LDAP_USE_TLS=true
LDAP_BASE_DN=DC=votre-domaine,DC=ch
LDAP_BIND_DN=CN=svc-rag,OU=Services,DC=votre-domaine,DC=ch
LDAP_BIND_PWD=REMPLACER
LDAP_DOMAIN=VOTREDOMAINE
LDAP_CA_CERT=/etc/ssl/certs/ad-chain.pem

# Synchronisation corpus (§7)
SYNC_SCRIPTS_DIR=/rag-pipeline
SMB_SHARE=//SERVEUR/FileService
SMB_MOUNT=/mnt/corpus-root
SMB_USER=svc-rag
SMB_PASSWORD=REMPLACER
SMB_DOMAIN=VOTREDOMAINE

# Open WebUI
WEBUI_SECRET_KEY=changeme-openwebui-secret
JWT_EXPIRES_IN=4h

# Paramètres avancés du pipeline
TOP_K=20
# Obsolète depuis v2.17.2 : remplacé par CANDIDATS. Conservé sans effet.
CONTEXT_THRESHOLD=0.01
# Score RRF minimum pour déclencher l'extension de contexte.
# Les scores RRF sont dans [0, ~0.033] avec k=60 et deux listes.
# 0.01 déclenche l'extension sur presque toutes les questions.
# Ne pas dépasser 0.05.
MAX_CONTEXT_CHUNKS=14
# Plafond d'extraits envoyés au modèle quand aucun document n'est en tête.
# Diversité des sources (§8.9) : les valeurs par défaut, validées en lab sur CPU,
# s'appliquent si ces lignes restent commentées.
# CANDIDATS=30                 # candidats retenus par la recherche avant sélection
# PRINCIPAL_MAX=9              # extraits du document principal
# CONTEXT_OTHER_DOCS=6         # documents complémentaires
# EXTRAITS_PAR_COMPLEMENT=4    # extraits consécutifs par document complémentaire (§10.6)
CHUNK_SIZE=150
CHUNK_OVERLAP=20
MIN_CHUNK_WORDS=8
# JUDGE_KEEP_ALIVE=2h       → rétention du juge en mémoire Ollama après chaque appel
#                             Format Ollama : "5m", "2h", "-1" (indéfiniment)
#                             Passer à -1 une fois le GPU installé
```

> **Point critique :** `LLM_BASE_URL` et `EMBED_BASE_URL` doivent utiliser l'adresse réseau du serveur de modèles (ou la passerelle Docker `172.17.0.1` s'il tourne sur la VM elle-même), jamais `localhost`. Depuis l'intérieur d'un conteneur, `localhost` désigne le conteneur lui-même. Pour vérifier l'IP de la passerelle Docker : `ip addr show docker0 | grep "inet "`.
>
> **Docker et variables vides :** avec `- VAR=${VAR}`, si `VAR` est absente du `.env`, Compose transmet une chaîne vide. Le code Python ne voit pas la valeur par défaut définie dans le script. Toute variable listée dans le bloc `environment` du Compose doit donc être définie dans `.env`.

---

## §3.3 RAG API FastAPI

La RAG API est construite localement via Docker. Les trois fichiers suivants forment l'image `rag-api`.

**api/requirements.txt**

Depuis la 2.21.0, le fichier fixe **toutes** les dépendances à la version exacte, relevées par `pip freeze` dans le conteneur validé (§16.8). Début du fichier ; la liste complète est dans le [dépôt](../../scripts/stack-ia-locale/api/requirements.txt) :

```
# Dépendances directes :
#   fastapi, uvicorn[standard], python-dotenv, httpx  : API
#   qdrant-client                                      : index vectoriel
#   rank-bm25                                          : recherche par mots-clés
#   ldap3                                              : groupes Active Directory (auth.py)
#   msal                                               : Entra ID, Partie 3 (auth.py, teams.py)
#   python-docx, pdfplumber, python-pptx               : extraction de texte (indexer.py)
#   PyJWT                                              : identité signée par Open WebUI (main.py),
#                                                        installé aussi comme dépendance de msal
# Les autres lignes sont leurs dépendances, figées elles aussi.
...
fastapi==0.143.2
...
```

L'index BM25 tient en mémoire : environ 1 Mo pour 1 000 chunks, 200 Mo pour 50 000 chunks. Au-delà de 200 000 chunks, migrer vers Qdrant BM42 (sparse vectors, voir §10).

`ldap3` est requis par `auth.py` pour la résolution des groupes Active Directory. `python-docx`, `pdfplumber` et `python-pptx` sont requis par `indexer.py`, qui tourne dans ce même conteneur via `/admin/sync` et qui indexe les fichiers `.docx`, `.pdf`, `.pptx`, `.txt` et `.md`. `rank-bm25` est requis par `main.py` pour le retrieval hybride BM25 : un index de recherche par mots-clés est construit en mémoire au démarrage du conteneur et fusionné avec la recherche vectorielle par Reciprocal Rank Fusion (RRF). L'index BM25 inclut le champ `chunk_index` pour que l'extension de contexte fonctionne même quand un chunk BM25 gagne le classement RRF.

**api/Dockerfile**

```dockerfile
# Image de base figée par empreinte (relevée sur la VM de test le 17 octobre 2026).
# Mettre à jour = revalider (§16.8).
FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce

# smbclient fournit le binaire smbcacls, appelé par acl_resolver.py
# pour lire les ACL NTFS du partage. Sans ce paquet, la synchronisation
# échoue avec FileNotFoundError: smbcacls.
# ca-certificates est requis pour la validation TLS du certificat LDAP.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        smbclient \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Locale UTF-8 : les noms de fichiers du corpus contiennent des accents.
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py auth.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

> **Pourquoi `smbclient` dans l'image RAG API ?** `acl_resolver.py` utilise le binaire `smbcacls` pour lire les ACL NTFS du partage. Ce script tourne dans le conteneur `rag-api` via l'endpoint `/admin/sync` (§7). Sans `smbclient` installé, chaque synchronisation échoue sur `FileNotFoundError: smbcacls`, après avoir correctement traité les embeddings. Le code de retour non nul remonte en fausse alerte dans n8n.

`main.py` et `auth.py` sont fournis en téléchargement dans ce dépôt. Ne pas copier les scripts `indexer.py` et `acl_resolver.py` dans l'image : ils sont montés depuis l'hôte en lecture seule, ce qui permet de les modifier sans reconstruire l'image.

---

## §3.4 docker-compose.yml

**Versions figées.** Les images sont désignées par leur numéro de version, jamais par `latest` ou `main` : un simple `docker compose pull` installerait sinon une autre version que celle validée, et peut changer le comportement de réglages dont dépend la sécurité. Versions validées en lab (octobre 2026), avec l'empreinte exacte des images :

| Service | Image | Empreinte validée |
|---|---|---|
| Qdrant | `qdrant/qdrant:v1.19.0` | `sha256:057ee3a8da769fe7310dd3537b4dc7583bf87a95ce8ac43c0af5a46bc580d1fc` |
| n8n | `n8nio/n8n:2.36.9` | `sha256:a9e2e3c8006ed453238266669ea1274be7136f515abe290a2f75a0ab9044c93d` |
| Open WebUI | `ghcr.io/open-webui/open-webui:v0.11.3` | `sha256:41daa0cf2561a5d4c8d1ff31ee2a98d93ab4d3ac2605cac69366ff6a3374a933` |
| Nginx | `nginx:1.30.6-alpine` | `sha256:970364228b1e4f932abc22d321932816782cca8a20b85a77552a7cfe9acfb3b5` |

Depuis la 2.21.0, le Compose du dépôt désigne chaque image du déploiement standard par son numéro **et** son empreinte (`image: nginx:1.30.6-alpine@sha256:…`) : le contenu ne peut pas changer sous un même numéro. Toute mise à jour d'un composant se revalide : §16.8 en donne un exemple concret et la marche à suivre. Exception : l'image du reranker (§10.8), profil facultatif désactivé par défaut, n'est désignée que par son numéro ; elle n'est pas qualifiée dans cette version.

> **Extrait.** Le bloc ci-dessous reprend les services des Parties 1 et 2 ; les variables de la Partie 3 (Entra ID, Teams, SharePoint, Purview) sont dans le [Compose du dépôt](../../scripts/stack-ia-locale/docker-compose.yml), qui fait foi.

```yaml
services:
  # Reranker (§10.8), OPTIONNEL : désactivé dans la configuration recommandée.
  # Démarrage : docker compose --profile reranker up -d reranker, puis RERANKER_URL=http://reranker:80
  reranker:
    image: ghcr.io/huggingface/text-embeddings-inference:cpu-1.9
    container_name: reranker
    profiles: ["reranker"]
    command: ["--model-id", "Alibaba-NLP/gte-multilingual-reranker-base", "--auto-truncate", "--max-batch-tokens", "4096", "--max-concurrent-requests", "64"]
    mem_limit: 4g
    environment:
      - HF_HUB_OFFLINE=${RERANKER_OFFLINE:-0}
    volumes:
      - ./reranker_data:/data
    restart: unless-stopped


  qdrant:
    image: qdrant/qdrant:v1.19.0
    container_name: qdrant
    ports:
      # Publié sur la boucle locale uniquement. Docker bypass UFW via iptables :
      # le binding 127.0.0.1 est la seule protection fiable contre un accès LAN
      # non authentifié au corpus Qdrant (voir §9.1.2).
      - "127.0.0.1:6333:6333"
    volumes:
      - ./qdrant_data:/qdrant/storage
    environment:
      # Clé d'API obligatoire pour tout accès à Qdrant (section 15)
      - QDRANT__SERVICE__API_KEY=${QDRANT_API_KEY}
      # Snapshots écrits dans le volume, pas dans le conteneur (§3.7)
      - QDRANT__STORAGE__SNAPSHOTS_PATH=/qdrant/storage/snapshots
    restart: unless-stopped

  n8n:
    image: n8nio/n8n:2.36.9@sha256:a9e2e3c8006ed453238266669ea1274be7136f515abe290a2f75a0ab9044c93d
    container_name: n8n
    # Aucun port publié : n8n est joint par Nginx, https://<RAG_FQDN>:5678 (§9.8)
    environment:
      # Pas de N8N_BASIC_AUTH_* : sans effet depuis n8n 1.0. L'accès est protégé
      # par les comptes de n8n : compte propriétaire créé à la première ouverture.
      # Adresse publique de n8n, derrière Nginx (TLS terminé par Nginx, §9.8)
      - N8N_HOST=${RAG_FQDN}
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - N8N_PROXY_HOPS=1
      # N8N_WEBHOOK_URL (n8n 2.30 et suivantes) : WEBHOOK_URL est dépréciée depuis la 2.35
      - N8N_WEBHOOK_URL=https://${RAG_FQDN}:5678/
      # Cookie de session réservé à HTTPS
      - N8N_SECURE_COOKIE=true
      # Aucun paquet communautaire non vérifié (valeur par défaut appelée à changer)
      - N8N_UNVERIFIED_PACKAGES_ENABLED=false
      # Fuseau des déclencheurs planifiés (défaut de n8n : America/New_York)
      - GENERIC_TIMEZONE=Europe/Zurich
      - TZ=Europe/Zurich
    volumes:
      - ./n8n_data:/home/node/.n8n
    restart: unless-stopped

  rag-api:
    build: ./api
    container_name: rag-api
    # Port 8080 non publié sur le LAN : joignable uniquement depuis le réseau
    # Compose interne (Nginx pour /sante, open-webui et n8n via http://rag-api:8080).
    # L'identité de l'utilisateur est en plus signée par Open WebUI (OWUI_JWT_SECRET).
    environment:
      - QDRANT_HOST=${QDRANT_HOST}
      - QDRANT_API_KEY=${QDRANT_API_KEY}
      - QDRANT_COLLECTION=${QDRANT_COLLECTION}
      # LLM_BASE_URL : génération (Ollama : port 11434 ; vLLM : port 8000, §2)
      # EMBED_BASE_URL : embeddings (Ollama : port 11434 ; vLLM : port 8001).
      # Le modèle d'embedding doit être celui qui a servi à indexer, sinon les
      # vecteurs des questions ne correspondent plus à ceux de l'index.
      - LLM_BASE_URL=${LLM_BASE_URL}
      - EMBED_BASE_URL=${EMBED_BASE_URL}
      - EMBED_MODEL=${EMBED_MODEL}
      - LLM_MODEL=${LLM_MODEL}
      - JUDGE_MODEL=${JUDGE_MODEL}
      # Protocole des serveurs de modèles (§2) : « ollama » (défaut) ou « openai »
      # (vLLM). JUDGE_BASE_URL vide = LLM_BASE_URL. VLLM_API_KEY : clé --api-key de vLLM.
      - LLM_API=${LLM_API:-ollama}
      - EMBED_API=${EMBED_API:-ollama}
      - JUDGE_BASE_URL=${JUDGE_BASE_URL:-}
      - VLLM_API_KEY=${VLLM_API_KEY:-}
      - ORG_NAME=${ORG_NAME}
      - API_TOKEN=${API_TOKEN}
      - ADMIN_TOKEN=${ADMIN_TOKEN}
      # Secret de vérification de l'identité signée par Open WebUI (§5.6.1)
      - OWUI_JWT_SECRET=${OWUI_JWT_SECRET}
      - LOG_FILE=${LOG_FILE}
      - REPORT_DIR=${REPORT_DIR}
      - TOP_K=${TOP_K}
      - CONTEXT_THRESHOLD=${CONTEXT_THRESHOLD}
      # Passage des droits incomplet : 1 = suspendre l'origine concernée (§16.5.2)
      - ACL_INCERTAIN_FERME=${ACL_INCERTAIN_FERME:-0}
      - MAX_CONTEXT_CHUNKS=${MAX_CONTEXT_CHUNKS}
      - CANDIDATS=${CANDIDATS:-30}
      - PRINCIPAL_MAX=${PRINCIPAL_MAX:-9}
      - CONTEXT_OTHER_DOCS=${CONTEXT_OTHER_DOCS:-6}
      - EXTRAITS_PAR_COMPLEMENT=${EXTRAITS_PAR_COMPLEMENT:-4}
      - LLM_SEED=${LLM_SEED:-}
      - JUDGE_NUM_GPU=${JUDGE_NUM_GPU:-}
      - EMBED_NUM_GPU=${EMBED_NUM_GPU:-}
      - PROMPT_REGLES_V2=${PROMPT_REGLES_V2:-1}
      - COMPLEMENT_VOISINS=${COMPLEMENT_VOISINS:-1}
      - DOC_COMPLET_MAX=${DOC_COMPLET_MAX:-15}
      - RERANKER_URL=${RERANKER_URL:-}
      - RERANK_CANDIDATS=${RERANK_CANDIDATS:-20}
      - RERANK_MODE=${RERANK_MODE:-fusion}
      - RERANK_RRF_K=${RERANK_RRF_K:-10}
      - RERANK_TIMEOUT=${RERANK_TIMEOUT:-20}
      - SUMMARY_KEEP_ALIVE=${SUMMARY_KEEP_ALIVE:-2m}
      - CHUNK_SIZE=${CHUNK_SIZE}
      - CHUNK_OVERLAP=${CHUNK_OVERLAP}
      - MIN_CHUNK_WORDS=${MIN_CHUNK_WORDS}
      - DOCUMENTATION_COLLECTION=${DOCUMENTATION_COLLECTION}
      - DOCUMENTATION_PATHS=${DOCUMENTATION_PATHS}
      # JUDGE_KEEP_ALIVE : rétention du juge en mémoire Ollama après chaque appel.
      # Format : "5m", "2h", "-1" (indéfiniment). Défaut : 2h.
      - JUDGE_KEEP_ALIVE=${JUDGE_KEEP_ALIVE}
      - LDAP_HOST=${LDAP_HOST}
      - LDAP_PORT=${LDAP_PORT}
      - LDAP_USE_TLS=${LDAP_USE_TLS}
      - LDAP_BASE_DN=${LDAP_BASE_DN}
      - LDAP_BIND_DN=${LDAP_BIND_DN}
      - LDAP_BIND_PWD=${LDAP_BIND_PWD}
      - LDAP_DOMAIN=${LDAP_DOMAIN}
      - LDAP_CA_CERT=${LDAP_CA_CERT}
      - SYNC_SCRIPTS_DIR=${SYNC_SCRIPTS_DIR}
      - SMB_SHARE=${SMB_SHARE}
      - SMB_MOUNT=${SMB_MOUNT}
      - SMB_USER=${SMB_USER}
      - SMB_PASSWORD=${SMB_PASSWORD}
      - SMB_DOMAIN=${SMB_DOMAIN}
    volumes:
      # Scripts indexeur et résolveur ACL, montés en LECTURE SEULE.
      # Le conteneur les exécute via /admin/sync mais ne peut pas les modifier.
      # Les rapports JSON sont écrits dans /var/log/rag (monté en écriture).
      - /root/rag-pipeline:/rag-pipeline:ro
      # Partage SMB monté sur l'hôte (accès aux fichiers pour l'indexeur)
      - /mnt/corpus-root:/mnt/corpus-root:ro
      # Certificat CA du contrôleur de domaine pour la validation TLS LDAP
      - /etc/ssl/certs/ad-chain.pem:/etc/ssl/certs/ad-chain.pem:ro
      # Logs nLPD persistants sur l'hôte (audit, rétention 90 jours)
      - /var/log/rag:/var/log/rag
    depends_on:
      - qdrant
    # « Up (healthy) » dans docker ps quand /health répond
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    restart: unless-stopped

  open-webui:
    image: ghcr.io/open-webui/open-webui:v0.11.3@sha256:41daa0cf2561a5d4c8d1ff31ee2a98d93ab4d3ac2605cac69366ff6a3374a933
    container_name: open-webui
    depends_on:
      - rag-api
    # Aucun port publié : Open WebUI est joint par Nginx, https://<RAG_FQDN> (§9.8)
    environment:
      - OLLAMA_BASE_URL=http://<IP-HOTE-OLLAMA>:11434
      - ENABLE_OLLAMA_API=false
      - WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}
      - ENABLE_FORWARD_USER_INFO_HEADERS=true
      # Identité signée (X-OpenWebUI-User-Jwt), même secret que rag-api (§5.6.1)
      - FORWARD_USER_INFO_HEADER_JWT_SECRET=${OWUI_JWT_SECRET}
      - ENABLE_TITLE_GENERATION=false
      - ENABLE_TAGS_GENERATION=false
      - ENABLE_FOLLOW_UP_GENERATION=false
      - ENABLE_AUTOCOMPLETE_GENERATION=false
      # Pas de vérification de version sur Internet (§16.8)
      - ENABLE_VERSION_UPDATE_CHECK=false
      - JWT_EXPIRES_IN=${JWT_EXPIRES_IN}
    volumes:
      - ./openwebui_data:/app/backend/data
      - /etc/ssl/certs/ad-chain.pem:/etc/ssl/certs/ad-chain.pem:ro
    restart: unless-stopped

  # Frontal TLS (§9.8) : seul service qui publie des ports sur la VM.
  nginx:
    image: nginx:1.30.6-alpine@sha256:970364228b1e4f932abc22d321932816782cca8a20b85a77552a7cfe9acfb3b5
    container_name: nginx
    depends_on:
      - open-webui
      - n8n
    ports:
      - "80:80"
      - "443:443"
      - "5678:5678"
    volumes:
      # <NOM-STACK> remplacé par RAG_FQDN (deploy.sh, ou sed de §9.8.1)
      - ./nginx/rag.conf:/etc/nginx/conf.d/default.conf:ro
      # rag.crt (certificat suivi de l'intermédiaire) et rag.key
      - /etc/rag-tls:/etc/nginx/tls:ro
    security_opt:
      - no-new-privileges:true
    restart: unless-stopped
```

> **Montage en lecture seule pour `/rag-pipeline` :** le conteneur exécute `indexer.py` et `acl_resolver.py` mais ne doit pas pouvoir les modifier. Si un lecteur suit ce guide avec un dépôt Git, ce montage protège les scripts d'une altération accidentelle depuis le conteneur.
>
> **Montage du certificat AD :** `/etc/ssl/certs/ad-chain.pem` doit exister sur l'hôte avant le lancement. En son absence, le montage échoue et le conteneur ne démarre pas. Voir §9.2 pour l'export et l'installation du certificat.
>
> **Certificat de Nginx :** `/etc/rag-tls/rag.crt` et `rag.key` doivent exister avant le lancement, sinon Nginx s'arrête aussitôt et la stack n'est pas joignable. `deploy.sh` génère un certificat auto-signé s'il n'en trouve pas ; à la main, la commande est en §9.8.6.

---

## §3.5 Lancement de la stack

```bash
# Créer le répertoire de logs s'il n'existe pas encore
sudo mkdir -p /var/log/rag
sudo chmod 750 /var/log/rag

# Certificat CA du DC : le fichier doit exister avant docker compose up,
# même vide, sinon le montage Docker bloque le démarrage de rag-api et open-webui.
# auth.py détecte un fichier vide et retombe sur CERT_NONE avec un avertissement.
# Une fois le vrai certificat exporté depuis le DC (§9.2), redémarrer les conteneurs :
#   docker compose restart rag-api open-webui
[ -f /etc/ssl/certs/ad-chain.pem ] || sudo touch /etc/ssl/certs/ad-chain.pem

# Corriger les permissions n8n avant le premier lancement
# (readlink -f : si n8n_data est un lien vers le disque chiffré du §1.5, corriger le vrai dossier)
sudo chown -R 1000:1000 "$(readlink -f ~/rag-stack/n8n_data)"

cd ~/rag-stack

# L'image rag-api est construite localement depuis api/Dockerfile.
# --no-cache est obligatoire si Dockerfile ou requirements.txt ont changé :
# sans lui, Docker réutilise les couches en cache et n'installe pas
# les nouveaux paquets (smbclient, ldap3, python-docx).
# Au premier lancement, --no-cache n'est pas indispensable mais reste
# une bonne habitude pour partir d'une image propre.
docker compose build --no-cache rag-api
docker compose up -d

# Vérification
docker compose ps

# Logs en temps réel
docker compose logs -f

# Arrêt propre
docker compose down
```

> **Point critique :** sans `chown -R 1000:1000` sur `n8n_data`, n8n redémarre en boucle avec `EACCES: permission denied`. Le conteneur n8n tourne sous l'utilisateur `node` (uid 1000), mais le répertoire est créé par root lors du `mkdir`. Si `n8n_data` est un lien (§1.5), `chown -R` appliqué au lien ne change pas le dossier : d'où `readlink -f`. L'adresse annoncée par n8n vient de `RAG_FQDN` dans le `.env` (2.21.0 ; auparavant `N8N_WEBHOOK_URL`).
>
> **Point critique :** si `/etc/ssl/certs/ad-chain.pem` est absent, Docker refuse de démarrer `rag-api` et `open-webui`. Créer un certificat auto-signé temporaire pour débloquer le démarrage, puis remplacer par le vrai certificat du DC (§9.2) avant toute connexion LDAP.

```bash
# Certificat temporaire pour débloquer le démarrage (à remplacer par le vrai)
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /tmp/ad-chain.key \
  -out /etc/ssl/certs/ad-chain.pem \
  -subj "/CN=placeholder"
```

---

## §3.6 Validation de la stack

```bash
# Les valeurs sont lues dans le .env : ni copiées à la main, ni laissées
# dans l'historique du shell.
cd /root/rag-stack
set -a && source .env && set +a

# Qdrant opérationnel (la clé d'API est obligatoire)
curl -s -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections

# Frontal Nginx et RAG API (certificat de l'autorité interne ; auto-signé : -k)
curl --cacert /etc/ssl/certs/ad-chain.pem https://$RAG_FQDN/sante

# n8n health check (n8n ne publie plus de port depuis la 2.21.0)
docker compose exec n8n wget -qO- http://localhost:5678/healthz

# RAG API health
docker compose exec n8n wget -qO- http://rag-api:8080/health

# RAG API stats (vérifie la connectivité Qdrant et la config LLM)
docker compose exec n8n wget -qO- --header="Authorization: Bearer $ADMIN_TOKEN" http://rag-api:8080/stats

# Test requête authentifiée via /query (outil d'administration et de test,
# réservé à ADMIN_TOKEN depuis la 2.21.0 ; API_TOKEN est refusé : 401)
# user_id doit être un email valide, sinon retourne 403
docker run --rm --network rag-stack_default curlimages/curl \
  -s -X POST http://rag-api:8080/query \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Test RAG", "user_id": "admin@votre-domaine.ch"}'

# Test rejet sans token (doit retourner 401)
docker run --rm --network rag-stack_default curlimages/curl \
  -s -X POST http://rag-api:8080/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "user_id": "admin@votre-domaine.ch"}'

# Test rejet user_id sans @ (doit retourner 403)
docker run --rm --network rag-stack_default curlimages/curl \
  -s -X POST http://rag-api:8080/query \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "user_id": "invalide"}'

# Test endpoint OpenAI-Compatible (pour Open WebUI). Sans l'identité signée
# par Open WebUI, la requête est refusée : {"detail":"Identité utilisateur non signée"}.
# Une question réelle se pose dans Open WebUI, ou avec tests-apres-modification.md.
docker run --rm --network rag-stack_default curlimages/curl \
  -s -X POST http://rag-api:8080/v1/chat/completions \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "rag", "messages": [{"role": "user", "content": "Test"}]}'

# Vérifier la création du log nLPD
ls -la /var/log/rag/
```

> **Collection Qdrant vide à ce stade :** si aucun document n'a encore été indexé, `/query` renvoie HTTP 422 (aucun chunk, réponse non ancrée). Le test avec un `user_id` sans `@` retourne 403, pas 401. Pour tester `/query`, utiliser un email d'un compte existant dans l'AD. L'indexation se fait via `indexer.py` (§5) ou via le pipeline n8n (§7).

---

## §3.7 Sauvegarde et restauration Qdrant

**Statut :** validé en lab le 17 octobre 2026 sur une VM Ubuntu 26.04 neuve, déployée par `deploy.sh` (disque de données chiffré, §1.5) : snapshot des deux collections, copie hors du dossier de Qdrant, suppression complète des données, restauration. Les deux collections ont été retrouvées à l'identique (76 et 1 616 extraits), la synchronisation des droits a réussi et le test de cloisonnement a donné les mêmes verdicts qu'avant.

Qdrant stocke les vecteurs et les métadonnées (droits d'accès, empreintes, `org_name`) dans `./qdrant_data/`. Perdre ce dossier sans snapshot oblige à réindexer tout le partage et à resynchroniser les droits. Prendre un snapshot avant toute opération risquée : mise à jour, modification du corpus, changement de modèle d'embedding.

> **Où Qdrant écrit ses snapshots.** Le `docker-compose.yml` du dépôt fixe `QDRANT__STORAGE__SNAPSHOTS_PATH=/qdrant/storage/snapshots` : les snapshots sont écrits dans le volume, donc dans `qdrant_data/snapshots/` sur la VM (sur le disque chiffré avec le §1.5). Sans ce réglage, présent depuis la 2.20.4, Qdrant les écrit dans `/qdrant/snapshots`, **à l'intérieur du conteneur** : ils sont introuvables sur la VM, et disparaissent à la première recréation du conteneur (`docker compose down`, mise à jour). Installation antérieure : récupérer d'abord les snapshots existants (`docker cp qdrant:/qdrant/snapshots/. <dossier-de-destination>/`), puis ajouter la ligne au Compose et lancer `docker compose up -d qdrant`.

### Créer un snapshot

```bash
set -a && source /root/rag-stack/.env && set +a

# Un snapshot par collection
curl -sS -X POST -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections/documents/snapshots; echo
curl -sS -X POST -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections/documentation/snapshots; echo

# Contrôle : les fichiers sont bien sur la VM
ls -lh /root/rag-stack/qdrant_data/snapshots/*/
```

**Attendu :** `"status":"ok"` pour chaque collection, puis un fichier `.snapshot` et son `.checksum` dans `documents/` et dans `documentation/`.

**Copier les snapshots hors du dossier de Qdrant.** La restauration commence par supprimer `qdrant_data/`, snapshots compris : un snapshot laissé à cet endroit ne permet pas de restaurer.

```bash
DEST=<dossier-de-sauvegarde>/qdrant-$(date +%Y%m%d)
mkdir -p "$DEST"
cp -r /root/rag-stack/qdrant_data/snapshots/documents /root/rag-stack/qdrant_data/snapshots/documentation "$DEST"/
ls -lhR "$DEST"
```

Une copie sur le disque de la VM protège d'une fausse manœuvre, pas de la perte de la VM : la copie de référence va sur un autre support. Un snapshot contient le texte de tout le corpus et ses droits d'accès : il se protège comme les données elles-mêmes (chiffré, accès restreint).

### Restaurer un snapshot

```bash
cd /root/rag-stack
set -a && source /root/rag-stack/.env && set +a
COPIE=<dossier-de-sauvegarde>/qdrant-<date>      # copie faite à l'étape précédente
ls -l "$COPIE"/documents "$COPIE"/documentation   # vérifier AVANT de supprimer

# 1. Arrêter la stack et supprimer les données
docker compose down
rm -rf /root/rag-stack/qdrant_data/
ls -la /root/rag-stack/qdrant_data/

# 2. Remettre les snapshots en place, puis démarrer Qdrant seul
mkdir -p /root/rag-stack/qdrant_data/snapshots
cp -r "$COPIE"/documents "$COPIE"/documentation /root/rag-stack/qdrant_data/snapshots/
docker compose up -d qdrant
sleep 5

# 3. Restaurer chaque collection (méthode PUT)
curl -sS -w '\nHTTP %{http_code}\n' -X PUT "http://localhost:6333/collections/documents/snapshots/recover" \
  -H "api-key: $QDRANT_API_KEY" -H "Content-Type: application/json" \
  -d '{"location": "file:///qdrant/storage/snapshots/documents/<nom-du-snapshot-documents>.snapshot"}'

curl -sS -w '\nHTTP %{http_code}\n' -X PUT "http://localhost:6333/collections/documentation/snapshots/recover" \
  -H "api-key: $QDRANT_API_KEY" -H "Content-Type: application/json" \
  -d '{"location": "file:///qdrant/storage/snapshots/documentation/<nom-du-snapshot-documentation>.snapshot"}'

# 4. Contrôler le nombre d'extraits, puis relancer toute la stack
for c in documents documentation; do
  echo -n "$c : "; curl -s -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections/$c | grep -o '"points_count":[0-9]*'; echo
done
docker compose up -d
```

**Attendu :** `{"result":true,"status":"ok",...}` et `HTTP 200` pour chaque collection, puis les mêmes nombres d'extraits qu'au moment du snapshot.

> **`PUT`, pas `POST`.** La restauration passe par la méthode `PUT`. Envoyée en `POST`, elle répond `HTTP 404` sans aucun message : Qdrant ne regarde même pas le fichier. Les versions du guide antérieures à la 2.20.4 indiquaient `POST`, et cette restauration n'a jamais pu fonctionner telle qu'elle était écrite.

> **`qdrant_data` est un lien symbolique** quand le disque chiffré du §1.5 est en place. `rm -rf /root/rag-stack/qdrant_data/`, avec la barre oblique finale, vide alors le dossier cible sur `/srv/rag-donnees` et **conserve le lien** (vérifié en lab) : la suite de la procédure est inchangée. Sans disque chiffré, la commande supprime le dossier, que `mkdir -p` recrée.

> **Après une restauration :** relancer impérativement `acl_resolver.py` pour vérifier que les ACL sont cohérentes avec les permissions actuelles du file server. Un snapshot peut dater de plusieurs heures : des permissions modifiées entre-temps ne seraient pas reflétées.

```bash
# Le port 8080 n'est pas publié. Tester depuis le réseau Compose.
# Le token est lu depuis le .env : ni copié à la main, ni conservé
# dans l'historique du shell. --post-data est obligatoire : /admin/sync
# n'accepte que POST, sans cette option wget envoie un GET (réponse 405).
cd /root/rag-stack
TOKEN=$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2-)
docker compose exec n8n wget -qO- --post-data='' \
  --header="Authorization: Bearer $TOKEN" \
  http://rag-api:8080/admin/sync | python3 -m json.tool
unset TOKEN
```

---

## §3.8 Structure de répertoires finale

```
~/rag-stack/
├── .env                    ← variables sensibles, ne pas committer
├── docker-compose.yml
├── qdrant_data/            ← données Qdrant (persist)
├── n8n_data/               ← workflows n8n (persist)
├── openwebui_data/         ← données Open WebUI (persist)
└── api/
    ├── Dockerfile
    ├── requirements.txt
    ├── main.py             ← RAG API complète
    └── auth.py             ← résolution LDAP

/root/rag-pipeline/         ← scripts d'indexation (montés en lecture seule)
├── indexer.py
├── acl_resolver.py
└── .venv/                  ← environnement Python pour lancement hôte

/var/log/rag/               ← logs nLPD et rapports de synchro
├── rag-queries.jsonl
├── rapport_indexer.json
└── rapport_acl.json

/mnt/corpus-root/           ← partage SMB monté sur l'hôte (lecture seule)
```

---

[Retour au sommaire](index.md) | [Section précédente : §2 Le serveur de modèles : Ollama ou vLLM](section-02-vllm.md) | [Section suivante : §4 Interfaces utilisateur : Onyx CE et Open WebUI](section-04-onyx.md)

---

*Validé sur VM-RAG-LAB, Ubuntu 26.04 LTS (resolute), Docker 29.7.2, août 2026.*
