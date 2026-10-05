---
title: "Tests après modification | Guide de déploiement stack IA locale"
description: "Procédure de tests à dérouler après toute modification de la stack RAG : démarrage, identité, qualité des réponses, refus, cloisonnement, synchronisation."
---

# Tests à passer après une modification de la stack RAG

Les valeurs propres au lab (comptes, documents, nombre de groupes, nombre de cas) sont à remplacer par celles de votre environnement.

Chaque bloc se copie tel quel dans le terminal de la VM, en root. Aucune variable ni fonction à préparer. Après chaque bloc, comparer avec la colonne « Attendu ». Un test en échec arrête la procédure : on corrige, ou on revient en arrière (§11).

---

## 1. Sauvegarder l'état actuel

À faire **avant** de copier les nouveaux fichiers.

```bash
cd /root/rag-stack
cp api/main.py api/main.py.avant-test
cp api/auth.py api/auth.py.avant-test
cp docker-compose.yml docker-compose.yml.avant-test
ls -l api/main.py.avant-test api/auth.py.avant-test docker-compose.yml.avant-test
```

**Attendu :** les trois fichiers de sauvegarde listés.

---

## 2. Déployer

Les fichiers modifiés doivent être dans `/home/<admin>`.

```bash
cd /root/rag-stack
cp /home/<admin>/main.py api/main.py
cp /home/<admin>/auth.py api/auth.py
docker compose up -d --build rag-api
```

**Attendu :** `✔ Container rag-api Started`.

Rappel : `main.py` et `auth.py` sont copiés **dans l'image**, d'où `--build`. Après une simple modification du `.env`, utiliser `docker compose up -d rag-api` (sans `--build`), **jamais** `docker compose restart`, qui ne relit pas le `.env`.

---

## 3. Démarrage propre

```bash
sleep 15
cd /root/rag-stack
docker compose ps
```

**Attendu :** cinq lignes, toutes `Up` : `mip-service`, `n8n`, `open-webui`, `qdrant`, `rag-api`.

```bash
docker logs rag-api 2>&1 | grep -E "SÉCURITÉ|ERROR|Traceback" | tail -5
```

**Attendu :** aucune ligne.

```bash
docker logs mip-service 2>&1 | grep -i "prêt" | tail -1
```

**Attendu :** `Moteur initialisé, service prêt`.

---

## 4. Points d'accès

```bash
docker exec rag-api python3 -c "import httpx; print(httpx.get('http://localhost:8080/health').text)"
```

**Attendu :** `{"status":"ok"}`

```bash
docker exec rag-api python3 -c "import httpx; print(httpx.get('http://localhost:8080/stats').status_code)"
```

**Attendu :** `401` (ou `403`).

---

## 5. Identité et résolution Entra

Une question au nom de un compte aux droits limités, puis lecture du journal.

```bash
docker exec rag-api python3 -c "
import httpx, os
r = httpx.post('http://localhost:8080/v1/chat/completions', timeout=900,
    headers={'Authorization': 'Bearer ' + os.environ['API_TOKEN'],
             'X-OpenWebUI-User-Email': 'client@votre-domaine.ch'},
    json={'model': 'rag-api', 'messages': [{'role': 'user',
          'content': 'Que dit le guide de dépannage helpdesk ?'}]})
print(r.status_code)"
```

**Attendu :** `200`.

```bash
docker logs rag-api --since 5m 2>&1 | grep -E "\[AUTH\]|Entra" | tail -3
```

**Attendu :**
- une ligne `[AUTH] Entra : 5 identifiant(s) pour 'client@votre-domaine.ch'` ;
- une ligne `[AUTH] /v1 user 'client@votre-domaine.ch' : 8 groupe(s) et identité(s)` ;
- **aucune** ligne `Résolution Entra échouée`.

Si la résolution a échoué, tester la connectivité :

```bash
curl -sS -m 10 -o /dev/null -w "%{http_code}\n" https://login.microsoftonline.com
docker exec rag-api python3 -c "import httpx; print(httpx.get('https://login.microsoftonline.com', timeout=10).status_code)"
```

**Attendu :** `302` puis `302`.

---

## 6. Question précise : aucune régression

```bash
time docker exec rag-api python3 -c "
import httpx, os
r = httpx.post('http://localhost:8080/v1/chat/completions', timeout=900,
    headers={'Authorization': 'Bearer ' + os.environ['API_TOKEN'],
             'X-OpenWebUI-User-Email': 'direction@votre-domaine.ch'},
    json={'model': 'rag-api', 'messages': [{'role': 'user',
          'content': 'Quelle est la durée du contrat de maintenance de l Etude Rochat ?'}]})
print(r.json()['choices'][0]['message']['content'])"
```

**Attendu :**
- la réponse indique **24 mois à compter du 1er janvier 2026** ;
- elle cite `03_Contrat_Maintenance_Etude_Rochat.docx` ;
- noter la durée (ligne `real`).

Sources utilisées pour cette question :

```bash
tail -1 /var/log/rag/rag-queries.jsonl | python3 -c "
import json, sys
e = json.loads(sys.stdin.read())
print(e['timestamp'], e['user_id'], '| ancrée :', e.get('ancree'))
for s in e['sources_accessed']: print('    ', s)"
```

**Attendu :** le contrat Rochat en **première** ligne.

---

## 7. Question large : diversité des sources

```bash
time docker exec rag-api python3 -c "
import httpx, os
r = httpx.post('http://localhost:8080/v1/chat/completions', timeout=900,
    headers={'Authorization': 'Bearer ' + os.environ['API_TOKEN'],
             'X-OpenWebUI-User-Email': 'direction@votre-domaine.ch'},
    json={'model': 'rag-api', 'messages': [{'role': 'user',
          'content': 'fait moi un resumé sur tout ce que tu sais sur les clients'}]})
print(r.json()['choices'][0]['message']['content'])"
```

**Attendu :** une réponse qui couvre **plusieurs clients** (Étude Rochat & Associés, Baumont Industries SA, Sarrasin Fiduciaire SA). Noter la durée (ligne `real`).

Construction du contexte :

```bash
docker logs rag-api 2>&1 | grep "Contexte étendu" | tail -1
```

**Attendu :** une ligne du type `Contexte étendu : N chunks de '…', 6 document(s) complémentaire(s) (12 extraits), M copie(s) écartée(s)`. Noter le document principal, N et M.

Sources réellement envoyées au modèle :

```bash
tail -1 /var/log/rag/rag-queries.jsonl | python3 -c "
import json, sys
e = json.loads(sys.stdin.read())
print(e['timestamp'], e['user_id'], '| ancrée :', e.get('ancree'))
for s in e['sources_accessed']: print('    ', s)"
```

**Attendu :** parmi les sources, `03_Contrat_Maintenance_Etude_Rochat.docx`, `21_Contrat_Maintenance_Baumont_Industries.docx` et `04_Reponse_AO_Migration_Azure_Sarrasin.docx`.

La réponse varie d'une exécution à l'autre (température 0.2) : relancer ce test une deuxième fois avant de conclure. La liste des sources, elle, doit rester la même.

Réglages réellement appliqués dans le conteneur :

```bash
docker exec rag-api printenv | grep -E "CANDIDATS|PRINCIPAL_MAX|CONTEXT_OTHER_DOCS|EXTRAITS_PAR|MAX_CONTEXT_CHUNKS"
```

**Attendu :** soit aucune ligne pour les quatre premiers (valeurs par défaut du code : 30, 9, 6, 2), soit les valeurs du `.env` si elles ont été ajoutées au Compose.

---

## 7 bis. Questions sans réponse : le refus doit tenir

Indispensable après toute modification du prompt : une question à laquelle le corpus ne répond pas doit **toujours** être refusée.

**Question hors du domaine** (connaissance générale, absente du corpus) :

```bash
docker exec rag-api python3 -c "
import httpx, os
r = httpx.post('http://localhost:8080/v1/chat/completions', timeout=900,
    headers={'Authorization': 'Bearer ' + os.environ['API_TOKEN'],
             'X-OpenWebUI-User-Email': 'direction@votre-domaine.ch'},
    json={'model': 'rag-api', 'messages': [{'role': 'user',
          'content': 'Quelle est la capitale de l Australie ?'}]})
print(r.json()['choices'][0]['message']['content'])"
```

**Attendu :** `Cette information ne figure pas dans les documents disponibles.` Toute autre réponse (« Canberra », par exemple) signifie que le modèle utilise ses connaissances générales : à corriger avant d'aller plus loin.

**Question du domaine, mais sans réponse** (le piège le plus dangereux : des documents proches existent, la tentation d'inventer est forte) :

```bash
docker exec rag-api python3 -c "
import httpx, os
r = httpx.post('http://localhost:8080/v1/chat/completions', timeout=900,
    headers={'Authorization': 'Bearer ' + os.environ['API_TOKEN'],
             'X-OpenWebUI-User-Email': 'direction@votre-domaine.ch'},
    json={'model': 'rag-api', 'messages': [{'role': 'user',
          'content': 'Quel est le montant mensuel du contrat de maintenance de la société Dupont Logistique SA ?'}]})
print(r.json()['choices'][0]['message']['content'])"
```

**Attendu :** un refus, ou une réponse qui dit explicitement qu'aucun document ne concerne Dupont Logistique SA. **Aucun montant** ne doit apparaître : un montant tiré d'un autre contrat serait une invention.

Vérifier aussi le contrôle d'ancrage de la dernière question :

```bash
tail -1 /var/log/rag/rag-queries.jsonl | python3 -c "
import json, sys
e = json.loads(sys.stdin.read())
print('ancrée :', e.get('ancree'), '| vérification :', e.get('verification'))"
```

**Attendu :** `ancrée : True | vérification : effectuee`.

Pour la question large du §7, relire aussi ce résultat juste après l'avoir posée : une réponse partielle doit rester **ancrée** (`True`). Si elle est `False`, la réponse affiche une mention d'avertissement dans Open WebUI, et le modèle a probablement ajouté des éléments non sourcés.

---

## 8. Open WebUI

Test manuel.

1. Se connecter à Open WebUI avec **un compte aux droits limités**.
2. Ouvrir la liste des modèles. **Attendu :** `rag-api` seul.
3. Poser la question : `Que dit le guide de dépannage helpdesk ?` **Attendu :** une réponse citée, affichée dans la conversation.
4. Dans le terminal, juste après :

```bash
docker logs -t --since 2m rag-api 2>&1 | grep -c "\[AUTH\] /v1"
```

**Attendu :** `2` (la question, et la génération du titre par Open WebUI), ou `1` si la génération des titres est désactivée.

---

## 9. Cloisonnement

### 9.1 Mode accès : le test de sécurité

```bash
docker exec -it rag-api python3 /rag-pipeline/test_cloisonnement.py /rag-pipeline/cas_cloisonnement.json
```

**Attendu :** dernière ligne `Bilan : {'OK': 40}`. Aucune `FUITE`, aucun `ABSENT`, aucun `REFUS À TORT`.

En cas de `FUITE` : arrêter immédiatement le service, puis analyser.

```bash
cd /root/rag-stack && docker compose stop rag-api
```

### 9.2 Mode complet : deux cas représentatifs

Une à deux minutes par cas. Le `-it` permet d'arrêter le test avec Ctrl+C.

```bash
docker exec -it rag-api python3 /rag-pipeline/test_cloisonnement.py /rag-pipeline/cas_cloisonnement.json --mode complet --cas S14-FIN
```

**Attendu :** `Bilan : {'OK': 4}`.

```bash
docker exec -it rag-api python3 /rag-pipeline/test_cloisonnement.py /rag-pipeline/cas_cloisonnement.json --mode complet --cas NTFS-DEPOT
```

**Attendu :** `Bilan : {'OK': 4}`.

Un `MANQUÉ` n'est pas un problème de sécurité : le document autorisé n'est simplement pas remonté par la recherche.

Si un test a été lancé **sans** `-it` et continue de tourner :

```bash
docker exec rag-api pkill -f test_cloisonnement
```

---

## 10. Synchronisation, Teams et journal

### 10.1 Synchronisation

Dans n8n, ouvrir **RAG Stack - Synchronisation corpus**, cliquer **Execute workflow**, attendre la fin, puis :

```bash
docker logs rag-api 2>&1 | grep -E "\[SYNC\] Terminé|\[CLOISONNEMENT\]" | tail -2
```

**Attendu :**
- `[SYNC] Terminé : success=True, quarantine=0, errors=0`
- `[CLOISONNEMENT] 40/40 conformes, fuites=0, refus à tort=0, absents=0, erreurs=0`

et **aucun courriel** reçu.

```bash
grep -o '"entrees_allowed_sans_lecture": [0-9]*' /var/log/rag/rapport_acl.json
```

**Attendu :** `"entrees_allowed_sans_lecture": 2`.

### 10.2 Synthèse Teams

Dans n8n, ouvrir le workflow Teams, cliquer **Execute workflow**.

**Attendu :** exécution terminée sans erreur 401.

### 10.3 Journal des requêtes

```bash
tail -1 /var/log/rag/rag-queries.jsonl
```

**Attendu :** `"question_hash": "hmac:…"` et `"verification": "effectuee"`.

---

## 11. Retour arrière

Si un test échoue et que la cause n'est pas évidente, revenir à l'état sauvegardé au §1 :

```bash
cd /root/rag-stack
cp api/main.py.avant-test api/main.py
cp api/auth.py.avant-test api/auth.py
cp docker-compose.yml.avant-test docker-compose.yml
docker compose up -d --build rag-api
```

Puis repasser les tests 3, 9.1 et 10.1.

---

## 12. Réponse de référence pour la question large (§7)

Réponse obtenue fin septembre 2026 avec le compte `direction@votre-domaine.ch` : trois clients couverts, Étude Rochat & Associés, Baumont Industries SA et Sarrasin Fiduciaire SA, avec pour chacun le contrat ou l'appel d'offres, le périmètre et la durée, à partir de `03_Contrat_Maintenance_Etude_Rochat.docx`, `21_Contrat_Maintenance_Baumont_Industries.docx` et `04_Reponse_AO_Migration_Azure_Sarrasin.docx`.

---

## Fiche de résultat

| § | Test | Résultat | À noter |
|---|---|---|---|
| 3 | Démarrage propre | | |
| 4 | Points d'accès | | |
| 5 | Identité et Entra | | Groupes : |
| 6 | Question précise | | Durée : |
| 7 | Question large | | Principal : / Documents clients : / Durée : |
| 7 bis | Questions sans réponse | | Capitale : / Dupont : |
| 8 | Open WebUI | | Requêtes par question : |
| 9.1 | Cloisonnement, mode accès | | |
| 9.2 | Cloisonnement, mode complet | | |
| 10.1 | Synchronisation et contrôle | | |
| 10.2 | Synthèse Teams | | |
| 10.3 | Journal | | |

Date : ………… Modification testée : ……………………
