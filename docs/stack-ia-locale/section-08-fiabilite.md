---
title: "§8 Fiabilité : hallucinations et contrôle d'ancrage | Guide de déploiement stack IA locale"
description: "Détecter et prévenir les hallucinations dans un pipeline RAG : contrôles déterministes, groundedness check, règles de formation utilisateurs."
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

# §8 Fiabilité : hallucinations et contrôle d'ancrage

[Retour au sommaire](index.md) | [Section précédente : §7 Pipelines n8n](section-07-n8n.md)

**Statut :** validé en lab sur VM-RAG-LAB avec corpus Axonix SA, RAG API et Open WebUI, septembre 2026. Tous les cas de test documentés ont été reproduits en session, y compris le contrôle 3 (format de citation confirmé, voir §8.4).

---

> **Ce que cette section documente :** un pipeline RAG peut produire des réponses incorrectes qui ressemblent à des réponses correctes. Cette section décrit comment les détecter, comment les prévenir côté utilisateur, et comment les intercepter côté technique. Les exemples sont issus de sessions de validation réelles sur le corpus Axonix SA, un corpus de documents fictifs créés pour le lab (voir §4, corpus de validation Axonix SA). Les noms de clients, montants et références de fichiers qui apparaissent dans cette section sont inventés.

---

## §8.1 Deux types de réponses : ancrée vs hallucinée

Un pipeline RAG peut produire deux types de réponses. La différence n'est pas toujours visible à l'oeil nu.

**Réponse ancrée :** le modèle a récupéré des chunks correspondant à la question, les a lus, et en a extrait les informations. Les citations pointent vers des documents réels. Le contenu est vérifiable.

**Réponse hallucinée :** le modèle n'a pas trouvé de document correspondant, mais a produit une réponse plausible en s'appuyant sur la structure de la question ou d'une réponse précédente. Les citations pointent vers des documents inexistants. Le contenu est inventé mais cohérent.

---

## §8.2 Cas documenté : hallucination par analogie dans Onyx CE

Les deux exemples suivants ont été obtenus lors de la même session de validation, avec le même modèle (`qwen2.5:14b`), le même corpus (12 documents Axonix SA indexés dans Onyx), et sans modification de configuration entre les deux questions.

### Cas 1 : réponse correcte (question directe)

**Question posée :**
> Quelles sont les conditions du contrat de maintenance d'Axonix SA avec Baumont Industries ?

**Comportement observé :** Onyx a récupéré les chunks du document `21_Contrat_Maintenance_Baumont_Industries.docx` et produit une réponse avec des citations SharePoint structurées.

**Extrait de la réponse :**

> Le contrat couvre l'infogérance de 35 postes Windows 11 Pro, l'infogérance d'un serveur Windows Server 2022 et d'un NAS Synology, le réseau (Firewall OPNsense, 3 switches, WiFi industriel). Forfait mensuel : CHF 4 200 HT. [SharePoint — 21_Contrat_Maintenance_Baumont_Industries.docx]

Toutes les données sont exactes et vérifiables dans le document source.

### Cas 2 : hallucination par analogie ("fais pareil")

**Question posée immédiatement après :**
> Fais pareil pour l'étude Rochat

**Comportement observé :** le document `03_Contrat_Maintenance_Etude_Rochat.docx` existe dans le corpus. Onyx ne l'a pas trouvé lors de la recherche. Le modèle a produit une réponse en reprenant la structure du Cas 1 et en inventant les données.

**Ce que le modèle a inventé :**

| Champ | Réponse hallucinée | Valeur réelle dans le document |
|---|---|---|
| Nom du fichier | `22_Contrat_Maintenance_Étude_Rochat.docx` | `03_Contrat_Maintenance_Etude_Rochat.docx` |
| Site SharePoint | Finances | Direction |
| Date de début | 1er janvier 2025 | 1er janvier 2026 |
| Postes | 20 Windows 10 Pro | 20 Windows 11 Pro |
| Serveur | Windows Server 2019 | Windows Server 2025 |
| Pare-feu | pfSense | OPNsense |
| Forfait mensuel | CHF 3 000 HT | CHF 3 840 HT |

La réponse était bien formatée, complète, et indiscernable d'une réponse correcte sans vérification.

### Les deux signaux visibles sans juge LLM

**Signal 1 : format des citations.** Une réponse ancrée produit des objets de citation structurés avec le nom du fichier. Une réponse hallucinée produit des URLs en texte brut répétées à chaque affirmation, signe que le modèle reproduit le format sans avoir de chunks à citer.

**Signal 2 : identifiant de document inventé.** Dans ce cas Onyx/SharePoint, l'URL hallucinée contenait le GUID `56601275-318D-47CD-960B-D94C762ED9C0`, absent de tout document SharePoint du tenant. C'est le signal le plus net d'hallucination : le modèle a inventé un identifiant structurellement plausible mais inexistant. Dans un pipeline file server SMB (§5), l'équivalent est un nom de fichier cité entre crochets mais absent des chunks récupérés par Qdrant : c'est ce que détecte le contrôle 3 de la RAG API.

---

## §8.3 Architecture de contrôle : RAG API et Open WebUI

La réponse architecturale est de ne pas laisser Onyx gérer seul la génération. La RAG API déployée en §3 implémente quatre couches de contrôle entre la récupération et l'affichage.

```
Utilisateur (Open WebUI, port 3001)
    ↓
RAG API (port 8080)
    ├── Retriever Qdrant : chunks du document le plus pertinent
    ├── Génération : qwen2.5:14b avec prompt strict
    ├── Contrôles déterministes (coût nul)
    ├── Groundedness check : qwen3:4b
    └── Journalisation nLPD
    ↓
Réponse affichée (endpoint /v1) ou bloquée avec HTTP 422 (endpoint /query)
```

> **Comportement selon l'endpoint :** sur `/v1/chat/completions` (chemin Open WebUI), la réponse est toujours renvoyée à l'utilisateur, quel que soit le résultat du groundedness check. Le champ `ancree` est journalisé pour l'audit nLPD mais ne bloque pas l'affichage : bloquer sur `/v1` casserait la compatibilité OpenAI et afficherait une erreur dans Open WebUI. Sur `/query` (endpoint machine à machine), une réponse non ancrée retourne HTTP 422 avec la réponse dans `reponse_bloquee`. C'est un choix délibéré documenté : la supervision humaine reste la mitigation principale sur le chemin utilisateur.

Open WebUI reçoit la réponse via l'endpoint `/v1/chat/completions` de la RAG API, compatible OpenAI. Open WebUI remplace Onyx CE pour l'interface utilisateur depuis la v2.0 : l'indexation est assurée par `indexer.py` et les ACL par `acl_resolver.py` (voir §5).

---

## §8.4 Contrôles déterministes

Quatre contrôles s'exécutent avant le juge LLM, sans coût de calcul.

**Contrôle 1 : aucun chunk récupéré.**
Si Qdrant ne retourne aucun chunk, il n'y a aucune source possible. Le prompt strict déclenche la réponse de refus standard ("Cette information ne figure pas dans les documents disponibles."), qui passe le contrôle 2 et est renvoyée à l'utilisateur.

**Contrôle 2 : réponse de refus standard.**
Si la réponse est courte (moins de 200 caractères) et contient "ne figure pas dans les documents disponibles", c'est un refus légitimé par le prompt strict. La vérification passe. La limite de 200 caractères est importante : une réponse longue qui contient cette phrase en passant n'est pas un refus.

**Contrôle 3 : sources citées inexistantes.**
Le prompt strict demande au modèle de citer les documents entre crochets : `[nom_du_fichier.docx]`. Chaque citation est comparée aux sources réellement récupérées par Qdrant. Une citation absente des chunks signale une hallucination.

```python
def verifier_citations(answer: str, chunks: list[dict]) -> list[str]:
    sources_reelles = {c["source"] for c in chunks}
    prefixes_reels = {os.path.splitext(s)[0] for s in sources_reelles}
    citees = set(re.findall(r'\[([^\]]{5,100})\]', answer))
    inventees = []
    for citee in citees:
        # Nettoyer le préfixe "Document N :" résiduel (format obsolète)
        # Le format actuel de build_context() est "→ filename" mais la regex
        # est conservée pour rétrocompatibilité avec d'anciens chunks indexés.
        citee_clean = re.sub(r'^Document\s+\d+\s*:\s*', '', citee).strip()
        citee_sans_ext = os.path.splitext(citee_clean)[0]
        if citee_clean in sources_reelles:
            continue
        if citee_sans_ext in prefixes_reels:
            continue
        if any(citee_clean in s or s in citee_clean for s in sources_reelles):
            continue
        if '.' not in citee_clean and '_' not in citee_clean:
            continue
        inventees.append(citee_clean)
    return sorted(inventees)
```

**Contrôle 4 : réponse longue sans citation.**
Si une réponse dépasse 200 caractères sans aucune citation entre crochets, le modèle a répondu sans ancrer ses affirmations. Ce contrôle alimente le champ `ancree: false` dans le journal nLPD. Sur `/v1`, la réponse est affichée avec ce statut journalisé. Sur `/query`, elle est bloquée avec HTTP 422.

### Résultats de validation

Ces contrôles ont été testés sur le corpus Axonix SA en septembre 2026 :

| Question | ancree | Sources retournées | Contrôle déclenchant |
|---|---|---|---|
| Conditions contrat Baumont Industries | `true` | `21_Contrat_Maintenance_Baumont_Industries.docx` (×2) | Aucun |
| Conditions contrat ClientB | `true` | `03_Contrat_Maintenance_Etude_Rochat.docx` (×2) | Aucun |
| Chiffrage migration Azure Sarrasin | `true` | `04_Reponse_AO_Migration_Azure_Sarrasin.docx` (×3) | Aucun |
| "Fais pareil pour Baumont" (hors contexte) | `false` | Aucun chunk Baumont pertinent | Contrôle 4 : réponse sans citation. Sur `/v1` : journalisé, affiché. Sur `/query` : HTTP 422. |

> **Format de citation confirmé en lab, septembre 2026.** Le modèle produit des citations entre crochets du type `[CLIENTS/test-deny-explicite.docx]`, format que `verifier_citations()` sait lire. Le contrôle 3 est donc fonctionnel sur ce format. Il n'a pas déclenché lors des sessions de test car aucune réponse n'a cité de document inexistant : les réponses incorrectes ont été interceptées par le contrôle 1 (aucun chunk récupéré) ou par le contrôle 4 (réponse longue sans citation). L'hallucination documentée en §8.2 a été observée dans Onyx CE, pas dans la RAG API avec les contrôles actifs.

---

## §8.5 Groundedness check : juge LLM

Les contrôles déterministes interceptent les cas grossiers. Pour les hallucinations subtiles (modèle qui cite un vrai document en lui faisant dire autre chose), un second appel LLM vérifie affirmation par affirmation.

**Modèle juge :** `qwen3:4b`. Appel via `/api/chat` avec `"think": false` et `"format": "json"`.

```bash
curl http://<IP-HOTE-OLLAMA>:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3:4b",
    "stream": false,
    "format": "json",
    "think": false,
    "options": {"temperature": 0},
    "messages": [{"role": "user", "content": "...prompt du juge..."}]
  }'
```

> **Paramètres critiques :** `"think": false` est requis pour Qwen3. Sans ce paramètre, la réponse JSON arrive dans le champ `thinking` au lieu de `message.content` et ne peut pas être parsée. L'endpoint `/api/chat` est requis : `/api/generate` ne supporte pas ce paramètre correctement avec Qwen3.

> **`keep_alive` et déchargement du juge :** Ollama décharge un modèle de la mémoire après 5 minutes d'inactivité par défaut. Pour `qwen3:4b`, ce déchargement ajoute 30 à 90 secondes au premier groundedness check suivant une période d'inactivité. La variable `JUDGE_KEEP_ALIVE` (défaut `2h` dans `main.py`, transmise par le Compose) contrôle cette durée. `qwen3:4b` occupe environ 2,5 Go en Q4 : le cumul avec `qwen2.5:14b` (~9 Go) tient en RAM système sur LABO-G9. Passer à `-1` une fois le GPU installé pour maintenir les deux modèles en VRAM indéfiniment.

**Prompt du juge :**

```python
juge_prompt = """Tu es un vérificateur de faits strict.

Sources :
{sources}

Réponse à vérifier :
{reponse}

Instructions :
- Une affirmation est sourcée si elle est directement tirée des sources ou en est une reformulation fidèle.
- Une affirmation est NON sourcée si elle contient un chiffre, une date, un nom ou un fait précis absent des sources.
- Une affirmation est NON sourcée si elle attribue une fonctionnalité ou une action au mauvais sujet : si la source dit que A fait X, la réponse ne peut pas dire que B fait X.
- Si la source documente un outil construit autour d'un produit, la réponse ne peut pas présenter cet outil comme une fonctionnalité native du produit.
- Ne valide pas une affirmation si tu ne la trouves pas dans les sources ou si l'attribution est incorrecte.

Réponds uniquement en JSON :
{"ancree": true ou false, "affirmations_non_sourcees": ["liste des affirmations avec des faits précis absents des sources"]}"""
```

> **Limite du juge sur CPU :** `qwen3:4b` détecte les hallucinations grossières (chiffres, dates, noms inventés) mais rate les mauvaises attributions subtiles : si une source documente un outil construit *autour* d'un produit, le juge peut valider une réponse qui présente cet outil comme une fonctionnalité native du produit. Les deux règles d'attribution ajoutées ci-dessus réduisent ce risque, mais ne l'éliminent pas. Une validation fiable des attributions nécessite un modèle juge plus grand (`qwen2.5:14b` sur GPU, en réutilisant le modèle principal déjà chargé en VRAM).

**En cas d'échec du juge**, la réponse est laissée passer pour ne pas bloquer le service. L'échec est journalisé avec le champ `verification: non_effectuee` pour l'audit nLPD. Un juge qui tombe pendant une semaine devient visible dans les logs, pas silencieux.

### Coût en temps d'inférence

| Étape | CPU LABO-G9 (i7-14700, sans GPU) | GPU RTX 5060 Ti 16 Go (estimé) |
|---|---|---|
| Retriever Qdrant | < 1 s | < 1 s |
| Génération qwen2.5:14b | ~3 à 5 min | ~10 à 20 s |
| Groundedness check qwen3:4b | 2,4 s (cas validé) à 8 s (cas complexe) | ~1 à 3 s |
| **Total** | **~5 à 8 min** | **~15 à 25 s** |

Les valeurs CPU sont mesurées. Les valeurs GPU sont des estimations à mesurer après installation du GPU sur LABO-G9.

---

## §8.6 Retrieval hybride BM25 et paramètres clés

Le retrieval combine deux approches fusionnées par Reciprocal Rank Fusion (RRF) :

| Approche | Avantage | Limite |
|---|---|---|
| Vectorielle (Qdrant) | Similarité sémantique, reformulations | Moins efficace sur les termes exacts |
| BM25 (mots-clés) | Termes exacts : noms de fichiers, acronymes, commandes | Ne comprend pas le sens |

L'index BM25 est construit en mémoire au démarrage du conteneur et reconstruit après chaque synchronisation. Il couvre les deux collections (`documents` et `documentation`). Chaque chunk BM25 inclut son `chunk_index` : si un chunk BM25 gagne le RRF, l'extension de contexte peut récupérer ses voisins par `chunk_index ± radius` au lieu de faire un scroll aléatoire.

### Note sur les PDF avec tables des matières

`indexer.py` nettoie les suites de points répétitifs (`......`) avant l'appel à Ollama. Ces patterns, fréquents dans les tables des matières PDF, provoquent une erreur 500 sur `nomic-embed-text`. Le nettoyage est appliqué dans `get_embedding()` et n'affecte pas la qualité des embeddings.

### Paramètres validés en lab

| Paramètre | Valeur | Justification |
|---|---|---|
| `TOP_K` | 20 | Améliore le recall sur les gros fichiers .md (100+ chunks). 12 était insuffisant. |
| `CONTEXT_THRESHOLD` | 0.01 | Les scores RRF sont dans [0, 0.016] avec k=60. 0.01 déclenche l'extension de contexte sur presque toutes les questions. |
| `MAX_CONTEXT_CHUNKS` | 14 | Validé en lab sur CPU. Extension par `chunk_index ± radius`. Augmenter à 15-20 après GPU. |

### Limite sur les très gros fichiers

Un fichier de 100+ chunks (ex. `11-correlations-yaml.md` à 189 chunks, `09-pipeline-llm.md` à 117 chunks) est trop dilué pour que ses chunks pertinents remontent systématiquement dans le top 20. Les questions génériques sur ces fichiers peuvent échouer. Les questions précises avec les bons termes techniques réussissent.

### Note sur la température de génération

La température est fixée à 0.2 (validé en lab). En dessous de 0.1, les réponses sont courtes et répétitives. Au-dessus de 0.3, le taux de hallucination augmente sur les données factuelles. 0.2 est le bon compromis entre fidélité aux sources et fluidité pour un RAG nLPD-compliant. Ne pas dépasser 0.3 sur ce type de corpus.

**Correctif documentaire recommandé :** découper les très gros fichiers en sections thématiques séparées. `11-correlations-yaml.md` gagnerait à être découpé en 6 fichiers par série de règles (W, WD, S, L, M, A). C'est un travail sur le file server, pas dans le code.

---

## §8.7 Citations enrichies avec chemin UNC

Depuis la v2.6.0, `enrichir_citations()` remplace chaque citation `[nom.docx]` par `[nom.docx : `\\\\SERVEUR\\Partage\\Dossier\\`]` en post-traitement côté API, après le groundedness check. Le chemin UNC est dans un bloc code inline Markdown : Open WebUI l'affiche tel quel et un clic le copie dans le presse-papiers. L'utilisateur colle ensuite le chemin dans la barre d'adresse de l'Explorateur Windows.

Cette opération est effectuée après tous les contrôles : `verifier_citations()` et le juge voient la citation brute `[nom.docx]`, pas la citation enrichie.

## §8.8 Règles de formation utilisateurs

La formation est la première ligne de défense, gratuite et sans développement.

### Formulations à proscrire

| Formulation | Pourquoi elle est dangereuse |
|---|---|
| "Fais pareil pour X" | Demande implicitement la même structure, que le document existe ou non |
| "Même chose pour Y" | Identique |
| "Compare X et Y" | Si l'un des documents n'existe pas, le modèle invente |
| "Liste tous les contrats de..." | Si la liste n'est pas exhaustive dans les chunks, le modèle complète |

### Formulations recommandées

| Formulation dangereuse | Formulation correcte |
|---|---|
| "Fais pareil pour l'étude Rochat" | "Quelles sont les conditions du contrat de maintenance avec l'étude Rochat ?" |
| "Même chose pour Sarrasin" | "Quel est le chiffrage de la migration Azure pour Sarrasin Fiduciaire ?" |
| "Compare les deux contrats" | "Quelles sont les différences de SLA entre le contrat Baumont et le contrat Rochat ?" |

La règle générale : toujours poser une question directe sur un sujet précis. Ne jamais demander au modèle de reproduire une structure ou de compléter une liste.

---

## §8.7 Résumé des couches de mitigation

| Couche | Mécanisme | Coût | Interface |
|---|---|---|---|
| 1. Prompt strict | "Réponds uniquement à partir des documents, ignore les chunks hors sujet" | Nul | Onyx CE et RAG API |
| 2. Formation utilisateurs | Proscrire "fais pareil", questions directes | Nul | Toutes interfaces |
| 3. Contrôles déterministes | Citations inventées, réponse sans source | Nul | RAG API uniquement |
| 4. Groundedness check | Juge qwen3:4b, affirmation par affirmation | ~2 à 8 s CPU | RAG API uniquement |

Les couches 1 et 2 s'appliquent à Onyx CE sans développement. Les couches 3 et 4 nécessitent la RAG API déployée en §3.

---

[Suite : §9 Sécurité, durcissement, journalisation nLPD](section-09-securite.md)

---

*Validé en lab sur VM-RAG-LAB, corpus Axonix SA + DOIT4EVERYONE (45 fichiers, 970 chunks), RAG API avec qwen2.5:14b et qwen3:4b, Open WebUI, septembre 2026.*
