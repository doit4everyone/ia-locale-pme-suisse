---
title: "IA locale pour PME suisse — Guide décisionnel et procédures | DoIt4Everyone"
description: "RTX Spark, DGX Spark, RTX PRO 6000, H100 : architectures IA locales pour PME suisses. TCO réel sur 3 ans en CHF, performances d'inférence mesurées, ingénierie RAG, sécurité et conformité nLPD. Procédures opérationnelles publiées progressivement."
---

<style>
  header, footer { display: none !important; }
  .wrapper {
    max-width: 900px !important;
    margin: 0 auto !important;
    float: none !important;
    position: relative !important;
    padding: 40px 20px !important;
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important;
    font-size: 1.1em !important;
  }
  section {
    width: 100% !important;
    float: none !important;
    margin: 0 !important;
  }
  h1, h2 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
</style>

# IA locale pour PME suisse 🤖

**Documentation technique et procédures opérationnelles sur le déploiement de systèmes IA locaux dans un contexte PME suisse.**

*Rédigé à titre documentaire, sans dépendance à aucun constructeur, revendeur ou intégrateur cité. Aucune prestation commerciale n'est associée à ces publications.*

---

## Guides décisionnels

Documents de référence destinés aux décideurs et aux consultants IT.

| Document | Format | Date |
|---|---|---|
| [IA locale pour PME suisse : guide décisionnel 2026](guides/gpu-ia-pme-suisse-2026.pdf) | PDF | Août 2026 |
| [Plan d'apprentissage RAG local](guides/plan-apprentissage-rag-2026.pdf) | PDF | Août 2026 |

---

## Procédures opérationnelles

| Ressource | Contenu | Lien |
|---|---|---|
| **Guide de déploiement stack IA locale** | Déploiement complet en 9 sections : VM, Docker Compose, cloisonnement ACL NTFS, authentification LDAP AD, pipelines n8n, fiabilité, sécurité | → [Accéder au guide](docs/stack-ia-locale/index.md) |
| **Scripts Python** | `indexer.py`, `acl_resolver.py`, `main.py`, `auth.py`, `docker-compose.yml` : valeurs sensibles remplacées par des placeholders, prêts à adapter | → [Accéder aux scripts](scripts/stack-ia-locale/index.md) |
| **Workflows n8n** | Synchronisation corpus + email quarantaine, rappel mensuel rotation svc-rag : fichiers JSON importables directement dans n8n | → [Accéder aux workflows](scripts/N8N/) |

### Ce que la stack fait concrètement

Validée en lab sur matériel CPU sans GPU. Ce n'est pas un proof of concept : c'est une stack opérationnelle.

- Authentification via compte Active Directory dans Open WebUI.
- Cloisonnement documentaire réel : chaque utilisateur ne voit que les documents auxquels ses groupes AD donnent accès sur le file server Windows, grâce à la propagation des ACL NTFS jusqu'aux chunks Qdrant.
- Contrôle d'ancrage : les réponses du LLM sont vérifiées par un juge LLM secondaire avant affichage.
- Journalisation nLPD : chaque requête est tracée avec l'identité de l'utilisateur et les sources consultées.
- Synchronisation et résolution des permissions automatisées via n8n.

**Stack technique :** Open WebUI + RAG API FastAPI + Qdrant + Ollama (qwen2.5:14b) + n8n, déployés via Docker Compose sur VM Ubuntu Server 26.04 LTS. Retrieval hybride BM25+vectoriel (RRF), indexation incrémentale. Formats indexés : `.docx`, `.pdf`, `.pptx`, `.txt`, `.md`.

---

## Ce qui vient ensuite

La stack actuelle couvre le cas d'usage file server Windows avec ACL NTFS. Deux extensions sont en préparation, après validation en lab avec un tenant Microsoft 365 actif et l'installation du GPU RTX 5060 Ti :

**Connecteurs Microsoft 365 :** connecteur SharePoint Online avec propagation des permissions Entra ID vers Qdrant, pipeline de résumé de réunions Teams, et RAG visuel avec ColVec pour les documents PDF complexes.

**Fichiers chiffrés Purview :** indexation des documents protégés par des labels de sensibilité Microsoft Information Protection, avec déchiffrement à la volée via clé RMS consultée depuis Azure Key Vault.

---

## À propos

Ce repo est maintenu dans le cadre de la documentation publiée sur [doit4everyone.github.io](https://doit4everyone.github.io).

Les guides au format `.docx` et `.pdf` sont dans le répertoire [`guides/`](guides/). Les procédures en markdown sont dans [`docs/`](docs/). Les scripts Python sont dans [`scripts/`](scripts/).

---

## ☕ Soutenir le projet

Ces guides représentent des centaines d'heures de travail de lab et de documentation.

👉 [![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/R5R31YHNIB)

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
