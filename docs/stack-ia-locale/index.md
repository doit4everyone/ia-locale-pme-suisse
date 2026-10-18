---
title: "Guide de déploiement : stack IA locale sur VM Ubuntu Server | DoIt4Everyone"
description: "Déploiement complet d'un pipeline RAG local conçu pour faciliter la conformité à la nLPD : Open WebUI, RAG API FastAPI, Qdrant, Ollama ou vLLM, cloisonnement ACL NTFS, authentification LDAP AD, journalisation nLPD."
---
<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2, h3 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
  code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
  blockquote { border-left: 4px solid #2563A8; margin: 20px 0; padding: 10px 20px; background: #f0f4ff; }
</style>

# Guide de déploiement : stack IA locale sur VM Ubuntu Server

*Architecture : VM de la stack (Ubuntu Server 26.04) + serveur de modèles (Ollama ou vLLM)*

---

## §0 Objet, périmètre et avertissements

### Architecture validée en lab

Ce guide documente le déploiement d'une stack RAG locale pour PME, validée en lab sur processeur, puis sur carte graphique (§10). L'architecture en service à l'issue de ce guide :

```
Utilisateur → Nginx (HTTPS, https://rag.votre-domaine.ch, §9.8)
                  └→ Open WebUI (authentification LDAP AD, identité signée)
                       └→ RAG API FastAPI (port 8080, réseau interne)
                            ├→ auth.py : résolution groupes AD (LDAP, svc-rag)
                            ├→ Qdrant : index vectoriel + ACL NTFS (autorises[])
                            └→ Serveur de modèles : Ollama ou vLLM, qwen3:14b (§2)
```

Onyx CE est déployé dans §4 comme étape de validation de l'indexation et du backend Ollama. Il est ensuite remplacé par Open WebUI + RAG API FastAPI qui constituent la stack finale, avec le cloisonnement documentaire réel.

Le serveur de modèles fonctionne avec l'un de deux moteurs, documentés au §2 et comparés au §10.12 : **Ollama**, simple à installer, pour un à deux utilisateurs simultanés, et **vLLM**, qui traite plusieurs questions en même temps et convient à une PME dont plusieurs collaborateurs utilisent l'assistant. Les deux ont été validés en lab.

### Périmètre : cloisonnement documentaire

Ce guide documente un déploiement avec cloisonnement documentaire réel basé sur les ACL NTFS du file server Windows. Chaque utilisateur connecté via LDAP AD ne voit que les documents auxquels ses groupes AD donnent accès sur le partage source.

Ce guide est adapté aux organisations dont les utilisateurs ont des droits différenciés sur les documents : données RH, financières, clients, direction.

Pour un corpus sans restriction d'accès (base de connaissances commune, documentation technique interne), le cloisonnement peut être désactivé en retirant le filtre Qdrant dans `main.py`.

### Avertissements

> Tous les secrets présents dans ce guide sont en `changeme-*` : depuis la 2.21.0, la RAG API refuse de démarrer tant qu'il en reste un dans le `.env` (§16.6). Open WebUI et n8n sont servis en HTTPS par Nginx (§9.8), avec un certificat auto-signé tant que celui de l'autorité interne n'est pas installé. C'est une configuration de lab. Ne pas transposer telle quelle en production sans avoir appliqué §9, §15, §16 et §17.

> Le serveur RAG concentre le contenu de plusieurs partages sans les ACL d'origine. Ses sauvegardes deviennent aussi sensibles que les sources. À traiter comme un actif de valeur, pas comme une VM de service ordinaire.

### Convention de statut

Chaque section porte en tête une de ces trois lignes :

- **Statut :** validé en lab sur VM-RAG-LAB, septembre 2026
- **Statut :** validé partiellement, voir les réserves en fin de section
- **Statut :** documentaire, non validé sur matériel

### Contexte de validation

Hôte Intel Core i7-14700 (8 P-cores + 12 E-cores, 64 Go DDR5), VMware Workstation, d'abord sans GPU, puis avec une carte NVIDIA RTX 5060 Ti 16 Go (§10). VM Ubuntu Server 26.04 LTS, 16 Go RAM, 6 vCPU. Les mesures de performance données dans ce guide valent pour cette configuration et ne sont pas transposables à d'autres environnements.

---

## Sommaire

### Parties 1 et 2 : file server Windows

| Section | Contenu | Statut |
|---|---|---|
| [§0 Démarrage rapide](section-00-quickstart.md) | Déploiement de bout en bout, avec Ollama ou vLLM, Microsoft 365 en option (étape 17) | Publié |
| [§1 Prérequis et création de la VM](section-01-prerequis.md) | Sizing, installation Ubuntu 26.04, épinglage CPU, Docker | Publié |
| [§2 Le serveur de modèles : Ollama ou vLLM](section-02-vllm.md) | Choisir le moteur selon le nombre d'utilisateurs simultanés, installer Ollama ou vLLM (WSL2), vérifications, pièges, bascule, DGX Spark | Publié |
| [§3 Infrastructure : Qdrant, n8n, RAG API, Open WebUI](section-03-docker-compose.md) | Docker Compose, Qdrant, n8n, RAG API complète, Open WebUI | Publié |
| [§4 Interfaces utilisateur : Onyx CE et Open WebUI](section-04-onyx.md) | Validation backend avec Onyx CE, déploiement Open WebUI, LDAP AD, cloisonnement | Publié |
| [§5 Connecteurs SMB et cloisonnement documentaire](section-05-connecteurs.md) | Montage SMB, ACL NTFS, résolution LDAP, filtrage Qdrant par identité | Publié |
| [§6 Cline : agent de codage](section-06-cline.md) | Agent de codage IA, configuration VS Code, Ollama | Publié |
| [§7 Pipelines n8n](section-07-n8n.md) | Synchronisation corpus, rappel rotation svc-rag, OCR (documentaire) ; Teams : voir §12 | Publié |
| [§8 Fiabilité : hallucinations et contrôle d'ancrage](section-08-fiabilite.md) | Contrôles déterministes, groundedness check, formation utilisateurs | Publié |
| [§9 Sécurité et durcissement](section-09-securite.md) | UFW, TLS LDAP, frontal HTTPS Nginx et renouvellement du certificat, journalisation nLPD, rotation svc-rag, injection prompt | Publié |
| [§10 Validation et performances sur GPU](section-10-gpu.md) | Passage sur GPU, placement des modèles, méthode de mesure, choix des modèles, construction du contexte, reranker, limites du corpus, Ollama contre vLLM | Publié |

> **Version de référence des Parties 1 et 2 :** les scripts tels qu'ils ont été validés en lab pour ces sections sont figés dans la Release [v2.12.0](https://github.com/doit4everyone/ia-locale-pme-suisse/tree/v2.12.0/scripts/stack-ia-locale). Les scripts du dossier principal évoluent avec la Partie 3, en restant compatibles avec la stack SMB.

### Partie 3 : Microsoft 365

| Section | Contenu | Statut |
|---|---|---|
| [§11 Prérequis Microsoft 365](section-11-prerequis-ms365.md) | Microsoft Graph, App Registration par certificat, résolution des groupes Entra ID, mise à niveau compatible des scripts | Publié |
| [§12 Synthèse des réunions Teams](section-12-teams.md) | Transcriptions via Graph, groupe d'adhésion, compte rendu par le modèle local envoyé en brouillon à l'organisateur, évaluation mesurée | Publié |
| [§13 Connecteur SharePoint Online](section-13-sharepoint.md) | Indexation des bibliothèques SharePoint, traduction des permissions (groupes SharePoint, Entra, AD synchronisés, partages, liens) jusqu'aux chunks Qdrant, application Sites.Selected, matrice de cloisonnement | Publié |
| [§14 Documents protégés par Purview](section-14-purview.md) | Service de déchiffrement interne, double condition (permissions SharePoint et droits de l'étiquette évalués par Purview à la question), autorisations, mise en garde, matrice de validation | Publié |
| [§15 Sécurité des données](section-15-securite-donnees.md) | Clé d'API Qdrant, chiffrement des données au repos (LUKS2, TPM), secrets et clés sur le disque chiffré, migration, composants abandonnés, sauvegardes | Publié |
| [§16 Contrôle du cloisonnement et durcissement](section-16-cloisonnement.md) | Test de non-divulgation automatisé, contrôle après chaque synchronisation avec alerte, masque des droits NTFS, durcissement de la RAG API, d'Open WebUI et de n8n, identité signée, versions figées, supervision externe | Publié |
| [§17 Gouvernance](section-17-gouvernance.md) | Responsabilités, rotation des secrets et certificats, politique de corpus, droit à l'effacement, audit périodique, limites de la conformité technique, modèle de matrice RACI | Publié |

Les numéros de section sont attribués à la publication.

### Référence

| Document | Contenu |
|---|---|
| [suivi-corrections.md](suivi-corrections.md) | Suivi des corrections identifiées par audit de sécurité, avec priorités et état d'avancement |
| [Scripts Python du pipeline RAG](../../scripts/stack-ia-locale/index.md) | `indexer.py` (indexation SMB incrémentale, deux collections Qdrant), `acl_resolver.py` (ACL NTFS vers Qdrant), `main.py` (RAG API FastAPI : retrieval hybride BM25+vectoriel, juge LLM, journalisation nLPD), `auth.py` (résolution groupes AD via LDAP, extension Entra ID optionnelle via Microsoft Graph), `teams.py` et `teams_graph.py` (synthèse Teams), `sp_indexer.py` (indexation SharePoint, déchiffrement Purview), `Set-AccesIndexationRAG.ps1` (lecture du partage par un groupe dédié). Valeurs sensibles remplacées par des placeholders, prêts à adapter. |
| [Scripts SharePoint](../../scripts/sharepoint/) | Inventaires des permissions, accord `Sites.Selected` site par site, sonde (§13) |
| [Scripts Purview](../../scripts/purview/) | Sonde de déchiffrement, tests du service `mip-service` (§14) |
| [Workflows n8n](../../scripts/N8N/) | `n8n-sync-corpus.json` (synchronisation horaire du corpus + email quarantaine) `n8n-rappel-rotation-svc-rag.json` (rappel mensuel rotation mot de passe) et `n8n-teams-sync.json` (synthèse horaire des réunions Teams, §12). Fichiers JSON importables directement dans n8n. |

---

## Ce qui vient ensuite

La **Partie 3** est complète, de §11 à §17 : prérequis Microsoft 365, synthèse des réunions Teams, indexation de SharePoint Online avec ses permissions, documents protégés par Purview, sécurité des données, contrôle du cloisonnement, gouvernance. Il reste à venir :

- **le déploiement sur une VM neuve** avec le disque de données chiffré préparé dès le départ (§1.5), et des scripts de déploiement simplifiés ;
- **le résumé d'un document entier** (lecture par morceaux puis synthèse), que le RAG ne sait pas faire en choisissant des extraits (§10.10) ;
- **le RAG visuel** (recherche directe dans les pages de PDF complexes, tableaux et schémas, par un modèle multimodal), comme extension de la Partie 2 ;
- **une section « Du lab à la production »**, qui listera ce qu'un déploiement en entreprise exige en plus du lab.

---

← [Retour aux procédures](../)

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
