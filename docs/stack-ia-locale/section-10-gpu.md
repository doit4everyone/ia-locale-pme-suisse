---
title: "§10 Validation et performances sur GPU | Guide de déploiement stack IA locale"
description: "Passage de la stack RAG sur GPU (RTX 5060 Ti 16 Go) : mise en place, placement des modèles, méthode de mesure, gains CPU contre GPU, choix du modèle principal, de l'embedding et du reranker, règles de prompt, limites qui relèvent du corpus."
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

# §10 Validation et performances sur GPU

[Retour au sommaire](index.md) | [Section précédente : §9 Sécurité et durcissement](section-09-securite.md) | [Section suivante : §11 Prérequis Microsoft 365](section-11-prerequis-ms365.md)

**Statut :** validé en lab sur VM-RAG-LAB et LABO-G9, octobre 2026, avec une carte NVIDIA RTX 5060 Ti 16 Go. Mesures sur un jeu de 17 questions, graine de génération fixée, cloisonnement contrôlé à 40 cas sur 40 (et en mode complet sur les cas Purview, écriture seule et refus explicite) après chaque modification.

Jusqu'ici, toute la stack tournait sur le processeur de LABO-G9. Cette section documente le passage sur une carte graphique, puis la campagne de mesures qui a suivi : ce que la carte change, et surtout ce qu'elle ne change pas. Car le résultat principal tient en une phrase : **la carte divise les temps de réponse par cinq à dix, sans rien changer à la qualité ni à la sécurité**. La qualité, elle, s'est gagnée ailleurs : dans la construction du contexte, dans le prompt, et dans le corpus.

---

## §10.1 Matériel et mise en place

### La carte

| Élément | Valeur |
|---|---|
| Carte | NVIDIA GeForce RTX 5060 Ti, 16 Go GDDR7, génération Blackwell |
| Bande passante mémoire | 448 Go/s (interface 128 bits) |
| Puissance | 180 W, un connecteur PCIe 8 broches |
| Alimentation du PC | 550 W au minimum selon le constructeur ; l'alimentation d'origine du PC du lab a dû être remplacée |
| Emplacement | Le slot PCIe câblé en x16 (sur la carte mère du lab, le long slot marqué `X16PCIEXP`) ; un slot de même longueur mais câblé en x4 fonctionnerait, avec un chargement des modèles plus lent |

Pour un modèle de langage, la vitesse de génération dépend surtout de la **bande passante mémoire**, pas de la puissance de calcul : c'est elle qui limite le nombre de mots produits par seconde.

### Le pilote, en installation minimale

Seul le pilote est nécessaire. Ollama embarque ses propres bibliothèques CUDA : le **CUDA Toolkit** (plusieurs gigaoctets, destiné aux développeurs) est inutile. À l'installation du pilote, choisir l'installation personnalisée, sans l'application NVIDIA, sans le pilote audio HD ni PhysX : ce sont ces logiciels, et non le pilote, qui occupent la mémoire du système.

```powershell
nvidia-smi
```

**Attendu :** la carte, ses 16 Go, la version du pilote et celle de CUDA. Dans le lab : pilote 616.92, CUDA 13.4.

### Ollama : des réglages vérifiés dans son journal

Ollama doit être à jour pour reconnaître une carte Blackwell. Les réglages se placent dans les **variables d'environnement utilisateur** de Windows (Ollama tourne dans la session de l'utilisateur, pas comme service) :

| Variable | Valeur | Effet |
|---|---|---|
| `OLLAMA_FLASH_ATTENTION` | `1` | Calcul de l'attention plus économe en mémoire |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | Cache du contexte sur 8 bits : environ moitié moins de mémoire, perte de qualité négligeable |
| `OLLAMA_NUM_PARALLEL` | `1` | Une requête à la fois : pas de cache de contexte dupliqué |
| `OLLAMA_KEEP_ALIVE` | `1h` | Modèles gardés en mémoire une heure (5 minutes par défaut) |
| `OLLAMA_NO_CLOUD` | `1` | Désactive les modèles hébergés sur ollama.com, appelables comme des modèles locaux : cohérent avec une stack dont rien ne doit sortir |

Deux variables d'Ollama se sont révélées ignorées dans ce lab au cours des mois précédents. **On vérifie donc le résultat, pas le réglage** : après un redémarrage d'Ollama (quitter depuis la zone de notification, puis relancer), son journal affiche la configuration lue et le moteur retenu.

```powershell
Select-String -Path "$env:LOCALAPPDATA\Ollama\server.log" -Pattern "FLASH_ATTENTION|KV_CACHE_TYPE|NUM_PARALLEL" | Select-Object -Last 1
Select-String -Path "$env:LOCALAPPDATA\Ollama\server.log" -Pattern "inference compute" | Select-Object -Last 1
```

**Attendu :** `OLLAMA_FLASH_ATTENTION:true`, `OLLAMA_KV_CACHE_TYPE:q8_0`, `OLLAMA_NUM_PARALLEL:1`, puis `library=CUDA` avec la carte et la mémoire disponible (14,8 Go dans le lab, l'écran étant branché sur la carte).

L'accès réseau d'Ollama, nécessaire pour que la VM le joigne, peut être réglé par la variable `OLLAMA_HOST` ou par l'option « Expose Ollama to the network » de ses paramètres : le journal indique `OLLAMA_HOST:http://0.0.0.0:11434` dans les deux cas.

### Administration à distance

Le calcul sur la carte fonctionne normalement dans une session Bureau à distance. Un piège : Ollama tourne dans la session de l'utilisateur. **Fermer la fenêtre RDP** laisse la session ouverte et Ollama actif ; **se déconnecter** (fermer la session) arrête Ollama, et la RAG API n'a plus de modèle.

### Température

Mesures dans un boîtier de bureau, profil BIOS silencieux de la carte (interrupteur sur la carte, à changer PC éteint) :

| Situation | Température | Puissance | Ventilateurs |
|---|---|---|---|
| Repos | 39 à 52 °C | 8 à 9 W | 0 à 39 % |
| Pleine charge (lecture d'un long contexte) | 79 °C au maximum | 180 W, la limite | 70 % |

La carte retombe à 52 °C quelques secondes après la charge. Elle commencerait à réduire ses fréquences vers 83 °C. Si cette limite était atteinte régulièrement, la solution la plus efficace serait de limiter la puissance (`nvidia-smi -pl 150`) : la génération de texte, limitée par la mémoire, n'en souffre presque pas.

---

## §10.2 Placement des modèles sur la carte

### Le budget de mémoire

| Modèle | Rôle | Mémoire occupée | Contexte |
|---|---|---|---|
| `qwen3:14b` | Modèle principal | 10 Go (12 Go sur CPU : le cache sur 8 bits fait la différence) | 16 384 |
| `qwen3:4b` | Juge d'ancrage | 3,9 Go | 16 384 (voir §10.6) |
| `nomic-embed-text` | Embedding | 0,3 Go | 2 048 |
| **Total**, avec l'affichage | | **environ 15,3 Go sur 16,3** | |

`ollama ps` doit afficher `100% GPU` pour chaque modèle placé sur la carte. Un partage du type `20%/80% CPU/GPU` signifie que le modèle déborde : la première mesure à prendre est alors de réduire la fenêtre de contexte (`LLM_NUM_CTX=12288` couvre largement les questions, qui envoient 4 000 à 6 000 tokens).

### Une décision révisée par la mesure

Le placement prévu laissait le juge et l'embedding sur le CPU, pour réserver la carte au modèle principal. La RAG API le permet par deux réglages, sans effet tant qu'aucune carte n'est présente :

| Réglage | Valeur | Effet |
|---|---|---|
| `JUDGE_NUM_GPU` | `0` | Juge sur le CPU ; vide, Ollama le place sur la carte s'il y a la place |
| `EMBED_NUM_GPU` | `0` | Embedding sur le CPU ; transmis aussi aux indexeurs, pour qu'Ollama ne recharge pas le modèle à chaque alternance |

La mesure a renversé la décision pour le juge. Avec le modèle principal sur la carte et le juge sur le CPU, une question vérifiée prenait environ une minute : le juge, qui relit la réponse et ses sources, était devenu le goulet d'étranglement. Il tient sur la carte :

Répartition mesurée pour une question à réponse détaillée, avant les règles de prompt du §10.9 qui ont raccourci les réponses :

| Étape d'une question | Placement | Durée |
|---|---|---|
| Embedding de la question | GPU | 0,3 s |
| Lecture du contexte et rédaction | GPU | 13,7 s |
| Vérification par le juge | **GPU** | **1,6 s** |

L'embedding a suivi, faute de raison de le laisser sur le CPU. Les trois modèles sont sur la carte.

### La mémoire « partagée »

Le Gestionnaire des tâches de Windows affiche deux compteurs : la mémoire **dédiée** (celle de la carte) et la mémoire **partagée** (de la RAM du PC que la carte peut utiliser). Quelques centaines de Mo de mémoire partagée sont normaux (affichage, session RDP). Mais si la carte manque de mémoire, le pilote peut déborder dans la RAM au lieu de signaler une erreur : le calcul continue, beaucoup plus lentement. Le signe est double : la mémoire partagée qui grimpe de plusieurs Go pendant une question, et des réponses soudain plusieurs fois plus lentes.

Sur un poste qui héberge aussi des VM, les consoles de VMware Workstation (`mksSandbox.exe`) occupent de la mémoire graphique. Fermer les consoles inutiles ou désactiver l'accélération 3D des VM serveurs libère de la place si la marge devient juste.

---

## §10.3 Méthode de mesure

Comparer des configurations à l'œil, sur quelques questions posées à la main, conduit à des conclusions fausses : une réponse varie d'un passage à l'autre, et une question réussie peut cacher un mauvais document en tête du contexte. Le lab a donc utilisé un jeu de questions fixe, et un script qui l'évalue.

### Le jeu de questions

17 questions, chacune avec des critères vérifiables automatiquement :

| Type | Exemples | Ce qu'elles mesurent |
|---|---|---|
| Précises | Durée, forfait et délais d'un contrat client | Exactitude, citation du bon document |
| Pièges | Le forfait du contrat (4 200), alors qu'une réunion parle d'un renouvellement à 3 900 ; deux versions d'un même contrat | Les confusions déjà observées |
| Cloisonnement | Un code confidentiel demandé par un compte sans droit | Ni le document ni le code dans la réponse |
| Multilingue | Le forfait du contrat, demandé en allemand | La recherche entre langues |
| Larges | « Résume ce que tu sais sur les clients » ; le guide du helpdesk | La synthèse de plusieurs documents |
| Inventaire | « Liste les règles YAML » | Une limite connue des RAG |
| Refus | La capitale de l'Australie ; un client inexistant | Aucune invention |

Les critères : le **document principal** du contexte (le premier, pas seulement présent), les éléments **attendus** dans la réponse, les éléments **interdits** (les pièges), le refus attendu ou non, et l'ancrage selon le juge.

### La graine et le nombre de passages

Avec `LLM_SEED` fixé (42 dans le lab), la génération devient reproductible : cinq passages de la configuration de référence ont donné des réponses identiques, au dixième de seconde près. C'est ce qu'il faut pour **comparer** deux configurations à conditions égales : **un passage suffit**. En contrepartie, une seule graine peut tomber sur un tirage favorable : la configuration finale se contrôle avec plusieurs graines. En usage normal, `LLM_SEED` reste vide.

### Le piège du cache

Ollama garde le calcul du dernier texte lu. Une question posée **deux fois de suite** est servie beaucoup plus vite (23 secondes au lieu de plus d'une minute sur CPU, dans le lab) : on mesure alors le cache, pas le modèle. Le script pose les questions du jeu dans l'ordre, passage après passage, pour qu'une même question ne soit jamais posée deux fois d'affilée. Le premier appel après un redémarrage ou un changement de réglage inclut, lui, le chargement des modèles.

### Le script

`mesure_s10.py`, lancé dans le conteneur de la RAG API, pose chaque question au nom du compte indiqué (comme Open WebUI), lit les sources dans le journal des requêtes, évalue la réponse et produit un rapport JSON avec la configuration mesurée (modèles, graine, réglages). Il est fourni dans le dépôt avec le jeu de questions.

```bash
docker exec -it rag-api python3 /rag-pipeline/s10/mesure_s10.py \
    /rag-pipeline/s10/jeu_questions_s10.json --passages 1 --etiquette ma-configuration
```

---

## §10.4 CPU contre GPU

Mêmes modèles, même configuration, seul le matériel change :

| Mesure | CPU (LABO-G9) | GPU (RTX 5060 Ti) |
|---|---|---|
| Question précise vérifiée par le juge | 1 min 15 à 1 min 30 | **2 à 6 s** |
| Question large ou longue réponse | 1 min 30 à 2 min | **7 à 15 s** |
| Synthèse d'une réunion Teams de test | 100 à 146 s | **11 s** |
| Score de la synthèse Teams (corrigé sur 14 points) | 11 à 12 | 11 |
| Refus (culture générale, client inexistant) | 2 sur 2 | 2 sur 2 |
| Cloisonnement | 40 sur 40 | 40 sur 40 |

Le gain est d'un facteur cinq à dix, sans aucun effet sur la qualité ni la sécurité : c'est attendu, puisque les modèles sont les mêmes. Ce qui change vraiment, c'est l'usage : une campagne de mesure de 15 questions prend désormais une à deux minutes. Les comparaisons qui suivent n'auraient pas été réalistes sur CPU.

---

## §10.5 Le modèle principal

Avant le GPU, le lab a comparé `qwen2.5:14b`, le modèle recommandé jusqu'ici, à `qwen3:14b`, de même taille :

| Critère | `qwen2.5:14b` | `qwen3:14b` |
|---|---|---|
| Question large sur les clients | Un client détaillé, aucune citation | Trois clients, chacun cité, avec la nuance juste (une réponse à appel d'offres présentée comme un client potentiel) |
| Phrase de refus contradictoire après une réponse | Présente | Absente |
| Refus (culture générale, client inexistant) | Tenus | Tenus |
| Synthèse Teams (deux passages) | 12 et 11 sur 14 | 11 et 11 sur 14 |

**`qwen3:14b` devient le modèle recommandé.** La meilleure capacité de synthèse ne s'est pas faite au prix de l'invention : les refus tiennent. Le mode de raisonnement de Qwen3 est désactivé par la directive `/no_think` en fin de prompt ; aucune réponse ne contient de balise de raisonnement.

### Apertus, le modèle suisse

Apertus, développé par l'EPFL, l'ETH Zurich et le Centre suisse de calcul scientifique (CSCS), est un modèle entièrement ouvert (poids, données et méthode d'entraînement) et conçu pour le multilinguisme. Pour une PME suisse attentive à l'origine de ses outils, la question de son usage se pose naturellement : il a été testé dans sa version de 8 milliards de paramètres (Apertus-8B-Instruct-2509), quantifiée en Q4_K_M, avec le même jeu de questions et le même juge.

Il n'est pas disponible dans la bibliothèque officielle d'Ollama au moment du test. La version utilisée est une conversion GGUF publiée par la communauté sur Hugging Face, que l'on télécharge par `ollama pull hf.co/<auteur>/<dépôt>:Q4_K_M`. Elle tient sur la carte (5 à 6 Go) et démarre sans erreur, mais elle embarque le gabarit de conversation d'origine, écrit pour la bibliothèque Transformers, et non un gabarit au format d'Ollama. Les jetons propres à Apertus risquent alors d'être mal placés : à la question « quelle est la capitale du canton du Jura ? », le modèle répondait « Delle ». Avec un gabarit réécrit au format d'Ollama (un modèle local créé par `ollama create` à partir d'un `Modelfile`), il répond « Delémont ».

| Mesure | `qwen3:14b` | Apertus 8B, gabarit d'origine | Apertus 8B, gabarit réécrit |
|---|---|---|---|
| Score sur le jeu de questions | 11 à 12 sur 15 | 4 sur 15 | 4 sur 15 |
| Questions précises, bon document en tête du contexte | Réponses justes et citées | Refus | Refus |
| Document absent pour le compte (code confidentiel) | Refus | Code **inventé** | Code **inventé** |
| Fuite du vrai document | Aucune | Aucune | Aucune |

Le gabarit n'était donc pas la seule cause. Isolé du RAG, avec un contexte d'une phrase et une consigne courte, le modèle extrait correctement l'information (sans la citer). Avec le contexte réel (environ 5 000 tokens) et un prompt strict, il refuse des questions dont la réponse est sous ses yeux, recopie des extraits bruts au lieu de répondre, et, sur la question posée par un compte sans droit, invente un code de vérification plausible. Ce dernier cas n'est pas une fuite : le cloisonnement a joué, le vrai document n'était pas dans le contexte, et le juge a signalé la réponse. Mais c'est le comportement le plus dangereux pour un outil documentaire.

**Apertus 8B n'est pas adapté à ce RAG, dans cette version et cette taille.** Ce résultat ne juge pas le projet : il compare un modèle de recherche de 8 milliards de paramètres, dont les priorités sont la transparence et le multilinguisme, à un modèle de 14 milliards fortement entraîné à suivre des consignes. Le test sera à refaire avec les versions suivantes. Deux enseignements valent pour tout modèle :

- **vérifier le gabarit d'une conversion communautaire** avant toute évaluation (`ollama show <modèle> --template`) : un gabarit inadapté fausse le jugement porté sur le modèle ;
- **un test court ne prédit pas le comportement dans le RAG** : seul le jeu de questions complet, avec le vrai contexte et le vrai prompt, a montré les refus et l'invention.

La synthèse Teams illustre une leçon de méthode. Comparé à un seul passage de l'ancien modèle (12 sur 14), `qwen3:14b` semblait moins bon (11). Deux passages de chaque montrent que `qwen2.5:14b` varie lui-même entre 11 et 12 : l'écart est dans le bruit. Le lab utilise donc **un seul modèle** pour les questions et la synthèse, ce qui économise 12 Go de mémoire et un rechargement à chaque passage Teams.

---

## §10.6 La construction du contexte

La façon dont les extraits sont choisis et assemblés a pesé davantage que le choix des modèles.

### La diversité des sources

Décrite au §8.9 : 30 candidats, un document principal, six documents complémentaires de deux extraits, copies écartées.

### Un document court envoyé en entier

Une question sur la durée d'un contrat était refusée sur GPU, alors que la réponse figure dans le contrat. Le journal l'a expliqué : le document principal était bien le contrat, mais seuls ses extraits 0 à 4 avaient été envoyés. Le meilleur extrait était **l'en-tête** du contrat, qui nomme le client et contient donc les mots de la question, et la fenêtre centrée sur lui butait sur le début du document. La clause « Durée et résiliation », en fin de contrat, était hors du contexte. Le modèle avait raison de refuser : il ne voyait pas l'information.

Deux corrections :

| Réglage | Valeur | Effet |
|---|---|---|
| `DOC_COMPLET_MAX` | 15 | Un document principal de 15 extraits au plus (contrat, procédure, note) est envoyé **en entier** |
| Fenêtre décalée | | Pour un long document, la fenêtre de 9 extraits se décale au lieu d'être tronquée quand elle touche le début ou la fin |

La même question a alors obtenu la bonne réponse, le contrat de 7 extraits ayant été envoyé complet.

### Les documents complémentaires : des extraits consécutifs

Le même défaut touchait les documents complémentaires, et c'est lui qui faisait échouer les questions larges. À « que disent les contrats clients d'Axonix SA », la RAG API envoyait, pour chaque contrat, ses deux extraits les mieux classés par la recherche : leur **en-tête** (« Contrat de maintenance informatique entre Axonix SA et… »), qui contient les mots de la question. Le modèle recopiait ces en-têtes, prêtait aux contrats des services tirés d'une autre source, et concluait que les détails manquaient.

Augmenter le nombre d'extraits par complément n'y changeait rien : les autres extraits des contrats ne figuraient même pas parmi les candidats de la recherche. La correction applique aux documents complémentaires le principe du document principal : à partir du meilleur extrait de chaque document, la RAG API charge les **extraits qui le suivent dans le document**, avec exactement les mêmes filtres (droits dans la requête Qdrant, refus explicites, Purview).

| Extraits consécutifs par complément | Score | Réponse « que disent les contrats clients » | Questions précises |
|---|---|---|---|
| 2 (sans fenêtre) | 12 sur 15 | En-têtes recopiés, fausse absence | 2 à 4 s |
| **4** | **12 sur 15** | **Périmètre des deux contrats** ; avec la question « que sais-tu des clients », les trois clients, chacun décrit | 4 à 6 s |
| 8 | 11 sur 15 | Tout, forfaits et durées compris | 6 à 9 s |

La valeur retenue est **4** (`EXTRAITS_PAR_COMPLEMENT`, fenêtre activée par `COMPLEMENT_VOISINS=1`). Avec 8, les contrats arrivent entiers, mais le contexte approche 11 000 tokens, les durées doublent et la carte n'a plus qu'un gigaoctet de marge : c'est une option pour une carte plus grande. Après ce changement, qui ouvre un nouveau chemin de lecture dans Qdrant, le test de cloisonnement a été rejoué **en mode complet** : un contrôle d'accès seul ne suffit pas à le valider.

### Une identité d'extrait plus juste, et pourtant écartée

Une revue externe a relevé que la fusion des deux classements (vectoriel et par mots-clés) identifie un extrait par **l'empreinte de son texte** : deux extraits au texte identique, dans deux documents différents, sont fusionnés en une seule entrée. Une identité par **position** (document et rang) est plus juste en théorie. Mesurée, elle a fait passer une copie de test du contrat Baumont, dont la plupart des extraits sont identiques à l'original, **devant le contrat lui-même** sur la question des délais, et la question sur les clients d'Axonix est devenue un refus. Avec l'empreinte du texte, les deux copies d'un même extrait cumulent leurs scores au lieu de se les partager. L'empreinte est donc conservée, avec un commentaire qui dit ce qu'elle est : une clé de fusion, pas une identité unique. Les droits ne sont pas en jeu, les deux classements étant filtrés avant la fusion.

### La fenêtre du juge doit couvrir celle du modèle

Le premier essai à 8 extraits a fait chuter le score de 12 à **8 sur 15**, avec cinq avertissements d'ancrage, dont deux sur des questions précises qui réussissaient toutes. Les réponses étaient pourtant justes. Le juge reçoit la réponse **et toutes les sources** ; sa fenêtre était de 8 192 tokens, celle du modèle principal de 16 384. Sur un contexte de 11 000 tokens, Ollama coupait le début du texte du juge : il perdait une partie des sources et déclarait non ancrées des affirmations qu'il ne voyait plus. Avec une fenêtre de 16 384, le score est remonté à 11, et le journal d'Ollama ne signale plus de coupure (`truncated = 0`).

La règle est simple : **la fenêtre du juge doit être au moins celle du modèle principal**. C'est désormais le comportement par défaut de la RAG API (`JUDGE_NUM_CTX` prend la valeur de `LLM_NUM_CTX` s'il n'est pas défini). Le coût, environ 0,6 Go de mémoire graphique, est celui du tableau du §10.2.

---

## §10.7 L'embedding

`nomic-embed-text` a été comparé à `bge-m3`, réputé meilleur en français et multilingue. Le changement d'embedding est un vrai chantier : de nouvelles collections (les vecteurs changent de taille), une réindexation complète, et la revalidation du cloisonnement, puisque les permissions sont recopiées dans chaque extrait. Les anciennes collections restent en place jusqu'à la décision : revenir en arrière tient en trois lignes du `.env`.

| | `nomic-embed-text` | `bge-m3` |
|---|---|---|
| Score sur le jeu de questions | 12 sur 15 | 12 sur 15 |
| Gagné par l'un, perdu par l'autre | Délais d'un contrat (le bon contrat en tête) | Liste des règles YAML (le bon chapitre en tête) |
| Mémoire | 0,4 Go | 1,2 Go |
| Réindexation complète sur CPU | | Plus de 10 minutes : coupée par la limite de durée des indexeurs, terminée en deux passages |
| Cloisonnement après réindexation | 40 sur 40 | 40 sur 40 |

Match nul. `bge-m3` comprend mieux la documentation technique, mais il a confondu deux contrats de maintenance au contenu très semblable. Son atout, le multilinguisme, ne se voit pas sur un corpus entièrement francophone : même la question posée en allemand réussit avec `nomic-embed-text`.

**`nomic-embed-text` reste le modèle recommandé** pour un corpus francophone. `bge-m3` se justifierait pour un corpus réellement multilingue (documents en allemand et en italien), ce qui serait à mesurer sur un tel corpus.

> **Une réindexation complète peut dépasser la limite des indexeurs.** La RAG API interrompt un indexeur après 10 minutes par défaut (`SYNC_TIMEOUT_INDEXER`, en secondes), ce qui suffit aux synchronisations horaires, pas à une réindexation complète avec un modèle d'embedding plus lourd sur CPU. Augmenter cette limite le temps de la réindexation, ou relancer la synchronisation, qui est incrémentale ; mais un fichier interrompu en cours d'indexation peut rester incomplet. Comparer, document par document, le nombre d'extraits de l'ancienne et de la nouvelle collection permet de le détecter : le découpage ne dépend pas du modèle d'embedding.

---

## §10.8 Le reranker

Un reranker relit chaque extrait candidat **avec la question**, au lieu de comparer des vecteurs. C'était la réponse attendue au principal défaut constaté : pour « résume ce que tu sais sur les clients », la recherche plaçait en tête des documents qui emploient souvent le mot (politique RH, politique de sécurité) plutôt que les contrats.

### Le service

Le serveur d'inférence de Hugging Face, Text Embeddings Inference, en version CPU (`ghcr.io/huggingface/text-embeddings-inference:cpu-1.9`), dans un conteneur sans port publié : seule la RAG API le joint. Le modèle se télécharge au premier démarrage. La RAG API ne lui envoie que des extraits **déjà autorisés** (après les filtres d'accès et Purview) ; s'il ne répond pas, l'ordre d'origine est conservé.

Il n'existe pas, au moment des essais, d'image de ce serveur pour les cartes Blackwell : la voie du reranker sur GPU est fermée par ce moyen.

### Premier modèle : `bge-reranker-v2-m3`

Son jugement est excellent : sur la question des clients, il donne 0,65 à un contrat de maintenance et 0,000025 à la politique RH qui mentionne « les données clients ». Mais sur CPU, il a révélé trois pièges :

| Constat | Cause | Correction |
|---|---|---|
| **9 Go de RAM** et deux à trois cœurs occupés **au repos** | Au démarrage, le serveur effectue un préchauffage sur un lot de la taille maximale autorisée (16 384 tokens par défaut) | `--max-batch-tokens 4096` et `mem_limit: 4g` : 1,2 à 1,9 Go |
| Toutes les requêtes refusées (HTTP 429) | `--max-concurrent-requests 2` : chaque texte à reclasser compte comme une requête | `--max-concurrent-requests 64` |
| 20 secondes de plus par question, sans effet | Délai de réponse dépassé : le reranker était trop lent | Mesurer sa vitesse avant tout |

Sa vitesse sur les 6 cœurs de la VM : 4,7 s pour 10 extraits, 8,7 s pour 20, 13,5 s pour 30, soit environ 0,45 s par extrait. Reclasser 30 candidats doublait la durée d'une question.

### Second modèle : `gte-multilingual-reranker-base`

Deux fois plus petit, pris en charge par le même serveur : 0,51 contre 0,054 sur le même test (un écart moins tranché, mais net), et deux fois plus rapide (1,9 s pour 10 extraits, 4,0 s pour 20, 6,8 s pour 30).

### Les résultats

Sur 20 candidats, avec `nomic-embed-text` :

| Configuration | Score | Durée d'une question précise |
|---|---|---|
| **Sans reranker** | **12 sur 15** | **2 à 5 s** |
| Reranker, ordre remplacé | 11 sur 15 | 8 à 10 s |
| Reranker, ordre fusionné avec celui de la recherche | 10 sur 15 | 8 à 10 s |

En remplaçant l'ordre de la recherche, le reranker gagne les questions larges (les trois clients enfin trouvés) et la liste des règles YAML, mais il en perd d'autres : il **ignore les noms propres**. Pour lui, le tableau des délais d'un contrat Rochat répond aussi bien à « délais du contrat Baumont » que celui du contrat Baumont, puisque les deux tableaux disent la même chose. La recherche par mots-clés, elle, tenait compte du nom. La fusion des deux classements retrouve les noms propres, mais perd les gains.

**Le reranker est désactivé dans ce lab.** Sur CPU, avec un corpus de cette taille, il n'apporte aucun gain mesurable et coûte 5 à 6 secondes par question. Le code reste en place, inactif tant que `RERANKER_URL` est vide, et le service est fourni dans le Compose comme option. Il deviendrait intéressant avec une carte dédiée, un corpus de milliers de documents, ou une recherche initiale plus faible.

> **Ce que le reranker a révélé sur le corpus.** Pour la question du forfait d'un contrat, il a classé en tête la section du guide sur la fiabilité, indexée dans la collection documentation : elle cite justement ce contrat, ses montants et les cas de test. Le reranker n'avait pas tort sur le texte, mais c'est le mauvais document. Voir §10.10.

---

## §10.9 Le prompt et la forme des réponses

### Trois règles de plus

| Règle | Pourquoi |
|---|---|
| Ne jamais affirmer qu'un document « ne contient pas » une information : écrire que les extraits consultés ne permettent pas de le dire | Le modèle ne voit que des extraits. Sur une procédure de plusieurs dizaines de pages, il a affirmé que « le document ne précise pas les étapes détaillées », ce qui était faux : une **fausse absence**, plus insidieuse qu'une invention |
| Chaque citation entre crochets, même dans une longue réponse | Sans crochets, les citations ne sont ni vérifiables par les contrôles ni transformées en liens |
| Synthétiser sans recopier ni remplir | Sur les questions de liste, le modèle recopiait des extraits entiers (titres, blocs de commandes) ou répétait la même formule pour chaque élément |

Activées par `PROMPT_REGLES_V2=1`, elles ont été mesurées seules :

| Mesure | Sans | Avec |
|---|---|---|
| Score | 12 sur 15 | 11 sur 15 (un avertissement d'ancrage de plus, dans le bruit) |
| Synthèse du guide helpdesk | 45 s | **14 s** |
| Liste des règles YAML | 127 s | **7 s** |
| Campagne de 15 questions | 4,2 min | **1,4 min** |
| Refus, éléments interdits | 2 sur 2, aucun | 2 sur 2, aucun |

Les réponses sont trois fois plus courtes là où le modèle recopiait. Les règles sont retenues.

### Ce que le prompt ne suffit pas à obtenir

**Les crochets.** Malgré la règle, le modèle continue de citer sans crochets dans les longues réponses. La RAG API corrige désormais côté code : les noms des documents réellement fournis au modèle, cités sans crochets, sont remis entre crochets. Les citations redeviennent vérifiables et cliquables.

**Les balises recopiées.** Le modèle recopiait parfois en tête de réponse les balises qui délimitent les documents dans le contexte (`[DONNÉES DOCUMENTAIRES]`, lignes `→ nom_de_fichier`). Elles sont retirées de la réponse, sans toucher au texte.

**Une invention que le juge n'a pas vue.** Dans un résumé par ailleurs exact, le modèle a développé le sigle « SIT » en « Système d'Information de Travail ». Dans Purview, SIT signifie *Sensitive Information Type*. Le modèle a complété un sigle avec ses propres connaissances, ce que le prompt interdit, et le juge ne l'a pas relevé. Le cas a rejoint le jeu de questions comme élément interdit : il rappelle qu'aucune couche de contrôle n'est infaillible.

---

### Deux pièges de configuration

Deux erreurs commises pendant ces mesures valent d'être connues, parce qu'un lecteur les ferait aussi.

**Un réglage absent du Compose reste sans effet, sans aucun message.** Une variable du `.env` n'atteint la RAG API que si elle figure dans la section `environment` du service `rag-api`. Pendant une matinée, `EXTRAITS_PAR_COMPLEMENT` a été modifiée dans le `.env` et mesurée à 4 puis à 8, alors que la RAG API utilisait toujours sa valeur par défaut : deux mesures sans valeur. Le signe était visible : `docker compose up -d` répondait `Running` au lieu de `Started` (rien à recréer), et `printenv` n'affichait rien. **Vérifier un réglage dans le conteneur, jamais seulement dans le `.env`** :

```bash
docker exec -i -w /app rag-api python3 -c "import main; print(main.EXTRAITS_PAR_COMPLEMENT, main.JUDGE_NUM_CTX)"
```

**Une variable transmise vide n'est pas une variable absente.** Écrite `- REGLAGE=${REGLAGE:-}` dans le Compose, elle arrive vide dans le conteneur ; un réglage numérique lu par `int("")` empêchait alors la RAG API de démarrer (redémarrage en boucle). Le Compose publié donne une valeur par défaut à chaque réglage, et la RAG API, l'indexeur et le module d'authentification traitent désormais une valeur vide comme une valeur absente. Un audit du code a recensé 19 lectures concernées.

---

## §10.10 Ce qui relève du corpus

Une fois les réglages mesurés, quatre limites sont restées. Aucune ne se corrige par un réglage : elles tiennent aux documents.

| Limite | Exemple dans le lab | Ce qui la corrige |
|---|---|---|
| **Questions d'inventaire** | « Liste les règles YAML » : 40 règles dans un chapitre de dizaines d'extraits ne tiennent dans aucun contexte. La réponse est partielle, au mieux honnête sur ce point | Un **document d'index** dans le corpus : une page qui liste les règles avec leur série et leur technique. Écrire pour le RAG ce qu'un humain chercherait dans une table des matières |
| **Entités mal retrouvées** | « Résume ce que tu sais sur les clients » : selon la formulation, la recherche classe un contrat de travail ou une politique interne devant les contrats clients, et une réponse à appel d'offres ne ressemble pas à « un client ». La fenêtre d'extraits consécutifs (§10.6) a beaucoup amélioré ces questions, sans les rendre fiables pour toutes les formulations | Une page « Clients », comme en a toute entreprise |
| **Versions contradictoires** | Deux contrats de maintenance pour le même client (24 mois et un an) : selon de petites variations de la recherche, la réponse cite l'un ou l'autre, toujours ancrée | Une seule version de chaque document dans les dossiers indexés (§17.4) |
| **Documentation qui décrit le corpus** | La section du guide sur la fiabilité, indexée, cite les contrats et les cas de test : elle concurrence les documents qu'elle décrit | Ne pas indexer les documents qui parlent des données du corpus lui-même |

Une cinquième limite relève d'un traitement à venir : **résumer un long document**. Le RAG choisit des extraits ; il ne lit pas un document de 40 pages du début à la fin. Un vrai résumé demanderait de lire le document en entier, par morceaux, puis de combiner : c'est désormais envisageable avec le GPU, et reste à construire.

> **À ce stade, la qualité d'un RAG se gagne dans les documents, plus dans les réglages.** Le GPU a apporté la vitesse ; la construction du contexte et le prompt ont apporté la fiabilité. Ce qui reste demande un corpus tenu : une version par document, des pages de synthèse là où les utilisateurs posent des questions de synthèse, et rien d'indexé qui parle du corpus lui-même.

---

## §10.11 Configuration recommandée

### Les réglages retenus

| Composant | Choix | Réglages |
|---|---|---|
| Modèle principal | `qwen3:14b`, sur la carte | `LLM_MODEL=qwen3:14b`, `LLM_NUM_CTX=16384` |
| Juge | `qwen3:4b`, sur la carte | `JUDGE_NUM_GPU` vide |
| Embedding | `nomic-embed-text`, sur la carte | `EMBED_NUM_GPU` vide |
| Synthèse Teams | Le modèle principal | `SUMMARY_MODEL` vide |
| Reranker | Désactivé | `RERANKER_URL` vide ; le service reste disponible en option |
| Contexte | Diversité des sources, document court en entier, extraits consécutifs pour les compléments | `CANDIDATS=30`, `PRINCIPAL_MAX=9`, `CONTEXT_OTHER_DOCS=6`, `EXTRAITS_PAR_COMPLEMENT=4`, `COMPLEMENT_VOISINS=1`, `DOC_COMPLET_MAX=15` |
| Fenêtres de contexte | Le juge couvre le modèle principal | `LLM_NUM_CTX=16384`, `JUDGE_NUM_CTX=16384` |
| Prompt | Règles complémentaires | `PROMPT_REGLES_V2=1` |
| Graine | Vide en usage normal ; fixée pour les mesures | `LLM_SEED` |
| Ollama | Attention économe, cache sur 8 bits, une requête à la fois, modèles gardés une heure, fonctions cloud désactivées | Variables du §10.1 |

### Mémoire système et cohabitation

Le GPU ne porte que les modèles. Tout le reste tourne en mémoire système, et un serveur d'IA se dimensionne aussi sur elle :

| Composant | Mémoire mesurée dans le lab |
|---|---|
| VM RAG complète, sans reranker | 2 à 3 Go utilisés ; la VM tourne avec 8 Go |
| Reranker `bge-reranker-v2-m3`, réglages par défaut | **9 Go**, préchauffage compris |
| Reranker bridé (`--max-batch-tokens 4096`) | 1,2 à 1,9 Go |
| Qdrant | Proportionnel aux collections chargées, y compris celles qui ne servent plus : supprimer les collections abandonnées |

Beaucoup de PME n'ont qu'un serveur, qui fait déjà tourner le contrôleur de domaine et le serveur de fichiers. Si l'IA s'installe dans une VM de cet hôte, une saturation de sa mémoire ne produit **aucun message d'erreur** : elle se manifeste dans les VM, par du swap et de la lenteur. Dans le lab, l'hôte a atteint 99 % de mémoire occupée, et la VM RAG écrivait dans son swap malgré 8 Go de mémoire libre. Pour le détecter, dans la VM :

```bash
vmstat 1 5
```

Les colonnes `si` et `so` (entrées et sorties du swap par seconde) doivent rester à 0. Si elles bougent pendant une question, la VM est ralentie par le disque. Un serveur dédié à l'IA reste préférable ; à défaut, réserver la mémoire de la VM et surveiller l'hôte.

### Checklist de mise en service sur GPU

| Vérification | Attendu |
|---|---|
| `nvidia-smi` | La carte, sa mémoire, le pilote |
| Journal d'Ollama, configuration | Attention économe, cache `q8_0`, une requête à la fois |
| Journal d'Ollama, moteur | `library=CUDA` |
| `ollama ps` après une question | Les trois modèles à `100% GPU` |
| `nvidia-smi` en charge | Mémoire sous 16 Go, température sous 83 °C |
| Réglages réellement appliqués | Lus dans le conteneur (`import main`), pas seulement dans le `.env` |
| Journal d'Ollama après une question riche | `truncated = 0` : aucune coupure du contexte, pour le modèle comme pour le juge |
| Mémoire partagée (Gestionnaire des tâches) | Quelques centaines de Mo, stable |
| Jeu de questions | Score comparable à la référence, aucun élément interdit, refus tenus |
| Test de cloisonnement | 40 sur 40, et en mode complet sur les cas Purview, écriture seule et refus explicite |
| Synthèse Teams | Durée et score sur la réunion de test |
| `vmstat` dans la VM | Pas de swap actif |

---

[Retour au sommaire](index.md) | [Section précédente : §9 Sécurité et durcissement](section-09-securite.md) | [Section suivante : §11 Prérequis Microsoft 365](section-11-prerequis-ms365.md)

*Validé en lab sur VM-RAG-LAB (Ubuntu Server, 8 Go) et LABO-G9 (Intel Core i7-14700, 64 Go, NVIDIA RTX 5060 Ti 16 Go), octobre 2026.*

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
