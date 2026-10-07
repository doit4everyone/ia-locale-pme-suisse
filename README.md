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

Stack : Open WebUI + RAG API FastAPI + Qdrant (deux collections : corpus entreprise + documentation) + Ollama + n8n, déployés via Docker Compose sur VM Ubuntu Server 26.04 LTS. Retrieval hybride BM25+vectoriel (RRF), indexation incrémentale. Validé en lab sur CPU (i7-14700, 64 Go DDR5), puis sur GPU (NVIDIA RTX 5060 Ti 16 Go, §10).

**Partie 3 (§11 à §17) : Microsoft 365.** Publiée :

- §11 : connexion à Microsoft Graph par certificat, résolution des groupes Entra ID, mise à niveau compatible des scripts.
- §12 : synthèse des réunions Teams. La transcription est récupérée via Graph, résumée par le modèle local et envoyée en brouillon à l'organisateur seul. Traitement limité aux organisateurs membres d'un groupe d'adhésion.
- §13 : connecteur SharePoint Online. Les documents sont indexés avec leurs permissions SharePoint, traduites en identifiants Entra : chaque utilisateur n'interroge que ce qu'il peut ouvrir dans SharePoint. Application en `Sites.Selected`, accordée site par site.
- §14 : documents protégés par Purview. Déchiffrement par un service interne, et double condition à chaque question : permissions SharePoint et droits de l'étiquette, évalués par Purview lui-même.
- §15 : sécurité des données. Clé d'API Qdrant, chiffrement des données au repos avec déverrouillage par TPM, secrets et clés sur le disque chiffré, sauvegardes.
- §16 : contrôle du cloisonnement. Test de non-divulgation automatisé, rejoué après chaque synchronisation avec alerte par courriel, et durcissement de la stack à la suite d'une revue externe.
- §17 : gouvernance. Responsabilités, rotation des secrets et certificats, politique de corpus, droit à l'effacement, audit, et ce que la nLPD exige au-delà de la technique.

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
| `sp_indexer.py` | Indexation SharePoint Online avec traduction des permissions |
| `Set-AccesIndexationRAG.ps1` | Lecture seule du compte d'indexation sur le partage, par un groupe dédié |

Workflows n8n importables : synchronisation du corpus, rappel de rotation du mot de passe `svc-rag`, synthèse des réunions Teams.

---

## Structure

```
ia-locale-pme-suisse/
├── index.md                    ← page d'accueil GitHub Pages
├── CHANGELOG.md                ← renvoi vers le journal détaillé
├── docs/
│   └── stack-ia-locale/        ← guide de déploiement (§0 à §17)
│       ├── index.md
│       ├── section-00-quickstart.md … section-17-gouvernance.md
│       └── CHANGELOG.md        ← journal détaillé des modifications
├── guides/                     ← guides décisionnels
└── scripts/
    ├── index.md
    ├── N8N/                    ← workflows n8n (.json)
    ├── sharepoint/             ← inventaires, accord Sites.Selected, sonde
    ├── purview/                ← sonde de déchiffrement, tests de mip-service
    ├── teams-test/             ← fichiers et scripts de test Teams
    └── stack-ia-locale/        ← scripts Python anonymisés
        ├── index.md
        ├── env.example
        ├── docker-compose.yml
        ├── deploy.sh
        ├── anon_indexer.py
        ├── anon_acl_resolver.py
        ├── sp_indexer.py
        ├── Set-AccesIndexationRAG.ps1
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
