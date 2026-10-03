---
title: "§15 Sécurité des données | Guide de déploiement stack IA locale"
description: "Protection des données de la stack RAG : clé d'API Qdrant, chiffrement des données au repos sur un disque dédié LUKS2 avec déverrouillage par TPM, migration des données, composants abandonnés, sauvegardes."
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

# §15 Sécurité des données

[Retour au sommaire](index.md) | [Section précédente : §14 Documents protégés par Purview](section-14-purview.md)

**Statut :** clé d'API Qdrant et chiffrement des données au repos validés en lab sur VM-RAG-LAB, octobre 2026, y compris un arrêt brutal de l'hôte. Sauvegardes chiffrées : exigence documentée, **non validée en lab**.

---

> **Ce que cette section documente :** une base vectorielle n'est pas un index abstrait. **Qdrant stocke le texte des chunks**, c'est-à-dire des extraits de tous les documents indexés, partage SMB et SharePoint compris, et, si §14 est mise en œuvre, le contenu déchiffré de documents protégés. Cette section protège ces données contre deux menaces : l'accès non authentifié à la base, et la copie ou le vol des disques. Elle concerne **tous** les déploiements, avec ou sans Purview.

---

## §15.1 Ce qu'il faut protéger

| Données | Emplacement par défaut | Contenu sensible |
|---|---|---|
| Qdrant | `/root/rag-stack/qdrant_data` | Texte des chunks, permissions, instantanés |
| Open WebUI | `/root/rag-stack/openwebui_data` | Comptes, **historique des conversations** : les réponses citent les documents |
| n8n | `/root/rag-stack/n8n_data` | Identifiants (SMTP), workflows avec jetons |
| Journaux | `/var/log/rag` | Empreintes des questions, noms et chemins des documents consultés |

L'historique d'Open WebUI est souvent oublié : une réponse qui cite un contrat est enregistrée en clair dans sa base. Sa durée de conservation est à définir dans la politique nLPD de l'organisation.

| Menace | Protection |
|---|---|
| Accès à Qdrant depuis le réseau Docker ou la VM | Clé d'API (§15.2) |
| Copie ou vol du disque, des fichiers de la VM, d'une sauvegarde | Chiffrement au repos (§15.3), sauvegardes chiffrées (§15.5) |
| Compromission de la VM en fonctionnement, avec des droits root | **Aucune** : le disque est déverrouillé et les données sont en mémoire. C'est la limite de fond de toute solution de ce type |

---

## §15.2 Clé d'API Qdrant

Qdrant auto-hébergé n'exige aucune authentification par défaut. Le port n'est publié que sur la boucle locale (§9), mais tout conteneur du réseau Docker peut lire et écrire dans la base.

### §15.2.1 Mise en place

```bash
cd /root/rag-stack
grep -q '^QDRANT_API_KEY=' .env || echo "QDRANT_API_KEY=$(openssl rand -hex 32)" >> .env
```

Le `docker-compose.yml` du dépôt transmet la clé aux deux services : `QDRANT__SERVICE__API_KEY` pour Qdrant, `QDRANT_API_KEY` pour `rag-api`. Les scripts (`main.py`, `indexer.py`, `acl_resolver.py`, `sp_indexer.py`) la lisent dans `QDRANT_API_KEY`, et `main.py` la transmet aux indexeurs lancés par `/admin/sync`. Une variable vide désactive la clé : les scripts restent compatibles avec une installation antérieure.

```bash
docker compose up -d --build qdrant rag-api
```

Les données de Qdrant ne sont pas modifiées par l'ajout de la clé.

### §15.2.2 Validation

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:6333/collections          # attendu : 401
CLE=$(grep '^QDRANT_API_KEY=' /root/rag-stack/.env | cut -d= -f2-)
curl -s -o /dev/null -w "%{http_code}\n" -H "api-key: $CLE" http://localhost:6333/collections   # attendu : 200
```

Puis une synchronisation complète par n8n : elle fait travailler les trois indexeurs avec la clé.

**Toutes les commandes `curl` vers Qdrant** doivent désormais envoyer l'en-tête `api-key`.

---

## §15.3 Chiffrement des données au repos

### §15.3.1 Principe

Les données de §15.1 sont déplacées sur un **disque virtuel dédié, chiffré avec LUKS2**, monté sur `/srv/rag-donnees`. Le système reste sur son disque, sans réinstallation.

| Méthode de déverrouillage | Protège contre | Inconvénient |
|---|---|---|
| **TPM** (retenu), phrase secrète en clé de secours | Vol ou copie du disque, des fichiers de la VM, d'une sauvegarde | Ne protège pas contre le vol de la machine entière, qui redémarre et se déverrouille seule |
| Phrase secrète seule, saisie en SSH | Les mêmes, et le vol de la machine entière | Intervention manuelle à chaque démarrage |
| Serveur Tang (Clevis) | Tout ce qui sort du réseau de l'entreprise | Un service de plus à héberger. Non testé en lab |
| Fichier de clé sur le disque système | Presque rien : la clé est volée avec la machine | Déconseillé |

Le TPM exige une machine en **UEFI avec un TPM 2.0**. La phrase secrète reste indispensable en clé de secours : une mise à jour du micrologiciel ou un changement de configuration du démarrage sécurisé peut empêcher le TPM de libérer la clé.

### §15.3.2 Créer le disque chiffré

**Identifier le disque juste avant chaque commande destructrice.** Sur une machine à plusieurs disques NVMe, les noms (`nvme0n1`, `nvme0n2`) peuvent **s'inverser d'un démarrage à l'autre** : le lab l'a constaté deux fois en une journée. Ne jamais recopier un nom de disque d'une sortie précédente.

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT     # le nouveau disque : bonne taille, aucune partition
wipefs -n /dev/<disque>                       # attendu : aucune sortie
```

**La phrase secrète** : cinq ou six mots tirés au hasard, séparés par des tirets, avec un chiffre. LUKS2 utilise Argon2id, qui rend chaque essai coûteux. Éviter les caractères dont la place change selon la disposition du clavier (pas de y, de z, d'accents ni de caractères spéciaux autres que le tiret), et la ranger dans un gestionnaire de mots de passe **avant** le formatage.

```bash
apt install -y cryptsetup tpm2-tools
cryptsetup luksFormat --type luks2 /dev/<disque>     # confirmer par YES, puis la phrase deux fois
cryptsetup open /dev/<disque> rag-donnees
mkfs.ext4 -L rag-donnees /dev/mapper/rag-donnees
mkdir -p /srv/rag-donnees && mount /dev/mapper/rag-donnees /srv/rag-donnees
```

### §15.3.3 Inscrire le TPM et configurer le démarrage

```bash
UUID=$(cryptsetup luksUUID /dev/<disque>)
systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /dev/disk/by-uuid/$UUID   # demande la phrase
cryptsetup luksDump /dev/disk/by-uuid/$UUID | grep -A3 -E "^Keyslots|^Tokens"  # 2 emplacements, jeton systemd-tpm2

echo "rag-donnees UUID=$UUID none luks,discard,tpm2-device=auto,nofail" >> /etc/crypttab
echo "/dev/mapper/rag-donnees /srv/rag-donnees ext4 defaults,nofail,x-systemd.device-timeout=30s 0 2" >> /etc/fstab
```

`--tpm2-pcrs=7` lie la clé à l'état du démarrage sécurisé : c'est le choix le plus stable, qui ne casse pas à chaque mise à jour du noyau. `nofail` garantit que le démarrage ne se bloque jamais si le disque ne s'ouvre pas.

**Docker ne doit démarrer qu'avec le disque monté, sans déclencher lui-même le déverrouillage :**

```bash
mkdir -p /etc/systemd/system/docker.service.d
printf '[Unit]\nAfter=srv-rag\\x2ddonnees.mount var-log-rag.mount\nConditionPathIsMountPoint=/srv/rag-donnees\n' \
  > /etc/systemd/system/docker.service.d/rag-donnees.conf
systemctl daemon-reload
```

Sans cette condition, Docker démarrerait sur un disque absent et créerait des dossiers **vides** : Qdrant repartirait avec une base vide. Ne pas utiliser `RequiresMountsFor`, qui ne se contente pas d'attendre le montage : il le **déclenche**, et provoque une demande de phrase à la console à chaque démarrage.

**Le déverrouillage de secours**, si le TPM refuse un jour la clé :

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
systemctl start docker
echo "Disque déverrouillé et monté, Docker démarré"
EOF
chmod 700 /usr/local/sbin/rag-deverrouiller
```

À lancer **seul**, en SSH : une commande qui demande un mot de passe ne doit jamais être collée avec d'autres, qui seraient lues comme la phrase.

### §15.3.4 Migrer les données existantes

```bash
cd /root/rag-stack && docker compose down
mkdir -p /srv/rag-donnees/{qdrant_data,openwebui_data,n8n_data,log-rag}
rsync -aHAXS --numeric-ids /root/rag-stack/qdrant_data/    /srv/rag-donnees/qdrant_data/
rsync -aHAXS --numeric-ids /root/rag-stack/openwebui_data/ /srv/rag-donnees/openwebui_data/
rsync -aHAXS --numeric-ids /root/rag-stack/n8n_data/       /srv/rag-donnees/n8n_data/
rsync -aHAXS --numeric-ids /var/log/rag/                   /srv/rag-donnees/log-rag/
du -sh /root/rag-stack/{qdrant_data,openwebui_data,n8n_data} /srv/rag-donnees/*   # tailles comparables
```

L'option **`-S`** est indispensable pour Qdrant, qui réserve d'avance de grands fichiers en grande partie vides (fichiers creux). Sans elle, ces zones sont recopiées en vrais zéros : dans le lab, 80 Mo sont devenus 609 Mo. `--numeric-ids` conserve les propriétaires exacts, nécessaires à n8n.

```bash
# Le Compose pointe vers le disque chiffré
cp docker-compose.yml docker-compose.yml.avant-chiffrement
sed -i 's|- \./qdrant_data:|- /srv/rag-donnees/qdrant_data:|; s|- \./openwebui_data:|- /srv/rag-donnees/openwebui_data:|; s|- \./n8n_data:|- /srv/rag-donnees/n8n_data:|' docker-compose.yml

# /var/log/rag redirigé vers le disque chiffré
mv /var/log/rag /var/log/rag.ancien && mkdir /var/log/rag
echo "/srv/rag-donnees/log-rag /var/log/rag none bind,nofail,x-systemd.requires-mounts-for=/srv/rag-donnees 0 0" >> /etc/fstab
systemctl daemon-reload && mount /var/log/rag

# Anciens dossiers mis de côté, pas supprimés
mv qdrant_data qdrant_data.ancien; mv openwebui_data openwebui_data.ancien; mv n8n_data n8n_data.ancien
docker compose up -d
```

Valider (compteurs de chunks identiques, historique Open WebUI présent, synchronisation n8n réussie, redémarrage complet sans intervention), **puis seulement** supprimer les dossiers `.ancien`.

> **Limite :** la suppression ne garantit pas l'effacement des anciens blocs du disque système, et `fstrim` peut rester sans effet selon la couche de stockage. C'est pourquoi le chiffrement au repos doit être mis en place **avant** l'indexation de contenus sensibles, en particulier avant §14.

### §15.3.5 Validation

```bash
reboot
# puis, en SSH, sans rien lancer :
df -h /srv/rag-donnees /var/log/rag            # montés, depuis /dev/mapper/rag-donnees
docker compose -f /root/rag-stack/docker-compose.yml ps   # tous les conteneurs démarrés
```

Dans le lab, la configuration a aussi passé un **arrêt brutal de l'hôte** : au redémarrage, le TPM a déverrouillé le disque, la stack est repartie seule, et aucune erreur de système de fichiers n'a été signalée.

### §15.3.6 Pièges rencontrés

| Piège | Symptôme | Correction |
|---|---|---|
| Phrase demandée à la console pendant le mode de secours | Deux programmes lisent le clavier : caractères perdus ou dédoublés, phrase refusée | Ne jamais saisir la phrase à cette invite ; utiliser le shell de maintenance, puis TPM ou déverrouillage en SSH |
| `RequiresMountsFor` dans l'unité Docker | Demande de phrase à chaque démarrage, malgré `noauto` | `After` + `ConditionPathIsMountPoint` |
| `rsync` sans `-S` | Qdrant multiplié par sept sur le nouveau disque | `rsync -aHAXS` |
| Noms NVMe inversés | Risque de formater le mauvais disque | `lsblk` juste avant, UUID partout ailleurs |
| Commandes collées avec une saisie de mot de passe | Les lignes suivantes lues comme la phrase | Lancer la commande seule |

---

## §15.4 Composants abandonnés

Remplacer un composant n'efface pas ses données. Le lab l'a illustré après un pilote abandonné : une plateforme RAG testée puis remplacée avait laissé dix volumes Docker, dont son index de recherche (texte des documents découpé), son stockage de fichiers et sa base de données, et environ 20 Go d'images. Soit une copie du corpus, **hors du cloisonnement et hors du chiffrement**, oubliée depuis des semaines. Sa suppression a libéré 28 Go.

```bash
docker volume ls                                # volumes sans conteneur associé ?
docker ps -a                                    # conteneurs arrêtés mais présents
docker images                                   # images d'outils qui ne sont plus utilisés
du -sh /root/* /home/* 2>/dev/null              # dépôts clonés, dossiers de données oubliés
```

Le même inventaire vaut côté Entra : une application d'un pilote abandonné garde ses autorisations et son certificat valide (§13.8.3).

---

## §15.5 Sauvegardes chiffrées

> **Non validées en lab.** La nLPD n'impose pas nommément le chiffrement des sauvegardes, mais son devoir de sécurité exige des mesures appropriées au risque. Une sauvegarde contient les mêmes données que le disque chiffré : la laisser en clair annule la protection, d'autant qu'elle est souvent stockée hors du serveur.

Ce qu'une sauvegarde doit contenir, et ce qu'elle implique :

| Élément | Remarque |
|---|---|
| Instantanés Qdrant (`POST /collections/<nom>/snapshots`, avec la clé d'API) | Texte des chunks : sensibilité maximale |
| `openwebui_data`, `n8n_data` | Historique des conversations, identifiants |
| `.env` et `/etc/rag-certs` | **Secrets** : à sauvegarder à part, ou à régénérer plutôt qu'à copier |

Les sauvegardes doivent être chiffrées avant de quitter le serveur, avec une clé conservée hors du serveur, et leur restauration testée. Le choix de l'outil (par exemple `restic`, qui chiffre nativement) sera documenté après validation en lab.

---

## §15.6 Checklist

| Point | Vérification | Attendu |
|---|---|---|
| Clé Qdrant active | `curl http://localhost:6333/collections` sans en-tête | HTTP 401 |
| Clé Qdrant transmise | Synchronisation complète par n8n | Succès, aucune erreur 401 |
| Disque chiffré | `lsblk -o NAME,FSTYPE,MOUNTPOINT` | `crypto_LUKS`, `rag-donnees` monté sur `/srv/rag-donnees` |
| Clés LUKS | `cryptsetup luksDump` | Deux emplacements (phrase, TPM), jeton `systemd-tpm2` |
| Phrase de secours | Gestionnaire de mots de passe | Enregistrée, testée avec `rag-deverrouiller` |
| Données migrées | `grep rag-donnees docker-compose.yml`, `findmnt /var/log/rag` | Trois volumes et les journaux sur le disque chiffré |
| Démarrage | Redémarrage sans intervention | Disque monté, conteneurs démarrés |
| Anciennes données | `ls /root/rag-stack`, `docker volume ls` | Plus de copie en clair, aucun reste de composant abandonné |
| Sauvegardes | Procédure de l'organisation | Chiffrées, restauration testée |

---

[Retour au sommaire](index.md) | [Section précédente : §14 Documents protégés par Purview](section-14-purview.md)

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
