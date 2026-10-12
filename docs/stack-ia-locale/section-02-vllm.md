---
title: "§2 Le serveur de modèles : Ollama ou vLLM | Guide de déploiement stack IA locale"
description: "Choisir et installer le moteur qui fait tourner les modèles d'IA de la stack : Ollama pour un à deux utilisateurs simultanés, vLLM pour plusieurs. Installation, réglages, vérifications et pièges rencontrés en lab."
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

# §2 Le serveur de modèles : Ollama ou vLLM

[Retour au sommaire](index.md) | [Section précédente : §1 Prérequis et création de la VM](section-01-prerequis.md) | [Section suivante : §3 Docker Compose : stack complète](section-03-docker-compose.md)

**Statut :** validé en lab, octobre 2026, sur une carte NVIDIA RTX 5060 Ti 16 Go. Ollama : validé sous Windows, puis sous Linux dans WSL2. vLLM 0.31.0 : validé dans WSL2 (Ubuntu 26.04), avec le jeu de questions, le test de cloisonnement (44 sur 44) et deux campagnes de questions simultanées. Services systemd (§2.4.7) : validés dans WSL2. **Non validés :** un serveur Linux dédié, le DGX Spark (§2.6), le démarrage de WSL2 au lancement de Windows sans session ouverte.

---

## §2.1 Ce que fait le serveur de modèles

La stack confie trois tâches à des modèles d'IA. Ils tournent tous sur une même machine équipée d'une carte graphique NVIDIA : le **serveur de modèles**.

| Tâche | Modèle | Ce qu'il fait |
|---|---|---|
| Rédiger la réponse | `qwen3:14b` | Lit les extraits de documents retrouvés et rédige la réponse, avec ses sources |
| Vérifier la réponse | Le **juge** | Relit la réponse et ses sources, et signale une affirmation qui n'y figure pas (§8) |
| Retrouver les passages | `nomic-embed-text` | Transforme chaque extrait de document, puis chaque question, en **vecteur** : une empreinte numérique du sens, qui permet de retrouver les passages proches d'une question |

La VM de la stack ne fait tourner aucun modèle. Elle envoie ses demandes au serveur de modèles par le réseau. Le logiciel qui reçoit ces demandes et fait travailler la carte s'appelle le **moteur**. Ce guide en documente deux, **Ollama** et **vLLM**. Le reste de la stack est identique dans les deux cas.

Dans le lab, le serveur de modèles est un poste Windows équipé de la carte, et la VM de la stack tourne sur ce même poste, dans VMware Workstation. Ils peuvent aussi être deux machines distinctes.

---

## §2.2 Choisir le moteur

### Une question à la fois, ou plusieurs

Une question prend de 2 secondes (une question précise) à près d'une minute (la synthèse d'un long guide), selon les mesures du §10.12. Deux personnes qui posent une question **dans les mêmes secondes** sont des utilisateurs simultanés.

- **Ollama**, dans la configuration de ce guide, traite **une question à la fois** : la seconde attend que la première soit terminée. Avec une minute pour une question de synthèse, l'attente se remarque vite.
- **vLLM** traite **plusieurs questions en même temps**, sur la même carte. Mesuré dans le lab : deux séries de 30 questions lancées en même temps se terminent en 6,9 minutes, contre 6,5 minutes pour une série seule. La carte sert presque deux fois plus de questions dans le même temps, et chacune n'attend que 6 % de plus.

### Comparaison

| | Ollama | vLLM |
|---|---|---|
| Questions simultanées | Une à la fois (la suivante attend) | Plusieurs en même temps |
| Pour qui | Un à deux utilisateurs simultanés, un essai, un poste unique | Plusieurs utilisateurs simultanés : une PME en service |
| Système | Windows ou Linux | Linux seulement ; sous Windows, dans WSL2, le Linux intégré à Windows (lab et essai, pas la production) |
| Installation | Quelques minutes, plus le téléchargement des modèles | Une à deux heures, plus le téléchargement des modèles |
| Mémoire de la carte | Chargée et libérée à la demande : trois modèles sur 16 Go (rédaction, juge `qwen3:4b`, embedding) | Réservée au démarrage : deux modèles sur 16 Go, le modèle de rédaction sert aussi de juge |
| Score sur le jeu de questions du lab (15 questions, 5 passages) | 61 sur 75 | 65 sur 75 (§10.12) |
| Durée d'une question précise, posée seule | 1 à 6 s | 2 à 9 s : le juge plus grand coûte quelques secondes |
| Cloisonnement (§16) | 44 sur 44 | 44 sur 44 |

> **Recommandation :** dès que plusieurs personnes utilisent l'assistant en même temps, ce qui est le cas d'une PME en service, choisir **vLLM**. Pour un essai, un poste unique, ou un à deux utilisateurs, **Ollama** est nettement plus simple à installer et à exploiter. Le choix n'est pas définitif : passer de l'un à l'autre ne demande ni réindexation ni nouvelle installation de la stack (§2.5).

> **Une réserve honnête.** Ollama sait aussi traiter plusieurs questions à la fois (variable `OLLAMA_NUM_PARALLEL`), à condition que la carte ait la mémoire nécessaire pour chaque question en cours. Le lab l'a réglé à 1 pour faire tenir trois modèles sur 16 Go, et n'a pas mesuré ce mode. La comparaison ci-dessus vaut pour la configuration du guide.

---

## §2.3 Ollama

### Sous Windows

C'est la configuration la plus éprouvée du lab. Les détails, et la façon de vérifier que les réglages sont bien lus, sont au §10.1.

**1. Installer Ollama** depuis [ollama.com](https://ollama.com), dans sa dernière version : une version ancienne ne reconnaît pas les cartes récentes.

**2. Régler Ollama.** Dans PowerShell, **ouvert avec le compte qui fera tourner Ollama** (les réglages sont des variables d'environnement de l'utilisateur) :

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", "q8_0", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "1h", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NO_CLOUD", "1", "User")
```

| Variable | Effet |
|---|---|
| `OLLAMA_HOST` | Ollama écoute sur le réseau, et pas seulement sur la machine elle-même : sans elle, la VM ne peut pas le joindre |
| `OLLAMA_FLASH_ATTENTION` | Calcul plus économe en mémoire |
| `OLLAMA_KV_CACHE_TYPE` | Mémoire de travail des questions sur 8 bits : environ deux fois moins de place, perte de qualité négligeable |
| `OLLAMA_NUM_PARALLEL` | Une question à la fois (voir §2.2) |
| `OLLAMA_KEEP_ALIVE` | Modèles gardés en mémoire une heure après usage (5 minutes par défaut) |
| `OLLAMA_NO_CLOUD` | Désactive les modèles hébergés chez Ollama : rien ne doit sortir de vos machines |

Quitter ensuite Ollama depuis la zone de notification (clic droit sur l'icône, puis *Quit*), et le relancer : les variables ne sont lues qu'au démarrage.

**3. Télécharger les trois modèles** (environ 12 Go) :

```powershell
ollama pull qwen3:14b
ollama pull qwen3:4b
ollama pull nomic-embed-text
ollama list
```

**4. Ouvrir le port au besoin.** Si la VM n'obtient pas de réponse (étape 8 du §0), autoriser le port 11434 dans le pare-feu Windows, de préférence pour la seule adresse de la VM :

```powershell
New-NetFirewallRule -DisplayName "Ollama (stack RAG)" -Direction Inbound -Protocol TCP -LocalPort 11434 -RemoteAddress <IP-VM> -Action Allow
```

> **Ollama tourne dans la session de l'utilisateur.** Fermer la fenêtre du Bureau à distance laisse la session ouverte et Ollama actif ; **se déconnecter** ferme la session et arrête Ollama. La stack n'a alors plus de modèle (§10.1).

### Sous Linux

Validé dans le lab dans WSL2, avec Ollama 0.40.3 : mêmes scores et mêmes durées que sous Windows. Installation par le script officiel, puis réglages dans un complément du service systemd :

```bash
curl -fsSL https://ollama.com/install.sh | sh

sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<'FIN'
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_KEEP_ALIVE=1h"
Environment="OLLAMA_NO_CLOUD=1"
FIN
sudo systemctl daemon-reload && sudo systemctl restart ollama
systemctl show ollama --property=Environment --no-pager | tr ' ' '\n'
```

**Attendu :** les six variables. Télécharger ensuite les trois modèles par `ollama pull`, comme sous Windows. Dans WSL2, la préparation de §2.4.2 s'applique aussi ; si la VM ne joint pas Ollama, ajouter le port 11434 à la règle de pare-feu. **Une seule installation d'Ollama à la fois** : en mode `mirrored`, une instance Windows et une instance WSL2 se disputeraient le même port.

> **À savoir sur le juge `qwen3:4b`.** Dans la bibliothèque d'Ollama, l'étiquette `qwen3:4b` désigne aujourd'hui la variante *Qwen3-4B-Thinking-2507*, qui raisonne toujours : sans contrainte de format, elle ignore la consigne de ne pas réfléchir et écrit son raisonnement avant sa réponse (143 tokens pour répondre « OK » dans un test du lab). Dans la stack, la réponse du juge est contrainte au format JSON dès le premier mot, ce qui la rend utilisable. Voir §10.12.

---

## §2.4 vLLM

vLLM est un moteur conçu pour servir plusieurs requêtes en même temps. Ce qu'il faut savoir avant de commencer :

- **Linux seulement, carte NVIDIA.** Il n'existe pas de version Windows. Sur un poste Windows, vLLM tourne dans **WSL2**, le sous-système Linux de Windows, qui accède à la carte par le pilote Windows.
- **Il réserve la mémoire de la carte au démarrage.** Une part fixe, réglée au lancement, lui appartient tant qu'il tourne. Rien d'autre ne doit utiliser la carte en même temps : ni Ollama, ni un logiciel de génération d'images.
- **Un serveur vLLM sert un seul modèle.** La stack en lance deux : un pour la rédaction (qui sert aussi de juge), un pour l'embedding.
- **Il parle la langue de l'API d'OpenAI**, pas celle d'Ollama. La RAG API s'y adapte par un réglage (`LLM_API=openai`), sans autre changement.
- **Les modèles viennent de Hugging Face**, au format AWQ : une compression sur 4 bits, l'équivalent du format utilisé par Ollama.

| Rôle | Avec Ollama | Avec vLLM (dépôt Hugging Face) |
|---|---|---|
| Rédaction | `qwen3:14b` | `Qwen/Qwen3-14B-AWQ`, la version officielle de Qwen, servie sous le nom `qwen3:14b` |
| Juge | `qwen3:4b` | Le même `Qwen3-14B-AWQ` |
| Embedding | `nomic-embed-text` | `nomic-ai/nomic-embed-text-v1.5`, servi sous le nom `nomic-embed-text` |

### §2.4.1 Où l'installer

| Machine | Statut |
|---|---|
| Poste Windows 11 avec la carte, vLLM dans WSL2 | **Validé en lab** (RTX 5060 Ti 16 Go, pilote Windows 616.92). Pour le lab et l'essai, **pas pour la production** |
| Serveur Linux (Ubuntu) avec une carte NVIDIA | La cible de production. Non testé en lab. Même procédure à partir de §2.4.3, sans la partie WSL2 ; le pilote NVIDIA pour Linux est alors à installer |
| DGX Spark | Documentaire (§2.6) |

Prévoir une carte d'au moins 16 Go, et environ 12 Go de disque pour les modèles, plus l'environnement de vLLM (plusieurs gigaoctets).

> **WSL2 sert au lab et à l'essai, pas à la production.** Constaté dans le lab : quand on ferme le dernier terminal Ubuntu, WSL2 s'arrête (`wsl -l -v` indique `Stopped` après trois minutes) et les serveurs de modèles s'arrêtent avec lui. Tant qu'un terminal Ubuntu reste ouvert, les services fonctionnent. Le lab n'a pas testé de moyen de garder WSL2 actif sans terminal, ni son démarrage au lancement de Windows. Pour un service que les utilisateurs de l'entreprise attendent en permanence, installer vLLM sur un serveur Linux.

### §2.4.2 Préparer WSL2 (poste Windows seulement)

**1. Le pilote NVIDIA de Windows**, à jour (§10.1). **N'installer aucun pilote NVIDIA dans Linux** : WSL2 utilise celui de Windows.

**2. Installer Ubuntu**, dans PowerShell ouvert en administrateur :

```powershell
wsl --install -d Ubuntu-26.04
```

Redémarrer si Windows le demande. Au premier lancement, Ubuntu demande de créer un utilisateur Linux et son mot de passe.

> **Si le poste fait aussi tourner VMware Workstation.** Activer WSL2 active la plateforme de virtualisation de Windows : VMware fonctionne alors au-dessus de l'hyperviseur Windows, et l'option de virtualisation imbriquée d'une VM (« Virtualiser Intel VT-x/EPT ») peut devenir indisponible. Vérifier les VM qui en dépendent avant d'activer WSL2.

**3. Régler WSL2.** Créer le fichier `.wslconfig` dans le dossier de l'utilisateur Windows (`C:\Users\<utilisateur>\.wslconfig`) :

```ini
[wsl2]
memory=16GB
swap=8GB
networkingMode=mirrored
```

| Réglage | Effet |
|---|---|
| `memory` | Mémoire maximale de WSL2. 16 Go suffisent au chargement du modèle (9,3 Go lus depuis le disque) |
| `networkingMode=mirrored` | WSL2 partage l'adresse réseau de Windows : la VM joint vLLM à l'adresse du poste Windows. Conséquence : vLLM est visible depuis tout le réseau local, d'où la clé d'API obligatoire (§2.4.4) |

Appliquer avec `wsl --shutdown`, puis rouvrir Ubuntu.

**4. Vérifier, dans Ubuntu :**

```bash
nvidia-smi
systemctl is-system-running
ip -br addr
```

**Attendu :** la carte et sa mémoire ; `running` ou `degraded` (dans le lab, `degraded` vient d'un service sans rapport, `systemd-binfmt`, sans conséquence) ; l'adresse IP du poste Windows sur l'interface `eth0`. Si `systemctl` répond que systemd n'est pas actif, ajouter `[boot]` puis `systemd=true` dans `/etc/wsl.conf`, et refaire `wsl --shutdown`.

**5. Ouvrir les ports de vLLM.** WSL2 a son propre pare-feu (pare-feu Hyper-V), qui bloque par défaut les connexions entrantes. Dans PowerShell ouvert en administrateur :

```powershell
New-NetFirewallHyperVRule -Name "vllm-entrant" -DisplayName "vLLM entrant 8000 et 8001" -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol TCP -LocalPorts 8000,8001 -Action Allow
```

L'identifiant `VMCreatorId` est celui de WSL, le même sur tous les postes. Sans cette règle, une connexion depuis la VM reste bloquée, sans message d'erreur.

### §2.4.3 Installer vLLM

Dans Ubuntu, avec l'utilisateur Linux créé à l'installation :

```bash
# Compilateur C : vLLM compile un petit module au premier calcul
sudo apt update && sudo apt install -y build-essential

# Dossier de vLLM
sudo mkdir -p /opt/vllm && sudo chown $USER /opt/vllm

# uv : l'outil d'installation Python recommandé par vLLM
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env

# Environnement Python isolé, puis vLLM, dans la version validée
cd /opt/vllm
uv venv --python 3.12 --seed --managed-python
source .venv/bin/activate
uv pip install vllm==0.31.0 --torch-backend=auto
```

L'option `--torch-backend=auto` choisit la version de PyTorch (la bibliothèque de calcul) adaptée à la carte et au pilote. Vérifier :

```bash
vllm --version
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_capability(0))"
```

**Attendu :** `0.31.0`, puis dans le lab `2.13.0+cu132 13.2 True (12, 0)`. `True` signifie que la carte est accessible ; `(12, 0)` désigne une carte de la génération Blackwell (série RTX 50).

> **Pas besoin du CUDA Toolkit.** La configuration de ce guide évite les deux composants de vLLM qui exigent le compilateur CUDA (`nvcc`) : le cache sur 8 bits et l'échantillonneur FlashInfer (§2.4.9). Certaines documentations citent aussi une commande `vllm download-kernels` : elle n'existe pas dans la version 0.31.0, et n'est pas nécessaire.

### §2.4.4 Télécharger les modèles et créer la clé d'API

**Les modèles** (environ 12 Go), dans un dossier commun :

```bash
source /opt/vllm/.venv/bin/activate   # la commande hf est installée avec vLLM
sudo mkdir -p /opt/hf /etc/vllm
sudo chown $USER /opt/hf
export HF_HOME=/opt/hf
hf download Qwen/Qwen3-14B-AWQ
hf download nomic-ai/nomic-embed-text-v1.5
du -sh /opt/hf
```

**La clé d'API**, que la stack devra présenter à chaque requête. Elle est créée directement dans un fichier lisible par root et par votre utilisateur seulement, sans jamais s'afficher :

```bash
echo "VLLM_API_KEY=$(openssl rand -hex 32)" | sudo tee /etc/vllm/vllm.env > /dev/null
sudo chown root:$USER /etc/vllm/vllm.env
sudo chmod 640 /etc/vllm/vllm.env
ls -l /etc/vllm/vllm.env
```

**Attendu :** `-rw-r-----`, propriétaire `root`, groupe votre utilisateur, 78 octets.

> **Ne jamais coller la clé dans un ticket, un message ou une capture d'écran.** Une clé qui a circulé est à régénérer (même commande).

Pour reporter la clé dans le `.env` de la VM (§2.4.8) sans l'afficher, la copier dans le presse-papiers de Windows depuis Ubuntu, la coller dans l'éditeur ouvert sur la VM, puis copier un autre texte pour vider le presse-papiers :

```bash
sudo grep '^VLLM_API_KEY=' /etc/vllm/vllm.env | cut -d= -f2- | tr -d '\n' | clip.exe
```

### §2.4.5 Lancer les deux serveurs

Le premier lancement se fait à la main, dans **deux terminaux Ubuntu**, pour voir les messages. Le démarrage automatique vient ensuite (§2.4.7). Un serveur lancé à la main s'arrête quand on ferme son terminal.

**Terminal 1 : rédaction et juge (port 8000).** Le lancer en premier.

```bash
cd /opt/vllm && source .venv/bin/activate
set -a; source /etc/vllm/vllm.env; set +a
export HF_HOME=/opt/hf VLLM_USE_FLASHINFER_SAMPLER=0
vllm serve Qwen/Qwen3-14B-AWQ \
  --served-model-name qwen3:14b \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.87 \
  --max-num-seqs 4 \
  --reasoning-parser qwen3 \
  --default-chat-template-kwargs '{"enable_thinking": false}' \
  --host 0.0.0.0 --port 8000 --api-key "$VLLM_API_KEY"
```

Attendre la ligne `Application startup complete` : une à trois minutes, le premier démarrage étant le plus long (préparation des calculs, mise en cache ensuite).

**Terminal 2 : embedding (port 8001).**

```bash
cd /opt/vllm && source .venv/bin/activate
set -a; source /etc/vllm/vllm.env; set +a
export HF_HOME=/opt/hf
vllm serve nomic-ai/nomic-embed-text-v1.5 \
  --runner pooling --trust-remote-code \
  --served-model-name nomic-embed-text \
  --max-model-len 2048 \
  --gpu-memory-utilization 0.06 \
  --host 0.0.0.0 --port 8001 --api-key "$VLLM_API_KEY"
```

Au premier démarrage, ce serveur télécharge le code du modèle depuis Hugging Face (dépôt `nomic-ai/nomic-bert-2048`) : l'accès Internet est nécessaire à ce moment.

| Option | Valeur | Pourquoi |
|---|---|---|
| `--served-model-name` | `qwen3:14b`, `nomic-embed-text` | Le nom sous lequel la stack appelle le modèle : le même qu'avec Ollama |
| `--max-model-len` | `16384` | La fenêtre de contexte : question, extraits et réponse. Même valeur que `LLM_NUM_CTX` avec Ollama |
| `--gpu-memory-utilization` | `0.87` et `0.06` | La part de la mémoire de la carte réservée par chaque serveur : 87 % et 6 %. Le reste sert à l'affichage de Windows |
| `--max-num-seqs` | `4` | Au plus quatre questions traitées ensemble |
| `--reasoning-parser` et `--default-chat-template-kwargs` | `qwen3`, réflexion désactivée | Qwen3 répond directement, sans écrire de raisonnement : c'est l'équivalent du `think: false` d'Ollama |
| `--api-key` | La clé | Toute requête sans la clé est refusée (code HTTP 401) |
| `--runner pooling` | | Mode embedding : le serveur produit des vecteurs, pas du texte |
| `--trust-remote-code` | | Le modèle nomic s'accompagne de code Python, exécuté par vLLM. Nécessaire pour ce modèle, qui vient de son éditeur |
| `VLLM_USE_FLASHINFER_SAMPLER=0` | | Écarte un composant qui exige le compilateur CUDA, non installé (§2.4.9) |

Dans le journal du terminal 1, quatre lignes confirment la configuration :

| Ligne | Ce qu'elle confirme |
|---|---|
| `non-default args: {... 'api_key': '***' ...}` | La clé est active (jamais affichée en clair) |
| `Using FLASH_ATTN attention backend` | Le calcul le plus courant est retenu, sans compilateur CUDA |
| `FlashInfer top-p/top-k sampling disabled via VLLM_USE_FLASHINFER_SAMPLER=0` | L'échantillonneur problématique est écarté |
| `GPU KV cache size: 26,128 tokens, Maximum concurrency for 16,384 tokens per request: 1.59x` | La mémoire de travail des questions en cours (valeurs du lab) : une question pleine de 16 384 tokens, et un peu plus de la moitié d'une autre. Les questions de la stack (4 000 à 11 000 tokens) tiennent à deux ou trois |

Une ligne d'avertissement signale que les réglages par défaut du modèle (température 0,6, `top_k` 20, `top_p` 0,95) remplacent ceux de vLLM : c'est attendu. Ce sont les mêmes qu'avec Ollama, et la RAG API impose de toute façon sa propre température.

> **Pourquoi pas le cache sur 8 bits, comme avec Ollama ?** vLLM le propose (`--kv-cache-dtype fp8`), mais il impose alors des composants qui exigent le compilateur CUDA. Contourné, il n'a apporté aucun gain de vitesse mesurable à la lecture d'un long contexte (§10.12). Sans lui, le cache prend deux fois plus de place, compensée par une réservation de 87 % au lieu de 80 %.

### §2.4.6 Vérifier

**Depuis le serveur, dans un troisième terminal.** Sans la clé, les deux serveurs doivent refuser :

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/v1/models
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/v1/models
```

**Attendu :** `401` deux fois. Puis un essai complet, avec la clé, qui contrôle la réponse sans raisonnement, la réponse au format JSON (celle du juge) et la vitesse :

```bash
set -a; source /etc/vllm/vllm.env; set +a
python3 - <<'FIN'
import json, time, os, urllib.request
K = os.environ["VLLM_API_KEY"]
def appel(corps):
    req = urllib.request.Request("http://localhost:8000/v1/chat/completions",
        data=json.dumps(corps).encode(),
        headers={"Authorization": "Bearer " + K, "Content-Type": "application/json"})
    t = time.time(); r = json.load(urllib.request.urlopen(req, timeout=300))
    return r, time.time() - t
m = "qwen3:14b"
r, d = appel({"model": m, "temperature": 0, "max_tokens": 200,
              "messages": [{"role": "user", "content": "Réponds uniquement par le mot OK."}]})
print("1 :", repr(r["choices"][0]["message"]["content"]), "|", r["usage"]["completion_tokens"], "tokens")
r, d = appel({"model": m, "temperature": 0, "max_tokens": 200, "response_format": {"type": "json_object"},
              "messages": [{"role": "user", "content": 'Réponds uniquement en JSON : {"ancree": true ou false}. La Terre est-elle plate ?'}]})
json.loads(r["choices"][0]["message"]["content"]); print("2 : JSON valide")
r, d = appel({"model": m, "temperature": 0.2, "max_tokens": 400,
              "messages": [{"role": "user", "content": "Rédige environ 300 mots sur la protection des données en Suisse."}]})
print("3 : %.1f tokens par seconde" % (r["usage"]["completion_tokens"] / d))
FIN
```

**Attendu :** `'OK'` en 2 tokens ; `JSON valide` ; de l'ordre de 40 tokens par seconde sur une carte de cette classe (44 mesurés dans le lab, 42 avec Ollama sur la même carte, §10.12).

**Depuis la VM de la stack**, l'adresse étant celle du poste Windows (ou du serveur Linux) :

```bash
curl -m 5 -s -o /dev/null -w "%{http_code}\n" http://<IP-SERVEUR-MODELES>:8000/v1/models
curl -m 5 -s -o /dev/null -w "%{http_code}\n" http://<IP-SERVEUR-MODELES>:8001/v1/models
```

**Attendu :** `401` deux fois. Un `000` après 5 secondes signale un blocage réseau : la règle de pare-feu de §2.4.2.

### §2.4.7 Démarrage automatique

> **Validé en lab dans WSL2**, avec un terminal Ubuntu ouvert : démarrage des deux services dans le bon ordre, relance automatique après un plantage, libération complète de la carte à l'arrêt (tableau ci-dessous). Les fichiers reprennent exactement les commandes validées au §2.4.5. Sur un serveur Linux dédié, ils n'ont pas encore été essayés.

Arrêter d'abord les deux serveurs lancés à la main (Ctrl+C dans chaque terminal), puis créer les deux services, en remplaçant `<utilisateur>` par votre utilisateur Linux :

```bash
sudo tee /etc/systemd/system/vllm-llm.service > /dev/null <<'FIN'
[Unit]
Description=vLLM : rédaction et juge (Qwen3-14B-AWQ)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<utilisateur>
EnvironmentFile=/etc/vllm/vllm.env
Environment=HF_HOME=/opt/hf
Environment=VLLM_USE_FLASHINFER_SAMPLER=0
ExecStart=/opt/vllm/.venv/bin/vllm serve Qwen/Qwen3-14B-AWQ --served-model-name qwen3:14b --max-model-len 16384 --gpu-memory-utilization 0.87 --max-num-seqs 4 --reasoning-parser qwen3 --default-chat-template-kwargs '{"enable_thinking": false}' --host 0.0.0.0 --port 8000 --api-key ${VLLM_API_KEY}
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
FIN

sudo tee /etc/systemd/system/vllm-embed.service > /dev/null <<'FIN'
[Unit]
Description=vLLM : embedding (nomic-embed-text)
After=network-online.target vllm-llm.service
Wants=network-online.target

[Service]
Type=simple
User=<utilisateur>
EnvironmentFile=/etc/vllm/vllm.env
Environment=HF_HOME=/opt/hf
# Attendre que le serveur de rédaction ait réservé sa mémoire
TimeoutStartSec=600
ExecStartPre=/usr/bin/timeout 500 /bin/bash -c 'until curl -s -o /dev/null http://127.0.0.1:8000/v1/models; do sleep 5; done'
ExecStart=/opt/vllm/.venv/bin/vllm serve nomic-ai/nomic-embed-text-v1.5 --runner pooling --trust-remote-code --served-model-name nomic-embed-text --max-model-len 2048 --gpu-memory-utilization 0.06 --host 0.0.0.0 --port 8001 --api-key ${VLLM_API_KEY}
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
FIN

sudo systemctl daemon-reload
sudo systemctl enable --now vllm-llm vllm-embed
```

Le serveur d'embedding attend que celui de la rédaction réponde : les deux réservent leur mémoire l'un après l'autre, dans l'ordre validé à la main.

| Contrôle | Commande | Attendu |
|---|---|---|
| Les deux services tournent | `systemctl status vllm-llm vllm-embed --no-pager` | `active (running)` |
| Journal d'un service | `journalctl -u vllm-llm -n 30 --no-pager` | Les quatre lignes de §2.4.5, puis `Application startup complete` |
| La clé est exigée | Les deux `curl` sans clé de §2.4.6 | `401` deux fois |
| La réflexion est désactivée | L'essai complet de §2.4.6 | `'OK'` en 2 tokens |
| Relance après un plantage | `sudo systemctl kill -s KILL vllm-llm`, puis `systemctl status vllm-llm --no-pager` | Le service redémarre seul après 15 secondes et répond de nouveau environ 35 secondes plus tard ; le serveur d'embedding n'est pas touché |
| La carte est libérée à l'arrêt | `sudo systemctl stop vllm-llm vllm-embed`, puis `nvidia-smi --query-gpu=memory.used --format=csv` | Une centaine de Mio utilisés ; relancer ensuite avec `sudo systemctl start vllm-llm vllm-embed` |
| Démarrage sans intervention | Redémarrer le poste, ne pas ouvrir de terminal Ubuntu, puis tester depuis la VM | Sur un serveur Linux : `401`. Dans WSL2 : non validé, WSL2 s'arrête quand le dernier terminal se ferme (§2.4.1) |

### §2.4.8 Raccorder la stack

Sur la VM, dans `/root/rag-stack/.env`, activer le bloc vLLM du serveur de modèles (bloc B du fichier `env.example` du dépôt) à la place du bloc Ollama :

```bash
LLM_API=openai
EMBED_API=openai
LLM_BASE_URL=http://<IP-SERVEUR-MODELES>:8000
EMBED_BASE_URL=http://<IP-SERVEUR-MODELES>:8001
JUDGE_BASE_URL=
LLM_MODEL=qwen3:14b
JUDGE_MODEL=qwen3:14b
EMBED_MODEL=nomic-embed-text
VLLM_API_KEY=<clé-vllm>
```

et, plus bas dans le même fichier, `OLLAMA_URL=http://<IP-SERVEUR-MODELES>:8001` (malgré son nom, cette variable désigne le serveur d'embedding pour les lancements manuels de l'indexeur).

Le `docker-compose.yml` du dépôt transmet ces variables à la RAG API. Après une mise à jour des scripts, reconstruire l'image (le code de la RAG API y est intégré), puis vérifier **depuis le conteneur** :

```bash
cd /root/rag-stack
docker compose up -d --build rag-api
docker exec rag-api printenv LLM_API EMBED_API LLM_BASE_URL EMBED_BASE_URL LLM_MODEL JUDGE_MODEL
docker exec rag-api python3 -c "
import os, httpx
h = {'Authorization': 'Bearer ' + os.environ['VLLM_API_KEY']}
print('rédaction', httpx.get(os.environ['LLM_BASE_URL'] + '/v1/models', headers=h, timeout=10).status_code,
      '| embedding', httpx.get(os.environ['EMBED_BASE_URL'] + '/v1/models', headers=h, timeout=10).status_code)
"
```

**Attendu :** `openai` deux fois, les deux adresses, `qwen3:14b` deux fois, puis `rédaction 200 | embedding 200`. La VM qui joint le serveur ne suffit pas : c'est le conteneur qui l'interroge, et dans le lab, la VM le joignait alors que le conteneur ne le pouvait pas (§2.4.9).

Terminer par une question dans Open WebUI, puis le test de cloisonnement (§16) : **44 sur 44** dans le lab après la bascule.

### §2.4.9 Les pièges rencontrés

Tous ces cas se sont produits pendant la mise en place du lab. Ils sont classés dans l'ordre où un lecteur les rencontrerait.

| Symptôme | Cause | Solution |
|---|---|---|
| `invalid choice: 'download-kernels'` | Commande citée par une documentation, absente de vLLM 0.31.0 | L'ignorer : elle n'est pas nécessaire |
| `Failed to find C compiler` au premier démarrage | vLLM compile un petit module au premier calcul | `sudo apt install -y build-essential` |
| `Could not find nvcc and default cuda_home='/usr/local/cuda' doesn't exist`, au démarrage | Avec le cache sur 8 bits (`--kv-cache-dtype fp8`), vLLM choisit un calcul (FlashInfer) qu'il compile à la volée avec le compilateur CUDA | Ne pas utiliser le cache sur 8 bits : vLLM retient alors FlashAttention, sans compilateur |
| Le même message, dans une ligne qui mentionne `flashinfer_sample` | L'échantillonneur FlashInfer, qui choisit le mot suivant, se compile lui aussi | `VLLM_USE_FLASHINFER_SAMPLER=0` |
| `2.5 GiB KV cache is needed, which is larger than the available KV cache memory (2.44 GiB)` | La réservation de mémoire ne laisse pas la place d'une question de 16 384 tokens | Augmenter `--gpu-memory-utilization` par petits pas (0.85 → 0.87 dans le lab), ou réduire `--max-model-len` |
| `Address already in use` | Un ancien serveur tourne encore : un Ctrl+C ne l'a pas toujours arrêté | `pkill -f "Qwen3-14B-AWQ"`, puis `ss -ltn \| grep -E ':800[01]'` pour vérifier que le port est libre |
| Le serveur s'arrête quand on ferme son terminal | Un serveur lancé à la main vit avec son terminal | Les services de §2.4.7 |
| Depuis la VM, `curl` reste bloqué sans réponse | Pare-feu Hyper-V de WSL2 | La règle de §2.4.2 |
| La VM joint le serveur, mais pas le conteneur (`No route to host`) | Le réseau Docker de la VM avait perdu son adresse (voir « En cas de problème » au §0) | `systemctl restart docker`, puis `docker compose up -d` |
| Questions refusées avec une erreur 503, journal : `Échec de la recherche documentaire` | Le serveur d'embedding (port 8001) est arrêté : sans vecteur, pas de recherche | `ss -ltn` sur le serveur : relancer le serveur manquant |
| Réponses quatre fois plus lentes, serveur souvent inactif entre deux questions | Une synchronisation du corpus tournait en même temps | Mesurer au repos (§10.3) |

### §2.4.10 Avant une mise en production

Ce qui précède est validé sur un réseau de lab de confiance. Trois points ne le sont pas, et sont à traiter avant de mettre le service à disposition de toute l'entreprise :

| Point | Situation | À faire avant la production |
|---|---|---|
| Transport | La VM parle aux deux serveurs en HTTP : la clé d'API et les questions circulent sans chiffrement. La clé protège l'accès, pas le contenu des échanges. | Limiter l'accès aux ports 8000 et 8001 à l'adresse de la VM, placer les deux machines sur un réseau isolé, ou chiffrer le lien (TLS). Non testé en lab. |
| Modèles téléchargés | Les commandes de §2.4.4 désignent les modèles par leur nom de dépôt, qui renvoie à la version courante au moment du téléchargement. Le modèle d'embedding est lancé avec `--trust-remote-code`, qui exécute le code Python fourni avec lui. | Relever la révision de chaque modèle, en conserver une copie locale validée (le répertoire `/opt/hf`) et lire le code distant avant d'autoriser son exécution. vLLM propose les options `--revision` et `--code-revision` : à vérifier dans la documentation de votre version, non testé en lab. |
| Charge | Seules deux séries de questions simultanées ont été mesurées (§10.12). | Mesurer la charge attendue (par exemple quatre questions simultanées, avec les durées maximales et la mémoire de la carte) avant d'annoncer une capacité. |

---

## §2.5 Passer d'un moteur à l'autre

### Pas de réindexation

L'index des documents ne dépend que du modèle d'embedding. Le même modèle, `nomic-embed-text` en version 1.5, sert avec les deux moteurs. Le lab l'a vérifié avant de basculer : 50 extraits pris au hasard dans l'index construit avec Ollama, recalculés avec vLLM, donnent des vecteurs **identiques** (similarité de 1,00000 pour chacun). La seule différence : vLLM ne ramène pas ses vecteurs à une longueur de 1, ce que la RAG API fait désormais elle-même.

La vérification n'est à refaire que si vous changez de version du modèle d'embedding. Le script utilisé, à lancer sur la VM, la clé vLLM étant saisie sans affichage par `read -rs VK` :

```bash
docker exec -i -e VLLM_API_KEY="$VK" -e VLLM_URL=http://<IP-SERVEUR-MODELES>:8001 rag-api python3 - <<'FIN'
import os, re, random, math, httpx
from qdrant_client import QdrantClient
q = QdrantClient(url=os.environ["QDRANT_HOST"], api_key=os.environ["QDRANT_API_KEY"])
pts, _ = q.scroll(collection_name="documents", limit=400, with_payload=["text"], with_vectors=True)
random.seed(1); pts = random.sample(pts, min(50, len(pts)))
cos = lambda a, b: sum(x*y for x, y in zip(a, b)) / (math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(y*y for y in b)))
h = {"Authorization": "Bearer " + os.environ["VLLM_API_KEY"]}
res = []
for p in pts:
    t = re.sub(r'[. ]{10,}', ' ', p.payload["text"]).strip()
    r = httpx.post(os.environ["VLLM_URL"] + "/v1/embeddings", headers=h, json={"model": "nomic-embed-text", "input": t}, timeout=60)
    v = p.vector if isinstance(p.vector, list) else list(p.vector.values())[0]
    res.append(cos(v, r.json()["data"][0]["embedding"]))
print("extraits :", len(res), "| similarité minimale : %.5f" % min(res))
FIN
```

**Attendu :** une similarité minimale d'au moins 0,999. En dessous de 0,99, réindexer.

### La bascule

| Étape | Vers vLLM | Retour à Ollama |
|---|---|---|
| 1. Sauvegarder | `cp /root/rag-stack/.env /root/rag-stack/.env.avant-bascule` | |
| 2. Libérer la carte | Arrêter Ollama : sous Windows, le quitter et retirer son démarrage automatique ; sous Linux, `sudo systemctl disable --now ollama` | `sudo systemctl disable --now vllm-llm vllm-embed` |
| 3. Démarrer l'autre moteur | §2.4.5 ou §2.4.7 | Relancer Ollama |
| 4. Changer le `.env` | Bloc B (§2.4.8) | Bloc A, ou restaurer la sauvegarde |
| 5. Appliquer | `docker compose up -d rag-api` (`--build` après une mise à jour des scripts) | Idem |
| 6. Vérifier | Le contrôle depuis le conteneur (§2.4.8), une question, le test de cloisonnement | Idem |

Les deux moteurs ne tiennent pas ensemble sur une carte de 16 Go : vLLM réserve sa mémoire au démarrage, et refuse de démarrer si Ollama l'occupe déjà.

---

## §2.6 DGX Spark

> **Documentaire :** non validé sur matériel réel. Les commandes reprennent la documentation de vLLM et les retours publiés par des utilisateurs de DGX Spark. Un défaut connu affecte certains modèles sur l'architecture ARM64 GB10 : vérifier que la version de vLLM installée comporte les correctifs SM121 avant une mise en production.

Sur DGX Spark (DGX OS, CUDA 13), l'installation par `uv pip install vllm --torch-backend=auto` (§2.4.3) s'applique, sans WSL2. Sa mémoire unifiée de 128 Go permet un modèle plus grand, par exemple une version NVFP4 de Qwen3-30B-A3B publiée par NVIDIA (disponibilité à vérifier au moment du déploiement) :

```bash
vllm serve nvidia/Qwen3-30B-A3B-NVFP4 \
  --served-model-name qwen3-30b \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.90 \
  --reasoning-parser qwen3 \
  --default-chat-template-kwargs '{"enable_thinking": false}' \
  --host 0.0.0.0 --port 8000 --api-key "$VLLM_API_KEY"
```

Les modèles `nvidia/*-NVFP4` intègrent leur quantification : vLLM la détecte sans option supplémentaire (sinon : `--quantization modelopt_fp4`). Dans le `.env`, `LLM_MODEL` et `JUDGE_MODEL` prennent alors le nom servi (`qwen3-30b`). Tout le reste de la stack est identique.

---

[Retour au sommaire](index.md) | [Section précédente : §1 Prérequis et création de la VM](section-01-prerequis.md) | [Section suivante : §3 Docker Compose : stack complète](section-03-docker-compose.md)

---

*Validé en lab sur LABO-G9 (Windows 11, WSL2 avec Ubuntu 26.04, NVIDIA RTX 5060 Ti 16 Go ; vLLM 0.31.0, PyTorch 2.13.0, CUDA 13.2 ; Ollama 0.40.3 sous Linux) et VM-RAG-LAB (Ubuntu Server 26.04), octobre 2026. Services systemd validés dans WSL2. Serveur Linux dédié, DGX Spark et démarrage de WSL2 sans session Windows : non validés.*

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
