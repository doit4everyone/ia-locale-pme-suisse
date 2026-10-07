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
| 23 | Qdrant sans clé d'API : tout conteneur du réseau Compose pouvait lire et écrire. Clé obligatoire, transmise aux quatre clients (§15.2) | v2.16.0 | 2026-10-01 |
| 24 | Aucun chiffrement au repos : disque de données LUKS2 dédié, déverrouillage par TPM, phrase secrète en clé de secours ; Qdrant, Open WebUI, n8n et journaux migrés (§15.3). Les sauvegardes restent au point 34 | v2.16.0 | 2026-10-01 |
| 25 | `sp_indexer.py` écrivait chaque document dans un fichier temporaire sur disque : extraction dans `/dev/shm` | v2.16.0 | 2026-10-02 |
| 14 (masque) | Toute entrée ALLOWED valait autorisation, quel que soit le masque : un fichier en écriture seule (boîte de dépôt) devenait interrogeable. Reproduit (FUITE), corrigé, prouvé sans régression (§16.5) | v2.17.0 | 2026-10-03 |
| 26 | Jeton d'administration en clair dans les workflows n8n : identifiant Header Auth partagé, domaine limité à `rag-api` (§16.7) | v2.17.0 | 2026-10-04 |
| 37 | Test de non-divulgation automatisé, en deux modes, et contrôle après chaque synchronisation avec alerte (§16.2 à §16.4) | v2.17.0 | 2026-10-03 |
| 38 | Mot de passe SMB hors de la ligne de commande : fichier d'identifiants en mémoire | v2.17.0 | 2026-10-03 |
| 39 | Juge en échec : réponse non vérifiée, plus jamais « ancrée » | v2.17.0 | 2026-10-03 |
| 40 | Citations : correspondance exacte ; deux documents de même nom signalés tous deux | v2.17.0 | 2026-10-03 |
| 41 | `/stats` réservé à l'administration, `/health` minimal, panne de Qdrant en erreur 503 | v2.17.0 | 2026-10-03 |
| 42 | Empreinte HMAC des questions (`LOG_HMAC_KEY`) | v2.17.0 | 2026-10-03 |
| 43 | Modèles Ollama bruts masqués dans Open WebUI, accès au moteur d'inférence à restreindre au pare-feu (§16.7) | v2.17.0 | 2026-10-03 |
| 45 | Aucun signal quand un secret garde une valeur d'exemple (`changeme`) : avertissement au démarrage. Constaté en lab : jeton d'administration **et** jeton d'API restés à leur valeur d'exemple ; le second a été signalé par l'avertissement dès son premier démarrage | v2.17.0 | 2026-10-04 |
| 46 | `.env` lisible par tous les comptes de la VM (`644`) en lab, `.env` et clés privées sur le disque système non chiffré : déplacés sur le disque chiffré (§15.3.6), préparation avant le déploiement (§1.5) | v2.17.0 | 2026-10-04 |
| 47 | `/v1` ignorait la demande de réponse en flux : Open WebUI `v0.11.3` n'affichait plus rien. Réponse en flux, en un seul fragment, contrôles inchangés (§16.8) | v2.17.1 | 2026-10-04 |
| 48 | Échec de la résolution Entra présenté comme une absence d'information : mention explicite dans la réponse (§16.9) | v2.17.1 | 2026-10-04 |
| 49 | Images en `latest` et `main` : versions figées et empreintes documentées (§3.4) ; contrôles automatiques du dépôt par GitHub Actions | v2.17.1 | 2026-10-04 |
| 50 | Contexte construit pour les seules questions précises : liste tronquée à 20 candidats, 3 extraits complémentaires quelconques, copies non écartées. Diversité des sources (§8.9) | v2.17.2 | 2026-10-05 |
| 51 | Prompt « tout ou rien » : refus dès qu'une réponse était incomplète. Réponse partielle explicite, protégée par deux tests de refus (§8.9) | v2.17.2 | 2026-10-05 |
| 53 | Juge et embedding sur CPU par défaut, sans graine de génération : réglages `JUDGE_NUM_GPU`, `EMBED_NUM_GPU`, `LLM_SEED` ; les trois modèles validés sur la carte (§10.2) | v2.18.0 | 2026-10-07 |
| 54 | Document principal tronqué quand son meilleur extrait est l'en-tête : document court envoyé en entier (`DOC_COMPLET_MAX`), fenêtre décalée pour les longs documents (§10.6) | v2.18.0 | 2026-10-07 |
| 55 | Documents complémentaires réduits à leurs en-têtes : extraits consécutifs autour du meilleur extrait, mêmes filtres d'accès que le document principal (§10.6) | v2.18.0 | 2026-10-07 |
| 56 | Fenêtre du juge plus petite que celle du modèle : sources coupées, affirmations justes déclarées non ancrées. Par défaut, la fenêtre du juge est celle du modèle (§10.6) | v2.18.0 | 2026-10-07 |
| 57 | Réponses : balises du contexte et extraits recopiés, citations sans crochets, liens recopiés depuis un document, fausses absences. Nettoyage, normalisation des citations, règles de prompt (§10.9) | v2.18.0 | 2026-10-07 |
| 58 | Réglages numériques transmis vides : la RAG API ne démarrait pas. Valeur vide traitée comme absente (19 lectures, RAG API, authentification, indexeur) ; réglages ajoutés au Compose avec leurs valeurs par défaut (§10.9) | v2.18.0 | 2026-10-07 |
| 60 | Test de cloisonnement : erreur de lecture de Qdrant traitée comme une collection absente ; correspondance partielle du document, un cas pouvant évaluer deux documents. Erreurs explicites (503), correspondance exacte par défaut, cas ambigus refusés (§16) | v2.18.2 | 2026-10-07 |

---

## Points ouverts

| Point | Description | Priorité | Remarque |
|---|---|---|---|
| 7 | Groundedness check ne bloque pas sur `/v1` | Choix délibéré | Documenté dans §8.3 depuis v2.9.0. Bloquer casserait la compatibilité OpenAI. Depuis v2.17.0, `/v1` signale dans la réponse une vérification impossible ou un ancrage non établi. |
| 10 | BM25 garde un instantané des ACL figées au démarrage | Faible | Les chunks BM25 ne repassent pas par Qdrant : le filtre ACL Qdrant ne s'applique pas sur le chemin BM25. Si les permissions d'un document changent, BM25 conserve les anciennes jusqu'à la reconstruction de l'index. Depuis v2.15.0, l'index est reconstruit après chaque synchronisation (horaire) : la fenêtre passe de « jusqu'au redémarrage » à une heure au plus. Impact limité en pratique : le chunk doit encore passer le filtre ACL Qdrant dans le scroll d'extension. Correction prévue : relire le payload Qdrant par ID pour les candidats BM25. |
| 14 | ACL par noms plutôt que par SIDs | Moyenne | Le masque des droits est corrigé et les permissions du partage sont contrôlées (v2.17.0, §16.5). Reste le passage aux SID, avec le groupe principal (auth.1) : **le masque d'abord, le groupe principal ensuite**, sinon un fichier en écriture seule pour « Utilisateurs du domaine » devient lisible par tout le domaine. |
| auth.1 | Groupe principal AD absent de `memberOf` | Moyenne | Ajouter `primaryGroupID` dans `auth.py`. À mesurer d'abord sur le partage. À faire **après** la correction du masque (faite en v2.17.0), voir §16.5. |
| auth.2 | Identités intégrées (`AUTORITE NT\Utilisateurs authentifiés`) dans `autorises[]` sans être dans les groupes LDAP | Moyenne | Fichiers concernés invisibles. Décision à prendre : ignorer ou injecter dans `get_user_groups`. |
| doc.3 | n8n : port 5678 publié sur LAN, `N8N_BASIC_AUTH_*` sans effet depuis n8n 1.0 | Faible | Accès admin uniquement, acceptable en lab. |
| 27 | `indexer.py` : un fichier chiffré par Purview sur le partage serait compté comme « vide », sans signalement explicite | Faible | Aucun fichier chiffré sur le partage du lab à ce jour. Détection prévue, comme dans `sp_indexer.py`. |
| 28 | Aucune détection de secrets dans le corpus indexé | Faible | Un fichier nommé comme une clé TLS a été trouvé dans un dossier indexé du lab. À traiter par la gouvernance (inventaire, exclusion), pas par l'indexeur seul. |
| 29 | Courriel de quarantaine sans statut par fichier | Faible | Le message présente les deux causes possibles (point 22), mais `main.py` ne transmet que les noms. Prévu avec la prochaine reconstruction (§10). |
| doc.5 | `deploy.sh` jamais réexécuté sur une VM vierge depuis v2.12.0 | Moyenne | À tester sur une VM neuve en UEFI avec TPM et deux disques, avec le disque chiffré et les liens préparés avant le déploiement (§1.5, contrôle ajouté à `deploy.sh` en v2.17.0), et les scripts de simplification du déploiement. |
| 30 | Recherche par mots-clés sensible aux accents et découpée sur les seules espaces (« règlement » ≠ « reglement ») | Moyenne | Constatée en §14.7.3. Normalisation des accents et de la ponctuation prévue dans `main.py` (§10). |
| 31 | Open WebUI envoie ses tâches d'arrière-plan (titres, suggestions) à `rag-api` : deux recherches complètes par question, une entrée de plus au journal nLPD | Moyenne | Réglage d'Open WebUI documenté en §14.8.2. |
| 32 | Cache des décisions Purview sans verrou : deux recherches simultanées interrogent Purview deux fois | Faible | Sans effet sur la sécurité. Verrou par clé prévu. |
| 33 | Étiquette Purview non affichée dans la réponse, contrairement à Copilot | Faible | §14.8.1. |
| 34 | Sauvegardes chiffrées non validées en lab | Moyenne | Exigence documentée en §15.5 ; obligatoire dès que §14 est mise en œuvre. |
| 35 | Variables d'environnement d'Ollama ignorées sans message : `OLLAMA_CONTEXT_LENGTH` (espace insécable), `OLLAMA_NUM_THREADS` (inexistante) | Faible | Réglages à passer par requête ou par Modelfile (`num_ctx`, `num_thread`). Vérifier la ligne de commande des processus `llama-server`. |
| 36 | Journal « Contexte étendu » : affiche la fenêtre demandée, pas les index réellement récupérés | Faible | A induit un diagnostic erroné en lab. Prévu avec la prochaine reconstruction. |
| 52 | Questions larges sensibles à la formulation ; copies non détectées quand les noms diffèrent ; environ 1 min 30 par question sur CPU | Moyenne | À reprendre au §10 : `bge-m3`, reranker, MMR. |
| 59 | Questions d'inventaire et entités mal retrouvées : limites qui relèvent du corpus (document d'index, page de synthèse) ; résumé d'un document entier à construire (§10.10) | Moyenne | Corpus et traitement dédié. |
| 61 | Recherche : une collection illisible est traitée comme absente, la réponse est construite sur des résultats partiels sans avertissement (constaté au redémarrage de Qdrant) | Moyenne | Même traitement que le test de cloisonnement : erreur explicite. |
| 62 | Clé de fusion des classements par empreinte du texte : deux extraits identiques de deux documents sont fusionnés. Identité par position mesurée et écartée (§10.6) ; à reconsidérer si le corpus ne contient plus de copies | Faible | Décision documentée. |
| 44 | Identité transmise par en-têtes simples entre Open WebUI et la RAG API | Faible en lab | Open WebUI peut transmettre un jeton signé (`ENABLE_FORWARD_USER_INFO_HEADERS`, `FORWARD_USER_INFO_HEADER_JWT_SECRET`). Passage en production. |

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

## Corrections documentaires v2.16.0 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §13.8.3 | Constats de gouvernance présentés avec leur origine dans le lab (essais antérieurs, pilote abandonné, documents de démonstration) | v2.16.0 |
| §14, §15 | Nouvelles sections : documents protégés par Purview, sécurité des données | v2.16.0 |
| Index, §8, procédures | « nLPD-compliant » remplacé par « conçu pour faciliter la conformité à la nLPD » | v2.16.0 |
| §9.4.4 | Journal archivé en `640` | v2.16.0 |


## Corrections documentaires v2.17.0 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §1.5 | Nouveau : disque de données chiffré et liens préparés avant le déploiement | v2.17.0 |
| §9.4 | Format du journal : empreinte HMAC, `verification: erreur` | v2.17.0 |
| §15.3.6 | Nouveau : secrets et clés sur le disque chiffré, piège de `docker compose restart` | v2.17.0 |
| §16 | Nouvelle section : contrôle du cloisonnement et durcissement | v2.17.0 |
| §17 | Nouvelle section : gouvernance | v2.17.1 |
| §3.4 | Versions figées et empreintes validées | v2.17.1 |
| §8.9, §8.8, §17.4 | Diversité des sources, réponses partielles, formulations, versions de documents | v2.17.2 |
| §10 | Nouvelle section : validation et performances sur GPU | v2.18.0 |
| §16, §10.6 | Correspondance exacte et erreurs explicites du test de cloisonnement ; clé de fusion mesurée | v2.18.2 |
| §16.8, §16.9 | Mise à jour d'Open WebUI revalidée, perte d'accès signalée | v2.17.1 |

---

*Dernière mise à jour : 7 octobre 2026.*
