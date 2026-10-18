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
| [n8n-sync-corpus.json](n8n-sync-corpus.json) | Synchronisation horaire du corpus (SMB et SharePoint) par `/admin/sync`, email en cas de quarantaine, d'erreur ou d'alerte de cloisonnement ; signal facultatif à une supervision externe (nœud « Signal supervision (Push) », désactivé à l'import) | §7.2, §13.6, §16.4, §16.10 |
| [n8n-rappel-rotation-svc-rag.json](n8n-rappel-rotation-svc-rag.json) | Rappel mensuel de rotation du mot de passe de `svc-rag` | §7.3 |
| [n8n-teams-sync.json](n8n-teams-sync.json) | Synthèse horaire des réunions Teams, brouillon envoyé à l'organisateur | §12.6 |

Avant l'import, créer dans n8n l'identifiant **Header Auth** `RAG API - ADMIN_TOKEN` (*Name* `Authorization`, *Value* `Bearer <ADMIN_TOKEN>`, domaine autorisé `rag-api`) : les nœuds HTTP l'utilisent, et le jeton n'est écrit dans aucun workflow (§16.7).

Créer aussi l'identifiant **SMTP** de la boîte d'envoi (avec Exchange Online : `smtp.office365.com`, port 587, *SSL/TLS* désactivé, *Disable STARTTLS* désactivé, *Client Host Name* vide).

Importer ensuite par **Import from File**, puis sélectionner **dans chaque nœud** l'identifiant Header Auth et l'identifiant SMTP : ceux référencés dans les fichiers n'existent pas chez vous (*Credentials not found*). Renseigner les adresses : `<EMAIL_EXPEDITEUR>` exactement égal à la boîte authentifiée par SMTP (Exchange Online refuse une autre adresse : `SendAsDenied`), `<EMAIL_DESTINATAIRE>` une boîte interne. Les workflows sont importés désactivés : les publier une fois vérifiés. Le Compose du dépôt règle n8n sur le fuseau `Europe/Zurich` : les déclenchements planifiés suivent l'heure suisse. Procédure complète : §0, étape 15.

Depuis la 2.21.0, n8n s'ouvre par `https://<RAG_FQDN>:5678`, à travers Nginx (§9.8). Les nœuds joignent toujours la RAG API par le réseau interne (`http://rag-api:8080`). Pour le nœud de supervision, indiquer le nom DNS **complet** de la machine de supervision : le conteneur n8n ne résout pas les noms courts (`EAI_AGAIN`).

Pour remplacer un workflow existant sans en créer un second : ouvrir l'existant, sélectionner tous les nœuds, les supprimer, puis coller le contenu du fichier sur le canevas.

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
