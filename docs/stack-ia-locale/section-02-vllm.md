---
title: "§2 Installation et configuration de vLLM | Guide de déploiement stack IA locale"
description: "Installation de vLLM en mode CPU sur Ubuntu 26.04, configuration pour validation sans GPU et script de lancement."
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

# §2 Installation et configuration de vLLM

[Retour au sommaire](index.md) | [Section précédente : §1 Prérequis](section-01-prerequis.md)

**Statut :** validé partiellement sur VM-RAG-LAB, septembre 2026. Le bloc vLLM-cpu est validé. Le bloc DGX Spark est documentaire, non validé sur matériel réel.

---

> **Pourquoi ce guide documente vLLM et utilise Ollama**
>
> vLLM est documenté dans cette section pour deux usages précis : valider la configuration du pipeline avant migration vers un DGX Spark, et servir de moteur d'inférence en production sur DGX Spark avec Qwen3-30B-A3B.
>
> Pour la validation sur le matériel de lab (LABO-G9, CPU), le backend retenu est **Ollama** sur le poste hôte. Onyx CE a été testé en §4 comme outil de validation du backend, puis abandonné au profit d'Open WebUI + RAG API FastAPI qui constituent la stack finale avec cloisonnement ACL NTFS réel.
>
> En production sur DGX Spark, le passage d'Ollama à vLLM se résume à modifier l'URL du provider LLM dans le fichier `.env`. Le reste de la stack (Docker Compose, Qdrant, n8n, Open WebUI, RAG API) est identique.

Architecture validée pour la démonstration : `WIN11-AD-TESTS → Open WebUI (VM-RAG-LAB, port 3001) → RAG API FastAPI → Ollama qwen2.5:14b (LABO-G9)`

Architecture cible pour la production DGX Spark : `Utilisateurs → Open WebUI → RAG API FastAPI → vLLM Qwen3-30B-A3B (DGX Spark)`

---

## §2.1 Installation

Le projet vLLM ne publie pas de wheel CPU sur PyPI. Pour la validation en mode CPU, ce guide utilise le paquet `vllm-cpu`, un reconditionnement communautaire maintenu indépendamment dans le dépôt [MekayelAnik/vllm-cpu](https://github.com/MekayelAnik/vllm-cpu) et distribué sous licence GPL-3.0 (le projet vLLM officiel est sous Apache 2.0). Il fonctionne et est utilisé ici pour la phase de validation, mais il ajoute une dépendance à un mainteneur unique. La voie officielle pour l'inférence CPU est l'image Docker `vllm/vllm-openai-cpu`, qui reste une alternative si vous préférez ne pas dépendre d'un paquet tiers.

Installer le wheel GPU standard puis tenter de le forcer en mode CPU ne fonctionne pas : le wheel officiel ne contient pas les kernels CPU compilés.

```bash
# Créer l'environnement virtuel
python3 -m venv /opt/vllm-env
source /opt/vllm-env/bin/activate

# Étape 1 : installer PyTorch CPU en premier
pip install torch==2.13.0+cpu \
  --index-url https://download.pytorch.org/whl/cpu

# Étape 2 : installer vllm-cpu (paquet communautaire, wheel unifié)
pip install vllm-cpu==0.28.0 \
  --extra-index-url https://download.pytorch.org/whl/cpu
```

> **Versions validées :** vllm-cpu 0.28.0, torch 2.13.0+cpu, intel-openmp 2024.2.1. Le téléchargement total est d'environ 600 Mo (contre 3 Go pour le wheel GPU).

> **Note sur les variantes ISA :** jusqu'à la version 0.16.0, le projet proposait des paquets distincts par jeu d'instructions (vllm-cpu-avx512, vllm-cpu-avx512vnni, etc.). Depuis la version 0.17.0, un seul paquet `vllm-cpu` détecte automatiquement les capacités du CPU au démarrage. Les anciens paquets par variante restent sur PyPI mais ne sont plus mis à jour.

---

## §2.2 Lancement pour validation CPU

La variable d'environnement `VLLM_TARGET_DEVICE=cpu` est obligatoire en vLLM 0.28.0 pour activer la plateforme CPU avant l'import des modules. Sans elle, vLLM tente de détecter un GPU et échoue.

```bash
source /opt/vllm-env/bin/activate

VLLM_TARGET_DEVICE=cpu OMP_NUM_THREADS=4 \
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-1.7B \
  --dtype float32 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.82 \
  --override-generation-config '{"temperature": 0.1, "top_p": 0.9, "top_k": 0}' \
  --host 0.0.0.0 \
  --port 8000
```

> **Sur `--gpu-memory-utilization` en mode CPU :** malgré son nom, ce paramètre contrôle la fraction de RAM système réservée par vLLM. La valeur 0.82 signifie que vLLM peut utiliser 82% de la RAM totale de la VM. La VM est dimensionnée à 16 Go dans ce guide parce que l'inférence est déportée sur Ollama et que la stack Open WebUI + RAG API tient dans cette enveloppe sans vLLM. Pour exécuter vLLM dans la VM à des fins de validation, il faut porter temporairement la VM à 20 Go : 16 Go se sont révélés insuffisants pour Qwen3 1.7B en float32 avec un KV cache de 8192 tokens. Avec 20 Go, la valeur 0.82 convient.

> **Sur le mode thinking Qwen3 :** Qwen3 active par défaut un mode de raisonnement interne (balises `<think>`) qui consomme des tokens inutilement pour les tâches RAG factuelles. Il faut le désactiver explicitement dans chaque requête (voir §2.4).

> **Sur la température :** Qwen3 1.7B a une température par défaut de 0.6 dans sa `generation_config.json`, trop élevée pour des tâches RAG factuelles. Le paramètre `--override-generation-config` force une température de 0.1, adaptée aux réponses déterministes.

Le premier lancement télécharge le modèle depuis HuggingFace (~3,8 Go). Les lancements suivants chargent le modèle depuis le cache local en environ 15 secondes.

---

## §2.3 Script de lancement

```bash
cat > /opt/start-vllm.sh << 'EOF'
#!/bin/bash
source /opt/vllm-env/bin/activate

VLLM_TARGET_DEVICE=cpu OMP_NUM_THREADS=4 \
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-1.7B \
  --dtype float32 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.82 \
  --override-generation-config '{"temperature": 0.1, "top_p": 0.9, "top_k": 0}' \
  --host 0.0.0.0 \
  --port 8000
EOF

chmod +x /opt/start-vllm.sh
```

Lancement : `/opt/start-vllm.sh`

---

## §2.4 Validation

Depuis un second terminal SSH, vérifier que le serveur répond :

```bash
# Test 1 : liste des modèles disponibles
curl http://localhost:8000/v1/models

# Test 2 : inférence avec mode thinking désactivé
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-1.7B",
    "messages": [
      {"role": "user", "content": "/no_think Réponds en une phrase : qu'\''est-ce qu'\''un pipeline RAG ?"}
    ],
    "max_tokens": 200,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

Résultat attendu : une réponse JSON avec `finish_reason: stop` et une réponse française cohérente en moins de 200 tokens.

---

## En production sur DGX Spark : ce qui change

> **Avertissement :** cette section est documentaire. Le bloc DGX Spark n'a pas été validé sur matériel réel dans le cadre de ce guide. Les commandes sont tirées de la documentation officielle vLLM et des retours publiés par des utilisateurs de DGX Spark. Un bug connu affecte certains modèles sur architecture ARM64 GB10 (bug NoPE) : vérifier que les correctifs SM121 sont présents dans la version de vLLM installée avant de déployer en production.

Sur DGX Spark, vLLM GPU standard remplace vllm-cpu. Seuls ces éléments changent :

```bash
# Installation : vllm standard sur DGX OS (CUDA 13 par défaut)
# uv est recommandé pour la résolution automatique du backend PyTorch
uv pip install vllm --torch-backend=auto

# Lancement sur DGX Spark avec un modèle NVFP4 pré-quantifié Nvidia
# Les modèles de la famille nvidia/* intègrent la quantification NVFP4 :
# la détection est automatique, --quantization n'est pas requis
python -m vllm.entrypoints.openai.api_server \
  --model nvidia/Qwen3-30B-A3B-NVFP4 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.90 \
  --enable-prefix-caching \
  --override-generation-config '{"temperature": 0.1, "top_p": 0.9, "top_k": 0}' \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key ${VLLM_API_KEY}

# Pour un modèle non pré-quantifié, ajouter explicitement :
# --quantization modelopt_fp4
```

> **Sur la commande d'installation :** la syntaxe `vllm[cuda13]` n'existe pas dans l'index officiel PyPI. Depuis vLLM 0.28.0, CUDA 13 est le défaut sur DGX OS. La commande `uv pip install vllm --torch-backend=auto` sélectionne automatiquement le backend PyTorch adapté à l'environnement détecté.

> **Sur la quantification NVFP4 :** le paramètre `--dtype` n'accepte pas `fp4`. La quantification NVFP4 relève de `--quantization modelopt_fp4`. Les modèles publiés par Nvidia sous la forme `nvidia/*-NVFP4` intègrent la quantification dans les poids : vLLM la détecte automatiquement sans flag supplémentaire. La disponibilité du modèle `nvidia/Qwen3-30B-A3B-NVFP4` est à vérifier au moment du déploiement : les références de modèles Nvidia évoluent.

Toutes les autres configurations (Docker Compose, Qdrant, n8n, Open WebUI, RAG API FastAPI, pipelines) sont identiques à ce qui est validé sur VM-RAG-LAB.

---

[Suite : §3 Docker Compose : stack complète](section-03-docker-compose.md)

---

*Validé sur VM-RAG-LAB, Ubuntu 26.04 LTS (resolute), vLLM-cpu 0.28.0, août 2026. Commandes testées en mode CPU sans GPU. Le bloc DGX Spark est documentaire, non validé sur matériel réel.*
