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

[Retour au sommaire](index.md) | [Section précédente : §2 vLLM](section-02-vllm.md)

**Statut :** validé sur VM-RAG-LAB, septembre 2026. La RAG API complète (avec authentification OIDC et filtrage ACL) fait l'objet de la Partie 2 : ce guide déploie la version production sans cloisonnement fin, valide pour un corpus homogène.

---

> **Ce que cette section déploie**
>
> Quatre composants via Docker Compose : Qdrant (vector store), n8n (orchestration des pipelines), la RAG API FastAPI (retrieval, génération, journalisation nLPD) et Open WebUI (interface utilisateur). Onyx n'est pas dans cette stack : il dispose de sa propre stack déployée séparément en §4, uniquement pour la phase de validation.
>
> La RAG API est le composant central de la Partie 1. Elle reçoit les requêtes utilisateurs, interroge Qdrant, appelle le LLM et journalise chaque échange. Sans authentification LDAP ni filtrage fin par ACL (Partie 2), elle convient pour un corpus dont tous les utilisateurs peuvent légitimement consulter tous les documents.
>
> **Avertissement rappelé de §0 :** ne pas indexer un partage contenant des données à accès restreint avant d'avoir déployé la Partie 2.

---

## §3.1 Structure des répertoires

```bash
mkdir -p ~/rag-stack/{qdrant_data,n8n_data,openwebui_data,api}
mkdir -p /var/log/rag
chmod 750 /var/log/rag
cd ~/rag-stack
```

`/var/log/rag` accueille le journal nLPD et les rapports de synchronisation. Ce répertoire doit exister avant le premier lancement, sinon le montage Docker échoue silencieusement.

---

## §3.2 Fichier .env

Toutes les variables sensibles sont centralisées dans `.env`. Ne jamais committer ce fichier dans Git : il contient les mots de passe du compte de service et le secret API.

Le fichier complet est fourni en téléchargement dans ce dépôt sous le nom `env.example`. Voici les variables clés à adapter à votre environnement :

```bash
# Génération LLM : Ollama sur LABO-G9 (hôte Windows, port 11434)
LLM_BASE_URL=http://<IP-HOTE-OLLAMA>:11434
LLM_MODEL=qwen2.5:14b
JUDGE_MODEL=qwen3:4b

# Embeddings : identique au service qui a servi à indexer
# En cas de changement de modèle, réindexer avec indexer.py --reset
EMBED_BASE_URL=http://<IP-HOTE-OLLAMA>:11434
EMBED_MODEL=nomic-embed-text

# Qdrant
QDRANT_HOST=http://qdrant:6333
QDRANT_COLLECTION=documents
# Deux collections Qdrant : corpus entreprise (documents) et documentation technique (documentation).
# Les dossiers racine listés dans DOCUMENTATION_PATHS vont dans DOCUMENTATION_COLLECTION.
# Ces dossiers doivent être à la racine du partage SMB uniquement.
# Modifier DOCUMENTATION_PATHS exige --reset + resync ACL (voir §5).
DOCUMENTATION_COLLECTION=documentation
DOCUMENTATION_PATHS=DOIT4EVERYONE

# Identité affichée dans le prompt système
ORG_NAME=Axonix SA

# Authentification API (générer avec openssl rand -hex 32)
API_TOKEN=changeme-api-token
ADMIN_TOKEN=changeme-admin-token

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
SMB_SHARE=//SERVEUR/PartageDocuments
SMB_MOUNT=/mnt/corpus-root
SMB_USER=svc-rag
SMB_PASSWORD=REMPLACER
SMB_DOMAIN=VOTREDOMAINE

# n8n
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=changeme

# Open WebUI
WEBUI_SECRET_KEY=changeme-openwebui-secret
JWT_EXPIRES_IN=4h

# Paramètres avancés du pipeline
TOP_K=20
# 20 améliore le recall sur les gros fichiers .md (100+ chunks). Valeur validée en lab.
CONTEXT_THRESHOLD=0.01
# Score RRF minimum pour déclencher l'extension de contexte.
# Les scores RRF sont dans [0, 0.016] avec k=60. 0.01 déclenche
# l'extension sur presque toutes les questions. Ne pas dépasser 0.05.
MAX_CONTEXT_CHUNKS=14
# Nombre maximum de chunks par extension de contexte.
# 14 validé en lab sur CPU. Augmenter à 15-20 une fois le GPU installé.
CHUNK_SIZE=150
CHUNK_OVERLAP=20
MIN_CHUNK_WORDS=8
# JUDGE_KEEP_ALIVE=2h       → rétention du juge en mémoire Ollama après chaque appel
#                             Format Ollama : "5m", "2h", "-1" (indéfiniment)
#                             Passer à -1 une fois le GPU installé
```

> **Point critique :** `LLM_BASE_URL` et `EMBED_BASE_URL` doivent utiliser l'IP réseau de l'hôte Windows ou la passerelle Docker (`172.17.0.1`), jamais `localhost`. Depuis l'intérieur d'un conteneur, `localhost` désigne le conteneur lui-même. Pour vérifier l'IP de la passerelle Docker : `ip addr show docker0 | grep "inet "`.
>
> **Docker et variables vides :** avec `- VAR=${VAR}`, si `VAR` est absente du `.env`, Compose transmet une chaîne vide. Le code Python ne voit pas la valeur par défaut définie dans le script. Toute variable listée dans le bloc `environment` du Compose doit donc être définie dans `.env`.

---

## §3.3 RAG API FastAPI

La RAG API est construite localement via Docker. Les trois fichiers suivants forment l'image `rag-api`.

**api/requirements.txt**

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
# Au-delà de 200 000 chunks, migrer vers Qdrant BM42 (sparse vectors, voir §10).
rank-bm25

# Résolution LDAP
ldap3

# Extraction de texte
python-docx
pdfplumber
python-pptx
```

`ldap3` est requis par `auth.py` pour la résolution des groupes Active Directory. `python-docx`, `pdfplumber` et `python-pptx` sont requis par `indexer.py`, qui tourne dans ce même conteneur via `/admin/sync` et qui indexe les fichiers `.docx`, `.pdf`, `.pptx`, `.txt` et `.md`. `rank-bm25` est requis par `main.py` pour le retrieval hybride BM25 : un index de recherche par mots-clés est construit en mémoire au démarrage du conteneur et fusionné avec la recherche vectorielle par Reciprocal Rank Fusion (RRF). L'index BM25 inclut le champ `chunk_index` pour que l'extension de contexte fonctionne même quand un chunk BM25 gagne le classement RRF.

**api/Dockerfile**

```dockerfile
FROM python:3.11-slim

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

```yaml
services:

  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    ports:
      # Publié sur la boucle locale uniquement. Docker bypass UFW via iptables :
      # le binding 127.0.0.1 est la seule protection fiable contre un accès LAN
      # non authentifié au corpus Qdrant (voir §9.1).
      - "127.0.0.1:6333:6333"
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
      - WEBHOOK_URL=http://<IP-VM>:5678
      - N8N_SECURE_COOKIE=false
    volumes:
      - ./n8n_data:/home/node/.n8n
    restart: unless-stopped

  rag-api:
    build: ./api
    container_name: rag-api
    # Port 8080 non publié sur le LAN : joignable uniquement depuis le réseau
    # Compose interne (open-webui via http://rag-api:8080, n8n idem).
    # Empêche la falsification de l'en-tête X-OpenWebUI-User-Email depuis le LAN.
    environment:
      - QDRANT_HOST=${QDRANT_HOST}
      - QDRANT_COLLECTION=${QDRANT_COLLECTION}
      # LLM_BASE_URL : génération (Ollama 11434, ou vLLM 8000 sur DGX Spark)
      # EMBED_BASE_URL : embeddings. Doit correspondre au service qui a servi
      # à indexer. Si les deux services diffèrent, définir EMBED_BASE_URL
      # explicitement dans .env, sinon les vecteurs de requête sont incohérents.
      - LLM_BASE_URL=${LLM_BASE_URL}
      - EMBED_BASE_URL=${EMBED_BASE_URL}
      - EMBED_MODEL=${EMBED_MODEL}
      - LLM_MODEL=${LLM_MODEL}
      - JUDGE_MODEL=${JUDGE_MODEL}
      - ORG_NAME=${ORG_NAME}
      - API_TOKEN=${API_TOKEN}
      - ADMIN_TOKEN=${ADMIN_TOKEN}
      - LOG_FILE=${LOG_FILE}
      - REPORT_DIR=${REPORT_DIR}
      - TOP_K=${TOP_K}
      - CONTEXT_THRESHOLD=${CONTEXT_THRESHOLD}
      - MAX_CONTEXT_CHUNKS=${MAX_CONTEXT_CHUNKS}
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
    restart: unless-stopped

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    depends_on:
      - rag-api
    ports:
      - "3001:8080"
    environment:
      - OLLAMA_BASE_URL=http://<IP-HOTE-OLLAMA>:11434
      - WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}
      - ENABLE_FORWARD_USER_INFO_HEADERS=true
      - JWT_EXPIRES_IN=${JWT_EXPIRES_IN}
    volumes:
      - ./openwebui_data:/app/backend/data
      - /etc/ssl/certs/ad-chain.pem:/etc/ssl/certs/ad-chain.pem:ro
    restart: unless-stopped
```

> **Montage en lecture seule pour `/rag-pipeline` :** le conteneur exécute `indexer.py` et `acl_resolver.py` mais ne doit pas pouvoir les modifier. Si un lecteur suit ce guide avec un dépôt Git, ce montage protège les scripts d'une altération accidentelle depuis le conteneur.
>
> **Montage du certificat AD :** `/etc/ssl/certs/ad-chain.pem` doit exister sur l'hôte avant le lancement. En son absence, le montage échoue et le conteneur ne démarre pas. Voir §9.3 pour l'export et l'installation du certificat.

---

## §3.5 Lancement de la stack

```bash
# Créer le répertoire de logs s'il n'existe pas encore
sudo mkdir -p /var/log/rag
sudo chmod 750 /var/log/rag

# Certificat CA du DC : le fichier doit exister avant docker compose up,
# même vide, sinon le montage Docker bloque le démarrage de rag-api et open-webui.
# auth.py détecte un fichier vide et retombe sur CERT_NONE avec un avertissement.
# Une fois le vrai certificat exporté depuis le DC (§9.3), redémarrer les conteneurs :
#   docker compose restart rag-api open-webui
[ -f /etc/ssl/certs/ad-chain.pem ] || sudo touch /etc/ssl/certs/ad-chain.pem

# Corriger les permissions n8n avant le premier lancement
sudo chown -R 1000:1000 ~/rag-stack/n8n_data

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

> **Point critique :** sans `chown -R 1000:1000` sur `n8n_data`, n8n redémarre en boucle avec `EACCES: permission denied`. Le conteneur n8n tourne sous l'utilisateur `node` (uid 1000), mais le répertoire est créé par root lors du `mkdir`.
>
> **Point critique :** si `/etc/ssl/certs/ad-chain.pem` est absent, Docker refuse de démarrer `rag-api` et `open-webui`. Créer un certificat auto-signé temporaire pour débloquer le démarrage, puis remplacer par le vrai certificat du DC (§9.3) avant toute connexion LDAP.

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
# Qdrant opérationnel
curl http://localhost:6333/collections

# n8n health check
curl http://localhost:5678/healthz

# RAG API health
docker compose exec n8n wget -qO- http://rag-api:8080/health

# RAG API stats (vérifie la connectivité Qdrant et la config LLM)
docker compose exec n8n wget -qO- http://rag-api:8080/stats

# Test requête authentifiée via /query (endpoint machine à machine)
# user_id doit être un email valide, sinon retourne 403
docker run --rm --network rag-stack_default curlimages/curl \
  -s -X POST http://rag-api:8080/query \
  -H "Authorization: Bearer changeme-api-token" \
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
  -H "Authorization: Bearer changeme-api-token" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "user_id": "invalide"}'

# Test endpoint OpenAI-Compatible (pour Open WebUI)
docker run --rm --network rag-stack_default curlimages/curl \
  -s -X POST http://rag-api:8080/v1/chat/completions \
  -H "Authorization: Bearer changeme-api-token" \
  -H "Content-Type: application/json" \
  -d '{"model": "rag", "messages": [{"role": "user", "content": "Test"}]}'

# Vérifier la création du log nLPD
ls -la /var/log/rag/
```

> **Collection Qdrant vide à ce stade :** `/query` renvoie une réponse du LLM sans sources tant qu'aucun document n'a été indexé. C'est le comportement attendu. L'indexation se fait via `indexer.py` (§5) ou via le pipeline n8n (§7).

---

## §3.7 Sauvegarde et restauration Qdrant

**Statut :** validé en lab sur VM-RAG-LAB, septembre 2026.

Qdrant stocke les vecteurs et les métadonnées (ACL, hashes, org_name) dans `./qdrant_data/`. Une perte de ce répertoire sans snapshot oblige à relancer une réindexation complète et un resync ACL. Prendre un snapshot avant toute opération risquée (mise à jour, modification du corpus, changement de modèle d'embedding).

### Créer un snapshot

```bash
# Snapshot de la collection documents
curl -X POST http://localhost:6333/collections/documents/snapshots

# Snapshot de la collection documentation
curl -X POST http://localhost:6333/collections/documentation/snapshots

# Lister les snapshots disponibles
curl http://localhost:6333/collections/documents/snapshots
curl http://localhost:6333/collections/documentation/snapshots
```

Les snapshots sont écrits dans `./qdrant_data/snapshots/`. Les copier hors du conteneur pour les conserver :

```bash
cp -r ~/rag-stack/qdrant_data/snapshots/ /backup/qdrant-snapshots-$(date +%Y%m%d)/
```

### Restaurer un snapshot

```bash
# Arrêter la stack
cd ~/rag-stack && docker compose down

# Supprimer les données existantes
rm -rf ~/rag-stack/qdrant_data/

# Redémarrer Qdrant seul
docker compose up -d qdrant
sleep 5

# Restaurer la collection documents depuis le snapshot
curl -X POST "http://localhost:6333/collections/documents/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "file:///qdrant/storage/snapshots/documents/<nom-du-snapshot>.snapshot"}'

# Restaurer la collection documentation
curl -X POST "http://localhost:6333/collections/documentation/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "file:///qdrant/storage/snapshots/documentation/<nom-du-snapshot>.snapshot"}'

# Redémarrer la stack complète
docker compose up -d
```

> **Après une restauration :** relancer impérativement `acl_resolver.py` pour vérifier que les ACL sont cohérentes avec les permissions actuelles du file server. Un snapshot peut dater de plusieurs heures : des permissions modifiées entre-temps ne seraient pas reflétées.

```bash
curl -X POST http://localhost:8080/admin/sync \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
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

[Suite : §4 Interfaces utilisateur](section-04-onyx.md)

---

*Validé sur VM-RAG-LAB, Ubuntu 26.04 LTS (resolute), Docker 29.7.2, août 2026.*
