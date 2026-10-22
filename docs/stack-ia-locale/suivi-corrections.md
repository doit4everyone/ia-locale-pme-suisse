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
| 63 | `deploy.sh` et `env.example` : fenêtre du juge fixée à 8 192 tokens, plus petite que celle du modèle principal, contrairement à la règle du §10.6. Portée à 16 384 | v2.20.0 | 2026-10-12 |
| 64 | §0 : contrôles de Qdrant (`curl`) sans la clé d'API obligatoire depuis la v2.16 (§15) ; `QDRANT_API_KEY`, `LOG_HMAC_KEY` et `MIP_TOKEN` absents des secrets à générer dans la procédure manuelle ; contrôle LDAP : option `-ZZ` (StartTLS) retirée d'une connexion déjà chiffrée en `ldaps://`, certificat de l'autorité indiqué explicitement (`LDAPTLS_CACERT`). Corrigé dans le §0 réécrit | v2.20.0 | 2026-10-12 |
| 68 | Juge d'Ollama : l'étiquette `qwen3:4b` raisonne toujours. Trois juges mesurés (4B raisonnant, 14B, `qwen3:4b-instruct`) ; `qwen3:4b-instruct` retenu (26 sur 30, 4,8 min contre 5,4 et 6,8 min). Étiquette, `env.example`, `deploy.sh`, valeurs par défaut du code et §2, §3, §10 alignés | v2.20.2 | 2026-10-12 |
| 69 | `OLLAMA_NUM_PARALLEL` mesuré : 2 ne tient pas sur 16 Go avec trois modèles (contexte réservé deux fois, modèles évincés et rechargés) ; avec 1, deux séries simultanées en 8,1 à 8,2 min contre 4,8 min seule. Recommandation du §2.2 appuyée par ces chiffres (§10.12). Au-delà de deux utilisateurs : non mesuré | v2.20.2 | 2026-10-12 |
| 70 | `deploy.sh` : un serveur vLLM qui répondait sans clé (code autre que 401) n'arrêtait pas le déploiement, il émettait un simple avertissement. Test rendu bloquant | v2.20.1 | 2026-10-12 |
| 71 | §3 : extraits du `.env` et du Compose sans `QDRANT_API_KEY` ; contrôles de la §3.6 (Qdrant, `/stats`), commandes de snapshot et de restauration sans la clé ni le jeton obligatoires ; exemples avec `changeme-api-token`. Alignés sur les fichiers du dépôt, valeurs lues dans le `.env` | v2.20.1 | 2026-10-12 |
| 77 | `deploy.sh` : à la confirmation, une réponse autre que « o » (un « 0 » tapé par erreur, par exemple) annulait le déploiement sans l'expliquer. Réponses « o », « oui », « y », « yes » acceptées ; toute autre réponse non reconnue est signalée | v2.20.3 | 2026-10-14 |
| 78 | n8n redémarrait en boucle (`EACCES`) sur une VM neuve : `n8n_data` doit appartenir à l'utilisateur 1000, et sur le disque chiffré le dossier est un lien (`chown` doit viser le vrai dossier). Ajouté à `deploy.sh`, au §0 (étape 6, « En cas de problème »), au §1.5 et au §3 | v2.20.3 | 2026-10-14 |
| 79 | `SP_EXCLUDE_DRIVES=Preservation Hold Library` sans apostrophes dans `env.example` : `source .env` échouait (« Hold: command not found »). Valeur entre apostrophes dans `env.example`, `deploy.sh` et `index.md` ; mise en garde au §0 | v2.20.3 | 2026-10-14 |
| 80 | §0 : `smbclient` sans `-W <DOMAINE>` échoue en `NT_STATUS_LOGON_FAILURE` sur un domaine Active Directory, mot de passe correct. Option ajoutée, cause documentée | v2.20.3 | 2026-10-14 |
| 81 | `deploy.sh` : l'environnement Python n'installait pas tous les paquets de l'indexation (`rank-bm25`, `smbprotocol` et autres absents). Liste alignée sur l'étape 11 du §0 | v2.20.3 | 2026-10-14 |
| 82 | `deploy.sh` : dossier de documentation par défaut différent de celui de l'indexeur, d'où des documents de documentation technique non reconnus comme tels à l'indexation. Valeur par défaut `DOIT4EVERYONE` alignée, invite précisée | v2.20.3 | 2026-10-14 |
| 83 | `deploy.sh` : annonçait « Déploiement terminé » sans contrôler l'état réel. Désormais : santé de la RAG API contrôlée depuis le conteneur (le port 8080 n'est pas publié), quatre conteneurs en `running` avec zéro redémarrage, liste des problèmes et sortie en erreur sinon | v2.20.3 | 2026-10-14 |
| 84 | `docker-compose.yml` : l'adresse annoncée par n8n était écrite en dur (`<IP-VM>`). Variable `N8N_WEBHOOK_URL` dans `env.example`, `docker-compose.yml`, §0 et §3 | v2.20.3 | 2026-10-14 |
| 85 | `api/anon_main.py` : sur un index vide (avant la première indexation), le journal affichait « Impossible de construire l'index : division by zero ». Message clair, sans erreur | v2.20.3 | 2026-10-14 |
| 86 | §0 étapes 2 et 4 : PKI à deux niveaux. Certificats listés puis exportés par empreinte (un filtre sur le nom et « le premier » sont ambigus, la racine figurant à plusieurs endroits), fichier de chaîne racine plus autorité intermédiaire, contrôle `openssl s_client` | v2.20.3 | 2026-10-14 |
| 87 | §0 étape 7 et §1.5 : `cp` refuse d'écrire dans le lien `.env` sans cible, et `sed -i` sur le lien le remplace par un fichier en clair sur le disque système. Commandes sur le vrai chemin ; `docker compose up -d` et non `restart` pour relire le `.env` | v2.20.3 | 2026-10-14 |
| 88 | §0 étape 14, §14.8.2, §16.8 : connexion à placer dans la section « API compatibles OpenAI » ; attributs LDAP distingués (courriel `userPrincipalName`, nom d'utilisateur `sAMAccountName`) ; désactivation des titres, étiquettes et questions de suivi (quatre appels par question dans le lab) ; §15.3.3 : contrôle `luksDump` qui n'affichait qu'un emplacement de clé sur deux ; §1.4 : versions de Docker relevées sur une VM neuve | v2.20.3 | 2026-10-14 |
| 89 | Open WebUI `v0.11.3` : appels supplémentaires à `rag-api` par conversation (titre, étiquettes, suggestions). Sur la VM neuve déployée avec le Compose du dépôt (variables d'état initial), une seule ligne au journal par question, y compris après des réglages de l'interface personnelle de l'utilisateur, qui sont sans effet sur ces appels | v2.20.4 | 2026-10-16 |
| 93 | `deploy.sh` : une coupure passagère vers `pypi.org` arrêtait le déploiement sur l'installation des paquets Python. `--retries 10 --timeout 60`, message d'erreur explicite ; le script est relançable | v2.20.4 | 2026-10-17 |
| 94 | DNS : un DNS public ajouté à côté de celui du domaine (contournement de la coupure du point 93) a fait échouer LDAP (`invalid server address`, refus 403 pour tous) et la lecture des droits (`NT_STATUS_INVALID_PARAMETER`) au deuxième redémarrage, `systemd-resolved` étant resté sur le serveur public. `deploy.sh` contrôle la résolution du contrôleur de domaine et du serveur de fichiers et signale un DNS public ; `acl_resolver.py` contrôle la résolution avant la première lecture ; §0 étape 4 réécrite (contrôler l'existant, ne rien modifier s'il convient, jamais de DNS public), §5.3.1, §15.3.5 et dépannage | v2.20.4 | 2026-10-17 |
| 95 | `acl_resolver.py` : un mot de passe refusé était réessayé sur chaque fichier. Le test du garde-fou avec un mot de passe faux a verrouillé `svc-rag` dans l'Active Directory au quatrième fichier, et avec lui la connexion de tous les utilisateurs. Arrêt au premier refus d'authentification (mot de passe, compte verrouillé, désactivé ou expiré), message `[GARDE-FOU]` aussi sur la sortie d'erreur (repris dans le courriel de synchronisation) ; test du garde-fou par un partage inexistant (§0 étape 16, §5.4.2b), déverrouillage documenté | v2.20.4 | 2026-10-17 |
| 96 | §3.7 : la procédure n'avait jamais pu fonctionner. Les snapshots étaient écrits dans le conteneur (`/qdrant/snapshots`), introuvables sur la VM et perdus à la recréation du conteneur ; la restauration était envoyée en `POST` (réponse `404` sans message) au lieu de `PUT` ; la suppression des données effaçait aussi les snapshots. `QDRANT__STORAGE__SNAPSHOTS_PATH` dans le Compose, copie hors de `qdrant_data` avant la suppression, remise en place, `PUT`. Restauration complète validée (76 et 1 616 extraits, droits et cloisonnement identiques) | v2.20.4 | 2026-10-17 |
| 97 | Avertissement « le contrôle automatique n'a pas pu rattacher toutes les affirmations » à tort sur une réponse correcte : le modèle avait recopié un nom de fichier sans son accent, et le contrôle exact des citations le jugeait inexistant. `normaliser_citations` remplace une citation par le nom réel quand, sans accents ni casse, elle correspond à un seul document fourni ; le contrôle exact (`verifier_citations`) est inchangé. Le journal indique le contrôle qui a conclu (`controle_echoue`) ; quatre tests unitaires (`test_citations.py`) | v2.20.4 | 2026-10-16 |
| 98 | n8n (§0 étape 15) : les identifiants des workflows importés ne correspondent à rien et doivent être sélectionnés à nouveau dans chaque nœud ; jeton d'administration dans un identifiant Header Auth restreint au domaine `rag-api`, et non à recopier dans le nœud ; expéditeur égal à la boîte authentifiée (`SendAsDenied` sinon) ; destinataire interne ; test du courriel par épingle sur le nœud amont. Fuseau `Europe/Zurich` (n8n comptait en America/New_York) ; `WEBHOOK_URL`, variable lue par n8n, à la place de `N8N_WEBHOOK_URL` dans le Compose (rectifié en v2.21.1, point 117 : c'est `N8N_WEBHOOK_URL` qui fait foi depuis n8n 2.35) ; mention publicitaire de n8n retirée du courriel de rappel | v2.20.4 | 2026-10-17 |
| 99 | `DOCUMENTATION_PATHS` : la valeur par défaut était le dossier du lab (`DOIT4EVERYONE`). Vide par défaut (tout le partage dans `documents`), finalité des deux collections expliquée par `deploy.sh`, `env.example` et §0 ; présence du dossier contrôlée après le montage ; chemin avec sous-dossier refusé. §5.9, règle 1 : la description d'un sous-dossier homonyme routé vers `documentation` ne correspondait pas au code (comparaison du début du chemin), corrigée | v2.20.4 | 2026-10-17 |
| 100 | Partage monté en écriture (`rw`) par le §0 et le §5, en lecture seule (`ro`) par `deploy.sh`. Lecture seule partout ; `deploy.sh` signale un montage existant en écriture | v2.20.4 | 2026-10-17 |
| 101 | Open WebUI (§0 étape 14) : libellés LDAP de l'interface en français relevés ; réglages d'administration et réglages personnels distingués | v2.20.4 | 2026-10-16 |
| 102 | `deploy.sh` : première indexation et synchronisation des droits proposées en fin de déploiement (facultatives, journalisées, un échec n'annule pas le déploiement) ; tests des citations lancés ; résumé final corrigé (étapes n8n, snapshot, coquilles) | v2.20.4 | 2026-10-17 |
| 103 | Rapports et journaux (`/var/log/rag`, rapports des scripts) créés lisibles par tous les comptes de la VM (`644`). Créés en `640` (`umask 027`). Les fichiers existants gardent leurs droits : `chmod 640 /var/log/rag/*.json /var/log/rag/*.jsonl` | v2.20.4 | 2026-10-17 |
| 104 | État de santé de `rag-api` absent de `docker ps` : contrôle de santé ajouté au Compose ; §0 étape 9 et §15.3.5 précisent que `qdrant` et `n8n` restent en `Up` sans mention | v2.20.4 | 2026-10-17 |
| 105 | Open WebUI (port 3001) et n8n (port 5678) publiés sur le réseau en HTTP : mots de passe LDAP, sessions et questions en clair. Frontal Nginx en HTTPS, seul service qui publie des ports (80, 443, 5678), sous un nom DNS propre à la stack ; certificat de l'autorité interne ou auto-signé ; WebSocket, réponses au fil de l'eau, délai de 600 s ; n8n configuré derrière un frontal (`N8N_PROTOCOL`, `N8N_PROXY_HOPS`, `WEBHOOK_URL`, cookie sécurisé). Procédures d'obtention et de renouvellement du certificat (§9.8) | v2.21.0 | 2026-10-18 |
| 106 | Requêtes par adresse IP ou par un autre nom servies comme les autres. Serveurs par défaut : connexion fermée sans réponse en HTTP (`return 444`), négociation TLS refusée en HTTPS (`ssl_reject_handshake`) ; `/sante` exposé pour la supervision, réponse minimale. Testé hors lab (Nginx 1.24), puis validé sur la VM au rejeu du 19 octobre 2026 (`000`, code 35, `301`) | v2.21.0 | 2026-10-18 |
| 107 | Secrets d'exemple : un simple avertissement au démarrage depuis la 2.17.0 (point 45). La RAG API refuse de démarrer sur un secret vide, une valeur d'exemple (`changeme…`, gabarit `<…>`), un jeton de moins de 32 caractères ou deux jetons identiques ; `deploy.sh` refuse un jeton saisi trop court | v2.21.0 | 2026-10-17 |
| 108 | `/query` acceptait `API_TOKEN` et répondait au nom du compte déclaré dans la requête (`user_id`) : tout détenteur du jeton d'Open WebUI pouvait se faire passer pour un autre utilisateur. Réservé à `ADMIN_TOKEN` ; `test_cloisonnement.py` adapté | v2.21.0 | 2026-10-18 |
| 109 | Images désignées par leur seul numéro de version, dépendances Python sans version : une reconstruction pouvait installer un autre contenu. Images figées par empreinte (`@sha256`), image de base de la RAG API figée, `requirements.txt` relevé par `pip freeze` ; Nginx sur la branche stable 1.30. Deux constructions identiques, aucun téléchargement au `pull` | v2.21.0 | 2026-10-17 |
| 110 | Open WebUI invitait à installer une nouvelle version (bannière v0.12.3), contraire à la règle du §16.8. `ENABLE_VERSION_UPDATE_CHECK=false` ; revue des versions inscrite à l'audit périodique (§17.6) | v2.21.0 | 2026-10-17 |
| 111 | Aucune alerte si la stack s'arrête, si la synchronisation ne tourne plus ou si le certificat expire. Contrôles définis (§16.10) ; nœud n8n « Signal supervision (Push) », désactivé par défaut, qui ne bloque jamais le courriel d'erreur ; exemple avec Uptime Kuma validé (sonde `/sante` avec échéance du certificat, sonde Push, courriel d'alerte reçu) | v2.21.0 | 2026-10-18 |
| 112 | `deploy.sh` : nom de la stack demandé et contrôlé (DNS vers la VM) ; certificat fourni contrôlé (clé, nom, échéance) ou auto-signé généré, auto-signé existant signalé ; `/etc/rag-tls` sur le disque chiffré ; configuration de Nginx au nom de la stack ; `OWUI_JWT_SECRET` généré ; cinq conteneurs et `/sante` contrôlés à travers Nginx ; adresses finales en HTTPS | v2.21.0 | 2026-10-18 |
| 113 | `tests-apres-modification.md` : les questions de test transmettaient l'identité par un en-tête simple, refusé depuis l'identité signée (point 44). Les commandes signent un jeton avec `OWUI_JWT_SECRET`, comme Open WebUI | v2.21.0 | 2026-10-18 |
| 117 | `WEBHOOK_URL` dépréciée depuis n8n 2.35 (alias de `N8N_WEBHOOK_URL`, avertissement au démarrage) ; le point 98 avait fait le changement dans le mauvais sens. `N8N_WEBHOOK_URL` dans le Compose, disponible depuis n8n 2.30 (documentation de n8n) | v2.21.1 | 2026-10-18 |
| 118 | Ancien point doc.3. `N8N_BASIC_AUTH_*` dans le Compose et le `.env`, sans effet depuis n8n 1.0 : fausse impression de protection. Retirées ; compte propriétaire de n8n à créer dès la première ouverture (§7.1.1, §0 étape 15) | v2.21.1 | 2026-10-18 |
| 119 | Fin de `deploy.sh` : `/sante` contrôlé avec `curl -k`, qui prouve que Nginx répond mais pas que le certificat est de confiance. Avec un certificat de l'autorité interne, second contrôle avec la chaîne (`--cacert`) | v2.21.1 | 2026-10-18 |
| 120 | Portée du chiffrement non dite : le TLS s'arrête à Nginx. Tableau des liaisons au §9.8.1, liaison vers le serveur de modèles en clair rappelée (point 72). « Toutes les images figées » inexact : le reranker facultatif ne l'est pas ; formulation corrigée | v2.21.1 | 2026-10-18 |
| 125 | `deploy.sh` réécrivait `/root/rag-stack/.env` sans contrôle : relancé sur une installation en service, il remplaçait tous les jetons et effaçait les réglages Microsoft 365, alors que le §0 le disait « relançable sans dommage ». Avant toute modification, le script signale un `.env` existant, demande confirmation (refus par défaut, rien n'est modifié) et en garde une copie datée en `600`. Une procédure de mise à jour d'une installation existante reste à écrire (passage de la VM Microsoft 365 en 2.21) | v2.21.1 | 2026-10-18 |
| 126 | `s10/mesure_s10.py` et `s10/charge_s10.py` transmettaient l'identité par l'en-tête simple, refusé depuis la 2.21.0 (403 à chaque question) : les campagnes du §10 et le test de charge ne pouvaient plus tourner. Les deux scripts signent un jeton avec `OWUI_JWT_SECRET`, comme Open WebUI | v2.21.1 | 2026-10-18 |
| 127 | §9.8.4 : la chaîne de Nginx se construit avec `ad-subca.pem`, que le §0 ne créait pas (il ne produit que `ad-chain.pem`). Constaté au rejeu du 19 octobre 2026. Le §0 (étape 4) garde l'intermédiaire en `ad-subca.pem` ; le §9.8.4 donne la commande d'extraction pour une installation antérieure et le cas d'une autorité à un seul niveau | v2.21.2 | 2026-10-19 |
| 128 | `deploy.sh` : le garde-fou du `.env` (point 125) intervenait après les seize questions, qu'il fallait remplir pour rien en cas de refus. Placé au début du script, avant toute question | v2.21.2 | 2026-10-19 |
| 129 | Résumé final de `deploy.sh` : le compte propriétaire de n8n, à créer tout de suite (sinon n'importe quel poste peut le créer), n'y figurait pas. Étape 0 ajoutée | v2.21.2 | 2026-10-19 |
| 130 | Rapports d'`indexer.py` et d'`acl_resolver.py` lancés à la main : sans `--rapport`, écrits dans `/root/rag-pipeline`, sur le disque système non chiffré (noms de fichiers et groupes autorisés). Le résumé de `deploy.sh` et la checklist du §0 donnent `--rapport /var/log/rag/...` | v2.21.2 | 2026-10-19 |
| 131 | n8n 2.36.9 annonce que les paquets communautaires non vérifiés seront refusés par défaut dans une version future. `N8N_UNVERIFIED_PACKAGES_ENABLED=false` fixé dès maintenant dans le Compose | v2.21.2 | 2026-10-19 |
| 10 | Recherche par mots-clés (BM25) : les candidats étaient autorisés sur les droits mémorisés dans l'index, construit au démarrage et en fin de synchronisation. Un droit retiré dans Qdrant restait valable par ce chemin jusqu'à la reconstruction (pendant la synchronisation, ou jusqu'à une heure après un `acl_resolver.py` lancé à la main) ; un document supprimé restait trouvable. Gravité **sous-estimée** jusqu'ici (« faible ») : la relecture des voisins, censée arrêter l'extrait, le remettait quand elle revenait vide (`fenetre or extraits`), c'est-à-dire précisément quand le droit avait été retiré ; sans extension du contexte, aucune relecture. Signalé par une revue externe du code. Chaque candidat est relu dans Qdrant par son identifiant et ses droits contrôlés sur cette lecture (`revalider_bm25`), refus par défaut ; repli supprimé. Fuite reproduite sur le code de la 2.21.2 et absente après correction : `test_revalidation_bm25.py`, 11 tests. Sur le vrai Qdrant de la VM de test (`test_revocation_bm25.py`, §16.5.1) : FUITE en 2.21.2 par les deux chemins, OK en 2.21.3 ; test de non-divulgation inchangé (70 OK, 2 INFO) | v2.21.3 | 2026-10-20 |
| 133 | `deploy.sh` : un échec des tests unitaires des droits sur la recherche par mots-clés (`test_revalidation_bm25.py`) n'affichait qu'un avertissement, et le déploiement se terminait normalement. Signalé par une seconde revue externe. L'échec arrête la RAG API et termine le script en erreur (« Déploiement incomplet ») ; vérifié en simulation | v2.21.4 | 2026-10-20 |
| 134 | `search_qdrant`, `revalider_bm25`, `etendre_complements` : sans groupes, les contrôles d'accès étaient sautés. Aucun chemin exposé (`/query` et `/v1` refusent ce cas avant la recherche), mais une route future qui l'oublierait aurait servi une recherche sans filtre. Signalé par une seconde revue externe. Refus dans les fonctions elles-mêmes : 403 pour la recherche, aucun résultat pour les deux autres ; trois tests unitaires ajoutés (14 au total, tous OK sur la VM de test) | v2.21.4 | 2026-10-20 |
| 135 | `acl_resolver.py` : une erreur de Qdrant pendant l'écriture des droits renvoyait 0, lu comme « non indexé » ; code de sortie 0, synchronisation réussie, aucune alerte, anciens droits conservés dans Qdrant. Même défaut pour la fermeture d'un fichier aux ACL illisibles, la suppression des extraits d'un fichier effacé et la lecture des orphelins. Signalé par une troisième revue externe ; reproduit sur le code de la 2.21.4 (Qdrant simulé). Trois issues distinctes, seconde tentative, code 2 et rapport ; synchronisation en échec et alerte ; documents retirés de la recherche jusqu'au prochain passage sans échec, liste gardée sur disque ; même règle pour les fichiers SharePoint en erreur (§16.5.2). VM de test : 12 tests unitaires OK, synchronisation réelle réussie ; échec réel d'écriture non provoqué | v2.21.5 | 2026-10-20 |
| 136 | `/admin/sync` cherchait le statut `non_indexé` dans le rapport des droits, qui écrit `non_indexe` : les fichiers non indexés n'étaient jamais comptés en quarantaine. Les deux graphies sont acceptées | v2.21.5 | 2026-10-20 |
| 137 | `deploy.sh` : un fichier de test de sécurité absent sautait le contrôle sans le dire. `test_revalidation_bm25.py` et `test_echec_droits.py` sont obligatoires : absent ou en échec, RAG API arrêtée et déploiement en erreur ; vérifié en simulation | v2.21.5 | 2026-10-20 |
| 138 | `sp_indexer.py` : un fichier déjà indexé qui dépassait ensuite `SP_MAX_FILE_MB` sortait sans relecture des droits ni suppression : anciens extraits et anciens droits conservés, sans alerte. Extraits supprimés ; suppression refusée = fichier en erreur, retiré de la recherche. Signalé par une quatrième revue externe | v2.21.6 | 2026-10-20 |
| 139 | RAG API (2.21.5) : un passage avec le code 2 remplaçait la liste des documents retirés ; une lecture des orphelins en échec, seul incident, la vidait et rendait visibles des documents retirés. Seul un passage complet retire des documents de la liste ; un passage incomplet ajoute les orphelins probables, ou tout le partage si leur inventaire échoue ; site ou bibliothèque SharePoint illisible retiré par périmètre. Signalé par une quatrième revue externe | v2.21.6 | 2026-10-20 |
| 140 | Registre `acl_bloques.json` : écriture non atomique ; absent ou illisible au démarrage, la RAG API démarrait sans rien retirer. Écriture atomique avec incident signalé ; registre créé vide par `deploy.sh` ; absent ou illisible, questions refusées (503) jusqu'à une synchronisation complète. Option `ACL_INCERTAIN_FERME` pour suspendre une origine après un passage abandonné ou interrompu. Signalé par une quatrième revue externe. VM de test : refus au démarrage sans registre, levée par une synchronisation complète, registre relu après redémarrage | v2.21.6 | 2026-10-20 |
| 141 | RAG API (2.21.6) : un échec d'écriture du registre était signalé mais les questions restaient servies ; après un redémarrage, l'ancien registre était relu comme valide, sans les documents retirés depuis. Questions refusées tant que le registre n'est pas écrit ; marqueur « synchronisation des droits en cours » posé avant toute modification des droits et retiré après l'écriture du résultat ; présent au démarrage, questions refusées jusqu'à une synchronisation terminée ; marqueur impossible à écrire, droits non synchronisés. Dossier synchronisé après le renommage. Signalé par une cinquième revue externe. VM de test : synchronisation interrompue simulée, questions refusées puis servies après une synchronisation | v2.21.7 | 2026-10-20 |
| 142 | Registre lisible mais mal formé (`{}`, chaîne au lieu d'une liste, version inconnue) accepté sans contrôle. Validation stricte du schéma ; toute anomalie = état inconnu, questions refusées. Signalé par une cinquième revue externe | v2.21.7 | 2026-10-20 |
| 143 | `ACL_INCERTAIN_FERME` valait 0 par défaut : après un passage abandonné ou interrompu, les derniers droits connus restaient appliqués. Défaut à 1 : origine suspendue jusqu'à un passage complet ; 0 reste possible par choix documenté | v2.21.7 | 2026-10-20 |
| 144 | Synchronisations arrêtées (n8n arrêté, workflow désactivé) : les derniers droits connus restaient appliqués sans limite de durée, sans alerte. Âge maximal des droits (`ACL_AGE_MAX_HEURES`, 3 heures par défaut) : date de la dernière synchronisation complète enregistrée dans le registre (version 3), mise à jour seulement si toutes les origines ont abouti sans passage incertain et si le registre est écrit ; au-delà, date absente ou dans le futur, questions refusées. Questions servies pendant une synchronisation normale : choix documenté (§5.4). Signalé par une sixième revue externe | v2.21.8 | 2026-10-21 |
| 145 | Marqueur « synchronisation des droits en cours » posé après l'indexation : une indexation interrompue n'était pas couverte. Marqueur posé avant ; droits non garantis, indexation sautée. Signalé par une sixième revue externe | v2.21.8 | 2026-10-21 |
| 146 | `deploy.sh` recréait un registre vide si celui-ci manquait sur une installation existante, ce qui effaçait la liste des documents retirés. Registre créé seulement sur une installation neuve ; installation existante sans registre, arrêt en erreur. Signalé par une sixième revue externe | v2.21.8 | 2026-10-21 |
| 147 | `deploy.sh` : un test de sécurité absent du dossier source n'était pas copié, sans erreur ; une ancienne copie restée dans `/root/rag-pipeline` était alors lancée à sa place. Présence obligatoire dans le dossier source et copie contrôlée. Signalé par une sixième revue externe | v2.21.8 | 2026-10-21 |
| 148 | `/health` répondait « ok » même avec des droits périmés ou inconnus : la supervision ne voyait rien. État des droits dans la réponse, toujours en HTTP 200. Signalé par une sixième revue externe | v2.21.8 | 2026-10-21 |
| 149 | `s10/charge_s10.py` comparait les médianes de paliers qui ne posaient pas les mêmes questions (« ×14,8 » à 8 questions, sans rapport avec la charge). Mesure de référence de chaque question seule, gain de chaque série ; compte rendu au §10.12 | v2.21.8 | 2026-10-21 |
| 150 | Procédures de mise à jour des Releases 2.21.2 à 2.21.7 : seul `main.py` était remplacé, jamais le `docker-compose.yml`. Sur la VM de test, le Compose était resté en 2.21.1 : `ACL_INCERTAIN_FERME` n'était pas transmis (valeur par défaut du code, 1, appliquée) et une valeur d'`ACL_AGE_MAX_HEURES` passée à Compose était ignorée sans message. Remplacement du Compose dans la procédure de la 2.21.8, avec comparaison préalable | v2.21.8 | 2026-10-21 |
| 151 | Verdict du juge lu sur la seule clé `ancree` : un juge qui répond « ancrée » tout en citant une affirmation non sourcée laissait passer la réponse comme vérifiée. Mesuré le 22 octobre 2026 (`s10/mesure_juge.py`) : le juge 4B d'Ollama l'a fait 14 fois sur 72 jugements de versions falsifiées, soit un fait inventé sur trois accepté. Liste non vide = réponse non ancrée ; aucune des 210 réponses réelles jugées n'est bloquée par la règle | v2.21.9 | 2026-10-22 |
| 152 | Réponse de moins de 200 caractères contenant « ne figure pas dans les documents » acceptée sans juge : un fait inventé suivi de cette phrase échappait à la vérification. Seule la phrase de refus exacte est acceptée sans juge. Trouvé à la relecture du code après le point 151 | v2.21.9 | 2026-10-22 |
| 153 | Même relecture : verdict de Purview lu avec `bool()` (une chaîne « false » aurait autorisé ; `mip-service` renvoie un booléen, sans conséquence constatée) ; valeur par défaut « ancrée » dans la lecture du résultat du juge (sans conséquence, toutes les branches la fixent). Lecture stricte et défaut « non ancrée » | v2.21.9 | 2026-10-22 |
| 44 | Identité transmise par en-têtes simples entre Open WebUI et la RAG API : quiconque connaissait `API_TOKEN` pouvait écrire l'adresse d'un autre compte. Open WebUI signe l'identité (`FORWARD_USER_INFO_HEADER_JWT_SECRET`, jeton HS256 de cinq minutes), la RAG API vérifie signature, émetteur et échéance, et ignore les en-têtes simples (403). Validé : compte de test avec ses 17 groupes, en-tête simple refusé, cloisonnement 6/6 | v2.21.0 | 2026-10-18 |

---

## Points ouverts

| Point | Description | Priorité | Remarque |
|---|---|---|---|
| 7 | Groundedness check ne bloque pas sur `/v1` | Choix délibéré | Documenté dans §8.3 depuis v2.9.0. Bloquer casserait la compatibilité OpenAI. Depuis v2.17.0, `/v1` signale dans la réponse une vérification impossible ou un ancrage non établi. |
| 14 | ACL par noms plutôt que par SIDs | Moyenne | Le masque des droits est corrigé et les permissions du partage sont contrôlées (v2.17.0, §16.5). Reste le passage aux SID, avec le groupe principal (auth.1) : **le masque d'abord, le groupe principal ensuite**, sinon un fichier en écriture seule pour « Utilisateurs du domaine » devient lisible par tout le domaine. |
| auth.1 | Groupe principal AD absent de `memberOf` | Moyenne | Ajouter `primaryGroupID` dans `auth.py`. À mesurer d'abord sur le partage. À faire **après** la correction du masque (faite en v2.17.0), voir §16.5. |
| auth.2 | Identités intégrées (`AUTORITE NT\Utilisateurs authentifiés`) dans `autorises[]` sans être dans les groupes LDAP | Moyenne | Fichiers concernés invisibles. Décision à prendre : ignorer ou injecter dans `get_user_groups`. |
| 27 | `indexer.py` : un fichier chiffré par Purview sur le partage serait compté comme « vide », sans signalement explicite | Faible | Aucun fichier chiffré sur le partage du lab à ce jour. Détection prévue, comme dans `sp_indexer.py`. |
| 28 | Aucune détection de secrets dans le corpus indexé | Faible | Un fichier nommé comme une clé TLS a été trouvé dans un dossier indexé du lab. À traiter par la gouvernance (inventaire, exclusion), pas par l'indexeur seul. |
| 29 | Courriel de quarantaine sans statut par fichier | Faible | Le message présente les deux causes possibles (point 22), mais `main.py` ne transmet que les noms. Prévu avec la prochaine reconstruction (§10). |
| doc.5 | `deploy.sh` rejoué trois fois sur une VM Ubuntu 26.04 neuve (octobre 2026), en dernier lieu en version 2.21.1 le 19 octobre 2026, avec Ollama : déploiement, certificat de l'autorité interne, indexation, droits, Open WebUI, n8n, cloisonnement (72 verdicts, aucune fuite), usurpation refusée, garde-fou par un partage inexistant, ports exposés, redémarrage et supervision validés ; corrections en 2.21.2 (points 127 à 131). Non couverts par ce rejeu : le contrôle `--cacert` de fin de déploiement (point 119, le certificat était encore auto-signé), le refus du garde-fou du `.env` à la relance (points 125 et 128), le choix de vLLM sur une VM neuve | Faible | Rejouer `deploy.sh` 2.21.2 avec un certificat fourni et avec vLLM, et le relancer une seconde fois en répondant **n** au garde-fou. |
| 30 | Recherche par mots-clés sensible aux accents et découpée sur les seules espaces (« règlement » ≠ « reglement ») | Moyenne | Constatée en §14.7.3. Normalisation des accents et de la ponctuation prévue dans `main.py` (§10). |
| 31 | Open WebUI envoie ses tâches d'arrière-plan (titres, suggestions) à `rag-api` : deux recherches complètes par question, une entrée de plus au journal nLPD | Faible | Réglage d'Open WebUI documenté en §14.8.2 et au §0 (étape 14). Sur une VM neuve : quatre appels par question avant le réglage (point 88), un seul avec le Compose du dépôt (point 89, corrigé en v2.20.4). Reste à surveiller à chaque mise à jour d'Open WebUI. |
| 32 | Cache des décisions Purview sans verrou : deux recherches simultanées interrogent Purview deux fois | Faible | Sans effet sur la sécurité. Verrou par clé prévu. |
| 33 | Étiquette Purview non affichée dans la réponse, contrairement à Copilot | Faible | §14.8.1. |
| 34 | Sauvegardes chiffrées non validées en lab : l'approche retenue (sauvegarde de la VM entière par l'outil de l'organisation, par exemple Veeam) est documentée en §15.5, mais la restauration (disque LUKS et TPM sur une VM restaurée, cohérence d'Open WebUI et de n8n) n'a pas été rejouée | Moyenne | Choix assumé en v2.21.0 : la sauvegarde relève de l'organisation, le guide la documente sans la mettre en place. Test de restauration décrit en §15.5 ; obligatoire dès que §14 est mise en œuvre. |
| 35 | Variables d'environnement d'Ollama ignorées sans message : `OLLAMA_CONTEXT_LENGTH` (espace insécable), `OLLAMA_NUM_THREADS` (inexistante) | Faible | Réglages à passer par requête ou par Modelfile (`num_ctx`, `num_thread`). Vérifier la ligne de commande des processus `llama-server`. |
| 36 | Journal « Contexte étendu » : affiche la fenêtre demandée, pas les index réellement récupérés | Faible | A induit un diagnostic erroné en lab. Prévu avec la prochaine reconstruction. |
| 52 | Questions larges sensibles à la formulation ; copies non détectées quand les noms diffèrent ; environ 1 min 30 par question sur CPU | Moyenne | À reprendre au §10 : `bge-m3`, reranker, MMR. |
| 59 | Questions d'inventaire et entités mal retrouvées : limites qui relèvent du corpus (document d'index, page de synthèse) ; résumé d'un document entier à construire (§10.10) | Moyenne | Corpus et traitement dédié. |
| 61 | Recherche : une collection illisible est traitée comme absente, la réponse est construite sur des résultats partiels sans avertissement (constaté au redémarrage de Qdrant) | Moyenne | Même traitement que le test de cloisonnement : erreur explicite. |
| 62 | Clé de fusion des classements par empreinte du texte : deux extraits identiques de deux documents sont fusionnés. Identité par position mesurée et écartée (§10.6) ; à reconsidérer si le corpus ne contient plus de copies | Faible | Décision documentée. |
| 65 | Réseau Docker de la VM sans adresse IPv4 : les conteneurs ne joignaient plus rien hors de la VM (`No route to host`), alors que la VM joignait le serveur de modèles. Cause non établie | Moyenne | Contournement documenté (§0, « En cas de problème ») : redémarrer Docker. Piste : un rechargement de la configuration réseau de la VM (systemd-networkd gère aussi les interfaces de Docker). À rechercher dans le journal système si le cas se reproduit. |
| 66 | WSL2 : arrêt à la fermeture du dernier terminal (constaté) ; démarrage au lancement de Windows et maintien en vie sans terminal non testés. Services systemd validés le 12 octobre 2026 | Faible | Hors WSL2, les services du §2.4.7 suffisent. Dans WSL2, garder un terminal Ubuntu ouvert, ou prévoir un serveur Linux dédié. |
| 67 | Synthèse du guide du helpdesk : 14 s mesurées au §10.9, 49 à 53 s en octobre, avec Ollama comme avec vLLM | Faible | Écart non expliqué : comparer la longueur des réponses et le contexte envoyé. |
| 72 | vLLM : échanges avec le serveur de modèles en HTTP ; modèles désignés par leur nom de dépôt, sans révision figée ; code distant du modèle d'embedding exécuté (`--trust-remote-code`) | Moyenne pour la production | Sur un serveur unique, cas visé par le guide, la liaison ne quitte pas la machine : pas de chiffrement à ajouter (décision du 19 octobre 2026, §9.8.1). Sur deux machines séparées : réseau dédié, tunnel ou TLS natif de vLLM, non testés. Révisions figées et copie locale validée : non testées. |
| 132 | Le moteur (vLLM `--host 0.0.0.0`, Ollama) écoute sur le réseau : n'importe quel poste peut l'interroger directement, sans journal ni cloisonnement (§16.7). Nécessaire dans le lab (VM vers l'hôte Windows), inutile sur un serveur unique | Moyenne pour la production | Sur un serveur Ubuntu ou un DGX Spark : faire écouter le moteur pour la seule machine, en restant joignable par le conteneur `rag-api`. Adresse d'écoute et règles à déterminer et tester avant de les documenter. |
| 73 | Charge de vLLM : seules deux séries simultanées mesurées. Quatre questions simultanées, durées maximales (P95) et mémoire de la carte sous charge non mesurées | Faible | À mesurer avant d'annoncer une capacité (§2.4.10). |
| 74 | Ollama, deux séries simultanées : pour la question d'inventaire des règles YAML (I1), chaque série place un autre document en tête (`10-integrations-agents.md` pour l'une, `14_Registre_Personnel_2026.docx` pour l'autre) au lieu de `11-correlations-yaml.md` ; cause non établie (§10.12) | Faible | Comparer le contexte envoyé dans les deux séries. |
| 75 | Échelle de l'index : l'index BM25 est construit en mémoire dans `rag-api`, et le chargement lisait au plus 100 000 chunks par collection sans avertissement (corrigé en v2.20.3 par lecture paginée). Capacité réelle non mesurée : le lab compte environ 2 000 chunks, les estimations de mémoire du code (1 Mo pour 1 000 chunks) ne sont pas vérifiées. Qdrant garde ses réglages par défaut (vecteurs en mémoire, sans quantification) | Moyenne pour un corpus important | Test de montée en charge à faire : corpus synthétique de 20 000, 50 000 et 100 000 chunks, injecté directement dans Qdrant (vecteurs aléatoires de la bonne dimension : la mesure porte sur l'index BM25, pas sur la qualité), sur la VM de test, depuis un snapshot ; mémoire de `rag-api` et de Qdrant, durée de reconstruction, temps de démarrage, durée d'une question, perte de rappel du point 123. Au besoin : recherche par mots-clés dans Qdrant (vecteurs creux), `on_disk`, quantification. |
| 76 | Une erreur de rédaction renvoyée par Ollama (HTTP 500) s'affiche dans Open WebUI comme « Internal Server Error », sans cause lisible. Constaté le 13 octobre 2026 sur une même question, deux fois de suite, puis disparu sans cause établie ; le journal d'Ollama ne contenait aucune ligne d'erreur | Faible | Journaliser le corps de la réponse d'Ollama en cas d'erreur, et renvoyer à l'utilisateur un message lisible. |
| 90 | Réponse non déterministe : à question identique et sources identiques, une réponse « Cette information ne figure pas dans les documents disponibles » une fois, une réponse complète citée une autre fois (VM neuve, octobre 2026). Le code considère un refus court comme ancré (`ancree=True`), donc le juge ne le détecte pas. Fréquence non mesurée | Moyenne | Mesurer : même question posée 20 fois, taux de refus à tort. Si confirmé : rejouer la rédaction quand les sources contiennent des passages pertinents mais que la réponse est un refus. |
| 91 | Procédure de changement du mot de passe de `svc-rag` : décrite (compte, fichier d'identifiants du partage, `.env`, connexion LDAP d'Open WebUI, §9.5.1) mais jamais validée de bout en bout | Faible | À valider ensemble, pas à pas, sur le lab, puis à consigner. |
| 92 | Un fichier nommé `TLS_KEY.txt` figure dans le corpus de test, avec un cas de cloisonnement dédié : nature du fichier (clé réelle, fichier factice) à confirmer | Faible | Lié au point 28 (détection de secrets dans le corpus). |
| 114 | Certificat de Nginx : la procédure §9.8.4 et §9.8.6 a été rejouée telle qu'écrite le 19 octobre 2026 (auto-signé remplacé par le certificat de la sous-CA, sans recréer de conteneur) ; le renouvellement d'un certificat proche de l'échéance n'a pas encore eu lieu | Faible | Même procédure. À consigner au premier renouvellement réel. |
| 115 | Ports de Nginx (80, 443, 5678) ouverts à tout le réseau ; n8n, réservé aux administrateurs, est joignable par tous les postes jusqu'à son écran de connexion | Moyenne pour la production | Restriction par la chaîne `DOCKER-USER` ou par le pare-feu du réseau, non testée (§9.1.2). |
| 121 | `deploy.sh` accepte un certificat fourni qui ne porte pas le nom de la stack ou qui expire bientôt (avertissement seulement), parce que l'auto-signé reste permis pour les essais | Faible en lab, moyenne pour la production | Idée de la revue externe : un mode production qui refuse le déploiement si le nom, l'échéance ou la chaîne ne conviennent pas. Non retenu pour l'instant, pour ne pas ajouter d'option ; à reconsidérer avec la section « Du lab à la production ». |
| 122 | Index BM25 : la reconstruction (`build_bm25_index`, au démarrage et après chaque synchronisation) s'exécute dans la boucle de la RAG API. Pendant sa durée, plus aucune requête n'est servie (questions, `/health`, supervision). Invisible sur le corpus du lab (1 692 extraits) ; durée non mesurée sur un gros corpus | Moyenne pour un corpus important | Reconstruire dans un fil séparé (`asyncio.to_thread`) puis remplacer index et extraits d'un seul coup ; journaliser la durée. À mesurer avec le point 75. |
| 123 | Index BM25 : le filtre des droits est appliqué après le classement, sur les 2 × top_k meilleurs extraits seulement. Sur un gros corpus, un utilisateur aux droits restreints peut ne recevoir aucun résultat par mots-clés alors que des extraits autorisés existent plus bas. Pas de fuite, une perte de rappel invisible | Moyenne pour un corpus important | Mesurer avec un corpus synthétique où la plupart des extraits sont réservés à un autre groupe. Solution durable : recherche par mots-clés dans Qdrant (vecteurs creux), avec le filtre des droits pendant la recherche (§10). |
| 124 | Index BM25 : un échec de reconstruction (mémoire insuffisante, Qdrant indisponible) laisse l'index vide avec un simple avertissement ; la recherche continue en vectoriel seul sans autre signal | Faible | Signaler l'échec dans le rapport de synchronisation (courriel n8n) ; limite mémoire de `rag-api` à fixer d'après les mesures du point 75. |
| 116 | Exemple de supervision (§16.10.2) : interface d'Uptime Kuma en HTTP, clé Push en clair dans l'URL du nœud n8n et dans les journaux | Faible | Limites documentées. À traiter par l'outil de supervision de l'organisation en production. |

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


## Corrections documentaires v2.20.0 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §0 | Réécrit : démarrage rapide avec Ollama ou vLLM, conventions pour les lecteurs non spécialistes, scripts récupérés par `git clone`, secrets générés automatiquement, contrôle de l'accès au serveur de modèles depuis le conteneur, dépannage du réseau Docker | v2.20.0 |
| §2 | Réécrit : le serveur de modèles, Ollama ou vLLM ; le contenu sur vLLM en mode CPU est retiré | v2.20.0 |
| §10.3, §10.4, §10.11, §10.12 | Piège de la synchronisation pendant une mesure, durées actuelles, moteur dans la configuration recommandée, comparaison mesurée d'Ollama et de vLLM | v2.20.0 |
| Index, §1, §3 | Les deux moteurs ; mémoire de la VM sans vLLM ; extraits du `.env` et du Compose | v2.20.0 |

---

## Corrections documentaires v2.21.9 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §10.12 | « Une piste, non testée » remplacée par la mesure : juge partagé abandonné ; ce que le juge détecte | v2.21.9 |
| §16.6 | Verdict du juge incohérent | v2.21.9 |
| §16.5.2 | « valeurs par défaut (1 et 3 heures) » précisé | v2.21.9 |

---

## Corrections documentaires v2.21.8 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §5.4 | Fenêtre de péremption des droits : latence normale et fenêtre supplémentaire bornée à 3 heures | v2.21.8 |
| §16.5.2, §16.10 | Compléments de la 2.21.8, mise à jour, synchronisation manuelle, limites ; état des droits dans `/sante` ; checklist | v2.21.8 |
| §10.12 | Mesure de charge de une à huit questions simultanées avec vLLM ; verdict nuancé au-delà de deux questions | v2.21.8 |
| §3 | `ACL_AGE_MAX_HEURES` dans l'extrait du Compose | v2.21.8 |
| §16.5.2 | Mise à jour : remplacement du `docker-compose.yml`, omis par les procédures de la 2.21.2 à la 2.21.7 | v2.21.8 |

---

## Corrections documentaires v2.21.7 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §16.5.2 | Compléments de la 2.21.7, limites revues (redémarrage pendant une synchronisation, disque plein, alerte Push) ; checklist | v2.21.7 |
| §3 | `ACL_INCERTAIN_FERME` à 1 par défaut dans l'extrait du Compose | v2.21.7 |

---

## Corrections documentaires v2.21.6 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §16.5.2 | Compléments de la 2.21.6, limites revues ; checklist | v2.21.6 |
| Sommaire du guide | Dernière Release à utiliser pour toutes les parties ; v2.12.0 présentée comme référence historique | v2.21.6 |
| §3, §13 | `ACL_INCERTAIN_FERME` dans l'extrait du Compose ; `SP_MAX_FILE_MB` commenté | v2.21.6 |

---

## Corrections documentaires v2.21.5 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §16.5.2 (nouveau) | Échecs d'écriture des droits : défaut, correction, conduite en cas d'alerte, limites ; checklist | v2.21.5 |
| §8 | Encadré : principes et essais historiques, configuration retenue au §10 | v2.21.5 |
| Sommaire du guide | Plus de consigne pour retirer le filtre des droits dans le code ; groupe large en lecture, sauf « Utilisateurs du domaine » (auth.1) | v2.21.5 |
| §5.4 | Renvoi au §16.5.2 | v2.21.5 |

---

## Corrections documentaires v2.21.4 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §16.5.1 | Compléments de la 2.21.4 ; ce que la correction ne change pas (fenêtre de péremption du §5.4) ; checklist à 14 tests | v2.21.4 |

---

## Corrections documentaires v2.21.3 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §8.6 | Les droits des candidats par mots-clés sont relus dans Qdrant | v2.21.3 |
| §16 | Statut ; §16.2, ce que le test de non-divulgation ne voit pas ; §16.5.1 (nouveau), seconde faille ; checklist | v2.21.3 |
| Page d'accueil, `README.md`, sommaire | Présentation mise à jour (18 sections, GPU, sécurité 2.21, lab et non production, rejeu du 19 octobre, prochaines étapes), publiée avec la 2.21.3 | v2.21.3 |

---

## Corrections documentaires v2.21.2 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §0 | Statut (rejeu du 19 octobre 2026) ; étape 4 (`ad-subca.pem`) ; encadré `deploy.sh` ; garde-fou validé ; `--rapport` dans la checklist | v2.21.2 |
| §7.1.1 | Paquets communautaires non vérifiés refusés | v2.21.2 |
| §9 | Statuts ; §9.8.1 (liaison vers le serveur de modèles sur un serveur unique) ; §9.8.4 (intermédiaire, autorité à un niveau) ; §9.8.6 (procédure rejouée) | v2.21.2 |
| §16.6 | Contrôle d'usurpation rejoué tel qu'écrit | v2.21.2 |

---

## Corrections documentaires v2.21.1 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §0, §7.1.1 | Compte propriétaire de n8n ; `N8N_BASIC_AUTH_*` retirées | v2.21.1 |
| §3.2, §3.4, §16.8 | Extraits du `.env` et du Compose ; images du déploiement standard figées, reranker excepté | v2.21.1 |
| §9.8.1 | `N8N_WEBHOOK_URL` ; ce que le frontal chiffre et ne chiffre pas | v2.21.1 |
| §17.9 | « A/R » sans retour à la ligne | v2.21.1 |

---

## Corrections documentaires v2.21.0 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §0 | Statut ; nom DNS et certificat dans les prérequis ; étape 6 (dossier `nginx`) ; étape 7 (`OWUI_JWT_SECRET`, `RAG_FQDN`, point 5 : nom de la stack, configuration de Nginx, certificat) ; étape 9 (cinq conteneurs, `/sante`) ; étapes 14 et 15 (adresses HTTPS, signal de supervision) ; étape 16 et checklist (frontal, refus par adresse IP, identité signée, ports, échéance du certificat) | v2.21.0 |
| §1.5 | Lien `/etc/rag-tls` vers le disque chiffré | v2.21.0 |
| §3 | `.env` (secrets refusés, `OWUI_JWT_SECRET`, `LOG_HMAC_KEY`, `RAG_FQDN`) ; `requirements.txt` et `Dockerfile` figés ; Compose (empreintes, n8n derrière Nginx, identité signée, service `nginx`) ; validation (`/sante`, `/query` par `ADMIN_TOKEN`) | v2.21.0 |
| §5.6.1, §5.7 | Identité signée par Open WebUI | v2.21.0 |
| §7.1.1, §8.3, §14.6.2 | Adresse HTTPS de n8n ; schéma ; en-tête d'identité | v2.21.0 |
| Sommaire | Schéma, avertissements, descriptions de §9, §16 et §17 | v2.21.0 |
| §9 | §9.1.2 et §9.1.5 (ports après Nginx) ; §9.8 nouvelle (frontal HTTPS, DNS, certificat auto-signé ou de l'autorité interne, postes clients, renouvellement, refus, HSTS, noms multiples, exposition) ; checklist devenue §9.9 | v2.21.0 |
| §15.5 | Choix assumé : la sauvegarde relève de l'organisation ; `/etc/rag-tls` | v2.21.0 |
| §16 | §16.6 (secrets refusés, identité signée, contrôle d'usurpation, `/query`) ; §16.7 ; §16.8 (empreintes, mise à jour d'une image, branche de Nginx, revue des versions) ; §16.10 nouvelle (supervision externe, exemple Uptime Kuma) ; checklist devenue §16.11 | v2.21.0 |
| §17 | §17.3 (identité signée, certificat de la stack, certificats de l'autorité) ; §17.6 (revue des versions, essai de la supervision) ; §17.7 en tableau d'état ; §17.9 nouvelle (matrice RACI, modèle à adapter) | v2.21.0 |

---

## Corrections documentaires v2.20.4 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §0 | Second rejeu sur VM neuve : statut ; étape 2 (`Select-Object -First 1` après le filtre d'empreinte) ; étape 4 (DNS : contrôler l'existant, jamais de DNS public) ; étape 5 (lecture seule) ; étape 6 (`deploy.sh`, `test_citations.py`) ; étape 7 (`DOCUMENTATION_PATHS`) ; étape 9 (état de santé) ; étape 11 (`pip` avec reprises) ; étape 14 (libellés LDAP en français, réglages personnels) ; étape 15 réécrite (n8n) ; étape 16 (garde-fou sans verrouillage, citations, redémarrage, snapshot à froid) ; dépannage (DNS, compte verrouillé, téléchargement Python) | v2.20.4 |
| §3.4, §3.7 | Compose (snapshots, fuseau de n8n, état de santé) ; §3.7 réécrite et validée (point 96) | v2.20.4 |
| §5.3, §5.4.2b, §5.9 | DNS, montage en lecture seule, arrêt au premier refus d'authentification et test du garde-fou, collection `documentation` | v2.20.4 |
| §15.3.5 | Contrôle des noms du domaine après redémarrage, état de santé attendu | v2.20.4 |

---

## Corrections documentaires v2.20.3 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| `main.py` | Chargement des chunks pour l'index BM25 par pages jusqu'à épuisement (plafond silencieux de 100 000 chunks par collection supprimé) | v2.20.3 |
| §10.1 | Note : la mémoire disponible de la carte dépend de la carte qui rend le bureau (14,8 Go avec l'affichage sur la carte, environ 16,2 Go après le passage du bureau sur le processeur graphique intégré), avec la commande de mesure | v2.20.3 |
| §0, §1, §3, §14, §15.3, §16 | Rejeu sur VM neuve : PKI à deux niveaux (étapes 2 et 4), `.env` et `n8n_data` derrière des liens, `smbclient -W`, connexion et attributs LDAP d'Open WebUI, tâches d'arrière-plan, contrôle `luksDump`, versions de Docker, résultat du test de cloisonnement (72 verdicts, 0 fuite), dépannage (points 77 à 88) | v2.20.3 |
| `deploy.sh`, `docker-compose.yml`, `env.example`, `index.md`, `main.py` | Confirmation par « o », `chown` de `n8n_data`, apostrophes de `SP_EXCLUDE_DRIVES`, paquets Python, dossier de documentation, contrôles de fin de déploiement, `N8N_WEBHOOK_URL`, index BM25 vide | v2.20.3 |
| §15.5 | Réécrite : sauvegarde de la VM entière par l'outil de l'organisation, quatre points propres à la stack (cohérence, disque chiffré et TPM à la restauration, éléments hors de la VM, chiffrement et rétention), ce qui se reconstruit, test de restauration à rejouer. Remplace la mention de `restic` | v2.20.3 |

---

## Corrections documentaires v2.20.2 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §10.12 | Trois juges d'Ollama mesurés, `OLLAMA_NUM_PARALLEL` 1 et 2, deux séries simultanées avec Ollama comparées à vLLM ; les tableaux de la comparaison de départ précisent qu'ils ont été relevés avec le juge `qwen3:4b` | v2.20.2 |
| §0, §2, §3, §10.2, §10.11 | Juge `qwen3:4b-instruct` pour Ollama | v2.20.2 |

---

## Corrections documentaires v2.20.1 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §2.4.10 | Nouvelle section : transport en HTTP, modèles et code distant non figés, charge non mesurée, avant une mise en production | v2.20.1 |
| §3 | Clé d'API Qdrant dans les extraits du `.env` et du Compose ; contrôles, snapshots et restauration avec la clé et les jetons lus dans le `.env` | v2.20.1 |

---

*Dernière mise à jour : 17 octobre 2026.*
