---
title: "§16 Contrôle du cloisonnement et durcissement | Guide de déploiement stack IA locale"
description: "Test de non-divulgation automatisé, contrôle du cloisonnement après chaque synchronisation avec alerte, correction du masque des droits NTFS, durcissement de la RAG API, d'Open WebUI et de n8n à la suite d'une revue externe, versions figées et supervision externe."
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

# §16 Contrôle du cloisonnement et durcissement

[Retour au sommaire](index.md) | [Section précédente : §15 Sécurité des données](section-15-securite-donnees.md) | [Section suivante : §17 Gouvernance](section-17-gouvernance.md)

**Statut :** validé en lab sur VM-RAG-LAB, octobre 2026 : 40 cas de cloisonnement conformes, une faille du calcul des droits NTFS reproduite puis corrigée, alerte prouvée par une fuite simulée. Compléments de la 2.21.0 (refus des secrets d'exemple, identité signée, versions figées, supervision externe) validés sur la VM de test, octobre 2026.

---

> **Ce que cette section documente :** jusqu'ici, le cloisonnement était vérifié par des matrices de questions posées à la main, compte par compte (§9, §13, §14). Cette section les remplace par un **test automatisé**, qui vérifie directement les filtres d'accès, en quelques secondes, et qui s'exécute **après chaque synchronisation** avec une alerte par courriel. Elle documente aussi la première faille trouvée grâce à lui, et le durcissement de la stack mené à la suite d'une revue externe du dépôt.

---

## §16.1 Pourquoi automatiser

Une matrice manuelle prouve que le cloisonnement fonctionnait **le jour du test**. Or ses causes de défaillance changent sans prévenir : un administrateur modifie les droits d'un dossier, un groupe change de membres, un document est déplacé, un script est mis à jour. Le contrôle doit donc être rejoué à chaque changement possible, c'est-à-dire à chaque synchronisation.

Poser des questions au modèle ne s'y prête pas : sur CPU, les 36 combinaisons du lab demandaient une vingtaine de minutes, et le résultat dépendait du **classement de la recherche**. Un compte qui a accès à presque tout le corpus ne voyait pas toujours remonter un petit document de test, noyé parmi des centaines de chunks : ce n'était pas un refus, mais le test ne pouvait pas le distinguer d'un refus.

## §16.2 Vérifier l'accès, pas la réponse

L'endpoint d'administration `/admin/verifier-acces` reçoit un utilisateur et un document, et applique **exactement les filtres de la recherche**, dans le même ordre, avec les mêmes fonctions :

1. le filtre Qdrant sur `autorises[]` (permissions NTFS ou SharePoint) ;
2. les refus explicites (DENY) ;
3. les droits de l'étiquette Purview (§14).

Il renvoie trois nombres : les chunks du document dans l'index, ceux qui restent après la première condition, et ceux qui restent après Purview. Pas de classement, pas de génération, pas de juge. On voit ainsi **quelle condition** a retiré le document.

## §16.3 Le test de non-divulgation

`test_cloisonnement.py` lit un fichier de cas : des comptes de test, et pour chaque document visé, l'accès attendu par compte.

```json
{
  "comptes": ["direction@votre-domaine.ch", "comptable@votre-domaine.ch", "client@votre-domaine.ch"],
  "cas": [
    {"id": "FIN-1", "question": "Quel code de vérification commence par FIN- ?",
     "document": "Test_RAG_Finances.docx", "secret": "4827",
     "attendu": {"direction@votre-domaine.ch": true, "comptable@votre-domaine.ch": true,
                 "client@votre-domaine.ch": false}}
  ]
}
```

| Mode | Ce qu'il vérifie | Durée (lab, CPU) |
|---|---|---|
| `--mode acces` (défaut) | **Le cloisonnement**, par `/admin/verifier-acces` : déterministe | Quelques secondes pour 40 cas |
| `--mode complet` | La chaîne entière par `/query`, recherche et modèle compris | 20 à 30 minutes pour 36 cas |

| Verdict | Signification |
|---|---|
| OK | Conforme |
| **FUITE** | Document interdit accessible : le script se termine en erreur |
| REFUS À TORT | Document autorisé inaccessible : défaut, mais dans le sens sûr |
| ABSENT | Document non indexé : le cas ne teste rien |
| ERREUR | Qdrant injoignable (HTTP 503), droits non résolus (403), ou cas ambigu (400) : aucun verdict n'est rendu |

Un cas désigne son document par son **nom de fichier exact**, ou par son **chemin complet** quand plusieurs documents portent le même nom. Un nom partagé est refusé comme ambigu : un cas qui évalue deux documents à la fois ne prouve rien sur aucun des deux. Dans le lab, ce contrôle a révélé que le cas du guide du helpdesk portait sur deux exemplaires, l'un à la racine du site (ouvert à tous), l'autre dans le site de l'équipe IT (restreint) : il passait grâce au premier, sans dire lequel. Le cas a été précisé, et le second exemplaire a reçu son propre cas. Une correspondance partielle (`"correspondance": "fragment"`) reste possible cas par cas, pour le lab.

Une **panne de Qdrant** produit une erreur, jamais un verdict : vérifié en arrêtant Qdrant pendant le test (quatre `ERREUR`, HTTP 503). Auparavant, une erreur de lecture était traitée comme une collection absente.

```bash
docker exec rag-api python3 /rag-pipeline/test_cloisonnement.py /rag-pipeline/cas_cloisonnement.json
```

Les cas du lab reprennent les matrices de §9 (DENY nominatif), §13 (quatre modes de partage SharePoint, site ouvert à tous) et §14 (trois étiquettes chiffrées), plus le cas de §16.5. Résultat : **40 sur 40**, puis **44 sur 44** avec le cas ajouté en v2.18.2, et la colonne « après ACL » montre, par exemple, le document Finances chiffré passer la première condition pour le comptable (il a accès au site), puis être retiré par Purview seul.

**Rejeu sur un déploiement neuf (octobre 2026).** Le test a été rejoué, en mode accès, sur la VM déployée à partir de zéro pour valider le §0 : 70 documents indexés (1692 extraits), droits résolus, `/admin/sync`, puis 9 comptes de test sur 8 cas. Résultat : **72 verdicts, dont 70 `OK`, 2 `INFO` et 0 `FUITE`**. Les deux `INFO` sont deux cas dont l'attendu avait été laissé à « ? » faute de savoir le résultat juste : le test les a tranchés (refus pour un compte de la comptabilité sur un budget, accès pour un compte client sur un contrat). Ce rejeu ne porte pas sur le mode complet, qui interroge le modèle et dure 20 à 30 minutes.

Le mode complet garde un intérêt : il mesure la qualité de la recherche. Ses cas « manqués » (document autorisé absent des sources) ne sont pas un sujet de sécurité, mais un indicateur pour le §10.

## §16.4 Le contrôle après chaque synchronisation

À la fin de `/admin/sync`, la RAG API rejoue tous les cas du fichier `CAS_CLOISONNEMENT` (par défaut `/rag-pipeline/cas_cloisonnement.json`) et ajoute au rapport :
- `cloisonnement` : nombre de cas conformes, listes des fuites, refus à tort, cas invalides et erreurs ;
- `cloisonnement_alerte` : vrai dès qu'un cas n'est pas conforme.

Sans fichier de cas, le contrôle est simplement absent. Le workflow n8n de synchronisation déclenche le courriel si `cloisonnement_alerte` est vrai, avec un sujet prioritaire en cas de fuite, et la consigne d'arrêter le service tant que la cause n'est pas comprise.

**Contre-épreuve, faite en lab** : en remettant l'ancienne version du calcul des droits (§16.5), la synchronisation suivante a envoyé le courriel « FUITE DE CLOISONNEMENT », avec le cas et le compte concernés. Un contrôle qui n'a jamais sonné n'est pas un contrôle prouvé.

## §16.5 Une faille réelle : le masque des droits NTFS

Une ACL NTFS est une liste d'entrées : qui, autorisé ou refusé, et quels droits (le masque). `smbcacls` les affiche ainsi :

```
ACL:DOMAINE\GRP-RAG-Indexation:ALLOWED/0x0/READ
ACL:DOMAINE\Comptabilité:ALLOWED/0x0/0x00100116
```

Jusqu'à la v2.16, `acl_resolver.py` ne lisait que le début de la ligne : **toute entrée `ALLOWED` valait autorisation**, quel que soit le masque. Or `0x00100116` accorde l'écriture des données, mais **pas leur lecture**.

**Le cas concret : la boîte de dépôt.** Un dossier où les collaborateurs peuvent déposer des fichiers sans lire ceux des autres : candidatures, notes de frais, signalements. Windows refuse la lecture ; le RAG l'accordait.

**Reproduction en lab** : un fichier avec trois entrées, administration en contrôle total, groupe d'indexation en lecture, groupe Comptabilité en écriture seule (`icacls <fichier> /grant "DOMAINE\Comptabilité:(W)"`). Le test a sorti **FUITE** pour le compte comptable.

**Correction** : une entrée `ALLOWED` n'est retenue que si son masque accorde la lecture du contenu (`READ`, `CHANGE`, `FULL`, une combinaison de lettres contenant `R`, ou le bit de lecture des données en hexadécimal). Un format inconnu vaut refus. Les entrées héritables seulement (`IO`) sont ignorées. Les refus (`DENIED`) sont tous conservés, quel que soit leur masque : un refus partiel rend un fichier invisible à tort, jamais visible à tort. Le rapport de synchronisation compte les entrées ignorées. Après correction : **40 sur 40**, sans qu'aucun des 36 autres cas ne change.

> **Deux défauts qui se masquaient.** Le premier essai, avec « Utilisateurs du domaine » en écriture seule, n'a révélé aucune fuite : ce groupe est le **groupe principal** des comptes AD, absent de l'attribut `memberOf` que lit la RAG API. Le défaut du masque était bien là, compensé par un second défaut. Corriger d'abord le groupe principal aurait rendu le fichier lisible par tout le domaine. **L'ordre des corrections compte : le masque d'abord, le groupe principal ensuite.** C'est le genre de piège qu'un test automatisé révèle, et qu'une correction faite sans lui aurait déclenché.

**Permissions du partage.** Sous Windows, l'accès réseau exige aussi les droits du partage. Le RAG ne lit que les NTFS : il suppose un partage ouvert largement (« Tout le monde » ou « Utilisateurs authentifiés »), la restriction étant portée par les NTFS, ce qui est la configuration habituelle. Lire les droits d'un partage exige en général des droits d'administration sur le serveur, que le compte d'indexation ne doit pas avoir. `Set-AccesIndexationRAG.ps1 -Verifier` affiche donc ces droits depuis le serveur, et signale un partage restreint (code de sortie 3).

## §16.6 Durcissement de la RAG API

| Point | Avant | Après |
|---|---|---|
| Mot de passe SMB | Sur la ligne de commande de `smbcacls`, visible dans la liste des processus | Fichier d'identifiants temporaire en mémoire (`-A`), lisible par le seul processus |
| Juge en échec | Réponse considérée comme ancrée | Considérée comme non vérifiée : `/query` la bloque, le journal indique `verification: erreur` |
| Réponse non vérifiée dans Open WebUI | Rendue sans signal | Rendue, avec une mention invitant à vérifier dans les sources |
| Citations | Comparées par sous-chaîne | Correspondance exacte sur le nom de fichier |
| Deux documents de même nom | Lien vers le premier trouvé | Les deux emplacements sont indiqués |
| Panne de Qdrant ou de l'embedding | « Information absente » | Erreur 503 explicite |
| `/stats`, `/health` | `/stats` ouvert, `/health` révèle l'adresse du moteur | `/stats` réservé à l'administration, `/health` minimal |
| Empreinte des questions au journal | SHA-256 tronqué : une question courte se retrouve par dictionnaire | HMAC avec une clé secrète (`LOG_HMAC_KEY`) |
| Valeurs d'exemple (`changeme`) | Aucun signal | Avertissement au démarrage (2.17.0), puis **démarrage refusé** (2.21.0) |
| Identité de l'utilisateur | En-têtes simples `X-OpenWebUI-User-*`, que tout détenteur d'`API_TOKEN` pouvait écrire | Jeton signé par Open WebUI, vérifié par la RAG API (2.21.0) |
| `/query` | Accepté avec `API_TOKEN` | Réservé à `ADMIN_TOKEN` (2.21.0) |

Le jeton d'administration du lab était d'ailleurs resté à sa valeur d'exemple : la stack fonctionnait sans rien signaler. L'avertissement aurait suffi à le voir ; depuis la 2.21.0, la RAG API refuse de démarrer.

**Secrets refusés au démarrage (2.21.0).** La RAG API s'arrête (code de sortie 1) si l'un de ses secrets est vide, garde une valeur d'exemple (`changeme…`, ou un gabarit entier comme `<mot-de-passe>`), est trop court (32 caractères au moins pour les jetons et clés générés), ou si deux jetons sont identiques (`API_TOKEN`, `ADMIN_TOKEN`, `OWUI_JWT_SECRET`). Le journal dit lequel :

```bash
docker logs rag-api 2>&1 | grep SÉCURITÉ
# [SÉCURITÉ] ADMIN_TOKEN garde une valeur d'exemple
# [SÉCURITÉ] Démarrage refusé. Corriger le .env (jetons : openssl rand -hex 32), puis docker compose up -d rag-api
```

Les mots de passe de `svc-rag` (`LDAP_BIND_PWD`, `SMB_PASSWORD`) ne sont contrôlés que pour le vide et la valeur d'exemple : leur longueur dépend de la politique de l'annuaire. `deploy.sh` génère tous les jetons ; le refus concerne surtout une installation à la main ou un `.env` repris d'un essai.

**Identité signée (2.21.0).** La RAG API résout les droits d'après l'adresse de l'utilisateur transmise par Open WebUI. Jusqu'à la 2.20, cette adresse arrivait dans un en-tête simple : un client qui connaissait `API_TOKEN` pouvait y écrire l'adresse d'un autre compte et obtenir ses droits. Désormais, Open WebUI signe l'identité avec un secret partagé (`OWUI_JWT_SECRET` du `.env`, passé à Open WebUI par `FORWARD_USER_INFO_HEADER_JWT_SECRET`) : jeton HS256, émetteur `open-webui`, valable cinq minutes. La RAG API vérifie la signature, l'émetteur et l'échéance, et ignore les en-têtes simples. Sans jeton valide : refus (403).

Contrôle d'usurpation, sur la VM (une seule ligne) :

```bash
docker exec rag-api python3 -c "import os,json,urllib.request as u; d=json.dumps({'model':'rag-api','messages':[{'role':'user','content':'test'}]}).encode(); r=u.Request('http://localhost:8080/v1/chat/completions',data=d,headers={'Authorization':'Bearer '+os.environ['API_TOKEN'],'Content-Type':'application/json','X-OpenWebUI-User-Email':'<COMPTE>@votre-domaine.ch'}); print(u.urlopen(r).status)"
# Attendu, en dernière ligne : urllib.error.HTTPError: HTTP Error 403: Forbidden
docker logs rag-api 2>&1 | grep "identité non signée" | tail -1
```

> **Validé sur la VM de test, octobre 2026 (2.21.0) :** une question posée dans Open WebUI obtient sa réponse, avec les 17 groupes du compte de test ; un en-tête d'identité simple est refusé (403) ; `/query` avec `API_TOKEN` est refusé (401) ; `test_cloisonnement.py`, qui passe désormais par `ADMIN_TOKEN`, donne 6 cas conformes sur 6. Le test d'usurpation a été mené avec une commande équivalente ; la ligne ci-dessus est à rejouer telle quelle.

## §16.7 Open WebUI, n8n et le moteur d'inférence

**Open WebUI** : depuis la 2.21.0, Open WebUI ne publie plus de port ; il n'est joignable que par Nginx, en HTTPS (§9.8). Il signe l'identité transmise à la RAG API (§16.6). `ENABLE_VERSION_UPDATE_CHECK=false` supprime la vérification des nouvelles versions et la bannière qui invite à mettre à jour (§16.8).

Dans **Réglages d'administration** → **Connexions**, désactiver **API Ollama** et **Direct connexions**. Les utilisateurs ne voient plus que le modèle de la RAG API, et ne peuvent pas ajouter eux-mêmes l'adresse d'Ollama. Faire ce réglage dans l'interface : la variable `ENABLE_OLLAMA_API=false`, placée dans le Compose du dépôt, n'est lue qu'au **premier** démarrage d'Open WebUI, qui garde ensuite ses réglages dans sa base.

**Le moteur d'inférence** : Ollama écoute sur le réseau pour que la VM puisse l'atteindre, donc n'importe quel poste peut l'interroger directement. Pas de fuite du corpus par ce chemin (le modèle n'a pas les documents), mais ni journal ni contrôle. Le pare-feu du serveur d'inférence doit n'accepter le port 11434 que depuis la VM de la stack. Si la VM est derrière un routeur qui traduit les adresses, le serveur voit l'adresse du routeur : la restriction se complète alors sur le routeur. Vérification : depuis un autre poste, `curl -m 5 http://<serveur>:11434/api/tags` doit échouer.

**n8n** : depuis la 2.21.0, n8n ne publie plus de port ; il est joint par `https://<RAG_FQDN>:5678`, à travers Nginx (§9.8). Le jeton d'administration n'est plus écrit dans les nœuds HTTP. Un identifiant unique de type **Header Auth** (*Name* `Authorization`, *Value* `Bearer <jeton>`, domaine autorisé : `rag-api`) est utilisé par les nœuds de synchronisation et de synthèse Teams, avec « Send Headers » désactivé. Le jeton n'apparaît plus dans les workflows ni dans leurs exports, et sa rotation se fait en un seul endroit :

```bash
cd /root/rag-stack
sed -i "s/^ADMIN_TOKEN=.*/ADMIN_TOKEN=$(openssl rand -hex 32)/" .env
docker compose up -d rag-api                      # recrée le conteneur (§15.3.6)
grep '^ADMIN_TOKEN=' .env | cut -d= -f2           # à reporter dans l'identifiant n8n
```

## §16.8 Une mise à jour se revalide : le cas d'Open WebUI

En figeant les versions (§3.4), le lab est passé d'une construction de développement d'Open WebUI (tag `main`) à la version publiée `v0.11.3`. Deux effets, invisibles sans revalidation :

| Constat | Cause | Correction |
|---|---|---|
| Plus aucune réponse affichée, alors que la RAG API répondait (code 200) | La version publiée demande la réponse **en flux** et n'affiche rien si elle reçoit un objet JSON simple ; la RAG API ignorait la demande | La RAG API respecte désormais la demande de flux. La réponse est calculée en entier, contrôles compris, puis envoyée en un seul fragment : un vrai flux mot par mot enverrait le texte avant le contrôle d'ancrage |
| Plusieurs requêtes par question | Tâches d'arrière-plan d'Open WebUI (titres, étiquettes, questions de suivi) adressées au modèle de la conversation : quatre appels par question dans le lab | Désactivées par le Compose du dépôt pour un déploiement neuf, ou dans **Interface** pour une base existante (§14.8.2, §0 étape 14) ; elles multiplient le calcul et polluent le journal nLPD, sans fausser les réponses |

La leçon tient en une règle : **une mise à jour d'Open WebUI, de n8n ou de Qdrant ne s'installe pas sur une invitation à mettre à jour**. Elle se fait sur décision, puis se revalide : connexions d'Open WebUI, transmission de l'identité (`[AUTH] /v1` dans les journaux), test de cloisonnement, synchronisation.

**Versions figées jusqu'à l'octet (2.21.0).** Un numéro de version (`tag`) peut être republié sur Docker Hub avec un autre contenu. Le `docker-compose.yml` fixe donc chaque image par son numéro **et** son empreinte (`image: nginx:1.30.6-alpine@sha256:…`) : Docker refuse une image dont le contenu diffère. L'image de base de la RAG API (`python:3.11-slim`) est figée de la même façon dans le `Dockerfile`, et `api/requirements.txt` fixe toutes les dépendances Python à la version exacte, relevées par `pip freeze` dans le conteneur validé. Validé sur la VM de test : deux constructions successives donnent la même liste de paquets, et un `docker compose pull` ne télécharge rien.

**Mettre à jour une image**, Nginx par exemple, quand une nouvelle version stable est publiée (`nginx.org`, rubrique des versions) :

```bash
# 1. Télécharger la nouvelle version et relever son empreinte
docker pull nginx:<VERSION>-alpine
docker image inspect --format '{{index .RepoDigests 0}}' nginx:<VERSION>-alpine
# → nginx@sha256:<EMPREINTE>

# 2. Reporter numéro et empreinte dans /root/rag-stack/docker-compose.yml :
#    image: nginx:<VERSION>-alpine@sha256:<EMPREINTE>

# 3. Recréer le seul conteneur concerné, puis contrôler
cd /root/rag-stack
docker compose up -d nginx
docker exec nginx nginx -v
curl --cacert /etc/ssl/certs/ad-chain.pem https://<RAG_FQDN>/sante
```

En cas de problème, remettre l'ancienne ligne `image:` et relancer `docker compose up -d nginx`. Même démarche pour Qdrant, n8n et Open WebUI, avec la revalidation ci-dessus. Pour les dépendances Python, modifier la version dans `requirements.txt`, reconstruire (`docker compose build rag-api`), revalider, puis relever la liste complète par `docker exec rag-api pip freeze`.

> **Branche suivie pour Nginx :** la branche *stable* (paire : 1.30 en octobre 2026). Une branche stable n'est plus maintenue quand la suivante sort : la 1.28 ne reçoit plus de correctifs depuis la sortie de la 1.30. Validé sur la VM de test avec la 1.30.6.

**Revue des versions.** Figer n'est pas oublier : les correctifs de sécurité n'arrivent que si quelqu'un met à jour. Revoir les versions de chaque composant lors de l'audit périodique (§17.6), et plus tôt en cas d'alerte de sécurité publiée pour l'un d'eux. Comme la bannière de mise à jour d'Open WebUI est désactivée, cette revue est le seul signal.

## §16.9 Une perte d'accès doit se détecter

Pendant ces tests, une coupure réseau de quelques instants a empêché la RAG API de joindre Microsoft Entra. Pour l'utilisateur concerné, la résolution des identités cloud a échoué : il n'a gardé que ses groupes AD (3 au lieu de 8), et a perdu l'accès à tous les documents SharePoint. Le comportement de sécurité était le bon (moins d'accès, jamais plus), mais la réponse ne l'était pas : « Cette information ne figure pas dans les documents disponibles », alors que le document existait et que l'utilisateur y avait droit.

Désormais, quand la résolution Entra échoue, la réponse le dit : « Les documents SharePoint n'ont pas pu être consultés : la vérification de vos droits auprès de Microsoft 365 a échoué. Réessayez dans quelques minutes. » L'échec n'est pas mis en cache : la question suivante retente la résolution.

Le contrôle après synchronisation (§16.4) détecte aussi ce cas : si la panne dure jusqu'à la synchronisation, les cas SharePoint autorisés sortent en « REFUS À TORT », et l'alerte part. Le contrôle ne signale donc pas seulement les fuites, mais aussi les pertes d'accès.

> **Un message d'erreur peut tromper.** Le journal indiquait `Network is unreachable`, une erreur IPv6, alors que la cause était une coupure IPv4. Le conteneur n'ayant pas d'IPv6, le système essaie l'IPv4, puis l'IPv6 en dernier recours : quand tout échoue, c'est la dernière erreur qui s'affiche. Vérifier la connectivité réelle (`curl` depuis la VM et depuis le conteneur) avant de conclure.

> **Deux jetons, deux usages.** `ADMIN_TOKEN` sert à n8n (synchronisation, synthèse Teams) et aux tests (`/query`), `API_TOKEN` à Open WebUI (questions des utilisateurs). Le lab avait renouvelé le premier ; l'avertissement de démarrage (§16.6) a signalé dès son premier lancement que le second gardait sa valeur d'exemple. Depuis la 2.21.0, la RAG API refuserait de démarrer. Sa rotation se fait dans le `.env`, puis dans la clé d'API de la connexion `rag-api` d'Open WebUI.

## §16.10 Supervision externe

Le contrôle après synchronisation (§16.4) alerte quand le cloisonnement est faux. Il ne dit rien si la stack est arrêtée, si la synchronisation ne tourne plus ou si le certificat arrive à échéance : **une alerte qui ne part pas ne se remarque pas.** Ces cas demandent une surveillance **depuis une autre machine** que la VM, puisqu'une VM arrêtée ne signale rien.

Le guide ne prescrit pas d'outil : l'organisation utilise le sien, s'il en a un. Ce qui compte, ce sont les contrôles.

### §16.10.1 Les contrôles

| Contrôle | Comment | Ce qu'il détecte | Exemple §16.10.2 |
|---|---|---|---|
| La stack répond | `GET https://<RAG_FQDN>/sante`, réponse contenant `ok` | VM, Nginx ou RAG API arrêtés, nom DNS perdu | Oui |
| Le certificat est valide | Contrôle TLS de la même adresse, échéance | Certificat expiré ou proche de l'échéance (§9.8.6), chaîne cassée | Oui |
| La synchronisation tourne | Signal envoyé par n8n après chaque synchronisation (« Push ») ; absence de signal = alerte | n8n arrêté, workflow désactivé, synchronisation en échec | Oui |
| Le cloisonnement est juste | Courriel du contrôle après synchronisation (§16.4) | Fuite ou refus à tort | Déjà en place, sans outil |
| Espace disque | `/srv/rag-donnees`, `/var/log/rag`, espace Docker | Disque plein : Qdrant, journaux nLPD | Non, outil de l'organisation |
| Moteur d'inférence | Contrôle du serveur Ollama ou vLLM | Questions sans réponse alors que `/sante` répond | Non, outil de l'organisation |

> **Ce que `/sante` ne dit pas :** la réponse prouve que Nginx et la RAG API répondent. Elle ne contrôle ni Qdrant, ni le moteur d'inférence, ni l'annuaire : `/health` est volontairement minimal (§16.6) et ne révèle rien de l'installation. Une question réelle reste le seul contrôle de bout en bout.

**Le certificat de l'autorité interne.** L'outil de supervision doit faire confiance à la racine de l'autorité, sinon la sonde HTTPS échoue ou doit ignorer les erreurs de certificat, et ne contrôle plus rien de ce côté. Pour un outil Node.js : variable `NODE_EXTRA_CA_CERTS` (§9.8.5).

**Le signal de synchronisation.** Le workflow `n8n-sync-corpus.json` du dépôt contient un nœud **Signal supervision (Push)**, **désactivé** par défaut. Branché en parallèle du test de résultat, il appelle l'adresse Push de l'outil après chaque synchronisation, avec `status=up` si elle a réussi, `status=down` sinon. Il ne bloque jamais le courriel d'erreur : en cas d'échec de l'appel, le workflow continue (*On Error* : *Continue*). Pour l'activer : remplacer `<NOM-COMPLET-SUPERVISION>` et `<CLE-PUSH>` dans l'URL, puis activer le nœud.

> **Nom complet obligatoire.** Le conteneur n8n ne résout pas les noms courts du domaine : `http://supervision:3001/...` échoue (`getaddrinfo EAI_AGAIN`), `http://supervision.votre-domaine.ch:3001/...` fonctionne. Le nom doit exister dans le DNS du domaine.

### §16.10.2 Exemple : Uptime Kuma

> **Exemple, pas une recommandation.** Uptime Kuma est un outil libre de surveillance, simple à installer en conteneur. Il a été utilisé dans le lab pour valider les trois premiers contrôles, sur une machine Docker existante, distincte de la VM de la stack. Testé avec Uptime Kuma 2.5.4, octobre 2026.

**Installation**, sur la machine de supervision (`/opt/uptime-kuma/docker-compose.yml`) :

```yaml
services:
  uptime-kuma:
    image: louislam/uptime-kuma:2.5.4@sha256:917318f9d7be5257f43ba412c766a473be336eb451d70744f3b482d0c3997c0e
    container_name: uptime-kuma
    ports:
      - "3001:3001"
    volumes:
      - ./data:/app/data
      # Chaîne de l'autorité interne (§9.2.4), pour contrôler le certificat de la stack
      - ./certs/ad-chain.pem:/certs/ad-chain.pem:ro
    environment:
      - NODE_EXTRA_CA_CERTS=/certs/ad-chain.pem
    mem_limit: 384m
    restart: unless-stopped
```

```bash
cd /opt/uptime-kuma
mkdir -p certs && cp /chemin/vers/ad-chain.pem certs/
docker compose up -d
```

L'interface s'ouvre sur `http://<machine-de-supervision>:3001` ; le premier compte créé est l'administrateur. Avant d'installer sur une machine qui porte déjà d'autres services, vérifier que le port 3001 est libre (`ss -tlnp | grep 3001`) et qu'il reste assez de mémoire.

**Notification.** Dans les paramètres d'Uptime Kuma, configurer une notification par courriel (SMTP), puis l'activer sur chaque sonde.

**Sonde 1, la stack et son certificat.** Nouvelle sonde :

- type **HTTP(s) - Mot-clé** ;
- URL `https://<RAG_FQDN>/sante`, mot-clé `ok` ;
- cocher la notification d'expiration du certificat.

**Sonde 2, la synchronisation.** Nouvelle sonde :

- type **Push** ; l'outil affiche une adresse Push, dont la clé est à reporter dans le nœud n8n (§16.10.1) ;
- intervalle de **3 900 secondes** : la synchronisation est horaire, l'alerte part si aucun signal n'arrive pendant 65 minutes.

> **Validé en lab, octobre 2026 :** la sonde 1 affiche la stack en service et l'échéance du certificat de l'autorité interne (chaîne validée grâce à `NODE_EXTRA_CA_CERTS`). La sonde 2 reçoit le signal de n8n, en ligne de commande et depuis le workflow. Synchronisation arrêtée, le courriel « [Synchronisation RAG] [🔴 Down] No heartbeat in the time window » est arrivé.

**Limites de cet exemple :**

- l'interface d'Uptime Kuma est en HTTP : la placer derrière un frontal HTTPS, ou la réserver au réseau d'administration ;
- la clé Push figure en clair dans l'URL du nœud n8n et dans les journaux de la machine de supervision : qui la connaît peut envoyer un faux signal « up ». Elle ne donne accès à rien d'autre ;
- l'appel Push part en HTTP ;
- une seule machine de supervision : si elle s'arrête, plus rien ne surveille. C'est le rôle de l'outil de l'organisation, s'il en a un, de couvrir ce cas.

## §16.11 Checklist

| Point | Vérification | Attendu |
|---|---|---|
| Test d'accès | `test_cloisonnement.py` | 0 FUITE, 0 ABSENT |
| Contrôle après synchronisation | `docker logs rag-api \| grep CLOISONNEMENT` | `N/N conformes, fuites=0` |
| Alerte | Contre-épreuve (fuite simulée) | Courriel « FUITE DE CLOISONNEMENT » reçu |
| Masque NTFS | Rapport de synchronisation | `entrees_allowed_sans_lecture` affiché |
| Permissions du partage | `Set-AccesIndexationRAG.ps1 -Verifier` | Ouverture large, pas d'alerte |
| Valeurs d'exemple | `docker logs rag-api \| grep SÉCURITÉ` | Aucune ligne ; la RAG API est démarrée |
| Identité signée | Contrôle d'usurpation (§16.6) | HTTP 403 |
| `/query` | Appel avec `API_TOKEN` | HTTP 401 |
| `/stats` | Appel sans jeton | HTTP 401 ou 403 |
| Journal | `tail -1 /var/log/rag/rag-queries.jsonl` | `question_hash` commençant par `hmac:` |
| Open WebUI | Liste des modèles avec un compte utilisateur | `rag-api` seul |
| Moteur d'inférence | `curl` depuis un autre poste | Pas de réponse |
| n8n | Export d'un workflow | Aucun jeton en clair |
| Versions figées | `grep 'image:' docker-compose.yml` | Chaque image avec `@sha256:` |
| Supervision externe | Sondes `/sante` et Push (§16.10) | En service ; alerte reçue lors d'un essai |
| Échéance du certificat | Sonde ou `openssl x509 -checkend` (§9.8.6) | Plus de 30 jours |
| Après une mise à jour d'un composant | Connexions, `[AUTH] /v1`, test, synchronisation | Tout conforme avant d'utiliser la nouvelle version |

---

[Retour au sommaire](index.md) | [Section précédente : §15 Sécurité des données](section-15-securite-donnees.md) | [Section suivante : §17 Gouvernance](section-17-gouvernance.md)

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
