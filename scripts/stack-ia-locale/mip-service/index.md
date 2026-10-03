---
title: "Service mip-service | IA locale pour PME suisse | DoIt4Everyone"
description: "Service interne de déchiffrement Purview (.NET 8, SDK MIP, image Ubuntu 24.04), construit avec le profil Compose purview. Voir §14.5 du guide."
---

<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2, h3 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
</style>

# Service mip-service

[Retour](../) | [§14 Documents protégés par Purview](../../../docs/stack-ia-locale/section-14-purview.html)

Service interne de déchiffrement Purview (.NET 8, SDK MIP, image Ubuntu 24.04), construit avec le profil Compose purview. Voir §14.5 du guide.

| Fichier | Rôle |
|---|---|
| [Program.cs](Program.cs) | Code |
| [MipService.csproj](MipService.csproj) | Projet .NET, paquet `Microsoft.InformationProtection.File.Ubuntu2404` |
| [Dockerfile](Dockerfile) | Image Ubuntu 24.04, dépendances natives du SDK, lien `libdl.so` |

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
