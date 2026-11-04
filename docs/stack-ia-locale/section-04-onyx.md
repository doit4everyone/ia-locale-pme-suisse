---
title: "§4 Interfaces utilisateur : Onyx CE et Open WebUI | Guide de déploiement stack IA locale"
description: "Validation du backend Ollama avec Onyx CE, puis déploiement d'Open WebUI avec authentification LDAP AD et cloisonnement documentaire."
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

# §4 Interfaces utilisateur : Onyx CE et Open WebUI

[Retour au sommaire](index.md) | [Section précédente : §3 Docker Compose : stack complète](section-03-docker-compose.md) | [Section suivante : §5 Connecteurs SMB et cloisonnement documentaire](section-05-connecteurs.md)

**Statut :** validé en lab sur VM-RAG-LAB, septembre 2026. **Section en partie historique :** Onyx CE (§4.1) n'a servi qu'à valider le serveur de modèles au début du lab, avec les modèles de l'époque (`qwen2.5:14b`, `nomic-embed-text`). La configuration d'Open WebUI en service est celle du §3.4 (Compose) et du §0, étape 14 : en cas de doute, ces deux-là font foi.

---

> **Ce que cette section documente :** deux interfaces successives. Onyx CE est déployé en première étape pour valider la connectivité Ollama et le pipeline d'embedding. Open WebUI est la stack finale retenue, avec authentification LDAP Active Directory et transmission de l'identité utilisateur à la RAG API pour le cloisonnement documentaire.

---

## §4.1 Onyx CE : validation du backend Ollama

Onyx CE est utilisé ici uniquement comme outil de validation. Il permet de vérifier rapidement que le backend Ollama répond, que le modèle d'embedding fonctionne et qu'un corpus de test s'indexe correctement. Il est arrêté une fois la validation terminée pour libérer les ressources (OpenSearch, Redis, Celery représentent 4 à 6 Go de RAM en veille).

### §4.1.1 Déploiement

```bash
git clone https://github.com/onyx-dot-app/onyx.git
cd onyx/deployment/docker_compose
```

Copier et adapter le fichier d'environnement :

```bash
cp .env.prod.example .env
nano .env
```

Variables minimales à configurer :

```bash
# LLM
GEN_AI_MODEL_PROVIDER=ollama
GEN_AI_MODEL_VERSION=qwen2.5:14b
GEN_AI_API_ENDPOINT=http://<IP-OLLAMA>:11434

# Embedding
DOCUMENT_ENCODER_MODEL=nomic-ai/nomic-embed-text-v1
NORMALIZE_EMBEDDINGS=true

# Secrets
SECRET_KEY=<secret-fort>
```

```bash
docker compose -f docker-compose.dev.yml up -d
```

Onyx est accessible sur `http://<IP-VM>:3000`.

### §4.1.2 Optimisation mémoire OpenSearch

OpenSearch consomme 2 Go de RAM par défaut. Limiter à 512 Mo pour un lab.

> **Note :** la variable `OPENSEARCH_JAVA_OPTS` dans `.env` n'est pas lue par le conteneur OpenSearch d'Onyx. Le heap doit être codé en dur dans `docker-compose.dev.yml`, dans la section `environment` du service `index` :

```yaml
  index:
    environment:
      - OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m
```

### §4.1.3 Validation du backend

Dans l'interface admin Onyx : **LLM → Ollama → tester la connexion**. Déposer 2 ou 3 documents de test, lancer une indexation, poser une question. Si la réponse cite les documents, le backend est validé.

> **Limite d'Onyx CE :** tout utilisateur accède à l'intégralité du contenu indexé, quels que soient ses droits sur les fichiers d'origine. Onyx CE ne filtre pas les résultats par permissions. Ne pas indexer de données à accès restreint avec Onyx CE.

### §4.1.4 Arrêt d'Onyx après validation

```bash
cd onyx/deployment/docker_compose
docker compose down
```

---

## §4.2 Open WebUI : stack finale

Open WebUI est l'interface retenue pour la stack finale. Elle s'authentifie via LDAP Active Directory et transmet l'identité de l'utilisateur connecté à la RAG API pour le filtrage documentaire par ACL NTFS.

### §4.2.1 Le service dans docker-compose.yml

Le service `open-webui` est déclaré dans le `docker-compose.yml` du dépôt (§3.4) : image figée par son numéro et son empreinte, **aucun port publié** (Open WebUI est joint par Nginx, à l'adresse `https://<RAG_FQDN>`, §9.8), tâches automatiques désactivées. Deux variables portent l'identité de l'utilisateur :

```yaml
    environment:
      - ENABLE_FORWARD_USER_INFO_HEADERS=true
      # Identité signée (X-OpenWebUI-User-Jwt), même secret que rag-api (§5.6.1)
      - FORWARD_USER_INFO_HEADER_JWT_SECRET=${OWUI_JWT_SECRET}
```

> **Les deux variables sont indispensables.** Sans la première, Open WebUI ne transmet pas l'identité de l'utilisateur connecté à la RAG API. Avec la seconde, Open WebUI **signe** cette identité ; la RAG API vérifie la signature et refuse (403) une identité transmise sans elle, dans de simples en-têtes (§5.6.1, §16.6). C'est sur cette identité signée que repose le cloisonnement documentaire du §5.

Les premières versions de ce guide publiaient Open WebUI sur le port 3001 de la VM, en HTTP, avec l'image `main` : ce n'est plus le cas (frontal HTTPS depuis la 2.21.0, §9.8 ; versions figées, §16.8).

### §4.2.2 Connexion OpenAI compatible vers la RAG API

Dans l'interface admin Open WebUI : **Settings → Admin → Connections → API compatibles OpenAI → ajouter une connexion** :

| Paramètre | Valeur |
|---|---|
| URL | `http://rag-api:8080/v1` |
| Clé API | valeur de `API_TOKEN` dans `.env` |

> **Utiliser le nom de service Docker `rag-api`** et non l'IP de la VM. Les deux fonctionnent, mais le nom de service est plus robuste lors des redémarrages.

### §4.2.3 Configuration LDAP

Dans **Settings → Admin → Authentication → LDAP** :

| Paramètre | Valeur | Note |
|---|---|---|
| Hôte | `<NOM-DC>.votre-domaine.ch` | Nom DNS, pas l'IP |
| Port | `636` | LDAPS obligatoire |
| TLS | Activé | |
| Validate Certificate | Activé | Avec la chaîne de l'autorité, `/etc/ssl/certs/ad-chain.pem` (§0 étape 4D, champ *Certificate Path*). Le cas d'un lab sans certificat est au §5.6.2 |
| DN de l'application | `CN=svc-rag,...` | |
| Mot de passe DN | mot de passe svc-rag | |
| Attribut email | `userPrincipalName` | `mail` souvent non renseigné dans l'AD |
| Attribut username | `sAMAccountName` | |
| Base de recherche | `DC=votre-domaine,DC=ch` | Pas `OU=UTILISATEURS` : certains comptes sont dans `CN=Users` |
| Filtres de recherche | `(objectClass=user)` | |

> **Port 636 obligatoire :** les DC Windows Server récents refusent les connexions LDAP sur le port 389 sans LDAP Signing. LDAPS sur 636 contourne cette contrainte.

> **Base de recherche `DC=votre-domaine,DC=ch` :** les comptes créés par défaut dans Windows sont dans le conteneur `CN=Users`, pas dans une OU personnalisée. Une base `OU=UTILISATEURS` ne les trouvera pas.

> **`userPrincipalName` comme attribut email :** l'attribut `mail` n'est pas toujours renseigné dans l'AD même si l'utilisateur a une adresse email. `userPrincipalName` (format `utilisateur@votre-domaine.ch`) est toujours présent et utilisé comme identifiant unique par `auth.py`.

### §4.2.4 Gestion des accès utilisateurs

**Première connexion d'un compte LDAP :** Open WebUI bloque le compte en attente de validation admin. L'administrateur doit activer le compte dans **Settings → Admin → Users**.

En production, c'est le comportement recommandé : chaque nouvel accès est validé explicitement par un administrateur avant d'être actif. C'est cohérent avec une politique nLPD qui exige le contrôle des accès aux données.

En lab, pour accélérer les tests, activer le compte dès réception de la demande de connexion dans le panneau admin.

### §4.2.5 Publication du modèle rag-api

Dans **Settings → Admin → Models** :

Cliquer sur `...` à côté du modèle `rag-api` → **Make Public**.

Sans cette étape, les utilisateurs non-admin voient une liste de modèles vide à la connexion, même si la connexion OpenAI compatible est correctement configurée.

### §4.2.6 Résultats de validation en lab

Validation effectuée avec deux comptes :

**Compte administrateur domaine :** 15 groupes AD résolus via `auth.py`, accès complet au corpus.

**Compte `test-client` (GRP-Clients uniquement) :**
- Question : "Quelles sont les conditions du contrat de travail de [employé RH] ?"
- Réponse : "Cette information ne figure pas dans les documents disponibles."
- Questions de suivi proposées par Open WebUI : uniquement sur les documents clients accessibles (ces suggestions sont désactivées depuis, §0 étape 14)

Le cloisonnement documentaire est opérationnel de bout en bout depuis l'interface Open WebUI. Il est depuis contrôlé par un test automatique (§16.3) : 207 verdicts, tous OK, au rejeu du 1er novembre 2026.

---

[Retour au sommaire](index.md) | [Section précédente : §3 Docker Compose : stack complète](section-03-docker-compose.md) | [Section suivante : §5 Connecteurs SMB et cloisonnement documentaire](section-05-connecteurs.md)

---

*Validé en lab sur VM-RAG-LAB, septembre 2026 ; Open WebUI v0.11.3 depuis la 2.21.0.*
