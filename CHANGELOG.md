# Changelog

Toutes les modifications notables de ce repo sont documentées ici.

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
