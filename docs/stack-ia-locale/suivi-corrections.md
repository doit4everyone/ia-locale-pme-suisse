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
| doc.5 | `deploy.sh` rejoué une fois sur une VM Ubuntu 26.04 neuve (octobre 2026), ce qui a fait corriger les points 77 à 85 ; la version corrigée n'a pas encore été rejouée de bout en bout. Le redémarrage complet avec la stack en service (§15.3.5) et le choix de vLLM sur une VM neuve n'ont pas été rejoués | Moyenne | Rejouer `deploy.sh` corrigé sur une VM neuve avec le disque chiffré préparé (§1.5), puis redémarrer la VM stack en service et vérifier le retour seul. Refaire l'essai avec vLLM. |
| 30 | Recherche par mots-clés sensible aux accents et découpée sur les seules espaces (« règlement » ≠ « reglement ») | Moyenne | Constatée en §14.7.3. Normalisation des accents et de la ponctuation prévue dans `main.py` (§10). |
| 31 | Open WebUI envoie ses tâches d'arrière-plan (titres, suggestions) à `rag-api` : deux recherches complètes par question, une entrée de plus au journal nLPD | Moyenne | Réglage d'Open WebUI documenté en §14.8.2 et au §0 (étape 14). Sur une VM neuve : quatre appels par question avant le réglage (point 88), un seul après, plus un appel résiduel par conversation (point 89). |
| 32 | Cache des décisions Purview sans verrou : deux recherches simultanées interrogent Purview deux fois | Faible | Sans effet sur la sécurité. Verrou par clé prévu. |
| 33 | Étiquette Purview non affichée dans la réponse, contrairement à Copilot | Faible | §14.8.1. |
| 34 | Sauvegardes chiffrées non validées en lab : l'approche retenue (sauvegarde de la VM entière par l'outil de l'organisation, par exemple Veeam) est documentée en §15.5, mais la restauration (disque LUKS et TPM sur une VM restaurée, cohérence d'Open WebUI et de n8n) n'a pas été rejouée | Moyenne | Test de restauration décrit en §15.5 ; obligatoire dès que §14 est mise en œuvre. |
| 35 | Variables d'environnement d'Ollama ignorées sans message : `OLLAMA_CONTEXT_LENGTH` (espace insécable), `OLLAMA_NUM_THREADS` (inexistante) | Faible | Réglages à passer par requête ou par Modelfile (`num_ctx`, `num_thread`). Vérifier la ligne de commande des processus `llama-server`. |
| 36 | Journal « Contexte étendu » : affiche la fenêtre demandée, pas les index réellement récupérés | Faible | A induit un diagnostic erroné en lab. Prévu avec la prochaine reconstruction. |
| 52 | Questions larges sensibles à la formulation ; copies non détectées quand les noms diffèrent ; environ 1 min 30 par question sur CPU | Moyenne | À reprendre au §10 : `bge-m3`, reranker, MMR. |
| 59 | Questions d'inventaire et entités mal retrouvées : limites qui relèvent du corpus (document d'index, page de synthèse) ; résumé d'un document entier à construire (§10.10) | Moyenne | Corpus et traitement dédié. |
| 61 | Recherche : une collection illisible est traitée comme absente, la réponse est construite sur des résultats partiels sans avertissement (constaté au redémarrage de Qdrant) | Moyenne | Même traitement que le test de cloisonnement : erreur explicite. |
| 62 | Clé de fusion des classements par empreinte du texte : deux extraits identiques de deux documents sont fusionnés. Identité par position mesurée et écartée (§10.6) ; à reconsidérer si le corpus ne contient plus de copies | Faible | Décision documentée. |
| 65 | Réseau Docker de la VM sans adresse IPv4 : les conteneurs ne joignaient plus rien hors de la VM (`No route to host`), alors que la VM joignait le serveur de modèles. Cause non établie | Moyenne | Contournement documenté (§0, « En cas de problème ») : redémarrer Docker. Piste : un rechargement de la configuration réseau de la VM (systemd-networkd gère aussi les interfaces de Docker). À rechercher dans le journal système si le cas se reproduit. |
| 66 | WSL2 : arrêt à la fermeture du dernier terminal (constaté) ; démarrage au lancement de Windows et maintien en vie sans terminal non testés. Services systemd validés le 12 octobre 2026 | Faible | Hors WSL2, les services du §2.4.7 suffisent. Dans WSL2, garder un terminal Ubuntu ouvert, ou prévoir un serveur Linux dédié. |
| 67 | Synthèse du guide du helpdesk : 14 s mesurées au §10.9, 49 à 53 s en octobre, avec Ollama comme avec vLLM | Faible | Écart non expliqué : comparer la longueur des réponses et le contexte envoyé. |
| 72 | vLLM : échanges de la VM avec les serveurs de modèles en HTTP (clé d'API et questions en clair sur le réseau), modèles désignés par leur nom de dépôt, sans révision figée, code distant du modèle d'embedding exécuté (`--trust-remote-code`) | Moyenne pour la production | Documenté au §2.4.10. Réseau restreint ou chiffré, révisions figées et copie locale validée : non testés en lab. |
| 73 | Charge de vLLM : seules deux séries simultanées mesurées. Quatre questions simultanées, durées maximales (P95) et mémoire de la carte sous charge non mesurées | Faible | À mesurer avant d'annoncer une capacité (§2.4.10). |
| 74 | Ollama, deux séries simultanées : pour la question d'inventaire des règles YAML (I1), chaque série place un autre document en tête (`10-integrations-agents.md` pour l'une, `14_Registre_Personnel_2026.docx` pour l'autre) au lieu de `11-correlations-yaml.md` ; cause non établie (§10.12) | Faible | Comparer le contexte envoyé dans les deux séries. |
| 75 | Échelle de l'index : l'index BM25 est construit en mémoire dans `rag-api`, et le chargement lisait au plus 100 000 chunks par collection sans avertissement (corrigé en v2.20.3 par lecture paginée). Capacité réelle non mesurée : le lab compte environ 2 000 chunks, les estimations de mémoire du code (1 Mo pour 1 000 chunks) ne sont pas vérifiées. Qdrant garde ses réglages par défaut (vecteurs en mémoire, sans quantification) | Moyenne pour un corpus important | Test de montée en charge à faire : corpus synthétique de 20 000, 50 000 et 100 000 chunks, mémoire de `rag-api` et de Qdrant, temps de démarrage, durée d'une question. Au besoin : recherche par mots-clés dans Qdrant (vecteurs creux), `on_disk`, quantification. |
| 76 | Une erreur de rédaction renvoyée par Ollama (HTTP 500) s'affiche dans Open WebUI comme « Internal Server Error », sans cause lisible. Constaté le 13 octobre 2026 sur une même question, deux fois de suite, puis disparu sans cause établie ; le journal d'Ollama ne contenait aucune ligne d'erreur | Faible | Journaliser le corps de la réponse d'Ollama en cas d'erreur, et renvoyer à l'utilisateur un message lisible. |
| 89 | Open WebUI `v0.11.3` : un appel supplémentaire par conversation atteignait encore `rag-api` après les réglages de l'interface. Contrôle du 15 octobre 2026 : sur la VM neuve, la table `config` d'Open WebUI contenait encore `task.title.enable`, `task.tags.enable` et `task.follow_up.enable` à `true` (l'autocomplétion est à `false` par défaut) : le réglage de l'interface n'avait donc pas été enregistré, et l'appel résiduel n'est pas établi comme une tâche inconnue | Faible | Variables posées dans le Compose du dépôt (état initial d'une base neuve). À vérifier sur une base neuve (conteneur jetable), puis sur test-rag après réglage et enregistrement : relire la table `config`, compter les lignes du journal par question. Autres tâches actives par défaut, à examiner si un appel subsiste : génération de requêtes de recherche et de récupération (`task.query.*`). |
| 90 | Réponse non déterministe : à question identique et sources identiques, une réponse « Cette information ne figure pas dans les documents disponibles » une fois, une réponse complète citée une autre fois (VM neuve, octobre 2026). Le code considère un refus court comme ancré (`ancree=True`), donc le juge ne le détecte pas. Fréquence non mesurée | Moyenne | Mesurer : même question posée 20 fois, taux de refus à tort. Si confirmé : rejouer la rédaction quand les sources contiennent des passages pertinents mais que la réponse est un refus. |
| 91 | Procédure de changement du mot de passe de `svc-rag` : décrite (compte, fichier d'identifiants du partage, `.env`, connexion LDAP d'Open WebUI, §9.5.1) mais jamais validée de bout en bout | Faible | À valider ensemble, pas à pas, sur le lab, puis à consigner. |
| 92 | Un fichier nommé `TLS_KEY.txt` figure dans le corpus de test, avec un cas de cloisonnement dédié : nature du fichier (clé réelle, fichier factice) à confirmer | Faible | Lié au point 28 (détection de secrets dans le corpus). |
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


## Corrections documentaires v2.20.0 (octobre 2026)

| Section | Correction | Version |
|---|---|---|
| §0 | Réécrit : démarrage rapide avec Ollama ou vLLM, conventions pour les lecteurs non spécialistes, scripts récupérés par `git clone`, secrets générés automatiquement, contrôle de l'accès au serveur de modèles depuis le conteneur, dépannage du réseau Docker | v2.20.0 |
| §2 | Réécrit : le serveur de modèles, Ollama ou vLLM ; le contenu sur vLLM en mode CPU est retiré | v2.20.0 |
| §10.3, §10.4, §10.11, §10.12 | Piège de la synchronisation pendant une mesure, durées actuelles, moteur dans la configuration recommandée, comparaison mesurée d'Ollama et de vLLM | v2.20.0 |
| Index, §1, §3 | Les deux moteurs ; mémoire de la VM sans vLLM ; extraits du `.env` et du Compose | v2.20.0 |

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

*Dernière mise à jour : 12 octobre 2026.*
