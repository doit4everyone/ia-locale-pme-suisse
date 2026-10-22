---
title: "§16 Contrôle du cloisonnement et durcissement | Guide de déploiement stack IA locale"
description: "Test de non-divulgation automatisé, contrôle du cloisonnement après chaque synchronisation avec alerte, correction du masque des droits NTFS, durcissement de la RAG API, d'Open WebUI et de n8n à la suite d'une revue externe, versions figées et supervision externe."
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

[Retour au sommaire](index.md) | [Section précédente : §15 Sécurité des données](section-15-securite-donnees.md) | [Section suivante : §17 Gouvernance](section-17-gouvernance.md)

**Statut :** validé en lab sur VM-RAG-LAB, octobre 2026 : 40 cas de cloisonnement conformes, une faille du calcul des droits NTFS reproduite puis corrigée, alerte prouvée par une fuite simulée. Compléments de la 2.21.0 (refus des secrets d'exemple, identité signée, versions figées, supervision externe) validés sur la VM de test, octobre 2026. Seconde faille (droits périmés de la recherche par mots-clés, §16.5.1) signalée par une revue externe du code, reproduite puis corrigée en 2.21.3, sur le vrai Qdrant de la VM de test, le 20 octobre 2026.

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

> **Ce que ce test ne voit pas.** Il vérifie les droits enregistrés dans Qdrant, pas le chemin que suit une question. Un défaut de la recherche elle-même, qui contournerait ces droits, lui échappe : c'est le cas de la faille du §16.5.1, trouvée par une lecture du code. D'où les tests propres à ce chemin.

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
| ERREUR | Qdrant injoignable (HTTP 503), droits non résolus (403), ou cas ambigu (400) : aucun verdict n'est rendu |

Un cas désigne son document par son **nom de fichier exact**, ou par son **chemin complet** quand plusieurs documents portent le même nom. Un nom partagé est refusé comme ambigu : un cas qui évalue deux documents à la fois ne prouve rien sur aucun des deux. Dans le lab, ce contrôle a révélé que le cas du guide du helpdesk portait sur deux exemplaires, l'un à la racine du site (ouvert à tous), l'autre dans le site de l'équipe IT (restreint) : il passait grâce au premier, sans dire lequel. Le cas a été précisé, et le second exemplaire a reçu son propre cas. Une correspondance partielle (`"correspondance": "fragment"`) reste possible cas par cas, pour le lab.

Une **panne de Qdrant** produit une erreur, jamais un verdict : vérifié en arrêtant Qdrant pendant le test (quatre `ERREUR`, HTTP 503). Auparavant, une erreur de lecture était traitée comme une collection absente.

```bash
docker exec rag-api python3 /rag-pipeline/test_cloisonnement.py /rag-pipeline/cas_cloisonnement.json
```

Les cas du lab reprennent les matrices de §9 (DENY nominatif), §13 (quatre modes de partage SharePoint, site ouvert à tous) et §14 (trois étiquettes chiffrées), plus le cas de §16.5. Résultat : **40 sur 40**, puis **44 sur 44** avec le cas ajouté en v2.18.2, et la colonne « après ACL » montre, par exemple, le document Finances chiffré passer la première condition pour le comptable (il a accès au site), puis être retiré par Purview seul.

**Rejeu sur un déploiement neuf (octobre 2026).** Le test a été rejoué, en mode accès, sur la VM déployée à partir de zéro pour valider le §0 : 70 documents indexés (1692 extraits), droits résolus, `/admin/sync`, puis 9 comptes de test sur 8 cas. Résultat : **72 verdicts, dont 70 `OK`, 2 `INFO` et 0 `FUITE`**. Les deux `INFO` sont deux cas dont l'attendu avait été laissé à « ? » faute de savoir le résultat juste : le test les a tranchés (refus pour un compte de la comptabilité sur un budget, accès pour un compte client sur un contrat). Ce rejeu ne porte pas sur le mode complet, qui interroge le modèle et dure 20 à 30 minutes.

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

### §16.5.1 Seconde faille : un droit retiré restait valable par les mots-clés

**Le défaut.** La recherche combine deux branches (§8.6). La branche vectorielle interroge Qdrant à chaque question, avec les droits actuels. La branche par mots-clés (BM25) cherche dans un index en mémoire, qui garde le texte **et les droits** du moment de sa construction : au démarrage, puis en fin de synchronisation. Jusqu'à la 2.21.2, ses candidats étaient autorisés sur ces droits mémorisés. Entre la modification des droits dans Qdrant et la reconstruction suivante, un droit retiré restait donc valable par ce chemin : pendant la synchronisation elle-même, ou jusqu'à une heure quand `acl_resolver.py` est lancé à la main. Un document supprimé restait aussi trouvable.

**Le repli qui l'aggravait.** Pour un document complémentaire, la RAG API relit dans Qdrant les extraits voisins, avec les droits actuels. Si cette lecture ne renvoyait rien, elle remettait l'extrait d'origine. Or une lecture vide, c'est précisément le cas d'un droit retiré.

**Comment il a été trouvé.** Par une revue externe du code, en octobre 2026. Le défaut figurait dans le suivi (point 10), avec une gravité « faible » : on comptait sur la relecture des voisins pour l'arrêter. Cette justification était fausse, à cause du repli. Le test de non-divulgation ne pouvait pas le voir (§16.2).

**Reproduction.** `test_revalidation_bm25.py` simule Qdrant : l'index est construit pendant que deux documents sont autorisés, puis le droit sur l'un est retiré, sans reconstruire l'index. Sur le code de la 2.21.2, le document retiré revient dans les sources, avec et sans extension du contexte : **FUITE**.

**Correction (2.21.3).** Les droits mémorisés ne servent plus qu'à présélectionner les candidats. Chaque candidat est relu dans Qdrant par son identifiant, en un appel par collection, et les droits (ALLOW, puis DENY) sont contrôlés sur cette lecture ; texte, source et étiquette Purview en sont repris. Refus par défaut : un point disparu ou une lecture en erreur écarte le candidat. Le repli est supprimé : une lecture des voisins vide ou en erreur écarte le document. Sur le code corrigé, les 11 tests unitaires passent.

**Sur le vrai Qdrant.** `test_revocation_bm25.py` retire quelques secondes le droit sur un document, sans reconstruire l'index, repose la question avec les mots les plus rares du document, puis remet les droits d'origine et les contrôle. Le test ne fait que retirer un droit : il ne donne accès à rien.

> **Validé sur la VM de test, 20 octobre 2026**, avec `COMPTABILITE/Test_RAG_Depot.docx`, lisible par l'administrateur seul, et la question « dépôt » :
>
> - **en 2.21.2 : FUITE par les deux chemins.** Avec l'extension du contexte, un autre document passe en tête après le retrait, et `Test_RAG_Depot.docx` revient en complément, par le repli. Sans extension, il revient directement ;
> - **en 2.21.3 : OK par les deux chemins.** Le journal de la RAG API indique `[BM25] Relecture : 0 candidat(s) disparu(s) ou illisible(s), 1 refusé(s) par les droits actuels` ;
> - droits d'origine restaurés et contrôlés après chaque passage ; tests unitaires : 11 OK ; test de non-divulgation inchangé après correction (70 OK, 2 INFO, aucune fuite).

**Compléments de la 2.21.4**, à la suite d'une seconde revue du correctif :

- **un échec de ces tests bloque le déploiement.** `deploy.sh` les lance à l'étape 10 ; jusqu'ici, un échec n'affichait qu'un avertissement. Désormais, il arrête la RAG API, pour qu'aucune question ne soit servie par un code qui laisserait passer un droit retiré, et le script se termine en erreur ;
- **sans groupes, aucune recherche.** La recherche, la relecture des candidats et l'extension du contexte ne désactivaient leurs contrôles qu'en l'absence de groupes. `/query` et `/v1` refusent déjà ce cas avant de chercher ; ces fonctions le refusent aussi elles-mêmes (403, ou aucun résultat), pour qu'une route future qui l'oublierait ne serve jamais une recherche sans filtre. Les tests unitaires passent de 11 à 14.

> **Validé sur la VM de test, 20 octobre 2026 :** 14 tests unitaires OK ; test sur le vrai Qdrant `Bilan : OK` ; test de non-divulgation inchangé (70 OK, 2 INFO) ; une question réelle dans Open WebUI, réponse citée. Le blocage de `deploy.sh` a été vérifié en simulation (test réussi : rien ne change ; test en échec : RAG API arrêtée, script en erreur), pas par un nouveau déploiement complet.

> **Ce que la correction ne change pas.** La recherche suit désormais les droits enregistrés dans Qdrant. Elle ne suit pas en temps réel ceux du serveur de fichiers : un droit retiré sous Windows n'atteint Qdrant qu'au passage suivant de `acl_resolver.py`, à chaque synchronisation. C'est la fenêtre de péremption du §5.4, distincte du défaut corrigé ici.

### §16.5.2 Troisième défaut : un échec d'écriture des droits passait inaperçu

**Le défaut.** `acl_resolver.py` lit les droits sur le partage, puis les écrit dans Qdrant, document par document. Jusqu'à la 2.21.4, une erreur de Qdrant pendant cette écriture renvoyait la même valeur que « aucun extrait » : le document passait pour « non indexé », le script se terminait normalement (code 0), la synchronisation était déclarée réussie et **aucune alerte ne partait**. Le document gardait ses anciens droits dans Qdrant, jusqu'à une écriture réussie, ou indéfiniment si l'erreur persistait. La correction du §16.5.1 n'y pouvait rien : elle relit Qdrant, et c'est Qdrant qui avait des droits périmés.

**Le scénario réaliste** : le disque de Qdrant plein (`/srv/rag-donnees`). Les lectures passent, les écritures échouent. Trois défauts de la même famille :

- un fichier aux ACL illisibles est fermé (droits vidés) ; si cette fermeture échouait, il restait ouvert, sans signal ;
- un fichier supprimé du partage voit ses extraits supprimés ; un échec était seulement affiché, et ses extraits restaient interrogeables ;
- la liste des extraits orphelins était lue sans contrôle d'erreur : une lecture interrompue laissait des orphelins sans le dire.

Défaut voisin, sans effet sur les droits : la synchronisation cherchait le statut `non_indexé`, alors que le script écrit `non_indexe`. Les fichiers non indexés n'étaient jamais comptés en quarantaine.

**Comment il a été trouvé.** Par une troisième revue externe du code, en octobre 2026. Reproduit sur le code de la 2.21.4 avec un Qdrant simulé qui refuse les écritures : code de sortie 0, statut « non indexé », anciens droits conservés.

**Correction (2.21.5).**

- `acl_resolver.py` distingue trois issues : mis à jour, non indexé, **échec d'écriture**. Une seconde tentative est faite après deux secondes. Les échecs de fermeture, de suppression et de lecture des orphelins sont traités de la même façon.
- En cas d'échec, le passage va à son terme, puis le script sort avec le **code 2**, et le rapport liste les documents concernés. La synchronisation est en échec : le courriel et le signal de supervision partent par le circuit existant (§7, §16.10).
- **Fermeture par défaut, document par document** : la RAG API retire de toute recherche les documents dont les droits n'ont pas pu être écrits, jusqu'au prochain passage sans échec. Seuls ces documents disparaissent, pas le service. La liste est gardée dans `/var/log/rag/acl_bloques.json`, sur le disque chiffré, pour survivre à un redémarrage. Le contrôle d'accès du §16.2 applique la même exclusion : le test de non-divulgation signale alors un `REFUS À TORT` pour les comptes autorisés, ce qui est voulu.
- Même règle pour SharePoint : un fichier en erreur dans le rapport de `sp_indexer.py` (code 2) est retiré de la recherche.
- `deploy.sh` : les tests de sécurité des droits sont obligatoires. Absent ou en échec, la RAG API est arrêtée et le déploiement se termine en erreur. Depuis la 2.21.10, `test_citations.py` (citations et lecture du verdict du juge) l'est aussi ; depuis la 2.22.0, `test_sid.py` (droits par SID).

**Que faire en cas d'alerte.** Le courriel de synchronisation indique le nombre de documents retirés, et `docker logs rag-api 2>&1 | grep DROITS` les nomme. Corriger la cause (espace disque, état de Qdrant, n8n arrêté), puis relancer une synchronisation : depuis n8n (*Execute workflow*), ou à la main sur la VM :

```bash
docker exec rag-api python3 -c "import os,httpx; r=httpx.post('http://localhost:8080/admin/sync', headers={'Authorization':'Bearer '+os.environ['ADMIN_TOKEN']}, timeout=1800); print(r.status_code, r.json().get('success'), r.json().get('errors'))"
```

Les documents reviennent dès que leurs droits sont écrits, et les questions sont de nouveau servies dès qu'une synchronisation complète a abouti.

**Compléments de la 2.21.6**, à la suite d'une quatrième revue, qui a trouvé deux chemins encore ouverts, dont un introduit par la 2.21.5 :

- **un passage incomplet ne vide plus jamais la liste.** En 2.21.5, une lecture des orphelins en échec donnait le code 2 avec une liste vide, qui **remplaçait** la précédente : des documents retirés redevenaient visibles. Désormais, seul un passage complet retire des documents de la liste. Un passage incomplet ne fait qu'ajouter : orphelins probables (sources du partage présentes dans Qdrant mais absentes du partage), ou tout le partage si même cet inventaire échoue ;
- **SharePoint : fichier devenu trop volumineux.** Au-delà de `SP_MAX_FILE_MB`, `sp_indexer.py` sortait sans relire les droits ni supprimer les anciens extraits : un fichier déjà indexé qui grossissait gardait ses anciens droits. Ses extraits sont désormais supprimés, comme pour un fichier vide ou chiffré ; une suppression refusée en fait un fichier en erreur, retiré de la recherche ;
- **SharePoint : site ou bibliothèque illisible.** Le rapport nomme le périmètre dont l'inventaire n'a pas abouti ; la RAG API le retire de la recherche jusqu'à un passage complet, sans vider la liste existante ;
- **registre atomique.** `acl_bloques.json` est écrit dans un fichier temporaire, forcé sur le disque, puis renommé : une coupure laisse l'ancienne version intacte. Un échec d'écriture est signalé dans la synchronisation ;
- **registre absent ou illisible au démarrage : aucune question servie** (HTTP 503, « Vérification des droits en cours ») jusqu'à une synchronisation complète. `deploy.sh` le crée vide à l'installation : son absence ensuite est anormale. Le contrôle d'accès du §16.2 refuse aussi, et le test de non-divulgation affiche une `ERREUR` ;
- **option `ACL_INCERTAIN_FERME`.** Un passage abandonné (annuaire ou partage injoignable, garde-fou) ou interrompu : avec 1, tous les documents de l'origine concernée (partage ou SharePoint) sont suspendus jusqu'à un passage complet ; avec 0, les derniers droits connus sont conservés. C'est l'arbitrage du §5.4 entre disponibilité et fraîcheur des droits. **Depuis la 2.21.7, la valeur par défaut est 1** (voir plus bas).

**Compléments de la 2.21.7**, à la suite d'une cinquième revue :

- **un registre non enregistré n'est plus jamais perdu au redémarrage.** En 2.21.6, un échec d'écriture du registre était signalé, mais les questions restaient servies, et un redémarrage relisait l'ancien registre, sans les documents retirés depuis. Désormais, tant que le registre n'a pas pu être écrit, **aucune question n'est servie**. Et un **marqueur** « synchronisation des droits en cours » est posé avant toute modification des droits, puis retiré seulement quand le résultat est écrit : présent au démarrage, il signale un résultat peut-être perdu, et les questions sont refusées jusqu'à une synchronisation terminée. Si le marqueur ne peut pas être écrit, les droits ne sont pas synchronisés du tout ;
- **registre validé strictement** : version de schéma, listes de chemins, indicateurs booléens. Un registre lisible mais mal formé (`{}`, une chaîne à la place d'une liste) est traité comme illisible : questions refusées ;
- **dossier synchronisé après le renommage**, pour que le remplacement du registre survive à une coupure brutale ;
- **`ACL_INCERTAIN_FERME=1` par défaut.** Le guide vise des documents RH, financiers et clients : la fermeture est le bon défaut. Une organisation qui préfère la disponibilité met 0 dans le `.env`, en connaissance de cause ;
- **reprise sans intervention** : une synchronisation terminée (code 0 ou 2) réécrit les droits de tous les documents et retrouve tous les échecs. Elle reconstruit donc la liste complète et lève le refus, même si le registre avait été perdu.

**Limites.**

- Avec `ACL_INCERTAIN_FERME=0`, un passage abandonné ou interrompu laisse en place les droits du passage précédent pour les documents qui n'étaient pas déjà retirés. L'alerte part à chaque synchronisation tant qu'aucun passage complet n'a abouti.
- Un redémarrage de la RAG API pendant une synchronisation laisse le marqueur : les questions sont refusées jusqu'à la synchronisation suivante, au plus une heure, ou tout de suite par une synchronisation lancée à la main.
- Le registre et le marqueur sont sur le même disque (`/var/log/rag`, disque chiffré) : un disque plein les rend impossibles à écrire, et l'assistant refuse alors les questions **tant que la RAG API tourne**. Après un redémarrage, ce refus en mémoire est perdu : si le marqueur n'avait pas pu être écrit, rien ne le signale, et les questions sont de nouveau servies avec les droits de la dernière synchronisation complète. C'est l'âge maximal des droits de la 2.21.8 qui borne ce cas (voir plus bas).
- L'alerte Push vers la supervision n'existe que si le nœud n8n correspondant a été activé (§16.10) ; le courriel, lui, part sans réglage supplémentaire.
- Un vrai échec d'écriture n'a pas été provoqué sur la VM de test : il est vérifié par les tests unitaires, Qdrant simulé (`test_echec_droits.py`, 31 tests).

**Compléments de la 2.21.8**, à la suite d'une sixième revue :

- **âge maximal des droits.** Le registre garde l'heure de la dernière synchronisation **complète** des droits : chaque origine configurée a terminé son passage, aucune n'est restée incertaine, et le registre a bien été écrit. Un passage partiel ne la change pas. Au-delà de `ACL_AGE_MAX_HEURES` (3 h par défaut ; avec une synchronisation horaire, deux échecs de suite sont tolérés), plus aucune question n'est servie. Un horodatage absent, illisible, ou situé plus de 5 minutes dans le futur (écart d'horloge toléré) vaut refus. Cette règle ne demande aucune écriture : elle survit à un redémarrage, même quand le disque refuse l'écriture, et couvre aussi n8n arrêté, un workflow désactivé et oublié, ou des échecs répétés. `ACL_AGE_MAX_HEURES=0` désactive ce seul contrôle, pas les autres. Depuis la 2.21.10, toute autre valeur doit être un nombre fini strictement positif : une valeur invalide (texte, `nan`, `inf`, négatif) applique la limite de 3 heures et le journal le signale (`[DROITS] ACL_AGE_MAX_HEURES=... invalide`) ;
- **le marqueur est posé avant l'indexation**, plus seulement avant les droits : l'indexeur reporte sur le nouveau contenu d'un fichier modifié les droits de son ancienne version. Si le marqueur ne s'écrit pas, rien de la synchronisation ne tourne ;
- **`/sante` signale l'état des droits** : `ok`, `droits_perimes` ou `droits_inconnus`, toujours avec le code HTTP 200, pour que le contrôle d'état de Docker ne redémarre pas la RAG API. La sonde de supervision du §16.10, qui cherche `ok`, alerte alors même quand aucune synchronisation n'a tourné, donc sans courriel d'échec. La sonde avertit ; c'est la RAG API qui bloque ;
- **`deploy.sh`** ne crée le registre que sur une installation neuve, et l'y date. Sur une installation existante dont le registre a disparu, il s'arrête au lieu d'en créer un vide. Les deux tests de sécurité sont exigés dans le dépôt, puis comparés après la copie ;
- **pendant une synchronisation normale, les questions restent servies.** C'est un choix : la bloquer coûterait plusieurs minutes d'indisponibilité chaque heure. Le risque pendant ces minutes est celui de la latence normale (§5.4) : un document dont le contenu et les droits changent ensemble garde ses anciens droits jusqu'au passage de `acl_resolver.py`, quelques minutes plus tard.

**Mettre à jour vers la 2.21.8.** Le registre de la 2.21.7 n'est pas daté : après la mise à jour, la RAG API refuse les questions jusqu'à la première synchronisation complète. La lancer aussitôt.

**Remplacer aussi le `docker-compose.yml`.** Les procédures de mise à jour de la 2.21.2 à la 2.21.7 ne remplaçaient que `main.py` : sur une installation mise à jour ainsi, le Compose ne transmet ni `ACL_INCERTAIN_FERME`, ni `ACL_AGE_MAX_HEURES`. Le code applique alors ses valeurs par défaut (suspension des origines incertaines, limite de 3 heures), mais une valeur écrite dans le `.env` est ignorée sans message. Copier le `docker-compose.yml` du dépôt dans le dossier personnel de l'administrateur, puis comparer :

```bash
cd /root/rag-stack && diff docker-compose.yml /home/<admin>/docker-compose.yml
```

Seules des lignes ajoutées (`>`) doivent apparaître ; une ligne retirée (`<`) est une adaptation locale à reporter dans le nouveau fichier. Puis remplacer le Compose, en gardant l'ancien, et recréer les conteneurs concernés :

```bash
cd /root/rag-stack && cp docker-compose.yml docker-compose.yml.avant-2.21.8 && cp /home/<admin>/docker-compose.yml docker-compose.yml && docker compose up -d
```

> **Constaté sur la VM de test, 22 octobre 2026 :** le workflow de synchronisation, désactivé pour des mesures, n'avait pas été réactivé. Au bout de 3,9 heures, `/health` répondait `droits_perimes` et chaque question était refusée (`Droits non garantis : droits non synchronisés depuis 3.9 h (limite 3 h)`). Une synchronisation manuelle a rétabli le service ; le test de non-divulgation est revenu à 70 OK, 2 INFO. C'est le cas pour lequel la limite a été conçue.

> **Validé sur la VM de test, 21 octobre 2026 (2.21.8) :** Mise à jour depuis la 2.21.7, Compose remplacé (il était resté en 2.21.1, point 150) ; `test_echec_droits.py` 42 tests OK et `test_revalidation_bm25.py` 14 tests OK, dans le conteneur ; âge des droits : limite passée à 0,01 h, `/health` à `droits_perimes`, question refusée avec le motif `droits non synchronisés depuis 0.3 h (limite 0.01 h)`, puis `ok` et questions servies avec la limite de 3 heures ; droit retiré sur le vrai Qdrant : `Bilan : OK` ; test de non-divulgation inchangé (70 OK, 2 INFO). Les modifications de `deploy.sh` (installation neuve, registre absent, tests manquants) sont vérifiées par simulation, pas sur une VM neuve.

> **Validé sur la VM de test, 20 octobre 2026 (2.21.7) :** 31 et 14 tests unitaires OK dans le conteneur ; registre de la 2.21.6 accepté au démarrage ; synchronisation interrompue simulée (marqueur posé à la main, RAG API redémarrée) : `Synchronisation des droits inachevée`, question refusée dans Open WebUI ; synchronisation lancée : `questions de nouveau servies`, `success=True`, question de nouveau servie ; droit retiré sur le vrai Qdrant : `Bilan : OK` ; test de non-divulgation inchangé (70 OK, 2 INFO).

> **Validé sur la VM de test, 20 octobre 2026 :** 23 et 14 tests unitaires OK dans le conteneur. Le registre n'existait pas sur cette installation, antérieure à la 2.21.6 : au démarrage, la RAG API a journalisé `Registre ... absent : ... AUCUNE question servie`. Une synchronisation a levé le refus (`questions de nouveau servies`, `success=True`) et créé le registre (droits 640). Après un redémarrage de la RAG API, le registre a été relu sans nouvelle alerte. Registre mis de côté puis RAG API redémarrée : une question posée dans Open WebUI a reçu « Vérification des droits en cours : réessayer après la prochaine synchronisation », sans réponse. La synchronisation horaire suivante a recréé le registre et levé le refus d'elle-même. Droit retiré sur le vrai Qdrant : `Bilan : OK` ; test de non-divulgation inchangé (70 OK, 2 INFO).

> **Validé sur la VM de test, 20 octobre 2026 :** `test_echec_droits.py` 12 tests OK et `test_revalidation_bm25.py` 14 tests OK, dans le conteneur ; synchronisation réelle avec le nouveau `acl_resolver.py` : `success=True`, aucun document retiré ; test du droit retiré sur le vrai Qdrant : `Bilan : OK` ; test de non-divulgation inchangé (70 OK, 2 INFO) ; une question réelle dans Open WebUI, réponse citée.

### §16.5.3 Des droits par SID, plus par noms (2.22.0)

**Le défaut.** Jusqu'à la 2.21.11, la stack comparait des **noms** : `acl_resolver.py` enregistrait les droits tels que `smbcacls` les affiche (`BSCULIER\RH`), et `auth.py` fabriquait des noms du même format à partir des groupes de l'annuaire (`memberOf`). Windows, lui, raisonne en **SID** (identifiants de sécurité). Trois écarts en découlaient (points 14, auth.1 et auth.2 du suivi) :

- **le groupe principal** (« Utilisateurs du domaine ») n'apparaît jamais dans `memberOf` : un document autorisé à ce seul groupe était invisible pour tous ;
- **un groupe dont le nom affiché (CN) diffère du nom pré-Windows 2000**, que `smbcacls` affiche, ne correspondait pas ; et si le CN d'un groupe égalait le nom pré-2000 d'un autre, les membres du premier auraient obtenu les droits du second ;
- **les identités intégrées** (« Utilisateurs authentifiés », « Tout le monde », groupes `BUILTIN`) ne sont pas des groupes de l'annuaire.

Les deux premiers écarts allaient presque toujours dans le sens prudent (documents invisibles), sauf la collision de noms.

**La correction.**

- `acl_resolver.py` lit les droits avec `smbcacls --numeric` : SID, type d'entrée (`0` autorisation, `1` refus), drapeaux et masque en hexadécimal. **Une ligne d'ACL non reconnue rend le fichier illisible**, donc retiré de la recherche : ignorer une ligne pourrait ignorer un refus. Un type d'entrée inconnu est traité comme un refus. Le contrôle du masque (§16.5) est inchangé : une entrée en écriture seule n'accorde rien.
- `auth.py` lit le SID du compte et l'attribut calculé **`tokenGroups`**, qui donne en une lecture les SID de tous les groupes de sécurité : directs, imbriqués, et le groupe principal. **Si `tokenGroups` ne peut pas être lu, aucun groupe n'est retourné : accès refusé**, sans repli sur une résolution partielle.
- Un nom ne servant plus à aucune décision, la collision de noms disparaît. Les noms restent dans le journal du conteneur, à côté des SID, pour le dépannage (`[AUTH] SID retenus pour '…' : S-1-5-21-…-513 (Utilisateurs du domaine), …`).

**Les groupes intégrés (`S-1-5-32-…`) sont ignorés par défaut.** `tokenGroups` renvoie ceux de l'annuaire, qui ne valent que sur les contrôleurs de domaine. Sur un serveur de fichiers, une ACL `BUILTIN\Utilisateurs` désigne le groupe **local** du serveur, au même SID mais aux membres définis sur ce serveur. Les confondre recréerait une équivalence approximative, exactement ce que la 2.22.0 supprime. « Tout le monde » (`S-1-1-0`) et « Utilisateurs authentifiés » (`S-1-5-11`) ne figurent pas dans `tokenGroups`. Les documents autorisés à ces seules identités restent donc invisibles, comme avant. `ACL_SID_ETENDUS=1` garde les groupes intégrés et ajoute ces deux identités à tout compte trouvé : plus fidèle à Windows dans le cas courant, mais à décider après revue des droits des partages, souvent trop ouverts pour ces identités.

**Ce qui s'élargit, et qu'il faut regarder avant la mise à jour.** Le groupe principal étant reconnu, **un document lisible par « Utilisateurs du domaine » devient visible pour tous les comptes du domaine**. C'est fidèle aux droits du partage, que Windows applique déjà, mais c'est un changement visible. Pour lister ces documents après la migration :

```bash
docker exec -w /app rag-api python3 -c "import main; s=set(); [s.add(p.payload['source']) for c in (main.COLLECTION, main.DOCUMENTATION_COLLECTION) for p in main.qdrant.scroll(collection_name=c, limit=10000, with_payload=['source','autorises'])[0] if any(str(a).endswith('-513') for a in p.payload.get('autorises',[]))]; print(len(s)); [print(x) for x in sorted(s)]"
```

Dans le lab, 54 documents : toute la documentation publique du dossier `DOIT4EVERYONE`, dont le partage accorde bien la lecture à « Utilisateurs du domaine ». Un document qui ne devrait pas y figurer se corrige **sur le partage**, pas dans la RAG.

**La migration, sans mélange.** Après la mise à jour, les droits encore enregistrés dans Qdrant sont des noms : aucun SID d'utilisateur ne leur correspond, les documents SMB sont donc **invisibles** jusqu'à la synchronisation suivante, à lancer aussitôt. À la fin de chaque passage, `acl_resolver.py` vérifie que **tous** les documents SMB ont des droits en SID. Un document encore au format des noms est compté comme un échec d'écriture : retiré de la recherche, signalé dans le rapport (`documents_non_migres_sid`), et l'alerte part. SharePoint et Purview ne sont pas concernés : leurs droits sont des identifiants Entra.

**Contrôler un compte** : `diag_sid.py` affiche les SID de `tokenGroups`, leur nom, et ceux que la RAG API retient. Il vérifie aussi que le compte de service lit `tokenGroups` ; dans certains domaines durcis, il faut l'ajouter au groupe « Groupe d'accès d'autorisation Windows ».

```bash
docker exec -w /app rag-api python3 /rag-pipeline/diag_sid.py <compte@domaine>
```

**Tests.** `test_sid.py` (16 tests, obligatoire et bloquant dans `deploy.sh`) part de **sorties réelles** de `smbcacls --numeric` relevées sur le partage du lab : boîte de dépôt (écriture seule écartée), refus explicite (prioritaire), entrées héritées, ligne au format des noms (fichier illisible), lecture de `tokenGroups` refusée (aucun groupe). `test_echec_droits.py` vérifie le contrôle de migration. Le test de non-divulgation, qui fonctionne par comptes, sert de contrôle avant et après.

> **Validé sur la VM de test, 22 octobre 2026 (2.22.0) :** `tokenGroups` lu par le compte de service sans droit supplémentaire (18 SID pour un compte administrateur, 3 pour un compte de test) ; synchronisation `success=True`, 70 fichiers relus, 1 692 extraits réécrits en SID, `documents_non_migres_sid` : 0 ; `test_sid.py` 16, `test_echec_droits.py` 46 et `test_revalidation_bm25.py` 14 tests OK ; droit retiré sur le vrai Qdrant : `Bilan : OK` ; test de non-divulgation inchangé (70 OK, 2 INFO), puis complété par le cas `DOC-DOMAINE` : un document autorisé à « Utilisateurs du domaine » est visible pour les 9 comptes, y compris un compte qui n'a que ce groupe (79 OK, 2 INFO). En 2.21.11, ce compte ne le voyait pas.

## §16.6 Durcissement de la RAG API

| Point | Avant | Après |
|---|---|---|
| Mot de passe SMB | Sur la ligne de commande de `smbcacls`, visible dans la liste des processus | Fichier d'identifiants temporaire en mémoire (`-A`), lisible par le seul processus |
| Juge en échec | Réponse considérée comme ancrée | Considérée comme non vérifiée : `/query` la bloque, le journal indique `verification: erreur` |
| Verdict du juge incohérent | « Ancrée » retenu même quand le juge cite des affirmations non sourcées | Réponse non ancrée dès que sa liste n'est pas vide, `[JUGE] Verdict incohérent` au journal (2.21.9, §10.12) |
| Réponse du juge incomplète | `{"ancree": true}` sans liste, ou une liste `null`, vide en texte ou mal formée, valait « ancrée » | « Ancrée » exige le booléen `true` **et** une liste vide ; sinon non ancrée, `[JUGE] Réponse du juge incomplète` au journal (2.21.10) |
| Réponse de refus | Moins de 200 caractères contenant « ne figure pas dans les documents » : acceptée sans juge | Seule la phrase de refus exacte est acceptée sans juge (2.21.9) |
| Verdict de Purview (`mip-service`) | Lu avec `bool()` : une chaîne « false » aurait autorisé | Seul le booléen `true` autorise (2.21.9) |
| Réponse non vérifiée dans Open WebUI | Rendue sans signal | Rendue, avec une mention invitant à vérifier dans les sources |
| Citations | Comparées par sous-chaîne | Correspondance exacte sur le nom de fichier |
| Deux documents de même nom | Lien vers le premier trouvé | Les deux emplacements sont indiqués |
| Panne de Qdrant ou de l'embedding | « Information absente » | Erreur 503 explicite |
| `/stats`, `/health` | `/stats` ouvert, `/health` révèle l'adresse du moteur | `/stats` réservé à l'administration, `/health` minimal |
| Empreinte des questions au journal | SHA-256 tronqué : une question courte se retrouve par dictionnaire | HMAC avec une clé secrète (`LOG_HMAC_KEY`) |
| Valeurs d'exemple (`changeme`) | Aucun signal | Avertissement au démarrage (2.17.0), puis **démarrage refusé** (2.21.0) |
| Identité de l'utilisateur | En-têtes simples `X-OpenWebUI-User-*`, que tout détenteur d'`API_TOKEN` pouvait écrire | Jeton signé par Open WebUI, vérifié par la RAG API (2.21.0) |
| `/query` | Accepté avec `API_TOKEN` | Réservé à `ADMIN_TOKEN` (2.21.0) |

Le jeton d'administration du lab était d'ailleurs resté à sa valeur d'exemple : la stack fonctionnait sans rien signaler. L'avertissement aurait suffi à le voir ; depuis la 2.21.0, la RAG API refuse de démarrer.

**Secrets refusés au démarrage (2.21.0).** La RAG API s'arrête (code de sortie 1) si l'un de ses secrets est vide, garde une valeur d'exemple (`changeme…`, ou un gabarit entier comme `<mot-de-passe>`), est trop court (32 caractères au moins pour les jetons et clés générés), ou si deux jetons sont identiques (`API_TOKEN`, `ADMIN_TOKEN`, `OWUI_JWT_SECRET`). Le journal dit lequel :

```bash
docker logs rag-api 2>&1 | grep SÉCURITÉ
# [SÉCURITÉ] ADMIN_TOKEN garde une valeur d'exemple
# [SÉCURITÉ] Démarrage refusé. Corriger le .env (jetons : openssl rand -hex 32), puis docker compose up -d rag-api
```

Les mots de passe de `svc-rag` (`LDAP_BIND_PWD`, `SMB_PASSWORD`) ne sont contrôlés que pour le vide et la valeur d'exemple : leur longueur dépend de la politique de l'annuaire. `deploy.sh` génère tous les jetons ; le refus concerne surtout une installation à la main ou un `.env` repris d'un essai.

**Identité signée (2.21.0).** La RAG API résout les droits d'après l'adresse de l'utilisateur transmise par Open WebUI. Jusqu'à la 2.20, cette adresse arrivait dans un en-tête simple : un client qui connaissait `API_TOKEN` pouvait y écrire l'adresse d'un autre compte et obtenir ses droits. Désormais, Open WebUI signe l'identité avec un secret partagé (`OWUI_JWT_SECRET` du `.env`, passé à Open WebUI par `FORWARD_USER_INFO_HEADER_JWT_SECRET`) : jeton HS256, émetteur `open-webui`, valable cinq minutes. La RAG API vérifie la signature, l'émetteur et l'échéance, et ignore les en-têtes simples. Sans jeton valide : refus (403).

Contrôle d'usurpation, sur la VM (une seule ligne) :

```bash
docker exec rag-api python3 -c "import os,json,urllib.request as u; d=json.dumps({'model':'rag-api','messages':[{'role':'user','content':'test'}]}).encode(); r=u.Request('http://localhost:8080/v1/chat/completions',data=d,headers={'Authorization':'Bearer '+os.environ['API_TOKEN'],'Content-Type':'application/json','X-OpenWebUI-User-Email':'<COMPTE>@votre-domaine.ch'}); print(u.urlopen(r).status)"
# Attendu, en dernière ligne : urllib.error.HTTPError: HTTP Error 403: Forbidden
docker logs rag-api 2>&1 | grep "identité non signée" | tail -1
```

> **Validé sur la VM de test, octobre 2026 (2.21.0) :** une question posée dans Open WebUI obtient sa réponse, avec les 17 groupes du compte de test ; un en-tête d'identité simple est refusé (403) ; `/query` avec `API_TOKEN` est refusé (401) ; `test_cloisonnement.py`, qui passe désormais par `ADMIN_TOKEN`, donne 6 cas conformes sur 6. Rejoué le 19 octobre 2026 sur un déploiement neuf (2.21.1), avec la commande ci-dessus telle quelle : `HTTP Error 403`, ligne `identité non signée reçue` au journal ; cloisonnement 72 verdicts, aucune fuite.

## §16.7 Open WebUI, n8n et le moteur d'inférence

**Open WebUI** : depuis la 2.21.0, Open WebUI ne publie plus de port ; il n'est joignable que par Nginx, en HTTPS (§9.8). Il signe l'identité transmise à la RAG API (§16.6). `ENABLE_VERSION_UPDATE_CHECK=false` supprime la vérification des nouvelles versions et la bannière qui invite à mettre à jour (§16.8).

Dans **Réglages d'administration** → **Connexions**, désactiver **API Ollama** et **Direct connexions**. Les utilisateurs ne voient plus que le modèle de la RAG API, et ne peuvent pas ajouter eux-mêmes l'adresse d'Ollama. Faire ce réglage dans l'interface : la variable `ENABLE_OLLAMA_API=false`, placée dans le Compose du dépôt, n'est lue qu'au **premier** démarrage d'Open WebUI, qui garde ensuite ses réglages dans sa base.

**Le moteur d'inférence** : Ollama écoute sur le réseau pour que la VM puisse l'atteindre, donc n'importe quel poste peut l'interroger directement. Pas de fuite du corpus par ce chemin (le modèle n'a pas les documents), mais ni journal ni contrôle. Le pare-feu du serveur d'inférence doit n'accepter le port 11434 que depuis la VM de la stack. Si la VM est derrière un routeur qui traduit les adresses, le serveur voit l'adresse du routeur : la restriction se complète alors sur le routeur. Vérification : depuis un autre poste, `curl -m 5 http://<serveur>:11434/api/tags` doit échouer.

**n8n** : depuis la 2.21.0, n8n ne publie plus de port ; il est joint par `https://<RAG_FQDN>:5678`, à travers Nginx (§9.8). Le jeton d'administration n'est plus écrit dans les nœuds HTTP. Un identifiant unique de type **Header Auth** (*Name* `Authorization`, *Value* `Bearer <jeton>`, domaine autorisé : `rag-api`) est utilisé par les nœuds de synchronisation et de synthèse Teams, avec « Send Headers » désactivé. Le jeton n'apparaît plus dans les workflows ni dans leurs exports, et sa rotation se fait en un seul endroit :

```bash
cd /root/rag-stack
sed -i "s/^ADMIN_TOKEN=.*/ADMIN_TOKEN=$(openssl rand -hex 32)/" .env
docker compose up -d rag-api                      # recrée le conteneur (§15.3.6)
grep '^ADMIN_TOKEN=' .env | cut -d= -f2           # à reporter dans l'identifiant n8n
```

## §16.8 Une mise à jour se revalide : le cas d'Open WebUI

En figeant les versions (§3.4), le lab est passé d'une construction de développement d'Open WebUI (tag `main`) à la version publiée `v0.11.3`. Deux effets, invisibles sans revalidation :

| Constat | Cause | Correction |
|---|---|---|
| Plus aucune réponse affichée, alors que la RAG API répondait (code 200) | La version publiée demande la réponse **en flux** et n'affiche rien si elle reçoit un objet JSON simple ; la RAG API ignorait la demande | La RAG API respecte désormais la demande de flux. La réponse est calculée en entier, contrôles compris, puis envoyée en un seul fragment : un vrai flux mot par mot enverrait le texte avant le contrôle d'ancrage |
| Plusieurs requêtes par question | Tâches d'arrière-plan d'Open WebUI (titres, étiquettes, questions de suivi) adressées au modèle de la conversation : quatre appels par question dans le lab | Désactivées par le Compose du dépôt pour un déploiement neuf, ou dans **Interface** pour une base existante (§14.8.2, §0 étape 14) ; elles multiplient le calcul et polluent le journal nLPD, sans fausser les réponses |

La leçon tient en une règle : **une mise à jour d'Open WebUI, de n8n ou de Qdrant ne s'installe pas sur une invitation à mettre à jour**. Elle se fait sur décision, puis se revalide : connexions d'Open WebUI, transmission de l'identité (`[AUTH] /v1` dans les journaux), test de cloisonnement, synchronisation.

**Versions figées jusqu'à l'octet (2.21.0).** Un numéro de version (`tag`) peut être republié sur Docker Hub avec un autre contenu. Le `docker-compose.yml` fixe donc chaque image du déploiement standard par son numéro **et** son empreinte (le reranker facultatif du §10.8 excepté) (`image: nginx:1.30.6-alpine@sha256:…`) : Docker refuse une image dont le contenu diffère. L'image de base de la RAG API (`python:3.11-slim`) est figée de la même façon dans le `Dockerfile`, et `api/requirements.txt` fixe toutes les dépendances Python à la version exacte, relevées par `pip freeze` dans le conteneur validé. Validé sur la VM de test : deux constructions successives donnent la même liste de paquets, et un `docker compose pull` ne télécharge rien.

**Mettre à jour une image**, Nginx par exemple, quand une nouvelle version stable est publiée (`nginx.org`, rubrique des versions) :

```bash
# 1. Télécharger la nouvelle version et relever son empreinte
docker pull nginx:<VERSION>-alpine
docker image inspect --format '{{index .RepoDigests 0}}' nginx:<VERSION>-alpine
# → nginx@sha256:<EMPREINTE>

# 2. Reporter numéro et empreinte dans /root/rag-stack/docker-compose.yml :
#    image: nginx:<VERSION>-alpine@sha256:<EMPREINTE>

# 3. Recréer le seul conteneur concerné, puis contrôler
cd /root/rag-stack
docker compose up -d nginx
docker exec nginx nginx -v
curl --cacert /etc/ssl/certs/ad-chain.pem https://<RAG_FQDN>/sante
```

En cas de problème, remettre l'ancienne ligne `image:` et relancer `docker compose up -d nginx`. Même démarche pour Qdrant, n8n et Open WebUI, avec la revalidation ci-dessus. Pour les dépendances Python, modifier la version dans `requirements.txt`, reconstruire (`docker compose build rag-api`), revalider, puis relever la liste complète par `docker exec rag-api pip freeze`.

> **Branche suivie pour Nginx :** la branche *stable* (paire : 1.30 en octobre 2026). Une branche stable n'est plus maintenue quand la suivante sort : la 1.28 ne reçoit plus de correctifs depuis la sortie de la 1.30. Validé sur la VM de test avec la 1.30.6.

**Revue des versions.** Figer n'est pas oublier : les correctifs de sécurité n'arrivent que si quelqu'un met à jour. Revoir les versions de chaque composant lors de l'audit périodique (§17.6), et plus tôt en cas d'alerte de sécurité publiée pour l'un d'eux. Comme la bannière de mise à jour d'Open WebUI est désactivée, cette revue est le seul signal.

## §16.9 Une perte d'accès doit se détecter

Pendant ces tests, une coupure réseau de quelques instants a empêché la RAG API de joindre Microsoft Entra. Pour l'utilisateur concerné, la résolution des identités cloud a échoué : il n'a gardé que ses groupes AD (3 au lieu de 8), et a perdu l'accès à tous les documents SharePoint. Le comportement de sécurité était le bon (moins d'accès, jamais plus), mais la réponse ne l'était pas : « Cette information ne figure pas dans les documents disponibles », alors que le document existait et que l'utilisateur y avait droit.

Désormais, quand la résolution Entra échoue, la réponse le dit : « Les documents SharePoint n'ont pas pu être consultés : la vérification de vos droits auprès de Microsoft 365 a échoué. Réessayez dans quelques minutes. » L'échec n'est pas mis en cache : la question suivante retente la résolution.

Le contrôle après synchronisation (§16.4) détecte aussi ce cas : si la panne dure jusqu'à la synchronisation, les cas SharePoint autorisés sortent en « REFUS À TORT », et l'alerte part. Le contrôle ne signale donc pas seulement les fuites, mais aussi les pertes d'accès.

> **Un message d'erreur peut tromper.** Le journal indiquait `Network is unreachable`, une erreur IPv6, alors que la cause était une coupure IPv4. Le conteneur n'ayant pas d'IPv6, le système essaie l'IPv4, puis l'IPv6 en dernier recours : quand tout échoue, c'est la dernière erreur qui s'affiche. Vérifier la connectivité réelle (`curl` depuis la VM et depuis le conteneur) avant de conclure.

> **Deux jetons, deux usages.** `ADMIN_TOKEN` sert à n8n (synchronisation, synthèse Teams) et aux tests (`/query`), `API_TOKEN` à Open WebUI (questions des utilisateurs). Le lab avait renouvelé le premier ; l'avertissement de démarrage (§16.6) a signalé dès son premier lancement que le second gardait sa valeur d'exemple. Depuis la 2.21.0, la RAG API refuserait de démarrer. Sa rotation se fait dans le `.env`, puis dans la clé d'API de la connexion `rag-api` d'Open WebUI.

## §16.10 Supervision externe

Le contrôle après synchronisation (§16.4) alerte quand le cloisonnement est faux. Il ne dit rien si la stack est arrêtée, si la synchronisation ne tourne plus ou si le certificat arrive à échéance : **une alerte qui ne part pas ne se remarque pas.** Ces cas demandent une surveillance **depuis une autre machine** que la VM, puisqu'une VM arrêtée ne signale rien.

Le guide ne prescrit pas d'outil : l'organisation utilise le sien, s'il en a un. Ce qui compte, ce sont les contrôles.

### §16.10.1 Les contrôles

| Contrôle | Comment | Ce qu'il détecte | Exemple §16.10.2 |
|---|---|---|---|
| La stack répond, droits à jour | `GET https://<RAG_FQDN>/sante`, réponse contenant `ok` | VM, Nginx ou RAG API arrêtés, nom DNS perdu ; depuis la 2.21.8, droits trop anciens ou inconnus (`droits_perimes`, `droits_inconnus`), donc aussi n8n arrêté ou workflow désactivé | Oui |
| Le certificat est valide | Contrôle TLS de la même adresse, échéance | Certificat expiré ou proche de l'échéance (§9.8.6), chaîne cassée | Oui |
| La synchronisation tourne | Signal envoyé par n8n après chaque synchronisation (« Push ») ; absence de signal = alerte | n8n arrêté, workflow désactivé, synchronisation en échec | Oui |
| Le cloisonnement est juste | Courriel du contrôle après synchronisation (§16.4) | Fuite ou refus à tort | Déjà en place, sans outil |
| Espace disque | `/srv/rag-donnees`, `/var/log/rag`, espace Docker | Disque plein : Qdrant, journaux nLPD | Non, outil de l'organisation |
| Moteur d'inférence | Contrôle du serveur Ollama ou vLLM | Questions sans réponse alors que `/sante` répond | Non, outil de l'organisation |

> **Ce que `/sante` ne dit pas :** la réponse prouve que Nginx et la RAG API répondent, et, depuis la 2.21.8, que les droits ont été synchronisés depuis moins de `ACL_AGE_MAX_HEURES` (§16.5.2). Elle ne contrôle ni Qdrant, ni le moteur d'inférence, ni l'annuaire : `/health` est volontairement minimal (§16.6) et ne révèle rien de l'installation. Une question réelle reste le seul contrôle de bout en bout. **`ok` ne dit pas non plus que le dernier passage de chaque origine s'est bien déroulé** : après un passage incomplet, l'origine concernée est suspendue (`ACL_INCERTAIN_FERME=1`), mais `/sante` reste à `ok` tant que la dernière synchronisation complète a moins de `ACL_AGE_MAX_HEURES`. Ce cas est signalé par le rapport de synchronisation et l'alerte du workflow, qui doivent donc être actifs.

**Le certificat de l'autorité interne.** L'outil de supervision doit faire confiance à la racine de l'autorité, sinon la sonde HTTPS échoue ou doit ignorer les erreurs de certificat, et ne contrôle plus rien de ce côté. Pour un outil Node.js : variable `NODE_EXTRA_CA_CERTS` (§9.8.5).

**Le signal de synchronisation.** Le workflow `n8n-sync-corpus.json` du dépôt contient un nœud **Signal supervision (Push)**, **désactivé** par défaut. Branché en parallèle du test de résultat, il appelle l'adresse Push de l'outil après chaque synchronisation, avec `status=up` si elle a réussi, `status=down` sinon. Il ne bloque jamais le courriel d'erreur : en cas d'échec de l'appel, le workflow continue (*On Error* : *Continue*). Pour l'activer : remplacer `<NOM-COMPLET-SUPERVISION>` et `<CLE-PUSH>` dans l'URL, puis activer le nœud.

> **Nom complet obligatoire.** Le conteneur n8n ne résout pas les noms courts du domaine : `http://supervision:3001/...` échoue (`getaddrinfo EAI_AGAIN`), `http://supervision.votre-domaine.ch:3001/...` fonctionne. Le nom doit exister dans le DNS du domaine.

### §16.10.2 Exemple : Uptime Kuma

> **Exemple, pas une recommandation.** Uptime Kuma est un outil libre de surveillance, simple à installer en conteneur. Il a été utilisé dans le lab pour valider les trois premiers contrôles, sur une machine Docker existante, distincte de la VM de la stack. Testé avec Uptime Kuma 2.5.4, octobre 2026.

**Installation**, sur la machine de supervision (`/opt/uptime-kuma/docker-compose.yml`) :

```yaml
services:
  uptime-kuma:
    image: louislam/uptime-kuma:2.5.4@sha256:917318f9d7be5257f43ba412c766a473be336eb451d70744f3b482d0c3997c0e
    container_name: uptime-kuma
    ports:
      - "3001:3001"
    volumes:
      - ./data:/app/data
      # Chaîne de l'autorité interne (§9.2.4), pour contrôler le certificat de la stack
      - ./certs/ad-chain.pem:/certs/ad-chain.pem:ro
    environment:
      - NODE_EXTRA_CA_CERTS=/certs/ad-chain.pem
    mem_limit: 384m
    restart: unless-stopped
```

```bash
cd /opt/uptime-kuma
mkdir -p certs && cp /chemin/vers/ad-chain.pem certs/
docker compose up -d
```

L'interface s'ouvre sur `http://<machine-de-supervision>:3001` ; le premier compte créé est l'administrateur. Avant d'installer sur une machine qui porte déjà d'autres services, vérifier que le port 3001 est libre (`ss -tlnp | grep 3001`) et qu'il reste assez de mémoire.

**Notification.** Dans les paramètres d'Uptime Kuma, configurer une notification par courriel (SMTP), puis l'activer sur chaque sonde.

**Sonde 1, la stack et son certificat.** Nouvelle sonde :

- type **HTTP(s) - Mot-clé** ;
- URL `https://<RAG_FQDN>/sante`, mot-clé `ok` ;
- cocher la notification d'expiration du certificat.

**Sonde 2, la synchronisation.** Nouvelle sonde :

- type **Push** ; l'outil affiche une adresse Push, dont la clé est à reporter dans le nœud n8n (§16.10.1) ;
- intervalle de **3 900 secondes** : la synchronisation est horaire, l'alerte part si aucun signal n'arrive pendant 65 minutes.

> **Validé en lab, octobre 2026 :** la sonde 1 affiche la stack en service et l'échéance du certificat de l'autorité interne (chaîne validée grâce à `NODE_EXTRA_CA_CERTS`). La sonde 2 reçoit le signal de n8n, en ligne de commande et depuis le workflow. Synchronisation arrêtée, le courriel « [Synchronisation RAG] [🔴 Down] No heartbeat in the time window » est arrivé.

**Limites de cet exemple :**

- l'interface d'Uptime Kuma est en HTTP : la placer derrière un frontal HTTPS, ou la réserver au réseau d'administration ;
- la clé Push figure en clair dans l'URL du nœud n8n et dans les journaux de la machine de supervision : qui la connaît peut envoyer un faux signal « up ». Elle ne donne accès à rien d'autre ;
- l'appel Push part en HTTP ;
- une seule machine de supervision : si elle s'arrête, plus rien ne surveille. C'est le rôle de l'outil de l'organisation, s'il en a un, de couvrir ce cas.

## §16.11 Checklist

| Point | Vérification | Attendu |
|---|---|---|
| Test d'accès | `test_cloisonnement.py` | 0 FUITE, 0 ABSENT |
| Contrôle après synchronisation | `docker logs rag-api \| grep CLOISONNEMENT` | `N/N conformes, fuites=0` |
| Alerte | Contre-épreuve (fuite simulée) | Courriel « FUITE DE CLOISONNEMENT » reçu |
| Masque NTFS | Rapport de synchronisation | `entrees_allowed_sans_lecture` affiché |
| Droits sur les mots-clés | `test_revalidation_bm25.py` (§16.5.1) | `14 tests OK` |
| Droit retiré, vrai Qdrant | `test_revocation_bm25.py` (§16.5.1) | `Bilan : OK`, droits restaurés |
| Échecs d'écriture des droits | `test_echec_droits.py` (§16.5.2) | `46 tests OK` |
| Droits par SID | `test_sid.py` (§16.5.3) | `16 tests OK` |
| Migration vers les SID | `rapport_acl.json`, `documents_non_migres_sid` | 0 après la première synchronisation (§16.5.3) |
| Registre des documents retirés | `ls -l /var/log/rag/acl_bloques.json*` | Registre présent, pas de `.en_cours` hors synchronisation ; sinon, questions refusées jusqu'à une synchronisation terminée |
| Fermeture si les droits sont incertains | `grep ACL_INCERTAIN_FERME /root/rag-stack/.env` | 1, ou absent (1 par défaut) ; 0 seulement par choix documenté |
| Âge des droits | `curl -s https://<RAG_FQDN>/sante` | `{"status":"ok"}` ; `droits_perimes` ou `droits_inconnus` : synchronisation à relancer |
| Documents retirés de la recherche | `docker logs rag-api 2>&1 \| grep DROITS` | Aucune ligne, ou documents nommés et alerte reçue |
| Permissions du partage | `Set-AccesIndexationRAG.ps1 -Verifier` | Ouverture large, pas d'alerte |
| Valeurs d'exemple | `docker logs rag-api \| grep SÉCURITÉ` | Aucune ligne ; la RAG API est démarrée |
| Identité signée | Contrôle d'usurpation (§16.6) | HTTP 403 |
| `/query` | Appel avec `API_TOKEN` | HTTP 401 |
| `/stats` | Appel sans jeton | HTTP 401 ou 403 |
| Journal | `tail -1 /var/log/rag/rag-queries.jsonl` | `question_hash` commençant par `hmac:` |
| Open WebUI | Liste des modèles avec un compte utilisateur | `rag-api` seul |
| Moteur d'inférence | `curl` depuis un autre poste | Pas de réponse |
| n8n | Export d'un workflow | Aucun jeton en clair |
| Versions figées | `grep 'image:' docker-compose.yml` | Chaque image avec `@sha256:` |
| Supervision externe | Sondes `/sante` et Push (§16.10) | En service ; alerte reçue lors d'un essai |
| Échéance du certificat | Sonde ou `openssl x509 -checkend` (§9.8.6) | Plus de 30 jours |
| Après une mise à jour d'un composant | Connexions, `[AUTH] /v1`, test, synchronisation | Tout conforme avant d'utiliser la nouvelle version |

---

[Retour au sommaire](index.md) | [Section précédente : §15 Sécurité des données](section-15-securite-donnees.md) | [Section suivante : §17 Gouvernance](section-17-gouvernance.md)

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
