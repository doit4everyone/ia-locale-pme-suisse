---
title: "Scripts Purview | IA locale pour PME suisse | DoIt4Everyone"
description: "Sonde de déchiffrement Purview et scripts de test du service mip-service."
---

<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2, h3 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
  code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.95em; }
</style>

# Scripts Purview

[Retour aux scripts](../) | [§14 Documents protégés par Purview](../../docs/stack-ia-locale/section-14-purview.html)

| Fichier | Rôle | Exécution |
|---|---|---|
| [sonde-mip/](sonde-mip/) | Sonde : déchiffre un seul document de test, affiche son étiquette, son propriétaire et le début de son texte (`Program.cs`, `SondeMip.csproj`, `Dockerfile`) | Conteneur jetable, voir §14.7.1 |
| [test_mip_service.py](test_mip_service.py) | Teste `/dechiffrer` : refus sans jeton, décision, contenu déchiffré | Dans le conteneur `rag-api` |
| [test_droits.py](test_droits.py) | Interroge `/droits` pour une étiquette et une liste d'utilisateurs : la vérité de référence de Purview | Dans le conteneur `rag-api` |

Le code du service lui-même est dans [`../stack-ia-locale/mip-service/`](../stack-ia-locale/mip-service/).

```bash
# Depuis le conteneur rag-api, par le réseau interne
docker exec -e MIP_TOKEN=$MIP_TOKEN rag-api python3 /rag-pipeline/test_mip_service.py /rag-pipeline/<document-de-test>.docx
docker exec -e MIP_TOKEN=$MIP_TOKEN rag-api python3 /rag-pipeline/test_droits.py \
  <identifiant-etiquette> <proprietaire> <utilisateur1> <utilisateur2>
```

Les documents de test copiés dans `/root/rag-pipeline` sont sur le disque système : les supprimer après le test.

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
