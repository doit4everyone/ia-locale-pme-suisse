# Changelog

Toutes les modifications notables de ce repo sont documentées ici.

---

## [2.1.0] — Septembre 2026

### Ajouté

**Retrieval hybride BM25 + vectoriel :**
- `main.py` : index BM25 construit en mémoire au démarrage depuis Qdrant, fusionné avec la recherche vectorielle par Reciprocal Rank Fusion (RRF). Améliore le retrieval sur les termes exacts (noms de fichiers, acronymes, commandes, termes techniques) là où la recherche vectorielle seule échoue sur les reformulations.
- `main.py` : reconstruction automatique de l'index BM25 après chaque synchronisation réussie via `/admin/sync`.
- `requirements.txt` : ajout de `rank-bm25`.

**Plan d'apprentissage RAG local refondu (`guides/plan-apprentissage-rag-2026.docx`) :**
- Document entièrement réécrit pour refléter la stack validée en lab (septembre 2026).
- 14 phases : 12 validées sur CPU, 2 optionnelles nécessitant un tenant MS 365.
- Choix techniques réels documentés : pipeline Python custom, chunking par blocs de paragraphes, `MIN_CHUNK_WORDS=8`, `JUDGE_KEEP_ALIVE`, `warmup_judge()`, Open WebUI comme interface finale.
- Note sur la migration BM42 (Qdrant sparse vectors) au-delà de 200 000 chunks.

### Modifié
- `main.py` : prompt système corrigé (suppression de la règle contradictoire "cite le document même hors sujet"), prompt juge enrichi avec deux règles d'attribution pour détecter les hallucinations par mauvaise attribution de contexte.
- `section-03-docker-compose.md` : `requirements.txt` documenté aligné sur la version réelle (`rank-bm25`, `pdfplumber`, `python-pptx`).
- `section-08-fiabilite.md` : nouvelles règles du prompt juge documentées, note sur les limites du juge `qwen3:4b` sur CPU et stratégie GPU (`JUDGE_MODEL=qwen2.5:14b`), footer mis à jour (970 chunks).
- `index.md` (racine du repo) : stack technique mise à jour avec "retrieval hybride BM25+vectoriel (RRF)".
- `scripts/stack-ia-locale/index.md` : fonctionnalités BM25 documentées, dépendances alignées.
- `docs/stack-ia-locale/index.md` : section Scripts ajoutée avec tableau des fichiers et lien vers `scripts/stack-ia-locale/`.

---

## [2.0.0] — Septembre 2026

### Ajouté

**Guide de déploiement stack IA locale (§1 à §9) :**
- §1 Prérequis et création de la VM Ubuntu Server 26.04
- §2 Installation et configuration de vLLM (mode CPU et référence DGX Spark)
- §3 Infrastructure Docker Compose : Qdrant, n8n, RAG API FastAPI, Open WebUI
- §4 Interfaces utilisateur : Onyx CE (validation) et Open WebUI (stack finale)
- §5 Connecteurs SMB et cloisonnement documentaire par ACL NTFS
- §6 Cline : agent de codage IA connecté à Ollama
- §7 Pipelines n8n : synchronisation corpus, rappel rotation svc-rag
- §8 Fiabilité : contrôles déterministes, groundedness check, formation utilisateurs
- §9 Sécurité et durcissement : UFW, TLS LDAP, journalisation nLPD, rotation svc-rag

**Scripts Python du pipeline RAG local (répertoire `scripts/stack-ia-locale/`) :**
- `indexer.py` : indexeur v5, cascade de détection org à 5 niveaux, support `.docx`, `.pdf`, `.pptx`, `.txt`, `.md`, exclusion `DfsrPrivate`, seuil minimal chunk configurable (`MIN_CHUNK_WORDS`)
- `acl_resolver.py` : v3 avec détection des chunks orphelins, résolution LDAP récursive (`memberOf`), DENY explicites
- `main.py` : RAG API FastAPI complète, filtrage Qdrant par ACL NTFS, groundedness check (`qwen3:4b`), `warmup_judge()`, journalisation nLPD, endpoint `/admin/sync`
- `auth.py` : résolution LDAP email → groupes AD, récursion `memberOf`, `CERT_REQUIRED`, cache TTL
- `docker-compose.yml` : stack complète Qdrant + n8n + RAG API + Open WebUI
- `.env.example` : template de configuration commenté
- `Dockerfile` et `requirements.txt` : image `rag-api` basée sur Python 3.11-slim

**Stack validée en lab :**
- Authentification LDAP Active Directory sur port 636 (LDAPS)
- Cloisonnement documentaire par ACL NTFS : propagation des SIDs jusqu'aux chunks Qdrant, filtrage à la requête par groupes AD de l'utilisateur
- DENY explicites NTFS prioritaires sur les ALLOW (cas validé en lab)
- Groupes imbriqués AD résolus par récursion `memberOf` (3 niveaux validés)
- Journalisation nLPD : hash de la question, identité utilisateur, sources consultées
- Groundedness check : juge `qwen3:4b` avec règles d'attribution pour détecter les hallucinations par mauvaise attribution de contexte

### Modifié
- `index.md` (racine) : description de la stack opérationnelle, liens corrigés vers les index de docs et scripts, section "Ce qui vient ensuite" (MS 365, Purview)

---

## [1.0.0] — Août 2026

### Ajouté
- Guide décisionnel « IA locale pour PME suisse » v1.0 (août 2026) — 25 pages, sources vérifiées
- Plan d'apprentissage RAG local — 12 phases, architecture LABO-G9 + VM-RAG-LAB
- Structure initiale du repo : `docs/`, `guides/`, `scripts/`
- Index des procédures opérationnelles à venir

---

*Les prochaines entrées seront ajoutées au fur et à mesure des publications.*
