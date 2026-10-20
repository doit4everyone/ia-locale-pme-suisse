---
title: "IA locale pour PME suisse : guide décisionnel et procédures | DoIt4Everyone"
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
| [Plan d'apprentissage RAG local](guides/plan-apprentissage-rag-2026.pdf) | PDF | Octobre 2026 |

---

## Procédures opérationnelles

| Ressource | Contenu | Lien |
|---|---|---|
| **Guide de déploiement stack RAG IA locale** | Déploiement complet en 18 sections (§0 à §17) : démarrage rapide, VM et disque chiffré, serveur de modèles, Docker Compose, cloisonnement par les droits NTFS, authentification Active Directory, n8n, fiabilité des réponses, sécurité, mesures sur GPU, Microsoft 365, contrôle du cloisonnement, gouvernance | → [Accéder au guide](docs/stack-ia-locale/index.md) |
| **Scripts** | `deploy.sh`, `docker-compose.yml`, RAG API, indexation, droits d'accès, tests de cloisonnement : valeurs sensibles remplacées par des repères, prêts à adapter | → [Accéder aux scripts](scripts/stack-ia-locale/index.md) |
| **Workflows n8n** | Synchronisation du corpus avec alertes, rappel de rotation du compte de service, synthèse des réunions Teams : fichiers JSON importables dans n8n | → [Accéder aux workflows](scripts/N8N/) |

### Ce que la stack fait concrètement

Un assistant qui répond à partir des documents de l'entreprise, sans service d'IA externe. Validé en lab, sur processeur puis sur carte graphique (NVIDIA RTX 5060 Ti 16 Go), avec Ollama et avec vLLM. Ce n'est pas une installation de production : le guide dit ce qu'il faut ajouter pour y arriver (§17.7).

- **Cloisonnement réel :** chaque utilisateur ne voit que les documents qu'il a déjà le droit d'ouvrir, sur le serveur de fichiers (droits NTFS) comme dans SharePoint, documents protégés par Purview compris.
- **Contrôlé automatiquement :** un test de non-divulgation est rejoué après chaque synchronisation, avec une alerte par courriel en cas de fuite.
- **Réponses vérifiées :** chaque réponse cite ses sources, et un second modèle contrôle qu'elle s'appuie bien sur elles.
- **Accès sécurisé :** connexion par le compte Active Directory, en HTTPS derrière un frontal Nginx, avec une identité signée entre l'interface et le moteur de recherche.
- **Traçabilité nLPD :** chaque question est journalisée avec l'utilisateur et les sources consultées ; les données sont chiffrées au repos.
- **Rejouable :** `deploy.sh` installe la stack sur une VM neuve ; la procédure complète a été rejouée de bout en bout le 19 octobre 2026.

**Stack technique :** Open WebUI, RAG API FastAPI, Qdrant, Ollama ou vLLM (qwen3:14b), n8n et Nginx, déployés par Docker Compose sur Ubuntu Server 26.04 LTS. Recherche hybride par mots-clés et par vecteurs, indexation incrémentale. Formats indexés : `.docx`, `.pdf`, `.pptx`, `.txt`, `.md`.

---

## Ce qui vient ensuite

Les trois parties du guide sont publiées : le serveur de fichiers Windows (§0 à §10), Microsoft 365 (§11 à §14), puis la sécurité, le contrôle du cloisonnement et la gouvernance (§15 à §17). Prochaines étapes :

- un test de charge avec vLLM, à quatre puis huit questions simultanées, et des mesures de l'index sur un corpus plus grand ;
- une procédure de mise à jour d'une installation existante ;
- une section « Du lab à la production » ;
- le RAG visuel, pour les PDF complexes (tableaux, schémas).

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
