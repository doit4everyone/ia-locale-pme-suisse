---
title: "Procédures opérationnelles | IA locale pour PME suisse | DoIt4Everyone"
description: "Procédures de déploiement d'une stack IA locale conçue pour faciliter la conformité à la nLPD des PME suisses, validées en lab : file server Windows, puis Microsoft 365."
---

<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2, h3 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
</style>

# Procédures opérationnelles

[Retour à l'accueil](../) | [Guides décisionnels](../guides/)

Les procédures sont publiées après validation en lab, sur l'environnement de référence : LABO-G9 (Windows 11, VMware Workstation, Ollama natif, NVIDIA RTX 5060 Ti 16 Go) et VM-RAG-LAB (Ubuntu Server 26.04, Docker Compose).

---

## Guide de déploiement stack IA locale

→ [Guide de déploiement stack IA locale](stack-ia-locale/)

| Partie | Contenu | Sections |
|---|---|---|
| Parties 1 et 2 : file server Windows | Pipeline RAG complet : Open WebUI, RAG API FastAPI, Qdrant, Ollama, n8n. Authentification LDAP AD, cloisonnement documentaire par ACL NTFS, contrôle d'ancrage, journalisation nLPD, durcissement | §0 à §9 |
| Partie 3 : Microsoft 365 | Microsoft Graph et groupes Entra ID, synthèse des réunions Teams, indexation de SharePoint Online avec ses permissions, documents protégés par Purview, sécurité des données, contrôle du cloisonnement, gouvernance | §11 à §17 |
| Validation et performances sur GPU | Passage sur GPU, placement des modèles, méthode de mesure reproductible, choix des modèles et construction du contexte mesurés, limites qui relèvent du corpus | §10 |

Les scripts et workflows correspondants sont publiés dans [scripts](../scripts/).

---

## Lien avec le plan d'apprentissage

Le [plan d'apprentissage RAG local](../guides/plan-apprentissage-rag-2026.pdf) décrit la progression en 17 phases : 12 pour le pipeline sur file server Windows, 3 pour les connecteurs Microsoft 365 qui demandent un tenant actif, et 2 pour la preuve du cloisonnement et la mesure. Le guide de déploiement en est la mise en œuvre validée en lab : les phases y sont couvertes dans l'ordre du déploiement, et non comme des procédures séparées.

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
