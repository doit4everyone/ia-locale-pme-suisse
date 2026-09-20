---
title: "§5 Connecteurs SMB et cloisonnement documentaire | Guide de déploiement stack IA locale"
description: "Connecteur file server Windows SMB, lecture des ACL NTFS, résolution LDAP et filtrage Qdrant par identité utilisateur."
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

# §5 Connecteurs SMB et cloisonnement documentaire

[Retour au sommaire](index.md) | [Section précédente : §4 Interfaces utilisateur](section-04-onyx.md)

**Statut :** validé en lab sur VM-RAG-LAB, septembre 2026. Formats indexés : `.docx`, `.pdf`, `.pptx`, `.txt`, `.md`. Les cas de test documentés ont été reproduits en session avec des comptes et corpus réels.

---

> **Ce que cette section documente :** comment connecter la stack RAG à un file server Windows, propager les ACL NTFS jusqu'aux chunks Qdrant, et filtrer les résultats selon l'identité AD de l'utilisateur connecté. Le résultat : un utilisateur ne voit que les documents auxquels ses groupes AD donnent accès sur le file server.

---

## §5.1 Principe : deux champs, deux rôles distincts

La première décision architecturale est de séparer clairement les deux types de métadonnées dans le payload Qdrant.

| Champ | Origine | Usage |
|---|---|---|
| `autorises[]` | ACL NTFS, lu par smbcacls | Sécurité, filtrage d'accès |
| `org_name` | Déduction heuristique | Confort de navigation uniquement |

`autorises[]` est une donnée **constatée** : elle reflète qui a réellement accès sur le file server. `org_name` est une donnée **déduite** par heuristique depuis le contenu ou la structure des dossiers. La confusion entre les deux est la cause principale des failles de cloisonnement dans les déploiements RAG d'entreprise.

> **Règle absolue :** `org_name` ne doit jamais entrer dans une décision d'accès. Le cloisonnement repose exclusivement sur `autorises[]`.

---

## §5.2 Préparation du file server Windows

### §5.2.1 Structure des dossiers et des partages SMB

La structure du file server conditionne la qualité du cloisonnement. Une organisation par département est la plus courante dans une PME.

> **`<NOM-FILESERVER>`** désigne dans ce guide un serveur membre du domaine AD, distinct du contrôleur de domaine. Il héberge les partages SMB et gère les ACL NTFS. Dans un déploiement typique, c'est un Windows Server 2019 ou 2022 joint au domaine. Ne pas installer le rôle file server sur le contrôleur de domaine.

```
D:\FileService\
├── CLIENTS\          → partage SMB "CLIENTS"
│   ├── Client A\
│   └── Client B\
├── DIRECTION\        → partage SMB "DIRECTION"
├── RH\               → partage SMB "RH"
│   ├── CONTRATS DE TRAVAIL\
│   └── POLITIQUE RH\
├── COMPTABILITE\     → partage SMB "COMPTABILITE"
└── SERVICE INFO\     → partage SMB "SERVICE INFO"
    └── ADMIN\
```

Créer également un partage racine pour l'indexation unifiée :

```powershell
# Partage racine pour l'indexeur (accès lecture à tous les départements)
New-SmbShare -Name "FileService" -Path "D:\FileService" `
    -FullAccess "DOMAINE\Admins du domaine" `
    -ReadAccess "DOMAINE\svc-rag" `
    -Description "Racine FileService - indexeur RAG"
```

### §5.2.2 Groupes AD par département

Créer un groupe de sécurité AD par périmètre d'accès. Ne jamais utiliser `Utilisateurs du domaine` comme groupe d'accès aux données sensibles.

```powershell
# Adapter le chemin de l'OU à votre organisation
$ouGroupes = "OU=GROUPES,DC=domaine,DC=ch"

New-ADGroup -Name "GRP-Clients" -GroupScope Global -GroupCategory Security `
    -Path $ouGroupes -Description "Accès documents clients"

New-ADGroup -Name "GRP-RH" -GroupScope Global -GroupCategory Security `
    -Path $ouGroupes -Description "Accès documents RH"

New-ADGroup -Name "GRP-Direction" -GroupScope Global -GroupCategory Security `
    -Path $ouGroupes

New-ADGroup -Name "GRP-Finances" -GroupScope Global -GroupCategory Security `
    -Path $ouGroupes

New-ADGroup -Name "GRP-ServiceInfo" -GroupScope Global -GroupCategory Security `
    -Path $ouGroupes
```

### §5.2.3 ACL NTFS par dossier

Casser l'héritage et poser des ACL explicites sur chaque dossier. La permission `Modify` est suffisante pour les utilisateurs : elle permet la lecture, l'écriture et la suppression de fichiers, mais pas la modification des ACL elles-mêmes. Ne jamais accorder `FullControl` sur un dossier source de RAG : un utilisateur avec `FullControl` peut modifier les ACL du dossier et casser le cloisonnement depuis l'intérieur.

```powershell
function Set-DossierACLPropre {
    param($Chemin, $Groupe)

    $acl = Get-Acl $Chemin
    # Casser l'héritage en conservant les règles existantes
    $acl.SetAccessRuleProtection($true, $true)
    Set-Acl $Chemin $acl

    $acl = Get-Acl $Chemin
    # Retirer Utilisateurs du domaine
    $acl.Access | Where-Object {
        $_.IdentityReference -like "*Utilisateurs du domaine*"
    } | ForEach-Object { $acl.RemoveAccessRule($_) | Out-Null }

    # Ajouter le groupe métier avec Modify (pas FullControl)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        "DOMAINE\$Groupe", "Modify",
        "ContainerInherit,ObjectInherit", "None", "Allow"
    )
    $acl.AddAccessRule($rule)
    Set-Acl $Chemin $acl
    Write-Host "OK : $Chemin -> $Groupe (Modify)"
}

Set-DossierACLPropre "D:\FileService\CLIENTS"         "GRP-Clients"
Set-DossierACLPropre "D:\FileService\RH"              "GRP-RH"
Set-DossierACLPropre "D:\FileService\DIRECTION"       "GRP-Direction"
Set-DossierACLPropre "D:\FileService\COMPTABILITE"    "GRP-Finances"
Set-DossierACLPropre "D:\FileService\SERVICE INFO\ADMIN" "GRP-ServiceInfo"
```

> **Sur les accès nominatifs :** une ACL posée directement sur un compte utilisateur (`DOMAINE\prenom.nom`) fonctionne et est correctement lue par `acl_resolver.py`. Elle apparaîtra dans `autorises[]` sous la forme `DOMAINE\prenom.nom`, et `auth.py` l'ajoutera automatiquement dans les groupes résolus de l'utilisateur concerné (voir §5.5). C'est un comportement intentionnel, utile pour les exceptions ponctuelles. Par hygiène, préférer les groupes pour les accès structurels et réserver les accès nominatifs aux exceptions documentées.

### §5.2.4 Compte de service svc-rag

Créer un compte de service dédié avec accès lecture à tous les partages. Ce compte peut lire l'intégralité du file server : c'est la condition de l'indexation, et cela déplace le risque vers ce compte et son mot de passe. Le traiter comme un compte à privilèges : mot de passe long et unique, rotation planifiée, pas de session interactive, accès SSH désactivé, journalisation des accès activée sur le contrôleur de domaine.

```powershell
# Adapter le chemin de l'OU à votre organisation
New-ADUser -Name "svc-rag" `
    -SamAccountName "svc-rag" `
    -UserPrincipalName "svc-rag@domaine.ch" `
    -AccountPassword (ConvertTo-SecureString "<mot-de-passe-fort>" -AsPlainText -Force) `
    -PasswordNeverExpires $false `
    -CannotChangePassword $true `
    -Enabled $true `
    -Path "OU=COMPTES-SERVICE,DC=domaine,DC=ch" `
    -Description "Compte de service indexeur RAG - lecture seule"

# Ajouter aux groupes nécessaires pour lire les ACL de tous les partages
Add-ADGroupMember -Identity "GRP-Clients"    -Members "svc-rag"
Add-ADGroupMember -Identity "GRP-RH"         -Members "svc-rag"
Add-ADGroupMember -Identity "GRP-Direction"  -Members "svc-rag"
Add-ADGroupMember -Identity "GRP-Finances"   -Members "svc-rag"
Add-ADGroupMember -Identity "GRP-ServiceInfo" -Members "svc-rag"
```

---

## §5.3 Montage des partages sur VM-RAG-LAB

### §5.3.1 Prérequis

```bash
# Installer les outils SMB et LDAP
sudo apt install -y cifs-utils smbclient samba-common-bin ldap-utils

# Configurer le DNS pour résoudre les noms AD
sudo nano /etc/systemd/resolved.conf
```

Ajouter dans le fichier :

```ini
[Resolve]
DNS=<IP-DC>
Domains=domaine.ch
```

```bash
sudo systemctl restart systemd-resolved

# Vérifier la résolution
nslookup <NOM-FILESERVER>
# doit retourner l'IP du file server
```

### §5.3.2 Fichier de credentials CIFS

Ne jamais passer le mot de passe en ligne de commande ou dans l'option `-o password=` : il apparaît dans la liste des processus (`ps aux`) et dans l'historique du shell, lisibles par tout utilisateur de la machine.

```bash
# Créer le fichier de credentials
sudo nano /etc/smbcredentials/svc-rag

# Contenu du fichier :
username=svc-rag
password=<mot-de-passe-fort>
domain=DOMAINE

# Protéger en lecture root uniquement
sudo chmod 600 /etc/smbcredentials/svc-rag
sudo chown root:root /etc/smbcredentials/svc-rag
```

### §5.3.3 Monter le partage racine

```bash
sudo mkdir -p /mnt/fileservice-root

sudo mount -t cifs //<NOM-FILESERVER>/FileService /mnt/fileservice-root \
    -o credentials=/etc/smbcredentials/svc-rag,uid=1000,gid=1000

# Vérifier
ls /mnt/fileservice-root/
# doit afficher : CLIENTS  COMPTABILITE  DIRECTION  RH  SERVICE INFO  ...
# Le répertoire DfsrPrivate est un répertoire système de réplication DFS,
# ainsi que System Volume Information et $RECYCLE.BIN.
# Ces répertoires sont dans EXCLUDE_PATTERNS d'indexer.py et ne sont pas indexés.
# Formats indexés : .docx, .pdf, .pptx, .txt, .md
# Les PDF scannés sans couche texte produisent un avertissement et tombent en quarantaine.
# Les tables et SmartArt PowerPoint ne sont pas extraits.
```

Pour rendre le montage persistant après redémarrage, ajouter dans `/etc/fstab` :

```bash
sudo tee -a /etc/fstab << 'FSTAB'

# Partage SMB FileService (corpus RAG, monté par svc-rag)
//<NOM-FILESERVER>/FileService /mnt/fileservice-root cifs credentials=/etc/smbcredentials/svc-rag,vers=3.1.1,uid=1000,gid=1000,rw,soft,nofail 0 0
FSTAB
```

`soft` : si le serveur est inaccessible, les opérations I/O retournent une erreur au lieu de bloquer indéfiniment. `nofail` : si le partage est inaccessible au démarrage, la VM démarre quand même au lieu de rester bloquée en attente.

Tester sans rebooter :

```bash
sudo mount -a
mount | grep fileservice
ls /mnt/fileservice-root | head -5
```

> **Rotation du mot de passe :** le fichier `/etc/smbcredentials/svc-rag` doit être mis à jour en même temps que `.env` lors de la rotation (§9.5.1). Si le fichier contient l'ancien mot de passe, le montage tombe au prochain reboot sans message d'erreur explicite.

> **Pourquoi le partage racine ?** L'indexeur et le résolveur d'ACL doivent partager la même racine pour que les chemins relatifs soient identiques dans Qdrant. Si l'indexeur tourne depuis `/mnt/fileservice-root` et stocke `CLIENTS/ClientA/contrat.docx`, le résolveur doit calculer ce chemin depuis la même racine.

---

## §5.4 Résolveur d'ACL : acl_resolver.py

`acl_resolver.py` lit les ACL NTFS de chaque fichier via `smbcacls` et met à jour le champ `autorises[]` dans le payload Qdrant. Il tourne séparément de l'indexeur parce que les permissions peuvent changer sans que le contenu des fichiers ne change.

> **Fenêtre de péremption :** entre deux passes du résolveur, un droit révoqué reste actif dans l'index. Si la cadence de resynchronisation est d'une heure, un utilisateur dont l'accès vient d'être révoqué peut encore interroger les documents concernés pendant au maximum une heure. C'est un arbitrage entre performance (éviter un appel smbcacls à chaque requête) et conformité. La cadence est à définir selon les exigences de l'organisation. La synchronisation récurrente est documentée dans §7.

### §5.4.1 Installation

```bash
cd /root/rag-pipeline
source .venv/bin/activate
# qdrant-client et httpx sont déjà installés pour l'indexeur
# smbclient est installé au §5.3.1
```

Copier `acl_resolver.py` dans `/root/rag-pipeline/`.

### §5.4.2 Variables d'environnement

```bash
# Variables requises (à ajouter dans le fichier .env ou à exporter)
export SMB_USER=svc-rag
export SMB_CREDENTIALS=/etc/smbcredentials/svc-rag
export SMB_DOMAIN=DOMAINE
export QDRANT_URL=http://localhost:6333
export QDRANT_COLLECTION=documents
```

### §5.4.3 Premier lancement en dry-run

Toujours tester en dry-run avant d'écrire dans Qdrant.

```bash
python acl_resolver.py \
    --share //<NOM-FILESERVER>/FileService \
    --mount /mnt/fileservice-root \
    --dry-run
```

Résultat attendu :

```
[1/12] CLIENTS\ClientA\contrat_maintenance.docx
Autorises (3) : DOMAINE\Administrateur, DOMAINE\Admins du domaine, DOMAINE\GRP-Clients
  [DRY-RUN] 7 chunks
    autorises  : ['DOMAINE\\Administrateur', 'DOMAINE\\Admins du domaine', 'DOMAINE\\GRP-Clients']
→ 7 chunks mis à jour
```

### §5.4.4 Lancement réel

```bash
python acl_resolver.py \
    --share //<NOM-FILESERVER>/FileService \
    --mount /mnt/fileservice-root
```

### §5.4.5 Vérifier le payload Qdrant

```bash
curl -s http://localhost:6333/collections/documents/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"must": [{"key": "source",
      "match": {"value": "CLIENTS/ClientA/contrat_maintenance.docx"}}]},
    "limit": 1,
    "with_payload": true
  }' | python3 -c "
import json, sys
r = json.load(sys.stdin)
p = r['result']['points'][0]['payload']
print('source:', p.get('source'))
print('autorises:', p.get('autorises'))
print('acl_updated_at:', p.get('acl_updated_at'))
"
```

Résultat attendu :

```
source: CLIENTS/ClientA/contrat_maintenance.docx
autorises: ['DOMAINE\\Administrateur', 'DOMAINE\\Admins du domaine', 'DOMAINE\\GRP-Clients']
acl_updated_at: 2026-09-10T11:03:30Z
```

### §5.4.6 Rapport de quarantaine ACL

Le résolveur signale les fichiers présents sur le partage mais absents de Qdrant. Le rapport JSON est sauvegardé dans le dossier du script.

```
RAPPORT ACL RESOLVER
Fichiers traités        : 12
Chunks mis à jour       : 68
Fichiers sans ACL       : 0
Fichiers non indexés    : 3  ← à indexer avec indexer.py
```

---

## §5.5 Authentification utilisateur : auth.py

`auth.py` résout les groupes AD d'un utilisateur à partir de son email, via LDAP, et retourne la liste au format `DOMAINE\Groupe` compatible avec `autorises[]`.

### §5.5.1 Principe

```
Utilisateur connecté → email → LDAP → groupes AD → filtre Qdrant
```

La résolution se fait en deux étapes : trouver le compte par son `userPrincipalName`, puis récupérer ses groupes via `memberOf` avec récursivité pour les groupes imbriqués.

### §5.5.2 Installation

`auth.py`, `ldap3`, et le `Dockerfile` complet sont décrits en §3. La stack déployée en §3 inclut déjà tout le nécessaire. Aucune modification manuelle du `requirements.txt` n'est nécessaire si §3 a été suivi.

Pour vérifier que `ldap3` est bien dans l'image en place :

```bash
docker exec rag-api python3 -c "import ldap3; print('ldap3 OK')"
```

### §5.5.3 Variables d'environnement

Ajouter dans `/root/rag-stack/.env` :

```bash
LDAP_HOST=<IP-DC>
LDAP_PORT=636
LDAP_USE_TLS=true
LDAP_BASE_DN=DC=domaine,DC=ch
LDAP_BIND_DN=CN=svc-rag,OU=COMPTES-SERVICE,DC=domaine,DC=ch
LDAP_BIND_PWD=<mot-de-passe-fort>
LDAP_DOMAIN=DOMAINE
```

> **`LDAP_BIND_PWD` en clair dans le `.env` :** ce compte lit l'annuaire AD complet pour résoudre les groupes. Traiter le fichier `.env` comme un secret : droits 600, propriétaire root, jamais commité dans Git. En production, préférer un gestionnaire de secrets (HashiCorp Vault, Azure Key Vault) ou les secrets Docker Swarm.

Ajouter dans le service `rag-api` du `docker-compose.yml` :

```yaml
rag-api:
  environment:
    - LDAP_HOST=${LDAP_HOST}
    - LDAP_PORT=${LDAP_PORT}
    - LDAP_USE_TLS=${LDAP_USE_TLS}
    - LDAP_BASE_DN=${LDAP_BASE_DN}
    - LDAP_BIND_DN=${LDAP_BIND_DN}
    - LDAP_BIND_PWD=${LDAP_BIND_PWD}
    - LDAP_DOMAIN=${LDAP_DOMAIN}
```

### §5.5.4 Points de sécurité

**Injection LDAP :** l'email reçu du header HTTP est échappé via `escape_filter_chars()` avant injection dans le filtre LDAP. Un email malformé comme `user@domaine)(|(cn=*)` ne peut pas casser la requête.

**Groupes imbriqués :** `memberOf` ne remonte que les appartenances directes. Si un utilisateur appartient à `GRP-Support` qui est lui-même membre de `GRP-Finance`, une implémentation naïve manquerait `GRP-Finance`. `auth.py` résout récursivement les groupes parents jusqu'à épuisement.

**Deny by default :** en cas d'erreur LDAP ou d'utilisateur introuvable, `auth.py` retourne une liste vide. L'utilisateur ne voit aucun document.

**Cache TTL :** les groupes sont mis en cache 5 minutes (configurable via `GROUPS_CACHE_TTL`) pour éviter un appel LDAP bloquant à chaque requête RAG.

> **Note sur `tokenGroups` :** l'attribut calculé AD `tokenGroups` résout nativement les groupes imbriqués en une seule requête, mais nécessite des droits étendus sur l'AD que le compte `svc-rag` n'a généralement pas. La récursivité sur `memberOf` est plus portable.

---

## §5.6 Configuration LDAP dans Open WebUI

Open WebUI doit transmettre l'identité de l'utilisateur connecté à la RAG API. Deux étapes sont nécessaires.

### §5.6.1 Activer la transmission de l'identité

Dans `docker-compose.yml`, ajouter la variable d'environnement au service `open-webui` :

```yaml
open-webui:
  environment:
    - ENABLE_FORWARD_USER_INFO_HEADERS=true
```

Sans cette variable, Open WebUI traite la RAG API comme un simple endpoint OpenAI et ne transmet pas l'identité. Les headers transmis sont `x-openwebui-user-name`, `x-openwebui-user-email`, `x-openwebui-user-id` et `x-openwebui-user-role`.

```bash
cd /root/rag-stack
docker compose up -d open-webui
```

### §5.6.2 Configurer l'authentification LDAP

Dans l'interface admin Open WebUI, naviguer vers **Settings → Admin → Authentication → LDAP** :

| Paramètre | Valeur |
|---|---|
| Étiquette | Annuaire AD |
| Hôte | `<IP-DC>` |
| Port | 636 |
| TLS | Activé |
| Validate Certificate | Désactivé |
| DN de l'application | `CN=svc-rag,OU=COMPTES-SERVICE,DC=domaine,DC=ch` |
| Mot de passe DN | mot de passe de svc-rag |
| Attribut pour le courriel | `userPrincipalName` |
| Attribut pour le nom d'utilisateur | `sAMAccountName` |
| Base de recherche | `DC=domaine,DC=ch` |
| Filtres de recherche | `(objectClass=user)` |

> **Port 636 obligatoire :** le port 389 est refusé par les contrôleurs de domaine Windows Server récents qui exigent LDAP Signing. LDAPS sur le port 636 contourne cette contrainte.

> **Validate Certificate désactivé :** les DC Windows utilisent des certificats auto-signés par défaut. Pour la production, exporter le certificat CA du DC et le pointer via le champ "Chemin du certificat". Voir §9.

> **Base de recherche `DC=domaine,DC=ch` :** certains comptes sont dans le conteneur `CN=Users` (par défaut Windows) plutôt que dans une OU. La base `OU=UTILISATEURS` ne les trouvera pas. La base racine couvre tous les cas.

> **`userPrincipalName` comme attribut email :** l'attribut `mail` n'est pas toujours renseigné dans l'AD. `userPrincipalName` (format `utilisateur@domaine.ch`) est toujours présent et utilisé comme identifiant unique par la RAG API.

### §5.6.3 Paramètres utilisateurs

Dans **Settings → Admin → Authentication → User Access** :

- **Rôle utilisateur par défaut :** `utilisateur` (pas `en attente`). Sans ce réglage, les nouveaux comptes LDAP sont bloqués en attente d'activation manuelle.

Dans **Settings → Admin → Models** :

- Cliquer sur `...` à côté du modèle `rag-api` → **Make Public**. Sans cette étape, les utilisateurs non-admin voient une liste de modèles vide à la connexion.

---

## §5.7 Intégration dans main.py

La RAG API extrait l'email du header `x-openwebui-user-email`, résout les groupes AD via `auth.py`, et filtre la recherche Qdrant en conséquence.

### §5.7.1 Filtre Qdrant par identité

```python
from auth import get_user_groups, check_access

# Dans l'endpoint /v1/chat/completions :
owui_email = raw_request.headers.get("X-OpenWebUI-User-Email", "")
user_groups = get_user_groups(owui_email) if owui_email else []

# Dans search_qdrant() :
query_filter = None
if user_groups:
    query_filter = Filter(must=[
        FieldCondition(
            key="autorises",
            match=MatchAny(any=user_groups)
        )
    ])

results = qdrant.query_points(
    collection_name=COLLECTION,
    query=embedding,
    query_filter=query_filter,
    limit=top_k,
    with_payload=True
).points
```

### §5.7.2 Vérification des DENY explicites

En NTFS, un DENY explicite est prioritaire sur un ALLOW. Après le filtre Qdrant, chaque chunk est vérifié individuellement :

```python
for r in results:
    interdits = r.payload.get("interdits", [])
    if interdits and user_groups:
        if not check_access(user_groups,
                           r.payload.get("autorises", []),
                           interdits):
            continue  # chunk exclu malgré l'ALLOW
    chunks.append({...})
```

La fonction `check_access()` dans `auth.py` implémente la logique NTFS : accès accordé si `(user_groups ∩ autorises != ∅) AND (user_groups ∩ interdits == ∅)`.

> **Chemin DENY validé en lab, septembre 2026.** Voir §9.4.5 pour les résultats complets. En résumé : `test-client`, membre de `GRP-Clients` (dans `autorises[]`) mais visé par un ACE de refus nominatif (dans `interdits[]`), ne voit pas `test-deny-explicite.docx`, alors qu'un compte sans DENY dans le même groupe y accède normalement. Le DENY nominatif l'emporte sur l'autorisation par groupe, y compris sur le chemin d'extension de contexte.

> **Comportement sur les cas limites (corrigé en v2.5.0) :**
> - `interdits` est toujours écrit dans Qdrant, même vide (`[]`). Si un DENY est retiré sur le file server, il sera écrasé au prochain passage du résolveur ACL.
> - Si les ACL d'un fichier sont illisibles (panne SMB, droits insuffisants), `autorises` est vidé dans Qdrant : le fichier devient invisible pour tous les utilisateurs filtrés jusqu'au prochain passage où les ACL redeviennent lisibles (deny by default).

---

## §5.8 Validation du cloisonnement

Deux cas de test ont été validés en lab sur un corpus de documents d'entreprise.

### §5.8.1 Cas 1 : administrateur du domaine (accès complet)

**Compte :** membre de `Admins du domaine`.

**Logs RAG API :**

```
Utilisateur trouvé : 'admin' (admin@domaine.ch)
Groupes résolus : ['DOMAINE\GRP-ServiceInfo', 'DOMAINE\Admins du domaine',
                   'DOMAINE\admin', ...]  → 15 groupes
/v1 user 'admin@domaine.ch' : 15 groupes AD
```

`Admins du domaine` figure dans `autorises[]` de tous les documents. L'utilisateur voit l'ensemble du corpus.

### §5.8.2 Cas 2 : utilisateur limité à GRP-Clients (cloisonnement négatif)

**Compte :** membre de `GRP-Clients` uniquement.

**Logs RAG API :**

```
Utilisateur trouvé : 'user-clients' (user-clients@domaine.ch)
Groupes résolus : ['DOMAINE\GRP-Clients', 'DOMAINE\user-clients']  → 2 groupes
/v1 user 'user-clients@domaine.ch' : 2 groupes AD
```

**Question posée :** "Quelles sont les conditions du contrat de travail de [employé RH] ?"

Le document RH a `autorises: ['DOMAINE\GRP-RH', ...]`. `GRP-Clients` n'y figure pas. Qdrant retourne 0 chunk.

**Réponse :** "Cette information ne figure pas dans les documents disponibles."

Les suggestions de suivi portaient uniquement sur les contrats clients, confirmant que seul le périmètre autorisé est visible.

### §5.8.3 Cas 3 : utilisateur limité à GRP-Clients (cloisonnement positif)

**Question posée :** "Quelles sont les prestations incluses dans le contrat de maintenance avec [Client A] ?"

**Réponse :** réponse détaillée avec citations du document `CLIENTS/ClientA/contrat_maintenance.docx`.

Ce cas confirme que le filtre ne renvoie pas systématiquement zéro chunk : il renvoie exactement les documents autorisés, ni plus ni moins.

> **Tests validés en lab, septembre 2026.** Le chemin DENY explicite (§5.7.2) et la résolution des groupes imbriqués multi-niveaux ont été exercés par des cas de validation dédiés. Les résultats sont documentés en §9.4.5.

---

[Suite : §6 Agent de codage](section-06-cline.md)

---

## §5.9 Deux collections Qdrant : règles de gouvernance

La stack utilise deux collections Qdrant distinctes pour séparer le corpus d'entreprise de la documentation technique :

| Collection | Contenu | Cloisonnement ACL |
|---|---|---|
| `documents` | Corpus entreprise (CLIENTS, RH, DIRECTION, etc.) | Oui, par groupes AD |
| `documentation` | Documentation technique (DOIT4EVERYONE/) | Oui, accessible à tous les utilisateurs authentifiés |

Le routage se fait automatiquement à l'indexation selon le chemin relatif du fichier. Les dossiers dont le chemin commence par un préfixe de `DOCUMENTATION_PATHS` vont dans `documentation`. Tout le reste va dans `documents`.

> **Ces règles sont structurelles.** Leur non-respect produit un routage silencieusement incorrect sans message d'erreur : des documents confidentiels peuvent se retrouver dans `documentation` sans cloisonnement ACL effectif.

**Règle 1 : dossiers de documentation uniquement à la racine du partage.**
Un dossier déclaré dans `DOCUMENTATION_PATHS` doit être directement à la racine de `\\SERVEUR\PartageDocuments`. Jamais dans un sous-dossier. Si `CLIENTS\DOIT4EVERYONE\` existe, ses fichiers partent en `documentation` sans cloisonnement ACL.

**Règle 2 : droits AD sur les dossiers racine.**
Seul un administrateur peut créer des dossiers à la racine du partage.

**Règle 3 : modifier `DOCUMENTATION_PATHS` exige une réindexation complète.**

```bash
# Modifier .env, puis :
docker compose build --no-cache rag-api && docker compose up -d rag-api
cd /root/rag-pipeline && source .venv/bin/activate
set -a && source /root/rag-stack/.env && set +a
python indexer.py --corpus /mnt/fileservice-root --reset
curl -X POST http://localhost:8080/admin/sync -H "Authorization: Bearer <ADMIN_TOKEN>"
```

**Règle 4 : vérifier les deux compteurs après chaque réindexation.**

```bash
curl -s http://localhost:6333/collections/documents | python3 -m json.tool | grep points_count
curl -s http://localhost:6333/collections/documentation | python3 -m json.tool | grep points_count
# Les deux compteurs additionnés doivent correspondre au total des chunks indexés.
```

---

*Validé en lab sur VM-RAG-LAB, septembre 2026. Les commandes et résultats présentés sont issus de sessions de test réelles.*
