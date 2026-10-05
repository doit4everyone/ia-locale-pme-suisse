---
title: "§17 Gouvernance | Guide de déploiement stack IA locale"
description: "Gouvernance d'un RAG d'entreprise : qui est responsable de quoi, rotation des secrets et des certificats, politique de corpus, droit à l'effacement, audit périodique, et ce que la nLPD exige au-delà de la technique."
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

# §17 Gouvernance

[Retour au sommaire](index.md) | [Section précédente : §16 Contrôle du cloisonnement et durcissement](section-16-cloisonnement.md)

---

> **Ce que cette section documente :** les sections précédentes installent et sécurisent la stack. Celle-ci porte sur ce qui la maintient digne de confiance dans le temps : qui est responsable de quoi, ce qui doit être renouvelé et à quelle échéance, ce qu'on indexe et ce qu'on refuse d'indexer, comment répondre à une demande d'effacement, et ce que la nLPD attend au-delà de la technique. Un RAG qui n'est pas gouverné se dégrade : les permissions dérivent, les certificats expirent, le corpus se périme, et les utilisateurs l'abandonnent ou, pire, lui font confiance à tort.

---

## §17.1 La conformité nLPD ne se déduit pas de la technique

Cette stack est **conçue pour faciliter la conformité à la nLPD**. Elle ne la garantit pas, et aucun logiciel ne le peut. La nLPD encadre un **traitement** de données personnelles, mené par un **responsable** : l'entreprise. La loi lui impose des obligations qu'aucun outil ne remplit à sa place.

| Obligation nLPD | Ce que la stack apporte | Ce qui reste au responsable |
|---|---|---|
| Finalité et proportionnalité (art. 6) | Rien en soi | Décider pourquoi on indexe tel corpus, et si c'est proportionné |
| Protection dès la conception et par défaut (art. 7) | Cloisonnement, refus par défaut, chiffrement | Choisir le périmètre, et le tenir à jour |
| Sécurité des données (art. 8) | ACL, chiffrement au repos, journalisation, local | Les mesures organisationnelles de cette section |
| Devoir d'informer (art. 19) | Rien | Informer les collaborateurs que leurs documents sont traités par une IA |
| Analyse d'impact (art. 22) | Rien | La réaliser lorsque le risque est élevé, ce qui est plausible pour des données RH |
| Droit d'accès (art. 25) et demandes d'effacement | Journal et synchronisation aident | Les procédures pour y répondre (§17.5) |
| Annonce des violations (art. 24) | Journal aide à reconstituer | La procédure d'annonce au PFPDT |

> **À dire à un client, pas l'inverse.** Présenter cette stack comme « conforme nLPD » exposerait l'auteur de cette affirmation : en cas de litige, elle se lirait comme une garantie. La formulation juste est « socle technique facilitant un traitement conforme », la conformité restant la responsabilité de l'organisation. Ce guide n'est pas un avis juridique ; une analyse par un juriste est recommandée dès que des données sensibles sont traitées.

## §17.2 Qui est responsable de quoi

Un RAG d'entreprise touche l'IT, la sécurité, les métiers et la direction. Sans attribution claire, chaque incident cherche un responsable qui n'existe pas. Cette matrice est un point de départ, à adapter à la taille de l'organisation ; dans une petite PME, une même personne peut tenir plusieurs rôles, mais aucun ne doit rester vacant.

| Action | Responsable type |
|---|---|
| Définir la finalité et le périmètre du corpus | Direction, avec les métiers |
| Décider quels dossiers sont indexés ou exclus (§17.4) | Propriétaires des données métier |
| Maintenir les permissions du serveur de fichiers et de SharePoint | IT, administration des droits |
| Exploiter la stack (synchronisation, mises à jour, sauvegardes) | IT, ou prestataire sous contrat |
| Renouveler les secrets et les certificats (§17.3) | IT |
| Lire les alertes de cloisonnement et de quarantaine | IT, avec escalade définie |
| Répondre aux demandes d'accès et d'effacement (§17.5) | Référent protection des données |
| Lire les journaux d'accès, conduire l'audit (§17.6) | Sécurité, ou référent désigné |
| Former les utilisateurs | IT, avec les métiers |

> **Sans responsable du corpus, le RAG se périme.** C'est la défaillance la plus fréquente : la technique fonctionne, mais personne n'est chargé de retirer les documents obsolètes ni d'ajouter les nouveaux. Les réponses deviennent fausses sans que rien ne le signale, et la confiance s'effondre. Nommer ce responsable avant le déploiement, pas après.

## §17.3 Rotation des secrets et des certificats

La stack repose sur des secrets et des certificats qui ont tous une durée de vie. Un secret jamais renouvelé finit par être connu de trop de monde ; un certificat expiré coupe le service sans prévenir. Chacun doit avoir une échéance et un responsable.

| Élément | Où | Échéance conseillée | Effet à l'expiration |
|---|---|---|---|
| Mot de passe de `svc-rag` | AD (§5.2.4) | Selon la politique de l'organisation | L'indexation SMB échoue |
| Certificats des applications Entra (identité, Teams, SharePoint, Purview) | Entra ID, `/etc/rag-certs` | 2 ans, alerte à J-30 | La fonction concernée échoue (§11.5.2) |
| `ADMIN_TOKEN`, `API_TOKEN` | `.env` | À chaque départ d'un administrateur, et périodiquement | n8n et les appels d'administration échouent (401) |
| `QDRANT_API_KEY`, `MIP_TOKEN`, `LOG_HMAC_KEY` | `.env` | Périodiquement | Service interrompu jusqu'au report de la nouvelle valeur |

Après toute modification du `.env`, recréer les conteneurs (`docker compose up -d`, et non `restart`, voir §15.3.6). Le jeton d'administration se renouvelle en un seul endroit grâce à l'identifiant n8n (§16.7).

Les certificats Entra sont le point le plus facile à oublier, parce qu'ils ne gênent personne jusqu'au jour de l'expiration, deux ans plus tard. Un rappel planifié vaut mieux que la mémoire : le dépôt fournit un workflow n8n de rappel mensuel pour `svc-rag`, à décliner pour chaque certificat avec sa date d'échéance.

Pour relever les échéances, sur le poste d'administration (module `Microsoft.Graph.Applications`, chargé avant `Connect-MgGraph -Scopes "Application.Read.All"` dans une session neuve, comme en §14.4.3) :

```powershell
foreach ($nom in "RAG-Identity-Resolver","RAG-Teams-Reader","RAG-SharePoint-Indexer","RAG-Purview-Decrypt") {
    $app = Get-MgApplication -Filter "displayName eq '$nom'"
    foreach ($c in $app.KeyCredentials) {
        [pscustomobject]@{ Application = $nom; Expire = $c.EndDateTime }
    }
}
```

Adapter les noms à ceux des applications réellement créées.

## §17.4 Politique de corpus : ce qu'on indexe, ce qu'on refuse

Le réflexe le plus coûteux est d'indexer « tout le serveur de fichiers ». Un RAG rend **trouvable** ce qui n'était que rangé dans une arborescence : un document mal classé, une copie oubliée, un export de données personnelles deviennent interrogeables en langage naturel par toute personne qui y a accès. La bonne question n'est pas « que peut-on indexer », mais « qu'a-t-on besoin d'indexer ».

Recommandations :
- **désigner explicitement les dossiers indexés**, plutôt que d'indexer une racine entière. Le périmètre de l'indexation est l'ensemble des dossiers où le groupe d'indexation a la lecture (§5.2.4) : c'est un choix, pas un défaut ;
- **exclure par principe** les dossiers personnels, les sauvegardes, les exports, les archives, et les données sensibles dont l'intérêt d'être interrogées par une IA ne justifie pas le risque. Pour les données RH, la recommandation du guide est de **ne pas les indexer** en production (§14) ;
- **avant la première indexation d'un dossier, le faire relire par son propriétaire métier** : lui seul sait s'il contient des documents qui n'ont rien à faire dans un index ;
- **écarter les secrets techniques** : clés, fichiers de configuration, exports de mots de passe n'ont pas leur place dans un corpus documentaire. Un contrôle avant indexation réduit le risque, sans le supprimer : la vraie protection est de ne pas les ranger dans les dossiers indexés.

- **une seule version de chaque document** dans les dossiers indexés : archiver les versions périmées hors de l'index. Un RAG ne sait pas quelle version fait foi, et peut citer l'une ou l'autre selon de petites variations de la recherche.

> **Illustré en lab.** Le corpus contenait deux contrats de maintenance pour le même client, l'un de 24 mois, l'autre d'un an, sur deux emplacements différents. Après un réglage de la recherche (§8.9), la même question a cité l'un puis l'autre : deux réponses ancrées, mais contradictoires.

> **Illustré en lab.** Le serveur de fichiers de démonstration contenait un fichier nommé comme une clé TLS et des copies en clair de documents par ailleurs chiffrés. Ni l'un ni l'autre n'avait à être indexé. C'est le genre de résidu qu'un serveur ayant servi à des essais accumule, et qu'une politique de corpus écrite permet d'écarter avant qu'une IA ne le rende trouvable.

## §17.5 Droit d'accès et droit à l'effacement

La nLPD donne à toute personne le droit de savoir quelles données la concernant sont traitées, et d'en demander l'effacement. Pour un RAG, cela se décline en deux questions concrètes.

**« Quels documents me concernant sont indexés ? »** Le RAG indexe des documents, pas des personnes : il n'y a pas d'index par personne. La réponse se construit à partir de la gestion documentaire de l'organisation (où sont rangés les documents concernant cette personne), le RAG n'indexant que ce que le serveur de fichiers contient déjà.

**« Supprimez les documents me concernant. »** La suppression se fait **à la source**, sur le serveur de fichiers ou SharePoint, jamais directement dans l'index. À la synchronisation suivante, l'indexeur constate l'absence du document et retire ses chunks de Qdrant. La chaîne à vérifier :

```
document supprimé à la source
        ↓ (synchronisation suivante)
chunks retirés de Qdrant
        ↓ (reconstruction en fin de synchronisation)
index BM25 régénéré sans le document
        ↓
sauvegardes : le document disparaît des sauvegardes postérieures,
              reste dans les sauvegardes antérieures jusqu'à leur péremption
```

Le dernier maillon est important pour une réponse honnête : une suppression n'efface pas rétroactivement les sauvegardes déjà prises. La politique de rétention des sauvegardes (§15.5) doit être cohérente avec les engagements d'effacement de l'organisation.

Pour vérifier qu'un document a bien disparu de l'index après sa suppression :

```bash
CLE=$(grep '^QDRANT_API_KEY=' /root/rag-stack/.env | cut -d= -f2-)
curl -s -X POST http://localhost:6333/collections/documents/points/count \
  -H "api-key: $CLE" -H 'Content-Type: application/json' \
  -d '{"filter":{"must":[{"key":"source","match":{"value":"<chemin du document>"}}]}}'
# attendu après synchronisation : {"result":{"count":0}}
```

## §17.6 Audit périodique

La journalisation (§9.4) enregistre qui a interrogé le RAG et quels documents ont été consultés. Elle n'a de valeur que si quelqu'un la relit, et si les permissions qu'elle reflète sont vérifiées.

| Contrôle | Fréquence conseillée | Outil |
|---|---|---|
| Les permissions dans Qdrant reflètent toujours celles de la source | À chaque synchronisation | Contrôle de cloisonnement automatique (§16.4) |
| Aucune application inattendue ne détient de droit de déchiffrement | Trimestrielle | Audit `Content.SuperUser` (§14.4.3) |
| Les droits du partage ne sont pas plus restrictifs que les NTFS | À chaque revue des droits | `Set-AccesIndexationRAG.ps1 -Verifier` (§16.5) |
| Les appartenances du compte d'indexation se limitent à son groupe dédié | Trimestrielle | Revue AD (§5.2.4) |
| Les certificats et secrets approchant de l'échéance | Mensuelle | §17.3 |
| Lecture des journaux d'accès : rien d'anormal | Selon le secteur | `/var/log/rag/rag-queries.jsonl` |
| Qualité des réponses sur un jeu de questions de référence | Périodique | À définir au §10 |

> **Un audit utile est un audit qui change quelque chose.** Relever qu'une application détient un droit de déchiffrement injustifié, qu'un compte a gardé une appartenance obsolète, ou qu'un certificat expire dans trois semaines n'a d'intérêt que si une action suit. Chaque contrôle de ce tableau doit avoir un responsable (§17.2) et une suite définie en cas d'anomalie.

## §17.7 Ce qui relève du passage en production

Ce guide documente un **lab** validé, pas une exploitation en entreprise. Plusieurs exigences de production dépassent son périmètre et feront l'objet d'une section « Du lab à la production » :

- images Docker figées par version et empreinte, dépendances verrouillées, intégration continue, inventaire des composants et analyse des vulnérabilités ;
- réseau segmenté, reverse proxy TLS devant Open WebUI et n8n, identité signée entre Open WebUI et la RAG API (§16, point 44) ;
- refus de démarrer sur une valeur d'exemple ou une clé d'empreinte absente, plutôt qu'un avertissement ;
- sauvegardes chiffrées automatisées, avec restauration testée (§15.5) ;
- supervision et alertes depuis un point extérieur à la stack ;
- haute disponibilité si la continuité de service l'exige.

Les mentionner ici évite de laisser croire qu'un lab validé est prêt pour la production. Le passage de l'un à l'autre est un projet en soi.

## §17.8 Checklist

| Point | Vérifié |
|---|---|
| Finalité et périmètre du corpus définis et écrits | |
| Collaborateurs informés du traitement par une IA | |
| Analyse d'impact réalisée si le risque est élevé | |
| Chaque rôle de §17.2 attribué à une personne nommée | |
| Responsable du corpus désigné | |
| Échéances des certificats et secrets planifiées, avec rappels | |
| Dossiers indexés désignés explicitement, dossiers sensibles exclus | |
| Procédure d'effacement documentée, chaîne jusqu'aux sauvegardes comprise | |
| Calendrier d'audit établi, chaque contrôle avec un responsable | |
| Politique de rétention des journaux et des sauvegardes définie | |
| Formulation « facilite la conformité », jamais « conforme » | |

---

[Retour au sommaire](index.md) | [Section précédente : §16 Contrôle du cloisonnement et durcissement](section-16-cloisonnement.md)

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
