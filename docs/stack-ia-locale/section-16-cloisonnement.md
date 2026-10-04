---
title: "§16 Contrôle du cloisonnement et durcissement | Guide de déploiement stack IA locale"
description: "Test de non-divulgation automatisé, contrôle du cloisonnement après chaque synchronisation avec alerte, correction du masque des droits NTFS, et durcissement de la RAG API, d'Open WebUI et de n8n à la suite d'une revue externe."
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

# §16 Contrôle du cloisonnement et durcissement

[Retour au sommaire](index.md) | [Section précédente : §15 Sécurité des données](section-15-securite-donnees.md)

**Statut :** validé en lab sur VM-RAG-LAB, octobre 2026 : 40 cas de cloisonnement conformes, une faille du calcul des droits NTFS reproduite puis corrigée, alerte prouvée par une fuite simulée.

---

> **Ce que cette section documente :** jusqu'ici, le cloisonnement était vérifié par des matrices de questions posées à la main, compte par compte (§9, §13, §14). Cette section les remplace par un **test automatisé**, qui vérifie directement les filtres d'accès, en quelques secondes, et qui s'exécute **après chaque synchronisation** avec une alerte par courriel. Elle documente aussi la première faille trouvée grâce à lui, et le durcissement de la stack mené à la suite d'une revue externe du dépôt.

---

## §16.1 Pourquoi automatiser

Une matrice manuelle prouve que le cloisonnement fonctionnait **le jour du test**. Or ses causes de défaillance changent sans prévenir : un administrateur modifie les droits d'un dossier, un groupe change de membres, un document est déplacé, un script est mis à jour. Le contrôle doit donc être rejoué à chaque changement possible, c'est-à-dire à chaque synchronisation.

Poser des questions au modèle ne s'y prête pas : sur CPU, les 36 combinaisons du lab demandaient une vingtaine de minutes, et le résultat dépendait du **classement de la recherche**. Un compte qui a accès à presque tout le corpus ne voyait pas toujours remonter un petit document de test, noyé parmi des centaines de chunks : ce n'était pas un refus, mais le test ne pouvait pas le distinguer d'un refus.

## §16.2 Vérifier l'accès, pas la réponse

L'endpoint d'administration `/admin/verifier-acces` reçoit un utilisateur et un document, et applique **exactement les filtres de la recherche**, dans le même ordre, avec les mêmes fonctions :

1. le filtre Qdrant sur `autorises[]` (permissions NTFS ou SharePoint) ;
2. les refus explicites (DENY) ;
3. les droits de l'étiquette Purview (§14).

Il renvoie trois nombres : les chunks du document dans l'index, ceux qui restent après la première condition, et ceux qui restent après Purview. Pas de classement, pas de génération, pas de juge. On voit ainsi **quelle condition** a retiré le document.

## §16.3 Le test de non-divulgation

`test_cloisonnement.py` lit un fichier de cas : des comptes de test, et pour chaque document visé, l'accès attendu par compte.

```json
{
  "comptes": ["direction@votre-domaine.ch", "comptable@votre-domaine.ch", "client@votre-domaine.ch"],
  "cas": [
    {"id": "FIN-1", "question": "Quel code de vérification commence par FIN- ?",
     "document": "Test_RAG_Finances.docx", "secret": "4827",
     "attendu": {"direction@votre-domaine.ch": true, "comptable@votre-domaine.ch": true,
                 "client@votre-domaine.ch": false}}
  ]
}
```

| Mode | Ce qu'il vérifie | Durée (lab, CPU) |
|---|---|---|
| `--mode acces` (défaut) | **Le cloisonnement**, par `/admin/verifier-acces` : déterministe | Quelques secondes pour 40 cas |
| `--mode complet` | La chaîne entière par `/query`, recherche et modèle compris | 20 à 30 minutes pour 36 cas |

| Verdict | Signification |
|---|---|
| OK | Conforme |
| **FUITE** | Document interdit accessible : le script se termine en erreur |
| REFUS À TORT | Document autorisé inaccessible : défaut, mais dans le sens sûr |
| ABSENT | Document non indexé : le cas ne teste rien |

```bash
docker exec rag-api python3 /rag-pipeline/test_cloisonnement.py /rag-pipeline/cas_cloisonnement.json
```

Les cas du lab reprennent les matrices de §9 (DENY nominatif), §13 (quatre modes de partage SharePoint, site ouvert à tous) et §14 (trois étiquettes chiffrées), plus le cas de §16.5. Résultat : **40 sur 40**, et la colonne « après ACL » montre, par exemple, le document Finances chiffré passer la première condition pour le comptable (il a accès au site), puis être retiré par Purview seul.

Le mode complet garde un intérêt : il mesure la qualité de la recherche. Ses cas « manqués » (document autorisé absent des sources) ne sont pas un sujet de sécurité, mais un indicateur pour le §10.

## §16.4 Le contrôle après chaque synchronisation

À la fin de `/admin/sync`, la RAG API rejoue tous les cas du fichier `CAS_CLOISONNEMENT` (par défaut `/rag-pipeline/cas_cloisonnement.json`) et ajoute au rapport :
- `cloisonnement` : nombre de cas conformes, listes des fuites, refus à tort, cas invalides et erreurs ;
- `cloisonnement_alerte` : vrai dès qu'un cas n'est pas conforme.

Sans fichier de cas, le contrôle est simplement absent. Le workflow n8n de synchronisation déclenche le courriel si `cloisonnement_alerte` est vrai, avec un sujet prioritaire en cas de fuite, et la consigne d'arrêter le service tant que la cause n'est pas comprise.

**Contre-épreuve, faite en lab** : en remettant l'ancienne version du calcul des droits (§16.5), la synchronisation suivante a envoyé le courriel « FUITE DE CLOISONNEMENT », avec le cas et le compte concernés. Un contrôle qui n'a jamais sonné n'est pas un contrôle prouvé.

## §16.5 Une faille réelle : le masque des droits NTFS

Une ACL NTFS est une liste d'entrées : qui, autorisé ou refusé, et quels droits (le masque). `smbcacls` les affiche ainsi :

```
ACL:DOMAINE\GRP-RAG-Indexation:ALLOWED/0x0/READ
ACL:DOMAINE\Comptabilité:ALLOWED/0x0/0x00100116
```

Jusqu'à la v2.16, `acl_resolver.py` ne lisait que le début de la ligne : **toute entrée `ALLOWED` valait autorisation**, quel que soit le masque. Or `0x00100116` accorde l'écriture des données, mais **pas leur lecture**.

**Le cas concret : la boîte de dépôt.** Un dossier où les collaborateurs peuvent déposer des fichiers sans lire ceux des autres : candidatures, notes de frais, signalements. Windows refuse la lecture ; le RAG l'accordait.

**Reproduction en lab** : un fichier avec trois entrées, administration en contrôle total, groupe d'indexation en lecture, groupe Comptabilité en écriture seule (`icacls <fichier> /grant "DOMAINE\Comptabilité:(W)"`). Le test a sorti **FUITE** pour le compte comptable.

**Correction** : une entrée `ALLOWED` n'est retenue que si son masque accorde la lecture du contenu (`READ`, `CHANGE`, `FULL`, une combinaison de lettres contenant `R`, ou le bit de lecture des données en hexadécimal). Un format inconnu vaut refus. Les entrées héritables seulement (`IO`) sont ignorées. Les refus (`DENIED`) sont tous conservés, quel que soit leur masque : un refus partiel rend un fichier invisible à tort, jamais visible à tort. Le rapport de synchronisation compte les entrées ignorées. Après correction : **40 sur 40**, sans qu'aucun des 36 autres cas ne change.

> **Deux défauts qui se masquaient.** Le premier essai, avec « Utilisateurs du domaine » en écriture seule, n'a révélé aucune fuite : ce groupe est le **groupe principal** des comptes AD, absent de l'attribut `memberOf` que lit la RAG API. Le défaut du masque était bien là, compensé par un second défaut. Corriger d'abord le groupe principal aurait rendu le fichier lisible par tout le domaine. **L'ordre des corrections compte : le masque d'abord, le groupe principal ensuite.** C'est le genre de piège qu'un test automatisé révèle, et qu'une correction faite sans lui aurait déclenché.

**Permissions du partage.** Sous Windows, l'accès réseau exige aussi les droits du partage. Le RAG ne lit que les NTFS : il suppose un partage ouvert largement (« Tout le monde » ou « Utilisateurs authentifiés »), la restriction étant portée par les NTFS, ce qui est la configuration habituelle. Lire les droits d'un partage exige en général des droits d'administration sur le serveur, que le compte d'indexation ne doit pas avoir. `Set-AccesIndexationRAG.ps1 -Verifier` affiche donc ces droits depuis le serveur, et signale un partage restreint (code de sortie 3).

## §16.6 Durcissement de la RAG API

| Point | Avant | Après |
|---|---|---|
| Mot de passe SMB | Sur la ligne de commande de `smbcacls`, visible dans la liste des processus | Fichier d'identifiants temporaire en mémoire (`-A`), lisible par le seul processus |
| Juge en échec | Réponse considérée comme ancrée | Considérée comme non vérifiée : `/query` la bloque, le journal indique `verification: erreur` |
| Réponse non vérifiée dans Open WebUI | Rendue sans signal | Rendue, avec une mention invitant à vérifier dans les sources |
| Citations | Comparées par sous-chaîne | Correspondance exacte sur le nom de fichier |
| Deux documents de même nom | Lien vers le premier trouvé | Les deux emplacements sont indiqués |
| Panne de Qdrant ou de l'embedding | « Information absente » | Erreur 503 explicite |
| `/stats`, `/health` | `/stats` ouvert, `/health` révèle l'adresse du moteur | `/stats` réservé à l'administration, `/health` minimal |
| Empreinte des questions au journal | SHA-256 tronqué : une question courte se retrouve par dictionnaire | HMAC avec une clé secrète (`LOG_HMAC_KEY`) |
| Valeurs d'exemple (`changeme`) | Aucun signal | Avertissement au démarrage pour chaque secret concerné |

Le jeton d'administration du lab était d'ailleurs resté à sa valeur d'exemple : la stack fonctionnait sans rien signaler. L'avertissement aurait suffi à le voir.

## §16.7 Open WebUI, n8n et le moteur d'inférence

**Open WebUI** : dans **Réglages d'administration** → **Connexions**, désactiver **API Ollama** et **Direct connexions**. Les utilisateurs ne voient plus que le modèle de la RAG API, et ne peuvent pas ajouter eux-mêmes l'adresse d'Ollama. Faire ce réglage dans l'interface : la variable `ENABLE_OLLAMA_API=false`, placée dans le Compose du dépôt, n'est lue qu'au **premier** démarrage d'Open WebUI, qui garde ensuite ses réglages dans sa base.

**Le moteur d'inférence** : Ollama écoute sur le réseau pour que la VM puisse l'atteindre, donc n'importe quel poste peut l'interroger directement. Pas de fuite du corpus par ce chemin (le modèle n'a pas les documents), mais ni journal ni contrôle. Le pare-feu du serveur d'inférence doit n'accepter le port 11434 que depuis la VM de la stack. Si la VM est derrière un routeur qui traduit les adresses, le serveur voit l'adresse du routeur : la restriction se complète alors sur le routeur. Vérification : depuis un autre poste, `curl -m 5 http://<serveur>:11434/api/tags` doit échouer.

**n8n** : le jeton d'administration n'est plus écrit dans les nœuds HTTP. Un identifiant unique de type **Header Auth** (*Name* `Authorization`, *Value* `Bearer <jeton>`, domaine autorisé : `rag-api`) est utilisé par les nœuds de synchronisation et de synthèse Teams, avec « Send Headers » désactivé. Le jeton n'apparaît plus dans les workflows ni dans leurs exports, et sa rotation se fait en un seul endroit :

```bash
cd /root/rag-stack
sed -i "s/^ADMIN_TOKEN=.*/ADMIN_TOKEN=$(openssl rand -hex 32)/" .env
docker compose up -d rag-api                      # recrée le conteneur (§15.3.6)
grep '^ADMIN_TOKEN=' .env | cut -d= -f2           # à reporter dans l'identifiant n8n
```

## §16.8 Checklist

| Point | Vérification | Attendu |
|---|---|---|
| Test d'accès | `test_cloisonnement.py` | 0 FUITE, 0 ABSENT |
| Contrôle après synchronisation | `docker logs rag-api \| grep CLOISONNEMENT` | `N/N conformes, fuites=0` |
| Alerte | Contre-épreuve (fuite simulée) | Courriel « FUITE DE CLOISONNEMENT » reçu |
| Masque NTFS | Rapport de synchronisation | `entrees_allowed_sans_lecture` affiché |
| Permissions du partage | `Set-AccesIndexationRAG.ps1 -Verifier` | Ouverture large, pas d'alerte |
| Valeurs d'exemple | `docker logs rag-api \| grep SÉCURITÉ` | Aucune ligne |
| `/stats` | Appel sans jeton | HTTP 401 ou 403 |
| Journal | `tail -1 /var/log/rag/rag-queries.jsonl` | `question_hash` commençant par `hmac:` |
| Open WebUI | Liste des modèles avec un compte utilisateur | `rag-api` seul |
| Moteur d'inférence | `curl` depuis un autre poste | Pas de réponse |
| n8n | Export d'un workflow | Aucun jeton en clair |

---

[Retour au sommaire](index.md) | [Section précédente : §15 Sécurité des données](section-15-securite-donnees.md)

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
