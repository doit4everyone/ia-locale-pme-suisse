# ia-locale-pme-suisse

Documentation technique et procédures opérationnelles sur le déploiement de systèmes IA locaux dans un contexte PME suisse.

Guides décisionnels, procédures RAG, scripts Python. Publié à titre documentaire, sans partenariat commercial.

→ **[Voir la documentation complète](https://doit4everyone.github.io/ia-locale-pme-suisse/)**

---

## Ce que contient ce repo

### Guides décisionnels

Deux documents PDF destinés aux décideurs et consultants IT : le guide décisionnel « IA locale pour PME suisse » (architectures, TCO sur 3 ans, performances d'inférence, ingénierie RAG, sécurité nLPD) et le plan d'apprentissage RAG local en 12 phases.

### Guide de déploiement stack IA locale (§1 à §9)

Procédures pas à pas pour déployer un pipeline RAG local opérationnel sur VM Ubuntu Server 26.04. La stack déployée à l'issue de ce guide :

- Les utilisateurs s'authentifient via leur compte Active Directory dans Open WebUI.
- Chaque utilisateur ne voit que les documents auxquels ses groupes AD donnent accès sur le file server Windows, grâce à la propagation des ACL NTFS jusqu'aux chunks Qdrant.
- Les réponses du LLM sont vérifiées par un juge LLM secondaire avant affichage.
- Chaque requête est journalisée avec l'identité de l'utilisateur et les sources consultées, pour l'audit nLPD.
- La synchronisation du corpus et la résolution des permissions sont automatisées via n8n.

Stack : Open WebUI + RAG API FastAPI + Qdrant + Ollama + n8n, sur Docker Compose. Validé en lab sur matériel CPU sans GPU (i7-14700, 64 Go DDR5).

### Scripts Python

Scripts du pipeline RAG local, publiés avec les valeurs sensibles remplacées par des placeholders :

| Script | Rôle |
|---|---|
| `indexer.py` | Indexation SMB, extraction `.docx` `.pdf` `.pptx` `.txt` `.md`, embedding Qdrant |
| `acl_resolver.py` | Lecture ACL NTFS, résolution LDAP récursive, propagation vers Qdrant |
| `main.py` | RAG API FastAPI : retrieval, génération, groundedness check, journalisation nLPD |
| `auth.py` | Résolution groupes AD via LDAP, filtrage ACL |

---

## Structure

```
ia-locale-pme-suisse/
├── index.md                    ← page d'accueil GitHub Pages
├── docs/
│   └── stack-ia-locale/        ← guide de déploiement §1 à §9
├── guides/                     ← guides décisionnels (.pdf)
├── scripts/
│   └── stack-ia-locale/        ← scripts Python anonymisés
│       ├── index.md
│       ├── .env.example
│       ├── docker-compose.yml
│       ├── indexer.py
│       ├── acl_resolver.py
│       └── api/
│           ├── main.py
│           ├── auth.py
│           ├── Dockerfile
│           └── requirements.txt
└── CHANGELOG.md
```

---

## Licence

Documentation publiée sous licence [MIT](https://opensource.org/licenses/MIT).
