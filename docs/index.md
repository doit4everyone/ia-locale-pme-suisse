# Procédures opérationnelles

Procédures dérivées du [plan d'apprentissage RAG local](../guides/plan-apprentissage-rag-2026.pdf).

Chaque procédure correspond à une phase du plan d'apprentissage et est publiée après validation en pratique. L'ordre suit la progression du plan.

**Environnement de référence :** LABO-G9 (Windows 11, VMware Workstation, Ollama natif) + VM-RAG-LAB (Ubuntu Server 24.04, Docker Compose).

---

## Guide de déploiement stack IA locale

Guide complet de déploiement d'un pipeline RAG local nLPD-compliant sur VM Ubuntu Server 24.04, avec cloisonnement documentaire par ACL NTFS, authentification LDAP AD et journalisation nLPD.

→ [Guide de déploiement stack IA locale](stack-ia-locale/index.md)

---

## Procédures disponibles

*Procédures unitaires par phase du plan d'apprentissage, publiées après validation en pratique.*

---

## Structure prévue

Les procédures seront publiées dans cet ordre, en suivant les phases du plan :

| Phase | Procédure | Statut |
|---|---|---|
| 1 | Créer la VM-RAG-LAB et valider la connectivité Ollama | À venir |
| 2 | Premier pipeline RAG avec LlamaIndex | À venir |
| 3 | Parsing des documents et stratégies de chunking | À venir |
| 4 | Qdrant : persistance, métadonnées et snapshot | À venir |
| 5 | Retrieval hybride et reranker BGE | À venir |
| 6 | Prompt strict, citations et groundedness check | À venir |
| 7 | Permissions NTFS : filtrage par identité AD | À venir |
| 8 | API FastAPI et service complet | À venir |
| 9 | Sécurité du pipeline : injection, durcissement, journalisation | À venir |
| 10 | Synchronisation et monitoring | À venir |
| 11 | Onyx : plateforme vs pipeline custom | À venir |
| 12 | Projet de synthèse sur cas réel | À venir |

---

← [Retour à l'accueil](../)
