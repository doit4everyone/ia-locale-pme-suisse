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
Réponse affichée ou bloquée
```

Open WebUI reçoit la réponse via l'endpoint `/v1/chat/completions` de la RAG API, compatible OpenAI. Onyx CE reste en place pour l'indexation et les connecteurs SharePoint.

---

## §8.4 Contrôles déterministes

Quatre contrôles s'exécutent avant le juge LLM, sans coût de calcul.

**Contrôle 1 : aucun chunk récupéré.**
Si Qdrant ne retourne aucun chunk, il n'y a aucune source possible. La réponse est bloquée immédiatement.

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
        # Nettoyer le préfixe "Document N :" produit par build_context()
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
Si une réponse dépasse 200 caractères sans aucune citation entre crochets, le modèle a répondu sans ancrer ses affirmations. La réponse est bloquée.

### Résultats de validation

Ces contrôles ont été testés sur le corpus Axonix SA en septembre 2026 :

| Question | ancree | Sources retournées | Contrôle déclenchant |
|---|---|---|---|
| Conditions contrat Baumont Industries | `true` | `21_Contrat_Maintenance_Baumont_Industries.docx` (×2) | Aucun |
| Conditions contrat ClientB | `true` | `03_Contrat_Maintenance_Etude_Rochat.docx` (×2) | Aucun |
| Chiffrage migration Azure Sarrasin | `true` | `04_Reponse_AO_Migration_Azure_Sarrasin.docx` (×3) | Aucun |
| "Fais pareil pour Baumont" (hors contexte) | `false` | Aucun chunk Baumont pertinent | Contrôle 4 : réponse sans citation |

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
- Ne valide pas une affirmation si tu ne la trouves pas dans les sources.

Réponds uniquement en JSON :
{"ancree": true ou false, "affirmations_non_sourcees": ["liste des affirmations avec des faits précis absents des sources"]}"""
```

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

## §8.6 Règles de formation utilisateurs

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
| 1. Prompt strict | "Réponds uniquement à partir des documents" | Nul | Onyx CE et RAG API |
| 2. Formation utilisateurs | Proscrire "fais pareil", questions directes | Nul | Toutes interfaces |
| 3. Contrôles déterministes | Citations inventées, réponse sans source | Nul | RAG API uniquement |
| 4. Groundedness check | Juge qwen3:4b, affirmation par affirmation | ~2 à 8 s CPU | RAG API uniquement |

Les couches 1 et 2 s'appliquent à Onyx CE sans développement. Les couches 3 et 4 nécessitent la RAG API déployée en §3.

---

[Suite : §9 Sécurité, durcissement, journalisation nLPD](section-09-securite.md)

---

*Validé en lab sur VM-RAG-LAB, corpus Axonix SA (12 documents, 68 chunks), RAG API avec qwen2.5:14b et qwen3:4b, Open WebUI, septembre 2026.*
