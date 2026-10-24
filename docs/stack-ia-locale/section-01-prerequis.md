---
title: "§1 Prérequis et création de la VM | Guide de déploiement stack IA locale"
description: "Création et configuration de la VM Ubuntu Server 26.04 pour la stack RAG locale : sizing, épinglage CPU, Docker."
---
<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
  code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.95em; }
  pre { background: #f4f4f4; padding: 16px; border-radius: 6px; overflow-x: auto; }
  blockquote { border-left: 4px solid #2563A8; margin: 20px 0; padding: 10px 20px; background: #f0f4ff; }
</style>

# §1 Prérequis et création de la VM

[Retour au sommaire](index.md) | [Section précédente : §0 Démarrage rapide](section-00-quickstart.md) | [Section suivante : §2 Le serveur de modèles : Ollama ou vLLM](section-02-vllm.md)

**Statut :** validé sur VM-RAG-LAB, septembre 2026. Machine à un seul disque (§1.5.1) et contrôleur de disque sous VMware Workstation validés sur une VM neuve, octobre 2026 (2.22.3).

---

## §1.1 Sizing de la VM

Ce guide a été validé sur la configuration suivante, dans VMware Workstation avec un hôte Intel Core i7-14700 (8 P-cores + 12 E-cores, 28 threads, 64 Go DDR5).

| Ressource | Minimum | Recommandé | Remarque |
|---|---|---|---|
| vCPU | 4 | 6 | Épingler sur P-cores physiques (voir §1.3) |
| RAM | 16 Go | 16 Go | Open WebUI + RAG API + Docker Compose complet : environ 8 à 10 Go en charge. Les modèles ne tournent pas dans cette VM, mais sur le serveur de modèles (§2) |
| Disque | 80 Go | 100 Go | Contrôleur **SCSI** (LSI Logic) dans VMware Workstation, pas NVMe : voir la note ci-dessous |
| Réseau | NAT | Réseau lab dédié | Un réseau lab donne accès aux ressources AD, SMB, DNS |

> **Note VMware Workstation :** choisir **1 processeur, 6 cœurs** (et non 2 processeurs × 3 cœurs). Un seul socket évite des problèmes de topologie NUMA. Pilote réseau **vmxnet3** plutôt que e1000.

> **Disque virtuel : SCSI, pas NVMe (constat du lab, octobre 2026).** Jusqu'à la 2.22.2, ce guide recommandait un disque NVMe. Avec Ubuntu 26.04 (noyau 7.0) sous VMware Workstation, le contrôleur NVMe virtuel perd par moments l'avis de fin d'une écriture : le noyau ne la découvre qu'après son délai de 30 secondes, et l'écriture se bloque d'autant. Mesuré sur deux VM, chiffrement ou non : une écriture de 2 Go sur trois prenait environ 30 s au lieu de 4. Le même disque branché en SCSI (LSI Logic) n'a montré aucun blocage. La stack fonctionne avec NVMe, mais synchronisations et écritures de Qdrant subissent ces pauses. Pour vérifier une VM existante :
>
> ```bash
> dmesg | grep -i "nvme" | grep -i timeout
> ```
>
> Des lignes `nvme nvme0: I/O tag … timeout, completion polled` signalent le défaut. Changer le contrôleur d'une VM existante est simple, sauf si elle a un TPM virtuel : VMware chiffre alors la VM, et il faut la déchiffrer pour retirer le disque. Pour une nouvelle VM, choisir SCSI dès la création. Ce constat vaut pour le lab ; d'autres versions de VMware ou du noyau peuvent se comporter autrement.

---

## §1.2 Installation Ubuntu Server 26.04 LTS

Créer la VM dans VMware Workstation avec Ubuntu Server 26.04 LTS (nom de code : **resolute**). Lors de l'installation :

- Laisser LVM activé. LVM est recommandé : il permet d'étendre un volume sans réinstallation si le corpus grossit, et, sur une machine à un seul disque, de créer le volume chiffré des données dans l'espace libre (§1.5.1).
- Activer OpenSSH lors de l'installation pour accéder à la VM depuis l'hôte.
- Configurer le réseau en mode statique si la VM doit rejoindre un réseau lab existant.

Une fois connecté en SSH, mettre à jour le système et installer les dépendances de base :

```bash
apt update && apt upgrade -y

apt install -y curl wget git python3-pip python3-venv \
  build-essential libssl-dev htop net-tools
```

### Extension du volume LVM : pas sur une machine à un seul disque

L'installateur Ubuntu n'alloue au système qu'environ la moitié du groupe de volumes LVM (48,5 Go sur 97 Go dans le lab). **Sur une machine à un seul disque, ne pas étendre** : l'espace libre accueillera le volume chiffré des données (§1.5.1). Étendre seulement si les données vont sur un second disque (§1.5), ou en gardant l'espace prévu pour elles :

```bash
# Vérifier la situation
lsblk
df -h

# Étendre le logical volume à 100% du VG
lvextend -l +100%FREE /dev/ubuntu-vg/ubuntu-lv

# Étendre le filesystem
resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv

# Vérification
df -h /
```

---

## §1.3 Épinglage des vCPU sur les P-cores (optionnel)

L'épinglage garantit que les vCPU de la VM s'exécutent uniquement sur les cœurs physiques performants (P-cores) de l'hôte, sans interférence des cœurs d'efficacité (E-cores) ni des threads HT des autres processus.

Éditer le fichier `.vmx` de la VM **à froid** (VM éteinte) et ajouter :

```
sched.cpu.affinity = "0,2,4,6,8,10"
```

> **Pour un i7-14700 :** le processeur compte 8 P-cores (hyperthreadés, CPU logiques 0 à 15) et 12 E-cores (non hyperthreadés, CPU logiques 16 à 27). Le masque `0,2,4,6,8,10` épingle les 6 vCPU de la VM sur six des seize threads P-core, en évitant les threads secondaires HT (numéros impairs) et les E-cores. Les numéros exacts à utiliser peuvent varier selon la configuration du BIOS et l'état du HyperThreading : vérifier l'affectation réelle dans le Gestionnaire des tâches Windows (onglet Performances, CPU, clic droit "Modifier les affinités") avant de figer le masque.

> **Syntaxe VMware Workstation :** utiliser `sched.cpu.affinity` et non `processor[N].use` qui n'est pas une valeur tristate valide dans VMware Workstation et génère des avertissements au démarrage.

Gain estimé : 10 à 20% sur les inférences CPU longues.

---

## §1.4 Installation Docker et Docker Compose

```bash
# Ajouter la clé GPG du dépôt Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /usr/share/keyrings/docker.gpg

# Ajouter le dépôt
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/usr/share/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | tee /etc/apt/sources.list.d/docker.list

# Installer Docker et Docker Compose
apt update && apt install -y docker-ce docker-ce-cli \
  containerd.io docker-buildx-plugin docker-compose-plugin

# Ajouter l'utilisateur au groupe docker
usermod -aG docker $USER

# Vérification
docker --version && docker compose version
```

Les commandes se lancent en root (`sudo -i`). Versions validées : **Docker 29.7.2** et **Compose 5.5.0** sur la première installation du lab, puis **Docker 29.9.0** et **Compose 5.6.0** sur une VM neuve, où le dépôt de Docker pour Ubuntu 26.04 (`resolute`) a fourni les versions les plus récentes sans autre manipulation.

---

## §1.5 Disque de données chiffré, avant le déploiement

**Statut :** principe et procédure de chiffrement validés en lab (§15.3), et préparation **avant** le premier déploiement validée sur une VM neuve (octobre 2026) : disque ajouté, chiffré, TPM inscrit, redémarrage avec déverrouillage automatique, Docker démarré sur le disque monté. Machine à **un seul disque** (§1.5.1) validée sur une seconde VM neuve le 24 octobre 2026 : volume chiffré dans l'espace libre du LVM, conteneur chiffré dans un fichier, déploiement complet, **redémarrage avec la stack en service**, mise à jour de la liste de révocation du Secure Boot et récupération.

La stack stocke des extraits de tous les documents indexés, l'historique des conversations, des identifiants et les clés privées des applications Entra. Tout cela doit être sur un disque chiffré **dès sa création** : un chiffrement ajouté après coup laisse des copies en clair sur le disque système, que la suppression n'efface pas (§15.3.4). Le disque chiffré se prépare donc **ici**, avant `deploy.sh`, avant que le `.env` et les clés n'existent.

| Plateforme | Solution | État |
|---|---|---|
| VM (Hyper-V, VMware, Proxmox) | Second disque virtuel, LUKS2, déverrouillage par TPM virtuel | Validé en lab |
| VM ou serveur à un seul disque, LVM avec espace libre | Volume logique LUKS2 dans l'espace libre (§1.5.1, solution A) | Validé en lab sur VM |
| Machine à un seul disque sans espace libre (DGX Spark, serveur déjà installé) | Conteneur LUKS2 dans un fichier (§1.5.1, solution B) | Procédure validée en lab sur VM, non testée sur DGX Spark |
| Serveur physique à deux disques | Même procédure sur le second disque, TPM matériel | Non testé sur matériel |

Le déverrouillage automatique exige une machine en **UEFI avec un TPM 2.0**. Selon l'hyperviseur, l'ajout d'un TPM virtuel peut exiger de chiffrer la VM elle-même. Sur le DGX Spark, la possibilité de réserver une partition à l'installation de DGX OS est à vérifier dans la documentation de NVIDIA ; un conteneur LUKS dans un fichier (§1.5.1) fonctionne sur tout Linux, sans repartitionner.

**1. Créer, chiffrer et monter le disque** : procédure de §15.3.2 et §15.3.3 (LUKS2, inscription du TPM, `/etc/crypttab`, `/etc/fstab`, condition de démarrage de Docker, script de déverrouillage de secours). Sur une machine à un seul disque : §1.5.1.

**2. Préparer l'arborescence et les liens**, avant `deploy.sh` :

```bash
mkdir -p /srv/rag-donnees/{qdrant_data,openwebui_data,n8n_data,log-rag,secrets/rag-certs,secrets/rag-tls}
chmod 700 /srv/rag-donnees/secrets /srv/rag-donnees/secrets/rag-certs /srv/rag-donnees/secrets/rag-tls
mkdir -p /root/rag-stack
for d in qdrant_data openwebui_data n8n_data; do ln -s /srv/rag-donnees/$d /root/rag-stack/$d; done
ln -s /srv/rag-donnees/secrets/.env      /root/rag-stack/.env     # lien vers un fichier qui n'existe pas encore : normal
ln -s /srv/rag-donnees/secrets/rag-certs /etc/rag-certs
ln -s /srv/rag-donnees/secrets/rag-tls   /etc/rag-tls        # certificat de Nginx (§9.8)
ln -s /srv/rag-donnees/log-rag           /var/log/rag
ls -l /root/rag-stack /etc/rag-certs /etc/rag-tls /var/log/rag
```

`deploy.sh` écrit ensuite le `.env`, les données et les journaux **à travers ces liens**, directement sur le disque chiffré. Les certificats des applications Entra, créés aux sections §11 à §14, iront de même dans `/etc/rag-certs`, et le certificat de Nginx dans `/etc/rag-tls` (depuis la 2.21.0, `deploy.sh` crée ce dernier lien lui-même s'il manque). Docker ne démarrant qu'avec le disque monté (§15.3.3), un lien sans sa cible ne peut pas se produire en fonctionnement normal.

**Deux conséquences à connaître.** Le `.env` est un lien vers un fichier qui n'existe pas encore : `cp` refuse d'y écrire tant qu'on le désigne par le lien, et `sed -i` **remplace** le lien par un vrai fichier, sur le disque système, en clair. On désigne donc toujours le vrai chemin (`/srv/rag-donnees/secrets/.env`, ou `$(readlink -f /root/rag-stack/.env)`), comme à l'étape 7 du §0. De même, le dossier `n8n_data` doit appartenir à l'utilisateur 1000 : `chown -R 1000:1000 /srv/rag-donnees/n8n_data` (sur le vrai dossier, pas sur le lien).

> **Le groupe `docker` équivaut à root** : un compte qui en est membre peut lire toutes les variables des conteneurs (`docker inspect`) et monter n'importe quel fichier de la VM. N'y ajouter aucun compte ordinaire. La commande `usermod -aG docker $USER` de §1.4, exécutée en root, ne concerne que root.

### §1.5.1 Machine à un seul disque

Un seul disque, c'est le cas d'une VM créée avec un disque unique, d'un serveur déjà installé, ou du DGX Spark. Deux solutions, validées sur une VM neuve (Ubuntu 26.04, disque de 100 Go, UEFI, TPM virtuel) le 24 octobre 2026 :

| | A. Volume logique dans l'espace libre du LVM | B. Conteneur dans un fichier |
|---|---|---|
| Quand | L'installation a laissé de l'espace libre dans le groupe de volumes (cas par défaut d'Ubuntu, §1.2) | Pas d'espace libre, ou pas de LVM : DGX Spark, serveur déjà installé |
| Principe | Un volume logique chiffré, utilisé comme un second disque | Un fichier sur le système de fichiers racine, chiffré et monté comme un disque |
| Déverrouillage par le TPM au démarrage | 0,5 s | 1,5 s |
| Écriture de 2 Go (première mesure, avant cache) | 497 Mo/s | 448 à 486 Mo/s |
| Recommandé | Oui, quand c'est possible | En repli |

Les commandes sont celles de §15.3.2 et §15.3.3, seule la désignation du volume change. Les commandes qui demandent la phrase secrète se lancent **seules**.

**A. Volume logique.** Vérifier l'espace libre (`vgs`, colonne `VFree`), puis créer le volume, ici de 30 Go dans le groupe `ubuntu-vg` :

```bash
apt install -y cryptsetup tpm2-tools
lvcreate -L 30G -n rag-donnees ubuntu-vg
wipefs -n /dev/ubuntu-vg/rag-donnees            # attendu : aucune sortie
cryptsetup luksFormat --type luks2 /dev/ubuntu-vg/rag-donnees
cryptsetup open /dev/ubuntu-vg/rag-donnees rag-donnees
mkfs.ext4 -L rag-donnees /dev/mapper/rag-donnees
mkdir -p /srv/rag-donnees && mount /dev/mapper/rag-donnees /srv/rag-donnees
```

Puis §15.3.3, tel quel : `/dev/disk/by-uuid/$UUID` désigne le volume logique comme un disque, avec `UUID=$(cryptsetup luksUUID /dev/ubuntu-vg/rag-donnees)`. Garder de l'espace libre dans le groupe permet d'agrandir le volume plus tard (`lvextend`, `cryptsetup resize`, `resize2fs`).

**B. Conteneur dans un fichier.** Ici de 10 Go, sur la racine :

```bash
fallocate -l 10G /var/lib/rag-conteneur.img && chmod 600 /var/lib/rag-conteneur.img
cryptsetup luksFormat --type luks2 /var/lib/rag-conteneur.img
cryptsetup open /var/lib/rag-conteneur.img rag-donnees
mkfs.ext4 -L rag-donnees /dev/mapper/rag-donnees
mkdir -p /srv/rag-donnees && mount /dev/mapper/rag-donnees /srv/rag-donnees
systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /var/lib/rag-conteneur.img
echo "rag-donnees /var/lib/rag-conteneur.img none luks,discard,tpm2-device=auto,nofail" >> /etc/crypttab
echo "/dev/mapper/rag-donnees /srv/rag-donnees ext4 defaults,nofail,x-systemd.device-timeout=30s 0 2" >> /etc/fstab
```

`cryptsetup` et `systemd-cryptenroll` acceptent directement le fichier ; au démarrage, systemd le présente lui-même comme un disque (périphérique de bouclage `loop0`) avant de le déchiffrer. Dans `/etc/crypttab`, la source est le **chemin du fichier**, pas un UUID. La condition de démarrage de Docker est la même qu'en §15.3.3. Le script de secours, lui, lit un UUID dans `/etc/crypttab` : pour un conteneur, y remplacer la ligne `cryptsetup open` par `cryptsetup status rag-donnees >/dev/null 2>&1 || cryptsetup open /var/lib/rag-conteneur.img rag-donnees`.

**Validé dans le lab (24 octobre 2026) :** A porte la stack ; B a été monté à côté, sur un autre point de montage. Redémarrage avec la stack en service : les deux volumes déverrouillés par le TPM sans saisie, le partage de fichiers monté après le volume chiffré (ses identifiants y sont, §0 étape 5), Docker démarré sur le volume monté, les cinq conteneurs repartis seuls, `/sante` à `ok`, test de non-divulgation 79 OK, 2 INFO. La mise à jour de la liste de révocation du Secure Boot a été appliquée puis récupérée sur les deux volumes (§15.3.3).

> **Une erreur des écritures directes, non expliquée.** Sur les deux volumes chiffrés, une écriture qui contourne le cache (`dd … oflag=direct`) échoue aussitôt en erreur d'entrée-sortie, sans message du noyau ; les écritures ordinaires passent. Le disque système non chiffré n'est pas touché, et le contrôleur de disque n'y est pour rien. La stack n'utilise pas ce mode d'écriture : Qdrant, Open WebUI et n8n fonctionnent normalement dans le lab. Cause non identifiée (point ouvert du suivi).

Pour une installation **existante**, déjà en service : voir la migration de §15.3.4 et §15.3.6.

---

[Retour au sommaire](index.md) | [Section précédente : §0 Démarrage rapide](section-00-quickstart.md) | [Section suivante : §2 Le serveur de modèles : Ollama ou vLLM](section-02-vllm.md)

---

*Validé sur VM-RAG-LAB, Ubuntu 26.04 LTS (resolute), août 2026. Commandes testées en mode CPU sans GPU.*
