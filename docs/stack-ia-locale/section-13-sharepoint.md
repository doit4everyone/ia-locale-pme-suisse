---
title: "§13 Connecteur SharePoint Online | Guide de déploiement stack IA locale"
description: "Indexation des bibliothèques SharePoint Online avec propagation des permissions (groupes SharePoint, groupes Entra et AD synchronisés, partages, liens) jusqu'aux chunks Qdrant, application Sites.Selected, validation par matrice de cloisonnement."
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

# §13 Connecteur SharePoint Online

[Retour au sommaire](index.md) | [Section précédente : §12 Synthèse des réunions Teams](section-12-teams.md)

**Statut :** validé en lab sur VM-RAG-LAB, septembre 2026, sur un tenant Microsoft 365 synchronisé par Entra Connect : cinq sites, trois comptes de test, 18 réponses sur 18 conformes à la matrice de cloisonnement.

---

> **Ce que cette section documente :** les documents des bibliothèques SharePoint Online sont indexés dans la même collection que ceux du partage SMB, et **chaque chunk porte les permissions SharePoint du fichier**, traduites en identifiants Entra. Un utilisateur ne peut interroger que les documents qu'il peut ouvrir dans SharePoint. L'application d'indexation n'a accès qu'aux sites qui lui sont accordés explicitement, en lecture seule.

---

## §13.1 Architecture

### §13.1.1 Le flux

```
n8n (toutes les heures) → POST /admin/sync (rag-api)
   1. indexer.py       partage SMB
   2. acl_resolver.py  ACL NTFS
   3. sp_indexer.py    SharePoint Online (si SP_SITES est renseigné)
        ├→ fichiers, permissions, contenu   (Graph, RAG-SharePoint-Indexer)
        ├→ groupes SharePoint du site       (API REST SharePoint, même application)
        ├→ UPN, groupes, propriétaires      (Graph, RAG-Identity-Resolver, §11)
        └→ chunks avec autorises[]          (Qdrant, collection documents)
   → reconstruction de l'index BM25
```

### §13.1.2 Deux applications, deux rôles

| Application | Permissions | Rôle |
|---|---|---|
| `RAG-SharePoint-Indexer` (nouvelle) | `Sites.Selected` (Graph et SharePoint), rôle **read** accordé site par site | Lire les fichiers, leurs permissions et les groupes SharePoint des sites accordés |
| `RAG-Identity-Resolver` (§11) | `User.Read.All`, `GroupMember.Read.All` | Traduire les UPN en identifiants, lire les propriétaires des groupes, vérifier l'existence des groupes |

L'application d'indexation ne sait rien de l'annuaire, et l'application d'identité ne voit aucun document. Chacune a le strict nécessaire.

### §13.1.3 Principes

- **Même découpage que le SMB.** `sp_indexer.py` réutilise l'extraction, le découpage et les embeddings d'`indexer.py` : un document SharePoint est traité exactement comme un document du partage.
- **Permissions recalculées à chaque passage**, contenu retéléchargé seulement si le fichier a changé.
- **Refus par défaut.** Un membre qu'on ne sait pas traduire n'ouvre aucun accès. Un fichier dont les permissions ne peuvent pas être lues n'est pas modifié.
- **Pas d'accès plus large que SharePoint.** La seule divergence est volontairement plus restrictive : les liens « toute l'organisation » (§13.4.3).

---

## §13.2 Inventaire préalable

Avant toute ligne de code, inventorier ce que l'indexeur verra : c'est ce qui a fixé les règles de traduction de §13.4, et révélé plusieurs pièges.

### §13.2.1 Les scripts

Trois scripts PowerShell en lecture seule, dans [`scripts/sharepoint/`](../../scripts/sharepoint/), exécutés avec un compte administrateur :

| Script | Module | Produit |
|---|---|---|
| `Inventaire-Permissions-SharePoint.ps1` | `Microsoft.Graph.Authentication` | Permissions de chaque fichier et dossier, telles que Graph les expose (CSV) |
| `Inventaire-GroupesSharePoint.ps1` | `Microsoft.Online.SharePoint.PowerShell` | Composition des groupes SharePoint de chaque site (CSV) |
| `Resoudre-Identifiants.ps1` | `Microsoft.Graph.Authentication` | Nom et type des identifiants (GUID) trouvés dans les inventaires |

```powershell
.\Inventaire-Permissions-SharePoint.ps1 `
  -Sites "https://<tenant>.sharepoint.com/sites/RH","https://<tenant>.sharepoint.com/" `
  -Sortie "C:\Temp\permissions-sharepoint.csv"
```

> **Deux pièges d'exécution.**
> - **Ne jamais charger les modules SharePoint Online et Graph dans la même session PowerShell.** Ils embarquent des versions différentes des mêmes bibliothèques d'authentification : le second module chargé échoue avec une erreur `TypeLoadException` peu explicite. Une console par module.
> - **`Connect-SPOService` exige l'authentification moderne.** Sans `-ModernAuth $true`, le module tente l'authentification héritée, refusée par les tenants actuels, et affiche seulement « Could not connect to SharePoint Online ». Le script la demande explicitement.

### §13.2.2 Ce que l'inventaire du lab a révélé

- **Une bibliothèque à exclure** : « Preservation Hold Library », sur les sites soumis à une stratégie de rétention. Elle contient les anciennes versions des documents modifiés et les documents supprimés. L'indexer ferait répondre le RAG avec des versions périmées ou des documents supprimés volontairement.
- **Des permissions renvoyées fichier par fichier**, héritées comprises, sans indication d'origine. Pour l'indexeur, c'est simple : il lit les permissions de chaque fichier, sans reconstruire l'héritage.
- **Des groupes SharePoint aux membres très variés** : groupes Microsoft 365, leurs propriétaires, groupes de sécurité synchronisés depuis l'AD, utilisateurs, invités externes, « tous les utilisateurs internes », compte système, groupes techniques de partage.
- **Un groupe supprimé encore membre de deux sites** : SharePoint conserve la référence et l'ancien nom d'un groupe qui n'existe plus ni dans l'AD ni dans Entra. Personne ne s'en aperçoit sans inventaire.
- **Un rôle d'annuaire présenté comme un groupe** : « Global Administrator » apparaît parmi les permissions du site racine.
- **Un partage excessif** : un contrat de travail partagé en lecture avec un compte invité externe, et par un lien « toute l'organisation » en modification.

---

## §13.3 Application et accès site par site

### §13.3.1 App Registration `RAG-SharePoint-Indexer`

Certificat, sur la VM :

```bash
cd /etc/rag-certs
sudo openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout rag-sharepoint.key -out rag-sharepoint.crt \
  -days 730 -subj "/CN=RAG-SharePoint-Indexer"
sudo chmod 600 rag-sharepoint.key
sudo cat rag-sharepoint.crt
openssl x509 -in rag-sharepoint.crt -noout -fingerprint -sha1 | tr -d ':' | cut -d= -f2
```

Dans le centre d'administration Entra :

1. **Inscriptions d'applications** → **Nouvelle inscription** : `RAG-SharePoint-Indexer`, comptes de cet annuaire uniquement, sans URI de redirection.
2. **Certificats et secrets** → charger `rag-sharepoint.crt`, vérifier l'empreinte.
3. **Autorisations de l'API** → deux autorisations **d'application** :
   - **Microsoft Graph** → `Sites.Selected` : fichiers, permissions des fichiers, contenu ;
   - **SharePoint** → `Sites.Selected` : composition des groupes SharePoint, que Graph n'expose pas.
4. **Consentement administrateur**, puis suppression de la permission déléguée `User.Read` ajoutée par défaut.

> **`Sites.Selected` ne donne accès à rien** tant qu'un accès n'est pas accordé site par site. C'est la différence essentielle avec `Sites.Read.All`, qui ouvre tous les sites du tenant, y compris ceux créés plus tard.

### §13.3.2 Accorder la lecture site par site

`Accorder-SitesSelected.ps1` accorde le rôle **read** à l'application sur une liste de sites, via Graph, puis affiche les accès applicatifs de chaque site. Il demande la portée déléguée `Sites.FullControl.All`, nécessaire pour **gérer** les accès des applications : l'application, elle, ne reçoit que la lecture.

```powershell
.\Accorder-SitesSelected.ps1 `
  -AppId "<ID-APPLICATION>" -AppNom "RAG-SharePoint-Indexer" `
  -Sites "https://<tenant>.sharepoint.com/sites/RH","https://<tenant>.sharepoint.com/"

# Consultation seule des accès applicatifs d'un site
.\Accorder-SitesSelected.ps1 -AppId "<ID-APPLICATION>" -AppNom "RAG-SharePoint-Indexer" `
  -Sites "https://<tenant>.sharepoint.com/sites/RH" -Lister
```

L'affichage des accès existants a une utilité propre : toute autre application qui apparaît sur un site est à examiner.

### §13.3.3 Sonde avant et après l'accord

`sonde_sharepoint.py` vérifie ce que l'application peut réellement lire, avant d'écrire l'indexeur. À exécuter dans le conteneur `rag-api` :

```bash
docker exec -e PYTHONPATH=/app -w /app rag-api python3 /rag-pipeline/sonde_sharepoint.py \
  --client-id <ID-APPLICATION> --thumbprint <EMPREINTE> \
  --site https://<tenant>.sharepoint.com/sites/RH
```

**Validé en lab, septembre 2026 :**

| Moment | Résultat |
|---|---|
| Avant l'accord | Jeton valide, mais **403** sur chaque site : la permission seule ne donne rien |
| Après l'accord, rôle read | Sites, bibliothèques, fichiers, **permissions de chaque fichier** et contenu lisibles |
| Groupes SharePoint | Propriétaires, Membres et Visiteurs lisibles ; seuls les **groupes système** (« Limited Access », « SharingLinks ») sont refusés, parce que leurs membres ne sont visibles que par eux-mêmes |
| Chiffrement | Document de test : format Office ouvert ; contrat étiqueté : conteneur OLE, donc chiffré |

Les groupes système refusés ne manquent pas à l'indexeur : les groupes « Limited Access » ne donnent pas accès au contenu, et les destinataires des liens de partage sont déjà fournis par Graph dans les permissions de chaque fichier. **Aucun droit supplémentaire n'est nécessaire.**

---

## §13.4 Traduction des permissions

### §13.4.1 Les règles

| Membre trouvé | Format dans SharePoint | Traduction dans `autorises[]` |
|---|---|---|
| Utilisateur | `i:0#.f\|membership\|<UPN>` ou identité Graph | `entra:usr:<id>` |
| Groupe de sécurité (cloud ou synchronisé AD) | `c:0t.c\|tenant\|<id>` | `entra:grp:<id>`, si le groupe existe |
| Membres d'un groupe Microsoft 365 | `c:0o.c\|federateddirectoryclaimprovider\|<id>` | `entra:grp:<id>` |
| Propriétaires d'un groupe Microsoft 365 | même format, suffixé `_o` | `entra:usr:<id>` de chaque propriétaire |
| Tous les utilisateurs internes | `c:0-.f\|rolemanager\|spo-grid-all-users/<tenant>` | `entra:tous-internes` |
| Groupe SharePoint | identifiant du groupe dans le site | traduction de chacun de ses membres |
| Lien « personnes précises » | lien de portée `users` | les personnes désignées |
| Lien « toute l'organisation » ou anonyme | lien de portée `organization` ou `anonymous` | **ignoré** |
| Invité externe | UPN contenant `#ext#` | ignoré |
| Compte système, groupes « Limited Access » | `SHAREPOINT\system` | ignoré |
| Rôle d'annuaire, groupe supprimé | identifiant introuvable | ignoré, signalé dans le rapport |

SharePoint n'a pas de refus explicite : `interdits[]` reste vide.

### §13.4.2 Propriétaires : ne pas élargir l'accès

Graph présente les propriétaires d'un groupe Microsoft 365 **comme le groupe lui-même**, avec le rôle `owner`. Le traduire en `entra:grp:<id>` donnerait l'accès à **tous les membres** du groupe, y compris sur un document réservé aux propriétaires. L'indexeur reconnaît ce cas et lit la liste des propriétaires : chacun reçoit un `entra:usr:<id>`.

### §13.4.3 Liens « toute l'organisation » : refus par défaut

Dans SharePoint, un lien de portée organisation permet à tout employé **qui possède le lien** d'ouvrir le document. Le RAG ne peut pas savoir qui le possède : il traite le document comme non partagé par ce lien. C'est la seule divergence avec SharePoint, et elle est volontairement plus restrictive.

### §13.4.4 « Tous les utilisateurs internes » : extension d'auth.py

`auth.py` ajoute `entra:tous-internes` aux comptes **membres** du tenant, pas aux invités. Validé en lab avec un compte **sans licence** Microsoft 365 : il accède au site ouvert à tous, et à rien d'autre.

### §13.4.5 Identifiants en minuscules

Qdrant compare les valeurs de `autorises[]` en respectant la casse. `auth.py` et `sp_indexer.py` écrivent tous les identifiants en minuscules : une traduction en majuscules d'un côté seulement rendrait les documents invisibles, sans erreur.

---

## §13.5 Documents chiffrés par Purview

Un document protégé par une étiquette avec chiffrement n'est pas un fichier Office ouvert, mais un **conteneur OLE** chiffré. L'indexeur le détecte, ne l'indexe pas, retire ses éventuels anciens chunks, et le compte dans le rapport (« chiffré, non indexé »). Rien n'est indexé à moitié. Le déchiffrement fera l'objet de la section Purview : il devra respecter à la fois les permissions SharePoint et les droits de l'étiquette.

> **Le chiffrement protège un fichier, pas son contenu une fois copié.** Dans le lab, les contrats de travail originaux étaient chiffrés, mais le site RH contenait des **copies en clair** : exports PDF et copies Word. Ces copies sont indexées, visibles des seuls membres du site RH, conformément aux droits SharePoint. Mais un outil d'IA rend ce genre de copie beaucoup plus facile à trouver que ne le fait une arborescence de dossiers. Un inventaire du contenu indexé, avant la mise en service, permet de les repérer.

---

## §13.6 Code et déploiement

### §13.6.1 Fichiers

| Fichier | Rôle |
|---|---|
| `sp_indexer.py` | Indexation SharePoint, traduction des permissions, détection du chiffrement |
| `api/anon_auth.py` | Identifiant `entra:tous-internes` |
| `api/anon_main.py` | Étape SharePoint dans `/admin/sync`, citations SharePoint, fenêtres de contexte explicites |
| `scripts/sharepoint/` | Inventaires, accord site par site, sonde |

### §13.6.2 Payload d'un chunk SharePoint

En plus des champs d'`indexer.py` :

```json
{
  "source": "SharePoint/RH/Documents/Politique_RH.docx",
  "source_type": "sharepoint",
  "sp_site": "https://<tenant>.sharepoint.com/sites/RH",
  "sp_drive": "Documents",
  "sp_item_id": "01ABC…",
  "sp_ctag": "\"c:{…},2\"",
  "web_url": "https://<tenant>.sharepoint.com/…",
  "autorises": ["entra:grp:<id>", "entra:usr:<id>"],
  "interdits": []
}
```

`source_type` protège ces chunks du nettoyage des orphelins d'`acl_resolver.py`, qui ne concerne que le SMB (§11).

### §13.6.3 Incrémental et orphelins

- **Contenu inchangé** (même `cTag`, mêmes paramètres de découpage) : le fichier n'est pas retéléchargé. Seules ses permissions sont recalculées, et mises à jour si elles ont changé.
- **Fichier supprimé** de SharePoint : ses chunks sont supprimés, **uniquement si le parcours du site s'est terminé sans erreur**. Un incident réseau ne peut pas provoquer d'effacement.
- **Erreur sur un fichier** : les autres fichiers sont traités, seul le nettoyage des orphelins du site est suspendu.

### §13.6.4 Citations

`main.py` enrichit les citations selon la source : chemin UNC pour le SMB, et pour SharePoint un **lien cliquable** vers le document :

```
[Politique_RH.docx : SharePoint, site RH, Documents](https://<tenant>.sharepoint.com/…)
```

SharePoint vérifie lui-même les droits de celui qui clique.

### §13.6.5 Variables

```bash
SP_CLIENT_ID=<ID-APPLICATION-SHAREPOINT>
SP_CERT_THUMBPRINT=<EMPREINTE-CERTIFICAT-SHAREPOINT>
SP_KEY_PATH=/etc/rag-certs/rag-sharepoint.key
# URL complètes, séparées par des virgules ; vide = étape désactivée
SP_SITES=https://<tenant>.sharepoint.com/sites/RH,https://<tenant>.sharepoint.com/
SP_EXCLUDE_DRIVES=Preservation Hold Library
SP_MAX_FILE_MB=50
SYNC_TIMEOUT_SHAREPOINT=900
LLM_NUM_CTX=16384
JUDGE_NUM_CTX=8192
```

`SP_SITES` doit contenir exactement les sites accordés en §13.3.2. Un site listé mais non accordé est signalé en erreur dans le rapport ; un site accordé mais non listé n'est pas indexé.

### §13.6.6 Déploiement

```bash
# Scripts : pas de reconstruction, le dossier est monté dans le conteneur
sudo cp /home/<utilisateur>/sp_indexer.py /home/<utilisateur>/sharepoint/sonde_sharepoint.py /root/rag-pipeline/

# Variables transmises au conteneur
cd /root/rag-stack
cp docker-compose.yml docker-compose.yml.bak
grep -q 'SP_CLIENT_ID=' docker-compose.yml || for v in JUDGE_NUM_CTX LLM_NUM_CTX SYNC_TIMEOUT_SHAREPOINT SP_MAX_FILE_MB SP_EXCLUDE_DRIVES SP_SITES SP_KEY_PATH SP_CERT_THUMBPRINT SP_CLIENT_ID; do
  sed -i "/- TEAMS_STATE_FILE=\${TEAMS_STATE_FILE}/a\      - $v=\${$v}" docker-compose.yml
done
docker compose config --quiet && echo "Compose OK"

# main.py et auth.py : reconstruction
sudo cp /home/<utilisateur>/main.py /home/<utilisateur>/auth.py /root/rag-stack/api/
docker compose build --no-cache rag-api
docker compose up -d rag-api
docker exec rag-api printenv SP_SITES
```

Dans n8n, workflow de synchronisation du corpus, nœud **POST /admin/sync** : délai d'attente porté à **1800000** ms (30 minutes). La version publiée du workflow contient déjà cette valeur.

Premier passage manuel, en simulation (rien n'est écrit) :

```bash
docker exec -e PYTHONPATH=/app -w /app rag-api python3 /rag-pipeline/sp_indexer.py --dry-run
```

Le rapport (`/var/log/rag/rapport_sharepoint_*.json`) donne, pour chaque fichier, son statut et ses `autorises[]` traduits : c'est le moment de les comparer à la matrice de test, avant toute écriture.

### §13.6.7 Index BM25

`/admin/sync` reconstruit maintenant l'index BM25 **après chaque synchronisation, même partiellement en échec** : une étape peut avoir modifié Qdrant avant l'échec d'une autre, et l'index doit refléter son contenu. Une indexation lancée à la main, en dehors de `/admin/sync`, ne le reconstruit pas : redémarrer `rag-api` ou lancer une synchronisation.

---

## §13.7 Validation

### §13.7.1 Jeu de test

| Élément | Rôle dans le test |
|---|---|
| `test-compta`, compte **AD** synchronisé, membre du seul groupe AD `Comptabilité`, licencié | Accès par groupe AD synchronisé, partage direct, refus |
| `test-client`, compte AD synchronisé, **sans licence**, sans droit SharePoint | « Tous les internes » uniquement |
| Compte administrateur | Accès à tous les sites |
| `Test_RAG_Finances` (site Finances, sans partage) | Accès par groupe AD |
| `Test_RAG_RH` (site RH, sans partage) | Cloisonnement |
| `Test_RAG_RH_Lien_Organisation` (lien « toute l'organisation ») | Règle de refus du lien |
| `Test_RAG_RH_Partage_Direct` (partagé à `test-compta`) | Permission lue fichier par fichier |

Chaque document de test contient une phrase avec un code unique (par exemple « Le code de test RH est RH-3159. ») : la réponse est soit le bon code, soit « information non disponible », sans ambiguïté possible.

> **Créer les comptes de test dans l'AD, pas dans Entra.** Open WebUI authentifie les utilisateurs en LDAP sur l'AD : un compte créé uniquement dans Entra ne pourrait pas interroger le RAG. Pour un compte synchronisé, renseigner le **lieu d'utilisation** avant d'attribuer une licence : sans lui, l'attribution est refusée.

> **Étiquetage obligatoire.** Si la stratégie d'étiquetage impose une étiquette, choisir une étiquette sans chiffrement pour les documents de test, n'y mettre aucune donnée qui déclencherait l'étiquetage automatique (numéro AVS, IBAN, terme médical), et vérifier l'étiquette le lendemain : l'étiquetage automatique côté serveur est asynchrone.

### §13.7.2 Simulation et indexation

**Validé en lab, septembre 2026 :** 5 sites, 36 fichiers indexés, 10 chiffrés et non indexés, 2 fichiers Excel ignorés, 2 identifiants introuvables (le groupe supprimé et le rôle d'annuaire). Permissions traduites des documents de test toutes conformes avant écriture. Second passage : les 36 fichiers « inchangés », sans téléchargement. Intégration à `/admin/sync` : les trois étapes enchaînées, index BM25 reconstruit (325 chunks dans `documents`, dont 250 issus de SharePoint).

### §13.7.3 Matrice de cloisonnement

| Question | Administrateur | test-compta | test-client |
|---|---|---|---|
| Code de test Finances | FIN ✓ | **FIN ✓** | Refusé ✓ |
| Code de test RH | RH ✓ | **Refusé ✓** | Refusé ✓ |
| Code de test lien organisation | ORG ✓ | **Refusé ✓** | **Refusé ✓** |
| Code de test partage direct | DIR ✓ | **DIR ✓** | Refusé ✓ |
| Guide de dépannage (site ouvert à tous) | Réponse ✓ | Réponse ✓ | **Réponse ✓** |
| Jours de vacances, politique RH (document réel) | 25 / 27 jours ✓ | **Refusé ✓** | Refusé ✓ |

**18 réponses sur 18 conformes.** Chaque règle de §13.4 est démontrée par un cas : groupe AD synchronisé, permission lue fichier par fichier, refus du lien organisation, « tous les internes » sans licence, cloisonnement sur un document réel.

Le guide de dépannage existe en deux exemplaires, sur un site réservé au service informatique et sur le site ouvert à tous. L'administrateur obtient la copie du site informatique, les deux autres comptes la copie du site ouvert, **la seule à laquelle ils ont accès** : le RAG ne se contente pas de refuser, il trouve la version autorisée du même contenu.

---

## §13.8 Limites et constats

### §13.8.1 Limites

**Questions générales.** Pendant les tests, « Que dit la politique RH ? » n'a pas trouvé le document, alors que « Combien de jours de vacances prévoit la politique RH ? » l'a trouvé. Le premier diagnostic mettait en cause le découpage : les chunks commencent par leur titre de section (« Temps de travail et congés »), et le titre du document n'apparaît que dans le premier. Mais ce test a eu lieu pendant la panne décrite en §13.8.3 : la copie SMB du même document était alors invisible pour tous. Une fois la lecture du partage rétablie, la même question générale a obtenu une réponse complète et correctement citée. L'effet du titre absent des chunks n'est donc pas démontré : il sera mesuré au §10, en répétant le titre du document en tête de chaque chunk et en comparant les réponses sur un même jeu de questions.

**Formats.** Les fichiers Excel ne sont pas indexés, comme pour le SMB.

**Liens organisation.** Un document partagé uniquement par ce type de lien reste invisible pour ceux qui ont reçu le lien (§13.4.3).

**Invités externes.** Ils ne peuvent pas se connecter à Open WebUI (authentification LDAP sur l'AD) : leurs accès SharePoint ne sont pas traduits.

**Documents chiffrés.** Non indexés dans cette section (§13.5).

### §13.8.2 Fenêtre de contexte d'Ollama

`main.py` ne demandait pas de fenêtre de contexte : Ollama appliquait sa valeur par défaut, **4 096 tokens** dans le lab, alors que le contexte du RAG (15 chunks, prompt système et réponse) peut la dépasser. Ollama tronque alors **sans erreur**. `main.py` demande maintenant ses fenêtres explicitement : `LLM_NUM_CTX` (16 384, identique à la synthèse Teams, pour éviter un rechargement du modèle) et `JUDGE_NUM_CTX` (8 192, y compris pour l'appel qui maintient le juge en mémoire).

> **Ne pas utiliser `OLLAMA_CONTEXT_LENGTH` sur le serveur Ollama.** Ce réglage s'applique à tous les modèles, y compris le juge, dont il augmente la mémoire sans raison. Et une valeur écrite à la française, avec une espace fine insécable (« 16 384 »), est **ignorée sans erreur** : Ollama affiche un avertissement, visible seulement avec `ollama ps`, et revient à sa valeur par défaut.

Sur la carte graphique de 16 Go prévue pour le §10, les fenêtres actuelles ne tiendront pas ensemble (16,3 Go mesurés sur CPU) : leur dimensionnement sera fait au §10, sur la base des tokens réellement consommés.

### §13.8.3 Constats de gouvernance

Le tenant et le serveur de fichiers du lab ont servi à de nombreux essais avant ce guide, comme ceux de beaucoup de PME qui ont testé des outils d'IA. Construire l'indexation y a mis au jour des situations typiques d'un tel environnement. La colonne « Origine » dit honnêtement d'où elles viennent : plusieurs ont été créées par nos propres essais, ce qui ne les rend pas moins représentatives. Elles sont reprises sous forme de recommandations dans la section gouvernance.

| Situation | Origine dans le lab | Risque | Traitement |
|---|---|---|---|
| Ancienne application d'indexation avec `Sites.Read.All` | Pilote abandonné (une plateforme RAG testée puis remplacée) | Lecture de tout le tenant, certificat valide deux ans | Supprimée |
| Compte d'indexation membre des groupes de droits Purview | Configuration initiale du lab | Droit de déchiffrer les documents financiers et RH | Retiré (et §5.2.4 réécrite) |
| Groupes Purview servant aussi d'ACL NTFS | Configuration antérieure du serveur de fichiers | Le retrait a coupé la lecture de six fichiers : invisibles pour tous dans le RAG, sans fuite | Groupe dédié à l'indexation, script `Set-AccesIndexationRAG.ps1` |
| Groupe supprimé encore membre de deux sites | Inconnue | Accès retiré sans que personne ne le sache | Signalé par l'indexeur à chaque passage |
| Copies en clair de documents chiffrés | Documents de test et de démonstration | Contenu sensible trouvable par le RAG | À supprimer ou déplacer |
| Fichier nommé comme une clé TLS dans le corpus | Inconnue | Secret possible, trouvable par le RAG | À sortir du partage |

Le point commun : **un outil d'IA rend trouvable ce qui n'était que caché dans une arborescence.** L'inventaire des permissions et le rapport de synchronisation sont les deux outils qui permettent de le voir avant les utilisateurs.

---

## §13.9 Checklist

| Point | Vérification | Résultat attendu |
|---|---|---|
| Inventaire | Scripts de §13.2 | Bibliothèques de conservation et membres atypiques identifiés |
| Application | Sonde avant l'accord | 403 sur chaque site |
| Accès | `Accorder-SitesSelected.ps1 -Lister` | L'application en read sur les seuls sites prévus |
| Sonde après accord | `sonde_sharepoint.py` | Fichiers, permissions, groupes du site lisibles |
| Simulation | `sp_indexer.py --dry-run` | `autorises[]` conformes à la matrice, chiffrés détectés |
| Incrémental | Second passage | Tous les fichiers « inchangés » |
| Synchronisation | `/admin/sync` | Étape `sharepoint` en succès, BM25 reconstruit |
| Cloisonnement | Matrice avec trois comptes | Toutes les réponses conformes |
| Citations | Question sur un document SharePoint | Lien cliquable vers le document |
| Fenêtres de contexte | `ollama ps` | Modèle principal et juge aux valeurs demandées |

---

§14 Documents protégés par Purview *(à venir)*

---

*Validé en lab sur VM-RAG-LAB, septembre 2026, sur un tenant Microsoft 365 synchronisé par Entra Connect, avec qwen2.5:14b sur CPU.*
