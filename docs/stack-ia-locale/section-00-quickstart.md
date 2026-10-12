---
title: "§0 Démarrage rapide | Guide de déploiement stack IA locale"
description: "Déployer la stack RAG locale de bout en bout : Active Directory, serveur de modèles Ollama ou vLLM, VM Ubuntu, indexation des documents, droits d'accès, Open WebUI et n8n."
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

# §0 Démarrage rapide

[Retour au sommaire](index.md) | [Section suivante : §1 Prérequis et création de la VM](section-01-prerequis.md)

**Statut :** validé en lab, octobre 2026, avec les deux moteurs du serveur de modèles, Ollama et vLLM (§2). Le script `deploy.sh`, qui automatise une partie des étapes, n'a pas encore été rejoué sur une VM neuve (encadré de l'étape 6).

---

## Ce que vous allez obtenir

Un assistant comparable à ChatGPT, mais **installé chez vous**. Vos collaborateurs lui posent des questions dans leur navigateur ; il répond **à partir des documents de l'entreprise** (le serveur de fichiers, et en option SharePoint), cite ses sources, et **ne montre à chacun que les documents qu'il a déjà le droit d'ouvrir** sur le serveur de fichiers. Les questions et les réponses sont traitées sur vos machines : aucun service d'IA externe n'est appelé.

Ce guide mène d'une installation vierge à un assistant en service. Comptez une journée pour un premier déploiement : deux à trois heures pour la stack elle-même, plus l'installation du serveur de modèles (une demi-heure avec Ollama, une à deux heures avec vLLM) et le téléchargement des modèles (environ 12 Go). Microsoft 365, en option, vient ensuite.

---

## Les trois machines

| Machine | Rôle | Ce qui y tourne |
|---|---|---|
| **Serveur Windows existant** | L'annuaire et les documents | Active Directory, serveur de fichiers (partage réseau) |
| **VM de la stack**, Ubuntu Server 26.04 | L'application | Open WebUI (l'interface de discussion), la RAG API (le cœur : identité, droits, recherche, contrôle des réponses), Qdrant (l'index des documents), n8n (les tâches planifiées) |
| **Serveur de modèles**, avec une carte graphique NVIDIA | Les modèles d'IA | Le moteur, Ollama ou vLLM, et trois modèles : rédaction, vérification, recherche (§2.1) |

```
 Utilisateur (navigateur)
        │
        ▼
 VM de la stack ── Open WebUI → RAG API → Qdrant (index des documents)
                                  │
                                  ├→ Active Directory : qui est l'utilisateur, quels sont ses groupes
                                  └→ Serveur de modèles : rédaction, vérification, recherche
```

Dans le lab, la VM de la stack tourne dans VMware Workstation sur le poste Windows qui porte la carte graphique. Ce peuvent aussi être deux machines distinctes.

---

## Choisir le moteur du serveur de modèles

C'est la seule décision à prendre avant de commencer. Le détail et les mesures sont au §2.2.

| | **Ollama** | **vLLM** |
|---|---|---|
| Questions simultanées | **Une à la fois** : la suivante attend | **Plusieurs en même temps** |
| Pour qui | Un à deux utilisateurs simultanés, un essai, un poste unique | **Plusieurs utilisateurs simultanés : une PME en service** |
| Système | Windows ou Linux | Linux ; sous Windows, dans WSL2 (essai seulement, pas la production) |
| Installation | Simple, quelques minutes | Plus technique, une à deux heures |

Mesuré dans le lab : avec vLLM, deux personnes qui posent leurs questions en même temps sont servies presque aussi vite qu'une seule (+6 %). **Recommandation : vLLM pour une PME en service, Ollama pour un essai ou un à deux utilisateurs.** Le choix n'est pas définitif : on passe de l'un à l'autre sans réindexer ni réinstaller la stack (§2.5).

---

## Avant de commencer

- **Les droits d'administrateur** sur l'Active Directory et sur le serveur de fichiers.
- **Une VM Ubuntu Server 26.04** préparée selon le §1 : 6 vCPU, 16 Go de mémoire, 100 Go de disque, Docker installé (§1.4). Préparer aussi le **disque de données chiffré** (§1.5) **avant l'étape 6** : préparé après coup, il laisse des copies en clair des secrets et des données sur le disque système.
- **Une carte graphique NVIDIA d'au moins 16 Go** sur le serveur de modèles (le lab : une RTX 5060 Ti 16 Go). Sans carte, Ollama fonctionne sur le processeur, mais une question prend une à deux minutes (§10.4) ; vLLM exige une carte.
- **Un accès à Internet** pendant l'installation : paquets, images Docker, modèles.
- **Les informations de votre réseau** : l'adresse IP de la VM, celle du serveur de modèles, le nom DNS du contrôleur de domaine, le nom du serveur de fichiers et du partage à indexer.

> **Conventions de ce guide.** Les blocs `powershell` se lancent sur Windows, dans PowerShell **ouvert en administrateur**. Les blocs `bash` se lancent sur Linux. Sur la VM, **toutes les commandes se lancent en root** : ouvrir d'abord une session root avec `sudo -i`. Les valeurs entre chevrons, `<comme-ceci>`, sont à remplacer par les vôtres, chevrons compris. Chaque étape se termine par un résultat **attendu** : ne pas passer à la suite tant qu'il n'est pas obtenu.

---

## Les étapes en un coup d'œil

| Étape | Où | Quoi |
|---|---|---|
| 1 | Windows, Active Directory | Créer le compte de service `svc-rag` |
| 2 | Windows, Active Directory | Exporter le certificat de l'autorité de certification |
| 3 | Serveur de modèles | Installer **Ollama (3A)** ou **vLLM (3B)** |
| 4 | VM | Préparer la VM |
| 5 | VM | Monter le partage de fichiers |
| 6 | VM | Récupérer les scripts du dépôt |
| 7 | VM | Remplir le fichier de configuration `.env` |
| 8 | VM | Vérifier que la VM joint le serveur de modèles |
| 9 | VM | Lancer la stack |
| 10 | VM | Vérifier que la stack joint le serveur de modèles |
| 11 | VM | Préparer Python pour l'indexation |
| 12 | VM | Première indexation des documents |
| 13 | VM | Synchronisation des droits d'accès |
| 14 | Navigateur | Configurer Open WebUI |
| 15 | Navigateur | Configurer n8n |
| 16 | VM et navigateur | Contrôles finaux |
| 17 | Microsoft 365, facultatif | Entra ID, Teams, SharePoint |

---

## Étape 1 : créer le compte de service svc-rag (Windows)

`svc-rag` est le compte avec lequel la stack lit les fichiers et leurs droits d'accès (les ACL NTFS) sur le serveur de fichiers, et interroge l'Active Directory. Il a accès à l'intégralité du corpus : son mot de passe est un secret à privilèges.

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
```

**Donner la lecture par un groupe dédié, pas par les groupes métier.** Sur le serveur de fichiers, en administrateur, le script [`Set-AccesIndexationRAG.ps1`](../../scripts/stack-ia-locale/Set-AccesIndexationRAG.ps1) crée le groupe `GRP-RAG-Indexation`, y ajoute `svc-rag`, et accorde la lecture seule sur chaque dossier à indexer, y compris les sous-dossiers dont l'héritage est coupé :

```powershell
# Vérification seule : affiche ce qui manque, ne modifie rien
.\Set-AccesIndexationRAG.ps1 -Racine "D:\FileService" -Exclure "UTILISATEURS" -Verifier

# Application, puis nouvelle vérification : 0 fichier sans lecture attendu
.\Set-AccesIndexationRAG.ps1 -Racine "D:\FileService" -Exclure "UTILISATEURS"
```

Adapter la racine du partage et la liste des dossiers exclus (les dossiers personnels notamment). **Ne pas ajouter `svc-rag` aux groupes métier** (`GRP-RH`, `GRP-Finances`, etc.) : il hériterait de tous leurs droits, et son retrait d'un de ces groupes lui couperait la lecture sans avertissement. Explications et cas réel : [§5.2.4](section-05-connecteurs.md).

```powershell
Get-ADPrincipalGroupMembership -Identity "svc-rag" | Select Name
```

**Attendu :** seulement `GRP-RAG-Indexation` et les utilisateurs du domaine.

> **Mot de passe :** `PasswordNeverExpires $false` impose sa rotation selon la politique du domaine. À chaque rotation, reporter le nouveau mot de passe sur la VM (étapes 5 et 7, procédure au §9.5.1) : sinon, le montage du partage tombe au prochain redémarrage, sans message clair.

---

## Étape 2 : exporter le certificat de l'autorité de certification (Windows)

La VM vérifie l'identité du contrôleur de domaine avant de lui envoyer le mot de passe de `svc-rag` (connexion LDAP chiffrée). Pour cela, elle a besoin du certificat de l'autorité de certification du domaine. Sans lui, tout le monde est refusé (erreur 403).

```powershell
# Ou par l'interface : certlm.msc → Autorités de certification racines de confiance
# → Certificats → clic droit sur le certificat racine → Toutes les tâches → Exporter
$cert = Get-ChildItem -Path Cert:\LocalMachine\Root |
    Where-Object { $_.Subject -like "*votre-domaine*" } |
    Select-Object -First 1

Export-Certificate -Cert $cert -FilePath "C:\Temp\ad-root-ca.cer" -Type CERT
```

Copier `ad-root-ca.cer` sur la VM, dans `/tmp` (par `scp` ou par un partage). Il sera converti à l'étape 4.

> **PKI à deux niveaux** (autorité racine et autorité émettrice) : exporter aussi le certificat intermédiaire. Les deux seront réunis dans le même fichier à l'étape 4.

---

## Étape 3 : installer le serveur de modèles

Suivre **3A** ou **3B** selon le moteur choisi. Les explications de chaque réglage sont au §2.

### 3A : Ollama (sous Windows)

**1. Installer Ollama** depuis [ollama.com](https://ollama.com), dans sa dernière version.

**2. Le régler**, dans PowerShell ouvert **avec le compte qui fera tourner Ollama** :

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", "q8_0", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "1h", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NO_CLOUD", "1", "User")
```

Puis quitter Ollama depuis la zone de notification et le relancer : les réglages ne sont lus qu'au démarrage.

**3. Télécharger les trois modèles :**

```powershell
ollama pull qwen3:14b
ollama pull qwen3:4b
ollama pull nomic-embed-text
ollama list
```

**Attendu :** les trois modèles dans la liste. La vérification depuis la VM vient à l'étape 8.

> **Ollama tourne dans la session Windows ouverte.** Se déconnecter de la session l'arrête. Fermer simplement la fenêtre du Bureau à distance le laisse tourner. Ollama sous Linux : §2.3.

### 3B : vLLM

Sur un poste Windows, vLLM tourne dans WSL2, ce qui convient au lab et à l'essai mais pas à la production (§2.4.1). Sur un serveur Linux, commencer au point 2 (configuration non testée en lab, §2.4.1).

**1. Préparer WSL2 (poste Windows seulement).** Dans PowerShell en administrateur :

```powershell
wsl --install -d Ubuntu-26.04
```

Au premier lancement, Ubuntu demande de créer un utilisateur Linux. Créer ensuite le fichier `C:\Users\<utilisateur>\.wslconfig` :

```ini
[wsl2]
memory=16GB
swap=8GB
networkingMode=mirrored
```

Puis, toujours en administrateur, appliquer et ouvrir les ports de vLLM dans le pare-feu de WSL2 :

```powershell
wsl --shutdown
New-NetFirewallHyperVRule -Name "vllm-entrant" -DisplayName "vLLM entrant 8000 et 8001" -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol TCP -LocalPorts 8000,8001 -Action Allow
```

Rouvrir Ubuntu et vérifier que la carte est visible : `nvidia-smi`. **N'installer aucun pilote NVIDIA dans Ubuntu** : WSL2 utilise celui de Windows. Avant d'activer WSL2 sur un poste qui fait aussi tourner VMware Workstation, lire la mise en garde du §2.4.2.

**2. Installer vLLM**, dans Ubuntu :

```bash
sudo apt update && sudo apt install -y build-essential
sudo mkdir -p /opt/vllm && sudo chown $USER /opt/vllm
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env
cd /opt/vllm
uv venv --python 3.12 --seed --managed-python
source .venv/bin/activate
uv pip install vllm==0.31.0 --torch-backend=auto
python -c "import torch; print(torch.cuda.is_available())"
```

**Attendu :** `True` (la carte est accessible).

**3. Télécharger les modèles et créer la clé d'API :**

```bash
source /opt/vllm/.venv/bin/activate
sudo mkdir -p /opt/hf /etc/vllm && sudo chown $USER /opt/hf
export HF_HOME=/opt/hf
hf download Qwen/Qwen3-14B-AWQ
hf download nomic-ai/nomic-embed-text-v1.5
echo "VLLM_API_KEY=$(openssl rand -hex 32)" | sudo tee /etc/vllm/vllm.env > /dev/null
sudo chown root:$USER /etc/vllm/vllm.env && sudo chmod 640 /etc/vllm/vllm.env
```

La clé protège vLLM, visible depuis tout le réseau local. Elle ne s'affiche jamais : ne pas la coller dans un message ou un ticket.

**4. Lancer les deux serveurs**, chacun dans son propre terminal Ubuntu, en commençant par le premier :

```bash
# Terminal 1 : rédaction et juge, port 8000
cd /opt/vllm && source .venv/bin/activate
set -a; source /etc/vllm/vllm.env; set +a
export HF_HOME=/opt/hf VLLM_USE_FLASHINFER_SAMPLER=0
vllm serve Qwen/Qwen3-14B-AWQ --served-model-name qwen3:14b \
  --max-model-len 16384 --gpu-memory-utilization 0.87 --max-num-seqs 4 \
  --reasoning-parser qwen3 --default-chat-template-kwargs '{"enable_thinking": false}' \
  --host 0.0.0.0 --port 8000 --api-key "$VLLM_API_KEY"
```

Attendre `Application startup complete` (une à trois minutes), puis :

```bash
# Terminal 2 : embedding, port 8001
cd /opt/vllm && source .venv/bin/activate
set -a; source /etc/vllm/vllm.env; set +a
export HF_HOME=/opt/hf
vllm serve nomic-ai/nomic-embed-text-v1.5 --runner pooling --trust-remote-code \
  --served-model-name nomic-embed-text --max-model-len 2048 --gpu-memory-utilization 0.06 \
  --host 0.0.0.0 --port 8001 --api-key "$VLLM_API_KEY"
```

**5. Vérifier**, dans un troisième terminal : `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/v1/models`, puis la même chose avec le port 8001. **Attendu :** `401` deux fois (le serveur répond, et exige la clé). L'essai complet, qui contrôle aussi la qualité des réponses, est au §2.4.6.

> **Les deux serveurs s'arrêtent si on ferme leur terminal.** Les laisser ouverts pendant tout le déploiement. Le démarrage automatique par des services systemd est décrit au §2.4.7 ; validé dans WSL2, il ne dispense pas de garder un terminal Ubuntu ouvert, car WSL2 s'arrête quand le dernier se ferme. Si un démarrage échoue, les messages rencontrés et leur solution sont au §2.4.9.

---

## Étape 4 : préparer la VM

Ouvrir une session root (`sudo -i`), puis :

```bash
apt update && apt install -y \
    cifs-utils smbclient samba-common-bin \
    ldap-utils curl wget git \
    python3 python3-pip python3-venv
```

**Le DNS du domaine**, pour que la VM trouve le contrôleur de domaine et le serveur de fichiers par leur nom. Dans `/etc/systemd/resolved.conf` (avec `nano`), section `[Resolve]` :

```ini
[Resolve]
DNS=<IP-DC>
Domains=votre-domaine.ch
```

```bash
systemctl restart systemd-resolved
nslookup <NOM-FILESERVER>
nslookup <NOM-DC>
```

**Attendu :** les deux noms donnent une adresse IP.

**Le certificat de l'étape 2**, converti au format attendu par Linux :

```bash
openssl x509 -inform DER -in /tmp/ad-root-ca.cer -out /etc/ssl/certs/ad-chain.pem
openssl x509 -in /etc/ssl/certs/ad-chain.pem -noout -subject -dates
```

**Attendu :** le nom de l'autorité de certification et ses dates de validité. Avec une PKI à deux niveaux, convertir aussi le certificat intermédiaire, puis réunir les deux : `cat ca-root.pem ca-intermediate.pem > /etc/ssl/certs/ad-chain.pem`.

---

## Étape 5 : monter le partage de fichiers

Le mot de passe de `svc-rag` va dans un fichier lisible par root seulement, jamais dans une ligne de commande :

```bash
mkdir -p /etc/smbcredentials
nano /etc/smbcredentials/svc-rag
```

Contenu :

```
username=svc-rag
password=<mot-de-passe-svc-rag>
domain=VOTREDOMAINE
```

```bash
chmod 600 /etc/smbcredentials/svc-rag

mkdir -p /mnt/corpus-root
mount -t cifs //<NOM-FILESERVER>/FileService /mnt/corpus-root \
    -o credentials=/etc/smbcredentials/svc-rag,vers=3.1.1,uid=1000,gid=1000
ls /mnt/corpus-root/
```

**Attendu :** les dossiers du partage. Rendre ensuite le montage permanent :

```bash
cat >> /etc/fstab << 'FSTAB'

# Partage du corpus RAG (monté avec svc-rag)
//<NOM-FILESERVER>/FileService /mnt/corpus-root cifs credentials=/etc/smbcredentials/svc-rag,vers=3.1.1,uid=1000,gid=1000,rw,soft,nofail 0 0
FSTAB
mount -a && mount | grep corpus-root
```

---

## Étape 6 : récupérer les scripts du dépôt

Les scripts sont publiés dans ce dépôt GitHub. Ceux qui contiennent des valeurs d'exemple portent le préfixe `anon_` : on les renomme en les copiant.

```bash
cd /root
git clone https://github.com/doit4everyone/ia-locale-pme-suisse.git
cd ia-locale-pme-suisse/scripts/stack-ia-locale

# Dossiers de la stack (déjà présents, sous forme de liens, si le disque chiffré du §1.5 est prêt)
mkdir -p /root/rag-stack/{qdrant_data,n8n_data,openwebui_data} /root/rag-pipeline /var/log/rag
mkdir -p /etc/rag-certs && chmod 700 /etc/rag-certs

# La stack : Compose, configuration d'exemple, RAG API, service Purview
cp docker-compose.yml env.example /root/rag-stack/
mkdir -p /root/rag-stack/api /root/rag-stack/mip-service
cp -r api/. /root/rag-stack/api/
mv /root/rag-stack/api/anon_main.py /root/rag-stack/api/main.py
mv /root/rag-stack/api/anon_auth.py /root/rag-stack/api/auth.py
cp -r mip-service/. /root/rag-stack/mip-service/

# Les scripts d'indexation, des droits et de contrôle
cp anon_indexer.py /root/rag-pipeline/indexer.py
cp anon_acl_resolver.py /root/rag-pipeline/acl_resolver.py
cp sp_indexer.py test_cloisonnement.py cas_cloisonnement.exemple.json /root/rag-pipeline/

ls /root/rag-stack /root/rag-stack/api /root/rag-pipeline
```

**Attendu :** `main.py`, `auth.py`, `teams.py`, `teams_graph.py`, `Dockerfile` et `requirements.txt` dans `api/` ; `indexer.py`, `acl_resolver.py`, `sp_indexer.py` et `test_cloisonnement.py` dans `/root/rag-pipeline`. `teams.py`, `teams_graph.py`, `sp_indexer.py` et `mip-service` servent à Microsoft 365 : ils restent inactifs tant que leurs réglages sont vides.

> **Variante automatisée : `deploy.sh`.** Le script du dépôt enchaîne les étapes 5 à 11 (montage, fichiers, `.env`, lancement, Python) en posant des questions, dont le choix du moteur ; il vérifie aussi que la stack joint le serveur de modèles. **Statut :** adapté aux deux moteurs dans cette version, mais pas encore rejoué de bout en bout sur une VM neuve. Pour un premier déploiement, la procédure manuelle reste la référence. Lancement : `chmod +x deploy.sh && ./deploy.sh`, depuis ce dossier.

---

## Étape 7 : remplir le fichier de configuration .env

Le fichier `.env` réunit tous les réglages et secrets de la stack. Il ne doit jamais être publié ni copié dans un document.

**1. Créer le fichier et générer les secrets automatiquement :**

```bash
cd /root/rag-stack
cp env.example .env
chmod 600 .env
for v in API_TOKEN ADMIN_TOKEN WEBUI_SECRET_KEY QDRANT_API_KEY LOG_HMAC_KEY MIP_TOKEN; do
    sed -i "s|^${v}=.*|${v}=$(openssl rand -hex 32)|" .env
done
sed -i "s|^N8N_BASIC_AUTH_PASSWORD=.*|N8N_BASIC_AUTH_PASSWORD=$(openssl rand -hex 16)|" .env
grep -c changeme .env
```

**Attendu :** `0` : plus aucune valeur d'exemple pour les secrets.

**2. Compléter le reste à la main** avec `nano .env` :

| Réglage | Valeur | Exemple |
|---|---|---|
| Bloc du serveur de modèles | Voir le point 3 ci-dessous | |
| `ORG_NAME`, `ORG_OWNER` | Le nom de votre organisation, le même dans les deux | `Exemple SA` |
| `LDAP_HOST` | Le nom DNS complet du contrôleur de domaine, pas son adresse IP | `dc01.votre-domaine.ch` |
| `LDAP_BASE_DN` | Le domaine, en notation LDAP | `DC=votre-domaine,DC=ch` |
| `LDAP_BIND_DN` | Le compte `svc-rag`, avec son OU | `CN=svc-rag,OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch` |
| `LDAP_BIND_PWD`, `SMB_PASSWORD` | Le mot de passe de `svc-rag`, le même aux deux endroits et dans le fichier de l'étape 5 | |
| `LDAP_DOMAIN`, `SMB_DOMAIN` | Le nom NetBIOS du domaine | `VOTREDOMAINE` |
| `SMB_SHARE` | Le partage à indexer | `//FILESERVER/FileService` |
| `DOCUMENTATION_PATHS` | Le dossier de documentation technique à la racine du partage, s'il existe (§3.2) | `DOCUMENTATION` |

**3. Le bloc du serveur de modèles**, en haut du fichier. Il contient deux blocs : **A pour Ollama**, actif par défaut, et **B pour vLLM**, désactivé (chaque ligne commence par `#`). **Un seul bloc doit être actif.**

- **Avec Ollama :** dans le bloc A, remplacer `<IP-SERVEUR-MODELES>` par l'adresse de la machine Ollama.
- **Avec vLLM :** ajouter un `#` au début de chaque ligne du bloc A, retirer le `#` des lignes du bloc B, remplacer `<IP-SERVEUR-MODELES>` par l'adresse du poste ou du serveur vLLM, et `<clé-vllm>` par la clé créée à l'étape 3B. Pour la copier sans l'afficher depuis un poste Windows : §2.4.4.

Plus bas dans le fichier, `OLLAMA_URL` prend la même valeur que `EMBED_BASE_URL` : port 11434 avec Ollama, **port 8001 avec vLLM**. Malgré son nom, cette ligne désigne le serveur d'embedding, avec les deux moteurs.

> **Jamais `localhost`** dans ces adresses, même si la VM et le serveur de modèles tournent sur le même poste : à l'intérieur d'un conteneur, `localhost` désigne le conteneur lui-même.

**4. Contrôler** qu'il ne reste aucune valeur à remplacer :

```bash
grep -nE "^[A-Z_]+=.*<" .env
```

**Attendu :** seulement des lignes `ENTRA_`, `TEAMS_`, `SP_` et `MIP_TENANT_DOMAINE`, qui concernent Microsoft 365 et restent inactives tant qu'il n'est pas configuré.

---

## Étape 8 : vérifier que la VM joint le serveur de modèles

**Avec Ollama :**

```bash
curl -s http://<IP-SERVEUR-MODELES>:11434/api/tags | python3 -m json.tool | grep '"name"'
```

**Attendu :** `qwen3:14b`, `qwen3:4b` et `nomic-embed-text`. Sans réponse : le réglage `OLLAMA_HOST` (étape 3A) ou le pare-feu Windows (§2.3).

**Avec vLLM :**

```bash
set -a; source /root/rag-stack/.env; set +a
curl -s -H "Authorization: Bearer $VLLM_API_KEY" http://<IP-SERVEUR-MODELES>:8000/v1/models | python3 -m json.tool | grep '"id"'
curl -s -H "Authorization: Bearer $VLLM_API_KEY" http://<IP-SERVEUR-MODELES>:8001/v1/models | python3 -m json.tool | grep '"id"'
```

**Attendu :** `qwen3:14b`, puis `nomic-embed-text`. Si `curl` reste bloqué : la règle de pare-feu de l'étape 3B. Si la réponse est vide : la clé du `.env` ne correspond pas à celle du serveur.

---

## Étape 9 : lancer la stack

```bash
cd /root/rag-stack
docker compose build --no-cache rag-api
docker compose up -d
docker compose ps
```

**Attendu :** `qdrant`, `n8n`, `rag-api` en `Up`, et `open-webui` en `Up (healthy)` après une minute environ. Si `rag-api` redémarre en boucle : `docker logs rag-api 2>&1 | tail -30` montre la cause (le plus souvent une variable manquante dans `.env`, ou le certificat de l'étape 4 absent).

---

## Étape 10 : vérifier que la stack joint le serveur de modèles

Que la VM joigne le serveur de modèles ne suffit pas : c'est le conteneur `rag-api` qui l'interroge, par le réseau interne de Docker. Ce contrôle l'interroge depuis le conteneur, avec les réglages qu'il a réellement reçus :

```bash
docker exec rag-api python3 -c "
import os, httpx
api = os.environ.get('LLM_API', 'ollama')
cle = os.environ.get('VLLM_API_KEY', '')
h = {'Authorization': 'Bearer ' + cle} if cle else {}
for nom in ('LLM_BASE_URL', 'EMBED_BASE_URL'):
    u = os.environ[nom] + ('/v1/models' if api == 'openai' else '/api/tags')
    print(nom, httpx.get(u, headers=h, timeout=10).status_code)
"
```

**Attendu :** `LLM_BASE_URL 200`, puis `EMBED_BASE_URL 200`. En cas d'erreur `No route to host` alors que l'étape 8 a réussi : voir « En cas de problème », en fin de page.

---

## Étape 11 : préparer Python pour l'indexation

L'indexation et la synchronisation des droits se lancent depuis la VM, dans un environnement Python isolé :

```bash
cd /root/rag-pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install qdrant-client python-docx pdfplumber python-pptx httpx \
    ldap3 impacket rank-bm25 smbprotocol
```

Tester ensuite les deux accès de `svc-rag`, à l'annuaire et au partage :

```bash
set -a && source /root/rag-stack/.env && set +a

LDAPTLS_CACERT=/etc/ssl/certs/ad-chain.pem \
    ldapwhoami -H ldaps://${LDAP_HOST}:${LDAP_PORT} -D "${LDAP_BIND_DN}" -w "${LDAP_BIND_PWD}" 2>&1
smbclient //<NOM-FILESERVER>/FileService -U "svc-rag%${SMB_PASSWORD}" -c "ls" 2>&1 | head -10
```

**Attendu :** `dn:CN=svc-rag,...`, puis la liste des dossiers du partage.

---

## Étape 12 : première indexation des documents

L'indexeur lit chaque document du partage, le découpe en extraits, calcule leurs vecteurs avec le modèle d'embedding, et les range dans Qdrant.

```bash
cd /root/rag-pipeline && source .venv/bin/activate
set -a && source /root/rag-stack/.env && set +a

python indexer.py --corpus /mnt/corpus-root --rapport /var/log/rag/rapport_indexation_initial.json
echo "Code de sortie : $?"
```

**Attendu :** au début, `Vérification du serveur d'embedding (ollama)`, ou `(openai)` avec vLLM, puis `Modèle d'embedding : nomic-embed-text ✓` ; à la fin, le code de sortie `0`. Compter les extraits indexés :

```bash
for c in documents documentation; do
    curl -s -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections/$c | \
        python3 -c "import sys,json; print('$c :', json.load(sys.stdin)['result']['points_count'])"
done
```

> **Quarantaine :** un fichier dont l'organisation propriétaire (client ou organisation interne) n'est pas identifiable est mis en quarantaine et n'est pas indexé ; il apparaît dans le rapport avec le statut `quarantaine`. Un PDF scanné sans texte ou un fichier corrompu ne produit aucun extrait (statut `vide`).

---

## Étape 13 : synchronisation des droits d'accès

L'outil de résolution des ACL recopie, dans chaque extrait indexé, la liste des groupes et des comptes autorisés à ouvrir son document. C'est ce qui permet ensuite de ne montrer à chacun que ses documents.

```bash
python acl_resolver.py \
    --share //<NOM-FILESERVER>/FileService \
    --mount /mnt/corpus-root \
    --rapport /var/log/rag/rapport_acl_initial.json
echo "Code de sortie : $?"
```

**Attendu :** code `0` et `Fichiers sans ACL : 0`. Vérifier qu'un extrait porte bien ses droits :

```bash
curl -s -H "api-key: $QDRANT_API_KEY" -H "Content-Type: application/json" \
    http://localhost:6333/collections/documents/points/scroll \
    -d '{"limit":1,"with_payload":["source","autorises","interdits"]}' | python3 -m json.tool | head -15
```

**Attendu :** un champ `autorises` non vide.

---

## Étape 14 : configurer Open WebUI

Ouvrir `http://<IP-VM>:3001` depuis un poste du réseau. Le premier compte créé devient administrateur.

**Raccorder la RAG API :**

1. *Settings → Admin → Connections → API compatibles OpenAI → +*
2. URL : `http://rag-api:8080/v1`
3. Clé API : la valeur de `API_TOKEN` du `.env` (`grep ^API_TOKEN /root/rag-stack/.env`)
4. Enregistrer : le modèle `rag-api` apparaît dans la liste.

**Authentification par l'Active Directory** (facultative en lab, obligatoire en production) :

1. *Settings → Admin → Authentication → LDAP*, activer LDAP
2. Server Address : `<NOM-DC>.votre-domaine.ch`, port `636`, TLS activé
3. Attribute : `userPrincipalName`
4. Base DN : `DC=votre-domaine,DC=ch`
5. Bind DN : `CN=svc-rag,OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch`, Bind Password : le mot de passe de `svc-rag`
6. Certificate Path : `/etc/ssl/certs/ad-chain.pem`

> **`userPrincipalName` est obligatoire**, pas `sAMAccountName`. Open WebUI transmet l'adresse de l'utilisateur à la RAG API, qui la cherche dans ce champ de l'annuaire. Avec un autre attribut, la recherche échoue et tout le monde est refusé (403).

**Rendre le modèle accessible :** *Settings → Admin → Models → rag-api → Make Public*, puis enregistrer.

---

## Étape 15 : configurer n8n

n8n lance la synchronisation du corpus toutes les heures, et rappelle chaque mois la rotation du mot de passe de `svc-rag`. Ouvrir `http://<IP-VM>:5678`.

1. **Créer le compte d'envoi des courriels :** *Settings → Credentials → Add credential → SMTP* (serveur, port, utilisateur et mot de passe de l'expéditeur).
2. **Importer les deux workflows** du dossier `scripts/N8N/` du dépôt (*Workflows → Import from file*) : `n8n-sync-corpus.json` et `n8n-rappel-rotation-svc-rag.json`.
3. Dans chacun, ouvrir le nœud de courriel, choisir le compte SMTP, et remplacer `<EMAIL_EXPEDITEUR>`, `<EMAIL_DESTINATAIRE>` et `<ADMIN_TOKEN>` (la valeur de `ADMIN_TOKEN` du `.env`).
4. Vérifier le nœud « POST /admin/sync » : URL `http://rag-api:8080/admin/sync`, méthode POST, en-tête `Authorization: Bearer <ADMIN_TOKEN>`.
5. Activer les deux workflows, puis lancer une exécution manuelle de la synchronisation.

```bash
docker logs rag-api 2>&1 | grep "\[SYNC\]" | tail -10
```

**Attendu :** `[SYNC] Terminé : success=True`.

> **Une synchronisation occupe la stack et le serveur de modèles.** Tant qu'elle tourne, les réponses sont nettement plus lentes : dans le lab, trois à cinq fois plus lentes pendant une synchronisation lancée juste avant une série de questions (§10.3). Ne pas juger la vitesse de la stack à ce moment-là.

---

## Étape 16 : contrôles finaux

**Une question de test**, dans Open WebUI, sur un document que vous connaissez : la réponse doit le citer entre crochets.

**Le test de cloisonnement**, qui prouve que chacun ne voit que ses documents. Il demande quelques comptes de test créés dans l'Active Directory, et un fichier qui décrit, pour quelques documents, qui doit y avoir accès : partir de `cas_cloisonnement.exemple.json`, l'adapter à vos documents et le copier en `/root/rag-pipeline/cas_cloisonnement.json` (format au §16.3). Puis :

```bash
docker exec rag-api python3 /rag-pipeline/test_cloisonnement.py /rag-pipeline/cas_cloisonnement.json
```

**Attendu :** uniquement des `OK`, et en aucun cas une `FUITE`. Une fois ce fichier en place, la RAG API rejoue ces cas après chaque synchronisation (§16.4).

### Checklist

| Contrôle | Commande ou action | Attendu |
|---|---|---|
| Serveur de modèles, depuis la stack | Étape 10 | `200` deux fois |
| Collections Qdrant | `curl -s -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections` | `documents` et `documentation` |
| Extraits indexés | Étape 12 | Plus de 0 dans les deux collections |
| Droits recopiés | Étape 13 | `autorises` non vide |
| Santé de la RAG API | `docker compose exec n8n wget -qO- http://rag-api:8080/health` | `"status":"ok"` |
| Recherche par mots-clés chargée | `docker logs rag-api \| grep BM25` | Un nombre d'extraits |
| Accès autorisé | Question sur un document accessible | Réponse avec citation |
| Accès refusé | Compte sans droit, question sur un document restreint | « Cette information ne figure pas... » |
| Test de cloisonnement | Étape 16 | Aucune `FUITE` |
| Journal nLPD | `tail -1 /var/log/rag/rag-queries.jsonl` | Une entrée avec `user_id` et `ancree` |
| Synchronisation horaire | n8n, dernière exécution | Réussie |
| Garde-fou des droits | `SMB_PASSWORD=faux python acl_resolver.py ...` | Code 1, `[GARDE-FOU]`, Qdrant intact |
| Lecture du partage | `.\Set-AccesIndexationRAG.ps1 ... -Verifier` | 0 fichier sans lecture |
| Avec vLLM : la clé est exigée | Étape 3B, point 5 | `401` sans la clé |
| Microsoft 365, si déployé | Checklists de §11.8, §12.9 et §13.9 | Tous les points validés |

---

## Étape 17 (facultative) : Microsoft 365

Cette étape relie la stack à un tenant Microsoft 365 synchronisé avec l'Active Directory par Entra Connect. Les trois modules sont indépendants, mais le premier est requis par les deux autres. Le `docker-compose.yml` du dépôt transmet déjà toutes les variables : il suffit de les renseigner dans `.env`, puis de redémarrer la RAG API :

```bash
cd /root/rag-stack && docker compose up -d rag-api
```

Chaque application Microsoft 365 s'authentifie par **certificat**, jamais par secret. Les certificats sont créés sur la VM, dans `/etc/rag-certs` :

```bash
cd /etc/rag-certs
openssl req -x509 -newkey rsa:2048 -nodes -keyout <nom>.key -out <nom>.crt -days 730 -subj "/CN=<Nom-Application>"
chmod 600 <nom>.key
openssl x509 -in <nom>.crt -noout -fingerprint -sha1 | tr -d ':' | cut -d= -f2    # empreinte pour .env
```

### 17.1 Groupes Entra ID (§11), prérequis des modules suivants

1. Certificat `rag-identity` ;
2. App Registration `RAG-Identity-Resolver` : certificat chargé, autorisations **d'application** Microsoft Graph `User.Read.All` et `GroupMember.Read.All`, consentement administrateur ;
3. `.env` : `ENTRA_ENABLED=true`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CERT_THUMBPRINT` (chemins par défaut conservés) ;
4. Validation : après une question dans Open WebUI, `docker logs rag-api 2>&1 | grep "\[AUTH\] Entra"` affiche le nombre d'identifiants Entra de l'utilisateur.

Détail : [§11 Prérequis Microsoft 365](section-11-prerequis-ms365.md).

### 17.2 Synthèse des réunions Teams (§12)

1. Centre d'administration Teams : transcription active dans la stratégie de réunion, et **Transcript API access** activé avec l'attribution des intervenants (désactivé par défaut : sans lui, toute requête est refusée) ;
2. Groupe d'adhésion `GRP-Teams-CompteRendu-IA`, de type sécurité à extension messagerie, créé en PowerShell Exchange Online, avec les organisateurs concernés ;
3. Certificat `rag-teams` et App Registration `RAG-Teams-Reader` : autorisation d'application `OnlineMeetingTranscript.Read.All`, consentement ;
4. Stratégie d'accès applicatif Teams attribuée au groupe (`New-CsApplicationAccessPolicy`, puis `Grant-CsApplicationAccessPolicy -Group <ID-objet-du-groupe>`) ;
5. `.env` : `TEAMS_CLIENT_ID`, `TEAMS_CERT_THUMBPRINT`, `TEAMS_GROUP_ID` ;
6. n8n : importer `n8n-teams-sync.json`, expéditeur = compte SMTP authentifié ;
7. Validation : `docker exec -e PYTHONPATH=/app -w /app rag-api python3 /rag-pipeline/test_teams_graph.py` (script de [`scripts/teams-test/`](../../scripts/teams-test/), copié dans `/root/rag-pipeline`).

Détail : [§12 Synthèse des réunions Teams](section-12-teams.md).

### 17.3 Connecteur SharePoint Online (§13)

1. Inventaire des permissions avec les scripts de [`scripts/sharepoint/`](../../scripts/sharepoint/) : bibliothèques de conservation, membres atypiques, partages ;
2. Certificat `rag-sharepoint` et App Registration `RAG-SharePoint-Indexer` : autorisations d'application `Sites.Selected` pour **Microsoft Graph et SharePoint**, consentement ;
3. Lecture accordée site par site : `Accorder-SitesSelected.ps1` ;
4. `.env` : `SP_CLIENT_ID`, `SP_CERT_THUMBPRINT`, `SP_SITES` (exactement les sites accordés) ;
5. Simulation, rien n'est écrit : `docker exec -e PYTHONPATH=/app -w /app rag-api python3 /rag-pipeline/sp_indexer.py --dry-run`, puis contrôle des `autorises[]` dans le rapport `/var/log/rag/rapport_sharepoint_*.json` ;
6. Première synchronisation par `/admin/sync` (workflow n8n), qui enchaîne le partage de fichiers et SharePoint ;
7. Validation : cloisonnement testé avec des comptes de test **créés dans l'Active Directory** (Open WebUI authentifie par LDAP).

Détail : [§13 Connecteur SharePoint Online](section-13-sharepoint.md). Pour les documents protégés par Purview : [§14](section-14-purview.md).

---

## En cas de problème

**La RAG API redémarre en boucle**

```bash
docker logs rag-api 2>&1 | tail -30
```

Le plus souvent : une variable manquante dans `.env`, le certificat `/etc/ssl/certs/ad-chain.pem` absent, ou Qdrant pas encore prêt (attendre 30 secondes, puis `docker compose restart rag-api`).

**Tout le monde est refusé (403)**

```bash
LDAPTLS_CACERT=/etc/ssl/certs/ad-chain.pem ldapwhoami -H ldaps://<NOM-DC>.votre-domaine.ch:636 \
    -D "CN=svc-rag,OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch" -w "<mot-de-passe>" 2>&1
```

Causes : mot de passe de `svc-rag` erroné ou changé, compte verrouillé, certificat de l'autorité de certification incorrect, ou attribut LDAP d'Open WebUI autre que `userPrincipalName`.

**La VM ne joint pas le serveur de modèles (étape 8)**

- Avec Ollama : `OLLAMA_HOST` absent (Ollama n'écoute que sur sa propre machine) ou port 11434 fermé dans le pare-feu Windows (§2.3).
- Avec vLLM dans WSL2 : la règle de pare-feu Hyper-V de l'étape 3B, ou un serveur arrêté (vérifier sur le serveur : `ss -ltn | grep -E ':800[01]'`, deux lignes attendues).

**La VM joint le serveur de modèles, mais pas la stack (étape 10 : `No route to host`)**

Constaté une fois dans le lab, sans cause établie : le réseau interne de Docker avait perdu son adresse IPv4. Le conteneur ne pouvait plus rien joindre hors de la VM, alors que la VM elle-même joignait le serveur. Vérifier :

```bash
ip -br addr show br-$(docker network inspect rag-stack_default --format '{{.Id}}' | cut -c1-12)
```

Si la ligne ne montre aucune adresse IPv4 (seulement une adresse qui commence par `fe80::`), redémarrer Docker, qui recrée l'adresse :

```bash
systemctl restart docker
cd /root/rag-stack && docker compose up -d
```

Puis refaire le contrôle de l'étape 10.

**Les questions échouent avec une erreur 503, journal : « Échec de la recherche documentaire »**

Le serveur d'embedding ne répond pas : sans vecteur de la question, pas de recherche. Avec vLLM, le serveur du port 8001 est arrêté (son terminal a été fermé, par exemple) ; avec Ollama, le modèle `nomic-embed-text` manque.

**vLLM refuse de démarrer**

Les messages rencontrés en lab et leur solution sont au §2.4.9.

**Les réponses sont soudain très lentes**

Une synchronisation est peut-être en cours (`docker logs rag-api 2>&1 | grep "\[SYNC\]" | tail -3`). Si les lenteurs persistent au repos : la mémoire de la carte déborde (§10.2).

**Le montage du partage tombe après un redémarrage**

```bash
mount -a && mount | grep corpus-root
```

Vérifier le mot de passe dans `/etc/smbcredentials/svc-rag` (rotation non reportée ?) et la ligne de `/etc/fstab`.

**La recherche par mots-clés est vide au démarrage (BM25)**

Qdrant a démarré après la RAG API. Attendre 30 secondes, puis :

```bash
docker compose restart rag-api
docker logs rag-api 2>&1 | grep BM25
```

**Le garde-fou des droits s'est déclenché (code 1)**

Plus de 20 % des fichiers étaient illisibles : le résolveur refuse alors de toucher à Qdrant. Vérifier que `svc-rag` n'est pas verrouillé (sur Windows : `Get-ADUser svc-rag -Properties LockedOut`, puis `Unlock-ADAccount -Identity svc-rag`), que le partage est monté (`ls /mnt/corpus-root`), et que le contrôleur de domaine répond (`ldapwhoami`, ci-dessus).

---

[Retour au sommaire](index.md) | [Section suivante : §1 Prérequis et création de la VM](section-01-prerequis.md)

---

*Validé en lab sur VM-RAG-LAB (Ubuntu Server 26.04) et LABO-G9 (NVIDIA RTX 5060 Ti 16 Go), avec Ollama puis vLLM 0.31.0, octobre 2026.*

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
