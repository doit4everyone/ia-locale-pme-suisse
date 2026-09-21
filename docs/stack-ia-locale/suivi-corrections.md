---
title: "Suivi des corrections | Guide de déploiement stack IA locale"
description: "Suivi des points identifiés par audit de sécurité, avec priorité, état et version de correction."
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

# Suivi des corrections

[Retour au sommaire](index.md)

Ce document suit les points identifiés par audit de sécurité sur le code et la documentation. Mis à jour à chaque session.

---

## Corrections appliquées

| Point | Description | Version | Session |
|---|---|---|---|
| 1 | Qdrant et port 8080 exposés sur le LAN (Docker bypass UFW) | v2.4.0 | 2026-09-14 |
| 2 | `/query` laisse passer sans filtre ACL si `user_groups` vide | v2.5.0 | 2026-09-14 |
| 3 | En-tête `X-OpenWebUI-User-Email` falsifiable | v2.4.0 | 2026-09-14 (effet de bord point 1) |
| 4 | Token et données personnelles en clair dans les logs Docker | v2.5.0 | 2026-09-14 |
| 5 | Extensions différentes entre `indexer.py` et `acl_resolver.py` | v2.1.0 | 2026-09-11 |
| 6 | `lire_acl_fichier` retourne `[]` au lieu de `[], []` | v2.1.0 | 2026-09-11 |
| 8 | Extension de contexte : scroll aléatoire au lieu de fenêtre par `chunk_index` | v2.3.0 | 2026-09-13 |
| 9 | RRF biaisé contre la collection `documentation` | v2.3.0 | 2026-09-13 |
| 11 | Réindexation complète à chaque passage (pas de détection des fichiers inchangés) | v2.3.0 | 2026-09-13 |
| 12 | Suppression par `content_hash` pouvait effacer des copies légitimes | v2.3.0 | 2026-09-13 |
| 13 | `interdits[]` jamais vidé, ACL illisibles restaient actives | v2.5.0 | 2026-09-14 |
| 15 | Nettoyage des orphelins sans seuil : garde-fou 20% ajouté dans `acl_resolver.py` | v2.7.0 | 2026-09-20 |
| 16 | `DOCUMENTATION_COLLECTION` et `DOCUMENTATION_PATHS` absents du Compose | v2.3.0 | 2026-09-13 |
| 17 | `EXCLUDE_PATTERNS` n'excluait pas les répertoires | v2.3.0 | 2026-09-13 |
| 18 | Pas de séparation structurelle instructions/données dans le prompt | v2.9.0 | 2026-09-21 |

---

## Points ouverts

| Point | Description | Priorité | Remarque |
|---|---|---|---|
| 7 | Groundedness check ne bloque pas sur `/v1` | Choix délibéré | Documenté dans §8.3 depuis v2.9.0. Bloquer casserait la compatibilité OpenAI. |
| 10 | BM25 garde un instantané des ACL figées au démarrage | Faible | Impact limité : BM25 est un filtre de pré-sélection, le filtre ACL Qdrant reste actif. |
| 14 | ACL par noms plutôt que par SIDs, masque ALLOWED non vérifié, permissions de partage ignorées | Moyenne | Identités intégrées à mesurer sur le partage avant de corriger. |
| auth.1 | Groupe principal AD absent de `memberOf` | Moyenne | Ajouter `primaryGroupID` dans `auth.py`. À mesurer d'abord sur le partage. |
| auth.2 | Identités intégrées (`AUTORITE NT\Utilisateurs authentifiés`) dans `autorises[]` sans être dans les groupes LDAP | Moyenne | Fichiers concernés invisibles. Décision à prendre : ignorer ou injecter dans `get_user_groups`. |
| doc.1 | `§9.8` checklist et commandes sur port 8080 | Corrigé | v2.9.0 documentation |
| doc.2 | `GROUPS_CACHE_TTL`, `SYNC_PYTHON`, `SYNC_TIMEOUT_*` absents du Compose | Faible | Variables sans effet, valeurs coïncident avec les défauts du code. |
| doc.3 | n8n : port 5678 publié sur LAN, `N8N_BASIC_AUTH_*` sans effet depuis n8n 1.0 | Faible | Accès admin uniquement, acceptable en lab. |

---

## Corrections documentaires appliquées (septembre 2026)

| Section | Correction | Version |
|---|---|---|
| §8.3 / §8.4 | Comportement `/v1` vs `/query` documenté. Référence Onyx CE supprimée. | v2.9.0 |
| §9.6.1 | Implémentation réelle des balises `[DONNÉES DOCUMENTAIRES]` documentée et validée en lab. | v2.9.0 |
| §9.6.2 | Rôle du juge corrigé : vérification d'ancrage, pas détection d'injection. | v2.9.0 |
| §9.6.3 | `indexer.py` : pas de contrôle de contenu, seulement rejet des fichiers vides/courts. | v2.9.0 |
| §7.2.3 | Encadré port 8080 corrigé : port non publié depuis v2.4.0. | v2.9.0 |
| §7.2.4 | Section remplacée par un renvoi vers §3.3 et §3.4. | v2.9.0 |
| §7.2.5 | MD5 corrigé en SHA-256 tronqué. Ligne "fichier inchangé" ajoutée. | v2.9.0 |
| §5.4.2 | `SMB_CREDENTIALS` supprimée, `DOCUMENTATION_COLLECTION` et `DOCUMENTATION_PATHS` ajoutées. | v2.9.0 |
| §5.7.1 | Extrait de code mis à jour : comportement réel avec 403 si résolution échoue. | v2.9.0 |
| §5.9 | Collection `documentation` : accès selon ACL NTFS, pas accès universel. | v2.9.0 |
| §9.8 | Checklist corrigée : lignes UFW/172.18 et port 8080 mises à jour. | v2.9.0 |
| §5.4.2b | Garde-fou 20% ACL illisibles documenté. | v2.9.0 |
| §9.7.1b | Garde-fou ACL documenté avec résultat de validation lab. | v2.9.0 |
| §8.6 | Second §8.5 renommé §8.6. `MAX_CONTEXT_CHUNKS` corrigé de 12 à 14. | v2.9.0 |
| §8.7 | Citations UNC documentées. | v2.9.0 |
| §0 | Commandes `localhost:8080` remplacées par `docker compose exec n8n wget`. | v2.9.0 |

---

## Corrections documentaires v2.11.0 (septembre 2026)

| Section | Correction |
|---|---|
| §0 étape 10 | Note de quarantaine corrigée : statut `quarantaine` vs `vide`, PDF scanné → aucun chunk |
| §0 étape 12 | `userPrincipalName` obligatoire (pas `sAMAccountName`) documenté |
| §0 | `FileService` aligné (au lieu de `PartageDocuments`) |
| §3.7 | Commande `localhost:8080` → `docker compose exec n8n wget` |
| §3 / §4 / §5 | Renvois `§9.3` → `§9.2` (certificat CA du DC) |
| §4.1.2 | Heap OpenSearch codé en dur dans le Compose, pas dans `.env` |
| §4.2.4 | Rôle par défaut `en attente` (pas `utilisateur`), cohérent avec §4.2.4 |
| §5 l.222 | `EXCLUDE_PATTERNS` → `EXCLUDE_DIR_PATTERNS` |
| §5.6.3 | Rôle par défaut `en attente` documenté |
| §5.9 | `PartageDocuments` → `FileService` + quarantaine corrigée |
| §7 | 3 tirets cadratins retirés (l.180, l.196, l.270) |
| §9.4.1 | `"verification": "effectuee"` ajouté à l'exemple de log. Note élargie aux contrôles déterministes |
| §9.5.2 | Comportement svc-rag désactivé corrigé : garde-fou, bind LDAP, fichiers inchangés |
| §9.6.1 | Limites de la neutralisation documentées, test de validation nuancé |
| §9.6.3 | Quarantaine corrigée, dernière phrase nuancée |
| §9.6 | `§9.5.1` commande `localhost:8080` corrigée |

---

*Dernière mise à jour : septembre 2026.*
