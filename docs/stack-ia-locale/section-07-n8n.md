---
title: "§7 Pipelines n8n | Guide de déploiement stack IA locale"
description: "Automatisation de la synchronisation du corpus, résolution ACL récurrente, notification email et rappel de rotation des comptes à privilèges."
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

# §7 Pipelines n8n

[Retour au sommaire](index.md) | [Section précédente : §6 Agent de codage](section-06-cline.md)

**Statut :** §7.1, §7.2 et §7.3 validés en lab sur VM-RAG-LAB, septembre 2026. §7.4 (résumé Teams) et §7.5 (OCR factures) sont documentaires : l'architecture est décrite mais non validée en lab, faute de tenant MS 365 avec Teams actif et de GPU pour le modèle multimodal.

---

> **Ce que cette section documente :** comment automatiser la synchronisation du corpus, la résolution des ACL NTFS et les notifications d'alerte via n8n. Trois pipelines sont validés en lab. Deux autres sont documentés comme architecture de référence pour les déploiements avec GPU et tenant Microsoft 365.

---

## §7.1 Architecture générale

n8n orchestre trois catégories de tâches dans la stack RAG :

| Catégorie | Pipeline | Déclencheur | Statut |
|---|---|---|---|
| Maintenance | Synchronisation corpus | Schedule horaire | Validé |
| Sécurité | Rappel rotation svc-rag | Schedule mensuel | Validé |
| Productivité | Résumé réunions Teams | Schedule horaire | Documentaire |
| Productivité | OCR et intégration factures | Watch folder | Documentaire |

Les pipelines de maintenance et de sécurité sont indépendants du GPU. Les pipelines de productivité nécessitent le GPU pour le modèle multimodal (OCR) et un tenant MS 365 avec Teams actif (résumé).

### §7.1.1 Accès à l'interface n8n

n8n est accessible sur `http://<IP-VM>:5678`. Identifiants définis dans le fichier `.env` :

```bash
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<mot-de-passe>
```

> **`N8N_SECURE_COOKIE=false` en lab :** n8n refuse l'accès via IP en HTTP par défaut. Cette variable désactive la restriction pour un accès en réseau local sans TLS. En production, mettre en place un reverse proxy Nginx avec TLS et retirer cette variable.

### §7.1.2 Importer un pipeline

Dans n8n : **Workflows → Import from file** → sélectionner le fichier JSON. Après import, rattacher les credentials SMTP via le nœud email, puis cliquer sur **Publish** pour activer le Schedule.

---

## §7.2 Pipeline 1 : synchronisation corpus

Ce pipeline ferme le point ouvert de §5 sur la cadence de resynchronisation des ACL. Il tourne toutes les heures et déclenche une notification email en cas d'erreur ou de fichiers en quarantaine.

### §7.2.1 Architecture

```
Schedule Trigger (toutes les heures)
    ↓
POST http://rag-api:8080/admin/sync
    Authorization: Bearer <ADMIN_TOKEN>
    ↓
Réponse JSON :
    {success, quarantine_count, quarantine[], errors[],
     indexer: {returncode, stdout}, acl_resolver: {returncode, stdout}}
    ↓
IF success=false OR quarantine_count > 0
    ↓ oui                          ↓ non
Formater email              (rien, fin du pipeline)
    ↓
Send Email → <destinataire>
```

### §7.2.2 Endpoint /admin/sync

L'endpoint est implémenté dans `main.py` de la RAG API. Il lance `indexer.py` puis `acl_resolver.py` en sous-processus et retourne un rapport JSON structuré.

```python
# Extrait de main.py - endpoint /admin/sync
@app.post("/admin/sync")
async def admin_sync(
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin invalide")
    # Lance indexer.py puis acl_resolver.py en sous-processus asyncio
    # Retourne {success, quarantine_count, quarantine[], errors[], ...}
```

Tester l'endpoint directement avant de construire le pipeline :

```bash
# Le port 8080 n'est pas publié sur le LAN (voir §3.4).
# Tester depuis le réseau Compose via le conteneur n8n :
docker compose exec n8n wget -qO- \
  --header="Authorization: Bearer <ADMIN_TOKEN>" \
  http://rag-api:8080/admin/sync
```

Résultat attendu en fonctionnement normal :

```json
{
    "timestamp": "2026-09-11T08:08:48Z",
    "indexer":     {"returncode": 0, "stdout": "...68 chunks indexés..."},
    "acl_resolver": {"returncode": 0, "stdout": "...68 chunks mis à jour..."},
    "quarantine": [],
    "errors": [],
    "success": true,
    "quarantine_count": 0
}
```

### §7.2.3 Variables requises

Dans `/root/rag-stack/.env`, ajouter :

```bash
# Synchronisation corpus
ADMIN_TOKEN=<token-admin-fort>
SYNC_SCRIPTS_DIR=/rag-pipeline
SMB_SHARE=//<NOM-FILESERVER>/FileService
SMB_MOUNT=/mnt/fileservice-root
SMB_USER=svc-rag
SMB_PASSWORD=<mot-de-passe-svc-rag>
SMB_DOMAIN=DOMAINE
```

> **Sécurité de l'endpoint `/admin/sync` :**
>
> **Injection de commande :** tous les paramètres transmis aux sous-processus (chemins, partage SMB, credentials) viennent exclusivement du fichier `.env`, jamais du corps de la requête HTTP. Un appelant ne peut pas modifier les arguments passés aux scripts.
>
> **Chevauchement de synchronisations :** un verrou global (`asyncio.Lock`) empêche deux synchronisations simultanées. Si une passe est déjà en cours, l'endpoint retourne HTTP 409. Sans ce verrou, deux appels simultanés (Schedule + appel manuel) pourraient corrompre les métadonnées Qdrant en écrivant les mêmes chunks en parallèle.
>
> **Exposition réseau :** le port 8080 n'est pas publié sur le LAN depuis la v2.4.0 (voir §3.4). `docker-compose.yml` ne comporte plus de section `ports` pour `rag-api`. Open WebUI et n8n joignent la RAG API via `http://rag-api:8080` sur le réseau Compose interne. Ne jamais publier ce port sur internet.
>
> **`ADMIN_TOKEN` distinct de `API_TOKEN` :** un token séparé permet de révoquer l'accès admin sans impacter les utilisateurs de la RAG API.

### §7.2.4 Dockerfile et volumes

> **Cette section est remplacée par §3.3 et §3.4.** Le Dockerfile, `requirements.txt` et les volumes de `rag-api` sont documentés et maintenus dans la section §3. Les rapports JSON sont écrits dans `/var/log/rag/` (monté en écriture), et `/rag-pipeline` est monté en lecture seule (`:ro`). Voir §3.4 pour la configuration complète.

### §7.2.5 Fenêtre de péremption des ACL

Entre deux passes du résolveur, un droit révoqué dans AD reste actif dans Qdrant. Avec une cadence horaire, la fenêtre maximale est d'une heure.

| Événement | Délai avant prise en compte |
|---|---|
| Nouveau fichier déposé | 0 à 60 minutes |
| Fichier modifié | 0 à 60 minutes (hash SHA-256 tronqué détecte le changement) |
| Fichier inchangé | Aucun traitement : l'indexeur compare le hash et saute le fichier |
| Permission révoquée | 0 à 60 minutes |
| Permission accordée | 0 à 60 minutes |

La cadence est configurable en modifiant l'expression cron dans le Schedule Trigger. Pour une organisation avec des révocations fréquentes, passer à 15 minutes.

### §7.2.6 Nœud IF : conditions de déclenchement

Le nœud IF déclenche l'email si l'une des deux conditions est vraie :

| Condition | Signification |
|---|---|
| `{{ $json.success }}` equals `false` | Un des deux scripts a retourné une erreur |
| `{{ $json.quarantine_count }}` greater than `0` | Des fichiers sont présents sur le partage mais absents de Qdrant |

En fonctionnement normal, le pipeline se termine silencieusement sans envoyer d'email. Une notification signale toujours une action requise.

### §7.2.7 Format des emails de notification

**Email d'erreur :**

```
RAPPORT DE SYNCHRONISATION RAG — ERREUR
Horodatage : 11.09.2026 10:08:48

Erreurs détectées :
  • indexer.py a retourné code 1

--- Détail indexeur ---
[stdout de indexer.py]

--- Détail acl_resolver ---
[stdout de acl_resolver.py]
```

**Email de quarantaine :**

```
RAPPORT DE SYNCHRONISATION RAG — QUARANTAINE
Horodatage : 11.09.2026 10:08:48
Synchronisation : succès

3 fichier(s) en quarantaine :
  • CLIENTS/ClientX/nouveau-contrat.docx
  • RH/POLITIQUE RH/reglement-2027.docx
  • ...

Ces fichiers sont présents sur le partage mais non indexés.
Action requise : vérifier le contenu et relancer l'indexation manuellement si nécessaire.
```

### §7.2.8 Validation en lab

Résultats obtenus sur le corpus Axonix SA (12 documents, 68 chunks) :

```
Exécution manuelle du workflow : success=true
indexer.py     : returncode 0, 68 chunks indexés
acl_resolver.py: returncode 0, 68 chunks mis à jour
quarantine_count: 0
Email reçu     : non (pas d'erreur, pas de quarantaine)
```

Test de déclenchement email (condition IF forcée à true) : email reçu sur `<destinataire>` avec le rapport correct.

---

## §7.3 Pipeline 2 : rappel mensuel de rotation du compte svc-rag

Ce pipeline envoie automatiquement la procédure de rotation du mot de passe de `svc-rag` le 1er de chaque mois. Il évite qu'une rotation soit oubliée et fournit les commandes exactes dans l'email.

### §7.3.1 Architecture

```
Schedule Trigger (1er du mois, 09h00)
    ↓
Code JS (formater le rappel avec date et procédure)
    ↓
Send Email → <destinataire>
```

### §7.3.2 Procédure incluse dans l'email

L'email contient la procédure complète en 7 étapes dans l'ordre exact à suivre :

1. Générer un nouveau mot de passe fort
2. Changer dans Active Directory via `Set-ADAccountPassword`
3. Mettre à jour `/etc/smbcredentials/svc-rag` sur VM-RAG-LAB
4. Mettre à jour `LDAP_BIND_PWD` et `SMB_PASSWORD` dans `.env`
5. Redémarrer la RAG API : `docker compose up -d rag-api`
6. Vérifier via `POST /admin/sync` : `success: true`
7. Tester l'authentification LDAP dans Open WebUI

> **Pourquoi l'ordre est critique :** si l'étape 2 (AD) est faite avant l'étape 3 (fichier credentials), le montage SMB tombe immédiatement. Si l'étape 5 (restart) est oubliée, la RAG API continue d'utiliser l'ancien mot de passe pour LDAP et les requêtes tombent silencieusement sans message d'erreur visible pour l'utilisateur.

### §7.3.3 Expression cron

```
0 9 1 * *
```

Heure suisse : vérifier que le conteneur n8n est en UTC et que 09h00 CET/CEST correspond à 08h00 ou 07h00 UTC selon la saison. Adapter l'expression cron en conséquence :

| Saison | Heure suisse | Expression cron (UTC) |
|---|---|---|
| Hiver (CET, UTC+1) | 09h00 | `0 8 1 * *` |
| Été (CEST, UTC+2) | 09h00 | `0 7 1 * *` |

Pour éviter ce problème, définir `TZ=Europe/Zurich` dans les variables d'environnement du conteneur n8n.

### §7.3.4 Validation en lab

Email reçu avec la procédure complète en 7 étapes. Sujet : `[RAG Stack] Rappel : rotation du mot de passe svc-rag — septembre 2026`.

---

## §7.4 Pipeline 3 : résumé de réunions Teams (documentaire)

> **Statut documentaire :** ce pipeline nécessite un tenant Microsoft 365 avec Teams actif et des droits admin Entra ID. Il sera validé en lab lors de la publication de la Partie 3 (connecteurs Microsoft 365), en même temps que le connecteur SharePoint Online.

Ce pipeline récupère les transcriptions des réunions Teams via Graph API, génère un compte-rendu structuré via le LLM local, et le dépose dans le canal Teams concerné.

### §7.4.1 Prérequis

- App Registration Entra ID avec les permissions :
  - `OnlineMeetings.Read.All` : accès aux réunions et transcriptions
  - `OnlineMeetingTranscript.Read.All` : fichiers VTT
  - `ChannelMessage.Send` : dépôt du compte-rendu dans Teams (nom exact à vérifier selon le mode application ou délégué, les permissions Graph pour l'envoi dans un canal sont plus restrictives que la lecture)
- Transcription automatique activée par un admin Teams : **Centre d'administration Teams → Réunions → Stratégies de réunion → Transcription → Activer**
- Attendre la propagation de la stratégie (jusqu'à 24h)

> **Contrainte nLPD :** les transcriptions Teams sont stockées dans le datacenter du tenant MS 365. Si le tenant n'est pas hébergé en Suisse, les transcriptions transitent hors juridiction avant d'arriver dans le pipeline local. La qualité du résumé dépend directement de la qualité de la transcription Teams automatique.

### §7.4.2 Architecture du pipeline

```
Schedule Trigger (toutes les heures)
    ↓
HTTP Request → GET Graph API /me/onlineMeetings
    Filter: réunions des 2 dernières heures
    ↓
Loop → pour chaque réunion
    ↓
HTTP Request → GET transcription VTT
    GET /me/onlineMeetings/{meetingId}/transcripts/{transcriptId}/content
    ↓
HTTP Request → POST LLM local (Ollama ou vLLM)
    Prompt de structuration : participants, décisions, actions, points ouverts
    ↓
HTTP Request → POST canal Teams
    POST /teams/{teamId}/channels/{channelId}/messages
```

### §7.4.3 Modèle recommandé

Qwen3 14B ou 30B-A3B pour la qualité de structuration. Sur CPU LABO-G9, la génération d'un compte-rendu de réunion de 30 minutes prend environ 5 à 10 minutes. Avec le GPU RTX 5060 Ti, la latence descend à 15 à 30 secondes.

---

## §7.5 Pipeline 4 : OCR et intégration de factures (documentaire)

> **Statut documentaire :** ce pipeline nécessite Qwen2-VL 7B (modèle multimodal) et sera validé lors de l'installation du GPU RTX 5060 Ti. Il sera documenté dans §10 avec les mesures de performance réelles.

Ce pipeline surveille un dossier de réception de factures, extrait les données structurées via le modèle multimodal et les envoie à l'ERP.

### §7.5.1 Architecture du pipeline

```
Watch Folder → /mnt/fileservice-root/FACTURES/entrant (polling 5 min)
    ↓
HTTP Request → POST vLLM /v1/chat/completions
    Model: Qwen2-VL-7B (multimodal)
    Message: image PDF + prompt extraction JSON
    ↓
Code Node → validation et mapping vers format ERP
    ↓
HTTP Request → POST endpoint ERP (API Abacus ou équivalent)
    ↓
IF anomalie détectée
    ↓
Email → notification validation manuelle requise
```

### §7.5.2 Prompt d'extraction

```
Tu reçois l'image d'une facture. Extrais les données suivantes
au format JSON strict, sans commentaire :
{
  "fournisseur": "...",
  "numero_facture": "...",
  "date_facture": "JJ.MM.AAAA",
  "montant_ht": 0.00,
  "montant_tva": 0.00,
  "montant_ttc": 0.00,
  "devise": "CHF",
  "iban": "...",
  "lignes": [
    {"description": "...", "quantite": 0, "prix_unitaire": 0.00}
  ]
}
Si un champ est absent de la facture, mettre null.
```

> **Fiabilité :** 85 à 95% sur un corpus de factures homogènes, selon des déploiements documentés publiquement (chiffre repris du guide décisionnel §2.1, non mesuré sur ce lab). Les cas ambigus sont signalés pour validation manuelle. La vérification humaine reste recommandée avant envoi à l'ERP.

---

## §7.6 Configuration SMTP

Les pipelines §7.2 et §7.3 utilisent le même credential SMTP. Le nœud email n8n supporte STARTTLS sur le port 587 (Office 365).

| Paramètre | Valeur |
|---|---|
| Host | smtp.office365.com |
| Port | 587 |
| SSL/TLS | Désactivé (STARTTLS sur 587) |
| User | `<compte-envoi>@domaine.ch` |
| Password | Mot de passe d'application |

> **Dépréciation SMTP AUTH :** Microsoft supprime progressivement SMTP AUTH et les mots de passe d'application sur Exchange Online. La date de suppression définitive n'est pas encore annoncée officiellement, mais la migration vers OAuth2 + Graph API est à planifier. Le nœud n8n "Microsoft Outlook" ou un HTTP Request vers `https://graph.microsoft.com/v1.0/me/sendMail` avec un token OAuth2 est la solution de remplacement. Cette migration sera documentée en Partie 3 avec les connecteurs Microsoft 365.

---

[Suite : §8 Fiabilité : hallucinations et contrôle d'ancrage](section-08-fiabilite.md)

---

*§7.1, §7.2 et §7.3 validés en lab sur VM-RAG-LAB, septembre 2026. §7.4 et §7.5 sont des architectures de référence non validées en lab.*
