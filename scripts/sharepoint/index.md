---
title: "Scripts SharePoint | IA locale pour PME suisse | DoIt4Everyone"
description: "Inventaire des permissions SharePoint Online, accord Sites.Selected site par site et sonde de l'application d'indexation."
---

<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2, h3 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
  code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.95em; }
</style>

# Scripts SharePoint

[Retour aux scripts](../) | [§13 Connecteur SharePoint Online](../../docs/stack-ia-locale/section-13-sharepoint.html)

| Fichier | Rôle | Exécution |
|---|---|---|
| [Inventaire-Permissions-SharePoint.ps1](Inventaire-Permissions-SharePoint.ps1) | Permissions de chaque fichier et dossier, via Graph (CSV) | Poste d'administration, module `Microsoft.Graph.Authentication` |
| [Inventaire-GroupesSharePoint.ps1](Inventaire-GroupesSharePoint.ps1) | Composition des groupes SharePoint de chaque site (CSV) | Windows PowerShell 5.1, module SharePoint Online |
| [Resoudre-Identifiants.ps1](Resoudre-Identifiants.ps1) | Nom et type des identifiants trouvés dans les inventaires | Module `Microsoft.Graph.Authentication` |
| [Accorder-SitesSelected.ps1](Accorder-SitesSelected.ps1) | Lecture accordée à l'application d'indexation, site par site | Module `Microsoft.Graph.Authentication`, compte administrateur |
| [sonde_sharepoint.py](sonde_sharepoint.py) | Ce que l'application peut réellement lire, avant et après l'accord | Conteneur `rag-api` |

Tous les scripts sont en lecture seule, sauf `Accorder-SitesSelected.ps1`. Ne pas charger les modules SharePoint Online et Graph dans la même session PowerShell (voir §13.2.1).

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
