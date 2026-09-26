---
title: "§12 Synthèse des réunions Teams | Guide de déploiement stack IA locale"
description: "Récupération des transcriptions Teams via Microsoft Graph, compte-rendu produit par un modèle local et envoyé en brouillon à l'organisateur : réglages du tenant, groupe d'adhésion, stratégie d'accès applicatif, évaluation mesurée."
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

# §12 Synthèse des réunions Teams

[Retour au sommaire](index.md) | [Section précédente : §11 Prérequis Microsoft 365](section-11-prerequis-ms365.md)

**Statut :** validé partiellement, voir les réserves en fin de section. Toute la chaîne a été exécutée en lab sur un tenant Microsoft 365 réel, de la réunion Teams jusqu'à l'email reçu par l'organisateur. Le déclenchement planifié par n8n, sans intervention manuelle, reste à observer sur une nouvelle réunion.

---

> **Ce que cette section documente :** après chaque réunion Teams transcrite, le pipeline récupère la transcription via Microsoft Graph, la fait résumer par le modèle local (décisions, actions, points ouverts) et envoie le résultat **en brouillon, à l'organisateur seul**. L'organisateur relit, corrige et décide lui-même de la diffusion. Aucune transcription ni aucun compte-rendu ne quitte le périmètre de l'organisation pour être traité par un service d'IA externe.

---

## §12.1 Architecture

### §12.1.1 Le flux

```
Réunion Teams planifiée, transcription activée
   → transcription stockée dans le tenant Microsoft 365
   → n8n (toutes les heures) → POST /teams/sync (rag-api)
        ├→ membres du groupe d'adhésion        (Graph, RAG-Identity-Resolver)
        ├→ transcriptions de chaque membre     (Graph, RAG-Teams-Reader)
        ├→ synthèse par le modèle local        (Ollama)
        └→ brouillons : objet, corps, destinataire
   → n8n → un email par brouillon, à son organisateur
```

### §12.1.2 Répartition des rôles

| Composant | Rôle |
|---|---|
| `rag-api`, module `teams_graph.py` | Lecture du groupe d'adhésion, récupération des transcriptions, fichier d'état |
| `rag-api`, module `teams.py` | Lecture du VTT, contrôle de longueur, prompt, contrôles déterministes, brouillon |
| `rag-api`, endpoint `/teams/sync` | Orchestration, journalisation nLPD |
| n8n | Planification horaire, envoi des emails, alerte en cas d'erreur |

La synthèse est faite dans `rag-api` plutôt que dans n8n : l'accès Graph par certificat existe déjà en Python (`auth.py`, §11), la journalisation nLPD aussi, et le prompt et les contrôles restent versionnés dans le code, testables et publiés, au lieu d'être enfouis dans un nœud n8n.

### §12.1.3 Pourquoi un brouillon à l'organisateur seul

- **Relecture humaine.** Le guide décisionnel recommande une validation avant la diffusion d'un résumé de réunion. Les tests de §12.7 le confirment : le modèle peut omettre un point, et une omission se repère plus difficilement qu'une erreur.
- **Pas d'élargissement de l'accès.** Le pipeline n'envoie jamais le contenu d'une réunion à quelqu'un qui n'y a pas participé. L'organisateur décide de la diffusion.
- **Simplicité.** L'envoi d'email est déjà en place dans la stack (§7). La publication dans un canal Teams par une application seule demanderait d'autres autorisations.

---

## §12.2 Réglages du tenant

### §12.2.1 Transcription des réunions

Centre d'administration Teams → **Settings & policies** → **Meeting policies** → **Global (Org-wide default)** → section **Recording & transcription**.

Valeurs par défaut constatées en lab :

| Réglage | Valeur par défaut | Commentaire |
|---|---|---|
| Transcription | On | Nécessaire au pipeline |
| Meeting recording | On | **Inutile au pipeline** : l'enregistrement vidéo stocke audio et image dans OneDrive, un volume de données personnelles sans utilité pour le compte-rendu (principe de minimisation) |
| Recordings and transcriptions automatically expire | On, 120 jours | Durée de conservation des transcriptions dans le tenant |
| Require participant agreement for recording, transcription, and Copilot | Off | Teams affiche de toute façon une bannière à tous les participants au démarrage de la transcription |

Ne pas modifier les stratégies prédéfinies (`AllOn`, `AllOff`, `Kiosk`, etc.) : elles ne s'appliquent qu'aux utilisateurs à qui elles sont attribuées explicitement. Ne pas créer de nouvelle stratégie non plus : il faudrait ensuite l'attribuer aux utilisateurs.

### §12.2.2 Accès Graph aux transcriptions : le blocage par défaut

> **Point bloquant, souvent ignoré.** Depuis l'été 2026, l'accès des applications aux transcriptions via Microsoft Graph est **désactivé par défaut** au niveau du tenant, quelles que soient les permissions accordées aux applications. Sans ce réglage, toute requête renvoie `403 Forbidden` avec le code `GraphAccessToTranscriptsDisabled`, sans contournement possible côté application.

Centre d'administration Teams → **Settings & policies** → **Global (Org-wide default) settings** → **Meeting settings** → section **Transcript API access** :

1. **Microsoft Graph access** : On.
2. **Configure** → **Include speaker attribution** : On.
3. **Save**, en bas de la page.

**L'attribution des intervenants est indispensable.** Sans elle, la transcription est récupérable mais sans le nom des intervenants : le compte-rendu ne peut plus dire qui doit faire quoi. Teams affiche à ce moment un avertissement : l'attribution peut exposer des informations personnelles ou sensibles. C'est le compromis assumé de cette section, compensé par l'envoi au seul organisateur, le contrôle des données de santé (§12.5.3) et une journalisation sans contenu.

Équivalent PowerShell :

```powershell
Set-CsTeamsMeetingConfiguration -Identity Global `
  -EnableGraphTranscriptAccess $true -EnableAttributedTranscripts $true
```

> **Avant d'activer :** ce réglage vaut pour tout le tenant. Toute application qui disposerait déjà de la permission `OnlineMeetingTranscript.Read.All` pourra lire les transcriptions. Vérifier dans Entra, **Applications d'entreprise**, les permissions des applications existantes.

---

## §12.3 Groupe d'adhésion

### §12.3.1 Le principe

Un seul groupe, `GRP-Teams-CompteRendu-IA`, joue deux rôles :

- **Il limite ce que l'application a le droit de lire.** La stratégie d'accès applicatif (§12.4.3) lui est attribuée : l'application ne peut lire que les réunions organisées par ses membres, même avec la permission Graph accordée.
- **Il définit qui le pipeline interroge.** L'API Graph exige l'identifiant de l'organisateur : le pipeline lit la liste des membres du groupe et interroge chacun d'eux.

Seules les réunions des organisateurs membres du groupe sont traitées. C'est une démarche d'adhésion volontaire, défendable au regard de la proportionnalité (nLPD) et plus simple à expliquer aux collaborateurs qu'un traitement généralisé. Retirer une personne du groupe arrête immédiatement le traitement de ses réunions.

L'attribution à tout le tenant (`-Global`) est techniquement possible, mais elle permettrait à l'application de lire les transcriptions de toutes les réunions de l'organisation, y compris celles de la direction ou des ressources humaines. Elle n'est pas recommandée.

### §12.3.2 Création

Le groupe est un **groupe de sécurité à extension messagerie**, le seul type validé en lab pour l'attribution de la stratégie d'accès. Les sources Microsoft sont contradictoires sur les autres types (groupe de sécurité simple, groupe Microsoft 365), qui n'ont pas été testés. Ce type de groupe ne se crée pas dans le portail Entra, mais en PowerShell Exchange Online :

```powershell
Install-Module ExchangeOnlineManagement -Scope AllUsers   # si absent
Connect-ExchangeOnline -UserPrincipalName <admin>@<domaine>

New-DistributionGroup -Name "GRP-Teams-CompteRendu-IA" `
  -Type Security `
  -PrimarySmtpAddress "grp-teams-cr-ia@<domaine>" `
  -Members "<organisateur>@<domaine>"

# Le groupe ne sert qu'aux autorisations : le masquer du carnet d'adresses
Set-DistributionGroup -Identity "GRP-Teams-CompteRendu-IA" `
  -HiddenFromAddressListsEnabled $true

# ID d'objet Entra du groupe, utilisé par la stratégie et par le pipeline
Get-DistributionGroup -Identity "GRP-Teams-CompteRendu-IA" |
  Format-List Name, PrimarySmtpAddress, ExternalDirectoryObjectId

Disconnect-ExchangeOnline -Confirm:$false
```

Adhésion et retrait d'un organisateur :

```powershell
Add-DistributionGroupMember    -Identity "GRP-Teams-CompteRendu-IA" -Member "prenom.nom@<domaine>"
Remove-DistributionGroupMember -Identity "GRP-Teams-CompteRendu-IA" -Member "prenom.nom@<domaine>"
```

---

## §12.4 Application et stratégie d'accès

### §12.4.1 Trois conditions cumulées

| Condition | Où | Sans elle |
|---|---|---|
| Permission Graph `OnlineMeetingTranscript.Read.All` (application), avec consentement | Entra, App Registration | Refus d'accès |
| Stratégie d'accès applicatif attribuée à l'organisateur | PowerShell Teams | Refus d'accès pour les réunions de cet organisateur |
| Transcript API access activé | Centre d'administration Teams (§12.2.2) | `403 GraphAccessToTranscriptsDisabled` |

### §12.4.2 App Registration `RAG-Teams-Reader`

Troisième application de la Partie 3, dédiée à la lecture des transcriptions. Elle ne donne accès ni à l'annuaire (rôle de `RAG-Identity-Resolver`, §11) ni aux documents SharePoint.

Certificat, généré sur la VM (même procédure qu'en §11.3) :

```bash
cd /etc/rag-certs
sudo openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout rag-teams.key -out rag-teams.crt \
  -days 730 -subj "/CN=RAG-Teams-Reader"
sudo chmod 600 rag-teams.key
sudo cat rag-teams.crt
openssl x509 -in rag-teams.crt -noout -fingerprint -sha1 | tr -d ':' | cut -d= -f2
```

Dans le centre d'administration Entra :

1. **Inscriptions d'applications** → **Nouvelle inscription** : `RAG-Teams-Reader`, comptes de cet annuaire uniquement, sans URI de redirection.
2. **Certificats et secrets** → charger `rag-teams.crt`. L'empreinte affichée doit correspondre à celle calculée sur la VM.
3. **Autorisations de l'API** → Microsoft Graph → **Autorisations d'application** → `OnlineMeetingTranscript.Read.All` → consentement administrateur.
4. Supprimer la permission déléguée `User.Read` ajoutée par défaut. Aucun secret client.

### §12.4.3 Stratégie d'accès applicatif

```powershell
Install-Module MicrosoftTeams -Scope AllUsers   # si absent
Connect-MicrosoftTeams

New-CsApplicationAccessPolicy -Identity "RAG-Teams-Reader-Policy" `
  -AppIds "<ID-CLIENT-RAG-TEAMS-READER>" `
  -Description "Lecture des transcriptions pour le pipeline RAG local"

Grant-CsApplicationAccessPolicy -PolicyName "RAG-Teams-Reader-Policy" `
  -Group "<ID-OBJET-DU-GROUPE>"

# Vérifications
Get-CsApplicationAccessPolicy -Identity "RAG-Teams-Reader-Policy" | Format-List
Get-CsGroupPolicyAssignment -PolicyType ApplicationAccessPolicy
Get-CsUserPolicyAssignment -Identity "<organisateur>@<domaine>" -PolicyType ApplicationAccessPolicy

Disconnect-MicrosoftTeams
```

**Validé en lab, septembre 2026 :** l'attribution par groupe fonctionne avec l'**ID d'objet** du groupe (`ExternalDirectoryObjectId`), et la stratégie est apparue immédiatement dans la stratégie effective du membre :

```
PolicyType              PolicyName              PolicySource
----------              ----------              ------------
ApplicationAccessPolicy RAG-Teams-Reader-Policy {RAG-Teams-Reader-Policy}
```

> **Une seule stratégie d'accès par utilisateur.** Attribuer une stratégie d'accès applicatif à un utilisateur remplace celle qu'il avait déjà. Si une autre application (enregistrement, conformité) utilise une stratégie d'accès, attribuer celle-ci l'écrase silencieusement pour les membres du groupe. Il faut alors une stratégie commune qui liste les identifiants des deux applications dans `-AppIds`.

---

## §12.5 Code

### §12.5.1 Fichiers

| Fichier | Rôle |
|---|---|
| `api/teams.py` | Lecture du VTT, contrôle de longueur, synthèse, contrôles, brouillon |
| `api/teams_graph.py` | Groupe d'adhésion, `getAllTranscripts`, téléchargement du VTT, fichier d'état |
| `api/anon_main.py` | Endpoints `/teams/summarize` et `/teams/sync` |
| `api/Dockerfile` | Copie de `teams.py` et `teams_graph.py` dans l'image |
| `N8N/n8n-teams-sync.json` | Workflow de planification et d'envoi |

### §12.5.2 Récupération des transcriptions

`getAllTranscripts` renvoie les transcriptions de toutes les réunions **planifiées** dont l'utilisateur indiqué est l'organisateur, sur une période donnée (48 heures par défaut, `TEAMS_LOOKBACK_HOURS`). Le contenu est téléchargé au format VTT. Si le contenu n'est pas encore disponible (404), la transcription est simplement reprise au passage suivant.

Les identifiants des transcriptions traitées sont conservés dans `/var/log/rag/teams_state.json`, **jamais leur contenu**, et purgés après 130 jours, au-delà de l'expiration des transcriptions dans Teams. Une transcription n'est marquée comme traitée qu'une fois son brouillon produit.

Le nombre de synthèses par passage est limité (`TEAMS_MAX_PAR_SYNC`, 3 par défaut) : chaque synthèse prend une à deux minutes sur CPU.

### §12.5.3 Synthèse

**Contrôle de longueur.** Ollama tronque silencieusement le texte qui dépasse sa fenêtre de contexte, dont la valeur par défaut dépend de la mémoire vidéo disponible (4 096 tokens en dessous de 24 Go). Une réunion de plus de quelques minutes serait coupée sans aucune erreur, et le compte-rendu ignorerait la fin de la réunion. `teams.py` demande donc explicitement une fenêtre de 16 384 tokens (`SUMMARY_NUM_CTX`) et **refuse** une transcription trop longue (HTTP 413) plutôt que de la tronquer. Le nombre de tokens réellement consommés est journalisé pour vérification.

**Prompt.** Température 0, sortie JSON imposée, transcription placée entre balises et neutralisée contre l'injection de prompt (même principe qu'en §9.6.1). Les règles demandent de n'utiliser que la transcription, de ne retenir que la valeur finale d'une date ou d'un montant modifié, d'écarter les idées évoquées au conditionnel, et de n'inclure aucune information de santé ou de vie privée.

**Contrôles déterministes**, affichés en tête du brouillon sous « Points à vérifier en priorité » :

- chiffres présents dans le compte-rendu mais absents de la transcription (les nombres écrits en lettres, comme « trois ans », sont pris en compte) ;
- responsable d'action qui n'est pas intervenu dans la réunion ;
- termes évoquant une donnée de santé ;
- échéances reprises automatiquement (voir ci-dessous).

**Complément des échéances.** Le modèle écrit souvent l'échéance dans le texte de l'action (« d'ici le vendredi 9 octobre ») mais laisse le champ échéance à « Non précisée ». Plutôt que de modifier le prompt, ce qui a provoqué des inventions lors des essais (§12.7.2), une expression régulière recopie dans le champ la date ou le délai **déjà présent dans le texte de l'action**. Rien n'est inventé, et une alerte le signale.

La liste des participants est extraite du VTT, pas produite par le modèle.

### §12.5.4 Journalisation

Chaque synthèse ajoute une ligne de type `teams_summary` au journal nLPD (§9.4) : horodatage, organisateur, empreinte de la transcription, nombre de participants et d'alertes. **Ni la transcription ni le compte-rendu ne sont conservés** par le pipeline.

### §12.5.5 Déploiement

Variables à ajouter au `.env` :

```bash
TEAMS_CLIENT_ID=<ID-CLIENT-RAG-TEAMS-READER>
TEAMS_CERT_PATH=/etc/rag-certs/rag-teams.crt
TEAMS_KEY_PATH=/etc/rag-certs/rag-teams.key
TEAMS_CERT_THUMBPRINT=<EMPREINTE-SHA1-SANS-DEUX-POINTS>
TEAMS_GROUP_ID=<ID-OBJET-DU-GROUPE>
TEAMS_LOOKBACK_HOURS=48
TEAMS_MAX_PAR_SYNC=3
TEAMS_STATE_FILE=/var/log/rag/teams_state.json
```

La lecture du groupe utilise `RAG-Identity-Resolver` : les variables `ENTRA_*` de §11 doivent être renseignées.

Ajout des variables au service `rag-api` du `docker-compose.yml` :

```bash
cd /root/rag-stack
cp docker-compose.yml docker-compose.yml.bak
grep -q 'TEAMS_CLIENT_ID=' docker-compose.yml || for v in TEAMS_STATE_FILE TEAMS_MAX_PAR_SYNC TEAMS_LOOKBACK_HOURS TEAMS_GROUP_ID TEAMS_CERT_THUMBPRINT TEAMS_KEY_PATH TEAMS_CERT_PATH TEAMS_CLIENT_ID; do
  sed -i "/- ENTRA_CERT_THUMBPRINT=\${ENTRA_CERT_THUMBPRINT}/a\      - $v=\${$v}" docker-compose.yml
done
docker compose config --quiet && echo "Compose OK"
```

Le dossier `/etc/rag-certs` est déjà monté dans le conteneur depuis §11. Copie des fichiers et reconstruction :

```bash
sudo cp /home/<utilisateur>/main.py /home/<utilisateur>/teams.py \
        /home/<utilisateur>/teams_graph.py /home/<utilisateur>/Dockerfile /root/rag-stack/api/
cd /root/rag-stack
docker compose build --no-cache rag-api
docker compose up -d rag-api
sleep 15
docker logs rag-api 2>&1 | grep "BM25\|startup\|Uvicorn\|Traceback" | tail -5
```

---

## §12.6 Workflow n8n

```
Toutes les heures → POST /teams/sync
   ├→ Brouillons produits ? → un élément par brouillon → email à son destinataire
   └→ Erreurs ?            → alerte formatée          → email à l'administrateur
```

1. **Import from File** → `n8n-teams-sync.json`. Le workflow est importé inactif.
2. Nœud **POST /teams/sync** : remplacer `<ADMIN_TOKEN>` par la valeur du `.env`. Le délai d'attente est de 30 minutes, pour laisser le temps à plusieurs synthèses sur CPU.
3. Nœuds email : identifiant SMTP, expéditeur et adresse d'alerte.
4. Tester avec **Execute workflow**, puis activer.

> **L'expéditeur doit être le compte SMTP authentifié.** Avec Exchange Online, un expéditeur différent du compte de l'identifiant SMTP est refusé : `554 5.2.252 SendAsDenied`. Pour un expéditeur interne, Outlook affiche le nom du compte dans l'annuaire, pas le nom indiqué dans le message.

> **Utiliser une boîte dédiée aux comptes-rendus.** En lab, la boîte d'envoi était partagée avec les notifications d'un autre outil : le compte-rendu est arrivé sous le nom de cet outil, et une règle Outlook l'a classé avec ses alertes. En production, une boîte dédiée (par exemple `comptes-rendus-ia@<domaine>`) évite la confusion et permet une rotation de mot de passe indépendante.

**Mention n8n.** Par défaut, n8n ajoute la phrase « This email was sent automatically with n8n » en fin de message. Le fichier fourni la désactive (`appendAttribution: false` dans les options des nœuds email). Validé en lab : la mention n'apparaît plus, même si l'option n'est pas proposée dans la liste « Add option » de ce nœud importé.

**Token.** Comme pour les autres workflows, le token figure en clair dans le nœud HTTP, et donc dans tout export du workflow. L'identifiant n8n de type **Header Auth** (en-tête `Authorization`, valeur `Bearer` suivie du token) le stocke chiffré et le retire des exports. Recommandé en production pour tous les workflows de la stack.

> **Le serveur d'envoi fait partie du périmètre.** Le brouillon contient des données personnelles. S'il passe par le serveur SMTP du tenant Microsoft 365, il reste dans le même périmètre que la transcription d'origine. Un serveur d'envoi tiers ferait sortir le compte-rendu de ce périmètre.

---

## §12.7 Validation

Les fichiers de test sont fournis dans [`scripts/stack-ia-locale/teams-test/`](../../scripts/stack-ia-locale/teams-test/) : transcription fictive, corrigé, script de réunion à lire à deux et scripts de test.

> **Fichiers de test uniquement.** Rien dans `teams-test/` n'est nécessaire au fonctionnement du pipeline, qui repose sur `teams.py`, `teams_graph.py`, `main.py` et le workflow n8n. Les deux scripts (`test_teams_summary.py`, `test_teams_graph.py`) servent à valider l'installation et à évaluer la qualité des comptes-rendus. Ils s'exécutent dans le conteneur `rag-api` : les copier dans `/root/rag-pipeline`, le dossier monté dans le conteneur, uniquement le temps des tests.

### §12.7.1 Accès Graph

```bash
docker exec -e PYTHONPATH=/app -w /app rag-api python3 /rag-pipeline/test_teams_graph.py
```

`PYTHONPATH` est nécessaire : le script importe les modules de l'API, qui se trouvent dans `/app` et non dans le dossier du script.

**Validé en lab, septembre 2026 :**

```
1. Configuration et jeton RAG-Teams-Reader
   OK
2. Membres du groupe d'adhésion
   1 membre(s)
3. Transcriptions des 48 dernières heures
   <organisateur>@<domaine> : 1 transcription(s)
4. Contenu de la transcription la plus récente
   3989 caractères, 28 répliques, intervenants : [2 intervenants]
```

Le script teste les étapes dans l'ordre (jeton, groupe, transcriptions, contenu) : en cas d'échec, l'étape en cause désigne directement le réglage manquant. Le contenu récupéré via Graph est identique au fichier téléchargé depuis Teams (28 répliques dans les deux cas).

### §12.7.2 Synthèse sur transcription fictive : comparatif des prompts

Transcription fictive de 4 minutes 30, quatre intervenants, avec un corrigé noté sur 14 : 3 décisions, 4 actions, 2 points ouverts et 5 pièges (date proposée puis abandonnée, montant initial différent du montant retenu, idée au conditionnel écartée, donnée de santé d'une personne absente, invention). Quatre versions du prompt ont été comparées :

| Critère | v1 | v2 | v3 | v4 |
|---|---|---|---|---|
| Décisions | 2/3 | 2/3 | 3/3 | 2/3 |
| Actions | 4/4 | 2/4 | 4/4 | 4/4 |
| Points ouverts | 1/2 | 1/2 | 1/2 | 1/2 |
| Pièges | 5/5 | 5/5 | 4/5 | 4/5 |
| **Total** | **12** | **10** | **12** | **11** |
| Fait inventé | Non | Non | Oui | Oui |

**La version 1 est retenue**, seule version sans fait inventé à égalité de score. Enseignements :

- **Corriger un prompt a des effets de bord.** La v2 corrigeait une erreur de classement mais a vidé les champs d'échéance. La v3 corrigeait les échéances mais a inventé qu'une question serait « tranchée lors de la prochaine réunion ». Sans grille de mesure, ces régressions seraient passées inaperçues.
- **Une erreur de classement vaut mieux qu'un fait inventé.** Pour un brouillon relu par l'organisateur, une action classée par erreur en décision est visible et sans conséquence, alors qu'un fait plausible peut passer inaperçu.
- **Les contrôles par mots-clés peuvent valider une erreur.** Un contrôle automatique vérifiant la présence de « prochaine réunion » a validé la v4 alors que le report était attribué au mauvais sujet.
- **Même à température 0, la sortie varie légèrement** d'un passage à l'autre (formulations), sans changement de fond. Une évaluation sérieuse demande plusieurs passages et une grille qui juge le contenu.

### §12.7.3 Réunion réelle

Réunion planifiée entre l'organisateur et une participante externe (compte invité), d'après un script fourni avec son corrigé sur 13 points. La participante a été informée de la transcription et du traitement par IA au début de la réunion, et son accord figure dans la transcription.

**Reconnaissance vocale.** Bonne dans l'ensemble, avec des erreurs typiques qui sont reprises telles quelles dans le compte-rendu :

| Prononcé | Transcrit |
|---|---|
| Horlogerie Vallon | « horlogerie wallon » |
| Je confirme **au** fournisseur | « Je confirme **mon** fournisseur » |
| 2 350, 2 100 | « 2350 », « 2100 » |
| 9 heures à midi | « 09h00 à 12h00 » |

La transcription contient aussi du bruit réel : essai du micro, échange hors script au milieu de la réunion. Ce passage a été correctement ignoré par le modèle.

**Attribution.** La participante a rejoint la réunion sans se connecter à son compte invité : ses répliques sont attribuées au nom qu'elle a saisi à l'entrée, et non au nom de son compte. Le modèle a néanmoins relié correctement le prénom prononcé à cet intervenant pour les actions.

**Résultat : 11/13, aucun fait inventé.**

| Critère | Score | Détail |
|---|---|---|
| Décisions | 2/3 | Date de l'atelier et engagement sur les licences exacts. **La question de la permanence, reportée à une réunion ultérieure, est omise** |
| Actions | 3/4 | Responsables justes. Échéances reprises du texte pour trois actions. « Aujourd'hui », absent du texte de l'action, est perdu |
| Point ouvert | 1/1 | Présent |
| Pièges | 5/5 | Date écartée, devis initial, idée écartée et donnée de santé tous exclus |

**Durée : 75 à 126 secondes sur CPU** pour une réunion de 3 minutes, selon que le modèle était déjà chargé avec la fenêtre de 16 384 tokens ou devait être rechargé (voir §12.8).

### §12.7.4 Chaîne complète

```bash
cd /root/rag-stack
TOKEN=$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2-)
docker compose exec n8n wget -qO- --post-data='' -T 1200 \
  --header="Authorization: Bearer $TOKEN" \
  http://rag-api:8080/teams/sync > /tmp/teams_sync.json
unset TOKEN
python3 -c "import json; d=json.load(open('/tmp/teams_sync.json')); print(d['brouillons_count'], d['erreurs'])"
```

**Validé en lab, septembre 2026 :** un brouillon produit à partir de la transcription récupérée via Graph, adressé à l'organisateur. Un second appel immédiat renvoie 0 brouillon : la transcription est marquée comme traitée. Lancé depuis n8n, le workflow a envoyé le brouillon, reçu par l'organisateur.

---

## §12.8 Limites et points d'attention

**Omissions.** C'est la limite principale observée : le modèle a omis une question reportée à une réunion ultérieure. Une omission est plus difficile à repérer à la relecture qu'une erreur, et aucun contrôle automatique ne la détecte. L'organisateur doit relire le brouillon en ayant la réunion en tête.

**Reconnaissance vocale.** Les noms propres et certaines tournures sont mal transcrits, et le compte-rendu reprend ces erreurs. Ce ne sont pas des erreurs du modèle de synthèse, mais elles doivent être corrigées à la relecture.

**Participants externes.** Un invité anonyme choisit librement le nom affiché dans la transcription. Ses propos deviennent des données personnelles traitées par l'organisation : il doit être informé, ce que fait la bannière de Teams, et l'information orale en début de réunion est une bonne pratique.

**Types de réunions.** Seules les réunions **planifiées** sont prises en charge. Les réunions de canal et les réunions créées sans événement de calendrier ne sont pas renvoyées par l'API.

**Performance sur CPU.** Une à deux minutes pour quelques minutes de réunion. Une réunion d'une heure prendra nettement plus longtemps. Quand le modèle est partagé avec le RAG, qui l'utilise avec une fenêtre de 4 096 tokens, Ollama doit le recharger à chaque changement de taille de fenêtre : environ 50 secondes de différence mesurées en lab. Deux solutions, à évaluer avec un GPU (§10) : une fenêtre commune, ou un modèle dédié à la synthèse (`SUMMARY_MODEL`).

**Limites du modèle.** Avec qwen2.5:14b, les ajustements de prompt déplacent les erreurs sans les supprimer. Le gain suivant viendra d'un modèle plus récent de même taille ou d'un matériel plus puissant, à mesurer avec le même fichier et la même grille.

**Expiration.** Les transcriptions expirent après 120 jours dans le tenant : une réunion non traitée dans ce délai ne pourra plus l'être.

**Réserve de validation.** Le déclenchement planifié, sans intervention manuelle, sur une nouvelle réunion, reste à observer. Cette section passera au statut « validé en lab » après ce test.

---

## §12.9 Checklist

| Point | Vérification | Résultat attendu |
|---|---|---|
| Transcription active | Stratégie de réunion Global | Transcription : On |
| Accès Graph | Meeting settings, Transcript API access | Microsoft Graph access et speaker attribution : On |
| Groupe d'adhésion | `Get-DistributionGroupMember` | Organisateurs concernés uniquement |
| Stratégie d'accès | `Get-CsUserPolicyAssignment` | `RAG-Teams-Reader-Policy` |
| Chaîne Graph | `test_teams_graph.py` | Quatre étapes réussies, intervenants nommés |
| Synthèse | `test_teams_summary.py` avec le fichier fictif | Pas de fait inventé, pièges évités |
| Double traitement | Second appel à `/teams/sync` | 0 brouillon |
| Envoi | Exécution du workflow n8n | Brouillon reçu, bon expéditeur, sans mention n8n |
| Journal | `grep teams_summary /var/log/rag/rag-queries.jsonl` | Une ligne par synthèse, sans contenu |

---

§13 Connecteur SharePoint Online *(à venir)*

---

*Validé en lab sur VM-RAG-LAB, septembre 2026, sur un tenant Microsoft 365 synchronisé par Entra Connect, avec qwen2.5:14b sur CPU. Les durées et scores mesurés valent pour cette configuration.*
