---
title: "Guide de déploiement : stack IA locale sur VM Ubuntu Server | DoIt4Everyone"
description: "Déploiement complet d'un pipeline RAG local nLPD-compliant : Open WebUI, RAG API FastAPI, Qdrant, Ollama, cloisonnement ACL NTFS, authentification LDAP AD, journalisation nLPD."
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

*Architecture : VM-RAG-LAB (Ubuntu Server 26.04) + LABO-G9 (Ollama)*

---

## §0 Objet, périmètre et avertissements

### Architecture validée en lab

Ce guide documente le déploiement d'une stack RAG locale pour PME, validée en lab sur matériel CPU sans GPU. L'architecture en service à l'issue de ce guide :

```
Utilisateur → Open WebUI (VM-RAG-LAB, port 3001, authentification LDAP AD)
                  └→ RAG API FastAPI (port 8080)
                       ├→ auth.py : résolution groupes AD (LDAP, svc-rag)
                       ├→ Qdrant : index vectoriel + ACL NTFS (autorises[])
                       └→ Ollama qwen2.5:14b (LABO-G9, hôte Windows)
```

Onyx CE est déployé dans §4 comme étape de validation de l'indexation et du backend Ollama. Il est ensuite remplacé par Open WebUI + RAG API FastAPI qui constituent la stack finale, avec le cloisonnement documentaire réel.

vLLM est documenté dans §2 comme cible de production sur DGX Spark. Ce n'est pas le backend en service dans la configuration décrite : Ollama sur LABO-G9 assure l'inférence.

### Périmètre : cloisonnement documentaire

Ce guide documente un déploiement avec cloisonnement documentaire réel basé sur les ACL NTFS du file server Windows. Chaque utilisateur connecté via LDAP AD ne voit que les documents auxquels ses groupes AD donnent accès sur le partage source.

Ce guide est adapté aux organisations dont les utilisateurs ont des droits différenciés sur les documents : données RH, financières, clients, direction.

Pour un corpus sans restriction d'accès (base de connaissances commune, documentation technique interne), le cloisonnement peut être désactivé en retirant le filtre Qdrant dans `main.py`.

### Avertissements

> Tous les secrets présents dans ce guide sont en `changeme-*`. n8n est configuré en authentification basique sans TLS, les services sont exposés en HTTP. C'est une configuration de lab. Ne pas transposer telle quelle en production sans avoir appliqué §9.

> Le serveur RAG concentre le contenu de plusieurs partages sans les ACL d'origine. Ses sauvegardes deviennent aussi sensibles que les sources. À traiter comme un actif de valeur, pas comme une VM de service ordinaire.

### Convention de statut

Chaque section porte en tête une de ces trois lignes :

- **Statut :** validé en lab sur VM-RAG-LAB, septembre 2026
- **Statut :** validé partiellement, voir les réserves en fin de section
- **Statut :** documentaire, non validé sur matériel

### Contexte de validation

Hôte Intel Core i7-14700 (8 P-cores + 12 E-cores, 64 Go DDR5), VMware Workstation, sans GPU. VM Ubuntu Server 26.04 LTS, 16 Go RAM, 6 vCPU. Les mesures de performance données dans ce guide valent pour cette configuration et ne sont pas transposables à d'autres environnements.

---

## Sommaire

### Parties 1 et 2 : file server Windows

| Section | Contenu | Statut |
|---|---|---|
| [§0 Déploiement rapide](section-00-quickstart.md) | Procédure condensée pour redéployer la stack en 30 minutes | Publié |
| [§1 Prérequis et création de la VM](section-01-prerequis.md) | Sizing, installation Ubuntu 26.04, épinglage CPU, Docker | Publié |
| [§2 vLLM, validation CPU](section-02-vllm.md) | vLLM-cpu pour validation, configuration production DGX Spark | Publié |
| [§3 Infrastructure : Qdrant, n8n, RAG API, Open WebUI](section-03-docker-compose.md) | Docker Compose, Qdrant, n8n, RAG API complète, Open WebUI | Publié |
| [§4 Interfaces utilisateur : Onyx CE et Open WebUI](section-04-onyx.md) | Validation backend avec Onyx CE, déploiement Open WebUI, LDAP AD, cloisonnement | Publié |
| [§5 Connecteurs SMB et cloisonnement documentaire](section-05-connecteurs.md) | Montage SMB, ACL NTFS, résolution LDAP, filtrage Qdrant par identité | Publié |
| [§6 Cline : agent de codage](section-06-cline.md) | Agent de codage IA, configuration VS Code, Ollama | Publié |
| [§7 Pipelines n8n](section-07-n8n.md) | Synchronisation corpus, rappel rotation svc-rag, Teams et OCR (documentaire) | Publié |
| [§8 Fiabilité : hallucinations et contrôle d'ancrage](section-08-fiabilite.md) | Contrôles déterministes, groundedness check, formation utilisateurs | Publié |
| [§9 Sécurité et durcissement](section-09-securite.md) | UFW, TLS LDAP, journalisation nLPD, rotation svc-rag, injection prompt | Publié |
| §10 Validation et benchmarks | Checklist complète, mesure du débit, services systemd | À venir |

> **Version de référence des Parties 1 et 2 :** les scripts tels qu'ils ont été validés en lab pour ces sections sont figés dans la Release [v2.12.0](https://github.com/doit4everyone/ia-locale-pme-suisse/tree/v2.12.0/scripts/stack-ia-locale). Les scripts du dossier principal évoluent avec la Partie 3, en restant compatibles avec la stack SMB.

### Partie 3 : Microsoft 365

| Section | Contenu | Statut |
|---|---|---|
| [§11 Prérequis Microsoft 365](section-11-prerequis-ms365.md) | Microsoft Graph, App Registration par certificat, résolution des groupes Entra ID, mise à niveau compatible des scripts | Publié |
| [§12 Synthèse des réunions Teams](section-12-teams.md) | Transcriptions via Graph, groupe d'adhésion, compte-rendu par le modèle local envoyé en brouillon à l'organisateur, évaluation mesurée | Publié |
| Connecteur SharePoint Online | Indexation des documents, propagation des permissions SharePoint et Entra ID vers Qdrant | À venir |
| Documents protégés par Purview | Indexation des documents chiffrés par une étiquette de confidentialité | À venir |
| Gouvernance Microsoft 365 | Rotation des certificats, audit des accès, limites et responsabilités | À venir |

Les numéros de section sont attribués à la publication.

### Référence

| Document | Contenu |
|---|---|
| [suivi-corrections.md](suivi-corrections.md) | Suivi des corrections identifiées par audit de sécurité, avec priorités et état d'avancement |
| [Scripts Python du pipeline RAG](../../scripts/stack-ia-locale/index.md) | `indexer.py` (indexation SMB incrémentale, deux collections Qdrant), `acl_resolver.py` (ACL NTFS vers Qdrant), `main.py` (RAG API FastAPI : retrieval hybride BM25+vectoriel, juge LLM, journalisation nLPD), `auth.py` (résolution groupes AD via LDAP, extension Entra ID optionnelle via Microsoft Graph). Valeurs sensibles remplacées par des placeholders, prêts à adapter. |
| [Workflows n8n](../../scripts/N8N/) | `n8n-sync-corpus.json` (synchronisation horaire du corpus + email quarantaine) et `n8n-rappel-rotation-svc-rag.json` (rappel mensuel rotation mot de passe). Fichiers JSON importables directement dans n8n. |

---

## Ce qui vient ensuite

La **Partie 3** connecte la stack RAG à Microsoft 365 : résumé des réunions Teams, indexation des documents SharePoint Online avec propagation des permissions Entra ID jusqu'aux chunks Qdrant, prise en charge des documents protégés par Purview et gouvernance de l'ensemble. Elle est publiée section par section, après validation en lab sur un tenant Microsoft 365 synchronisé par Entra Connect. Elle ne nécessite pas de GPU.

Le **RAG visuel** (recherche directe dans les pages de PDF complexes, tableaux et schémas, par un modèle multimodal) sera documenté comme extension de la Partie 2, après l'installation du GPU RTX 5060 Ti et les mesures de §10.

---

← [Retour aux procédures](../)

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
