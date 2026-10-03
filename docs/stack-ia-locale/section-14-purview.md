---
title: "§14 Documents protégés par Purview | Guide de déploiement stack IA locale"
description: "Indexation des documents SharePoint chiffrés par une étiquette Microsoft Purview : service de déchiffrement interne, double condition (permissions SharePoint et droits de l'étiquette évalués à la question), mise en garde, validation par matrice."
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

# §14 Documents protégés par Purview

[Retour au sommaire](index.md) | [Section précédente : §13 Connecteur SharePoint Online](section-13-sharepoint.md) | [Section suivante : §15 Sécurité des données](section-15-securite-donnees.md)

**Statut :** validé en lab sur VM-RAG-LAB, octobre 2026, sur un tenant Microsoft 365 Business Premium : trois étiquettes chiffrées, onze documents déchiffrés et indexés, quatre comptes de test, 12 réponses sur 12 conformes à la matrice.

---

> **Mise en garde : lire avant toute mise en œuvre.**
>
> Cette section montre comment indexer des documents **chiffrés** par une étiquette de confidentialité. Techniquement, c'est possible, et les droits de chaque utilisateur restent respectés à chaque question. Mais trois conséquences doivent être acceptées en connaissance de cause :
>
> 1. **Le contenu sort de la protection de l'étiquette.** Une fois indexé, le texte des documents est stocké en clair dans Qdrant, sur votre serveur. Microsoft 365 Copilot déchiffre à l'intérieur du périmètre de Microsoft ; ce RAG déchiffre à l'extérieur. Le serveur, ses disques et ses sauvegardes deviennent aussi sensibles que les documents eux-mêmes.
> 2. **L'application de déchiffrement est l'identité la plus puissante de la stack.** Elle peut lire tout le contenu protégé du tenant. Son certificat doit être protégé en conséquence.
> 3. **Les prérequis de sécurité ne sont pas facultatifs** : clé d'API Qdrant, chiffrement des données au repos, sauvegardes chiffrées (§14.2).
>
> **Posez-vous d'abord la question : avez-vous vraiment besoin qu'une IA lise ces documents ?** Pour beaucoup de PME, la bonne réponse est de ne pas les indexer, comme le fait §13 par défaut. Dans tous les cas, nous recommandons d'**exclure les données RH** (contrats, salaires, dossiers du personnel) : l'intérêt de les interroger par une IA est faible face au risque. Le lab les indexe uniquement pour démontrer le fonctionnement de la double condition.

---

> **Ce que cette section documente :** un service interne, `mip-service`, déchiffre les documents protégés au moment de l'indexation. À chaque question, l'accès à un document chiffré exige **deux conditions** : avoir accès au document dans SharePoint, comme en §13, **et** disposer des droits de l'étiquette. La seconde condition est évaluée par Purview lui-même, au nom de l'utilisateur, au moment de la question. Tout fonctionne depuis Linux, sans poste Windows ni exportation manuelle.

---

## §14.1 Ce que fait Copilot, ce que fait ce RAG

Microsoft 365 Copilot traite lui aussi les documents chiffrés, avec des règles qu'il est utile de reproduire.

| Règle | Microsoft 365 Copilot | Ce RAG |
|---|---|---|
| Droits exigés de l'utilisateur | VIEW **et** EXTRACT ([documentation](https://learn.microsoft.com/fr-fr/purview/ai-m365-copilot-considerations)) | VIEW **et** EXTRACT, ou propriétaire du document |
| Permissions définies par l'utilisateur | Peuvent empêcher Copilot d'utiliser le contenu ([architecture](https://learn.microsoft.com/fr-fr/microsoft-365/copilot/microsoft-365-copilot-architecture-data-protection-auditing)) | Documents exclus de l'indexation |
| Où le déchiffrement a lieu | Dans le périmètre du service Microsoft 365 | **Sur votre serveur**, hors du périmètre de Microsoft |
| Étiquette affichée dans la réponse | Oui, la plus prioritaire | Non, à ce jour (§14.8.1) |

Pour les fichiers SharePoint et OneDrive, Copilot exige que la prise en charge des étiquettes de confidentialité soit activée pour ces services. Dans le lab, `Get-SPOTenant | Select EnableAIPIntegration` renvoie `True`.

La différence de fond est la troisième ligne. Elle justifie à elle seule la mise en garde de début de section.

---

## §14.2 Prérequis

### §14.2.1 Licence et service de protection

Le lab utilise Microsoft 365 Business Premium, qui inclut Azure Information Protection Premium P1, et un compte de test sous Business Standard, qui permet de **consulter** un contenu protégé sans pouvoir en créer. Le service de protection doit être activé : `Get-AipService` renvoie `Enabled`.

### §14.2.2 Sécurité des données

Le contenu déchiffré est stocké en clair dans Qdrant. Avant d'indexer le premier document chiffré :

| Mesure | Pourquoi |
|---|---|
| **Clé d'API Qdrant** | Sans elle, tout conteneur du réseau Docker peut lire et écrire dans la base |
| **Chiffrement des données au repos** | Protège contre la copie ou le vol des disques et des fichiers de la VM |
| **Fichiers temporaires en mémoire** | `sp_indexer.py` extrait le texte dans `/dev/shm`, jamais sur disque |
| **Sauvegardes chiffrées** | Une sauvegarde de Qdrant contient le texte des documents |

Le chiffrement des données au repos (disque dédié LUKS2, déverrouillage par TPM, phrase secrète en clé de secours) et la clé d'API Qdrant sont décrits en [§15 Sécurité des données](section-15-securite-donnees.md). Le déverrouillage automatique par TPM exige une machine en UEFI avec un TPM 2.0.

> **Sauvegardes chiffrées : non validées en lab.** La nLPD n'impose pas nommément le chiffrement des sauvegardes, mais son devoir de sécurité exige des mesures appropriées au risque. Une copie en clair de contrats de travail ou de fiches de salaire, souvent stockée hors du serveur, serait difficile à défendre comme mesure appropriée. Nous considérons donc le chiffrement des sauvegardes comme une exigence dès que des documents chiffrés sont indexés.

### §14.2.3 Inventaire des étiquettes

Comme pour SharePoint en §13.2, l'inventaire précède toute configuration. Dans une session Security & Compliance (`Connect-IPPSSession`) :

```powershell
# Les réglages de chiffrement ne sont renvoyés qu'avec -IncludeDetailedLabelActions
Get-Label -IncludeDetailedLabelActions | Sort Priority | ForEach-Object {
    "=== $($_.DisplayName)"
    $_ | Format-List EncryptionEnabled, EncryptionProtectionType, EncryptionRightsDefinitions,
                     EncryptionOfflineAccessDays, EncryptionContentExpiredOnDateInDaysOrNever,
                     EncryptionDoubleKeyEncryptionUrl, EncryptionTemplateId
}
```

Points à relever pour chaque étiquette chiffrée : le type de protection (`Template` pour des droits fixés par l'administrateur, permissions définies par l'utilisateur sinon), les détenteurs de droits et la présence d'EXTRACT, l'accès hors connexion, et l'absence de double chiffrement (`EncryptionDoubleKeyEncryptionUrl` vide). Le lab n'a testé aucun document à double chiffrement.

Dans la console AIP (`Connect-AipService`), vérifier aussi la fonction super-utilisateur et sa liste :

```powershell
Get-AipServiceSuperUserFeature
Get-AipServiceSuperUser
```

---

## §14.3 Architecture

### §14.3.1 Le flux

```
Indexation (sp_indexer.py, synchronisation horaire)
  SharePoint (Graph) → document chiffré (conteneur OLE)
      → mip-service  POST /dechiffrer   → contenu en mémoire + étiquette + propriétaire
      → extraction dans /dev/shm, découpage, embeddings
      → Qdrant : chunks avec autorises[] (SharePoint) + chiffre, mip_etiquette_id, mip_proprietaire

Question (main.py)
  1. Qdrant filtre selon autorises[]                 → première condition (SharePoint ou NTFS)
  2. pour chaque chunk chiffré restant :
       mip-service  POST /droits (utilisateur, étiquette, propriétaire)
       → Purview répond, au nom de l'utilisateur     → seconde condition
  3. seuls les chunks qui remplissent les deux conditions atteignent le modèle
```

### §14.3.2 Pourquoi évaluer les droits à la question

Pour un document protégé par un modèle de droits fixés par l'administrateur, la licence du document **ne contient pas** la liste des détenteurs de droits : elle renvoie au modèle. Deux approches étaient possibles :

| | Copier les droits des étiquettes | Les évaluer à la question |
|---|---|---|
| Plateforme | PowerShell et module Purview, donc un poste Windows | `mip-service`, depuis Linux |
| Fraîcheur | Valable jusqu'à la prochaine exportation | Toujours celle de Purview (cache d'une heure) |
| Groupes imbriqués, `AuthenticatedUsers`, propriétaire | À traduire soi-même | Résolus par Purview |

La seconde approche est celle retenue. Elle reproduit le principe de Copilot : les droits ne sont pas recopiés, ils sont vérifiés pour l'utilisateur qui pose la question.

### §14.3.3 Refus par défaut

Un chunk chiffré est retiré si `mip-service` ne répond pas, si l'identité de l'utilisateur ou l'étiquette du document est inconnue, ou si Purview renvoie une erreur. Un document chiffré dont l'étiquette ne peut pas être lue n'est pas indexé.

---

## §14.4 Application de déchiffrement

### §14.4.1 Certificat et App Registration

Sur la VM, comme pour les applications des sections précédentes :

```bash
cd /etc/rag-certs
openssl req -x509 -newkey rsa:2048 -nodes -keyout rag-purview.key -out rag-purview.crt \
  -days 730 -subj "/CN=RAG-Purview-Decrypt"
cat rag-purview.crt       # à copier dans un fichier .crt sur le poste d'administration
openssl x509 -in rag-purview.crt -noout -fingerprint -sha1 | tr -d ':' | cut -d= -f2
```

Ne jamais afficher ni copier le fichier `.key`. Dans Entra : App Registration `RAG-Purview-Decrypt`, certificat chargé dans **Certificats et secrets**.

### §14.4.2 Autorisations

Dans **API autorisées** → **API utilisées par mon organisation**. Les deux services ne se trouvent pas toujours par leur nom : chercher par **identifiant d'application**.

| Service | Identifiant d'application | Autorisation (application) | Usage |
|---|---|---|---|
| Azure Rights Management Services | `00000012-0000-0000-c000-000000000000` | `Content.SuperUser` | Déchiffrer, au nom de l'application |
| Azure Rights Management Services | `00000012-0000-0000-c000-000000000000` | `Content.DelegatedReader` | Évaluer les droits d'un utilisateur, en son nom |
| Microsoft Information Protection Sync Service | `870c4f2e-85b6-4d43-bdda-6ed9a579b725` | `UnifiedPolicy.Tenant.Read` | Lire les étiquettes |

Puis **Accorder le consentement administrateur**. `Content.Writer`, que certains éditeurs ajoutent, n'est **pas** nécessaire : il sert à créer du contenu protégé. La [documentation du SDK MIP](https://learn.microsoft.com/fr-fr/information-protection/develop/concept-api-permissions) décrit ces autorisations.

Si le service de synchronisation MIP est absent de l'annuaire, le créer :

```powershell
Connect-MgGraph -Scopes "Application.ReadWrite.All"
New-MgServicePrincipal -AppId "870c4f2e-85b6-4d43-bdda-6ed9a579b725"
```

Sans `Content.DelegatedReader`, le service de protection refuse l'évaluation des droits avec `ServiceDisabledException : Calling principal is forbidden`.

### §14.4.3 La fonction super-utilisateur n'est pas nécessaire

Dans le lab, la fonction super-utilisateur du service de protection est **désactivée**, et l'application déchiffre pourtant les documents avec la seule autorisation `Content.SuperUser`. Il n'est donc pas nécessaire d'activer cette fonction ni d'y inscrire l'application.

> **Conséquence pour la gouvernance :** désactiver la fonction super-utilisateur **ne protège pas** contre une application qui a reçu `Content.SuperUser`. La liste des super-utilisateurs ne dit pas qui peut déchiffrer. Il faut aussi auditer les applications qui détiennent cette autorisation. Constat fait sur le tenant du lab.

Pour l'audit, dans une **session PowerShell neuve** : le module `Microsoft.Graph.Applications` doit être chargé avant `Connect-MgGraph`, et dans la même version que le module d'authentification, sinon la commande échoue avec une erreur générique (« Une ou plusieurs erreurs se sont produites »).

```powershell
Install-Module Microsoft.Graph.Applications -Scope CurrentUser   # si absent
Update-Module Microsoft.Graph.Authentication                     # versions alignées
# puis, dans une nouvelle fenêtre :
Import-Module Microsoft.Graph.Applications
Connect-MgGraph -Scopes "Application.Read.All" -NoWelcome
$rms  = Get-MgServicePrincipal -Filter "appId eq '00000012-0000-0000-c000-000000000000'"
$role = $rms.AppRoles | Where-Object Value -eq 'Content.SuperUser'
Get-MgServicePrincipalAppRoleAssignedTo -ServicePrincipalId $rms.Id -All |
  Where-Object AppRoleId -eq $role.Id | Select-Object PrincipalDisplayName, PrincipalId
```

Dans le lab, une seule application détient `Content.SuperUser` : `RAG-Purview-Decrypt`. Toute autre ligne mérite une explication.

---

## §14.5 Le service `mip-service`

### §14.5.1 Rôle et points d'accès

`mip-service` est un service ASP.NET 8 construit sur le SDK MIP de Microsoft (`File SDK`). Il tourne dans un conteneur, joignable uniquement depuis le réseau Docker de la stack, sans port publié, et exige un jeton à chaque appel.

| Point d'accès | Entrée | Sortie |
|---|---|---|
| `POST /dechiffrer` | Le document (corps brut), son nom dans l'en-tête `X-Nom-Fichier` | Étiquette, modèle, type de protection, propriétaire, expiration, **décision**, contenu déchiffré en base64 |
| `POST /droits` | `utilisateur`, `etiquette_id`, `proprietaire` | Liste des droits de l'utilisateur, et `autorise` (OWNER, ou VIEW et EXTRACT) |
| `GET /sante` | | État du moteur |

Les règles sont appliquées **avant** tout déchiffrement :

| Décision | Cas |
|---|---|
| `dechiffre` | Protection par modèle, non expirée, étiquette autorisée |
| `permissions_definies_par_utilisateur` | Droits fixés document par document : exclus |
| `contenu_expire` | Un super-utilisateur pourrait le lire, le RAG ne le fait pas |
| `etiquette_exclue` | Étiquette listée dans `MIP_ETIQUETTES_EXCLUES` |
| `non_protege` | Document sans protection |

Le contenu des documents n'est jamais journalisé : seuls le nom du fichier, l'étiquette et la décision le sont.

### §14.5.2 Le SDK MIP sous Linux : les pièges

Le SDK n'existe pas en Python. Sa version .NET est prise en charge sur Ubuntu, la version la plus récente étant la 24.04. Le service tourne donc dans un conteneur **Ubuntu 24.04**, quelle que soit la version d'Ubuntu de l'hôte (26.04 dans le lab).

| Piège | Correction |
|---|---|
| Le paquet NuGet générique ne contient pas les bibliothèques natives Linux | Paquet `Microsoft.InformationProtection.File.Ubuntu2404` |
| `libdl.so` introuvable dans l'image Ubuntu 24.04 (bibliothèque C 2.34 et suivantes) | Lien vers `libdl.so.2` dans l'image |
| `libgmime-3.0.so.0` manquante | Paquet `libgmime-3.0-0t64` |
| Le flux déchiffré est renvoyé positionné à sa fin | Le rembobiner avant lecture |
| Un utilisateur sans aucun droit lève `NoPermissionsException` | Traité comme un refus, pas comme une erreur |

Le Dockerfile et le code fournis intègrent toutes ces corrections.

### §14.5.3 Sécurité du conteneur

- utilisateur sans privilèges, d'identifiant **10001**, groupe 10001 ;
- système de fichiers en lecture seule, `/tmp` en mémoire (`tmpfs`) ;
- option `no-new-privileges` ;
- certificat et clé montés en lecture seule.

La clé privée doit **appartenir à l'utilisateur 10001**, lisible par lui seul :

```bash
chown 10001:10001 /etc/rag-certs/rag-purview.key /etc/rag-certs/rag-purview.crt
chmod 600 /etc/rag-certs/rag-purview.key
chmod 644 /etc/rag-certs/rag-purview.crt
```

Sur l'hôte, aucun compte n'a cet identifiant : seul root peut lire la clé.

### §14.5.4 Variables

| Variable | Rôle |
|---|---|
| `MIP_TENANT_DOMAINE` | Domaine initial du tenant (`votre-tenant.onmicrosoft.com`) |
| `MIP_CLIENT_ID` | Identifiant de `RAG-Purview-Decrypt` |
| `MIP_TOKEN` | Jeton partagé entre `mip-service` et `rag-api` (`openssl rand -hex 32`) |
| `MIP_ETIQUETTES_EXCLUES` | Identifiants des étiquettes jamais déchiffrées, séparés par des virgules |
| `MIP_URL` | `http://mip-service:8080`, côté `rag-api` (vide : Purview désactivé) |
| `COMPOSE_PROFILES` | `purview`, pour construire et démarrer `mip-service` |
| `MIP_CACHE_TTL` | Durée du cache des décisions de droits, en secondes (défaut : 3600) |

`ENTRA_TENANT_ID` est réutilisée. En production, renseigner `MIP_ETIQUETTES_EXCLUES` avec au moins les étiquettes RH.

### §14.5.5 Déploiement

Le service est fourni dans `scripts/stack-ia-locale/mip-service/`, que `deploy.sh` copie dans `/root/rag-stack/mip-service/`. Dans le `docker-compose.yml` du dépôt, il appartient au **profil `purview`** : il n'est ni construit ni démarré tant que ce profil n'est pas activé, et une installation sans Purview n'est pas affectée.

Dans le `.env` :

```bash
COMPOSE_PROFILES=purview
MIP_URL=http://mip-service:8080
MIP_TOKEN=<openssl rand -hex 32>
MIP_TENANT_DOMAINE=votre-tenant.onmicrosoft.com
MIP_CLIENT_ID=<identifiant de RAG-Purview-Decrypt>
MIP_ETIQUETTES_EXCLUES=<identifiants des étiquettes RH>
```

Puis :

```bash
cd /root/rag-stack
docker compose config --quiet && docker compose up -d --build mip-service rag-api
docker logs mip-service 2>&1 | tail -2       # attendu : « Moteur initialisé, service prêt »
```

Les scripts de test (`test_mip_service.py`, `test_droits.py`) et la sonde sont dans `scripts/purview/`.

---

## §14.6 Intégration à la stack

### §14.6.1 `sp_indexer.py`

Pour un document chiffré, si `MIP_URL` et `MIP_TOKEN` sont renseignées, `sp_indexer.py` l'envoie à `/dechiffrer`. Sans ces variables, il garde le comportement de §13 : document ignoré.

| Situation | Comportement |
|---|---|
| Décision `dechiffre` | Indexé, chaque chunk portant `chiffre: true`, `mip_etiquette_id`, `mip_etiquette_nom`, `mip_proprietaire` |
| Autre décision | Non indexé, chunks existants supprimés |
| Étiquette illisible | Non indexé : les droits ne pourraient pas être évalués |
| `mip-service` injoignable | Erreur, chunks existants **conservés** : les droits restant vérifiés à chaque question, il n'y a pas d'accès indu |

L'extraction du texte se fait dans `/dev/shm`, en mémoire, pour tous les documents SharePoint.

### §14.6.2 `main.py`

La fonction `filtrer_purview` s'applique deux fois : sur les résultats de la recherche hybride, puis sur l'extension de contexte (les chunks voisins du meilleur résultat). Les décisions sont gardées en cache pour chaque combinaison utilisateur, étiquette et propriétaire, pendant `MIP_CACHE_TTL` secondes.

L'utilisateur est identifié par l'adresse transmise par Open WebUI (`X-OpenWebUI-User-Email`). Cette adresse doit être à la fois l'UPN de l'AD, pour l'authentification LDAP, et l'adresse de messagerie connue de Purview.

Un changement de droits sur une étiquette est donc pris en compte au plus tard après la durée du cache. Un changement d'étiquette sur un document modifie le fichier : il est pris en compte à la synchronisation suivante.

---

## §14.7 Validation

### §14.7.1 Sonde

Avant le service, une sonde a déchiffré un seul document de test dans un conteneur, et affiché son étiquette, son propriétaire et le début de son texte. C'est elle qui a levé les inconnues : fonctionnement du SDK sous Linux, autorisation minimale, absence des droits dans la licence des documents protégés par modèle.

### §14.7.2 La vérité de référence de Purview

Avant de tester le RAG, `/droits` a été interrogé directement pour chaque compte et chaque étiquette indexée :

| Étiquette | Propriétaire | Directeur financier | Comptable | Client |
|---|---|---|---|---|
| RH-Confidentiel | Autorisé (OWNER) | Autorisé | Autorisé | Autorisé |
| Direction - Documents | Autorisé (OWNER) | Refusé | Refusé | Refusé |
| Finances-Confidentiel | Autorisé (OWNER) | Autorisé | Refusé | Refusé |

L'étiquette RH autorise tous les comptes : elle contient une entrée `AuthenticatedUsers` restée de tests antérieurs (§14.8.3).

### §14.7.3 Matrice

Trois questions, chacune visant un document qui n'existe qu'en version chiffrée, et contenant un terme propre à ce document, pour que la recherche le trouve à coup sûr : un refus prouve alors que c'est le filtre qui a retiré le document.

| Question | Propriétaire | Directeur financier | Comptable | Client |
|---|---|---|---|---|
| Q1. « Quel code de vérification commence par FIN-CHIF ? » | ✓ | ✓ **les deux conditions** | ✗ **Purview** (site accessible) | ✗ SharePoint |
| Q2. « Que contient la note disciplinaire de … ? » | ✓ | ✗ SharePoint | ✗ **SharePoint** (étiquette accessible) | ✗ **SharePoint** (étiquette accessible) |
| Q3. « Que dit le reglement interieur 2025 ? » | ✓ | ✗ **Purview** | ✗ **Purview** | ✗ **Purview** |

**12 réponses sur 12 conformes.** Chaque refus est expliqué, dans les journaux de `rag-api`, par la bonne condition :

```
[PURVIEW] comptable@votre-domaine.ch sur l'étiquette <identifiant-étiquette-Finances> : refusé
[PURVIEW] 4 chunk(s) chiffré(s) retiré(s) pour comptable@votre-domaine.ch
```

Pour Q2, aucune décision Purview n'apparaît : le document est écarté dès Qdrant, par la première condition.

La matrice démontre :
- **la double condition dans les deux sens** : SharePoint protège les documents RH que l'étiquette laisserait lire à tous, Purview protège les documents Direction rangés sur un site ouvert à tous ;
- **qu'elle laisse passer qui doit passer** : le directeur financier, sans être propriétaire, obtient le document Finances ;
- **le cas central** : le comptable a accès au site Finances, et c'est Purview seul qui lui retire le document chiffré.

Q3 est volontairement écrite **sans accents** : voir §14.8.1.

---

## §14.8 Limites et constats

### §14.8.1 Limites

| Limite | Détail |
|---|---|
| **Étiquette non affichée dans la réponse** | Copilot affiche l'étiquette la plus prioritaire des sources ; ce RAG ne le fait pas encore |
| **Délai de prise en compte** | Un changement de droits sur une étiquette est appliqué au plus tard après `MIP_CACHE_TTL` |
| **Double chiffrement** | Non testé ; les documents concernés ne peuvent pas être déchiffrés par le service |
| **Recherche sensible aux accents** | La recherche par mots-clés compare les mots tels quels : « règlement » et « reglement » sont deux mots différents. Le règlement du lab, rédigé sans accents, n'était pas trouvé avec une question accentuée. Une normalisation des accents est prévue |
| **Questions vagues** | Avec deux documents très proches (les deux documents de test Finances), une question générale peut faire remonter l'un et écarter l'autre. Ce n'est pas un sujet de sécurité, mais une limite de la recherche |

### §14.8.2 Tâches d'arrière-plan d'Open WebUI

Open WebUI génère automatiquement titres et suggestions en interrogeant le modèle de la conversation, c'est-à-dire `rag-api`. Chaque question déclenche alors **deux** recherches complètes (recherche, Purview, génération, juge), deux entrées dans le journal des requêtes, et deux décisions Purview simultanées, avant que le cache ne soit rempli.

Correction : dans **Réglages d'administration** → **Interface**, désactiver la génération automatique des titres et des suggestions, ou choisir un modèle de tâche Ollama direct.

### §14.8.3 Constats de gouvernance

Comme en §13.8.3, plusieurs de ces situations viennent d'essais antérieurs sur le tenant du lab, ou du jeu de démonstration lui-même. Elles sont présentées pour ce qu'elles illustrent, et reprises en recommandations dans la section gouvernance.

| Situation | Origine dans le lab | Enseignement |
|---|---|---|
| L'étiquette RH autorise `AuthenticatedUsers` | Réglage de test d'une documentation Purview antérieure, resté en place | Une étiquette nommée « Confidentiel » et chiffrée peut n'empêcher personne de lire. **Le chiffrement ne vaut que ce que valent ses droits.** Un réglage de test oublié en production est un cas réel |
| `Content.SuperUser` fonctionne sans la fonction super-utilisateur | Comportement du service, constaté | Auditer les applications qui détiennent cette autorisation (§14.4.3) |
| Compte d'administration inscrit comme super-utilisateur, et nommé dans les droits des étiquettes | Essais antérieurs | Inactif tant que la fonction est désactivée, actif dès qu'elle l'est. En entreprise : un groupe de super-utilisateurs à appartenance temporaire, des groupes plutôt que des personnes dans les droits, et un compte d'administration distinct du compte de travail |

Deux autres situations du jeu de test sont des **choix de démonstration**, pas des constats : des documents étiquetés « Direction » placés sur le site ouvert à tous (pour montrer que Purview les protège), et des copies en clair de documents chiffrés (§13.8.3). Le risque qu'elles illustrent est réel : un document mal rangé n'est protégé que par son étiquette, et une copie en clair ne l'est plus du tout.

---

## §14.9 Checklist

| Point | Vérification | Attendu |
|---|---|---|
| Prérequis | Clé d'API Qdrant, données au repos chiffrées | Les deux en place |
| Inventaire | `Get-Label -IncludeDetailedLabelActions` | Étiquettes, droits, EXTRACT, absence de double chiffrement relevés |
| Autorisations | API autorisées de `RAG-Purview-Decrypt` | `Content.SuperUser`, `Content.DelegatedReader`, `UnifiedPolicy.Tenant.Read`, consentement accordé |
| Audit `Content.SuperUser` | Commande de §14.4.3 | Seule l'application de déchiffrement apparaît |
| Clé privée | `ls -ln /etc/rag-certs/rag-purview.key` | `10001 10001`, `-rw-------` |
| Service | `docker logs mip-service` | « Moteur initialisé, service prêt » |
| Jeton | Appel sans jeton (`test_mip_service.py`) | HTTP 401 |
| Déchiffrement | `test_mip_service.py` sur un document de test | `decision: dechiffre`, contenu `PK`, code retrouvé |
| Droits | `test_droits.py`, chaque compte et chaque étiquette | Conforme à la définition des étiquettes |
| Exclusions | `MIP_ETIQUETTES_EXCLUES` | Étiquettes RH exclues en production |
| Indexation | Synchronisation `/admin/sync` | Documents chiffrés `indexé (déchiffré)`, aucune erreur |
| Matrice | Questions à terme propre, un compte par profil | Chaque refus expliqué par la bonne condition dans les journaux |
| Open WebUI | Une question, `grep -c "\[AUTH\] /v1"` | 1 requête par question |

---

[Retour au sommaire](index.md) | [Section précédente : §13 Connecteur SharePoint Online](section-13-sharepoint.md) | [Section suivante : §15 Sécurité des données](section-15-securite-donnees.md)

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
