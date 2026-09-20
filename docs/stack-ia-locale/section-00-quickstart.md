---
title: "§0 Déploiement rapide | Guide de déploiement stack IA locale"
description: "Procédure de déploiement condensée de la stack RAG locale : prérequis, configuration, lancement et validation en 30 minutes."
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

# §0 Déploiement rapide

[Retour au sommaire](index.md)

> Ce guide condensé couvre un redéploiement complet en 30 minutes sur une infrastructure existante. Pour un premier déploiement, lire le guide complet à partir de [§1 Prérequis](section-01-prerequis.md).

---

## Prérequis vérifiés avant de commencer

| Prérequis | Vérification |
|---|---|
| VM Ubuntu 26.04, 16 Go RAM, 6 vCPU | `free -h && nproc` |
| Docker et Docker Compose installés | `docker --version && docker compose version` |
| Ollama accessible depuis la VM | `curl http://<IP-HOTE-OLLAMA>:11434/api/tags` |
| Modèles Ollama présents | `qwen2.5:14b` et `qwen3:4b` dans la liste |
| Partage SMB monté | `ls /mnt/corpus-root/` |
| Compte svc-rag actif dans l'AD | `smbclient //<NOM-FILESERVER>/PartageDocuments -U svc-rag` |
| Certificat CA du DC présent | `ls /etc/ssl/certs/ad-chain.pem` |

---

## Étape 1 : structure des répertoires

```bash
mkdir -p ~/rag-stack/{qdrant_data,n8n_data,openwebui_data,api}
mkdir -p /root/rag-pipeline
mkdir -p /var/log/rag
```

Déposer les fichiers :

```
~/rag-stack/
├── .env                    ← copier depuis .env.example et adapter
├── docker-compose.yml
├── api/
│   ├── main.py
│   ├── auth.py
│   ├── Dockerfile
│   └── requirements.txt

/root/rag-pipeline/
├── indexer.py
└── acl_resolver.py
```

---

## Étape 2 : fichier .env

Les trois variables obligatoires à changer avant tout lancement :

```bash
# Copier le template
cp .env.example .env

# Éditer les trois valeurs critiques
nano .env
```

```bash
LLM_BASE_URL=http://<IP-HOTE-OLLAMA>:11434
API_TOKEN=<token-fort-32-caracteres-minimum>
ADMIN_TOKEN=<token-fort-distinct-du-precedent>
```

Vérifier aussi :

```bash
LDAP_HOST=<NOM-DC>.domaine.ch
LDAP_BIND_DN=CN=svc-rag,OU=COMPTES-SERVICE,DC=domaine,DC=ch
LDAP_BIND_PWD=<mot-de-passe-svc-rag>
SMB_SHARE=//NOM-FILESERVER/PartageDocuments
SMB_USER=svc-rag
SMB_PASSWORD=<mot-de-passe-svc-rag>
SMB_DOMAIN=DOMAINE
```

---

## Étape 3 : lancement de la stack

```bash
cd ~/rag-stack

# Premier lancement : construire l'image rag-api
docker compose build --no-cache rag-api
docker compose up -d

# Vérifier que tout tourne
docker compose ps
```

Résultat attendu :

```
NAME         STATUS
n8n          Up
open-webui   Up (healthy)
qdrant       Up
rag-api      Up
```

---

## Étape 4 : environnement Python pour les scripts

```bash
cd /root/rag-pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install qdrant-client python-docx pdfplumber python-pptx httpx
```

---

## Étape 5 : première indexation

```bash
cd /root/rag-pipeline && source .venv/bin/activate
set -a && source ~/rag-stack/.env && set +a

# Indexer le corpus (première fois : complet)
python indexer.py --corpus /mnt/corpus-root \
  --rapport /var/log/rag/rapport_initial.json

echo "Code de sortie : $?"
```

Résultat attendu : code 0, 0 erreur, rapport JSON produit.

---

## Étape 6 : synchronisation des ACL

```bash
curl -X POST http://localhost:8080/admin/sync \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  | python3 -m json.tool
```

Résultat attendu : `"success": true`, `"quarantine_count": 0`.

---

## Étape 7 : validation de la stack

```bash
# RAG API
curl http://localhost:8080/health

# Qdrant (depuis la VM uniquement)
curl http://localhost:6333/collections

# BM25 chargé
docker logs rag-api 2>&1 | grep BM25 | tail -2

# Open WebUI accessible
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001
# Attendu : 200
```

---

## Étape 8 : configuration Open WebUI

1. Ouvrir `http://<IP-VM>:3001`
2. Créer le compte administrateur au premier accès
3. Settings → Admin → Connections → ajouter une connexion API OpenAI :
   - URL : `http://rag-api:8080/v1`
   - Clé : valeur de `API_TOKEN`
4. Settings → Admin → Authentication → LDAP : configurer avec les valeurs du `.env`
5. Settings → Admin → Models → `rag-api` → Make Public

---

## Checklist de validation finale

| Test | Commande / action | Résultat attendu |
|---|---|---|
| RAG API répond | `curl http://localhost:8080/health` | `{"status":"ok"}` |
| Qdrant accessible | `curl http://localhost:6333/collections` | JSON avec collections |
| BM25 chargé | `docker logs rag-api \| grep BM25` | Nombre de chunks |
| Cloisonnement positif | Question sur document accessible | Réponse avec citation et chemin UNC |
| Cloisonnement négatif | Compte test limité, question hors périmètre | "Cette information ne figure pas..." |
| Journal nLPD | `tail -1 /var/log/rag/rag-queries.jsonl` | Entrée JSON avec user_id |
| n8n sync horaire | `http://<IP-VM>:5678` → workflow actif | Dernière exécution réussie |

---

## En cas de problème

**`rag-api` redémarre en boucle :**

```bash
docker logs rag-api 2>&1 | tail -20
```

Causes fréquentes : variable manquante dans `.env`, certificat CA absent, Qdrant pas encore prêt.

**Qdrant vide après redémarrage :**

Les données sont dans `~/rag-stack/qdrant_data/`. Vérifier que le volume est monté :

```bash
ls ~/rag-stack/qdrant_data/
```

**BM25 vide au démarrage :**

Qdrant a démarré après `rag-api`. Attendre 30 secondes et relancer :

```bash
docker compose restart rag-api
```

**ACL non propagées (sources_accessed vide) :**

Relancer manuellement le résolveur ACL :

```bash
curl -X POST http://localhost:8080/admin/sync \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

---

[Suite : §1 Prérequis et création de la VM](section-01-prerequis.md)

---

*Validé sur VM-RAG-LAB, Ubuntu 26.04 LTS, septembre 2026.*
