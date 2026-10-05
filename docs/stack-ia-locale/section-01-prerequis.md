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

[Retour au sommaire](index.md) | [Section précédente : §0 Déploiement complet](section-00-quickstart.md) | [Section suivante : §2 Installation et configuration de vLLM](section-02-vllm.md)

**Statut :** validé sur VM-RAG-LAB, septembre 2026.

---

## §1.1 Sizing de la VM

Ce guide a été validé sur la configuration suivante, dans VMware Workstation avec un hôte Intel Core i7-14700 (8 P-cores + 12 E-cores, 28 threads, 64 Go DDR5).

| Ressource | Minimum | Recommandé | Remarque |
|---|---|---|---|
| vCPU | 4 | 6 | Épingler sur P-cores physiques (voir §1.3) |
| RAM | 16 Go | 16 Go | Open WebUI + RAG API + Docker Compose complet : environ 8 à 10 Go en charge. Pour exécuter vLLM dans la VM, porter à 20 Go (voir §2) |
| Disque | 80 Go | 100 Go | Type NVMe recommandé dans VMware Workstation |
| Réseau | NAT | Réseau lab dédié | Un réseau lab donne accès aux ressources AD, SMB, DNS |

> **Note VMware Workstation :** choisir **1 processeur, 6 cœurs** (et non 2 processeurs × 3 cœurs). Un seul socket évite les problèmes de topologie NUMA que vLLM pourrait mal interpréter en mode CPU. Pour le disque virtuel, choisir **NVMe** et le pilote réseau **vmxnet3** plutôt que e1000.

---

## §1.2 Installation Ubuntu Server 26.04 LTS

Créer la VM dans VMware Workstation avec Ubuntu Server 26.04 LTS (nom de code : **resolute**). Lors de l'installation :

- Laisser LVM activé et étendre le volume après installation (voir ci-dessous). LVM est recommandé : il permet d'étendre le disque sans réinstallation si le corpus grossit.
- Activer OpenSSH lors de l'installation pour accéder à la VM depuis l'hôte.
- Configurer le réseau en mode statique si la VM doit rejoindre un réseau lab existant.

Une fois connecté en SSH, mettre à jour le système et installer les dépendances de base :

```bash
apt update && apt upgrade -y

apt install -y curl wget git python3-pip python3-venv \
  build-essential libssl-dev htop net-tools
```

### Extension du volume LVM (si LVM activé)

L'installateur Ubuntu n'alloue que 50% du groupe de volumes LVM par défaut. Étendre immédiatement après installation :

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

Versions validées sur cette configuration : **Docker 29.7.2**, **Docker Compose 5.5.0**.

---

## §1.5 Disque de données chiffré, avant le déploiement

**Statut :** principe et procédure de chiffrement validés en lab (§15.3) ; préparation **avant** le premier déploiement à valider sur une VM neuve.

La stack stocke des extraits de tous les documents indexés, l'historique des conversations, des identifiants et les clés privées des applications Entra. Tout cela doit être sur un disque chiffré **dès sa création** : un chiffrement ajouté après coup laisse des copies en clair sur le disque système, que la suppression n'efface pas (§15.3.4). Le disque chiffré se prépare donc **ici**, avant `deploy.sh`, avant que le `.env` et les clés n'existent.

| Plateforme | Solution | État |
|---|---|---|
| VM (Hyper-V, VMware, Proxmox) | Second disque virtuel, LUKS2, déverrouillage par TPM virtuel | Validé en lab |
| Serveur physique à deux disques | Même procédure sur le second disque, TPM matériel | Non testé sur matériel |
| DGX Spark (un seul disque interne) | Partition réservée à l'installation, ou conteneur LUKS dans un fichier | Non validé |

Le déverrouillage automatique exige une machine en **UEFI avec un TPM 2.0**. Selon l'hyperviseur, l'ajout d'un TPM virtuel peut exiger de chiffrer la VM elle-même. Sur le DGX Spark, la possibilité de réserver une partition à l'installation de DGX OS est à vérifier dans la documentation de NVIDIA ; un conteneur LUKS dans un fichier fonctionne sur tout Linux, sans repartitionner, au prix de performances un peu moindres.

**1. Créer, chiffrer et monter le disque** : procédure de §15.3.2 et §15.3.3 (LUKS2, inscription du TPM, `/etc/crypttab`, `/etc/fstab`, condition de démarrage de Docker, script de déverrouillage de secours).

**2. Préparer l'arborescence et les liens**, avant `deploy.sh` :

```bash
mkdir -p /srv/rag-donnees/{qdrant_data,openwebui_data,n8n_data,log-rag,secrets/rag-certs}
chmod 700 /srv/rag-donnees/secrets /srv/rag-donnees/secrets/rag-certs
mkdir -p /root/rag-stack
for d in qdrant_data openwebui_data n8n_data; do ln -s /srv/rag-donnees/$d /root/rag-stack/$d; done
ln -s /srv/rag-donnees/secrets/.env      /root/rag-stack/.env
ln -s /srv/rag-donnees/secrets/rag-certs /etc/rag-certs
ln -s /srv/rag-donnees/log-rag           /var/log/rag
ls -l /root/rag-stack /etc/rag-certs /var/log/rag
```

`deploy.sh` écrit ensuite le `.env`, les données et les journaux **à travers ces liens**, directement sur le disque chiffré. Les certificats des applications Entra, créés aux sections §11 à §14, iront de même dans `/etc/rag-certs`. Docker ne démarrant qu'avec le disque monté (§15.3.3), un lien sans sa cible ne peut pas se produire en fonctionnement normal.

> **Le groupe `docker` équivaut à root** : un compte qui en est membre peut lire toutes les variables des conteneurs (`docker inspect`) et monter n'importe quel fichier de la VM. N'y ajouter aucun compte ordinaire. La commande `usermod -aG docker $USER` de §1.4, exécutée en root, ne concerne que root.

Pour une installation **existante**, déjà en service : voir la migration de §15.3.4 et §15.3.6.

---

[Retour au sommaire](index.md) | [Section précédente : §0 Déploiement complet](section-00-quickstart.md) | [Section suivante : §2 Installation et configuration de vLLM](section-02-vllm.md)

---

*Validé sur VM-RAG-LAB, Ubuntu 26.04 LTS (resolute), août 2026. Commandes testées en mode CPU sans GPU.*
