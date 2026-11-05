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

**Statut :** validé en lab avec les deux moteurs du serveur de modèles, Ollama et vLLM (§2). **Dernier rejeu de bout en bout : version 2.23.0, le 1er novembre 2026**, sur une VM neuve à un seul disque, avec Ollama, `bge-m3`, le reranker sur la carte du serveur de modèles et un certificat auto-signé : volume chiffré et TPM (mise à jour du dbx et réinscription comprises), `deploy.sh`, indexation (1 616 extraits), tests de sécurité (28, 32, 27, 56 et 6 tests OK), Open WebUI en LDAPS, n8n et synchronisation, cloisonnement (207 verdicts, tous OK), usurpation refusée, refus par adresse IP, mesure du §10 (76 réponses conformes sur 105 sans reranker, 83 avec, aucun élément interdit), sauvegarde et restauration de Qdrant 1.20, redémarrage avec la stack en service. Ce rejeu a fait corriger `deploy.sh` (recherche par mots-clés à activer après la première indexation) et quelques points du guide. **Depuis la 2.23.1**, l'étape 4 décrit elle-même la création de la VM, l'installation de Docker, le chiffrement du volume des données et l'inscription du TPM, mise à jour du dbx comprise : ce §0 suffit pour un déploiement complet. Elle reprend les commandes du §1.4, du §1.5.1 (solution A) et du §15.3, telles qu'elles ont été rejouées le 1er novembre 2026 ; l'étape 17 reprend de même la mise en place du reranker du §10.8. Leur nouvelle présentation n'a pas encore été rejouée telle quelle. **Non rejoué sur une VM neuve :** le déploiement complet avec vLLM (validé dans le lab sur une installation existante, §2.4). Rejeux précédents : du 15 au 17 octobre 2026 (2.20.4), le 19 octobre 2026 avec le frontal HTTPS et l'identité signée (2.21.1, 72 verdicts de cloisonnement), les 23 et 24 octobre 2026 sur une première VM à un seul disque avec un certificat de l'autorité interne (2.22.2, 81 verdicts) ; chacun a fait corriger le script et ce guide (CHANGELOG).

---

## Ce que vous allez obtenir

Un assistant comparable à ChatGPT, mais **installé chez vous**. Vos collaborateurs lui posent des questions dans leur navigateur ; il répond **à partir des documents de l'entreprise** (le serveur de fichiers, et en option SharePoint), cite ses sources, et **ne montre à chacun que les documents qu'il a déjà le droit d'ouvrir** sur le serveur de fichiers. Les questions et les réponses sont traitées sur vos machines : aucun service d'IA externe n'est appelé.

Ce guide mène d'une installation vierge à un assistant en service. Comptez une journée pour un premier déploiement : deux à trois heures pour la stack elle-même, plus l'installation du serveur de modèles (une demi-heure avec Ollama, une à deux heures avec vLLM) et le téléchargement des modèles (environ 13 Go). Microsoft 365, en option, vient ensuite.

---

## Les trois machines

| Machine | Rôle | Ce qui y tourne |
|---|---|---|
| **Serveur Windows existant** | L'annuaire et les documents | Active Directory, serveur de fichiers (partage réseau) |
| **VM de la stack**, Ubuntu Server 26.04 | L'application | Open WebUI (l'interface de discussion), la RAG API (le cœur : identité, droits, recherche, contrôle des réponses), Qdrant (l'index des documents), n8n (les tâches planifiées) |
| **Serveur de modèles**, avec une carte graphique NVIDIA | Les modèles d'IA | Le moteur, Ollama ou vLLM, et les modèles de trois tâches : rédaction, vérification, recherche (trois modèles avec Ollama, deux avec vLLM, §2.1) |

```
 Utilisateur (navigateur)
        │
        ▼
 VM de la stack ── Nginx (HTTPS) → Open WebUI → RAG API → Qdrant (index des documents)
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
- **De quoi héberger la VM de la stack** : un hyperviseur (VMware Workstation dans le lab) capable de lui donner 6 vCPU, 16 Go de mémoire, 100 Go de disque, un démarrage **UEFI** et un **TPM 2.0** virtuel. L'étape 4 crée la VM, installe Ubuntu Server 26.04 et Docker, et chiffre le volume des données.
- **Une carte graphique NVIDIA d'au moins 16 Go** sur le serveur de modèles (le lab : une RTX 5060 Ti 16 Go). Sans carte, Ollama fonctionne sur le processeur, mais une question prend une à deux minutes (§10.4) ; vLLM exige une carte.
- **Un accès à Internet** pendant l'installation : paquets, images Docker, modèles.
- **Les informations de votre réseau** : l'adresse IP de la VM, celle du serveur de modèles, le nom DNS du contrôleur de domaine, le nom du serveur de fichiers et du partage à indexer.
- **Un nom DNS pour la stack**, par exemple `rag.votre-domaine.ch` : un enregistrement A vers l'adresse de la VM, dans la zone du domaine (§9.8.2). C'est par ce nom que les utilisateurs ouvriront l'assistant, en HTTPS.
- **Facultatif : un certificat de l'autorité interne** pour ce nom (§9.8.4). Sans lui, un certificat auto-signé est généré : les connexions sont chiffrées, mais les navigateurs affichent un avertissement jusqu'à son remplacement.

> **Conventions de ce guide.** Les blocs `powershell` se lancent sur Windows, dans PowerShell **ouvert en administrateur**. Les blocs `bash` se lancent sur Linux. Sur la VM, **toutes les commandes se lancent en root** : ouvrir d'abord une session root avec `sudo -i`. Les valeurs entre chevrons, `<comme-ceci>`, sont à remplacer par les vôtres, chevrons compris. Chaque étape se termine par un résultat **attendu** : ne pas passer à la suite tant qu'il n'est pas obtenu.

---

## Les étapes en un coup d'œil

| Étape | Où | Quoi |
|---|---|---|
| 1 | Windows, Active Directory | Créer le compte de service `svc-rag` |
| 2 | Windows, Active Directory | Exporter le certificat de l'autorité de certification |
| 3 | Serveur de modèles | Installer **Ollama (3A)** ou **vLLM (3B)** |
| 4 | Hyperviseur, puis VM | Créer la VM, installer Ubuntu et Docker (4A, 4B), chiffrer le volume des données et inscrire le TPM (4C), préparer l'accès au domaine (4D) |
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
| 17 | Serveur de modèles, puis VM, facultatif | Le reranker, sur la carte du serveur de modèles |
| 18 | Microsoft 365, facultatif | Entra ID, Teams, SharePoint |

Les étapes 5 à 11 peuvent aussi être enchaînées par le script `deploy.sh` : voir « Avant l'étape 5 ».

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

Commencer par **lister** les certificats, sans rien exporter, pour choisir le bon en connaissance de cause :

```powershell
# Autorités racines, puis autorités intermédiaires
Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -like "*votre-domaine*" } |
    Format-List Subject, Issuer, Thumbprint, NotAfter
Get-ChildItem Cert:\LocalMachine\CA | Where-Object { $_.Subject -like "*votre-domaine*" } |
    Format-List Subject, Issuer, Thumbprint, NotAfter
```

Une autorité **racine** a un `Issuer` identique à son `Subject`. Une autorité **intermédiaire** (émettrice) a pour `Issuer` la racine. Exporter ensuite chaque certificat par son empreinte (`Thumbprint`), jamais par « le premier de la liste » : la racine peut apparaître à plusieurs endroits des magasins de certificats, et un filtre sur le nom ne désigne alors pas un certificat unique.

```powershell
# Ou par l'interface : certlm.msc → clic droit sur le certificat → Toutes les tâches → Exporter
$racine = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Thumbprint -eq "<EMPREINTE-RACINE>" } |
    Select-Object -First 1
Export-Certificate -Cert $racine -FilePath "C:\Temp\ad-root-ca.cer" -Type CERT
```

Garder `ad-root-ca.cer` sous la main : la VM n'existe pas encore. Il sera copié sur la VM et converti à l'étape 4D.

> **PKI à deux niveaux** (autorité racine et autorité émettrice) : exporter de la même façon le certificat de l'autorité intermédiaire (`C:\Temp\ad-sub-ca.cer`, magasin `Cert:\LocalMachine\CA`). Les deux seront réunis dans le même fichier à l'étape 4D. Le lab compte deux niveaux : le certificat du contrôleur de domaine y est délivré directement par la racine, et le fichier de chaîne contient la racine et l'autorité intermédiaire.

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
[Environment]::SetEnvironmentVariable("LLAMA_ARG_CACHE_RAM", "2048", "User")
```

Puis quitter Ollama depuis la zone de notification et le relancer : les réglages ne sont lus qu'au démarrage. `LLAMA_ARG_CACHE_RAM` limite le cache des questions que chaque modèle garde en mémoire centrale : environ 12 Go de mémoire du serveur de modèles en moins pour les deux modèles, sans perte de qualité mesurée (§10.1). Le rôle de chaque réglage, et le contrôle dans le journal d'Ollama : §10.1.

**3. Télécharger les trois modèles :**

```powershell
ollama pull qwen3:14b
ollama pull qwen3:4b-instruct
ollama pull bge-m3
ollama list
```

**Attendu :** les trois modèles dans la liste. La vérification depuis la VM vient à l'étape 8.

> **Ollama tourne dans la session Windows ouverte.** Se déconnecter de la session l'arrête, et sur un poste qui porte aussi les VM (VMware Workstation), la fermeture de session suspend en plus les VM (constaté dans le lab). Fermer simplement la fenêtre du Bureau à distance, ou verrouiller le poste, laisse tout tourner. Ollama sous Linux : §2.3.

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
hf download BAAI/bge-m3 --exclude "onnx/*" --exclude "imgs/*"
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
vllm serve BAAI/bge-m3 --runner pooling \
  --served-model-name bge-m3 --max-model-len 2048 --gpu-memory-utilization 0.11 --enforce-eager \
  --host 0.0.0.0 --port 8001 --api-key "$VLLM_API_KEY"
```

**5. Vérifier**, dans un troisième terminal : `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/v1/models`, puis la même chose avec le port 8001. **Attendu :** `401` deux fois (le serveur répond, et exige la clé). L'essai complet, qui contrôle aussi la qualité des réponses, est au §2.4.6.

> **Les deux serveurs s'arrêtent si on ferme leur terminal.** Les laisser ouverts pendant tout le déploiement. Le démarrage automatique par des services systemd est décrit au §2.4.7 ; validé dans WSL2, il ne dispense pas de garder un terminal Ubuntu ouvert, car WSL2 s'arrête quand le dernier se ferme. Si un démarrage échoue, les messages rencontrés et leur solution sont au §2.4.9.

> **Facultatif, après la mise en service : le reranker.** Il reclasse les extraits trouvés avant la rédaction de la réponse. Dans le lab, sur la carte du serveur de modèles : 83 réponses conformes sur 105 au lieu de 76, plus aucun élément interdit, 0,2 seconde par question. Il est désactivé par défaut ; sa mise en place est l'étape 17.

---

## Étape 4 : créer et préparer la VM

Quatre parties, **dans cet ordre** :

| Partie | Quoi |
|---|---|
| 4A | Créer la VM et installer Ubuntu Server 26.04 |
| 4B | Installer Docker |
| 4C | Chiffrer le volume des données et inscrire le TPM |
| 4D | Paquets, DNS du domaine et certificat de l'autorité |

Le chiffrement (4C) vient **avant** tout le reste : tout ce qui serait écrit avant lui (secrets, `.env`, données) resterait en clair sur le disque système, et la suppression ne l'efface pas (§15.3.4).

Cette étape décrit le cas validé dans le lab : une VM sous VMware Workstation, **un seul disque**, le volume chiffré créé dans l'espace libre du LVM. Pour un second disque dédié aux données, ou une machine sans espace libre (DGX Spark, serveur déjà installé), seule la désignation du volume change dans 4C : voir §1.5 et §1.5.1 (solution B).

### 4A : créer la VM et installer Ubuntu Server 26.04

**Créer la VM** (VMware Workstation ; avec un autre hyperviseur, les réglages équivalents) :

| Réglage | Valeur | Pourquoi |
|---|---|---|
| Système invité | Ubuntu 64 bits | |
| Micrologiciel | **UEFI** | Exigé par le TPM |
| TPM | **Ajouter un TPM virtuel** (*Trusted Platform Module*) | Il ouvre le volume chiffré au démarrage, sans saisie (4C). VMware Workstation chiffre alors les fichiers de la VM et demande un mot de passe : le ranger dans le gestionnaire de mots de passe de l'organisation |
| Processeurs | **1 processeur, 6 cœurs** | Un seul socket, pas 2 × 3 (§1.1) |
| Mémoire | 16 Go | Les modèles ne tournent pas dans cette VM |
| Disque | **100 Go, contrôleur SCSI (LSI Logic)**, pas NVMe | Avec NVMe, des écritures se bloquent 30 secondes (constat du lab, §1.1). Le contrôleur d'une VM avec TPM ne se change plus facilement : le choisir dès la création |
| Réseau | Carte vmxnet3, sur le réseau qui joint le contrôleur de domaine et le serveur de fichiers | |

**Installer Ubuntu Server 26.04 LTS** depuis son image ISO :

- **Disque** : disposition proposée par défaut, **LVM activé**, sans agrandir le volume système. L'installateur n'en attribue au système qu'environ la moitié (48,5 Go sur 97 Go dans le lab) : l'espace restant accueillera le volume chiffré (4C). **Ne pas l'étendre.**
- **Réseau** : adresse IP fixe, et comme serveur DNS **uniquement celui du domaine** (l'adresse du contrôleur de domaine), jamais un DNS public (explication en 4D).
- **SSH** : cocher l'installation du serveur OpenSSH, pour travailler depuis un poste.
- Un compte d'administration, avec un mot de passe fort.

Après le redémarrage, se connecter en SSH depuis un poste, puis :

```bash
sudo -i
apt update && apt upgrade -y && apt install -y curl gnupg
```

Contrôler ensuite le micrologiciel, le TPM et l'espace libre :

```bash
[ -d /sys/firmware/efi ] && echo "Démarrage UEFI"; systemd-cryptenroll --tpm2-device=list; vgs
```

**Attendu :** `Démarrage UEFI`, une ligne avec `/dev/tpmrm0`, puis le groupe `ubuntu-vg` avec **au moins 30 Go** dans la colonne `VFree`. Sans `Démarrage UEFI` ou sans `/dev/tpmrm0`, la VM démarre en BIOS ou n'a pas de TPM : la corriger (ou la recréer) avant d'aller plus loin, car 4C échouerait. Sans espace libre, voir §1.5.1 (solution B).

### 4B : installer Docker

Depuis le dépôt officiel de Docker, en root :

```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
docker --version && docker compose version
```

**Attendu :** les deux versions. Validé au rejeu du 1er novembre 2026 : Docker 29.9.2 et Compose 5.6.1, fournis sans autre manipulation par le dépôt de Docker pour Ubuntu 26.04 (`resolute`). **N'ajouter aucun compte au groupe `docker`** : ce groupe équivaut à root (§1.5).

### 4C : chiffrer le volume des données et inscrire le TPM

La stack conserve des extraits de tous les documents indexés, l'historique des conversations, le journal nLPD, des mots de passe et des clés privées. Tout cela va sur un volume **chiffré avec LUKS2**, monté sur `/srv/rag-donnees`. Au démarrage, le **TPM** de la VM libère la clé sans saisie ; une **phrase secrète** reste la clé de secours. Principe et limites : §15.3.1.

> **Deux règles pour toute cette partie.** Une commande qui demande la phrase secrète se lance **seule** : collée avec d'autres, les lignes suivantes seraient lues comme la phrase. Et chaque commande se termine avant de passer à la suivante.

**1. Choisir la phrase secrète, avant tout le reste.** Cinq ou six mots tirés au hasard, séparés par des tirets, avec un chiffre. Éviter les lettres dont la place change selon le clavier (y, z), les accents et les caractères spéciaux autres que le tiret : la phrase devra peut-être être saisie un jour depuis une console. **La ranger dans le gestionnaire de mots de passe avant le formatage** : sans elle, un refus du TPM rend les données irrécupérables.

**2. Créer le volume**, ici de 30 Go (la taille du lab ; il s'agrandit plus tard, voir §1.5.1) :

```bash
apt install -y cryptsetup tpm2-tools
lvcreate -L 30G -n rag-donnees ubuntu-vg
wipefs -n /dev/ubuntu-vg/rag-donnees
```

**Attendu :** `Logical volume "rag-donnees" created.`, puis **aucune sortie** pour `wipefs` (le volume est vierge).

**3. Le chiffrer.** Cette commande, **seule** : taper `YES` en majuscules, puis la phrase deux fois.

```bash
cryptsetup luksFormat --type luks2 /dev/ubuntu-vg/rag-donnees
```

Puis l'ouvrir, **seule** aussi (la phrase est demandée) :

```bash
cryptsetup open /dev/ubuntu-vg/rag-donnees rag-donnees
```

Puis créer le système de fichiers et le monter :

```bash
mkfs.ext4 -L rag-donnees /dev/mapper/rag-donnees
mkdir -p /srv/rag-donnees && mount /dev/mapper/rag-donnees /srv/rag-donnees
findmnt /srv/rag-donnees
```

**Attendu :** une ligne `/srv/rag-donnees /dev/mapper/rag-donnees ext4`.

**4. Inscrire le TPM.** Relever d'abord l'identifiant du volume :

```bash
UUID=$(cryptsetup luksUUID /dev/ubuntu-vg/rag-donnees); echo "$UUID"
```

Puis cette commande, **seule** (la phrase est demandée) :

```bash
systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /dev/disk/by-uuid/$UUID
```

**Attendu :** `New TPM2 token enrolled as key slot 1.` Contrôle :

```bash
cryptsetup luksDump /dev/disk/by-uuid/$UUID | grep -E "^  [0-9]+: (luks2|systemd-tpm2)"
```

**Attendu :** deux lignes `luks2` (l'emplacement 0, la phrase, et 1, le TPM) et une ligne `systemd-tpm2`. `--tpm2-pcrs=7` lie la clé à l'état du démarrage sécurisé : elle résiste aux mises à jour du noyau, mais pas à celles de la liste de révocation du Secure Boot (point 9). Ne pas modifier non plus le réglage du démarrage sécurisé de la VM après l'inscription.

**5. Ouvrir et monter le volume à chaque démarrage.** Chaque ligne n'est ajoutée que si elle manque : relancée, la commande ne crée pas de doublon (une ligne en double dans `/etc/fstab` a été constatée au rejeu du 1er novembre 2026).

```bash
grep -q '^rag-donnees ' /etc/crypttab || echo "rag-donnees UUID=$UUID none luks,discard,tpm2-device=auto,nofail" >> /etc/crypttab
grep -q ' /srv/rag-donnees ' /etc/fstab || echo "/dev/mapper/rag-donnees /srv/rag-donnees ext4 defaults,nofail,x-systemd.device-timeout=30s 0 2" >> /etc/fstab
systemctl daemon-reload
grep -c rag-donnees /etc/crypttab /etc/fstab
```

**Attendu :** `/etc/crypttab:1` et `/etc/fstab:1`, avec l'UUID affiché au point 4 dans `/etc/crypttab`. `nofail` garantit que la VM démarre même si le volume ne s'ouvre pas : elle reste alors joignable en SSH pour le déverrouillage de secours (point 7).

**6. Docker ne démarre qu'avec le volume monté**, sans déclencher lui-même le déverrouillage :

```bash
mkdir -p /etc/systemd/system/docker.service.d
printf '[Unit]\nAfter=srv-rag\\x2ddonnees.mount var-log-rag.mount\nConditionPathIsMountPoint=/srv/rag-donnees\n' > /etc/systemd/system/docker.service.d/rag-donnees.conf
systemctl daemon-reload
systemctl cat docker | grep Condition
```

**Attendu :** une seule ligne, `ConditionPathIsMountPoint=/srv/rag-donnees`. Sans cette condition, Docker démarrerait sur un volume fermé, dans des dossiers **vides** : Qdrant repartirait avec une base vide. Ne pas utiliser `RequiresMountsFor`, qui déclenche le déverrouillage et provoque une demande de phrase à la console à chaque démarrage (§15.3.7).

**7. Le déverrouillage de secours**, pour le jour où le TPM refuse la clé :

```bash
cat > /usr/local/sbin/rag-deverrouiller <<'EOF'
#!/bin/bash
# Déverrouille le disque de données chiffré, le monte, puis démarre Docker.
set -e
UUID=$(awk '$1=="rag-donnees"{sub("UUID=","",$2);print $2}' /etc/crypttab)
cryptsetup status rag-donnees >/dev/null 2>&1 || cryptsetup open /dev/disk/by-uuid/$UUID rag-donnees
mountpoint -q /srv/rag-donnees || mount /srv/rag-donnees
if grep -q " /var/log/rag " /etc/fstab; then
  mountpoint -q /var/log/rag || mount /var/log/rag
fi
# Partage du corpus : ses identifiants sont sur le volume chiffré (§0, étape 5)
if grep -q " /mnt/corpus-root " /etc/fstab; then
  mountpoint -q /mnt/corpus-root || mount /mnt/corpus-root || echo "Partage non monté : vérifier le réseau, puis mount /mnt/corpus-root"
fi
systemctl start docker
echo "Disque déverrouillé et monté, Docker démarré"
EOF
chmod 700 /usr/local/sbin/rag-deverrouiller
```

Il se lance **seul**, en SSH : `rag-deverrouiller`. Il demande la phrase, ouvre et monte le volume, remonte le partage de fichiers (étape 5), puis démarre Docker.

**8. Préparer les dossiers de la stack sur le volume.** La stack les trouvera à leurs emplacements habituels, sous forme de liens vers le volume chiffré :

```bash
mkdir -p /srv/rag-donnees/{qdrant_data,openwebui_data,n8n_data,log-rag,secrets/rag-certs,secrets/rag-tls}
chmod 700 /srv/rag-donnees/secrets /srv/rag-donnees/secrets/rag-certs /srv/rag-donnees/secrets/rag-tls
chown -R 1000:1000 /srv/rag-donnees/n8n_data
mkdir -p /root/rag-stack
for d in qdrant_data openwebui_data n8n_data; do ln -s /srv/rag-donnees/$d /root/rag-stack/$d; done
ln -s /srv/rag-donnees/secrets/.env      /root/rag-stack/.env
ln -s /srv/rag-donnees/secrets/rag-certs /etc/rag-certs
ln -s /srv/rag-donnees/secrets/rag-tls   /etc/rag-tls
ln -s /srv/rag-donnees/log-rag           /var/log/rag
ls -l /root/rag-stack /etc/rag-certs /etc/rag-tls /var/log/rag
```

**Attendu :** sept liens vers `/srv/rag-donnees` : `qdrant_data`, `openwebui_data`, `n8n_data` et `.env` dans `/root/rag-stack`, puis `/etc/rag-certs`, `/etc/rag-tls` et `/var/log/rag`. Le lien `.env` désigne un fichier qui n'existe pas encore : c'est normal, il est créé à l'étape 7. `n8n_data` appartient à l'utilisateur 1000, sous lequel tourne n8n : sinon, il redémarre en boucle (`EACCES`). Si `/var/log/rag` existe déjà en dossier ordinaire, `ln` le signale : le retirer (`rmdir /var/log/rag`, il est vide) et relancer la ligne.

> **Avec le `.env` en lien, deux pièges.** `sed -i` sur `/root/rag-stack/.env` **remplace le lien par un vrai fichier**, sur le disque système, en clair ; `cp` refuse d'écrire tant que la cible n'existe pas. Toujours désigner le vrai fichier : `/srv/rag-donnees/secrets/.env`, ou `$(readlink -f /root/rag-stack/.env)`, comme à l'étape 7.

**9. La liste de révocation du Secure Boot (dbx), à mettre à jour maintenant.** Ubuntu propose cette mise à jour de sécurité par `fwupd`. Le PCR 7 la mesure : **après elle, le TPM refuse la clé** au redémarrage suivant. Mieux vaut l'appliquer maintenant, sur un volume encore vide, que plus tard sur une stack en service. Chercher d'abord :

```bash
fwupdmgr refresh --force
fwupdmgr get-upgrades
```

**Attendu :** soit aucune mise à jour (rien à faire, passer au point 10), soit un appareil **UEFI dbx** avec une flèche de version, par exemple `Current version: 20230501` puis `New version: 20260707`. Sans `refresh --force`, des métadonnées périmées peuvent masquer la mise à jour. Et le nom « UEFI dbx » figure aussi dans la liste des appareils **sans** mise à jour : seule la flèche de version fait foi (constat du rejeu du 1er novembre 2026).

S'il y a une mise à jour : `fwupdmgr update`, puis redémarrer (`reboot`). Au redémarrage, le volume reste fermé : c'est attendu. En SSH, ouvrir le volume avec la phrase, **seul** :

```bash
rag-deverrouiller
```

Le message `TPM policy does not match current system state` est attendu. Puis réinscrire le TPM, **seul** aussi (la phrase est redemandée) :

```bash
systemd-cryptenroll --wipe-slot=tpm2 --tpm2-device=auto --tpm2-pcrs=7 /dev/disk/by-uuid/$(awk '$1=="rag-donnees"{sub("UUID=","",$2);print $2}' /etc/crypttab)
```

**Attendu :** l'ancienne inscription effacée et une nouvelle créée ; le contrôle du point 4 montre de nouveau deux lignes `luks2` et une seule ligne `systemd-tpm2`. Après un refus du TPM, systemd attend la phrase du volume et l'affiche dans les sessions root : une invite « Please enter passphrase for disk … » peut apparaître dans un terminal SSH sans qu'aucune commande l'ait posée. Y répondre ouvre aussi le volume.

**10. Redémarrer pour valider :**

```bash
reboot
```

Puis, en SSH, sans rien lancer d'autre :

```bash
sudo -i
findmnt /srv/rag-donnees && systemctl is-active docker && ls -l /root/rag-stack
```

**Attendu :** `/srv/rag-donnees` monté depuis `/dev/mapper/rag-donnees` **sans aucune saisie**, `active`, puis les liens du point 8. Si le volume est fermé : `rag-deverrouiller`, puis reprendre l'inscription du TPM (point 4, avec `--wipe-slot=tpm2` comme au point 9).

**Prendre un snapshot de la VM arrêtée** (`shutdown -h now`) : une VM chiffrée, avec Docker et le TPM, est un bon point de reprise avant le déploiement.

### 4D : paquets, DNS du domaine et certificat de l'autorité

Ouvrir une session root (`sudo -i`). Contrôle de 4B et 4C, utile aussi en reprenant après une pause :

```bash
docker compose version && systemctl show docker -p DropInPaths && findmnt /srv/rag-donnees && ls -la /root/rag-stack /var/log/rag /etc/rag-certs /etc/rag-tls | grep -- '->'
```

**Attendu :** la version de Compose, le fichier `rag-donnees.conf` (4C, point 6), `/srv/rag-donnees` monté depuis `/dev/mapper/rag-donnees`, puis les liens de 4C (point 8). Sans eux, l'étape 5 échoue : le dossier des identifiants n'existe pas (oubli constaté au rejeu du 1er novembre 2026). Puis :

```bash
apt update && apt install -y \
    cifs-utils smbclient samba-common-bin \
    ldap-utils curl wget git \
    python3 python3-pip python3-venv
```

**Le DNS du domaine**, pour que la VM trouve le contrôleur de domaine et le serveur de fichiers par leur nom. Commencer par contrôler l'existant :

```bash
getent hosts <NOM-DC>.votre-domaine.ch
getent hosts <NOM-FILESERVER>
resolvectl status | grep -E "DNS Servers|DNS Domain"
```

**Attendu :** une adresse pour chaque nom, et **uniquement les DNS du domaine** dans `DNS Servers` (l'adresse IP de votre contrôleur de domaine, par exemple). Si c'est le cas, ne rien modifier.

**Jamais de DNS public** (8.8.8.8, 1.1.1.1...) à côté de celui du domaine. `systemd-resolved` bascule sur le serveur public dès que celui du domaine tarde une seule fois, au démarrage par exemple, et n'en revient pas : les noms du domaine deviennent introuvables, et la connexion LDAP comme la lecture des droits tombent en panne au hasard d'un redémarrage. Cas vécu dans le lab : un DNS public ajouté pour contourner une lenteur de téléchargement a provoqué la panne au deuxième redémarrage suivant. Si `resolvectl` en affiche un, le retirer de la configuration réseau, en général `/etc/netplan/*.yaml` (liste `nameservers: addresses:`), puis :

```bash
netplan generate && netplan apply
resolvectl status | grep -E "DNS Servers"
```

Si les noms ne se résolvent pas du tout (aucun DNS du domaine configuré), l'ajouter dans `/etc/systemd/resolved.conf` (avec `nano`), section `[Resolve]`, puis `systemctl restart systemd-resolved` et refaire les deux `getent` :

```ini
[Resolve]
DNS=<IP-DC>
Domains=votre-domaine.ch
```

**Le certificat de l'étape 2.** Copier d'abord `ad-root-ca.cer` (et `ad-sub-ca.cer` avec une PKI à deux niveaux) dans `/tmp` sur la VM, par `scp` depuis le poste Windows ou par un partage, par exemple `scp C:\Temp\ad-root-ca.cer <compte-admin>@<IP-VM>:/tmp/`, depuis PowerShell, avec le compte d'administration créé en 4A. Puis le convertir au format attendu par Linux :

```bash
openssl x509 -inform DER -in /tmp/ad-root-ca.cer -out /etc/ssl/certs/ad-chain.pem
openssl x509 -in /etc/ssl/certs/ad-chain.pem -noout -subject -dates
```

**Attendu :** le nom de l'autorité de certification et ses dates de validité.

Avec une **PKI à deux niveaux**, convertir aussi le certificat intermédiaire, puis réunir les deux dans le fichier de chaîne :

```bash
openssl x509 -inform DER -in /tmp/ad-root-ca.cer -out /tmp/ca-root.pem
openssl x509 -inform DER -in /tmp/ad-sub-ca.cer  -out /tmp/ca-sub.pem
cat /tmp/ca-root.pem /tmp/ca-sub.pem > /etc/ssl/certs/ad-chain.pem
# L'intermédiaire seul sert aussi au certificat de Nginx (§9.8.4)
cp /tmp/ca-sub.pem /etc/ssl/certs/ad-subca.pem
grep -c "BEGIN CERTIFICATE" /etc/ssl/certs/ad-chain.pem
```

**Attendu :** `2`. Contrôler ensuite que le contrôleur de domaine présente un certificat que cette chaîne valide :

```bash
openssl s_client -connect <NOM-DC>.votre-domaine.ch:636 -CAfile /etc/ssl/certs/ad-chain.pem </dev/null 2>/dev/null | grep -E "Verify return code|Verification"
```

**Attendu :** `Verify return code: 0 (ok)`. Une autre valeur indique un certificat manquant dans la chaîne, ou un nom de contrôleur qui ne correspond pas à celui du certificat.

---

## Avant l'étape 5 : à la main ou avec deploy.sh

Les étapes 5 à 11 se font **soit à la main**, dans l'ordre, **soit avec `deploy.sh`**, le script du dépôt, qui les enchaîne en posant des questions. Le résultat est le même ; le script évite les erreurs de recopie et contrôle davantage. Les étapes 1 à 4 restent dans tous les cas à faire à la main, chiffrement compris.

**Ce que fait `deploy.sh` :**

- il demande le moteur (Ollama ou vLLM), les adresses, le nom de la stack (`RAG_FQDN`), le domaine, le compte `svc-rag` et son mot de passe (saisi sans affichage), le serveur de fichiers et le partage ;
- il vérifie que le volume chiffré de l'étape 4C est monté et que chaque chemin sensible y aboutit ; sinon, il demande confirmation avant de continuer en clair ;
- il vérifie que les noms du contrôleur de domaine, du serveur de fichiers et de la stack se résolvent, signale un DNS public dans la configuration de la VM, et contrôle que la stack joint le serveur de modèles ;
- il utilise le certificat placé dans `/etc/rag-tls` (autorité interne, §9.8.4) ou, à défaut, génère un certificat auto-signé (étape 7, point 5) ;
- à la fin, il contrôle que les cinq conteneurs tournent sans redémarrage, que la RAG API répond à travers Nginx et que les tests de sécurité passent ; sinon il liste les problèmes et se termine en erreur au lieu d'annoncer « Déploiement terminé » ;
- il propose enfin la première indexation et la synchronisation des droits (étapes 12 et 13), avec un journal dans `/var/log/rag` ; un échec à ce stade n'annule pas le déploiement.

**Avant de le lancer :** les étapes 1 à 4 faites, le certificat de l'autorité converti (étape 4D), et, pour un certificat de l'autorité interne, `rag.crt` et `rag.key` déjà placés dans `/etc/rag-tls`. Il demande de confirmer par **o** (ou `oui`) : toute autre réponse annule le déploiement, avec un message.

**Le lancer**, en root, avec un journal complet :

```bash
cd /root && git clone https://github.com/doit4everyone/ia-locale-pme-suisse.git
cd /root/ia-locale-pme-suisse/scripts/stack-ia-locale && chmod +x deploy.sh && ./deploy.sh 2>&1 | tee -a /root/deploy.log
```

L'option `-a` ajoute au journal au lieu de l'écraser : sans elle, une relance efface la trace du premier déploiement (cas vécu). Le script peut être relancé après une erreur passagère (téléchargement interrompu, par exemple). S'il trouve un `.env` existant, il demande confirmation avant de le remplacer et en garde une copie datée : le remplacer change tous les jetons, donc l'identifiant n8n et la clé de la connexion d'Open WebUI sont à refaire, et efface les réglages Microsoft 365. **Ne pas relancer `deploy.sh` sur une installation en service.**

**Ensuite**, reprendre à l'**étape 12** si l'indexation proposée a été refusée ou a échoué, ou directement à l'**étape 14** si elle a réussi (le script redémarre lui-même la RAG API pour activer la recherche par mots-clés, fin de l'étape 13). Les explications des étapes 5 à 11 restent utiles pour comprendre ce que le script a fait, et pour le dépannage.

**Statut :** rejoué cinq fois sur une VM neuve, en dernier lieu en version 2.23.0 le 1er novembre 2026, avec un certificat auto-signé (en 2.22.2, le 24 octobre 2026, avec un certificat fourni par l'autorité interne) ; une relance par erreur a été annulée par le garde-fou du `.env`, sans rien modifier.

---

## Étape 5 : monter le partage de fichiers

Le mot de passe de `svc-rag` va dans un fichier lisible par root seulement, jamais dans une ligne de commande, et **sur le volume chiffré** : comme le `.env`, le fichier réel est dans `/srv/rag-donnees/secrets`, avec un lien à l'emplacement habituel. Jusqu'à la 2.22.2, ce fichier était créé dans `/etc/smbcredentials`, sur le disque système, en clair (constat du rejeu du 23 octobre 2026).

```bash
mkdir -p /etc/smbcredentials
ln -s /srv/rag-donnees/secrets/smb-svc-rag /etc/smbcredentials/svc-rag
nano /srv/rag-donnees/secrets/smb-svc-rag
```

Contenu (`<PARTAGE>`, dans les commandes qui suivent, est le nom du partage à indexer : `FileService` dans le lab) :

```
username=svc-rag
password=<mot-de-passe-svc-rag>
domain=VOTRE-DOMAINE
```

```bash
chmod 600 /srv/rag-donnees/secrets/smb-svc-rag
ls -l /etc/smbcredentials/svc-rag /srv/rag-donnees/secrets/smb-svc-rag

mkdir -p /mnt/corpus-root
mount -t cifs //<NOM-FILESERVER>/<PARTAGE> /mnt/corpus-root \
    -o credentials=/etc/smbcredentials/svc-rag,vers=3.1.1,uid=1000,gid=1000,ro
ls /mnt/corpus-root/
```

**Attendu :** le lien vers le volume chiffré, le fichier réel en `-rw-------`, puis les dossiers du partage. Le domaine est donné par la ligne `domain=` du fichier d'identifiants : sans elle, le montage échoue sur un domaine Active Directory. Le montage est en **lecture seule** (`ro`) : la stack ne modifie jamais le partage. Rendre ensuite le montage permanent :

```bash
umount /mnt/corpus-root
cat >> /etc/fstab << 'FSTAB'

# Partage du corpus RAG (monté avec svc-rag, identifiants sur le volume chiffré)
//<NOM-FILESERVER>/<PARTAGE> /mnt/corpus-root cifs credentials=/etc/smbcredentials/svc-rag,vers=3.1.1,uid=1000,gid=1000,ro,soft,nofail,_netdev,x-systemd.after=/srv/rag-donnees 0 0
FSTAB
systemctl daemon-reload && mount -a && findmnt /mnt/corpus-root
```

`x-systemd.after=/srv/rag-donnees` fait monter le partage **après** le volume chiffré, qui porte ses identifiants, sans déclencher lui-même le déverrouillage ; `_netdev` le désigne comme un montage réseau. Si le volume reste fermé (TPM refusé, §15.3.3), le partage n'est pas monté et `nofail` laisse le démarrage se poursuivre : `rag-deverrouiller`, puis `mount /mnt/corpus-root`. Validé au redémarrage avec la stack en service, le 24 octobre 2026 : volume chiffré monté, puis le partage une seconde plus tard.

---

## Étape 6 : récupérer les scripts du dépôt

Les scripts sont publiés dans ce dépôt GitHub. Ceux qui contiennent des valeurs d'exemple portent le préfixe `anon_` : on les renomme en les copiant.

```bash
cd /root
# Déjà cloné si deploy.sh a été envisagé (« Avant l'étape 5 ») : le clone n'est pas refait
[ -d ia-locale-pme-suisse ] || git clone https://github.com/doit4everyone/ia-locale-pme-suisse.git
cd ia-locale-pme-suisse/scripts/stack-ia-locale

# Dossiers de la stack (déjà présents, sous forme de liens, depuis l'étape 4C)
mkdir -p /root/rag-stack/{qdrant_data,n8n_data,openwebui_data} /root/rag-pipeline /var/log/rag
mkdir -p /etc/rag-certs && chmod 700 /etc/rag-certs

# n8n tourne sous l'utilisateur « node » (uid 1000) : sans ce droit, il redémarre en boucle (EACCES).
# readlink -f : suivre le lien de l'étape 4C jusqu'au vrai dossier, sinon chown change le lien et pas le dossier.
chown -R 1000:1000 "$(readlink -f /root/rag-stack/n8n_data)"

# La stack : Compose, configuration d'exemple, RAG API, service Purview
cp docker-compose.yml env.example /root/rag-stack/
mkdir -p /root/rag-stack/api /root/rag-stack/mip-service /root/rag-stack/nginx
cp -r api/. /root/rag-stack/api/
mv /root/rag-stack/api/anon_main.py /root/rag-stack/api/main.py
mv /root/rag-stack/api/anon_auth.py /root/rag-stack/api/auth.py
cp -r mip-service/. /root/rag-stack/mip-service/

# Les scripts d'indexation, des droits et de contrôle
cp anon_indexer.py /root/rag-pipeline/indexer.py
cp anon_acl_resolver.py /root/rag-pipeline/acl_resolver.py
cp sp_indexer.py test_cloisonnement.py diag_sid.py cas_cloisonnement.exemple.json /root/rag-pipeline/

# Les tests de sécurité (étape 16), le test du reranker et la campagne de mesure du §10
cp test_citations.py test_sid.py test_revalidation_bm25.py test_echec_droits.py test_reranker.py /root/rag-pipeline/
mkdir -p /root/rag-pipeline/s10 && cp s10/*.py s10/*.json /root/rag-pipeline/s10/

ls /root/rag-stack /root/rag-stack/api /root/rag-pipeline
```

**Attendu :** `main.py`, `auth.py`, `teams.py`, `teams_graph.py`, `Dockerfile` et `requirements.txt` dans `api/` ; `indexer.py`, `acl_resolver.py`, `sp_indexer.py`, `test_cloisonnement.py`, `diag_sid.py`, les cinq tests (`test_citations.py`, `test_sid.py`, `test_revalidation_bm25.py`, `test_echec_droits.py`, `test_reranker.py`) et le dossier `s10` dans `/root/rag-pipeline`. `teams.py`, `teams_graph.py`, `sp_indexer.py` et `mip-service` servent à Microsoft 365 : ils restent inactifs tant que leurs réglages sont vides.

---

## Étape 7 : remplir le fichier de configuration .env

Le fichier `.env` réunit tous les réglages et secrets de la stack. Il ne doit jamais être publié ni copié dans un document.

**1. Créer le fichier et générer les secrets automatiquement :**

```bash
cd /root/rag-stack
# Avec le volume chiffré de l'étape 4C, .env est un lien : on travaille sur le vrai fichier.
# (sed -i remplace le fichier : appliqué au lien, il le détruirait et laisserait le .env en clair sur le disque système.)
ENVF=$(readlink -f /root/rag-stack/.env)
cp env.example "$ENVF"
chmod 600 "$ENVF"
for v in API_TOKEN ADMIN_TOKEN WEBUI_SECRET_KEY QDRANT_API_KEY LOG_HMAC_KEY MIP_TOKEN OWUI_JWT_SECRET; do
    sed -i "s|^${v}=.*|${v}=$(openssl rand -hex 32)|" "$ENVF"
done
grep -c changeme "$ENVF"
```

**Attendu :** `0` : plus aucune valeur d'exemple pour les secrets. C'est indispensable : depuis la 2.21.0, la RAG API refuse de démarrer sur une valeur d'exemple, un secret vide ou trop court, ou deux jetons identiques (§16.6). Sans disque chiffré, `readlink -f` rend simplement le chemin de `.env` : la suite est identique.

Pour toute modification ultérieure du `.env`, utiliser le même chemin (`$ENVF`, ou `nano /srv/rag-donnees/secrets/.env`), puis **`docker compose up -d <service>`**, jamais `docker compose restart` : `restart` ne relit pas le `.env` et garde l'ancienne valeur, sans erreur.

**2. Compléter le reste à la main** avec `nano .env` :

| Réglage | Valeur | Exemple |
|---|---|---|
| Bloc du serveur de modèles | Voir le point 3 ci-dessous | |
| `ORG_NAME`, `ORG_OWNER` | Le nom de votre organisation, le même dans les deux, **entre apostrophes** (voir ci-dessous) | `'Exemple SA'` |
| `LDAP_HOST` | Le nom DNS complet du contrôleur de domaine, pas son adresse IP | `dc01.votre-domaine.ch` |
| `LDAP_BASE_DN` | Le domaine, en notation LDAP | `DC=votre-domaine,DC=ch` |
| `LDAP_BIND_DN` | Le compte `svc-rag`, avec son OU | `CN=svc-rag,OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch` |
| `LDAP_BIND_PWD`, `SMB_PASSWORD` | Le mot de passe de `svc-rag`, le même aux deux endroits et dans le fichier de l'étape 5 | |
| `LDAP_DOMAIN`, `SMB_DOMAIN` | Le nom NetBIOS du domaine | `VOTRE-DOMAINE` |
| `SMB_SHARE` | Le partage à indexer, le même qu'à l'étape 5 | `//<NOM-FILESERVER>/<PARTAGE>` (lab : `FileService`) |
| `DOCUMENTATION_PATHS` | Facultatif. Le ou les dossiers de documentation technique (guides, procédures, manuels), **à la racine** du partage, séparés par des virgules. Leur contenu va dans la collection `documentation`, tout le reste dans `documents` ; les droits NTFS s'appliquent de la même façon aux deux. **Vide** : tout le partage va dans `documents`. Changer ce réglage après l'indexation exige une réindexation complète (§5.9) | `DOCUMENTATION` (lab : `DOIT4EVERYONE`) |
| `RAG_FQDN` | Le nom DNS de la stack, sans `https://` (§9.8.2). Il fixe aussi l'adresse de n8n, `https://<RAG_FQDN>:5678` | `rag.votre-domaine.ch` |

Les valeurs qui contiennent un espace sont **entre apostrophes** dans `env.example` (par exemple `ORG_NAME='<Nom organisation>'` ou `SP_EXCLUDE_DRIVES='Preservation Hold Library'`). Les conserver, et en mettre à toute valeur saisie qui contient un espace : sans elles, `source .env` échoue avec « command not found » sur le mot qui suit l'espace.

**3. Le bloc du serveur de modèles**, en haut du fichier. Il contient deux blocs : **A pour Ollama**, actif par défaut, et **B pour vLLM**, désactivé (chaque ligne commence par `#`). **Un seul bloc doit être actif.**

- **Avec Ollama :** dans le bloc A, remplacer `<IP-SERVEUR-MODELES>` par l'adresse de la machine Ollama.
- **Avec vLLM :** ajouter un `#` au début de chaque ligne de réglage du bloc A, retirer le `#` des lignes de réglage du bloc B (de `# LLM_API=openai` à `# VLLM_API_KEY=<clé-vllm>`, pas des lignes d'explication qui les précèdent), remplacer `<IP-SERVEUR-MODELES>` par l'adresse du poste ou du serveur vLLM, et `<clé-vllm>` par la clé créée à l'étape 3B. Pour la copier sans l'afficher depuis un poste Windows : §2.4.4.

Plus bas dans le fichier, `OLLAMA_URL` prend la même valeur que `EMBED_BASE_URL` : port 11434 avec Ollama, **port 8001 avec vLLM**. Malgré son nom, cette ligne désigne le serveur d'embedding, avec les deux moteurs.

> **Jamais `localhost`** dans ces adresses, même si la VM et le serveur de modèles tournent sur le même poste : à l'intérieur d'un conteneur, `localhost` désigne le conteneur lui-même.

**4. Contrôler** qu'il ne reste aucune valeur à remplacer :

```bash
grep -nE "^[A-Z_]+=.*<" .env
```

**Attendu :** seulement des lignes `ENTRA_`, `TEAMS_`, `SP_` et `MIP_TENANT_DOMAINE`, qui concernent Microsoft 365 et restent inactives tant qu'il n'est pas configuré.

**5. Le nom de la stack et son certificat** (§9.8). Vérifier d'abord le nom, puis préparer la configuration de Nginx et le certificat :

```bash
cd /root/rag-stack
FQDN=$(grep '^RAG_FQDN=' .env | cut -d= -f2)
getent hosts "$FQDN"
# Attendu : l'adresse IP de la VM

# Configuration de Nginx, au nom de la stack
sed "s/<NOM-STACK>/${FQDN}/g" /root/ia-locale-pme-suisse/scripts/stack-ia-locale/nginx/rag.conf > nginx/rag.conf
grep -c "$FQDN" nginx/rag.conf

# Dossier du certificat : sur le volume chiffré (lien de l'étape 4C)
[ -e /etc/rag-tls ] || mkdir -p /etc/rag-tls
chmod 700 "$(readlink -f /etc/rag-tls)"
ls -l /etc/rag-tls/
```

**Attendu :** l'adresse de la VM, puis un nombre supérieur à 0.

- **Avec un certificat de l'autorité interne :** suivre §9.8.4 pour obtenir `rag.crt` (certificat suivi de l'autorité intermédiaire) et `rag.key`, et les placer dans `/etc/rag-tls`, la clé en `600`.
- **Sans autorité :** générer un certificat auto-signé, remplaçable plus tard sans redéployer (§9.8.6) :

```bash
cd /etc/rag-tls
FQDN=$(grep '^RAG_FQDN=' /root/rag-stack/.env | cut -d= -f2)
openssl req -x509 -newkey rsa:3072 -nodes -days 825 \
    -keyout rag.key -out rag.crt \
    -subj "/CN=${FQDN}" -addext "subjectAltName=DNS:${FQDN}"
chmod 600 rag.key
```

**Attendu :** `rag.crt` et `rag.key` dans `/etc/rag-tls`. Sans eux, Nginx s'arrête au démarrage et la stack n'est pas joignable.

---

## Étape 8 : vérifier que la VM joint le serveur de modèles

**Avec Ollama :**

```bash
curl -s http://<IP-SERVEUR-MODELES>:11434/api/tags | python3 -m json.tool | grep '"name"'
```

**Attendu :** `qwen3:14b`, `qwen3:4b-instruct` et `bge-m3:latest`. Sans réponse : le réglage `OLLAMA_HOST` (étape 3A) ou le pare-feu Windows (§2.3).

**Avec vLLM :**

```bash
VK=$(grep -oP '^VLLM_API_KEY=\K.*' /root/rag-stack/.env)
curl -s -H "Authorization: Bearer $VK" http://<IP-SERVEUR-MODELES>:8000/v1/models | python3 -m json.tool | grep '"id"'
curl -s -H "Authorization: Bearer $VK" http://<IP-SERVEUR-MODELES>:8001/v1/models | python3 -m json.tool | grep '"id"'
```

**Attendu :** `qwen3:14b`, puis `bge-m3`. Si `curl` reste bloqué : la règle de pare-feu de l'étape 3B. Si la réponse est vide : la clé du `.env` ne correspond pas à celle du serveur.

---

## Étape 9 : lancer la stack

```bash
cd /root/rag-stack
docker compose build --no-cache rag-api
docker compose up -d
docker compose ps
```

**Attendu :** `qdrant`, `n8n` et `nginx` en `Up`, `rag-api` et `open-webui` en `Up (healthy)` après une minute environ. Seuls ces deux services déclarent un contrôle de santé : `Up` sans mention est normal pour les trois autres. Seul `nginx` publie des ports sur le réseau (80, 443, 5678) ; `qdrant` publie le sien sur `127.0.0.1` seulement, pour les scripts d'indexation lancés depuis la VM (étapes 12 et 13), et il n'est pas joignable d'une autre machine. Si `rag-api` redémarre en boucle : `docker logs rag-api 2>&1 | tail -30` montre la cause (le plus souvent un secret refusé, ligne `[SÉCURITÉ]`, une variable manquante dans `.env`, ou le certificat de l'étape 4D absent). Si `nginx` s'arrête : `docker logs nginx` (certificat absent de `/etc/rag-tls`, ou `nginx/rag.conf` manquant).

```bash
curl -sk https://$(grep '^RAG_FQDN=' .env | cut -d= -f2)/sante
```

**Attendu :** `{"status":"ok"}` (avec `-k`, le certificat n'est pas vérifié ; contrôle complet à l'étape 16).

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
pip install --retries 10 --timeout 60 qdrant-client python-docx pdfplumber python-pptx httpx \
    ldap3 impacket smbprotocol
```

Les huit paquets sont tous nécessaires : sans `smbprotocol`, par exemple, la synchronisation échoue au premier import. `rank-bm25` n'en fait plus partie depuis la 2.23.0 : la recherche par mots-clés se fait dans Qdrant.

Tester ensuite les deux accès de `svc-rag`, à l'annuaire et au partage :

```bash
set -a && source /root/rag-stack/.env && set +a

LDAPTLS_CACERT=/etc/ssl/certs/ad-chain.pem \
    ldapwhoami -H ldaps://${LDAP_HOST}:${LDAP_PORT} -D "${LDAP_BIND_DN}" -w "${LDAP_BIND_PWD}" 2>&1
smbclient //<NOM-FILESERVER>/<PARTAGE> -W "${SMB_DOMAIN}" -U "svc-rag%${SMB_PASSWORD}" -c "ls" 2>&1 | head -10
```

**Attendu :** `dn:CN=svc-rag,...`, puis la liste des dossiers du partage. Sur un domaine Active Directory, `smbclient` exige `-W <DOMAINE>` : sans lui, l'erreur est `NT_STATUS_LOGON_FAILURE` alors que le mot de passe est correct.

---

## Étape 12 : première indexation des documents

L'indexeur lit chaque document du partage, le découpe en extraits, calcule leurs vecteurs avec le modèle d'embedding, et les range dans Qdrant.

```bash
cd /root/rag-pipeline && source .venv/bin/activate
set -a && source /root/rag-stack/.env && set +a

python indexer.py --corpus /mnt/corpus-root --rapport /var/log/rag/rapport_indexation_initial.json
echo "Code de sortie : $?"
```

**Attendu :** au début, `Vérification du serveur d'embedding (ollama)`, ou `(openai)` avec vLLM, puis `Modèle d'embedding : bge-m3 ✓ (calcul vérifié)` ; à la fin, le code de sortie `0`. Le code `2` signale au moins un fichier en erreur, listé en fin de sortie et dans le rapport (voir ci-dessous). Compter les extraits indexés :

```bash
for c in documents documentation; do
    curl -s -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections/$c | \
        python3 -c "import sys,json; print('$c :', json.load(sys.stdin)['result']['points_count'])"
done
```

> **Les variables du `.env` restent chargées dans ce shell.** Si le `.env` est modifié ensuite, `docker compose` prend les valeurs du shell, pas celles du fichier : le changement semble sans effet (constaté en lab). Ouvrir une nouvelle session avant tout `docker compose` qui doit lire un `.env` modifié.

> **Quarantaine :** un fichier dont l'organisation propriétaire (client ou organisation interne) n'est pas identifiable est mis en quarantaine et n'est pas indexé ; il apparaît dans le rapport avec le statut `quarantaine`. Un PDF sans texte extractible (scanné, par exemple) ne produit aucun extrait (statut `vide`). Un fichier illisible ou abîmé est compté en erreur (statut `erreur`, code de sortie 2) ; s'il était déjà indexé, ses anciens extraits restent en place (§5.4.2b).

---

## Étape 13 : synchronisation des droits d'accès

L'outil de résolution des ACL recopie, dans chaque extrait indexé, la liste des groupes et des comptes autorisés à ouvrir son document. C'est ce qui permet ensuite de ne montrer à chacun que ses documents.

```bash
python acl_resolver.py \
    --share //<NOM-FILESERVER>/<PARTAGE> \
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

**Activer la recherche par mots-clés** (2.23.0). La RAG API crée l'index plein texte de chaque collection à son démarrage et après chaque synchronisation par `/admin/sync`. Elle a démarré avant cette première indexation, quand les collections n'existaient pas : la redémarrer, sinon la recherche par mots-clés reste inactive jusqu'à la première synchronisation n8n, sans message (constaté au rejeu du 1er novembre 2026). `deploy.sh` le fait lui-même après l'indexation qu'il propose.

```bash
cd /root/rag-stack && docker compose restart rag-api && sleep 15 && docker logs rag-api 2>&1 | grep "\[BM25\]" | tail -3
```

**Attendu :** `Index plein texte créé` pour chaque collection, puis `Recherche par mots-clés dans Qdrant : documentation, documents`.

---

## Étape 14 : configurer Open WebUI

Ouvrir `https://<RAG_FQDN>` (par exemple `https://rag.votre-domaine.ch`) depuis un poste du réseau. Le premier compte créé devient administrateur. Avec le certificat auto-signé, le navigateur affiche un avertissement : l'accepter pour ce poste, en sachant que tous les utilisateurs le verront jusqu'au remplacement du certificat (§9.8.6). Par l'adresse IP, la connexion est refusée : c'est voulu (§9.8.7).

**Raccorder la RAG API :**

1. *Settings → Admin → Connections*, section **API compatibles OpenAI** (et non la section Ollama, même si le moteur est Ollama : la RAG API parle le protocole OpenAI) → *+*
2. URL : `http://rag-api:8080/v1`
3. Clé API : la valeur de `API_TOKEN` du `.env` (`grep ^API_TOKEN /root/rag-stack/.env`)
4. Enregistrer : le modèle `rag-api` apparaît dans la liste. Une erreur de connexion à cette étape vient presque toujours d'une adresse ou d'une clé erronée, ou d'une connexion créée dans la mauvaise section.

**Authentification par l'Active Directory** (facultative en lab, obligatoire en production) : *Settings → Admin → Authentication → LDAP*, activer LDAP, puis remplir les champs. Open WebUI affiche leurs libellés dans la langue de l'interface ; la deuxième colonne donne ceux de l'interface en français (fichier de traduction de la version 0.11.3).

| Champ (interface en anglais) | Libellé en français | Valeur |
|---|---|---|
| Label | Étiquette | Un nom libre, par exemple `Active Directory` |
| Host | Hôte | `<NOM-DC>.votre-domaine.ch`, port `636`, TLS activé |
| Attribute for Mail | Attribut pour l'e-mail | `userPrincipalName` |
| Attribute for Username | Attribut pour le nom d'utilisateur | `sAMAccountName` |
| Application DN | DN de l'application | `CN=svc-rag,OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch` |
| Application DN Password | Mot de passe DN de l'application | Le mot de passe de `svc-rag` |
| Search Base | Base de recherche | `DC=votre-domaine,DC=ch` |
| Search Filters | Filtres de recherche | `(objectClass=user)`, **avec les parenthèses** : sans elles, la connexion échoue (constaté au rejeu du 1er novembre 2026) |
| Certificate Path | Chemin du certificat | `/etc/ssl/certs/ad-chain.pem` |
| Validate Certificate | Validate Certificate (non traduit) | Activé : la chaîne de l'étape 4D permet la validation (le §5.6.2 décrit le cas d'un lab sans certificat) |
| Ciphers | Chiffres | Valeur par défaut |

> **L'attribut du courriel doit être `userPrincipalName`.** Open WebUI transmet l'adresse de l'utilisateur à la RAG API, qui la cherche dans ce champ de l'annuaire. Avec un autre attribut, la recherche échoue et tout le monde est refusé (403). L'attribut du **nom d'utilisateur** est celui que la personne tape pour se connecter : `sAMAccountName` permet de saisir `blaise` plutôt que `blaise@votre-domaine.ch`.

**Rendre le modèle accessible :** *Settings → Admin → Models → rag-api → Make Public*, puis enregistrer.

**Les tâches automatiques d'Open WebUI** (titres, étiquettes, questions de suivi) interrogent le modèle de la conversation, donc `rag-api` : une seule question de l'utilisateur déclenchait quatre appels dans le lab (un pour le titre, trois pour les suggestions), chacun avec sa recherche complète et son entrée dans le journal nLPD (§14.8.2). Le `docker-compose.yml` du dépôt les désactive (`ENABLE_TITLE_GENERATION`, `ENABLE_TAGS_GENERATION`, `ENABLE_FOLLOW_UP_GENERATION` à `false`). Ces variables ne fixent que l'**état initial** : Open WebUI les recopie dans sa base au premier démarrage, puis la base décide. Si la base existe déjà (Open WebUI démarré avant ce réglage), le faire une fois dans l'interface : *Settings → Admin → Interface*, désactiver les trois générations, et **enregistrer**.

> **Réglages d'administration et réglages personnels sont distincts.** Chaque utilisateur dispose aussi, dans ses propres paramètres (menu de son compte), d'une rubrique *Interface* avec des options de titre, d'étiquettes et de suggestions de suivi. Elles ne remplacent pas le réglage d'administration : dans le lab, les modifier n'a rien changé au nombre d'appels. Le seul réglage qui compte est celui de *Settings → Admin → Interface*, vérifié par le contrôle ci-dessous.

**Contrôle de la base :**

```bash
docker exec -i open-webui python3 - <<'PYEOF'
import sqlite3
c = sqlite3.connect('/app/backend/data/webui.db')
for k, v, _ in c.execute("select * from config where key in ('task.title.enable','task.tags.enable','task.follow_up.enable','task.autocomplete.enable')"):
    print(k, v)
PYEOF
```

**Attendu :** `false` aux quatre lignes. Puis poser une question et comparer `wc -l /var/log/rag/rag-queries.jsonl` avant et après : une seule ligne ajoutée par question.

---

## Étape 15 : configurer n8n

n8n lance la synchronisation du corpus toutes les heures, et rappelle chaque mois la rotation du mot de passe de `svc-rag`. Ouvrir `https://<RAG_FQDN>:5678` **sans attendre** : la première ouverture crée le compte propriétaire de n8n, et tant qu'il n'existe pas, n'importe qui joignant l'adresse peut le créer (§7.1.1). Mot de passe fort, conservé dans le gestionnaire de mots de passe de l'organisation. Si la page ne répond pas et que `docker logs n8n` montre `EACCES: permission denied`, le dossier `n8n_data` n'appartient pas à l'utilisateur 1000 : corriger par `chown -R 1000:1000 "$(readlink -f /root/rag-stack/n8n_data)"` puis `docker compose up -d n8n`. `deploy.sh` et l'étape 6 le font déjà.

**1. Créer les deux identifiants** (*Credentials → Add credential*). Le jeton d'administration n'est écrit dans aucun workflow : il reste dans l'identifiant (§16.7).

| Identifiant | Type | Réglages |
|---|---|---|
| `RAG API - ADMIN_TOKEN` | **Header Auth** | *Name* : `Authorization` ; *Value* : `Bearer ` suivi de la valeur de `ADMIN_TOKEN` du `.env` (`grep ^ADMIN_TOKEN /root/rag-stack/.env`) ; domaines autorisés : *Specific Domains*, `rag-api` |
| Compte d'envoi des courriels | **SMTP** | Serveur, port, utilisateur et mot de passe de la boîte d'envoi ; *SSL/TLS* désactivé avec le port 587 (STARTTLS), *Disable STARTTLS* désactivé, *Client Host Name* vide |

Restreindre `RAG API - ADMIN_TOKEN` au domaine `rag-api` empêche n8n d'envoyer le jeton à une autre adresse, par exemple dans un workflow modifié par erreur. Avec Exchange Online, le serveur est `smtp.office365.com`, port 587, et l'authentification SMTP doit être autorisée pour la boîte d'envoi.

**2. Importer les deux workflows** du dossier `scripts/N8N/` du dépôt (*Import from File*) : `n8n-sync-corpus.json` et `n8n-rappel-rotation-svc-rag.json`.

**3. Rattacher les identifiants dans chaque nœud.** Les identifiants référencés dans les fichiers importés n'existent pas chez vous : n8n affiche *Credentials not found* ou laisse le champ vide. Ouvrir **chaque** nœud concerné et y sélectionner l'identifiant créé à l'étape 1 : le nœud « POST /admin/sync » (*Authentication* : *Generic Credential Type*, *Header Auth*, `RAG API - ADMIN_TOKEN`), et chaque nœud de courriel (identifiant SMTP).

**4. Renseigner les adresses** dans chaque nœud de courriel, à la place de `<EMAIL_EXPEDITEUR>` et `<EMAIL_DESTINATAIRE>` :
- **Expéditeur** : exactement la boîte authentifiée par l'identifiant SMTP. Avec Exchange Online, une autre adresse est refusée (`554 5.2.252 SendAsDenied`).
- **Destinataire** : une boîte **interne** à l'organisation. Les alertes citent des noms de fichiers et des comptes : elles ne sortent pas de l'organisation.

**5. Vérifier le nœud « POST /admin/sync »** : URL `http://rag-api:8080/admin/sync`, méthode POST, authentification par l'identifiant `RAG API - ADMIN_TOKEN`. Aucun jeton n'est à recopier dans le nœud.

**6. Publier les deux workflows**, puis lancer une exécution manuelle de la synchronisation :

```bash
docker logs rag-api 2>&1 | grep "\[SYNC\]" | tail -10
```

**Attendu :** `[SYNC] Terminé : success=True`. Le courriel de la synchronisation ne part qu'en cas d'erreur, de quarantaine ou d'alerte de cloisonnement. Pour tester son envoi sans provoquer de panne : épingler des données d'erreur sur le nœud « POST /admin/sync » (*Pin data*, avec par exemple `"success": false`), lancer le workflow, vérifier la réception, puis **retirer l'épingle** avant de publier. Modifier la sortie d'un nœud en aval (*Set mock data*) ne teste rien : le nœud de courriel suivant reçoit toujours les données réelles.

**7. Facultatif : le signal de supervision.** Si l'organisation surveille la stack depuis une autre machine (§16.10), le nœud « Signal supervision (Push) » du workflow de synchronisation, désactivé à l'import, prévient l'outil après chaque synchronisation. Remplacer `<NOM-COMPLET-SUPERVISION>` et `<CLE-PUSH>` dans son URL, l'activer, publier. Le nom de la machine de supervision doit être un nom DNS **complet** : le conteneur n8n ne résout pas les noms courts.

> **Une synchronisation occupe la stack et le serveur de modèles.** Tant qu'elle tourne, les réponses sont nettement plus lentes : dans le lab, trois à cinq fois plus lentes pendant une synchronisation lancée juste avant une série de questions (§10.3). Ne pas juger la vitesse de la stack à ce moment-là.

---

## Étape 16 : contrôles finaux

**Une question de test**, dans Open WebUI, sur un document que vous connaissez : la réponse doit le citer entre crochets.

**Le test de cloisonnement**, qui prouve que chacun ne voit que ses documents. Il demande quelques comptes de test créés dans l'Active Directory, et un fichier qui décrit, pour quelques documents, qui doit y avoir accès : partir de `cas_cloisonnement.exemple.json`, l'adapter à vos documents et le copier en `/root/rag-pipeline/cas_cloisonnement.json` (format au §16.3). Puis :

```bash
docker exec rag-api python3 /rag-pipeline/test_cloisonnement.py /rag-pipeline/cas_cloisonnement.json
```

**Attendu :** uniquement des `OK`, et en aucun cas une `FUITE`. Une fois ce fichier en place, la RAG API rejoue ces cas après chaque synchronisation (§16.4). Ce test vérifie les **droits** (le filtre sur les groupes, les refus nominatifs, Purview), pas la réponse du modèle : il dure quelques secondes. Dans le lab, au rejeu du 1er novembre 2026 : 207 verdicts sur 23 cas et 9 comptes, tous `OK`, aucune `FUITE` (§16.3).

> **Le test du garde-fou ne doit pas verrouiller `svc-rag`.** Le contrôle « Garde-fou des droits » ci-dessous désigne un partage qui n'existe pas : le compte s'authentifie normalement, chaque lecture échoue, et le garde-fou doit abandonner sans toucher à Qdrant. Ne pas le tester avec un mot de passe faux : chaque essai compte dans le seuil de verrouillage de l'Active Directory, et un compte `svc-rag` verrouillé bloque la connexion de tous les utilisateurs (cas vécu dans le lab, avant la 2.20.4 qui arrête `acl_resolver.py` au premier refus d'authentification). Déverrouillage, sur un contrôleur de domaine : `Unlock-ADAccount -Identity svc-rag`. Validé lors du rejeu du 19 octobre 2026 : `[GARDE-FOU] 70/70 fichiers en ACL illisible, abandon sans modification`, code 1, Qdrant intact, compte non verrouillé.

**Le frontal HTTPS et l'identité signée** (§9.8, §16.6), sur la VM :

```bash
FQDN=$(grep '^RAG_FQDN=' /root/rag-stack/.env | cut -d= -f2)
# Certificat de l'autorité interne ; avec l'auto-signé, remplacer --cacert ... par -k
curl --cacert /etc/ssl/certs/ad-chain.pem https://${FQDN}/sante; echo
# Par l'adresse IP : refusé
curl -sk https://<IP-VM>/; echo "code $?"
```

**Attendu :** `{"status":"ok"}`, puis `code 35`. Puis le contrôle d'usurpation de §16.6 : une identité transmise sans signature est refusée (`HTTP Error 403`). Depuis un autre poste, seuls les ports 80, 443 et 5678 doivent répondre (§9.8.8).

**Avant la mise en service : un snapshot de la VM arrêtée**, une fois tous les contrôles passés. Arrêter la VM (`shutdown -h now`) avant le snapshot : un snapshot à chaud d'une VM dont le disque est chiffré et où tourne une base de données peut être incohérent. Prendre ensuite un snapshot Qdrant et le copier hors de la VM (§3.7).

### Checklist

| Contrôle | Commande ou action | Attendu |
|---|---|---|
| Volume chiffré et TPM | `findmnt /srv/rag-donnees` et le contrôle de l'étape 4C, point 4 | Monté depuis `/dev/mapper/rag-donnees` ; deux `luks2`, un `systemd-tpm2` |
| Serveur de modèles, depuis la stack | Étape 10 | `200` deux fois |
| Collections Qdrant | `curl -s -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections` | `documents` et `documentation` |
| Extraits indexés | Étape 12 | Plus de 0 dans les deux collections |
| Droits recopiés | Étape 13 | `autorises` non vide |
| Santé de la RAG API | `docker compose exec n8n wget -qO- http://rag-api:8080/health` | `"status":"ok"` |
| Frontal HTTPS | `curl --cacert /etc/ssl/certs/ad-chain.pem https://<RAG_FQDN>/sante` | `{"status":"ok"}` (auto-signé : `-k`) |
| Refus par adresse IP | `curl -sk https://<IP-VM>/; echo $?` | `35` |
| Identité signée | Contrôle d'usurpation (§16.6) | `HTTP Error 403` |
| Ports exposés | `docker compose ps` | `nginx` : 80, 443, 5678 ; `qdrant` : `127.0.0.1:6333` seulement |
| Contrôle des citations | `docker exec -w /app rag-api python3 /rag-pipeline/test_citations.py` | `28 tests OK` |
| Droits par SID | `docker exec -w /app rag-api python3 /rag-pipeline/test_sid.py` | `32 tests OK` |
| Droits et recherche par mots-clés | `docker exec -w /app rag-api python3 /rag-pipeline/test_revalidation_bm25.py` | `27 tests OK` |
| Échecs d'écriture des droits, indexation | `docker exec -w /app rag-api python3 /rag-pipeline/test_echec_droits.py` | `56 tests OK` |
| Reclassement (reranker) | `docker exec -w /app rag-api python3 /rag-pipeline/test_reranker.py` | `6 tests OK` |
| Reranker, si activé (étape 17) | Une question, puis `docker logs rag-api --since 5m 2>&1 \| grep RERANK` | `[RERANK] N extraits reclassés`, aucun `Échec` |
| SID d'un compte | `docker exec -w /app rag-api python3 /rag-pipeline/diag_sid.py <compte>` | `Lecture de tokenGroups : OK` (§16.5.3) |
| Recherche par mots-clés | `docker logs rag-api \| grep BM25` | `Recherche par mots-clés dans Qdrant : documentation, documents` (après le redémarrage de l'étape 13) |
| Accès autorisé | Question sur un document accessible | Réponse avec citation |
| Accès refusé | Compte sans droit, question sur un document restreint | « Cette information ne figure pas... » |
| Test de cloisonnement | Étape 16 | Aucune `FUITE` |
| Journal nLPD | `tail -1 /var/log/rag/rag-queries.jsonl` | Une entrée avec `user_id` et `ancree` |
| Synchronisation horaire | n8n, dernière exécution | Réussie |
| Échéance du certificat | `openssl x509 -in /etc/rag-tls/rag.crt -noout -enddate` | Notée au calendrier des rotations (§17.3) |
| Garde-fou des droits | `python acl_resolver.py --share //<NOM-FILESERVER>/PartageInexistant --mount /mnt/corpus-root --rapport /var/log/rag/rapport_acl_gardefou.json` | Code 1, `[GARDE-FOU]`, Qdrant intact |
| Lecture du partage | `.\Set-AccesIndexationRAG.ps1 ... -Verifier` | 0 fichier sans lecture |
| Avec vLLM : la clé est exigée | Étape 3B, point 5 | `401` sans la clé |
| Redémarrage complet | `reboot`, puis §15.3.5 et `getent hosts <NOM-DC>.votre-domaine.ch <NOM-FILESERVER>` | Disque ouvert sans saisie, conteneurs `Up`, les deux noms résolus |
| Sauvegarde | Snapshot de la VM arrêtée, puis snapshots Qdrant copiés hors de `qdrant_data` (§3.7) | Fichiers `.snapshot` présents dans la copie |
| Microsoft 365, si déployé | Checklists de §11.8, §12.9 et §13.9 | Tous les points validés |

---

## Étape 17 (facultative) : le reranker

Le reranker reclasse les extraits trouvés par la recherche avant que le modèle rédige la réponse. Dans le lab, avec Ollama, `bge-m3` et `qwen3:14b` : **83 réponses conformes sur 105 au lieu de 76, plus aucun élément interdit, 0,2 seconde par question** (§10.8, rejeu du 1er novembre 2026). Il tourne sur la carte du serveur de modèles, à côté d'Ollama, et occupe environ 0,7 Go : vérifier d'abord que les modèles d'Ollama restent à `100% GPU` (`ollama ps`). Sans lui, la stack fonctionne : la RAG API garde l'ordre de la recherche.

Le serveur est `llama-server`, de llama.cpp, avec le modèle `bge-reranker-v2-m3` converti au format GGUF dans le lab, pour connaître l'origine du fichier. Les explications de chaque choix sont au §10.8.

> **Avec vLLM**, le reranker est un troisième serveur vLLM sur la carte (port 8002), et la part de mémoire du modèle principal passe de 0,87 à 0,82 : commande et réglages au §10.8, « Avec vLLM : un troisième serveur sur la carte ». Validé dans le lab à la limite d'une carte de 16 Go (37 Mio libres) : en service, prévoir une carte plus grande. Le reste de cette étape concerne Ollama.

**1. Installer `llama-server`**, sur le serveur de modèles. Depuis la page de la version b11934 de llama.cpp ([github.com/ggml-org/llama.cpp/releases/tag/b11934](https://github.com/ggml-org/llama.cpp/releases/tag/b11934)), télécharger `llama-b11934-bin-win-cuda-13.4-x64.zip` et `cudart-llama-bin-win-cuda-13.4-x64.zip`, version utilisée dans le lab. Contrôler leurs empreintes SHA-256 (`Get-FileHash <fichier>`) avec celles publiées sur la page de la version, puis extraire les deux archives dans `C:\IA\llama.cpp`, et créer le dossier du reranker :

```powershell
New-Item -ItemType Directory -Force C:\IA\reranker | Out-Null; Test-Path C:\IA\llama.cpp\llama-server.exe
```

**Attendu :** `True`.

**2. Convertir le modèle**, une seule fois, dans Ubuntu sous WSL2. Avec vLLM, c'est celui de l'étape 3B. Avec Ollama seul, installer WSL2 comme à l'étape 3B, point 1 (la règle de pare-feu de vLLM n'est pas nécessaire), puis `uv` comme au point 2 (`curl -LsSf https://astral.sh/uv/install.sh | sh` et `source ~/.local/bin/env`). Le convertisseur de llama.cpp, à un commit figé, dans un environnement Python à part :

```bash
sudo mkdir -p /opt/llama.cpp-conv && sudo chown $USER /opt/llama.cpp-conv && git clone -q https://github.com/ggml-org/llama.cpp /opt/llama.cpp-conv/src && cd /opt/llama.cpp-conv/src && git checkout -q 9ff0d7e90 && uv venv -q --python 3.12 --seed /opt/llama.cpp-conv/.venv && uv pip install -q --python /opt/llama.cpp-conv/.venv/bin/python -r requirements/requirements-convert_hf_to_gguf.txt
```

Puis, depuis `/opt/llama.cpp-conv/src`, le téléchargement du modèle, la conversion en Q8 et la copie vers Windows :

```bash
sudo mkdir -p /opt/hf && sudo chown $USER /opt/hf && HF_HOME=/opt/hf /opt/vllm/.venv/bin/hf download BAAI/bge-reranker-v2-m3 --exclude "onnx/*" && D=$(ls -d /opt/hf/hub/models--BAAI--bge-reranker-v2-m3/snapshots/*) && mkdir -p /opt/hf/gguf && /opt/llama.cpp-conv/.venv/bin/python convert_hf_to_gguf.py "$D" --outtype q8_0 --outfile /opt/hf/gguf/bge-reranker-v2-m3-q8_0.gguf && sha256sum /opt/hf/gguf/bge-reranker-v2-m3-q8_0.gguf && cp /opt/hf/gguf/bge-reranker-v2-m3-q8_0.gguf /mnt/c/IA/reranker/
```

**Attendu :** un fichier de 636 Mo ; dans le lab, révision `953dc6f6` du dépôt du modèle et empreinte `a525387ce1faf3d7a31f60120f064d0f53e994304f5da36cfa56cbc0b4607ff7`. La commande utilise l'outil `hf` installé avec vLLM. **Sans vLLM** (non rejoué dans le lab), l'installer dans l'environnement de conversion, `uv pip install -q --python /opt/llama.cpp-conv/.venv/bin/python huggingface_hub`, et remplacer `/opt/vllm/.venv/bin/hf` par `/opt/llama.cpp-conv/.venv/bin/hf`.

**3. Créer la clé et ouvrir le port**, dans PowerShell en administrateur, **avec le compte qui fait tourner Ollama**. La clé (64 caractères aléatoires) est écrite dans un fichier lisible par ce seul compte ; `llama-server` la reçoit par une variable, et elle n'apparaît pas dans la ligne de commande du processus :

```powershell
$k = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'); Set-Content -Path C:\IA\reranker\cle.txt -Value $k -NoNewline; icacls C:\IA\reranker\cle.txt /inheritance:r /grant:r "$($env:USERNAME):R" | Out-Null; Remove-Variable k
New-NetFirewallRule -DisplayName 'Reranker llama-server (lab)' -Direction Inbound -Protocol TCP -LocalPort 8091 -RemoteAddress <IP-VM-STACK> -Action Allow
```

`<IP-VM-STACK>` est l'adresse de la VM **telle que le serveur de modèles la voit** : derrière un routeur qui traduit les adresses, c'est celle du routeur (§16.7). La clé ne s'affiche jamais : ne pas la coller dans un message ou un ticket.

**4. Le démarrage automatique.** Copier `demarrer-reranker.ps1`, fourni dans le dépôt (`scripts/stack-ia-locale/reranker/`), dans `C:\IA\reranker`. Il lit la clé, puis lance `llama-server` sur le port 8091, avec le modèle sur la carte. La tâche planifiée le lance à l'ouverture de session, comme Ollama, sans fenêtre :

```powershell
$a = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument '--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\IA\reranker\demarrer-reranker.ps1'; $t = New-ScheduledTaskTrigger -AtLogOn -User "$env:COMPUTERNAME\$env:USERNAME"; $s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries; Register-ScheduledTask -TaskName 'Reranker llama-server (lab)' -Description 'bge-reranker-v2-m3 sur la carte, port 8091 (§10.8)' -Action $a -Trigger $t -Settings $s
Start-ScheduledTask -TaskName 'Reranker llama-server (lab)'
```

**Attendu :** après quelques secondes, `llama-server.exe` dans `nvidia-smi`, et la ligne `listening on http://0.0.0.0:8091` dans `C:\IA\reranker\reranker.log`. Comme Ollama, le serveur s'arrête quand la session Windows est **fermée** et repart seul à sa réouverture (vérifié dans le lab : à l'écoute 2,5 secondes après l'ouverture de session). Arrêt, redémarrage et changement de clé : §10.8.

**5. Activer le reranker dans la stack**, sur la VM. Relire la clé sur le serveur de modèles, depuis le même compte (`Get-Content C:\IA\reranker\cle.txt`), puis ouvrir le vrai fichier `.env` :

```bash
nano /srv/rag-donnees/secrets/.env
```

Dans le bloc « Reranker optionnel », ajouter ces trois lignes, sans `#` devant :

```
RERANKER_URL=http://<IP-SERVEUR-MODELES>:8091
RERANKER_API=llamacpp
RERANKER_API_KEY=<clé lue à l'instant>
```

Puis recréer la RAG API, qui relit le `.env` :

```bash
cd /root/rag-stack && docker compose up -d rag-api
```

**6. Vérifier.** Poser une question dans Open WebUI, puis, sur la VM :

```bash
docker logs rag-api --since 5m 2>&1 | grep RERANK
docker exec -w /app rag-api python3 /rag-pipeline/test_reranker.py
```

**Attendu :** une ligne `[RERANK] N extraits reclassés (fusion) en 0.2 s, premier : '…'` par question, puis `6 tests OK`. Une ligne `[RERANK] Échec, ordre de la recherche conservé` signale un reranker injoignable ou une clé refusée : la question est servie quand même, sans reclassement. Contrôler alors la tâche planifiée, la règle de pare-feu et la clé. Le Compose reclasse les 20 meilleurs candidats et fusionne les deux classements (`RERANK_CANDIDATS=20`, `RERANK_MODE=fusion`), les réglages des mesures du §10.8.

---

## Étape 18 (facultative) : Microsoft 365

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

### 18.1 Groupes Entra ID (§11), prérequis des modules suivants

1. Certificat `rag-identity` ;
2. App Registration `RAG-Identity-Resolver` : certificat chargé, autorisations **d'application** Microsoft Graph `User.Read.All` et `GroupMember.Read.All`, consentement administrateur ;
3. `.env` : `ENTRA_ENABLED=true`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CERT_THUMBPRINT` (chemins par défaut conservés) ;
4. Validation : après une question dans Open WebUI, `docker logs rag-api 2>&1 | grep "\[AUTH\] Entra"` affiche le nombre d'identifiants Entra de l'utilisateur.

Détail : [§11 Prérequis Microsoft 365](section-11-prerequis-ms365.md).

### 18.2 Synthèse des réunions Teams (§12)

1. Centre d'administration Teams : transcription active dans la stratégie de réunion, et **Transcript API access** activé avec l'attribution des intervenants (désactivé par défaut : sans lui, toute requête est refusée) ;
2. Groupe d'adhésion `GRP-Teams-CompteRendu-IA`, de type sécurité à extension messagerie, créé en PowerShell Exchange Online, avec les organisateurs concernés ;
3. Certificat `rag-teams` et App Registration `RAG-Teams-Reader` : autorisation d'application `OnlineMeetingTranscript.Read.All`, consentement ;
4. Stratégie d'accès applicatif Teams attribuée au groupe (`New-CsApplicationAccessPolicy`, puis `Grant-CsApplicationAccessPolicy -Group <ID-objet-du-groupe>`) ;
5. `.env` : `TEAMS_CLIENT_ID`, `TEAMS_CERT_THUMBPRINT`, `TEAMS_GROUP_ID` ;
6. n8n : importer `n8n-teams-sync.json`, expéditeur = compte SMTP authentifié ;
7. Validation : `docker exec -e PYTHONPATH=/app -w /app rag-api python3 /rag-pipeline/test_teams_graph.py` (script de [`scripts/teams-test/`](../../scripts/teams-test/), copié dans `/root/rag-pipeline`).

Détail : [§12 Synthèse des réunions Teams](section-12-teams.md).

### 18.3 Connecteur SharePoint Online (§13)

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

Causes : mot de passe de `svc-rag` erroné ou changé, compte verrouillé, certificat de l'autorité de certification incorrect, attribut LDAP d'Open WebUI autre que `userPrincipalName`, ou nom du contrôleur de domaine qui ne se résout plus (DNS public dans la configuration de la VM, voir plus bas).

**Tout fonctionnait, puis tout le monde est refusé après un redémarrage, et la synchronisation échoue**

Journal de `rag-api` : `Erreur LDAP ... invalid server address` ; synchronisation : `NT_STATUS_INVALID_PARAMETER` sur chaque fichier, ou le garde-fou qui signale un nom de serveur introuvable. Les noms du domaine ne se résolvent plus :

```bash
resolvectl status | grep -E "Current DNS Server|DNS Servers"
getent hosts <NOM-DC>.votre-domaine.ch <NOM-FILESERVER>
```

Si `Current DNS Server` est un DNS public, le retirer de la configuration réseau (étape 4D). Le partage peut rester monté et lisible : il a été monté au démarrage, par son adresse ; ce sont les connexions suivantes, par le nom, qui échouent.

**Le compte `svc-rag` est verrouillé**

Journal : `NT_STATUS_ACCOUNT_LOCKED_OUT`, ou `[GARDE-FOU] Authentification refusée`. Le plus souvent, un mot de passe changé dans l'Active Directory et pas sur la VM (rotation, §9.5.1). Corriger le `.env` et le fichier de l'étape 5, puis déverrouiller sur un contrôleur de domaine :

```powershell
Unlock-ADAccount -Identity svc-rag
Get-ADUser svc-rag -Properties LockedOut,BadLogonCount | Select-Object LockedOut,BadLogonCount
```

**`deploy.sh` ou l'étape 11 s'arrête sur un délai dépassé pendant l'installation des paquets Python**

Coupure passagère vers `pypi.org`. Relancer `deploy.sh` : il signale le `.env` du premier essai et demande de le remplacer ; répondre **o**, puisque ni Open WebUI ni n8n ne sont encore configurés. L'installation essaie désormais dix fois avant d'abandonner. Si l'échec se répète, tester l'accès en IPv4 puis en IPv6 : `curl -4 -sS -o /dev/null -w "%{http_code}\n" https://pypi.org/simple/`, puis la même chose avec `-6`. **Ne pas ajouter de DNS public pour contourner** : c'est la cause de la panne décrite plus haut.

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

Le serveur d'embedding ne répond pas : sans vecteur de la question, pas de recherche. Avec vLLM, le serveur du port 8001 est arrêté (son terminal a été fermé, par exemple) ; avec Ollama, le modèle `bge-m3` manque (`ollama pull bge-m3`).

**vLLM refuse de démarrer**

Les messages rencontrés en lab et leur solution sont au §2.4.9.

**Les réponses sont soudain très lentes**

Une synchronisation est peut-être en cours (`docker logs rag-api 2>&1 | grep "\[SYNC\]" | tail -3`). Si les lenteurs persistent au repos : la mémoire de la carte déborde (§10.2).

**n8n redémarre en boucle (`EACCES: permission denied`)**

Le dossier `n8n_data` n'appartient pas à l'utilisateur 1000, sous lequel tourne n8n. Avec le disque chiffré, c'est le dossier réel qu'il faut corriger, pas le lien :

```bash
chown -R 1000:1000 "$(readlink -f /root/rag-stack/n8n_data)"
cd /root/rag-stack && docker compose up -d n8n
```

**`source .env` répond « command not found »**

Une valeur du `.env` contient un espace sans apostrophes (`SP_EXCLUDE_DRIVES` le plus souvent). Mettre la valeur entre apostrophes, comme dans `env.example`.

**Une modification du `.env` n'est pas prise en compte**

`docker compose restart` ne relit pas le `.env`. Utiliser `docker compose up -d <service>`, qui recrée le conteneur.

**La RAG API ne répond pas aux contrôles de santé depuis la VM**

Son port 8080 n'est pas publié sur le réseau : tester depuis l'intérieur de Docker.

```bash
docker exec rag-api python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/health', timeout=5).read().decode())"
```

**`smbclient` : `NT_STATUS_LOGON_FAILURE` avec un mot de passe correct**

Ajouter le domaine : `smbclient //<NOM-FILESERVER>/<PARTAGE> -W <DOMAINE> -U "svc-rag%<mot-de-passe>"`.

**Le montage du partage tombe après un redémarrage**

```bash
mount -a && mount | grep corpus-root
```

Vérifier le mot de passe dans `/etc/smbcredentials/svc-rag` (rotation non reportée ?) et la ligne de `/etc/fstab`.

**La recherche par mots-clés est vide au démarrage (BM25)**

Avant la première indexation, les collections n'existent pas : aucune ligne `Recherche par mots-clés dans Qdrant`, ce qui est normal. La RAG API crée l'index plein texte de chaque collection à son démarrage et après chaque synchronisation (`/admin/sync`) : après une première indexation lancée à la main, il faut donc la redémarrer (étape 13). Si la ligne manque alors que Qdrant contient des extraits, ou si le journal signale une version de Qdrant antérieure à la 1.20 ou un index indisponible, la recherche se fait en vectoriel seul. Vérifier la version de Qdrant (§3.4), attendre 30 secondes, puis :

```bash
cd /root/rag-stack && docker compose restart rag-api
docker logs rag-api 2>&1 | grep BM25
```

**Le garde-fou des droits s'est déclenché (code 1)**

Plus de 20 % des fichiers étaient illisibles : le résolveur refuse alors de toucher à Qdrant. Vérifier que `svc-rag` n'est pas verrouillé (sur Windows : `Get-ADUser svc-rag -Properties LockedOut`, puis `Unlock-ADAccount -Identity svc-rag`), que le partage est monté (`ls /mnt/corpus-root`), et que le contrôleur de domaine répond (`ldapwhoami`, ci-dessus).

---

[Retour au sommaire](index.md) | [Section suivante : §1 Prérequis et création de la VM](section-01-prerequis.md)

---

*Validé en lab sur VM-RAG-LAB (Ubuntu Server 26.04) et LABO-G9 (NVIDIA RTX 5060 Ti 16 Go), avec Ollama puis vLLM 0.31.0, octobre 2026. Rejoué sur une VM neuve le 1er novembre 2026 (2.23.0) ; étape 4 complétée en novembre 2026 (2.23.1).*

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
