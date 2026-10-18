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

[Retour au sommaire](index.md) | [Section précédente : §14 Documents protégés par Purview](section-14-purview.md) | [Section suivante : §16 Contrôle du cloisonnement et durcissement](section-16-cloisonnement.md)

**Statut :** clé d'API Qdrant, chiffrement des données au repos, et déplacement des secrets et des clés sur le disque chiffré validés en lab sur VM-RAG-LAB, octobre 2026, y compris un arrêt brutal de l'hôte et un redémarrage complet. Sauvegardes chiffrées : exigence documentée, **non validée en lab**.

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
| Secrets | `/root/rag-stack/.env` | Mots de passe LDAP et SMB, jetons, clé Qdrant, clé des empreintes |
| Clés privées | `/etc/rag-certs` | Identités des applications Entra, dont celle qui peut déchiffrer tout le contenu protégé du tenant (§14) |

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
cryptsetup luksDump /dev/disk/by-uuid/$UUID | grep -E "^  [0-9]+: (luks2|systemd-tpm2)"  # 2 x luks2, 1 x systemd-tpm2

echo "rag-donnees UUID=$UUID none luks,discard,tpm2-device=auto,nofail" >> /etc/crypttab
echo "/dev/mapper/rag-donnees /srv/rag-donnees ext4 defaults,nofail,x-systemd.device-timeout=30s 0 2" >> /etc/fstab
```

**Attendu** pour la ligne de contrôle : deux lignes `luks2` (les emplacements 0, la phrase, et 1, le TPM) et une ligne `systemd-tpm2` (le jeton). Avec l'ancien filtre `grep -A3`, seul le premier emplacement s'affichait, ce qui laissait croire que l'inscription du TPM avait échoué. `systemd-cryptenroll` confirme de lui-même : « New TPM2 token enrolled as key slot 1 ».

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

Pour une **nouvelle** installation, cette migration n'a pas lieu d'être : le disque chiffré et les liens sont préparés avant le déploiement (§1.5).

> **Limite :** la suppression ne garantit pas l'effacement des anciens blocs du disque système, et `fstrim` peut rester sans effet selon la couche de stockage. C'est pourquoi le chiffrement au repos doit être mis en place **avant** l'indexation de contenus sensibles, en particulier avant §14.

### §15.3.5 Validation

```bash
reboot
# puis, en SSH, sans rien lancer :
df -h /srv/rag-donnees /var/log/rag            # montés, depuis /dev/mapper/rag-donnees
docker compose -f /root/rag-stack/docker-compose.yml ps   # tous les conteneurs démarrés
getent hosts <NOM-DC>.votre-domaine.ch <NOM-FILESERVER>   # les noms du domaine se résolvent
```

`rag-api` et `open-webui` apparaissent en `Up (healthy)`, `qdrant` et `n8n` en `Up` : seuls les deux premiers déclarent un contrôle de santé. Le contrôle des noms n'est pas superflu : dans le rejeu d'octobre 2026, un DNS public ajouté à la configuration de la VM a fait échouer LDAP et la lecture des droits au deuxième redémarrage, alors que le premier s'était bien passé (§0, « En cas de problème »).

Sur une VM neuve (octobre 2026), un simple `reboot` a suffi : disque ouvert par le TPM sans saisie, monté sur `/srv/rag-donnees`, Docker actif. Dans le lab, la configuration a aussi passé un **arrêt brutal de l'hôte** : au redémarrage, le TPM a déverrouillé le disque, la stack est repartie seule, et aucune erreur de système de fichiers n'a été signalée.

### §15.3.6 Secrets et clés privées

Chiffrer les données sans chiffrer les secrets laisse sur le disque système de quoi y accéder : le `.env` et les clés privées des applications Entra. Le lab l'a constaté après coup : `.env` et `/etc/rag-certs` étaient restés sur le disque système, et le `.env` était lisible par tous les comptes de la VM (`644`).

```bash
chmod 600 /root/rag-stack/.env              # avant le déplacement : mv conserve les droits
cd /root/rag-stack && docker compose down
mkdir -p /srv/rag-donnees/secrets && chmod 700 /srv/rag-donnees/secrets
mv /root/rag-stack/.env /srv/rag-donnees/secrets/.env
ln -s /srv/rag-donnees/secrets/.env /root/rag-stack/.env
mv /etc/rag-certs /srv/rag-donnees/secrets/rag-certs        # conserve propriétaires et droits
ln -s /srv/rag-donnees/secrets/rag-certs /etc/rag-certs
ls -l /root/rag-stack/.env /etc/rag-certs
ls -ln /srv/rag-donnees/secrets/ /srv/rag-donnees/secrets/rag-certs/
docker compose up -d
```

Attendu : deux liens vers `/srv/rag-donnees/secrets/`, le `.env` en `-rw-------`, les clés en `-rw-------` (la clé de `mip-service` appartenant à `10001`). Le dossier `secrets` en `700` ne gêne pas `mip-service` : Docker monte le fichier de clé directement dans le conteneur, où seuls les droits du fichier comptent.

Valider par une synchronisation (qui lit les clés SharePoint et Purview), une synthèse Teams, puis un redémarrage complet de la VM. La même limite qu'en §15.3.4 s'applique : les anciens blocs restent sur le disque système. C'est la raison de §1.5.

> **Le `.env` est lu par Docker Compose, pas par les applications**, et seulement à la **création** des conteneurs. Après une modification du `.env`, `docker compose up -d <service>` recrée le conteneur avec les nouvelles valeurs ; `docker compose restart` et `docker restart` redémarrent l'ancien conteneur, **avec les anciennes valeurs**, sans aucun message. Pour vérifier sans afficher le secret : `docker exec rag-api printenv ADMIN_TOKEN | cut -c1-8`, à comparer au début de la valeur du `.env`.

### §15.3.7 Pièges rencontrés

| Piège | Symptôme | Correction |
|---|---|---|
| Phrase demandée à la console pendant le mode de secours | Deux programmes lisent le clavier : caractères perdus ou dédoublés, phrase refusée | Ne jamais saisir la phrase à cette invite ; utiliser le shell de maintenance, puis TPM ou déverrouillage en SSH |
| `RequiresMountsFor` dans l'unité Docker | Demande de phrase à chaque démarrage, malgré `noauto` | `After` + `ConditionPathIsMountPoint` |
| `rsync` sans `-S` | Qdrant multiplié par sept sur le nouveau disque | `rsync -aHAXS` |
| Noms NVMe inversés | Risque de formater le mauvais disque | `lsblk` juste avant, UUID partout ailleurs |
| Commandes collées avec une saisie de mot de passe | Les lignes suivantes lues comme la phrase | Lancer la commande seule |
| `docker compose restart` après une modification du `.env` | Ancienne valeur toujours active, sans erreur | `docker compose up -d <service>` (§15.3.6) |

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

> **Non validées en lab.** La nLPD n'impose pas nommément le chiffrement des sauvegardes, mais son devoir de sécurité exige des mesures appropriées au risque. Une sauvegarde contient les mêmes données que le disque chiffré : la laisser en clair annule la protection, d'autant qu'elle est souvent stockée hors du serveur. La procédure ci-dessous décrit l'approche retenue ; **elle n'a pas été rejouée en lab**, et le test de restauration de la fin de cette section est à faire avant de la déclarer validée.
>
> **Choix assumé (2.21.0) :** la sauvegarde de la VM relève de l'outil et des procédures de l'organisation, qui sait sauvegarder et restaurer ses machines virtuelles. Ce guide décrit ce qu'elle doit couvrir et comment la tester ; il ne la met pas en place. Seuls les snapshots Qdrant (§3.7) ont été validés en lab, restauration comprise.

### L'approche retenue : la sauvegarde de la VM entière

La plupart des entreprises disposent déjà d'un outil de sauvegarde de machines virtuelles (par exemple Veeam), avec chiffrement des fichiers de sauvegarde. Ce guide s'appuie sur lui plutôt que sur une procédure propre à la stack : la VM est sauvegardée et restaurée d'un bloc, avec le disque chiffré de §15.3. Cette approche est courante, à condition de traiter les quatre points ci-dessous, qui tiennent à la façon dont la stack est construite.

### Ce que la sauvegarde contient, et ce qui se reconstruit

| Élément | Où | Reconstructible ? |
|---|---|---|
| Index Qdrant (texte des chunks, permissions) | `qdrant_data`, sur le disque chiffré | **Oui, à partir des sources** : le serveur de fichiers et SharePoint font foi. Il suffit de relancer l'indexation et la synchronisation des droits (§0, étapes 12 et 13). Le temps nécessaire dépend du corpus et n'a pas été mesuré pour une restauration |
| Index BM25 | En mémoire de la RAG API | Oui : reconstruit à chaque démarrage et après chaque synchronisation |
| Open WebUI (comptes, historique des conversations) | `openwebui_data` | **Non** |
| n8n (workflows, identifiants) | `n8n_data` | **Non** (les workflows sont aussi dans le dépôt, les identifiants non) |
| `.env`, `/etc/rag-certs` (clés des applications Entra) | Disque chiffré | Non pour le `.env` ; les certificats se régénèrent mais exigent de les réinscrire dans les App Registrations |
| `/etc/rag-tls` (certificat et clé de Nginx, §9.8) | Disque chiffré | Oui : nouvelle demande à l'autorité interne (§9.8.6), ou auto-signé régénéré par `deploy.sh` |
| Phrase secrète du disque (§15.3) | **Hors de la VM** | Non : sans elle, la restauration ne sert à rien |

Seuls Open WebUI, n8n et les secrets déterminent donc la perte tolérable. L'index, lui, se reconstruit.

### Quatre points propres à la stack

**1. La cohérence de la sauvegarde.** Une sauvegarde de VM prise pendant que la stack tourne est « crash-consistent » : équivalente à l'état après une coupure de courant. Qdrant s'y rétablit normalement grâce à son journal d'écriture, mais Open WebUI et n8n utilisent par défaut des bases locales (SQLite) qui peuvent être copiées en cours d'écriture. Deux précautions possibles, selon l'outil et l'hyperviseur (à vérifier dans leur documentation) :

- le traitement tenant compte des applications, ou des scripts de pré-gel et de post-dégel de l'outil de sauvegarde, qui arrêtent brièvement les conteneurs (`docker compose stop` avant, `docker compose start` après) ;
- ou une fenêtre de sauvegarde qui évite la synchronisation horaire du corpus (workflow n8n) et les heures d'usage.

**2. Le disque chiffré à la restauration.** Le déverrouillage automatique repose sur le TPM virtuel de la VM (§15.3). Sur une VM restaurée, en particulier sur un autre hôte, le TPM peut être différent : le déverrouillage automatique échoue, et il faut la phrase secrète. La procédure de restauration doit donc prévoir : phrase conservée dans un coffre hors de la VM, déverrouillage par `rag-deverrouiller` (§15.3) lancé seul en SSH, puis ré-inscription du TPM (`systemd-cryptenroll`) si l'on veut retrouver le démarrage sans intervention. Ce comportement dépend de l'hyperviseur et **n'a pas été testé**.

**3. Ce qui n'est pas dans la VM.** La sauvegarde de la VM ne contient pas :

- la configuration du serveur de modèles : variables d'Ollama, services et fichier de clé d'API de vLLM (`/etc/vllm/vllm.env`, §2.4.4), les modèles eux-mêmes (retéléchargeables) ;
- le compte `svc-rag`, ses groupes et le certificat de l'autorité de l'AD ;
- les App Registrations Entra et leurs certificats si la Partie 3 est utilisée.

Ces éléments appartiennent aux systèmes qui les portent et se sauvegardent avec eux. Dresser la liste de ce qu'il faut pouvoir recréer fait partie du dossier d'exploitation.

**4. Le chiffrement et la durée de conservation.** Le fichier de sauvegarde contient le texte extrait de tous les documents indexés, y compris ceux dont l'accès est cloisonné. Il doit donc être chiffré par l'outil de sauvegarde, avec un mot de passe ou une clé conservés **hors** de la sauvegarde elle-même. Sa durée de conservation doit être décidée : une suppression à la source ne retire pas un document des sauvegardes déjà prises (§17.5).

### Le test de restauration, à rejouer

Une sauvegarde n'est validée qu'une fois restaurée. Dans le lab :

1. Relever les compteurs avant la sauvegarde :

```bash
for c in documents documentation; do
  echo -n "$c : "
  curl -s -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections/$c | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['points_count'])"
done
```

2. Sauvegarder la VM avec l'outil de l'organisation, chiffrement activé.
3. Restaurer la VM sous un autre nom, réseau isolé de la production.
4. Si le disque ne se déverrouille pas seul : lancer `rag-deverrouiller` seul, en SSH, avec la phrase secrète.
5. Vérifier que les conteneurs sont démarrés (`docker compose ps`), refaire les compteurs du point 1, puis poser une question dans Open WebUI avec un compte de test.
6. Noter la durée totale et tout ce qui a demandé une intervention.

**Attendu :** mêmes compteurs qu'avant la sauvegarde, comptes et historique d'Open WebUI présents, workflows n8n présents, réponse correcte à la question. Si les compteurs diffèrent, relancer la synchronisation (§0, étape 13) et relever les compteurs de nouveau.

> **Après une restauration :** relancer `acl_resolver.py` pour vérifier que les droits sont cohérents avec les permissions actuelles du serveur de fichiers. Une sauvegarde peut dater de plusieurs heures, et des permissions modifiées entre-temps ne seraient pas reflétées (§3.6).

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
| Secrets et clés | `ls -l /root/rag-stack/.env /etc/rag-certs` | Liens vers le disque chiffré, `.env` en `600`, clés en `600` |
| Démarrage | Redémarrage sans intervention | Disque monté, conteneurs démarrés |
| Anciennes données | `ls /root/rag-stack`, `docker volume ls` | Plus de copie en clair, aucun reste de composant abandonné |
| Sauvegardes | Sauvegarde de la VM chiffrée (§15.5), phrase du disque hors de la VM | Restauration testée : compteurs identiques, disque déverrouillé, réponse correcte |

---

[Retour au sommaire](index.md) | [Section précédente : §14 Documents protégés par Purview](section-14-purview.md) | [Section suivante : §16 Contrôle du cloisonnement et durcissement](section-16-cloisonnement.md)

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
