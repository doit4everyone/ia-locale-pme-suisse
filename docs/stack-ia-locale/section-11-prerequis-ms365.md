---
title: "§11 Prérequis Microsoft 365 | Guide de déploiement stack IA locale"
description: "Connexion de la stack RAG à Microsoft Graph : App Registration par certificat, résolution des groupes Entra ID et mise à niveau compatible des scripts avant l'indexation SharePoint."
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

# §11 Prérequis Microsoft 365

[Retour au sommaire](index.md) | [Section précédente : §9 Sécurité](section-09-securite.md)

**Statut :** validé en lab sur VM-RAG-LAB, septembre 2026. Toutes les étapes de cette section ont été exécutées et testées sur un tenant Microsoft 365 réel synchronisé par Entra Connect. L'indexation des documents SharePoint n'est pas couverte ici : elle fait l'objet de §12 (à venir).

---

> **Ce que cette section documente :** les fondations de la Partie 3. La stack RAG apprend à interroger Microsoft Graph et à connaître les groupes Entra ID d'un utilisateur, en plus de ses groupes Active Directory. Les scripts existants sont mis à niveau pour cohabiter avec de futurs documents SharePoint, sans rien changer au fonctionnement de la stack SMB validée en Parties 1 et 2.

---

## §11.1 Architecture

### §11.1.1 Ce qui change, et ce qui ne change pas

La stack des Parties 1 et 2 cloisonne les documents du file server à partir des ACL NTFS : chaque chunk porte la liste des groupes AD autorisés (`autorises[]`), et `auth.py` résout les groupes AD de l'utilisateur par LDAP. Pour SharePoint, le principe reste identique, mais les permissions sont exprimées en identités Entra ID. Il faut donc que `auth.py` connaisse aussi les groupes Entra de l'utilisateur.

| Élément | Stack SMB (Parties 1 et 2) | Ajout Partie 3 |
|---|---|---|
| Source des permissions | ACL NTFS du file server | Permissions SharePoint (§12) |
| Format dans `autorises[]` | `DOMAINE\Groupe` | `entra:grp:<id>`, `entra:usr:<id>` |
| Résolution de l'utilisateur | LDAP sur le contrôleur de domaine | Microsoft Graph |
| Interface utilisateur | Open WebUI, authentification LDAP AD | Inchangée |

Les deux formats coexistent dans la même liste de groupes. Un chunk SMB ne contient que des groupes `DOMAINE\Groupe` : les identifiants Entra ajoutés à l'utilisateur ne lui donnent accès à aucun document SMB supplémentaire.

### §11.1.2 Le chemin réseau

La VM n'échange rien avec le serveur Entra Connect. Entra Connect synchronise l'AD vers Entra ID dans le cloud, et la VM interroge ensuite Entra ID par Microsoft Graph :

```
Active Directory → Entra Connect → Entra ID (cloud)
                                        ↑
VM-RAG-LAB (rag-api) → HTTPS 443 → login.microsoftonline.com (jeton)
                                 → graph.microsoft.com (groupes)
```

Le seul besoin réseau est une sortie HTTPS vers ces deux points de terminaison, depuis la VM et depuis le conteneur `rag-api`.

### §11.1.3 Pourquoi l'extension Entra est nécessaire, même avec un AD synchronisé

On pourrait penser que, si tous les groupes viennent de l'AD, la résolution LDAP suffit aussi pour SharePoint. Le test de §11.6 montre le contraire : pour le compte `test-client`, LDAP trouve deux groupes, Graph en trouve trois. Le troisième, « Tous les utilisateurs », est un groupe dynamique créé dans Entra ID, qui n'existe pas dans l'AD. Les groupes Microsoft 365, les groupes créés depuis Teams et les groupes dynamiques ne sont visibles que dans Entra ID. Un site SharePoint partagé avec l'un d'eux ne peut être cloisonné correctement qu'avec la résolution Graph.

---

## §11.2 Prérequis

### §11.2.1 Tenant et synchronisation

- Un tenant Microsoft 365 avec des droits d'administration Entra ID.
- Entra Connect (ou Cloud Sync) actif, qui synchronise les utilisateurs et groupes de l'AD.
- Le suffixe UPN utilisé par les comptes AD (ici `bsculier.ch`) déclaré comme domaine vérifié dans le tenant. Sans cela, l'UPN transmis par Open WebUI ne correspond à aucun compte dans Entra ID.

Vérification dans le centre d'administration Entra : **Utilisateurs** → le compte de test → le nom d'utilisateur principal doit être identique à celui utilisé dans Open WebUI, et l'onglet **Propriétés** doit indiquer que la synchronisation locale est activée.

### §11.2.2 Connectivité et heure système

Depuis la VM :

```bash
curl -sI https://login.microsoftonline.com | head -1
curl -sI https://graph.microsoft.com/v1.0/ | head -1
docker exec rag-api python3 -c "import httpx; print(httpx.get('https://graph.microsoft.com/v1.0/').status_code)"
timedatectl | grep -E "synchronized|NTP"
```

Résultat obtenu en lab :

```
HTTP/1.1 200 OK
HTTP/1.1 405 Method Not Allowed
200
System clock synchronized: yes
              NTP service: active
```

Le code `405` sur la deuxième ligne est normal : `curl -I` envoie une requête HEAD, que Graph refuse. Seule compte l'obtention d'une réponse HTTP. La troisième ligne confirme que le conteneur atteint Graph (DNS et sortie Internet depuis le réseau Docker).

> **L'heure système n'est pas un détail.** L'authentification par certificat repose sur une assertion signée et horodatée. Un décalage de quelques minutes entre la VM et Microsoft suffit à faire rejeter le jeton, avec un message d'erreur peu explicite. La synchronisation NTP doit être active.

---

## §11.3 Certificat de l'application

L'application s'authentifie auprès d'Entra ID par certificat, sans secret client. La clé privée est générée sur la VM et n'en sort jamais : seule la partie publique est chargée dans Entra ID.

```bash
sudo mkdir -p /etc/rag-certs && sudo chmod 700 /etc/rag-certs
cd /etc/rag-certs
sudo openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout rag-identity.key -out rag-identity.crt \
  -days 730 -subj "/CN=RAG-Identity-Resolver"
sudo chmod 600 rag-identity.key

# Partie publique à charger dans Entra ID
sudo cat rag-identity.crt

# Empreinte SHA-1, pour contrôle après chargement
openssl x509 -in rag-identity.crt -noout -fingerprint -sha1
```

Copier le bloc affiché par `cat`, de `-----BEGIN CERTIFICATE-----` à `-----END CERTIFICATE-----` inclus, dans un fichier `rag-identity.crt` sur le poste d'administration. Ce fichier ne contient que la partie publique et peut circuler sans risque.

> **Échéance à suivre :** le certificat est valable deux ans. À son expiration, la résolution Entra échoue et les utilisateurs perdent l'accès aux documents SharePoint (l'accès SMB n'est pas affecté, voir §11.5.2). Le renouvellement est à planifier au même titre que la rotation du mot de passe de `svc-rag` (§9.5.1).

---

## §11.4 App Registration de résolution d'identité

### §11.4.1 Deux applications, deux rôles

La Partie 3 utilise deux App Registrations distinctes, chacune limitée aux droits de sa fonction :

| Application | Rôle | Permissions Graph (application) | Section |
|---|---|---|---|
| `RAG-Identity-Resolver` | `auth.py` : résoudre les groupes Entra d'un utilisateur | `User.Read.All`, `GroupMember.Read.All` | §11 |
| `RAG-SharePoint-Indexer` | Indexeur SharePoint : lire les documents et leurs permissions | `Sites.Selected`, accordée site par site | §12 |

Séparer les deux limite l'impact d'une compromission : le certificat de résolution d'identité ne donne accès à aucun document, et celui de l'indexeur ne donne pas accès à l'annuaire complet.

> **Ne jamais utiliser `Sites.Read.All`** pour l'indexation : cette permission donne accès à tous les sites du tenant, y compris ceux qui ne doivent pas être indexés. Si une ancienne inscription dispose de cette permission, elle doit être supprimée, ainsi que l'application d'entreprise associée.

### §11.4.2 Création

Dans le centre d'administration Entra (entra.microsoft.com) :

1. **Applications** → **Inscriptions d'applications** → **+ Nouvelle inscription**.
   - Nom : `RAG-Identity-Resolver`
   - Types de comptes pris en charge : **Comptes dans cet annuaire d'organisation uniquement**
   - URI de redirection : laisser vide
   - **S'inscrire**
2. Sur la page **Vue d'ensemble**, noter l'**ID d'application (client)** et l'**ID de l'annuaire (locataire)**.
3. **Certificats et secrets** → onglet **Certificats** → **Charger le certificat** → `rag-identity.crt`. Vérifier que l'empreinte affichée correspond à celle calculée en §11.3.
4. **Autorisations de l'API** → **Ajouter une autorisation** → **Microsoft Graph** → **Autorisations d'application** → cocher `User.Read.All` et `GroupMember.Read.All` → **Ajouter des autorisations**.
5. **Accorder un consentement d'administrateur** → confirmer. Les deux permissions doivent passer à l'état « Accordé ».
6. Supprimer la permission déléguée `User.Read` ajoutée par défaut : elle ne sert à rien pour une application sans utilisateur connecté.

Aucun secret client ne doit être créé.

> **Attention au menu :** l'inscription se fait dans **Inscriptions d'applications**, pas dans **Applications d'entreprise**. Ce second menu sert à ajouter des applications tierces de la galerie. L'application d'entreprise correspondant à l'inscription est créée automatiquement.

---

## §11.5 Mise à niveau compatible des scripts

Les modifications de cette section préparent l'arrivée des documents SharePoint. Elles sont conçues pour ne rien changer au comportement de la stack SMB : sans document SharePoint et avec l'extension Entra désactivée, le résultat est strictement identique à la version validée en Parties 1 et 2.

> **Version de référence des Parties 1 et 2 :** les scripts tels qu'ils ont été validés avant ces modifications restent disponibles dans la Release [v2.12.0](https://github.com/doit4everyone/ia-locale-pme-suisse/tree/v2.12.0/scripts/stack-ia-locale).

### §11.5.1 `acl_resolver.py` v4 : protection des futurs chunks SharePoint

**Le problème.** `acl_resolver.py` supprime les chunks « orphelins », présents dans Qdrant mais absents du partage SMB. Un chunk issu de SharePoint n'est, par définition, jamais sur le partage : sans modification, tous les chunks SharePoint seraient supprimés à chaque synchronisation horaire.

**La correction.** Chaque chunk porte désormais un champ `source_type` (`smb` ou `sharepoint`). La détection des orphelins ne considère que les chunks `smb`. Un chunk sans ce champ, comme tous ceux indexés avant la Partie 3, est traité comme `smb` : aucune réindexation n'est nécessaire.

**Un défaut corrigé au passage.** La suppression des orphelins récupérait les chunks à supprimer par un parcours limité à 500 points. Un fichier orphelin de plus de 500 chunks n'était donc supprimé que partiellement, et le reste restait interrogeable. La suppression se fait maintenant par filtre, sans limite.

Déploiement (script exécuté hors conteneur et, via `/admin/sync`, dans le conteneur par le montage en lecture seule) :

```bash
sudo cp /root/rag-pipeline/acl_resolver.py /root/rag-pipeline/acl_resolver.py.v3.bak
sudo cp /home/<utilisateur>/acl_resolver.py /root/rag-pipeline/acl_resolver.py

cd /root/rag-pipeline
source .venv/bin/activate
python -m py_compile acl_resolver.py && echo "OK"
deactivate
```

Aucun redémarrage n'est nécessaire.

### §11.5.2 `auth.py` : extension Entra ID

Une nouvelle fonction `get_entra_groups()` interroge Graph et retourne :

- `entra:usr:<object-id>` pour le compte lui-même ;
- `entra:grp:<object-id>` pour chaque groupe, imbrications comprises (`transitiveMemberOf`, l'équivalent de la récursion `memberOf` faite côté LDAP). Les rôles d'annuaire et les unités administratives sont écartés.

`get_user_groups()` n'appelle cette fonction que si `ENTRA_ENABLED=true`. Le comportement en cas d'échec est conçu pour ne jamais élargir l'accès :

| Situation | Groupes retournés | Conséquence |
|---|---|---|
| `ENTRA_ENABLED=false` | Groupes AD uniquement | Comportement des Parties 1 et 2 |
| Graph répond | Groupes AD + identifiants Entra | Accès SMB et SharePoint |
| Graph échoue (réseau, certificat expiré, consentement retiré) | Groupes AD uniquement, non mis en cache | Accès SMB intact, aucun accès SharePoint, nouvel essai à la requête suivante |
| Utilisateur absent d'Entra ID | Groupes AD uniquement | Accès SMB intact, aucun accès SharePoint |
| LDAP échoue | Aucun groupe | Refus complet (403), comme en Parties 1 et 2 |

L'authentification par certificat utilise la bibliothèque MSAL de Microsoft, qui met le jeton en cache et ne le renouvelle qu'à expiration. `msal` est ajouté au `requirements.txt` de l'image.

### §11.5.3 Configuration

Variables à ajouter au `.env`, extension désactivée dans un premier temps :

```bash
# Extension Entra ID (Partie 3)
ENTRA_ENABLED=false
ENTRA_TENANT_ID=<ID-ANNUAIRE>
ENTRA_CLIENT_ID=<ID-APPLICATION>
ENTRA_CERT_PATH=/etc/rag-certs/rag-identity.crt
ENTRA_KEY_PATH=/etc/rag-certs/rag-identity.key
ENTRA_CERT_THUMBPRINT=<EMPREINTE-SHA1-SANS-DEUX-POINTS>
```

Ajouts au service `rag-api` du `docker-compose.yml` :

```yaml
    environment:
      # (après GROUPS_CACHE_TTL)
      - ENTRA_ENABLED=${ENTRA_ENABLED}
      - ENTRA_TENANT_ID=${ENTRA_TENANT_ID}
      - ENTRA_CLIENT_ID=${ENTRA_CLIENT_ID}
      - ENTRA_CERT_PATH=${ENTRA_CERT_PATH}
      - ENTRA_KEY_PATH=${ENTRA_KEY_PATH}
      - ENTRA_CERT_THUMBPRINT=${ENTRA_CERT_THUMBPRINT}
    volumes:
      # (après /var/log/rag)
      - /etc/rag-certs:/etc/rag-certs:ro
```

Pour appliquer ces ajouts sur une installation existante sans éditeur, en prenant `/var/log/rag` comme repère pour le montage (la ligne du certificat AD existe aussi dans le service Open WebUI et ne convient pas) :

```bash
cd /root/rag-stack
cp docker-compose.yml docker-compose.yml.bak

grep -q 'ENTRA_ENABLED=' docker-compose.yml || sed -i \
  -e '/- GROUPS_CACHE_TTL=\${GROUPS_CACHE_TTL}/a\      - ENTRA_ENABLED=${ENTRA_ENABLED}' \
  -e '/- GROUPS_CACHE_TTL=\${GROUPS_CACHE_TTL}/a\      - ENTRA_TENANT_ID=${ENTRA_TENANT_ID}' \
  -e '/- GROUPS_CACHE_TTL=\${GROUPS_CACHE_TTL}/a\      - ENTRA_CLIENT_ID=${ENTRA_CLIENT_ID}' \
  -e '/- GROUPS_CACHE_TTL=\${GROUPS_CACHE_TTL}/a\      - ENTRA_CERT_PATH=${ENTRA_CERT_PATH}' \
  -e '/- GROUPS_CACHE_TTL=\${GROUPS_CACHE_TTL}/a\      - ENTRA_KEY_PATH=${ENTRA_KEY_PATH}' \
  -e '/- GROUPS_CACHE_TTL=\${GROUPS_CACHE_TTL}/a\      - ENTRA_CERT_THUMBPRINT=${ENTRA_CERT_THUMBPRINT}' \
  docker-compose.yml

grep -q '/etc/rag-certs' docker-compose.yml || sed -i \
  '/- \/var\/log\/rag:\/var\/log\/rag/a\      - /etc/rag-certs:/etc/rag-certs:ro' \
  docker-compose.yml

docker compose config --quiet && echo "Compose OK"
```

Chaque variable référencée dans le Compose doit exister dans le `.env` : une variable absente est transmise vide au conteneur, ce qui écrase la valeur par défaut du code.

Déploiement de `auth.py` et `requirements.txt` (rebuild obligatoire, `requirements.txt` ayant changé) :

```bash
sudo cp /home/<utilisateur>/auth.py /root/rag-stack/api/auth.py
sudo cp /home/<utilisateur>/requirements.txt /root/rag-stack/api/requirements.txt

cd /root/rag-stack
docker compose build --no-cache rag-api
docker compose up -d rag-api
sleep 15
docker logs rag-api 2>&1 | grep "BM25\|startup\|Uvicorn\|Traceback" | tail -5
```

---

## §11.6 Validation

### §11.6.1 `acl_resolver.py` v4

**Non-régression**, en dry-run dans le conteneur, c'est-à-dire dans l'environnement réellement utilisé par la synchronisation horaire :

```bash
cd /root/rag-stack
docker exec rag-api sh -c 'QDRANT_URL=$QDRANT_HOST python3 /rag-pipeline/acl_resolver.py \
  --share "$SMB_SHARE" --mount "$SMB_MOUNT" --dry-run \
  --rapport /var/log/rag/rapport_acl_dryrun.json' | tail -15
```

**Validé en lab, septembre 2026 :**

```
Fichiers traites        : 69
Chunks mis a jour       : 1691
Fichiers sans ACL       : 0
Fichiers non indexes    : 0

NETTOYAGE DES CHUNKS ORPHELINS
Aucun chunk orphelin détecté.
```

**Protection des chunks SharePoint.** Un faux chunk `sharepoint`, sans aucun droit d'accès (`autorises` vide, donc invisible pour tous les utilisateurs), est inséré dans Qdrant, puis une synchronisation complète est lancée :

```bash
python3 - <<'EOF'
import json, urllib.request
base = "http://localhost:6333/collections/documents"
dim = json.load(urllib.request.urlopen(base))["result"]["config"]["params"]["vectors"]["size"]
body = {"points": [{"id": "00000000-0000-0000-0000-00000000f001", "vector": [0.01] * dim,
        "payload": {"source": "sharepoint/TEST/test-v4.docx", "source_type": "sharepoint",
                    "text": "test v4", "autorises": [], "interdits": []}}]}
req = urllib.request.Request(base + "/points?wait=true", data=json.dumps(body).encode(),
                             method="PUT", headers={"Content-Type": "application/json"})
print(urllib.request.urlopen(req).read().decode())
EOF

TOKEN=$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2-)
docker compose exec n8n wget -qO- --post-data='' \
  --header="Authorization: Bearer $TOKEN" \
  http://rag-api:8080/admin/sync | python3 -m json.tool
unset TOKEN

curl -s http://localhost:6333/collections/documents/points/00000000-0000-0000-0000-00000000f001 \
  | python3 -m json.tool | head -8
```

**Validé en lab, septembre 2026 :** la synchronisation retourne `"success": true` et le faux chunk est toujours présent après son passage. Avec la version 3, il aurait été supprimé comme orphelin.

Nettoyage du chunk de test, puis contrôle des compteurs, qui doivent revenir à leur valeur initiale :

```bash
curl -s -X POST "http://localhost:6333/collections/documents/points/delete?wait=true" \
  -H "Content-Type: application/json" \
  -d '{"points": ["00000000-0000-0000-0000-00000000f001"]}'
docker compose exec n8n wget -qO- http://rag-api:8080/stats
```

### §11.6.2 Extension Entra ID

**Test 1 : non-régression, extension désactivée.** Une question posée dans Open WebUI avec un compte AD obtient la même réponse qu'avant la mise à niveau, et les logs ne contiennent aucune ligne Entra :

```bash
docker logs rag-api 2>&1 | grep "\[AUTH\]" | tail -5
```

**Test 2 : appel Graph direct, sans impact sur les utilisateurs.** La fonction est appelée dans le conteneur alors que l'extension est encore désactivée. Ce test valide à lui seul le certificat, les permissions et le consentement :

```bash
docker exec rag-api python3 -c "import auth; print(auth.get_entra_groups('test-client@bsculier.ch'))"
```

**Validé en lab, septembre 2026 :**

```
['entra:usr:<ID-OBJET-UTILISATEUR>', 'entra:grp:<ID-GROUPE-1>', 'entra:grp:<ID-GROUPE-2>', 'entra:grp:<ID-GROUPE-3>']
```

L'identifiant `entra:usr:` correspond à l'ID d'objet affiché pour ce compte dans le centre d'administration Entra.

Pour identifier les groupes retournés :

```bash
docker exec rag-api python3 -c "
import auth, httpx
t = auth._get_graph_token()
for gid in ['<ID-GROUPE-1>', '<ID-GROUPE-2>', '<ID-GROUPE-3>']:
    r = httpx.get(f'https://graph.microsoft.com/v1.0/groups/{gid}', params={'\$select':'displayName,onPremisesSyncEnabled,groupTypes'}, headers={'Authorization':'Bearer '+t}).json()
    print(gid[:8], r.get('displayName'), '| synchronisé AD :', r.get('onPremisesSyncEnabled'), '| types :', r.get('groupTypes'))
"
```

Résultat obtenu en lab :

| Groupe | Synchronisé depuis l'AD | Type | Visible par LDAP |
|---|---|---|---|
| Tous les utilisateurs | Non | Groupe dynamique | Non |
| GRP-Clients-Niveau2 | Oui | Groupe de sécurité | Oui |
| GRP-Clients | Oui | Groupe de sécurité | Oui |

C'est la démonstration de §11.1.3 : le groupe dynamique « Tous les utilisateurs » n'existe que dans Entra ID.

**Test 3 : extension activée.**

```bash
sed -i 's/^ENTRA_ENABLED=false/ENTRA_ENABLED=true/' .env
docker compose up -d rag-api
```

Après une question posée dans Open WebUI avec `test-client` :

```bash
docker logs rag-api 2>&1 | grep "\[AUTH\]" | tail -5
```

**Validé en lab, septembre 2026 :**

```
[AUTH] Utilisateur trouvé : 'test-client' (test-client@bsculier.ch)
[AUTH] Groupes résolus pour 'test-client@bsculier.ch' : ['BSCULIER\\GRP-Clients-Niveau2', 'BSCULIER\\GRP-Clients', 'BSCULIER\\test-client']
[AUTH] Entra : 4 identifiant(s) pour 'test-client@bsculier.ch'
```

La réponse dans Open WebUI est identique à celle obtenue sans l'extension, citation et chemin UNC compris : l'ajout des identifiants Entra ne modifie pas l'accès aux documents SMB.

> **Retour arrière immédiat :** repasser `ENTRA_ENABLED=false` dans le `.env` puis `docker compose up -d rag-api` neutralise l'extension sans rebuild.

---

## §11.7 Limites et points ouverts

**Délai de prise en compte des changements de groupe.** Un utilisateur ajouté à un groupe AD n'obtient les droits correspondants côté Entra qu'après le cycle de synchronisation d'Entra Connect (30 minutes par défaut), auquel s'ajoute le cache des groupes d'`auth.py` (`GROUPS_CACHE_TTL`, 5 minutes par défaut). Le délai cumulé peut atteindre 35 minutes.

**Libellé de log trompeur.** Avec l'extension activée, `main.py` affiche « 7 groupes AD » alors que ce nombre inclut les identifiants Entra. C'est un libellé, sans effet sur le filtrage. Il sera corrigé en §12, avec les autres modifications de `main.py`.

**Portée de `User.Read.All`.** Cette permission permet de lire les profils de tous les utilisateurs du tenant, pas seulement ceux qui utilisent la stack RAG. C'est le prix de la résolution par UPN. La protection repose sur la clé privée, qui ne quitte pas la VM (`/etc/rag-certs`, droits `600`).

**Autorisation « Tout le monde sauf les utilisateurs externes ».** SharePoint propose cette autorisation, qui n'est pas un groupe Entra ID et n'aura donc jamais d'identifiant `entra:grp:`. Sa traduction dans `autorises[]` sera traitée en §12.

---

## §11.8 Checklist

| Point | Commande / vérification | Résultat attendu |
|---|---|---|
| Sortie HTTPS vers Microsoft | `curl -sI https://login.microsoftonline.com \| head -1` | `HTTP/1.1 200 OK` |
| Graph depuis le conteneur | Commande de §11.2.2 | `200` |
| Heure synchronisée | `timedatectl` | `System clock synchronized: yes` |
| Clé privée protégée | `ls -l /etc/rag-certs` | `rag-identity.key` en `-rw-------` |
| App Registration | Centre d'administration Entra | Deux permissions application, consentement accordé, aucun secret |
| `acl_resolver.py` v4 | Dry-run de §11.6.1 | Aucun orphelin, aucune erreur |
| Protection SharePoint | Test du faux chunk de §11.6.1 | Chunk conservé après `/admin/sync` |
| Graph depuis `auth.py` | Test 2 de §11.6.2 | `entra:usr:` + groupes |
| Extension active | Test 3 de §11.6.2 | Ligne `[AUTH] Entra : N identifiant(s)` |
| Non-régression SMB | Question dans Open WebUI | Réponse identique, avec citation |

---

§12 Connecteur SharePoint *(à venir)*

---

*Validé en lab sur VM-RAG-LAB, septembre 2026, sur un tenant Microsoft 365 synchronisé par Entra Connect. L'indexation SharePoint (§12) et le déchiffrement des documents protégés par Purview (§13) ne sont pas couverts par cette section.*
