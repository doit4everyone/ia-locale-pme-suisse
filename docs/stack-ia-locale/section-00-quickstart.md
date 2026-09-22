---
title: "§0 Déploiement complet | Guide de déploiement stack IA locale"
description: "Procédure de déploiement pas à pas de la stack RAG locale : AD, SMB, certificat CA, Docker, indexation, ACL, Open WebUI et n8n."
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

# §0 Déploiement complet

[Retour au sommaire](index.md)

> Ce guide couvre un déploiement complet depuis zéro : création du compte de service dans l'AD, montage SMB, certificat CA, lancement de la stack Docker, première indexation, synchronisation des ACL, configuration d'Open WebUI et de n8n. Durée estimée : 2 à 3 heures pour un premier déploiement. Pour les sections détaillées, voir le guide complet à partir de [§1 Prérequis](section-01-prerequis.md).

---

## Vue d'ensemble de la séquence

```
AD (Windows)          VM Ubuntu (Linux)              Open WebUI / n8n
─────────────         ─────────────────              ────────────────
1. svc-rag        →   3. montage SMB
2. certificat CA  →   4. ad-chain.pem
                      5. .env + tokens
                      6. docker compose up
                      7. indexer.py
                      8. acl_resolver.py        →    9. connexion RAG API
                                                     10. workflow n8n
```

---

## Étape 1 : créer le compte de service svc-rag (Windows, PowerShell admin)

`svc-rag` est le compte qui lit les fichiers et les ACL NTFS sur le file server. Il a accès à l'intégralité du corpus : traiter son mot de passe comme un secret à privilèges.

```powershell
# Adapter le chemin de l'OU à votre organisation
New-ADUser -Name "svc-rag" `
    -SamAccountName "svc-rag" `
    -UserPrincipalName "svc-rag@votre-domaine.ch" `
    -AccountPassword (ConvertTo-SecureString "<mot-de-passe-fort-20-caracteres>" -AsPlainText -Force) `
    -PasswordNeverExpires $false `
    -CannotChangePassword $true `
    -Enabled $true `
    -Path "OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch" `
    -Description "Compte de service indexeur RAG - lecture seule"

# Ajouter aux groupes qui ont accès aux partages à indexer
# Adapter à la structure de groupes de l'organisation
Add-ADGroupMember -Identity "GRP-Clients"     -Members "svc-rag"
Add-ADGroupMember -Identity "GRP-RH"          -Members "svc-rag"
Add-ADGroupMember -Identity "GRP-Direction"   -Members "svc-rag"
Add-ADGroupMember -Identity "GRP-Finances"    -Members "svc-rag"
Add-ADGroupMember -Identity "GRP-ServiceInfo" -Members "svc-rag"
```

Vérifier que le compte est actif et que les groupes sont bien assignés :

```powershell
Get-ADUser svc-rag -Properties MemberOf | Select -ExpandProperty MemberOf
```

> **Politique de mot de passe :** `PasswordNeverExpires $false` force la rotation selon la politique du domaine. Planifier la mise à jour de `/etc/smbcredentials/svc-rag` et de `.env` à chaque rotation (voir §9.5.1). Une rotation non répercutée sur la VM fait tomber le montage SMB au prochain redémarrage sans message explicite.

---

## Étape 2 : exporter le certificat CA du contrôleur de domaine (Windows)

Le certificat CA est nécessaire pour que la VM valide la connexion LDAP TLS vers l'AD. Sans lui, `auth.py` refuse la connexion et tout le monde est refusé avec 403.

```powershell
# Ouvrir le gestionnaire de certificats
# Démarrer → Exécuter → certlm.msc → Autorités de certification racines de confiance
# → Certificats → clic droit sur le certificat racine → Toutes les tâches → Exporter

# Ou via PowerShell :
$cert = Get-ChildItem -Path Cert:\LocalMachine\Root |
    Where-Object { $_.Subject -like "*votre-domaine*" } |
    Select-Object -First 1

Export-Certificate -Cert $cert `
    -FilePath "C:\Temp\ad-root-ca.cer" `
    -Type CERT
```

Copier le fichier `ad-root-ca.cer` sur la VM (via SCP ou partage réseau).

```bash
# Sur la VM : convertir et installer
openssl x509 -inform DER -in /tmp/ad-root-ca.cer \
    -out /etc/ssl/certs/ad-chain.pem

# Vérifier
openssl x509 -in /etc/ssl/certs/ad-chain.pem -noout -subject -dates
```

> **Certificat intermédiaire :** si l'AD utilise une PKI à deux niveaux (CA racine + CA émettrice), exporter aussi le certificat intermédiaire et les concaténer dans le même fichier : `cat ca-root.pem ca-intermediate.pem > /etc/ssl/certs/ad-chain.pem`.

---

## Étape 3 : préparer la VM Ubuntu

```bash
# Dépendances système
# python3.11 n'est pas dans les dépôts Ubuntu 26.04 (python3 → 3.12+).
sudo apt update && sudo apt install -y \
    cifs-utils smbclient samba-common-bin \
    ldap-utils curl wget git \
    python3 python3-pip python3-venv

# Configurer le DNS pour résoudre les noms AD
sudo nano /etc/systemd/resolved.conf
```

Ajouter :

```ini
[Resolve]
DNS=<IP-DC>
Domains=votre-domaine.ch
```

```bash
sudo systemctl restart systemd-resolved

# Vérifier la résolution
nslookup <NOM-FILESERVER>
nslookup <NOM-DC>
```

---

## Étape 4 : monter le partage SMB

```bash
# Créer le fichier de credentials (jamais de mot de passe en ligne de commande)
sudo mkdir -p /etc/smbcredentials
sudo nano /etc/smbcredentials/svc-rag
```

Contenu du fichier :

```
username=svc-rag
password=<mot-de-passe-fort>
domain=VOTREDOMAINE
```

```bash
# Protéger en lecture root uniquement
sudo chmod 600 /etc/smbcredentials/svc-rag
sudo chown root:root /etc/smbcredentials/svc-rag

# Créer le point de montage et monter
sudo mkdir -p /mnt/corpus-root
sudo mount -t cifs //<NOM-FILESERVER>/FileService /mnt/corpus-root \
    -o credentials=/etc/smbcredentials/svc-rag,vers=3.1.1,uid=1000,gid=1000

# Vérifier
ls /mnt/corpus-root/
```

Rendre le montage persistant :

```bash
sudo tee -a /etc/fstab << 'FSTAB'

# Partage SMB corpus RAG (monté par svc-rag)
//<NOM-FILESERVER>/FileService /mnt/corpus-root cifs credentials=/etc/smbcredentials/svc-rag,vers=3.1.1,uid=1000,gid=1000,rw,soft,nofail 0 0
FSTAB

# Tester sans rebooter
sudo mount -a && mount | grep corpus-root
```

---

## Étape 5 : structure des répertoires et fichiers

```bash
# Répertoires de la stack
mkdir -p ~/rag-stack/{qdrant_data,n8n_data,openwebui_data,api}
mkdir -p /root/rag-pipeline
mkdir -p /var/log/rag
```

Déposer les fichiers (depuis le dépôt GitHub) :

```
~/rag-stack/
├── .env                    ← à créer depuis env.example
├── docker-compose.yml
└── api/
    ├── main.py
    ├── auth.py
    ├── Dockerfile
    └── requirements.txt

/root/rag-pipeline/
├── indexer.py
└── acl_resolver.py
```

---

## Étape 6 : fichier .env

```bash
cd ~/rag-stack
cp env.example .env
```

**Générer des tokens forts :**

```bash
# Deux tokens distincts, ne jamais utiliser les valeurs changeme en production
echo "API_TOKEN=$(openssl rand -hex 32)"
echo "ADMIN_TOKEN=$(openssl rand -hex 32)"
echo "WEBUI_SECRET_KEY=$(openssl rand -hex 32)"
```

Éditer `.env` avec ces valeurs. Variables obligatoires à adapter :

```bash
# Ollama : IP du poste Windows qui fait tourner Ollama
LLM_BASE_URL=http://<IP-HOTE-OLLAMA>:11434
EMBED_BASE_URL=http://<IP-HOTE-OLLAMA>:11434

# Tokens générés ci-dessus
API_TOKEN=<sortie openssl>
ADMIN_TOKEN=<sortie openssl distinct>
WEBUI_SECRET_KEY=<sortie openssl distinct>

# Organisation
ORG_NAME=<Nom de votre organisation>

# LDAP : connexion à l'AD pour la résolution des groupes
LDAP_HOST=<NOM-DC>.votre-domaine.ch
LDAP_PORT=636
LDAP_USE_TLS=true
LDAP_BASE_DN=DC=votre-domaine,DC=ch
LDAP_BIND_DN=CN=svc-rag,OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch
LDAP_BIND_PWD=<mot-de-passe-svc-rag>
LDAP_DOMAIN=VOTREDOMAINE
LDAP_CA_CERT=/etc/ssl/certs/ad-chain.pem

# SMB : partage à indexer
SMB_SHARE=//NOM-FILESERVER/FileService
SMB_MOUNT=/mnt/corpus-root
SMB_USER=svc-rag
SMB_PASSWORD=<mot-de-passe-svc-rag>
SMB_DOMAIN=VOTREDOMAINE
```

> **`LDAP_CA_CERT` et `SMB_PASSWORD` identiques :** `svc-rag` est utilisé à la fois pour le montage SMB et pour la résolution LDAP. Le même mot de passe doit être renseigné dans `/etc/smbcredentials/svc-rag` et dans `.env`.

---

## Étape 7 : vérifier Ollama depuis la VM

```bash
# Vérifier que les deux modèles sont présents
curl http://<IP-HOTE-OLLAMA>:11434/api/tags | python3 -m json.tool | grep name

# Résultat attendu : qwen2.5:14b et qwen3:4b dans la liste
# Si absent, sur LABO-G9 (Windows) :
# ollama pull qwen2.5:14b
# ollama pull qwen3:4b
```

> **Ollama doit écouter sur toutes les interfaces :** sur Windows, vérifier que `OLLAMA_HOST=0.0.0.0:11434` est défini dans les variables d'environnement système. Sans cela, Ollama n'écoute que sur `127.0.0.1` et la VM ne peut pas le joindre.

---

## Étape 8 : lancer la stack Docker

```bash
cd ~/rag-stack

# Construire l'image rag-api (nécessaire au premier lancement)
docker compose build --no-cache rag-api

# Lancer tous les services
docker compose up -d

# Vérifier l'état
docker compose ps
```

Résultat attendu :

```
NAME         STATUS
n8n          Up
open-webui   Up (healthy)
qdrant       Up
rag-api      Up
```

Si `rag-api` redémarre en boucle :

```bash
docker logs rag-api 2>&1 | tail -30
```

Causes fréquentes : variable manquante dans `.env`, `ad-chain.pem` absent, Qdrant pas encore prêt au démarrage (relancer `docker compose restart rag-api` après 30 secondes).

---

## Étape 9 : environnement Python pour les scripts

```bash
cd /root/rag-pipeline
python3 -m venv .venv
source .venv/bin/activate

pip install qdrant-client python-docx pdfplumber python-pptx httpx \
    ldap3 impacket rank-bm25 smbprotocol
```

Tester la connexion LDAP avant d'aller plus loin :

```bash
set -a && source ~/rag-stack/.env && set +a

ldapwhoami -H ldaps://${LDAP_HOST}:${LDAP_PORT} \
    -D "${LDAP_BIND_DN}" \
    -w "${LDAP_BIND_PWD}" \
    -ZZ 2>&1
# Attendu : dn:CN=svc-rag,...
```

Tester la connexion SMB :

```bash
smbclient //<NOM-FILESERVER>/FileService \
    -U svc-rag%<mot-de-passe> \
    -c "ls" 2>&1 | head -10
# Attendu : liste des dossiers racines du partage
```

---

## Étape 10 : première indexation

```bash
cd /root/rag-pipeline && source .venv/bin/activate
set -a && source ~/rag-stack/.env && set +a

python indexer.py \
    --corpus /mnt/corpus-root \
    --rapport /var/log/rag/rapport_indexation_initial.json

echo "Code de sortie : $?"
```

Résultat attendu : code 0, rapport JSON produit. Vérifier :

```bash
# Nombre de chunks indexés
curl -s http://localhost:6333/collections/documents | \
    python3 -c "import sys,json; r=json.load(sys.stdin); \
    print('documents :', r['result']['points_count'])"

curl -s http://localhost:6333/collections/documentation | \
    python3 -c "import sys,json; r=json.load(sys.stdin); \
    print('documentation :', r['result']['points_count'])"
```

> **Quarantaine :** un fichier dont l'organisation propriétaire (client ou organisation interne) n'est pas identifiable par la cascade de détection est mis en quarantaine et n'est pas indexé. Il apparaît dans le rapport JSON avec le statut `quarantaine`. Un PDF scanné sans couche texte ou un fichier corrompu ne produit aucun chunk et prend le statut `vide`. Un document court est indexé en un seul chunk.

---

## Étape 11 : synchronisation des ACL

```bash
python acl_resolver.py \
    --share //<NOM-FILESERVER>/FileService \
    --mount /mnt/corpus-root \
    --rapport /var/log/rag/rapport_acl_initial.json

echo "Code de sortie : $?"
```

Résultat attendu : code 0, `Fichiers sans ACL : 0`, rapport JSON produit.

Vérifier qu'un chunk porte bien les ACL :

```bash
curl -s http://localhost:6333/collections/documents/points/scroll \
    -H "Content-Type: application/json" \
    -d '{"limit":1,"with_payload":["source","autorises","interdits"]}' \
    | python3 -m json.tool | head -15
```

---

## Étape 12 : configuration Open WebUI

Ouvrir `http://<IP-VM>:3001` depuis un poste du réseau.

**Connexion RAG API :**

1. Settings → Admin → Connections → API compatibles OpenAI → `+`
2. URL : `http://rag-api:8080/v1`
3. Clé API : valeur de `API_TOKEN` dans le `.env`
4. Enregistrer → le modèle `rag-api` doit apparaître dans la liste

**Authentification LDAP (optionnel en lab, obligatoire en production) :**

1. Settings → Admin → Authentication → LDAP
2. Activer LDAP
3. Server Address : `<NOM-DC>.votre-domaine.ch`
4. Port : `636`, TLS activé
5. Attribute : `userPrincipalName`

> **`userPrincipalName` est obligatoire**, pas `sAMAccountName`. Open WebUI transmet l'email de l'utilisateur dans `X-OpenWebUI-User-Email`. `auth.py` cherche cet email dans le champ `userPrincipalName` de l'AD. Sans cet attribut, la résolution LDAP échoue et tout le monde reçoit un 403.

6. Base DN : `DC=votre-domaine,DC=ch`
7. Bind DN : `CN=svc-rag,OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch`
8. Bind Password : mot de passe de `svc-rag`
9. Certificate Path : `/etc/ssl/certs/ad-chain.pem`

**Rendre le modèle accessible :**

Settings → Admin → Models → `rag-api` → Make Public → Enregistrer.

---

## Étape 13 : configurer le workflow n8n

Ouvrir `http://<IP-VM>:5678`.

Le workflow "RAG Stack - Synchronisation corpus" déclenche `/admin/sync` toutes les heures. Si le workflow n'existe pas encore, l'importer depuis le fichier JSON du dépôt.

Vérifier la configuration du nœud "POST /admin/sync" :

- URL : `http://rag-api:8080/admin/sync`
- Method : POST
- Header : `Authorization: Bearer <ADMIN_TOKEN>`

Activer le workflow et lancer une exécution manuelle pour valider :

```
Workflows → RAG Stack → Execute workflow
```

Résultat attendu dans les logs :

```bash
docker logs rag-api 2>&1 | grep "sync\|indexer\|acl" | tail -10
```

---

## Checklist de validation finale

| Test | Commande / action | Résultat attendu |
|---|---|---|
| Qdrant collections | `curl http://localhost:6333/collections` | `documents` et `documentation` présentes |
| Chunks indexés | Voir étape 10 | Nombre > 0 dans les deux collections |
| ACL propagées | Voir étape 11 | `autorises` non vide dans le payload |
| RAG API santé | `docker compose exec n8n wget -qO- http://rag-api:8080/health` | `{"status":"ok"}` |
| BM25 chargé | `docker logs rag-api \| grep BM25` | Nombre de chunks |
| Cloisonnement positif | Question dans Open WebUI sur document accessible | Réponse avec citation et chemin UNC |
| Cloisonnement négatif | Compte sans droits, question sur document restreint | "Cette information ne figure pas..." |
| Cloisonnement DENY | Compte avec DENY explicite sur un fichier | Fichier absent de la réponse |
| Journal nLPD | `tail -1 /var/log/rag/rag-queries.jsonl` | Entrée JSON avec `user_id` et `ancree` |
| n8n sync horaire | Interface n8n → dernière exécution | Réussie, sans erreur |
| Garde-fou ACL | `SMB_PASSWORD=faux python acl_resolver.py ...` | Code 1, `[GARDE-FOU]`, Qdrant intact |

---

## En cas de problème

**`rag-api` ne démarre pas :**

```bash
docker logs rag-api 2>&1 | tail -30
```

Vérifier : variable manquante dans `.env`, `ad-chain.pem` absent sur l'hôte, Qdrant pas encore prêt.

**LDAP refuse la connexion (403 sur toutes les requêtes) :**

```bash
ldapwhoami -H ldaps://<NOM-DC>:636 \
    -D "CN=svc-rag,OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch" \
    -w "<mot-de-passe>" 2>&1
```

Causes : mauvais mot de passe, compte verrouillé, certificat CA incorrect.

**Montage SMB tombe après redémarrage :**

```bash
sudo mount -a
mount | grep corpus-root
```

Vérifier que `/etc/smbcredentials/svc-rag` contient le bon mot de passe et que la ligne `/etc/fstab` est correcte.

**BM25 vide au démarrage :**

Qdrant a démarré après `rag-api`. Attendre 30 secondes et relancer :

```bash
docker compose restart rag-api
docker logs rag-api 2>&1 | grep BM25
```

**Garde-fou ACL déclenché (code 1) :**

Plus de 20% des fichiers sont illisibles. Vérifier :

```bash
# svc-rag verrouillé ?
# Windows PowerShell :
# Get-ADUser svc-rag -Properties LockedOut | Select LockedOut
# Unlock-ADAccount -Identity svc-rag

# Montage SMB présent ?
ls /mnt/corpus-root/ | head -5

# DC joignable ?
ldapwhoami -H ldaps://<NOM-DC>:636 \
    -D "CN=svc-rag,..." -w "<mot-de-passe>"
```

---

[Suite : §1 Prérequis et création de la VM](section-01-prerequis.md)

---

*Validé sur VM-RAG-LAB, Ubuntu 26.04 LTS, septembre 2026.*
