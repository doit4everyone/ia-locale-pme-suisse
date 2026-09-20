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

### Référence

| Document | Contenu |
|---|---|
| [suivi-corrections.md](suivi-corrections.md) | Suivi des corrections identifiées par audit de sécurité, avec priorités et état d'avancement |

---

## Partie 3 : connecteurs Microsoft 365 (à venir)

La Partie 3 documentera l'intégration de la stack RAG avec Microsoft 365 : connecteur SharePoint Online avec propagation des permissions Entra ID vers Qdrant, pipeline de résumé de réunions Teams (§7.4), et RAG visuel avec ColVec pour les documents PDF complexes. Elle sera publiée après validation en lab avec un tenant MS 365 actif et le GPU RTX 5060 Ti installé.

---

← [Retour aux procédures](../)

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
