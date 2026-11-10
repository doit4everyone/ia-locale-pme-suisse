---
title: "IA locale pour PME suisse : stack RAG, guide et scripts | DoIt4Everyone"
description: "Déployer une IA locale dans une PME suisse : une stack RAG sur votre infrastructure, des réponses limitées aux droits de chaque utilisateur, des mesures de qualité. Guide pas à pas, scripts et corpus de test, gratuits."
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
- **Réponses vérifiées :** chaque réponse cite ses sources, et un modèle juge contrôle qu'elle s'appuie bien sur elles ; une réponse qu'il ne peut pas rattacher aux documents est affichée avec un avertissement.
- **Accès sécurisé :** connexion par le compte Active Directory, en HTTPS derrière un frontal Nginx, avec une identité signée entre l'interface et le moteur de recherche.
- **Traçabilité nLPD :** chaque question est journalisée avec l'utilisateur et les sources consultées ; un échec d'écriture du journal est signalé mais n'interrompt pas le service (point ouvert 186) ; les données sont chiffrées au repos.
- **Rejouable :** le démarrage rapide (§0) décrit chaque étape, de la création de la VM au contrôle final, et `deploy.sh` en automatise une partie ; la procédure complète a été rejouée de bout en bout le 1er novembre 2026, en version 2.23.0 : cloisonnement contrôlé sur 207 verdicts sans aucune fuite, qualité des réponses mesurée, sauvegarde et restauration, redémarrage.

**Stack technique :** Open WebUI, RAG API FastAPI, Qdrant, Ollama ou vLLM (qwen3:14b), n8n et Nginx, déployés par Docker Compose sur Ubuntu Server 26.04 LTS. Recherche hybride par mots-clés (dans Qdrant 1.20) et par vecteurs (`bge-m3`), reranker optionnel sur la carte graphique, indexation incrémentale. Formats indexés : `.docx`, `.pdf`, `.pptx`, `.txt`, `.md`.

---

## Ce qui vient ensuite

Les trois parties du guide sont publiées : le serveur de fichiers Windows (§0 à §10), Microsoft 365 (§11 à §14), puis la sécurité, le contrôle du cloisonnement et la gouvernance (§15 à §17). Prochaines étapes :

- des mesures de l'index sur un corpus plus grand, et le passage de l'interface en compte non privilégié ;
- une procédure de mise à jour d'une installation existante, rejouée de bout en bout ;
- une section « Du lab à la production » ;
- la migration du service de déchiffrement Purview vers .NET 10, le support de .NET 8 prenant fin le 10 novembre 2026 ;
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
