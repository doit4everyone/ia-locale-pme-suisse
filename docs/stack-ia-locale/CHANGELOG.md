# Changelog

Toutes les modifications notables de ce repo sont documentées ici.

---

## [2.10.0] — Septembre 2026

### Documentation : corrections et mises à jour complètes

**Corrections de fond (affirmations incorrectes) :**
- `section-07-n8n.md` §7.2.3 : encadré port 8080 corrigé (non publié depuis v2.4.0).
- `section-07-n8n.md` §7.2.4 : section remplacée par renvoi vers §3.3/§3.4 (Dockerfile et volumes documentés là).
- `section-07-n8n.md` §7.2.5 : MD5 → SHA-256 tronqué. Ligne "fichier inchangé : aucun traitement" ajoutée.
- `section-05-connecteurs.md` §5.4.2 : `SMB_CREDENTIALS` supprimée (variable inexistante). `DOCUMENTATION_COLLECTION` et `DOCUMENTATION_PATHS` ajoutées.
- `section-05-connecteurs.md` §5.7.1 : extrait de code mis à jour (403 si résolution échoue).
- `section-05-connecteurs.md` §5.9 : collection `documentation` : accès selon ACL NTFS, pas accès universel.
- `section-08-fiabilite.md` §8.5 doublon → §8.6. `MAX_CONTEXT_CHUNKS` corrigé de 12 à 14.
- `section-09-securite.md` §9.8 : checklist corrigée (ligne 172.18 et port 8080 UFW).

**6 commandes `localhost:8080` remplacées** dans `section-00`, `section-03`, `section-07`, `section-09` par `docker compose exec n8n wget -qO- http://rag-api:8080/...`

**Ajouts :**
- `section-05-connecteurs.md` §5.4.2b : garde-fou 20% ACL illisibles documenté.
- `section-08-fiabilite.md` §8.7 : citations enrichies avec chemin UNC documentées.
- `section-09-securite.md` §9.7.1b : garde-fou ACL documenté avec validation lab.
- `suivi-corrections.md` : remis à jour, statuts corrigés, points ouverts précisés.

---

## [2.9.0] — Septembre 2026

### Sécurité

**Point 18 de l'audit : séparation structurelle instructions/données (main.py)**

- `get_system_prompt()` : ajout d'une règle explicite sur les balises `[DONNÉES DOCUMENTAIRES]` et `[FIN DES DONNÉES]`.
- `generate_answer()` : le contexte est désormais injecté entre ces balises dans le `prompt_user`. Toute instruction hostile dans un document indexé est traitée comme du contenu, jamais comme une instruction.
- **Validé en lab, septembre 2026 :** fichier `test.txt` contenant une instruction hostile indexé dans le corpus. La RAG API a ignoré l'instruction et répondu normalement.

### Documentation

- `section-08-fiabilite.md` : §8.3 et §8.4 corrigés. Comportement différencié `/v1` (affichage) vs `/query` (HTTP 422). Référence à Onyx CE supprimée.
- `section-09-securite.md` : §9.6.1 mis à jour avec l'implémentation réelle des balises. §9.6.2 corrigé : le juge vérifie l'ancrage, pas les URLs ni les injections. §9.6.3 corrigé : `indexer.py` ne fait pas de contrôle de contenu.

---

## [2.8.0] — Septembre 2026

### Nettoyage

**`main.py` :**
- Variables mortes supprimées : `owui_user`, `owui_email`, `owui_token`, `owui_user2`. `owui_id` conservé avec commentaire pour future corrélation dans le journal nLPD.
- Lecture redondante de `owui_email2` supprimée (doublon ligne 749).
- `except Exception as e` → `except Exception` dans `/stats` (`e` non utilisé).

**`acl_resolver.py` :**
- 5 f-strings sans variable converties en strings normales.
- `if not dry_run` redondant en phase 2 supprimé : `mettre_a_jour_qdrant` gère déjà le cas.
- Logs phase 2 enrichis avec `source_name` pour faciliter le diagnostic.

---

## [2.7.0] — Septembre 2026

### Corrigé

**`main.py` : 5 corrections suite au second audit**

- Branche fallback `search_qdrant` : `idx_min = idx_max = None` initialisés explicitement pour éviter un `NameError` sur les chunks sans `chunk_index` (indexés avant v2.3.0). Le `limit` adapté : `(idx_max - idx_min + 1) if idx_min is not None else MAX_CONTEXT_CHUNKS`.
- `enrichir_citations` déplacé après `groundedness_check` et `log_query` dans `/query` et `/v1`. Avant ce correctif, le juge et `verifier_citations` voyaient la citation enrichie `[nom.docx : \\\\serveur\\...]` au lieu de `[nom.docx]`, produisant des faux positifs `ancree: false` sur des réponses correctement sourcées.
- Docstring `build_context` mise à jour : suppression de la référence au lien cliquable et au commentaire chemin UNC devenus obsolètes.

**`acl_resolver.py` : réécriture en deux phases**

- Phase 1 : lecture complète de toutes les ACL en mémoire, sans aucune écriture dans Qdrant.
- Garde-fou 20% évalué AVANT toute écriture. Dans la version précédente, le garde-fou était placé après la boucle d'écriture : il se déclenchait après avoir déjà vidé les ACL de tout le corpus, rendant le message "abandon sans modification" faux.
- Phase 2 : écriture dans Qdrant uniquement si le seuil 20% n'est pas atteint.

---

## [2.6.0] — Septembre 2026

### Ajouté

**Chemin UNC dans les citations (`main.py`) :**
- Nouvelle fonction `enrichir_citations()` : post-traitement côté API qui remplace
  chaque citation `[nom.docx]` par `[nom.docx — `\\\\SERVEUR\\Partage\\Dossier\\`]`.
- Le chemin UNC est injecté dans un bloc code inline Markdown : non interprété par
  Open WebUI, copiable en un clic dans le presse-papiers.
- L'utilisateur colle le chemin dans la barre d'adresse de l'Explorateur Windows
  pour ouvrir directement le dossier source du document.
- Opère côté API après la génération, sans modifier le prompt ni dépendre du LLM.
- Variable `SMB_SHARE` déjà présente dans le conteneur (transmise via `docker-compose.yml`).

---

## [2.5.0] — Septembre 2026

### Sécurité

**Point 2 : `/query` laisse passer sans filtre ACL**
- `main.py` : `/query` refuse avec 403 si `user_id` ne contient pas `@`.
- `main.py` : `/query` refuse avec 403 si la résolution LDAP échoue ou retourne zéro groupe.
- `main.py` : `skip_groundedness` réservé à `ADMIN_TOKEN`. Un appelant avec `API_TOKEN` ne peut plus court-circuiter le groundedness check.

**Point 4 : token et données personnelles en clair dans les logs Docker**
- `main.py` : suppression des blocs `logger.info` de debug (en-têtes, token `Authorization`, noms, emails, `request.user`). Ces données personnelles étaient hors politique de rétention nLPD.

**Point 13 : `interdits[]` jamais vidé, ACL illisibles restent actives**
- `acl_resolver.py` : `interdits` toujours écrit dans le payload Qdrant, même vide. Un DENY retiré sur le file server est maintenant écrasé au prochain passage du résolveur.
- `acl_resolver.py` : fichier avec ACL illisible → `autorises` vidé dans Qdrant (deny by default). Avant cette correction, le fichier conservait ses anciennes ACL indéfiniment.

---

## [2.4.0] — Septembre 2026

### Sécurité

**Point 1 de l'audit : exposition LAN de Qdrant et de la RAG API (Docker bypass UFW)**

- `docker-compose.yml` : Qdrant lié à `127.0.0.1:6333` au lieu de `0.0.0.0:6333`. Le corpus n'est plus accessible depuis le LAN sans passer par la RAG API.
- `docker-compose.yml` : port 8080 (RAG API) supprimé de la section `ports`. La RAG API est joignable uniquement depuis le réseau Compose interne (`http://rag-api:8080`). L'en-tête `X-OpenWebUI-User-Email` ne peut plus être forgé depuis le LAN.
- Open WebUI : URL de connexion OpenAI mise à jour de `http://<IP-VM>:8080/v1` vers `http://rag-api:8080/v1`.
- n8n : URL du nœud `/admin/sync` déjà correcte (`http://rag-api:8080/admin/sync`).

### Modifié
- `section-03-docker-compose.md` : §3.4 mis à jour avec binding `127.0.0.1` et suppression du port 8080, note sur le contournement UFW par Docker.
- `section-09-securite.md` : §9.1 mis à jour, règles UFW corrigées (8080 et 6333 retirés), note explicite sur le fait que Docker bypass UFW via iptables.

---

## [2.3.0] — Septembre 2026

### Ajouté

**Indexation incrémentale (`indexer.py`) :**
- Comparaison `content_hash` + `embed_model` + `chunk_size` + `chunk_overlap` + `min_chunk_words` + `chunker_version` : les fichiers non modifiés sont ignorés sans appel Ollama.
- Report des ACL (`autorises`, `interdits`, `acl_updated_at`) sur les fichiers modifiés : plus de fenêtre sans ACL entre indexeur et résolveur.
- IDs de chunks déterministes + upsert : plus de fenêtre d'indisponibilité.
- `supprimer_chunks_excedentaires` via `Range(gte=nb_chunks)` sur `chunk_index` : les chunks de l'ancienne version qui n'existent plus sont supprimés proprement.
- Index de payload Qdrant créés dans `init_collection` : `source` (keyword) + `chunk_index` (integer). Idempotent, créé une seule fois par collection.
- `CHUNKER_VERSION=2` : réindexation automatique si `chunk_blocks()` est modifié.
- `MIN_CHUNK_WORDS` lu depuis l'environnement (défaut 8, corrigé de 15).
- `SUPPORTED_EXTENSIONS` partagée entre `indexer.py` et `acl_resolver.py`.
- Gestion erreurs par fichier : code de sortie 2 si erreur, pas plantage global.
- Répertoires exclus réellement élagués via `dirs[:]=` dans `os.walk` (DfsrPrivate, etc.).

**Correctifs `main.py` :**
- `chunk_index` ajouté dans `_load_collection_chunks` : l'extension de contexte fonctionne désormais quand un chunk BM25 gagne le RRF.
- Nettoyage des suites de points répétitifs dans `get_embedding()` : corrige l'erreur 500 Ollama sur les PDF avec tables des matières.

### Modifié
- `section-03-docker-compose.md` : note sur `chunk_index` dans l'index BM25.
- `section-08-fiabilite.md` : note sur `chunk_index` BM25 et nettoyage PDF.

---

## [2.2.0] — Septembre 2026

### Ajouté

**Deux collections Qdrant (documents + documentation) :**
- `indexer.py` : `get_collection_for_path()` route les fichiers vers la collection correcte selon le préfixe de chemin.
- `acl_resolver.py` : même logique, scan des orphelins sur les deux collections.
- `main.py` : recherche vectorielle sur les deux collections, fusion avant RRF, scroll d'extension de contexte dans la bonne collection.
- `section-05-connecteurs.md` : §5.8 ajouté, règles de gouvernance des collections.

**Correctifs retrieval (bugs identifiés en session) :**
- Clé RRF unique par chunk (`chunk_key = md5(text)`) au lieu du `source_id` (hash du fichier). Permet à plusieurs chunks du même fichier d'entrer dans le classement indépendamment.
- Scroll d'extension de contexte dans la bonne collection (`best_collection` déduit du chunk, non hardcodé à `documents`).
- `DOCUMENTATION_COLLECTION` et `DOCUMENTATION_PATHS` transmis aux sous-processus `indexer.py` et `acl_resolver.py` via `/admin/sync`.

**Paramètres ajustés (validés en lab) :**
- `TOP_K=20` : améliore le recall sur les gros fichiers .md.
- `CONTEXT_THRESHOLD=0.01` : adapté à l'échelle des scores RRF ([0, 0.016] avec k=60).
- `MAX_CONTEXT_CHUNKS=14` : validé en lab sur CPU (12 était insuffisant pour les documents denses).

### Modifié
- `section-03-docker-compose.md` : nouvelles variables `.env` documentées, `requirements.txt` mis à jour avec `rank-bm25`.
- `section-08-fiabilite.md` : §8.5 ajouté (retrieval hybride BM25, paramètres validés, limite sur les gros fichiers).

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
