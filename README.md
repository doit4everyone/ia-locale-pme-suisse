# ia-locale-pme-suisse

Documentation technique et procédures opérationnelles sur le déploiement de systèmes IA locaux dans un contexte PME suisse.

Guides décisionnels, procédures RAG, scripts Python. Publié à titre documentaire, sans partenariat commercial.

→ **[Voir la documentation complète](https://doit4everyone.github.io/ia-locale-pme-suisse/)**

---

## Ce que contient ce repo

### Guides décisionnels

Deux documents PDF destinés aux décideurs et consultants IT : le guide décisionnel « IA locale pour PME suisse » (architectures, TCO sur 3 ans, performances d'inférence, ingénierie RAG, sécurité nLPD) et le plan d'apprentissage RAG local en 14 phases (dont 2 optionnelles nécessitant un tenant Microsoft 365), refondu en septembre 2026 pour refléter la stack validée en lab.

### Guide de déploiement stack IA locale

Procédures pas à pas pour déployer un pipeline RAG local opérationnel sur VM Ubuntu Server 26.04, publiées section par section après validation en lab.

**Parties 1 et 2 (§0 à §9) : file server Windows.** La stack déployée :

- Les utilisateurs s'authentifient via leur compte Active Directory dans Open WebUI.
- Chaque utilisateur ne voit que les documents auxquels ses groupes AD donnent accès sur le file server Windows, grâce à la propagation des ACL NTFS jusqu'aux chunks Qdrant.
- Les réponses du LLM sont vérifiées par un juge LLM secondaire avant affichage.
- Chaque requête est journalisée avec l'identité de l'utilisateur et les sources consultées, pour l'audit nLPD.
- La synchronisation du corpus et la résolution des permissions sont automatisées via n8n.

Stack : Open WebUI + RAG API FastAPI + Qdrant (deux collections : corpus entreprise + documentation) + Ollama + n8n, déployés via Docker Compose sur VM Ubuntu Server 26.04 LTS. Retrieval hybride BM25+vectoriel (RRF), indexation incrémentale. Validé en lab sur matériel CPU sans GPU (i7-14700, 64 Go DDR5).

**Partie 3 (§11 et suivantes) : Microsoft 365.** En cours de publication :

- §11 : connexion à Microsoft Graph par certificat, résolution des groupes Entra ID, mise à niveau compatible des scripts.
- §12 : synthèse des réunions Teams. La transcription est récupérée via Graph, résumée par le modèle local et envoyée en brouillon à l'organisateur seul. Traitement limité aux organisateurs membres d'un groupe d'adhésion.
- À venir : connecteur SharePoint Online, documents protégés par Purview, gouvernance.

Les versions validées sont publiées sous forme de [Releases](https://github.com/doit4everyone/ia-locale-pme-suisse/releases). La Release v2.12.0 fige les scripts des Parties 1 et 2.

### Scripts Python

Scripts du pipeline RAG local, publiés avec les valeurs sensibles remplacées par des repères. Les fichiers contenant des valeurs d'exemple sont préfixés `anon_` ; `deploy.sh` les renomme à l'installation.

| Script | Rôle |
|---|---|
| `indexer.py` | Indexation SMB incrémentale, extraction `.docx` `.pdf` `.pptx` `.txt` `.md`, embedding Qdrant, deux collections |
| `acl_resolver.py` | Lecture des ACL NTFS, propagation vers Qdrant, nettoyage des chunks orphelins |
| `main.py` | RAG API FastAPI : retrieval hybride BM25+vectoriel (RRF), génération, groundedness check, journalisation nLPD, synthèse Teams |
| `auth.py` | Résolution des groupes AD via LDAP (récursive), extension Entra ID via Microsoft Graph, filtrage ACL |
| `teams.py` | Synthèse des réunions Teams : lecture VTT, prompt, contrôles déterministes, brouillon |
| `teams_graph.py` | Récupération des transcriptions Teams via Microsoft Graph |

Workflows n8n importables : synchronisation du corpus, rappel de rotation du mot de passe `svc-rag`, synthèse des réunions Teams.

---

## Structure

```
ia-locale-pme-suisse/
├── index.md                    ← page d'accueil GitHub Pages
├── CHANGELOG.md                ← renvoi vers le journal détaillé
├── docs/
│   └── stack-ia-locale/        ← guide de déploiement (§0 à §12)
│       ├── index.md
│       ├── section-00-quickstart.md … section-12-teams.md
│       └── CHANGELOG.md        ← journal détaillé des modifications
├── guides/                     ← guides décisionnels
└── scripts/
    ├── index.md
    ├── N8N/                    ← workflows n8n (.json)
    └── stack-ia-locale/        ← scripts Python anonymisés
        ├── index.md
        ├── env.example
        ├── docker-compose.yml
        ├── deploy.sh
        ├── anon_indexer.py
        ├── anon_acl_resolver.py
        ├── teams-test/         ← fichiers et scripts de test Teams
        └── api/
            ├── anon_main.py
            ├── anon_auth.py
            ├── teams.py
            ├── teams_graph.py
            ├── Dockerfile
            └── requirements.txt
```

---

## Licence

Documentation publiée sous licence [MIT](https://opensource.org/licenses/MIT).
