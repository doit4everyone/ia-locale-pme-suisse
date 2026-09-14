---
title: "§6 Cline : agent de codage | Guide de déploiement stack IA locale"
description: "Configuration de Cline dans VS Code pour connecter un agent de codage IA à Ollama sur LABO-G9."
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

# §6 Cline : agent de codage

[Retour au sommaire](index.md) | [Section précédente : §5 Connecteurs SMB](section-05-connecteurs.md)

**Statut :** validé sur WIN11-AD-TESTS avec VS Code et Ollama sur LABO-G9, septembre 2026.

---

> **Cette section est indépendante de §5.** Elle ne nécessite qu'Ollama configuré sur LABO-G9 (§4) et VS Code installé sur le poste développeur. Elle peut être lue dans n'importe quel ordre par rapport aux autres sections.

> **Note sur Continue.dev :** le guide prévoyait initialement Continue.dev comme copilote développeur. Continue.dev a été acquis par Cursor en juin 2026 et le produit est arrêté (dernière version : v2.0.0-vscode, dépôt en lecture seule, plus de mises à jour). L'outil retenu est **Cline**, le remplaçant direct le plus proche, open source, activement maintenu.

---

Cline est une extension VS Code open source qui connecte l'éditeur à un modèle LLM local. Contrairement à un copilote de complétion en ligne, Cline est un **agent de codage** : il raisonne sur une tâche entière, crée des fichiers, exécute des commandes dans le terminal et gère les erreurs. Un développeur peut lui décrire une tâche en langage naturel et Cline produit le code, les tests, et les exécute.

Dans cette configuration, Cline s'installe sur le poste développeur (WIN11-AD-TESTS) et se connecte à Ollama sur LABO-G9 via le réseau local avec le modèle `qwen2.5:14b`.

---

## §6.1 Prérequis

**Python sur le poste développeur :** Cline peut exécuter des scripts Python. Pour que l'exécution fonctionne, Python doit être installé avec le PATH configuré.

Télécharger Python depuis [python.org](https://python.org/downloads) et lors de l'installation, **cocher impérativement "Add python.exe to PATH"** sur le premier écran avant de cliquer Install Now. Sans cette case, Python s'installe mais reste inaccessible depuis le terminal.

Désactiver aussi le stub Microsoft Store qui interfère : **Paramètres Windows → Applications → Alias d'exécution des applications** → désactiver les entrées `python.exe` et `python3.exe`.

Vérification :

```powershell
python --version
```

Doit retourner `Python 3.x.x`.

---

## §6.2 Installation de Cline

Sur WIN11-AD-TESTS, dans VS Code :

1. Ouvrir l'onglet Extensions (Ctrl+Shift+X)
2. Rechercher **Cline**
3. Installer l'extension publiée par **Cline** (5M+ téléchargements, badge vérifié)
4. Redémarrer VS Code

---

## §6.3 Configuration

Ouvrir le panneau Cline dans la barre latérale gauche. Au premier lancement, sélectionner **"Bring my own API key"**, puis :

1. Dans le champ **API Provider**, sélectionner **Ollama**
2. Cocher **"Use custom base URL"**
3. Entrer `http://<IP-HOTE-OLLAMA>:11434` (adapter à l'IP de LABO-G9)
4. Laisser **Ollama API Key** vide : pas d'authentification pour Ollama local
5. Dans le champ **Model**, taper `qwen2.5:14b`
6. Laisser **Model Context Window** à la valeur par défaut (32768)
7. Passer **Request Timeout** à `300000` ms (5 minutes, nécessaire sur CPU)
8. Cliquer **Continue**

> **Sur le timeout :** en mode CPU, qwen2.5:14b génère du code à 3 à 5 tokens/s. Une réponse complète avec fonction et tests unitaires peut prendre 2 à 4 minutes. Le timeout par défaut est souvent insuffisant et provoque une interruption en milieu de génération. Avec le GPU, ce paramètre peut revenir à la valeur par défaut.

---

## §6.4 Validation

**Test 1 : connectivité Ollama**

Depuis PowerShell sur WIN11-AD-TESTS :

```powershell
curl http://<IP-HOTE-OLLAMA>:11434/api/tags
```

Doit retourner HTTP 200 avec la liste des modèles, dont `qwen2.5:14b`.

**Test 2 : tâche de codage complète**

Dans le chat Cline, taper :

```
Écris une fonction Python qui calcule la TVA suisse (8.1%) sur un montant HT
et retourne le montant TTC. Ajoute des tests unitaires et exécute-les.
```

Cline doit :
1. Générer la fonction avec docstring
2. Créer un fichier `.py` dans le workspace
3. Écrire les tests unitaires
4. Exécuter le fichier et rapporter le résultat

Résultat attendu dans le terminal :

```
Tous les tests sont passés avec succès
```

> **Résultat observé en validation :** Cline a généré la fonction `calculer_tva_suisse`, créé `calcul_tva.py` avec quatre tests unitaires (100 CHF, 250 CHF, 0 CHF, montant négatif), exécuté le fichier et confirmé que tous les tests passent. Temps total sur CPU : environ 3 à 4 minutes.

---

## §6.5 Différence avec un copilote de complétion en ligne

Cline n'est pas un copilote de complétion en ligne (pas de suggestions en gris clair pendant la frappe). C'est un agent qui agit sur instruction.

| Fonctionnalité | Cline | Copilote en ligne |
|---|---|---|
| Suggestions pendant la frappe | Non | Oui |
| Chat contextuel sur le code | Oui | Oui |
| Création de fichiers | Oui | Non |
| Exécution de commandes terminal | Oui | Non |
| Tâches multi-étapes autonomes | Oui | Non |
| Modèles nécessaires | 1 | 2 (chat + complétion) |

Pour un développeur seul dans une PME, la capacité à déléguer une tâche entière (écrire la fonction, les tests, les exécuter) est plus utile qu'une complétion caractère par caractère. Avec le GPU, Cline devient réellement fluide.

---

## §6.6 Points d'attention

- **OLLAMA_HOST sur LABO-G9 :** Ollama doit écouter sur le réseau. Vérifier que la variable d'environnement `OLLAMA_HOST=0.0.0.0:11434` est définie sur LABO-G9 (déjà configuré si Onyx fonctionne).
- **Auto-approve :** Cline demande confirmation avant d'écrire des fichiers ou d'exécuter des commandes. Le mode Auto-approve accélère les tâches répétitives mais doit être utilisé avec précaution sur des projets en production.
- **Workspace Cline :** les fichiers créés par Cline se trouvent dans `%USERPROFILE%\.cline\data\workspaces\chat\` par défaut. Ouvrir un dossier de projet dans VS Code pour que Cline travaille directement dans le bon répertoire.

---

## En production sur DGX Spark ou avec GPU local : ce qui change

> **Note :** cette section est documentaire pour le DGX Spark. Avec le GPU RTX 5060 Ti prévu sur LABO-G9, la configuration reste identique, seules les performances changent.

Avec GPU, changer uniquement l'URL si vLLM remplace Ollama :

```
Provider : openai (compatible OpenAI)
Base URL : http://<IP-HOTE-OLLAMA>:8000/v1
API Key  : <VLLM_API_KEY>
Model    : Qwen/Qwen3-30B-A3B
```

Les temps de réponse passent de plusieurs minutes (CPU, qwen2.5:14b) à quelques dizaines de secondes (GPU). Ces valeurs seront mesurées et documentées après installation du GPU sur LABO-G9. Le timeout peut être réduit une fois les performances réelles connues.

---

[Suite : §7 Pipelines n8n](section-07-n8n.md)

---

*Validé sur WIN11-AD-TESTS, VS Code, Ollama LABO-G9 (CPU), septembre 2026. Cline v2.x, qwen2.5:14b.*
