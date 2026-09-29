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
| 19 | `svc-rag` lisait le partage par les groupes métier : droits hérités au-delà du partage (droits d'étiquettes Purview, modification d'un site SharePoint), et perte de lecture silencieuse au retrait d'un groupe. Remplacé par le groupe dédié `GRP-RAG-Indexation` et `Set-AccesIndexationRAG.ps1` | v2.14.2 | 2026-09-27 |
| 20 | Fenêtre de contexte non demandée à Ollama : valeur par défaut de 4 096 tokens, contexte du RAG et du juge tronqué sans erreur. Fenêtres explicites par requête (`LLM_NUM_CTX`, `JUDGE_NUM_CTX`) | v2.15.0 | 2026-09-27 |
| 21 | Index BM25 non reconstruit après une synchronisation partiellement en échec : décalage possible avec Qdrant. Reconstruit après chaque synchronisation | v2.15.0 | 2026-09-27 |
| 22 | Courriel de quarantaine trompeur : fichiers aux permissions illisibles présentés comme « non indexés », avec une action inefficace. Les deux causes sont distinguées | v2.15.4 | 2026-09-29 |
| doc.2 | `GROUPS_CACHE_TTL`, `SYNC_PYTHON`, `SYNC_TIMEOUT_*` absents du Compose | v2.12.0 | 2026-09-24 |
| doc.4 | `deploy.sh` générait un `.env` incomplet | v2.12.0 | 2026-09-24 |

---

## Points ouverts

| Point | Description | Priorité | Remarque |
|---|---|---|---|
| 7 | Groundedness check ne bloque pas sur `/v1` | Choix délibéré | Documenté dans §8.3 depuis v2.9.0. Bloquer casserait la compatibilité OpenAI. |
| 10 | BM25 garde un instantané des ACL figées au démarrage | Faible | Les chunks BM25 ne repassent pas par Qdrant : le filtre ACL Qdrant ne s'applique pas sur le chemin BM25. Si les permissions d'un document changent, BM25 conserve les anciennes jusqu'à la reconstruction de l'index. Depuis v2.15.0, l'index est reconstruit après chaque synchronisation (horaire) : la fenêtre passe de « jusqu'au redémarrage » à une heure au plus. Impact limité en pratique : le chunk doit encore passer le filtre ACL Qdrant dans le scroll d'extension. Correction prévue : relire le payload Qdrant par ID pour les candidats BM25. |
| 14 | ACL par noms plutôt que par SIDs, masque ALLOWED non vérifié, permissions de partage ignorées | Moyenne | Identités intégrées à mesurer sur le partage avant de corriger. |
| auth.1 | Groupe principal AD absent de `memberOf` | Moyenne | Ajouter `primaryGroupID` dans `auth.py`. À mesurer d'abord sur le partage. |
| auth.2 | Identités intégrées (`AUTORITE NT\Utilisateurs authentifiés`) dans `autorises[]` sans être dans les groupes LDAP | Moyenne | Fichiers concernés invisibles. Décision à prendre : ignorer ou injecter dans `get_user_groups`. |
| doc.3 | n8n : port 5678 publié sur LAN, `N8N_BASIC_AUTH_*` sans effet depuis n8n 1.0 | Faible | Accès admin uniquement, acceptable en lab. |
| 23 | Qdrant sans clé d'API | Moyenne | Le port n'est pas publié (point 1), mais tout conteneur du réseau Compose peut lire et écrire. Prérequis de la section Purview, avant tout contenu déchiffré. |
| 24 | Aucun chiffrement au repos : chunks Qdrant, historique Open WebUI, sauvegardes | Moyenne, élevée avec Purview | Qdrant auto-hébergé n'a pas de chiffrement natif. Prévu : disque de données LUKS, sauvegardes chiffrées. Prérequis de la section Purview. |
| 25 | `sp_indexer.py` écrit chaque document dans un fichier temporaire avant extraction | Faible, élevée avec Purview | Sans conséquence pour des documents déjà lisibles sur SharePoint. Pour des documents déchiffrés : extraction en mémoire et `tmpfs`, prévues avec la section Purview. |
| 26 | Token d'administration en clair dans les nœuds HTTP des workflows n8n | Faible | Visible dans tout export de workflow. Passage prévu à l'identifiant n8n « Header Auth ». |
| 27 | `indexer.py` : un fichier chiffré par Purview sur le partage serait compté comme « vide », sans signalement explicite | Faible | Aucun fichier chiffré sur le partage du lab à ce jour. Détection prévue, comme dans `sp_indexer.py`. |
| 28 | Aucune détection de secrets dans le corpus indexé | Faible | Un fichier nommé comme une clé TLS a été trouvé dans un dossier indexé du lab. À traiter par la gouvernance (inventaire, exclusion), pas par l'indexeur seul. |
| 29 | Courriel de quarantaine sans statut par fichier | Faible | Le message présente les deux causes possibles (point 22), mais `main.py` ne transmet que les noms. Prévu avec la prochaine reconstruction (§10). |
| doc.5 | `deploy.sh` jamais réexécuté sur une VM vierge depuis v2.12.0 | Moyenne | À tester avec les scripts de simplification du déploiement. |

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

## Corrections documentaires v2.12.0 à v2.15.4 (septembre 2026)

| Section | Correction | Version |
|---|---|---|
| §9.1 | Docker contourne UFW : règles inutiles supprimées, validation par test de connexion | v2.12.0 |
| §5.2.4 | Lecture du partage par un groupe dédié, encadré sur le cas réel, script `Set-AccesIndexationRAG.ps1` | v2.14.2 |
| §7 | Résumé Teams : renvoi vers §12, étape SharePoint de `/admin/sync`, délai de 30 minutes | v2.15.0 |
| §3, §11 | Mentions « à venir » périmées remplacées par des renvois vers §11 à §13 | v2.15.0 |
| Accueil, `docs/index.md`, index des scripts | Passages périmés, pages d'index des dossiers (erreurs 404 sur GitHub Pages) | v2.15.0 |
| §0 | Étape 1 alignée sur §5.2.4 (elle ajoutait `svc-rag` aux groupes métier), étape 14 Microsoft 365, liste des fichiers | v2.15.1 |
| Tout le guide | Anonymisation complétée (§9, §11), repères de domaine harmonisés | v2.15.2 |
| §11.4.1 | Trois App Registrations au lieu de deux, renvois de sections corrigés | v2.15.3 |
| §7, §12, index | Graphie « compte rendu » | v2.15.3 |
| §13.8.1 | Diagnostic de la question générale sur la politique RH corrigé : test fait pendant la panne de lecture du partage | v2.15.4 |

---

*Dernière mise à jour : 29 septembre 2026.*
