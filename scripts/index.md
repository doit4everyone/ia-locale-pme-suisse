---
title: "Scripts | IA locale pour PME suisse | DoIt4Everyone"
description: "Scripts Python et workflows n8n du guide de déploiement de la stack IA locale."
---

<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2, h3 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
</style>

# Scripts

[Retour au sommaire](../) | [Guide de déploiement](../docs/stack-ia-locale/)

| Dossier | Contenu |
|---|---|
| [stack-ia-locale](stack-ia-locale/) | Scripts Python du pipeline RAG local (RAG API, indexation, ACL, extension Entra ID, synthèse Teams), `docker-compose.yml`, `env.example`, `deploy.sh`, fichiers de test |
| [N8N](N8N/) | Workflows n8n importables : synchronisation du corpus, rappel de rotation du mot de passe `svc-rag`, synthèse des réunions Teams |

Les scripts sont publiés à titre documentaire. Les valeurs sensibles ont été remplacées par des repères. Détail de chaque script : [index des scripts du pipeline](stack-ia-locale/).

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
