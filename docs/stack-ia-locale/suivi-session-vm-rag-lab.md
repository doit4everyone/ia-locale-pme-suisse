# Suivi de session : déploiement VM-RAG-LAB

**Date :** 31 août 2026  
**Objectif :** valider les commandes du guide de déploiement chapitre par chapitre sur VM-RAG-LAB

---

## Environnement

| Élément | Valeur |
|---|---|
| Hôte de virtualisation | LABO-G9, Intel Core i7-14700, 64 Go DDR5, Windows 11, fait tourner VMware Workstation |
| Poste lab | WIN11-AD-TESTS, Windows 11, accès aux interfaces web et VS Code |
| VM | VM-RAG-LAB, Ubuntu 26.04 LTS (resolute) |
| IP VM | 10.100.1.15/24 |
| Gateway | 10.100.1.254 |
| DNS | 10.100.1.1 (DC Active Directory) + 8.8.8.8 |
| Réseau VMware | VMnet3 (réseau lab) |
| vCPU | 6, épinglés sur P-cores 0, 2, 4, 6, 8, 10 via `sched.cpu.affinity` |
| RAM | 20 Go (augmenté depuis 16 Go, nécessaire pour vLLM + KV cache 8192 tokens) |
| Disque | 100 Go NVMe (97 Go utilisables après extension LVM) |
| Mode inférence | CPU uniquement, Qwen3 1.7B |

---

## Corrections à apporter au guide

- [ ] Remplacer **VM-DEPLOY** par **VM-RAG-LAB** partout dans le guide
- [ ] Remplacer **Ubuntu Server 24.04** par **Ubuntu Server 26.04 LTS (resolute)** dans les références OS
- [ ] Retirer **DoIt4Everyone** de la page de titre
- [ ] Mettre à jour les versions : Docker 29.7.2, Docker Compose 5.5.0
- [ ] Corriger la syntaxe d'épinglage CPU : `sched.cpu.affinity` au lieu de `processor[N].use`
- [ ] Ajouter l'étape d'extension LVM après installation (l'installateur Ubuntu n'alloue que 50% du VG par défaut)
- [ ] Ajouter la note sur le nom de code Ubuntu 26.04 : **resolute** (au lieu de noble pour 24.04)
- [ ] Préciser le type de disque virtuel recommandé : **NVMe** (au lieu de SCSI par défaut)
- [ ] Préciser le pilote réseau recommandé : **vmxnet3** (au lieu de e1000)

---

## Statut par section

### §0 Architecture cible
- [ ] À valider

### §1 Prérequis et création de la VM
- [x] **§1.1 Sizing de la VM** : validé (6 vCPU / 16 Go / 100 Go NVMe)
- [x] **§1.2 Installation Ubuntu Server** : validé (Ubuntu 26.04 LTS resolute)
- [x] **§1.3 Épinglage vCPU** : validé, syntaxe corrigée (`sched.cpu.affinity`)
- [x] **§1.4 Installation Docker** : validé (Docker 29.7.2, Compose 5.5.0)

### §2 Installation et configuration de vLLM
- [x] **§2.1 Installation vllm-cpu** : validé (vllm-cpu 0.28.0, torch 2.13.0+cpu)
- [x] **§2.2 Lancement mode CPU** : validé (voir commande corrigée ci-dessous)
- [x] **§2.3 Script de lancement** : créé `/opt/start-vllm.sh`
- [x] **§2.4 Test inférence** : validé (réponse française correcte, 55 tokens)

### §3 Docker Compose : stack complète
- [x] **§3.1 Structure des répertoires** : validé
- [x] **§3.2 Fichier .env** : validé, correction LLM_BASE_URL (localhost → 172.17.0.1)
- [x] **§3.3 docker-compose.yml** : validé (Qdrant, n8n, rag-api)
- [x] **§3.4 Lancement de la stack** : validé
- [x] **§3.5 Authentification API** : validé (401 sans token)
- [ ] §3.6 Onyx : en cours (déploiement officiel via repo GitHub)
- [ ] §3.7 Nginx : à faire

**Corrections identifiées :**
- `LLM_BASE_URL` : utiliser l'IP passerelle Docker `172.17.0.1` et non `localhost`
- `chown -R 1000:1000 ~/rag-stack/n8n_data` obligatoire avant premier lancement n8n
- Onyx : déployer via le repo officiel, pas via docker-compose custom

### §4 Configuration Onyx
- [ ] À valider

### §5 Continue.dev
- [ ] À valider

### §6 Pipelines n8n
- [ ] À valider

### §7 Sécurité et durcissement
- [ ] À valider

### §8 Validation et benchmarks
- [ ] À valider

---

## Notes de session

- Ubuntu 26.04 s'appelle **resolute** (lsb_release -cs retourne `resolute`)
- Le dépôt Docker détecte correctement resolute et fournit les paquets correspondants
- L'installateur Ubuntu 26.04 n'alloue que 50% du VG LVM par défaut : extension manuelle nécessaire avec `lvextend` + `resize2fs`
- La syntaxe `processor[N].use` de VMware Workstation est invalide : utiliser `sched.cpu.affinity` à la place
- Le pilote réseau e1000 est sélectionné par défaut par VMware : remplacer par vmxnet3
- **vLLM-cpu 0.28.0** : le wheel GPU standard ne fonctionne pas en mode CPU. Il faut installer `vllm-cpu` avec `torch+cpu` depuis le dépôt PyTorch
- Procédure d'installation correcte :
  1. `python3 -m venv /opt/vllm-env && source /opt/vllm-env/bin/activate`
  2. `pip install torch==2.13.0+cpu --index-url https://download.pytorch.org/whl/cpu`
  3. `pip install vllm-cpu==0.28.0 --extra-index-url https://download.pytorch.org/whl/cpu`
- Variable d'environnement obligatoire : `VLLM_TARGET_DEVICE=cpu`
- `--device cpu` et `--gpu-memory-utilization 0` ne fonctionnent plus en 0.28.0 : les supprimer
- `--gpu-memory-utilization 0.82` contrôle la fraction de RAM CPU réservée (malgré son nom)
- RAM VM minimum : **20 Go** (16 Go insuffisant pour Qwen3 1.7B float32 + KV cache 8192 tokens)
- Mode thinking Qwen3 actif par défaut : désactiver avec `enable_thinking: false` dans chaque requête
- Temperature par défaut 0.6 trop élevée pour RAG : forcer à 0.1 via `--override-generation-config`
- Script de lancement : `/opt/start-vllm.sh`
- **`--gpu-memory-utilization` varie selon la RAM disponible et les services actifs :**
  - VM 20 Go sans Onyx : `0.82`
  - VM 32 Go avec Onyx (qui consomme ~8-9 Go) : `0.60`
  - Règle générale : vLLM a besoin d'environ 11 Go pour Qwen3 1.7B float32 + KV cache 8192 tokens. Calculer la valeur avec : `RAM_disponible_après_autres_services / RAM_totale_VM`
  - Le script `/opt/start-vllm.sh` doit être mis à jour en conséquence selon l'environnement
- RAM VM recommandée avec stack complète (vLLM + Onyx + Docker Compose) : **32 Go minimum**
- Onyx déployé via repo officiel : `~/onyx/deployment/docker_compose/docker-compose.yml`
- Onyx accessible sur `http://10.100.1.15` (port 80 via Nginx interne Onyx)
- Configuration LLM Onyx : via interface admin → Language Models → OpenAI-Compatible
- **Onyx nécessite `--enable-auto-tool-choice` et `--tool-call-parser hermes`** dans la commande vLLM. Sans ces paramètres, Onyx retourne une erreur `"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set` dès la première conversation. Le parser `hermes` est compatible avec Qwen3.

## Notes session 2 (1er septembre 2026)

### §4 Configuration Onyx
- [x] Onyx déployé via repo officiel (`~/onyx/deployment/docker_compose/docker-compose.yml`)
- [x] Connexion vLLM établie via OpenAI-Compatible provider
- [x] Modèle Qwen/Qwen3-1.7B détecté automatiquement par Onyx
- [x] Conversations fonctionnelles depuis l'interface web
- [ ] Mode thinking Qwen3 à désactiver (session dédiée)
- [ ] Langue française à forcer dans le system prompt (session dédiée)
- [ ] Connecteurs SMB et SharePoint à configurer (session dédiée)

**Corrections et tweaks identifiés pour le guide :**

- **RAM VM recommandée avec stack complète** : 32 Go minimum (vLLM ~11 Go + Onyx ~9 Go + Docker Compose ~2 Go)
- **`--gpu-memory-utilization` avec Onyx actif** : passer de 0.82 à 0.60 (Onyx consomme ~9 Go, il ne reste que ~21 Go disponibles sur 32 Go)
- **OpenSearch heap mémoire** : la valeur par défaut `-Xms2g -Xmx2g` dans `docker-compose.yml` est trop élevée pour une VM de validation. Modifier à `-Xms512m -Xmx1g` dans le fichier `docker-compose.yml` (la variable d'environnement dans `.env` est ignorée car la valeur est hardcodée)
- **vLLM avec Onyx** : ajouter `--enable-auto-tool-choice` et `--tool-call-parser hermes` au script de lancement. Sans ces paramètres, Onyx retourne `"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`
- **Onyx : ne pas configurer GEN_AI_* dans le .env avant le premier démarrage** : Onyx valide le modèle en base Postgres au démarrage. Si la base est vide et qu'un modèle invalide est injecté via .env, l'api_server plante en boucle. Configurer le LLM via l'interface admin après le premier démarrage propre
- **Swap** : avec vLLM + Onyx sur 32 Go, le swap peut s'activer. Vider avec `swapoff -a && swapon -a` si nécessaire
- **Script `/opt/start-vllm.sh` final validé avec Onyx :**

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

### System prompt Onyx validé

System prompt adapté pour usage RAG PME suisse, à configurer dans Admin → Chat Preferences :

```
Tu es un assistant documentaire expert au service des collaborateurs. Tu réponds toujours en français, de manière précise et concise.

Tu réponds UNIQUEMENT à partir des documents fournis dans le contexte. Si la réponse n'est pas dans les documents disponibles, tu réponds exactement : "Cette information ne figure pas dans les documents disponibles."

Tu ne complètes jamais avec tes connaissances générales. Chaque affirmation dans ta réponse doit être directement tirée d'un document du contexte. Tu cites le document source après chaque affirmation.

/no_think

La date actuelle est {{CURRENT_DATETIME}}.{{CITATION_GUIDANCE}}

# Style de réponse
Tu utilises le Markdown pour structurer tes réponses. Tu es concis et factuel.
{{REMINDER_TAG_DESCRIPTION}}
```

**Résultat validé :**
- Réponse en français : OK
- Guardrail RAG ("Cette information ne figure pas dans les documents disponibles") : OK
- Balises `<think></think>` : encore présentes malgré `/no_think` dans le prompt. Le thinking Qwen3 n'est pas complètement désactivé via le system prompt seul. À résoudre en session dédiée (option native Onyx ou `enable_thinking: false` via vLLM).

### §4 Connecteur SharePoint Onyx : prérequis WIN11-AD-TESTS

**App Registration Entra ID créée :**
- Nom : `Onyx-RAG-Indexer`
- Client ID : `e4e2c758-eebc-4d19-ad62-f5e9aa7f15d7`
- Tenant ID : `9e48c8f8-87f3-4788-a270-1589e817b3d3`
- Permissions accordées : `Sites.Selected` (Application) + `Files.Read.All` (Application)

**Sites SharePoint cibles :**
- `https://bsculier.sharepoint.com/sites/Direction`
- `https://bsculier.sharepoint.com/sites/RH`
- `https://bsculier.sharepoint.com/sites/Finances`
- `https://bsculier.sharepoint.com/sites/EquipeIT`

**Prérequis PowerShell sur WIN11-AD-TESTS :**
- Windows PowerShell 5.1 est insuffisant pour PnP.PowerShell 3.x qui exige PowerShell 7.4+
- Installer PowerShell 7 via winget : `winget install Microsoft.PowerShell`
- Toujours utiliser **PowerShell 7** (pwsh.exe) et non Windows PowerShell (powershell.exe) pour PnP
- Séquence d'installation PnP dans PowerShell 7 :
  ```powershell
  Install-Module PnP.PowerShell -Force -Scope CurrentUser
  Import-Module PnP.PowerShell
  Connect-PnPOnline -Url "https://bsculier.sharepoint.com/sites/Direction" -Interactive
  Grant-PnPAzureADAppSitePermission `
    -AppId "e4e2c758-eebc-4d19-ad62-f5e9aa7f15d7" `
    -DisplayName "Onyx-RAG-Indexer" `
    -Site "https://bsculier.sharepoint.com/sites/Direction" `
    -Permissions Read
  ```
- Répéter pour chaque site (Direction, RH, Finances, EquipeIT)

### Notes techniques DGX Spark production (source : Tutanka01/glm5.3-flash-2x-dgx-spark-nvfp4)

**Point critique vLLM sur GB10 :**
- Le runtime vLLM officiel produit une sortie incorrecte sur GB10 (ARM64 DGX Spark) à cause d'un bug sur le chemin NoPE
- Il faut que les correctifs SM121 soient présents, pas seulement vLLM v0.24+
- À documenter dans la section DGX Spark du guide comme avertissement explicite

**SGLang comme alternative à vLLM sur DGX Spark :**
- SGLang avec six correctifs SM121 spécifiques donne de meilleures performances que vLLM sur GB10
- Débit mesuré : 67,2 tok/s agrégés sur GLM-5.3-Flash 320B NVFP4 avec 2 DGX Spark en TP=2
- TTFT p99 : 1,02 s (contre 45 s avec MTP5 batché)
- À mentionner dans le guide comme alternative sérieuse à vLLM pour la production DGX Spark

**EXL3 4bpw avec vLLM :**
- Atteint 990K tokens de contexte validés
- Meilleure fidélité que NVFP4
- Référence utile pour la section performances du guide

**Source :** https://github.com/Tutanka01/glm5.3-flash-2x-dgx-spark-nvfp4

### Conclusions session 2 - Validation Onyx + SharePoint

**Problèmes identifiés et solutions :**

- **Qwen3-1.7B insuffisant pour Onyx** : le function calling échoue systématiquement sous 4B. Minimum validé : Qwen3-4B (function calling déclenché, "Searching internal documents" confirmé). Recommandation production : 8B minimum.
- **Purview chiffrement** : les documents SharePoint protégés par Microsoft Purview sont indexés (métadonnées) mais le contenu est illisible. Solution : passer Purview en mode audit pour les documents de démo, ou utiliser le connecteur SMB on-premise.
- **Timeout CPU** : Qwen3-4B sur CPU est trop lent pour les timeouts d'Onyx. La stack CPU ne convient pas pour Onyx en production.
- **Context window** : `--max-model-len 4096` trop petit pour Onyx qui injecte plusieurs chunks. Utiliser 8192 minimum.

**Décision architecture pour la prochaine session :**
- Abandonner vLLM-cpu pour Onyx : trop lent, timeouts
- Utiliser **Ollama sur LABO-G9** comme backend LLM pour Onyx
- URL depuis VM-RAG-LAB : `http://<IP-LABO-G9>:11434/v1`
- vLLM-cpu reste documenté pour la section §2 du guide (validation CPU avant DGX)
- Dans Onyx : provider OpenAI-Compatible pointant vers Ollama LABO-G9

**RAM VM-RAG-LAB :**
- 30 Go insuffisant pour vLLM 4B+ + Onyx simultanément
- Passer à 48 Go lors de la prochaine session (éteindre autres VMs)
- Avec Ollama sur LABO-G9, la VM n'a plus besoin de faire tourner vLLM : 20 Go suffisent pour Onyx seul

**Purview :**
- Passer en mode audit (pas de chiffrement, juste journalisation)
- Générer 5 documents de démo sans protection dans SharePoint Direction
- Réindexer le connecteur SharePoint après changement

**Prochaine session :**
1. Configurer Ollama LABO-G9 comme backend Onyx
2. Valider RAG complet avec documents sans Purview
3. Passer VM-RAG-LAB à 48 Go
4. §5 Continue.dev sur WIN11-AD-TESTS

### Configuration Ollama LABO-G9 pour Onyx

**Variables d'environnement utilisateur Windows (LABO-G9) :**
- `OLLAMA_KEEP_ALIVE` = `600` (garder le modèle chargé 10 minutes)
- `OLLAMA_CONTEXT_LENGTH` = `32768` (contexte complet pour qwen2.5:14b)

**Modèle retenu pour Onyx :** `qwen2.5:14b` (capabilities: tools, context: 32768)

**Configuration Onyx → Ollama :**
- Provider : Ollama (natif, pas OpenAI-Compatible)
- API Base URL : `http://192.168.1.198:11434`
- Display Name : `DEMO 1`
- Model : `qwen2.5:14b`

**Timeout Onyx :**
- Variable : `LLM_SOCKET_READ_TIMEOUT` dans `.env` Onyx
- Valeur par défaut : 60 secondes (insuffisant pour CPU)
- Valeur configurée : 300 secondes
- Fichier : `~/onyx/deployment/docker_compose/.env`
- Redémarrer après modification : `docker compose restart api_server background`

**RAM VM-RAG-LAB réduite à 16 Go :**
- Onyx seul n'a besoin que de ~10-12 Go
- L'inférence est déportée sur LABO-G9 via Ollama
- Pinning vCPU de la VM plus nécessaire (inférence sur LABO-G9)

### Validation RAG complète - 2 septembre 2026

**Stack validée :**
- VM-RAG-LAB (Ubuntu 26.04, 16 Go RAM) : Onyx + Docker Compose
- LABO-G9 : Ollama avec qwen2.5:14b (15 Go RAM, contexte 32768)
- SharePoint Online : corpus Axonix SA (37 documents + 5 nouveaux sans Purview)
- Embedding : intfloat/multilingual-e5-small (en cours de migration vers multilingual-e5-base)

**Résultats validés :**
- "Quel est le chiffre d'affaires d'Axonix SA ?" → "CHF 3,2 millions" avec citation SharePoint ✅
- "Quelle est la vision d'Axonix pour l'intelligence artificielle locale ?" → réponse correcte tirée de 05_Strategie_IA_Axonix_2025.docx ✅
- Function calling qwen2.5:14b : opérationnel ✅
- Citations sources SharePoint : présentes ✅

**Configuration finale validée :**

Onyx provider :
- Type : Ollama (natif)
- URL : http://192.168.1.198:11434
- Modèle : qwen2.5:14b

Variables LABO-G9 (utilisateur Windows) :
- OLLAMA_KEEP_ALIVE=600
- OLLAMA_CONTEXT_LENGTH=32768

Variable Onyx (.env) :
- LLM_SOCKET_READ_TIMEOUT=300

**Points à noter pour le guide :**
- Sans filtre de date dans le chat Onyx, les réponses sont meilleures (le filtre date exclut des documents)
- La formulation de la question influence fortement le retrieval avec multilingual-e5-small
- multilingual-e5-base donne de meilleures correspondances sémantiques (migration en cours)
- Purview chiffrement bloque l'indexation : utiliser des documents sans label de sensibilité pour les démos
- Les 5 documents de démo Axonix SA générés et déposés dans SharePoint Direction fonctionnent correctement

**Documents de démo générés :**
- 01_Presentation_Axonix_SA.docx
- 02_Politique_Qualite_Axonix.docx
- 03_Reglement_Interieur_Axonix.docx
- 04_Procedure_Onboarding_Axonix.docx
- 05_Strategie_IA_Axonix_2025.docx

**Prochaines étapes :**
- §5 Continue.dev sur WIN11-AD-TESTS
- §6 Pipelines n8n
- §7 UFW et journalisation nLPD
- §8 Validation complète checklist
- Services systemd pour démarrage automatique
- Connecteurs séparés par département pour gestion permissions (Option 2)

### Analyse comparative : options RAG pour documents confidentiels Purview

**Problème identifié en session :**
Les documents SharePoint avec étiquettes Purview (même en mode audit) ne peuvent pas être indexés par Onyx via Graph API. Le contenu est chiffré et illisible. Seuls les documents avec étiquette "1 — Public" ou sans étiquette sont indexables.

**Implications pour la sécurité du RAG :**
- Les chunks dans OpenSearch sont stockés en texte clair, sans protection Purview
- En cas de leak du vector store, les documents sont exposés sans leur protection d'origine
- Onyx Community Edition ne filtre pas les résultats par permissions SharePoint par utilisateur

**Trois options pour les entreprises :**

1. **Microsoft Copilot for M365 (30 USD/user/mois)**
   - Respect natif des permissions SharePoint et étiquettes Purview
   - Pas de déploiement technique
   - Données restent dans le tenant M365
   - Pas de contrôle sur le modèle (GPT-4o)
   - Souveraineté dépend du datacenter du tenant

2. **Azure AI Foundry (anciennement Azure OpenAI Studio)**
   - RAG custom avec connecteurs SharePoint natifs
   - Permissions et Purview intégrés nativement
   - Plus flexible que Copilot
   - Dépendance à Azure, pas de modèle open weight
   - Coût à l'usage (tokens + compute)

3. **Stack open source (notre approche)**
   - Contrôle total sur le modèle et les données
   - Souveraineté réelle si hébergé en Suisse
   - Pas de coût de licence
   - Gestion des permissions à construire (Phase 7 du plan d'apprentissage)
   - Pour documents Purview : pipeline de déchiffrement sécurisé requis (compte super user Purview)

**Tableau de décision pour le guide :**

| Situation | Recommandation |
|---|---|
| Déjà sur M365, budget licence | Copilot for M365 |
| Sur Azure, besoin de contrôle | Azure AI Foundry |
| Souveraineté stricte nLPD, budget CapEx | Stack open source + Phase 7 |
| Documents publics / internes non sensibles | Stack open source Community Edition |
| Documents Purview confidentiels + stack open source | Compte super user Purview + pipeline déchiffrement sécurisé |

**Note pour le guide décisionnel :**
Ajouter une section "RAG et documents confidentiels Purview" qui explique cette limitation et les options disponibles. C'est un angle différenciateur important pour les PME suisses soumises à la nLPD.

### bge-m3 + TEI : piste validée techniquement, non intégrable dans Onyx Community Edition

**Ce qui fonctionne :**
- TEI (text-embeddings-inference) cpu-1.5 déployé avec bge-m3
- Modèle ONNX téléchargé dans ~/tei_data/bge-m3
- API embed opérationnelle sur port 8001
- Commande de lancement :
```bash
docker run -d \
  --name tei \
  -p 8001:80 \
  -v ~/tei_data/bge-m3:/data \
  -e HF_HUB_OFFLINE=1 \
  ghcr.io/huggingface/text-embeddings-inference:cpu-1.5 \
  --model-id /data \
  --port 80
```

**Limitation Onyx Community Edition :**
- Le formulaire Custom Model n'a pas de champ API URL
- Onyx CE ne supporte pas les endpoints d'embedding externes
- Fonctionnalité probablement réservée à Enterprise Edition

**Pour intégrer bge-m3 avec Onyx :**
- Option 1 : Onyx Enterprise Edition
- Option 2 : Modifier le code source Onyx (fork)
- Option 3 : Utiliser notre RAG API FastAPI custom avec bge-m3 via TEI

**Configuration finale retenue :**
- Embedding : intfloat/multilingual-e5-base (natif Onyx)
- LLM : qwen2.5:14b via Ollama sur LABO-G9
- TEI + bge-m3 : disponible pour la RAG API custom (Phase 8 du plan d'apprentissage)

### Script de démarrage de la stack

Fichier : `/root/start-stack.sh` sur VM-RAG-LAB

**Séquence de démarrage complète :**

1. **LABO-G9 (Windows)** : Ollama démarre automatiquement. Précharger le modèle :
   ```powershell
   ollama run qwen2.5:14b "prêt"
   ```

2. **VM-RAG-LAB** : lancer le script :
   ```bash
   bash /root/start-stack.sh
   ```

3. **Vérification** depuis WIN11-AD-TESTS : ouvrir `http://10.100.1.15`

### Comparatif modèles LLM pour Onyx sur CPU (session 2 septembre 2026)

| Modèle | Function calling | Qualité RAG | Vitesse CPU | Verdict |
|---|---|---|---|---|
| qwen3:1.7B | Non | N/A | Rapide | Insuffisant pour Onyx |
| qwen3:4B | Partiel | Moyen | Lent | Instable, timeout |
| **qwen2.5:14b** | **Oui** | **Excellent** | **Lent (3-5 min)** | **Recommandé pour validation CPU** |
| llama3.1:8b | Oui | Bon | Très lent | Trop lent, timeout systématique |
| mistral-nemo:12b | Non | Mauvais | Lent | Hallucine sans chercher |

**Configuration finale retenue :**
- Modèle LLM : `qwen2.5:14b` via Ollama sur LABO-G9
- Modelfile dédié recommandé pour limiter le contexte (voir mistral-rag:12b comme exemple)
- Embedding : `intfloat/multilingual-e5-base`
- Timeout Onyx : `LLM_SOCKET_READ_TIMEOUT=300`

**Résultats de validation finaux :**
- "Quel est le chiffre d'affaires d'Axonix SA ?" → CHF 3,2 millions ✅ (instable selon les sessions)
- "Qui est responsable qualité chez Axonix ?" → Philippe Crettaz, directeur technique ✅
- "Quelles sont les étapes du premier jour chez Axonix ?" → Réponse correcte et complète ✅
- "Quelle est la vision IA d'Axonix pour l'IA locale ?" → Référence romande nLPD ✅

---

## Notes session 3 (2 septembre 2026, suite)

### Clarifications architecturales intégrées

#### vLLM-cpu : exclusion définitive pour Onyx sur VM-RAG-LAB

Les raisons sont documentées et définitives :

- Les timeouts Onyx (300 s après correction) sont incompatibles avec les performances vLLM-cpu
- `qwen2.5:14b` sur vLLM-cpu serait encore plus lent qu'Ollama (overhead vLLM supérieur au démarrage)
- La RAM de la VM (16 Go) est insuffisante pour vLLM + Onyx simultanément

vLLM reste documenté dans le guide pour deux usages précis :
- **§2 du guide** : validation de la configuration CPU avant migration DGX Spark (documenté et validé)
- **Production DGX Spark** : Qwen3-30B-A3B avec FP4 Blackwell natif, 35 à 45 tok/s

#### Architecture validée pour la démo

```
WIN11-AD-TESTS → Onyx (VM-RAG-LAB) → Ollama qwen2.5:14b (LABO-G9)
```

#### Architecture production DGX Spark

```
Utilisateurs → Onyx (VM ou conteneur) → vLLM Qwen3-30B-A3B (DGX Spark)
```

C'est exactement ce que le guide documente : valider sur CPU avec Ollama, déployer sur DGX avec vLLM. Le changement en production se résume à modifier l'URL du provider LLM dans Onyx.

#### RAG API FastAPI custom : optionnelle, réalisable avec Ollama

La RAG API FastAPI custom (port 8080, `~/rag-stack`) n'est pas obligatoire pour Onyx. Elle devient nécessaire uniquement pour :

- Gestion fine des permissions NTFS/ACL par utilisateur (Phase 7 du plan d'apprentissage)
- Intégrations avec des systèmes tiers (ERP Abacus, etc.)
- Pipelines n8n automatisés (OCR, résumés Teams, rapports)
- Applications consommant le RAG via API sans passer par l'interface Onyx

Pour une PME standard, `Onyx → vLLM (DGX Spark)` couvre 80% des cas d'usage sans RAG API custom.

Pour les cas avancés, les deux chemins cohabitent avec vLLM comme moteur commun :

```
Onyx → vLLM (DGX Spark)
n8n  → RAG API FastAPI → Qdrant → vLLM
```

#### RAG API FastAPI avec Ollama : faisable dès maintenant

La RAG API FastAPI peut pointer vers Ollama LABO-G9 au lieu de vLLM. Ollama expose une API compatible OpenAI, donc aucun changement de code n'est nécessaire. Mise à jour du `.env` de `~/rag-stack` :

```bash
sed -i 's|LLM_BASE_URL=.*|LLM_BASE_URL=http://192.168.1.198:11434/v1|' ~/rag-stack/.env
sed -i 's|LLM_MODEL=.*|LLM_MODEL=qwen2.5:14b|' ~/rag-stack/.env
docker compose -f ~/rag-stack/docker-compose.yml restart rag-api
```

La Phase 7 (permissions ACL Qdrant) est donc réalisable avec la configuration actuelle, sans DGX Spark.

#### Tableau de synthèse : chemins selon les besoins

| Besoin | Architecture | DGX Spark requis |
|---|---|---|
| Interface RAG utilisateurs (Onyx) | Onyx → Ollama/vLLM | Non (Ollama suffit pour valider) |
| Permissions granulaires NTFS/Entra ID | RAG API FastAPI → Qdrant → Ollama/vLLM | Non |
| Pipelines automatisés (OCR, résumés) | n8n → RAG API → Ollama/vLLM | Non |
| Production multi-utilisateurs (équipe) | Onyx + RAG API → vLLM | Oui (ou GPU équivalent) |


### Hallucination observée en session : cas documenté pour le guide

**Contexte :** Lors d'une requête Onyx avec la formulation "fais pareil" après une question sur un document existant, le modèle a produit une réponse complète et bien formatée sur un document inexistant : `Contrat_Maintenance_Baumont_Industries.docx`.

**Ce qui s'est passé :**
- Le document `04_Reponse_AO_Migration_Azure_Baumont.docx` existe dans SharePoint Finances
- Le modèle a trouvé "Baumont" dans ce document existant
- Il a conclu qu'un contrat de maintenance devait exister et l'a inventé, avec une URL SharePoint plausible, un nom de contact fictif (Jean-Luc Baumont), des détails techniques inventés (45 postes Windows 10, Palo Alto PA-220)
- La réponse était parfaitement structurée, indiscernable d'une vraie réponse

**Cause :** La formulation "fais pareil" a court-circuité le guardrail du prompt strict. Le modèle a compris la structure attendue et l'a remplie avec des données plausibles mais fictives. C'est une hallucination par analogie.

**Ce que le prompt strict aurait dû produire :**
> "Cette information ne figure pas dans les documents disponibles."

**Leçon pour la formation utilisateurs :** ne jamais utiliser "fais pareil", "même chose pour X", "sur le même modèle". Toujours poser une question directe : "Que sais-tu sur Baumont Industries SA ?"

**Impact selon la taille du modèle :**

| Modèle | Comportement face à "fais pareil" sans document |
|---|---|
| 14B (qwen2.5:14b) | Invente le document sans hésiter |
| 30B (Qwen3-30B-A3B) | Plus susceptible de résister, mais aucune garantie |
| Aucun modèle | N'est pas immunisé à 100% contre ce type de prompt |

Un modèle plus puissant réduit le risque, il ne l'élimine pas. Seul le groundedness check garantit la détection systématique.

**Leçon pour le guide :** la cohérence du format et la présence d'URLs SharePoint ne garantissent pas l'exactitude d'une réponse. Une hallucination bien formatée est indiscernable sans vérification.

### Groundedness check : fonctionnement et coût

**Ce que fait le groundedness check :**

C'est un second appel LLM après la génération de la réponse. Un modèle "juge" lit la réponse générée et vérifie que chaque affirmation est directement tirée des chunks récupérés dans le vector store. Exemple :

```
Réponse générée : "Jean-Luc Baumont, Directeur Général..."
Chunks récupérés : [04_Reponse_AO_Migration_Azure_Baumont.docx]

Juge : "Jean-Luc Baumont" figure-t-il dans les chunks ? → NON → HALLUCINATION détectée
```

Si le juge détecte une affirmation non sourcée, la réponse est bloquée avant d'être envoyée à l'utilisateur.

**Coût en temps d'inférence :**

Le groundedness check double approximativement le temps d'inférence total.

| Étape | CPU (qwen2.5:14b, LABO-G9) | DGX Spark (Qwen3-30B-A3B, vLLM) |
|---|---|---|
| Recherche documentaire | ~30 s | ~1 s |
| Génération de la réponse | ~3 à 5 min | ~5 à 8 s |
| Groundedness check (juge) | ~2 à 3 min | ~3 à 5 s |
| **Total** | **~8 à 10 min** | **~10 à 15 s** |

Sur CPU, le groundedness check est prohibitif en pratique. Sur DGX Spark, 10 à 15 secondes au total sont tout à fait acceptables pour un outil métier.

**Optimisations possibles :**
- Utiliser un modèle plus petit pour le juge (ex. qwen3:4b au lieu de 14b) : la vérification est plus simple que la génération
- Ne lancer le check que sur les réponses longues ou les requêtes marquées comme critiques
- Paralléliser génération et vérification si l'architecture le permet

**Validation pratique de la citation du guide décisionnel (§11.1) :**
> "Les 4 à 20 secondes sont le prix de la fiabilité. Un intégrateur qui annonce des temps de réponse inférieurs à 2 secondes sans mentionner le groundedness check n'a probablement pas de groundedness check."

Ce cas de hallucination validé en session illustre exactement pourquoi cette affirmation figure dans le guide. Le groundedness check est la couche qui manque à la stack actuelle.


### Groundedness check avec GPU 16 Go VRAM : architecture validée

**Configuration recommandée (16 Go VRAM, ex. RTX 4080/4090) :**

| Rôle | Modèle | VRAM estimée | Vitesse |
|---|---|---|---|
| Générateur RAG (Onyx) | qwen2.5:14b | ~9 Go | ~60 tok/s |
| Juge groundedness | qwen3:4b | ~3 Go | ~100 tok/s |
| Copilote dev (Continue.dev) | qwen2.5-coder:7b | ~4 Go | ~80 tok/s |

Les trois simultanément dépassent 16 Go. Solution : charger le juge à la demande, pas en permanence.

**Séquence de chargement dynamique avec Ollama :**

```
Requête utilisateur
    ↓
qwen2.5:14b génère la réponse (9 Go, chargé en permanence)
    ↓
qwen3:4b chargé temporairement pour le groundedness check (~3 Go supplémentaires)
    ↓ réponse validée ou bloquée
qwen3:4b déchargé automatiquement (keep_alive=0)
```

**Budget VRAM résultant :**
- qwen2.5:14b en permanence : 9 Go
- qwen3:4b à la volée : 3 Go supplémentaires = 12 Go total au pic
- Marge pour KV cache : ~4 Go

C'est faisable. C'est l'architecture cible de la Phase 6 du plan d'apprentissage.

**Modelfile Ollama pour le juge (déchargement immédiat après usage) :**

```
FROM qwen3:4b
PARAMETER num_keep 0
```

`num_keep 0` force Ollama à décharger le modèle immédiatement après usage, libérant la VRAM pour le générateur principal.

### Comparatif stack open source vs Azure AI Foundry : notes pour publications futures

Ces éléments sont apparus en session. Le guide décisionnel est publié, on ne le modifie plus. À intégrer lors de la prochaine session de travail sur le guide de déploiement ou GitHub Pages.

**Tableau comparatif :**

| Critère | Stack open source | Azure AI Foundry |
|---|---|---|
| Intégration Purview | Complexe, SDK limité Linux | Native, zéro configuration |
| Permissions SharePoint | Phase 7, développement custom | Native, respecte les ACL |
| Maintenance | IT interne requis | Microsoft gère |
| Conformité nLPD | À construire et auditer | Certifié, documenté |
| Temps de mise en œuvre | 4 à 8 semaines | 1 à 2 semaines |
| Coût visible | CHF 4 à 6k matériel + intégration | Pay-as-you-go, difficile à prévoir |
| Coût à faible usage | Élevé (CapEx fixe) | Faible |
| Coût à fort usage | Quasi nul (coût marginal zéro) | Peut exploser sans plafond |
| Prévisibilité budgétaire | Totale | Faible sans monitoring strict |
| Risque de facture surprise | Nul | Réel si usage non maîtrisé |

**Détail des coûts Azure AI Foundry (ordres de grandeur) :**

| Usage | Coût mensuel estimé |
|---|---|
| 10 utilisateurs, 20 questions/jour | CHF 150 à 300/mois |
| 10 utilisateurs, 200 questions/jour | CHF 1 500 à 3 000/mois |
| Indexation d'un gros corpus (1M tokens) | CHF 50 à 200 (ponctuel) |
| Fine-tuning | CHF 500 à 5 000 selon volume |

**Pourquoi la prédiction est difficile chez Azure :**
- Le coût dépend des tokens entrants ET sortants
- Un contexte RAG avec plusieurs chunks multiplie les tokens entrants
- Les questions longues font monter la facture sans avertissement
- Microsoft peut modifier les tarifs sans préavis

**Lien avec le guide décisionnel publié (§1) :**
> "Le cloud gagne en dessous de ~2 millions de tokens/jour. Le local gagne au-delà."

En pratique, les PME ne savent pas combien de tokens elles consommeront avant d'avoir déployé. C'est un risque financier réel à documenter.

**Destination des ces notes :**
- Guide de déploiement (`guide-deploiement-stack-ia.docx`) : introduction ou conclusion
- GitHub Pages : page dédiée "Stack open source ou Azure AI Foundry : comment choisir"
- Plan d'apprentissage (`plan-apprentissage-rag-2026.docx`) : note dans la phase comparaison plateformes (Phase 11)


---

## Notes session 4 : revue du guide publié et plan de travail

### Revue des sections §1 à §4 publiées : problèmes identifiés

#### Bloquants à corriger avant publication des sections suivantes

**1. Récit vLLM vs Ollama non expliqué pour le lecteur**

La décision est assumée et documentée dans les notes de session. Elle n'existe nulle part dans le guide publié. Le lecteur suit vLLM-cpu pendant deux sections, puis découvre l'abandon en §4.7 sans explication. Trois phrases en tête de §2 suffisent :

> vLLM est documenté ici pour deux usages : valider la configuration CPU avant migration DGX Spark, et servir de moteur d'inférence en production sur DGX Spark. Pour la démo Onyx sur matériel de lab, le backend retenu est Ollama sur poste hôte : les timeouts d'Onyx sont incompatibles avec les performances de vLLM en mode CPU. Le passage en production se résume à modifier l'URL du provider LLM dans Onyx.

**2. Trois valeurs de RAM contradictoires entre les sections**

| Section | Valeur annoncée |
|---|---|
| §1.1 | 16 Go minimum et recommandé |
| §2 (encadré) | 20 Go |
| §4 (encadré) | 32 Go minimum |
| §4.7 | 16 Go suffisent |

Config finale retenue : Onyx seul dans la VM, inférence déportée sur LABO-G9. §1.1 doit annoncer 16 Go. L'encadré 32 Go de §4 doit être requalifié en "si vous faites tourner vLLM dans la VM, ce que ce guide déconseille".

**3. Erreur factuelle sur le i7-14700**

Le i7-14700 a 8 P-cores et 12 E-cores, soit 20 cœurs et 28 threads. La phrase "20 cœurs physiques" est fausse. Le masque d'épinglage reste valide en pratique, mais la phrase explicative est à réécrire.

**4. Calculs mémoire incohérents**

- §2.2 : le raisonnement 0.82 × 20 Go ne colle pas avec le sizing 16 Go de §1.1
- §4.5 : "0.60 × 30 Go = 18 Go" sur une VM de 32 Go. Origine du 30 Go non documentée.

#### Problèmes techniques

- §4.5 : API Key = `changeme-vllm-secret` alors que vLLM est lancé sans `--api-key` en §2.2 et §2.3
- §3.3 : la RAG API ne fait pas de RAG. Elle proxifie vers le LLM, n'interroge jamais Qdrant, et renvoie `"sources": []` en dur. À qualifier explicitement comme squelette
- §3.1 et §3.4 : répertoires `onyx_data` et `nginx` créés mais inutilisés. `ONYX_SECRET_KEY` dans le `.env` de §3.2 est orpheline
- §4.2 : le `sed` sur `USER_AUTH_SECRET=""` peut casser silencieusement si le template change de format. Ajouter un `grep USER_AUTH_SECRET .env` de contrôle

#### Fidélité entre les notes de session et le guide publié

- §4.7, tableau validation RAG : le guide donne "CHF 3,2 millions, correct avec citation SharePoint". Les notes précisent "instable selon les sessions". Publier un résultat instable comme validé est risqué en démo client. Ajouter la mention ou retirer la ligne.

- Modèle minimum pour le function calling : trois valeurs contradictoires coexistent. Le 14B est recommandé en pratique pour notre config CPU, mais un lecteur avec GPU conclurait à tort qu'il lui faut 14B. À séparer en deux critères : capacité de function calling (minimum 8B) et vitesse acceptable sur CPU (14B recommandé).

#### À nettoyer avant publication

- Client ID et Tenant ID Entra ID : à remplacer par des placeholders dans le guide publié
- `bsculier.sharepoint.com` : tenant réel visible dans les URLs, à anonymiser
- `192.168.1.198` : IP du poste hôte, à remplacer par `<IP-HOTE-OLLAMA>` avec note explicative
- Corpus Axonix SA : fictif, le préciser une fois dans le guide pour lever le doute
- Emoji ✅ dans §4.7 : remplacer par "Correct" ou "Conforme" pour rester cohérent avec le reste
- Tirets "10-15 minutes" → "10 à 15 minutes"

#### Versions à vérifier avant publication

- Docker Compose 5.5.0 : la branche stable était en 2.x, un saut à 5.x mérite confirmation
- `pip install vllm-cpu` comme paquet PyPI distinct : à confirmer
- `vllm[cuda13]`, `torch 2.13.0+cpu`, Docker 29.7.2

### Plan de sections révisé

Contenu documenté en session mais sans section rattachée :
- Cas hallucination Baumont Industries : cas réel reproductible, meilleur argument commercial du dossier
- Groundedness check : fonctionnement, coût mesuré, architecture VRAM 16 Go
- RAG et documents Purview : limitation d'indexation des documents étiquetés, chunks en clair dans OpenSearch, angle nLPD le plus différenciant
- Connecteur SharePoint : App Registration, Sites.Selected, procédure faite mais non documentée dans le guide

**Découpage proposé :**

| Section | Contenu |
|---|---|
| §5 | Continue.dev |
| §6 | Connecteurs SharePoint et SMB |
| §7 | Pipelines n8n |
| §8 | Fiabilité : hallucinations et groundedness check |
| §9 | RAG et documents confidentiels Purview |
| §10 | Sécurité, durcissement, journalisation nLPD |
| §11 | Validation et benchmarks |

Le comparatif open source vs Azure AI Foundry est destiné à une page GitHub Pages séparée, pas au guide de déploiement. Décision confirmée.

**Ordre de travail recommandé :**
1. Encadré de cadrage en tête de §2 + harmonisation RAM (cohérence des sections existantes, environ 1 heure)
2. §6 SharePoint (la matière est prête, procédure déjà réalisée)
3. §8 Hallucinations et groundedness check (valeur commerciale forte)
4. §9 Purview et documents confidentiels (angle nLPD différenciant)


### Vérification des versions douteuses (5 septembre 2026)

| Élément | Dans le guide | Réalité vérifiée | Verdict |
|---|---|---|---|
| Docker Compose 5.5.0 | Mentionné | v5.5.0 est la dernière version stable, publiée le 17 août 2026 | Correct |
| `pip install vllm-cpu` | Mentionné | Paquet `vllm-cpu` v0.27.1 existe bien sur PyPI. Les anciens paquets fragmentés (vllm-cpu-avx512, etc.) sont dépréciés. Le wheel unifié détecte automatiquement les capacités CPU | Correct, mais à préciser dans le guide |
| `pip install vllm[cuda13]` | Mentionné | Les binaires vLLM officiels sont compilés avec CUDA 12.9. Blackwell requiert CUDA 12.8 minimum. La syntaxe `vllm[cuda13]` n'existe pas dans l'index officiel PyPI | **Faux, à corriger** |

**Correction à apporter dans le guide pour DGX Spark ARM64 :**

```bash
# À la place de pip install vllm[cuda13]
pip install vllm --extra-index-url https://download.pytorch.org/whl/cu129
```

L'image Docker officielle Nvidia (`nvcr.io/nvidia/pytorch`) reste la voie recommandée pour DGX Spark ARM64.

### Encadré de cadrage §2 : texte validé

Texte prêt à insérer en tête de §2 du guide de déploiement :

> **Pourquoi ce guide documente vLLM et utilise Ollama**
>
> vLLM est documenté dans cette section pour deux usages précis : valider la configuration du pipeline avant migration vers un DGX Spark, et servir de moteur d'inférence en production sur DGX Spark avec Qwen3-30B-A3B.
>
> Pour la démonstration Onyx sur le matériel de lab (LABO-G9, CPU), le backend retenu est Ollama sur le poste hôte. Les raisons sont techniques et non négociables dans ce contexte : les timeouts d'Onyx (300 secondes même après correction) sont incompatibles avec les vitesses d'inférence de vLLM en mode CPU, et la RAM de la VM (16 Go) est insuffisante pour faire cohabiter vLLM et Onyx simultanément.
>
> En production sur DGX Spark, le passage d'Ollama à vLLM se résume à modifier une seule ligne dans la configuration Onyx : l'URL du provider LLM. Le reste de la stack, les connecteurs, les pipelines n8n et la configuration Qdrant, est identique.
>
> Architecture validée pour la démo :
> WIN11-AD-TESTS → Onyx (VM-RAG-LAB) → Ollama qwen2.5:14b (LABO-G9)
>
> Architecture cible pour la production DGX Spark :
> Utilisateurs → Onyx → vLLM Qwen3-30B-A3B (DGX Spark)


### Vérifications complémentaires versions §2 (5 septembre 2026, suite)

#### torch 2.13.0+cpu : confirmé

PyTorch 2.13 est disponible en version générale depuis début juillet 2026. Rien à corriger dans le guide.

Note pour le guide : PyTorch 2.13 ne fournit plus de wheels cp313t (CPython 3.13t retiré par manylinux le 7 mai 2026 au profit de 3.14t). Sans effet sur l'installation standard.

#### intel-openmp 2024.2.1 : à confirmer localement

La dernière version publiée sur PyPI est 2026.1.0. Le 2024.2.1 du guide est vraisemblablement une dépendance transitive épinglée par le wheel vllm-cpu. À vérifier avant publication :

```bash
pip show intel-openmp
```

Si la valeur est bien 2024.2.1, c'est une information utile à laisser telle quelle : elle documente un pin ancien dans la chaîne de dépendances.

#### vllm-cpu : paquet communautaire tiers, pas officiel (correction importante)

C'est le résultat le plus significatif de cette vérification.

**Le guide écrit en §2.1 :**
> "vLLM existe en deux variantes distinctes sur PyPI : vllm (GPU, CUDA) et vllm-cpu (CPU, Intel OpenMP)."

**La réalité :**
Le paquet `vllm-cpu` est un projet communautaire indépendant, maintenu dans le dépôt MekayelAnik/vllm-cpu, sans affiliation avec le projet vLLM officiel. Il est distribué sous licence **GPL-3.0**, alors que vLLM officiel est sous **Apache 2.0**. Les wheels sont construits depuis les sources dans des conteneurs manylinux_2_28 avec GCC 14.

La voie officielle pour l'inférence CPU du projet vLLM est l'image Docker : `vllm/vllm-openai-cpu:v0.28.0`.

**Texte de remplacement pour §2.1 :**

> vLLM ne publie pas de wheel CPU sur PyPI. Le paquet `vllm-cpu` est un reconditionnement communautaire, maintenu indépendamment du projet vLLM et distribué sous licence GPL-3.0. Il fonctionne et est utilisé ici pour la phase de validation, mais il ajoute une dépendance à un mainteneur unique. La voie officielle pour l'inférence CPU est l'image Docker `vllm/vllm-openai-cpu`, qui reste une alternative si vous préférez ne pas dépendre d'un paquet tiers.

**Note sur la licence :** la différence Apache 2.0 (vLLM officiel) contre GPL-3.0 (vllm-cpu) est à mentionner dans le guide sans en tirer de conclusion juridique. L'impact dépend du contexte de déploiement.

#### vllm[cuda13] : correction confirmée et précisée

CUDA 13.0 est le défaut dans vLLM 0.28.0. La commande recommandée est :

```bash
uv pip install vllm --torch-backend=auto
```

Il n'y a pas d'extra `[cuda13]` à préciser : le défaut gère automatiquement CUDA 13. Des images séparées existent pour CUDA 12.9.

#### Bug NoPE GB10 : non vérifié

Le bug NoPE sur les modèles ARM64 GB10 (DGX Spark) avec SGLang n'a pas été vérifié. Le bloc DGX de §2 doit porter un avertissement explicite : non validé sur matériel réel.

### Récapitulatif des corrections à porter sur §2

| Élément | Statut | Action |
|---|---|---|
| torch 2.13.0+cpu | Confirmé | Aucune |
| Docker 29.7.2, Compose 5.5.0 | Confirmé | Aucune |
| intel-openmp 2024.2.1 | À confirmer localement | `pip show intel-openmp` dans /opt/vllm-env |
| vllm-cpu : paquet tiers | Confirmé | Requalifier dans §2.1 : paquet communautaire, licence GPL-3.0, pas officiel |
| Variantes ISA dépréciées | Confirmé | Ajouter note : wheel unifié depuis 0.17.0 |
| vllm[cuda13] | Faux | Remplacer par `uv pip install vllm --torch-backend=auto` |
| Bug NoPE GB10 | Non vérifié | Ajouter avertissement dans le bloc DGX |
| Encadré cadrage vLLM vs Ollama | Rédigé | À insérer en tête de §2 |

**Total : 4 modifications à porter sur §2 en une seule passe :**
1. Encadré de cadrage vLLM vs Ollama (en tête)
2. Requalification du paquet vllm-cpu + note GPL-3.0
3. Note de dépréciation des variantes ISA
4. Réécriture du bloc DGX (commande corrigée + avertissement NoPE)


### section-02-vllm.md : corrections appliquées (5 septembre 2026)

Les 4 corrections identifiées ont été appliquées en une seule passe sur le fichier.

| Correction | Emplacement | Nature |
|---|---|---|
| Encadré de cadrage vLLM vs Ollama | En tête, remplace l'ancien encadré "Contexte de validation" | Ajout |
| Requalification vllm-cpu | §2.1, premier paragraphe | Réécriture |
| Note dépréciation variantes ISA | §2.1, après le bloc de code | Ajout |
| RAM 20 Go → 16 Go | §2.2, encadré gpu-memory-utilization | Correction |
| Commande DGX : `vllm[cuda13]` → `uv pip install vllm --torch-backend=auto` | Bloc DGX Spark | Correction |
| Avertissement NoPE GB10 | Bloc DGX Spark, en tête | Ajout |
| Pied de page : mention "bloc DGX documentaire" | Dernière ligne | Ajout |

À vérifier localement avant publication : `pip show intel-openmp` dans `/opt/vllm-env` pour confirmer la version 2024.2.1.


### section-02-vllm.md : corrections passe 2 (5 septembre 2026)

Six corrections supplémentaires après relecture approfondie.

| Correction | Nature |
|---|---|
| Encadré d'ouverture : "même portés à 300 secondes" au lieu de "(300 secondes même après correction)" | Clarification |
| Architectures sorties du bloc citation, en texte normal | Forme |
| Phrase sur le wheel GPU : "le wheel officiel ne contient pas les kernels CPU compilés" | Correction technique |
| Encadré gpu-memory-utilization : 16 Go insuffisant pour vLLM, 20 Go requis, phrase orpheline "0.85" supprimée | Correction factuelle (contrainte mesurée en session restaurée) |
| Avertissement NoPE : attribution "utilisateurs DGX Spark" + ajout mention correctifs SM121 | Correction attribution + élément actionnable |
| `--dtype fp4` remplacé par `--quantization modelopt_fp4` + modèle nvidia/Qwen3-30B-A3B-NVFP4 | Correction technique confirmée par sources |

**Sur --dtype fp4 :** confirmé faux après vérification. `--dtype` attend auto/float16/bfloat16/float32. La quantification NVFP4 relève de `--quantization modelopt_fp4`. Les modèles pré-quantifiés Nvidia (`nvidia/*-NVFP4`) la détectent automatiquement sans flag. Sources : playbooks officiels Nvidia DGX Spark, retours communauté, hub HuggingFace.

**Points restants sur les autres sections :**
- §1.1 : harmonisation RAM (annoncer 16 Go pour Onyx seul, note 20 Go si vLLM dans la VM)
- §4.7 : résultat instable à mentionner (CHF 3,2 millions "instable selon les sessions")
- §4.7 : séparer critère function calling (8B minimum) et critère vitesse CPU (14B recommandé)


### section-01-prerequis.md : corrections appliquées (5 septembre 2026)

| Correction | Emplacement | Nature |
|---|---|---|
| "20 cœurs physiques" → "8 P-cores + 12 E-cores, 28 threads" | §1.1, intro | Correction factuelle |
| Remarque RAM : "vLLM CPU + Docker Compose" → "Onyx + Docker Compose, ~8 à 10 Go. Porter à 20 Go pour vLLM dans la VM (voir §2)" | §1.1, tableau sizing | Cohérence avec config finale |
| Description masque d'épinglage i7-14700 réécrite : 8 P-cores (CPU logiques 0 à 15) + 12 E-cores (16 à 27), masque 0,2,4,6,8,10 = 6 threads P-core, note pour vérifier via Gestionnaire des tâches | §1.3, encadré | Correction factuelle + conseil actionnable |


### section-04-onyx.md : corrections appliquées (5 septembre 2026)

| Correction | Emplacement | Nature |
|---|---|---|
| Encadré RAM : 32 Go → 16 Go suffisent pour Onyx seul, note 32 Go si vLLM en parallèle | En tête | Cohérence avec config finale |
| Note de stabilité sous le tableau résultats RAG : résultats corrects dans les conditions de test, instables sur formulations différentes | Après §4.7 tableau | Fidélité aux notes de session |
| Mention corpus fictif Axonix SA ajoutée dans la note | Même note | Clarté pour le lecteur |
| Modèle minimum : deux critères séparés (capacité function calling vs vitesse CPU) | §4.7 Points d'attention | Correction conceptuelle |
| "10-15 minutes" → "10 à 15 minutes" | §4.7 Embedding | Typographie |


### section-04-onyx.md : réécriture structurelle (5 septembre 2026)

Réécriture complète du fichier. La structure précédente documentait le chemin abandonné (vLLM) comme chemin principal, et la configuration réelle (Ollama) comme annexe après le lien de navigation.

**Nouvelle structure :**

| Section | Contenu |
|---|---|
| §4.1 | Déploiement via repo officiel (inchangé) |
| §4.2 | Configuration .env, grep de contrôle ajouté |
| §4.3 | Optimisation OpenSearch (inchangé) |
| §4.4 | Lancement stack (inchangé) |
| §4.5 | Configuration LLM : Ollama (chemin principal, anciennement §4.7) |
| §4.6 | Modèle d'embedding (anciennement dans §4.7) |
| §4.7 | Résultats de validation et points d'attention (anciennement dans §4.7) |
| En production | Bloc DGX avec avertissement "documentaire" |
| §4.8 | Configuration alternative vLLM dans la VM, non retenue |
| Lien Suite + pied de page | En dernier |

**Corrections de contenu appliquées :**

| Erreur | Correction |
|---|---|
| frontmatter description "connexion à vLLM" | "connexion à Ollama" |
| §4.5 : chemin vLLM comme chemin principal | Ollama comme chemin principal |
| §4.7 après le lien de navigation | §4.8 en annexe, après le lien |
| "0.60 × 30 Go" (arithmétique fausse) | "0.60 × 32 Go donne environ 19 Go" |
| API Key "changeme-vllm-secret" sans --api-key dans vLLM | "(laisser vide : vLLM est lancé sans --api-key)" |
| IP 192.168.1.198 en clair | Remplacée par `<IP-HOTE-OLLAMA>` |
| ✅ emoji dans le tableau | Supprimés, texte "Correct avec citation SharePoint" |
| "60 secondes par défaut" (mauvaise raison) | "même portés à 300 secondes" aligné sur §2 |
| Bloc DGX sans avertissement | Note "documentaire, non validé" ajoutée |
| grep USER_AUTH_SECRET manquant | Ajouté dans §4.2 |


### Test bloquant priorité 1 : documents chiffrés Purview via Graph API (7 septembre 2026)

**Question testée :** Graph API retourne-t-il le contenu en clair d'un document chiffré par Purview, avec un compte applicatif habilité ?

**Document de test :** `11_Contrat_Travail_Beraz_Valerie_RH.docx`, site RH SharePoint Axonix SA.

**Méthode :** token client_credentials via l'App Registration Onyx-RAG-Indexer, appel direct à l'endpoint `/drives/{driveId}/items/{itemId}/content` depuis VM-RAG-LAB.

**Résultat :**

```
HTTP/1.1 302 Found
Content-Type: application/octet-stream
Location: https://bsculier.sharepoint.com/...
```

Fichier téléchargé : 67 072 octets. Résultat `file` : `CDFV2 Encrypted`. Seules des métadonnées non chiffrées sont lisibles via `strings` ("contrats, salaires"). Le contenu du document est illisible.

**Conclusion :** Graph API accepte la requête et livre le fichier (pas de 403), mais le chiffrement Purview est appliqué côté serveur avant la livraison. Le fichier est retourné dans son état chiffré, illisible par la RAG API ou tout autre extracteur de texte.

**Impact sur l'architecture Partie 2 :**

| Type de document | Indexable par la RAG API |
|---|---|
| Sans label chiffrant (label "Public" ou sans label) | Oui |
| Avec label Purview appliquant un chiffrement | Non, CDFV2 Encrypted |

**Voies pour contourner la limite :**
- Super user AIP (`Add-AipServiceSuperUser`, module AIPService) : permet au compte de service de déchiffrer les documents avant extraction. Non testé, implique de stocker le contenu déchiffré dans Qdrant sans la protection d'origine.
- Token délégué (mode `on_behalf_of`) : utiliser l'identité d'un utilisateur habilité pour le déchiffrement. Plus complexe, change l'architecture d'authentification.
- Exclure les documents chiffrés du périmètre RAG et documenter la limitation.

**Note sécurité :** le secret client utilisé pour ce test (`Nnb8Q~...`) a été exposé dans la conversation et doit être supprimé immédiatement dans Azure (Entra ID → Onyx-RAG-Indexer → Certificats et secrets). Générer un nouveau secret si nécessaire pour Onyx.


### Notes de cadrage : divergence plan d'apprentissage / documentation (7 septembre 2026)

Les sessions de validation ont naturellement divergé du plan d'apprentissage. Les deux ont leur légitimité mais des audiences distinctes.

**Plan d'apprentissage** : parcours pédagogique linéaire, 18 à 22 semaines, pour quelqu'un qui part de zéro et veut construire les compétences phase par phase.

**Guide de déploiement** : documentation technique de niveau production, pour une PME ou un IT qui veut reproduire un déploiement validé.

**Ce que les sessions ont produit en plus :** retours d'expérience et décisions architecturales qui appartiennent à une troisième publication potentielle : test Purview, cas hallucination Baumont, comparatif Onyx EE vs RAG API, groundedness check, coûts Azure imprévisibles.

**Prochaine étape envisagée :** évaluation Onyx Enterprise Edition après validation complète de la stack CE et de la RAG API custom. Séquence proposée :
1. Valider la RAG API custom avec filtrage NTFS (Partie 2 du guide)
2. Comparer avec ce qu'Onyx EE fait nativement sur les mêmes données
3. Décider si la RAG API se justifie ou si l'EE vaut son coût pour ce cas d'usage PME suisse

Ce comparatif constituerait du contenu de valeur pour GitHub Pages : "RAG API custom vs Onyx Enterprise Edition, ce que chaque option coûte vraiment en temps et en argent pour une PME suisse."


### section-03-docker-compose.md : corrections appliquées (7 septembre 2026)

| Correction | Emplacement | Nature |
|---|---|---|
| Encadré de cadrage en tête | Après le titre | Ajout : rôle de la section, Onyx hors de cette stack, RAG API squelette |
| `onyx_data` et `nginx` retirés du mkdir | §3.1 | Suppression : répertoires orphelins |
| Note explicative après mkdir | §3.1 | Ajout : Onyx déployé séparément via son repo |
| `ONYX_SECRET_KEY` supprimée du .env | §3.2 | Suppression : variable orpheline |
| Avertissement squelette avant main.py | §3.3 | Ajout : proxy LLM, pas de RAG, sources vides |
| Commentaire dans le code | §3.3, `app = FastAPI(...)` | Ajout : titre et commentaire SQUELETTE DE VALIDATION |


### Corrections passe finale sur les quatre sections (7 septembre 2026)

| Correction | Fichier | Nature |
|---|---|---|
| Point Purview réécrit : super user déconseillé, risque nLPD documenté, renvoi Partie 2 | §4.7 | Correction de fond, régression supprimée |
| `localhost:8000/v1` → `172.17.0.1:8000/v1` dans le bloc DGX | §4 DGX | Correction technique |
| "plus de 32 Go" → "au moins 32 Go" | §4.8 | Alignement §4 encadré RAM |
| Commentaire `.env` DGX : `localhost:8000` retiré, seul le modèle change | §3.2 | Correction contradiction avec encadré Point critique |
| `VLLM_API_KEY` supprimée du `.env` | §3.2 | Suppression variable orpheline |
| `Nginx` retiré de la liste bloc DGX | §2 bloc DGX | Cohérence avec stack §3 sans Nginx |
| Contradiction LVM résolue : LVM recommandé, procédure d'extension conservée | §1.2 | Cohérence conseil / contenu |


### Nouvelles observations sur la fiabilité RAG (session 7 septembre 2026, suite)

#### Deux contrôles déterministes avant le juge LLM

Observation issue de la comparaison des réponses Sarrasin (correcte) vs Baumont (hallucinée) :

**Contrôle 1 : format des citations**
- Réponse ancrée sur des chunks réels : citations structurées, noms de fichiers réels dans les objets de citation
- Réponse hallucinée : URLs en texte brut insérées dans la prose, répétées à chaque ligne, aucun objet de citation
- Ce contrôle est déterministe, gratuit, et attrape le cas Baumont à coup sûr

**Contrôle 2 : validité du GUID dans les URLs citées**
- Le GUID inventé par le modèle dans la réponse Baumont : `3A2F3D5C-1234-4D56-89AB-CDEF01234567`
- Séquence 1234 + CDEF01234567 : signature d'un GUID de remplissage de documentation, jamais rencontré dans un vrai tenant SharePoint
- Contrôle possible : vérifier que les GUIDs cités existent parmi les chunks récupérés

**Observation sur le cas Sarrasin :**
Les citations pointent vers `06_Contrat_Maintenance_Etude_Rochat.docx`. Le nom de fichier ne correspond pas au client cité (Sarrasin). À vérifier : document renommé sans changement de contenu, ou problème d'appariement dans la première réponse. Si la réponse Sarrasin est elle-même douteuse, elle ne peut pas servir de cas positif dans le jeu de test.

**Observation sur le contenu halluciné Baumont :**
Le modèle n'a pas halluciné librement : il a réutilisé la structure de la réponse Sarrasin en changeant les noms propres (iManage Work attribué à une société industrielle, mêmes SLA, même structure de tenant, même formulation de résiliation). C'est exactement ce que "fais pareil" demande mécaniquement.

#### Où placer les contrôles déterministes

Pas dans Onyx CE : l'interface ne permet pas d'insérer une vérification entre la récupération et l'affichage.

Leur place est dans `main.py` de la RAG API, entre le retriever et la réponse :

```python
def verifier_ancrage(reponse: str, chunks: list) -> tuple[bool, str]:
    # Contrôle 1 : aucun chunk récupéré
    if not chunks:
        return False, "Aucun document pertinent trouvé"

    # Contrôle 2 : les sources citées existent parmi les chunks récupérés
    ids_reels = {c["source_id"] for c in chunks}
    ids_cites = extraire_citations(reponse)   # regex sur le format de citation

    inventees = ids_cites - ids_reels
    if inventees:
        return False, f"Sources inexistantes citées : {inventees}"

    # Contrôle 3 : réponse longue sans aucune citation
    if len(reponse) > 200 and not ids_cites:
        return False, "Réponse substantielle sans citation"

    return True, "OK"
```

Les contrôles déterministes couvrent les cas grossiers (aucun chunk, GUID inventé). Le juge LLM sert pour les hallucinations fines : modèle qui cite un vrai document mais lui fait dire autre chose.

#### Groundedness check : appel de base avec qwen3:4b

Vérifier que le modèle est disponible sur LABO-G9 : `ollama list`

```bash
curl http://<IP-LABO-G9>:11434/api/generate -d '{
  "model": "qwen3:4b",
  "prompt": "<prompt du juge>",
  "stream": false,
  "format": "json",
  "options": {"temperature": 0}
}'
```

Paramètres importants :
- `"format": "json"` : contraint la sortie, règle la majorité des problèmes de format instable
- `"temperature": 0` : rend le jugement reproductible

Le prompt du juge sera construit à partir de cas réels avec chunks connus. À faire après avoir récupéré les chunks d'un cas correct via OpenSearch ou l'API Onyx.

#### Matériel LABO-G9 : alimentation et accès distant

**Alimentation :**
- Référence : HP M86264-001
- Désignation : "SKO-PSU 550W ENT22 EPA92 5x12V"
- S'installe sans adaptateur dans le châssis Elite Tower 800 G9
- Deux connecteurs 6/8 broches fournis en plus du connecteur carte mère
- Le bloc actuel 260 W d'origine est insuffisant pour un GPU dédié

**Carte de prise en main à distance (KVM) :**
- Non tranchée dans les sessions précédentes
- HP ne propose pas d'équivalent iLO sur ses tours de bureau
- Piste à explorer : KVM sur IP externes pour accès headless
- Référence mentionnée dans les notes : Sipeed NanoKVM-PCIe (à évaluer)


### Corrections finales §4 (7 septembre 2026)

| Correction | Nature |
|---|---|
| Lien "Suite" : `section-05-continuedev.md` → `section-05-connecteurs.md` | Alignement plan de sections arrêté |
| Note "Chemin de menu à vérifier" ajoutée sous Admin → Language Models → Ollama | Honnêteté sur ce qui n'a pas été vérifié en live |

### Points ouverts avant publication

| Point | Fichier | Bloquant |
|---|---|---|
| Chemin exact Admin → Language Models → Ollama → Connect à vérifier en live | §4.5 | Non, note ajoutée |
| `pip show intel-openmp` dans /opt/vllm-env | §2 | Non |
| Cas Sarrasin : vérifier que `06_Contrat_Maintenance_Etude_Rochat.docx` correspond bien au client cité | Jeu de test | Non |
| `index.md` à rédiger | Guide complet | Oui pour GitHub Pages |


### État final Partie 1 : publiable (7 septembre 2026)

Les cinq fichiers sont cohérents et validés pour publication sur GitHub Pages.

**Fichiers à pousser :**
- `index.md` : §0 complet, déclaration de périmètre nette, sommaire, convention de statut
- `section-01-prerequis.md` : statut validé
- `section-02-vllm.md` : statut validé partiellement (bloc DGX documentaire)
- `section-03-docker-compose.md` : statut validé (RAG API squelette qualifiée)
- `section-04-onyx.md` : statut validé partiellement (chemin menu Onyx à confirmer)

**Deux vérifications à faire au prochain passage sur le lab :**
- Chemin de menu exact `Admin → Language Models → Ollama → Connect` dans Onyx CE. Si le chemin natif existe, retirer l'encadré de repli en §4.5. Si non, le repli OpenAI-Compatible reste la procédure.
- `pip show intel-openmp` dans `/opt/vllm-env` sur VM-RAG-LAB pour confirmer la version 2024.2.1 dans l'encadré "Versions validées" de §2.

**Ordre de travail pour la suite :**
1. §5 Connecteurs SharePoint et SMB : matière entièrement disponible dans les notes de session, App Registration validée, procédure SMB documentée.
2. §8 Fiabilité : hallucinations et contrôle d'ancrage. Nécessite une session de test avant rédaction. Les contrôles déterministes (format citations, validation GUID) sont la première brique, indépendants du GPU.
3. `indexer.py` Partie 2 : premier script Python de la RAG API, indexation SMB avec TEI bge-m3.


### Plan de rédaction des sections suivantes (7 septembre 2026)

Ordre arrêté :

| Ordre | Section | Raison |
|---|---|---|
| 1 | §6 Continue.dev | Court, matière prête, section publiable rapidement |
| 2 | §8 Fiabilité : hallucinations et contrôle d'ancrage | Priorité thématique, cas Baumont documenté, contrôles déterministes prêts |
| 3 | §5 Connecteurs SharePoint et SMB | Matière prête, App Registration validée |
| 4 | §7 Pipelines n8n | Complète le guide opérationnel |

La Partie 2 (indexer.py, RAG API avec permissions) démarre après §5.


### Matériel LABO-G9 : commandes en cours (8 septembre 2026)

**GPU commandé :** ASUS Dual GeForce RTX 5060 Ti OC, 16 Go GDDR7
**Alimentation commandée :** HP M86264-001, 550W ENT22 EPA92 (remplacement du 260W d'origine)

**Ce que ce GPU change pour la stack :**

| Composant | CPU actuel (i7-14700) | RTX 5060 Ti 16 Go |
|---|---|---|
| qwen2.5:14b inférence | ~3 à 5 tok/s | ~40 à 60 tok/s estimé |
| qwen2.5-coder:7b complétion | ~8 à 15 tok/s | ~80 à 120 tok/s estimé |
| bge-m3 embedding (TEI) | CPU VM | GPU LABO-G9 possible |
| Groundedness check qwen3:4b | ~2 à 3 min | ~5 à 10 s estimé |
| Modèle 30B (Qwen3-30B-A3B Q4_K_M) | Ne tient pas en RAM | ~14 Go VRAM, faisable |

**Architecture cible après installation GPU :**
- Ollama sur LABO-G9 avec GPU : inférence GPU automatique
- TEI bge-m3 : déplaçable sur GPU LABO-G9 ou rester CPU VM selon les mesures
- qwen3:4b juge groundedness : chargement dynamique, ~3 Go VRAM, compatible avec qwen2.5:14b en permanence (~9 Go) dans 16 Go

**Impact sur §6 (copilote développeur) :** les temps de réponse documentés pour la complétion passeront de 5 à 20 secondes (CPU) à 1 à 3 secondes (GPU). À remesurer après installation et mettre à jour la section.

**Impact sur §8 (fiabilité) :** le groundedness check devient pratique en production avec GPU. Les temps du tableau (2 à 3 min CPU → 3 à 5 s GPU) seront à valider sur le matériel réel.

**À faire à la réception du matériel :**
1. Installer le bloc 550W (remplacement du 260W)
2. Installer la RTX 5060 Ti
3. Vérifier que LABO-G9 démarre et détecte le GPU (`nvidia-smi` depuis WSL ou PowerShell)
4. Vérifier qu'Ollama utilise le GPU (`ollama ps` pendant une inférence)
5. Mesurer les tokens/s réels sur qwen2.5:14b et qwen2.5-coder:7b
6. Mettre à jour les tableaux de performance dans §6, §8 et §10


### Validation §6 : Cline en remplacement de Continue.dev (8 septembre 2026)

#### Continue.dev : arrêté

Continue.dev a été acquis par Cursor dans un acqui-hire annoncé le 16 juin 2026. Dernière version : v2.0.0-vscode, publiée le 19 juin 2026. Dépôt GitHub en lecture seule. Le hub cloud a fermé le 15 juillet 2026. L'extension s'installe encore mais ne reçoit plus de mises à jour. Non recommandé pour un nouveau déploiement.

#### Cline : outil retenu pour §6

- Provider : Ollama
- URL : `http://192.168.1.198:11434`
- Modèle : `qwen2.5:14b`
- API Key : vide
- Timeout : 300 000 ms (5 minutes, nécessaire sur CPU)

#### Ce qui a été validé en live sur WIN11-AD-TESTS

- Connexion à Ollama sur LABO-G9 via le réseau : OK
- Génération de code Python en français (fonction TVA suisse + tests unitaires) : OK
- Création du fichier `calcul_tva.py` dans le workspace : OK
- Exécution des tests : "Tous les tests sont passés avec succès"
- Gestion d'erreur (Python manquant) : Cline détecte et cherche une alternative

#### Observations importantes pour §6

- Cline est un agent de codage, pas un copilote de complétion en ligne. Il raisonne sur la tâche entière, crée les fichiers et exécute les commandes.
- Le timeout de 300 s est nécessaire sur CPU : les premières tentatives ont crashé avant la fin de la génération.
- Avec le GPU RTX 5060 Ti 16 Go attendu, les temps de réponse descendront à 5 à 15 secondes.
- Python doit être installé sur le poste développeur avec "Add to PATH" coché. Le stub Microsoft Store (`WindowsApps\python.exe`) interfère et doit être désactivé.
- `qwen2.5-coder:7b` n'est plus utilisé dans §6 : Cline utilise un seul modèle pour tout.

#### Différence Cline vs Continue.dev pour §6

| Fonctionnalité | Continue.dev (arrêté) | Cline |
|---|---|---|
| Complétion en ligne (gris pendant la frappe) | Oui | Non |
| Chat contextuel | Oui | Oui |
| Création de fichiers | Non | Oui |
| Exécution de commandes | Non | Oui |
| Agent autonome multi-étapes | Non | Oui |
| Modèles nécessaires | 2 (chat + complétion) | 1 |

