---
title: "Guide de déploiement stack IA locale | DoIt4Everyone"
description: "Déployer une stack RAG locale sur Ubuntu Server 26.04 avec Onyx, Qdrant et Ollama. Validé en lab sur VM Ubuntu + LABO-G9, sans GPU."
---
<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2, h3 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
  code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.95em; }
  pre { background: #f4f4f4; padding: 16px; border-radius: 6px; overflow-x: auto; }
  blockquote { border-left: 4px solid #2563A8; margin: 20px 0; padding: 10px 20px; background: #f0f4ff; }
</style>

# Guide de déploiement : stack IA locale sur VM Ubuntu Server

*Architecture : VM-RAG-LAB (Ubuntu Server 26.04) + LABO-G9 (Ollama)*

---

## §0 Objet, périmètre et avertissements

### Objet et architecture

Ce guide documente le déploiement d'une stack RAG locale pour PME, validée en lab sur matériel CPU sans GPU. L'architecture en service :

```
Utilisateur → Onyx (VM-RAG-LAB, Ubuntu 26.04, 16 Go)
                 ├→ OpenSearch (index documentaire)
                 └→ Ollama qwen2.5:14b (LABO-G9, hôte Windows)
```

vLLM est documenté dans ce guide comme cible de production sur DGX Spark. Ce n'est pas le backend en service dans la configuration décrite.

### Périmètre : permissions

**Dans la configuration décrite par ce guide, tout utilisateur d'Onyx accède à l'intégralité du contenu indexé, quels que soient ses droits sur les fichiers d'origine. Onyx Community Edition ne filtre pas les résultats par permissions.**

Ce guide est valide pour un corpus dont l'ensemble des utilisateurs peut légitimement consulter tous les documents : documentation technique, procédures internes, base de connaissances. N'indexez pas un partage contenant des données à accès restreint.

Pour un corpus à droits différenciés, voir la Partie 2 de ce guide, consacrée à la RAG API avec filtrage ACL.

### Ce que ce guide ne couvre pas

- Le filtrage des résultats par permissions utilisateur, traité en Partie 2
- Les documents chiffrés par Purview : indexés mais illisibles, voir §4.7 et la Partie 2
- Le déploiement DGX Spark : documentaire, non validé sur matériel réel

### Avertissements de sécurité

Le serveur RAG concentre le contenu de plusieurs partages sans les ACL d'origine. Ses sauvegardes deviennent aussi sensibles que les sources. À traiter comme un actif de valeur, pas comme une VM de service ordinaire.

Tous les secrets présents dans les sections de ce guide sont en `changeme-*`, n8n est configuré en authentification basique sans TLS, Onyx est exposé en HTTP. C'est une configuration de lab. Ne pas transposer telle quelle en production.

### Convention de statut

Chaque section porte en tête une de ces trois lignes :

- **Statut :** validé sur VM-RAG-LAB, septembre 2026
- **Statut :** validé partiellement, voir les réserves en fin de section
- **Statut :** documentaire, non validé sur matériel

### Contexte de validation

Hôte Intel Core i7-14700 (8 P-cores + 12 E-cores, 64 Go DDR5), VMware Workstation, sans GPU. VM Ubuntu Server 26.04 LTS, 16 Go RAM, 6 vCPU. Les mesures de performance données dans ce guide valent pour cette configuration et ne sont pas transposables à d'autres environnements.

---

## Sommaire

| Section | Contenu | Statut |
|---|---|---|
| [§1 Prérequis et création de la VM](section-01-prerequis.md) | Sizing, installation Ubuntu 26.04, épinglage CPU, Docker | Publié |
| [§2 vLLM, validation CPU](section-02-vllm.md) | vLLM-cpu pour validation, configuration production DGX Spark | Publié |
| [§3 Infrastructure : Qdrant, n8n, squelette RAG API](section-03-docker-compose.md) | Docker Compose, Qdrant, n8n, RAG API squelette | Publié |
| [§4 Onyx et backend Ollama](section-04-onyx.md) | Déploiement Onyx CE, connexion Ollama, embedding, corpus de test | Publié |
| [§5 Connecteurs SMB et cloisonnement documentaire](section-05-connecteurs.md) | Montage SMB, ACL NTFS, résolution LDAP, filtrage Qdrant par identité | Publié |
| [§6 Cline : agent de codage](section-06-cline.md) | Agent de codage IA, configuration VS Code, Ollama | Publié |
| [§7 Pipelines n8n](section-07-n8n.md) | Synchronisation corpus, rappel rotation svc-rag, Teams et OCR (documentaire) | Publié |
| [§8 Fiabilité : hallucinations et contrôle d'ancrage](section-08-fiabilite.md) | Contrôles déterministes, groundedness check, formation utilisateurs | Publié |
| [§9 Sécurité et durcissement](section-09-securite.md) | UFW, TLS LDAP, journalisation nLPD, rotation svc-rag, injection prompt | Publié |
| §10 Validation et benchmarks | Checklist complète, mesure du débit, services systemd | À venir |


---

**Partie 2 :** document distinct, consacré à la RAG API FastAPI avec filtrage ACL NTFS. Destiné aux déploiements locaux sur corpus à droits différenciés.

---

## Partie 3 : connecteurs Microsoft 365 (à venir)

La Partie 3 documentera l'intégration de la stack RAG avec Microsoft 365 : connecteur SharePoint Online avec propagation des permissions Entra ID vers Qdrant, pipeline de résumé de réunions Teams (§7.4), et RAG visuel avec ColVec pour les documents PDF complexes. Elle sera publiée après validation en lab avec un tenant MS 365 actif et le GPU RTX 5060 Ti installé.

---

*Rédigé à titre documentaire, sans dépendance à aucun constructeur, revendeur ou intégrateur cité. Aucune prestation commerciale n'est associée à ce guide.*
