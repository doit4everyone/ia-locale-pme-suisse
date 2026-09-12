---
title: "§4 Configuration Onyx | Guide de déploiement stack IA locale"
description: "Déploiement d'Onyx community edition et connexion à Ollama sur VM-RAG-LAB Ubuntu 26.04."
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

# §4 Configuration Onyx

[Retour au sommaire](index.md) | [Section précédente : §3 Docker Compose](section-03-docker-compose.md)

**Statut :** validé partiellement sur VM-RAG-LAB, septembre 2026. Le chemin de menu Admin → Language Models → Ollama est à confirmer en live (voir §4.5). Le bloc DGX Spark et §4.8 sont documentaires, non validés sur matériel réel.

---

> **Prérequis RAM :** dans la configuration finale de ce guide (Onyx seul, inférence déportée sur Ollama), **16 Go suffisent**. Onyx avec OpenSearch occupe environ 10 à 12 Go en charge. Pour faire tourner vLLM dans la VM en parallèle pour des tests, il faut au minimum 32 Go : les deux composants ne peuvent pas cohabiter sur 16 ou 20 Go.

---

## §4.1 Déploiement Onyx via le repo officiel

Onyx ne s'intègre pas comme un simple conteneur dans notre Docker Compose custom. Il dispose de sa propre stack complète (OpenSearch, Postgres, Redis, MinIO, Nginx, Celery) et se déploie via son repo officiel.

```bash
cd ~
git clone https://github.com/onyx-dot-app/onyx.git
cd onyx/deployment/docker_compose
```

---

## §4.2 Configuration du fichier .env

```bash
cp env.template .env

# Générer et injecter le secret d'authentification (obligatoire)
SECRET=$(openssl rand -hex 32)
sed -i "s|USER_AUTH_SECRET=\"\"|USER_AUTH_SECRET=\"${SECRET}\"|" .env

# Vérifier que l'injection a fonctionné
grep USER_AUTH_SECRET .env

# URL de base
echo "WEB_DOMAIN=http://10.100.1.15" >> .env
```

> **Ne pas configurer les variables GEN_AI_* dans le `.env` avant le premier démarrage.** Onyx valide le nom du modèle en base Postgres au démarrage. Si la base est vide et qu'un modèle non reconnu est injecté via `.env`, l'`api_server` plante en boucle. Configurer le LLM via l'interface admin après le premier démarrage propre.

---

## §4.3 Optimisation mémoire OpenSearch

La valeur par défaut du heap OpenSearch dans `docker-compose.yml` est `-Xms2g -Xmx2g`, trop élevée pour une VM de validation. La réduire avant le premier lancement :

```bash
sed -i 's/OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g/OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx1g/' docker-compose.yml

grep "OPENSEARCH_JAVA_OPTS" docker-compose.yml
```

> **Note :** cette modification doit être faite dans `docker-compose.yml` directement. La variable `OPENSEARCH_JAVA_OPTS` dans `.env` est ignorée car la valeur est hardcodée dans le fichier Compose.

---

## §4.4 Lancement de la stack Onyx

```bash
docker compose -f docker-compose.yml up -d
```

Le premier lancement télécharge environ 3 Go d'images. Vérifier l'état après 2 minutes :

```bash
docker compose -f docker-compose.yml ps
```

Tous les services doivent être `healthy` ou `Up`. Si `api_server` est en erreur, vérifier les logs :

```bash
docker logs onyx-api_server-1 --tail=20
```

---

## §4.5 Configuration du LLM via l'interface admin

Le backend LLM retenu est **Ollama sur LABO-G9**. La configuration vLLM-cpu dans la VM a été testée et abandonnée : les détails et les raisons sont en §4.8.

**Prérequis sur LABO-G9 :** définir les variables d'environnement utilisateur Windows avant de lancer Ollama.

```
OLLAMA_KEEP_ALIVE=600
OLLAMA_CONTEXT_LENGTH=32768
```

**Timeout Onyx :** ajouter dans le `.env` d'Onyx (sur VM-RAG-LAB) :

```
LLM_SOCKET_READ_TIMEOUT=300
```

Après modification du `.env`, redémarrer avec `down && up`, pas juste `restart` :

```bash
docker compose -f docker-compose.yml down && docker compose -f docker-compose.yml up -d
```

**Depuis un navigateur du réseau lab**, ouvrir `http://10.100.1.15` et créer le compte administrateur au premier lancement.

Naviguer dans **Admin → Language Models → Ollama → Connect** et renseigner :

> **Chemin de menu à vérifier :** ce chemin a été reconstruit par analogie avec le chemin OpenAI-Compatible. Si le provider natif Ollama ne figure pas dans la liste, utiliser **OpenAI-Compatible** avec `http://<IP-HOTE-OLLAMA>:11434/v1` comme API Base URL et laisser le champ API Key vide. Le `/v1` est requis : Ollama expose sa compatibilité OpenAI sur ce suffixe. Si Onyx ajoute `/v1` lui-même, l'URL sans suffixe `http://<IP-HOTE-OLLAMA>:11434` évite le doublon qui retourne un 404. À noter lors de la vérification en live.

| Champ | Valeur |
|---|---|
| Type | Ollama (natif) |
| API Base URL | `http://<IP-HOTE-OLLAMA>:11434` |
| Display Name | DEMO 1 |
| Modèle | `qwen2.5:14b` |

Cliquer **Connect**. Le provider apparaît dans la liste avec le badge **Default**.

---

## §4.6 Modèle d'embedding

Migrer de `intfloat/multilingual-e5-small` vers `intfloat/multilingual-e5-base` pour de meilleures correspondances sémantiques sur le multilingue. La réindexation complète prend 10 à 15 minutes sur un corpus d'une quarantaine de documents.

Dans **Admin → Embedding Models**, sélectionner `intfloat/multilingual-e5-base` et lancer la réindexation. Attendre la fin avant de tester les requêtes RAG.

---

## §4.7 Résultats de validation et points d'attention

### Résultats de validation RAG

Les résultats suivants ont été obtenus avec le corpus de démonstration Axonix SA (cinq documents fictifs déposés dans SharePoint Direction). Le corpus est fictif et ne correspond à aucune entreprise réelle.

| Question | Réponse attendue | Résultat |
|---|---|---|
| "Quel est le chiffre d'affaires d'Axonix SA ?" | CHF 3,2 millions | Correct avec citation SharePoint |
| "Quelle est la vision d'Axonix pour l'IA locale ?" | Référence romande nLPD, 15 clients PME d'ici 2026 | Correct avec citation SharePoint |

> **Note de fiabilité :** ces résultats sont corrects dans les conditions de test décrites. La fiabilité varie selon la formulation de la question et l'état du modèle en mémoire. Des questions formulées par analogie ("fais pareil pour X") ont produit des hallucinations complètes lors de sessions ultérieures. L'analyse détaillée et les règles de formation utilisateurs font l'objet d'une section dédiée dans ce guide.

### Points d'attention

- **Filtre de date dans le chat Onyx :** le désactiver pour éviter d'exclure des documents récents de l'index.
- **Purview chiffrement :** les documents portant un label appliquant un chiffrement sont indexés mais leur contenu est illisible dans OpenSearch. Seuls les labels sans protection permettent l'indexation. Un compte super user Purview lèverait la limitation, mais cette voie est déconseillée pour un indexeur permanent : le privilège rend son détenteur propriétaire de tout le contenu protégé du tenant, et les extraits indexés sont ensuite stockés en clair, sans la protection d'origine. La question est traitée dans la Partie 2.
- **Modèle minimum pour function calling :** deux critères à distinguer. Capacité : un modèle 8B est capable de function calling, un 4B est instable. Vitesse sur CPU : `qwen2.5:14b` est recommandé en pratique parce que les modèles 8B sont trop lents sur CPU pour les timeouts d'Onyx, même portés à 300 secondes. Avec un GPU, un bon modèle 8B peut suffire.
- **Analogies dans les prompts :** la formulation "fais pareil" court-circuite le guardrail du prompt strict et déclenche des hallucinations par analogie. Former les utilisateurs à poser des questions directes. Ce comportement est documenté dans la section consacrée à la fiabilité du pipeline.

---

## §4.8 Configuration alternative : vLLM dans la VM (non retenue)

> **Cette configuration a été testée et abandonnée.** Elle est documentée ici comme référence et pour les lecteurs qui disposent d'une VM avec au moins 32 Go de RAM.

La configuration vLLM-cpu dans la VM nécessite qu'Onyx et vLLM cohabitent. Sur 32 Go de RAM, vLLM doit être lancé avec les paramètres de compatibilité Onyx suivants :

```bash
VLLM_TARGET_DEVICE=cpu OMP_NUM_THREADS=4 \
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-1.7B \
  --dtype float32 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.60 \
  --override-generation-config '{"temperature": 0.1, "top_p": 0.9, "top_k": 0}' \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --host 0.0.0.0 \
  --port 8000
```

> **`--enable-auto-tool-choice` et `--tool-call-parser hermes` sont obligatoires pour Onyx.** Sans ces paramètres, Onyx retourne une erreur `"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set` dès la première conversation. Le parser `hermes` est compatible avec Qwen3.

> **`--gpu-memory-utilization 0.60` avec Onyx actif :** Onyx consomme environ 9 Go (OpenSearch 1 Go + background 1,7 Go + autres services environ 1,5 Go). Sur une VM de 32 Go, il reste environ 21 Go disponibles pour vLLM. La valeur 0.60 × 32 Go donne environ 19 Go, dans cette marge.

Dans l'interface Onyx, naviguer dans **Admin → Language Models → OpenAI-Compatible → Connect** :

| Champ | Valeur |
|---|---|
| API Base URL | `http://172.17.0.1:8000/v1` |
| API Key | (laisser vide : vLLM est lancé sans `--api-key`) |
| Display Name | vLLM local |
| Models | Cliquer le bouton de détection automatique |

**Pourquoi cette configuration a été abandonnée :** les timeouts d'Onyx, même portés à 300 secondes, sont incompatibles avec les vitesses d'inférence de vLLM en mode CPU sur le matériel de lab (VM Ubuntu, i7-14700 partagé avec l'hôte). Les requêtes Onyx expirent systématiquement avant la fin de la génération.

---

## En production sur DGX Spark : ce qui change

> **Note :** cette section est documentaire, non validée sur matériel réel dans le cadre de ce guide.

Sur DGX Spark avec 128 Go de RAM, aucune optimisation mémoire n'est nécessaire. Les valeurs par défaut d'OpenSearch (`-Xms2g -Xmx2g`) conviennent. Onyx pointe vers vLLM au lieu d'Ollama : le changement se fait dans **Admin → Language Models** en remplaçant l'URL du provider par `http://172.17.0.1:8000/v1` (IP de la passerelle Docker, voir §3.2) ou par l'IP réseau du DGX Spark si vLLM tourne sur une machine séparée. Les paramètres `--enable-auto-tool-choice` et `--tool-call-parser hermes` sont requis au lancement de vLLM pour la compatibilité Onyx.

---

[Suite : §5 Connecteurs SMB et cloisonnement documentaire](section-05-connecteurs.md)

---

*Validé sur VM-RAG-LAB, Ubuntu 26.04 LTS (resolute), Onyx latest, septembre 2026. La configuration §4.5 utilise Ollama sur LABO-G9. Le bloc DGX Spark et §4.8 (vLLM dans la VM) sont documentaires, non validés dans cette configuration.*
