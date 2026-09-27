---
title: "Workflows n8n | IA locale pour PME suisse | DoIt4Everyone"
description: "Workflows n8n importables du guide de déploiement stack IA locale."
---

<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2, h3 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
  code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.95em; }
</style>

# Workflows n8n

[Retour aux scripts](../) | [Guide de déploiement](../../docs/stack-ia-locale/)

| Fichier | Rôle | Guide |
|---|---|---|
| [n8n-sync-corpus.json](n8n-sync-corpus.json) | Synchronisation horaire du corpus (SMB et SharePoint) par `/admin/sync`, email en cas de quarantaine ou d'erreur | §7.2, §13.6 |
| [n8n-rappel-rotation-svc-rag.json](n8n-rappel-rotation-svc-rag.json) | Rappel mensuel de rotation du mot de passe de `svc-rag` | §7.3 |
| [n8n-teams-sync.json](n8n-teams-sync.json) | Synthèse horaire des réunions Teams, brouillon envoyé à l'organisateur | §12.6 |

Importer dans n8n par **Import from File**, puis renseigner le token, l'identifiant SMTP et les adresses. Les valeurs sensibles sont remplacées par des repères (`<ADMIN_TOKEN>`, `<EMAIL_EXPEDITEUR>`).

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
