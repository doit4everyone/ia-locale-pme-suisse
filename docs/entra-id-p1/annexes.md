---
title: "Entra ID P1 : Annexes MVC nLPD"
description: "Annexes du guide Entra ID P1 : glossaire, checklist complète, références nLPD, récapitulatif des politiques d'accès conditionnel, adaptations sectorielles, différences POC et production."
lang: fr
---
<style>
  header, footer { display: none !important; }
  .wrapper {
    max-width: 900px !important;
    margin: 0 auto !important;
    float: none !important;
    position: relative !important;
    padding: 40px 20px !important;
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important;
    font-size: 1.1em !important;
  }
  section {
    width: 100% !important;
    float: none !important;
    margin: 0 !important;
  }
  h1, h2 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
</style>

<h1>Entra ID P1 : Annexes</h1>
<h2>MVC nLPD · Identité et accès · v3.5</h2>

> [← Retour au guide Entra ID P1](index.html) · [← Procédure de déploiement](procedure-deploiement.html)

## Sommaire

- [Annexe A : Glossaire](#annexe-a)
- [Annexe B : Checklist MVC complète avec références nLPD](#annexe-b)
- [Annexe C : Références nLPD, mesures techniques couvertes](#annexe-c)
- [Annexe D : Tableau récapitulatif des politiques CA](#annexe-d)
- [Annexe E : Adaptations sectorielles](#annexe-e)
- [Annexe F : Différences POC et production](#annexe-f)

---

## Annexe A : Glossaire {#annexe-a}

| Terme | Définition |
|-------|------------|
| **AiTM (Adversary-in-the-Middle)** | Attaque interceptant la session après un MFA réussi en volant le cookie de session. Token Protection (CA-04) bloque cette attaque. Voir l'[annexe AiTM](../aitm-cookie-hijacking/index.html). |
| **Authentication Strength** | Fonctionnalité CA P1 définissant le niveau minimal de méthode d'authentification requis. 3 niveaux intégrés : Authentification multifacteur, Authentification multifacteur sans mot de passe, MFA anti-hameçonnage. |
| **Break-glass** | Comptes admin d'urgence exclus de toutes les politiques CA. Utilisés uniquement si le tenant est verrouillé. Deux comptes recommandés avec des méthodes différentes. Doivent avoir FIDO2 ou CBA enregistré (MFA des portails admin obligatoire depuis 2025). Noms neutres recommandés en production. |
| **CAE (Continuous Access Evaluation)** | Révocation des sessions M365 en temps réel si un changement est détecté (désactivation de compte, IP suspecte). |
| **Credential stuffing** | Attaque automatisée testant des millions de paires identifiant/mot de passe volés sur d'autres services. |
| **Contrôles personnalisés / MFA externe** | Les « Contrôles personnalisés » CA (MFA tiers) sont remplacés par MFA externe (External MFA). Depuis septembre 2026, il n'est plus possible d'ajouter ou de modifier des contrôles personnalisés ; le retrait complet est prévu début 2027 (source : documentation Microsoft Learn). Non utilisés dans le MVC : à vérifier si le client a un fournisseur MFA tiers. |
| **Emplacement nommé** | Zone géographique (pays) ou plage IP définie dans Entra ID, utilisée comme condition dans les politiques CA. |
| **Entra Connect / Cloud Sync** | Outil de synchronisation entre l'Active Directory local et Entra ID. Requis en environnement hybride. Microsoft encourage Entra Cloud Sync (agent léger cloud-natif). Pour Entra Connect Sync, la version 2.6.84.0 ou supérieure avec l'authentification basée sur une application est obligatoire avant le 7 avril 2027, sans quoi la synchronisation s'arrête (échéance précédemment annoncée au 30 septembre 2026, avec la version 2.5.79.0, puis repoussée). |
| **FIDO2 / Passkey** | Standard cryptographique pour l'authentification sans mot de passe. Résistant au phishing car lié à l'URL de destination. |
| **MFA** | Multi-Factor Authentication. Exige deux facteurs : mot de passe + téléphone (ou biométrie). |
| **Mode Rapport uniquement** | Les politiques CA sont évaluées mais n'appliquent aucun contrôle. Permet de tester l'impact avant activation. |
| **PFPDT** | Préposé fédéral à la protection des données et à la transparence, autorité de contrôle suisse. |
| **SSPR** | Self-Service Password Reset. Réinitialisation autonome et auditée du mot de passe sans helpdesk. |
| **TAP (Temporary Access Pass, « Passe d'accès temporaire »)** | Code temporaire à usage unique pour enregistrer le premier facteur MFA lors de l'onboarding. |
| **Token Protection** | Fonctionnalité CA P1 liant les jetons de session à l'appareil émetteur. Réduit le risque de rejeu de jetons volés sur les plateformes et applications compatibles. |

---

## Annexe B : Checklist MVC complète avec références nLPD {#annexe-b}

### Prérequis

| ☐ | Action | Portail / Chemin | nLPD |
|---|--------|------------------|------|
| ☐ | Deux comptes break-glass créés (bga1 + bga2), Administrateur général permanent, FIDO2 | entra.microsoft.com → Utilisateurs | |
| ☐ | Alerte sur toute connexion break-glass en place, test tous les 90 jours | Azure Monitor, SIEM ou revue des journaux | |
| ☐ | Groupe `GRP-CA-BreakGlass` créé | entra.microsoft.com → Groupes | |
| ☐ | Security Defaults désactivé | entra.microsoft.com → Propriétés → Paramètres de sécurité | |

### Méthodes d'authentification

| ☐ | Action | Portail / Chemin | nLPD |
|---|--------|------------------|------|
| ☐ | Authenticator activé, tous les utilisateurs | Entra ID → Méthodes d'auth → Authenticator | art. 8 |
| ☐ | FIDO2/Passkeys activé : liés à l'appareil (Authenticator, clés physiques) ; synchronisés non autorisés pour les administrateurs | Entra ID → Méthodes d'auth → Passkey | art. 8 |
| ☐ | SMS : optionnel et transitoire | Entra ID → Méthodes d'auth → SMS | |
| ☐ | Passe d'accès temporaire activée, usage unique, 1 heure par défaut | Entra ID → Méthodes d'auth → Passe d'accès temporaire | |
| ☐ | Campagne d'inscription active (tous les utilisateurs, sauf break-glass) | Entra ID → Méthodes d'auth → Campagne d'inscription | |
| ☐ | MFA per-user legacy vérifié (tous en Désactivé) | admin.microsoft.com → Utilisateurs actifs → MFA | |

### Emplacements nommés

| ☐ | Action | Portail / Chemin | nLPD |
|---|--------|------------------|------|
| ☐ | Emplacement `Pays-Autorises-[Client]` créé (CH + pays voisins) | CA → Emplacements nommés | art. 8 |
| ☐ | Emplacement `Bureau-[Client]` créé si IP fixe disponible (optionnel, non référencé par les politiques) | CA → Emplacements nommés | |

### Politiques d'accès conditionnel

| ☐ | Action | Portail / Chemin | nLPD |
|---|--------|------------------|------|
| ☐ | CA-01 MFA tous utilisateurs : Application (après 7 j de rapport) | CA → Stratégies → CA-01 | art. 8 |
| ☐ | CA-02 Blocage auth héritée : Application (après 7 à 14 j de rapport et inventaire) | CA → Stratégies → CA-02 | art. 8 |
| ☐ | CA-09 MFA anti-hameçonnage administrateurs : Application (après 7 j de rapport et clés d'accès enregistrées) | CA → Stratégies → CA-09 | art. 8 |
| ☐ | CA-03 Filtrage géographique : Application (après 14 j de rapport) | CA → Stratégies → CA-03 | art. 8 |
| ☐ | CA-04 Token Protection : Rapport uniquement (Application après MVC Intune) | CA → Stratégies → CA-04 | art. 8 |
| ☐ | CA-05 Session limitée : Application | CA → Stratégies → CA-05 | art. 8 |
| ☐ | Prérequis CA-05 : SharePoint Admin → accès limité au web actif | admin.sharepoint.com → Stratégies → Contrôle d'accès → Appareils non gérés | art. 8 |
| ☐ | CA-06 Hors horaires (expérimental, optionnel) : Rapport uniquement | CA → Stratégies → CA-06 | art. 8 |
| ☐ | CA-08 Appareil conforme : Rapport uniquement (Application après MVC Intune) | CA → Stratégies → CA-08 | art. 8 |

### SSPR

| ☐ | Action | Portail / Chemin | nLPD |
|---|--------|------------------|------|
| ☐ | SSPR activé pour `GRP-SSPR-Utilisateurs` | Entra ID → Réinit. MDP → Propriétés | art. 8 |
| ☐ | 2 méthodes configurées (Authenticator, E-mail ; téléphone transitoire, retrait SMS et voix Microsoft : 1er février 2027 pour les utilisateurs standards, 1er juillet 2027 pour les administrateurs généraux et externes, avec transition SSPR de 50 jours) | Entra ID → Réinit. MDP → Méthodes | art. 8 |
| ☐ | Notifications utilisateur + admin activées | Entra ID → Réinit. MDP → Notifications | art. 8 |
| ☐ | Écriture différée activée (si environnement hybride) | Entra ID → Réinit. MDP → Intégration locale | art. 8 |

### Tests et validation

| ☐ | Action | Portail / Chemin | nLPD |
|---|--------|------------------|------|
| ☐ | T1 MFA déclenché sur compte utilisateur standard | Navigation privée → connexion | |
| ☐ | T2 Break-glass non bloqué par CA-01 | Connexion bga1 et bga2 | |
| ☐ | T3 Auth héritée bloquée (CA-02) | Client IMAP ou Outlook ancien | |
| ☐ | T4 Pays bloqué (CA-03) | VPN | |
| ☐ | T5 Session limitée SharePoint (CA-05) | Appareil non géré → SharePoint | |
| ☐ | T6 SSPR fonctionnel | https://aka.ms/sspr | |
| ☐ | T7 Journaux de connexion, colonnes CA visibles | entra.microsoft.com → Surveillance | |
| ☐ | T8 à T10 en Rapport (CA-04, CA-08, CA-06) ; T11 (CA-09) en Rapport puis en Application | Journaux de connexion | |

---

## Annexe C : Références nLPD, mesures techniques couvertes {#annexe-c}

Ce tableau peut être utilisé comme pièce justificative lors d'un audit PFPDT. Référence : **nLPD RS 235.1**, en vigueur depuis le 1er septembre 2023. Délai de notification d'une violation : **« dès que possible »** (pas 72 heures comme dans le RGPD européen). Autorité : **PFPDT** (pas la CNIL). Amende maximale : 250'000 CHF (personne physique).

| Article nLPD | Obligation | Mesure technique déployée | Section |
|--------------|------------|---------------------------|---------|
| **art. 8 al. 1** | Mesures techniques adaptées au risque : contrôle des accès | MFA obligatoire via CA-01 (Authentication Strength niveau 1) | Partie 3 |
| **art. 8 al. 1** | Fermer les vecteurs de contournement | Blocage authentification héritée (IMAP, POP3, SMTP) via CA-02 | Partie 4 |
| **art. 8 al. 1** | Réduction de la surface d'attaque géographique | Filtrage géographique : restrictions géographiques définies par l'entreprise via CA-03 | Partie 5 |
| **art. 8 al. 1** | Réduction du risque de rejeu de jetons de session | Token Protection (plateformes et applications compatibles) via CA-04 | Partie 6 |
| **art. 8 al. 1** | Contrôle des accès depuis appareils non gérés | Session restreinte SharePoint/OneDrive via CA-05 | Partie 7 |
| **art. 8 al. 1** | Détection des connexions inhabituelles (mesure complémentaire expérimentale) | Signalement des connexions hors horaires via CA-06 (Rapport) | Partie 8 |
| **art. 8 al. 1** | Protection des comptes à privilèges | MFA anti-hameçonnage pour les administrateurs via CA-09 | §3.2 |
| **art. 8 al. 1** | Contrôle d'accès par état de sécurité de l'appareil | CA-08 Exiger un appareil conforme (Rapport, puis Application après MVC Intune) | Partie 9 |
| **art. 8 al. 1** | Sécurité et traçabilité des opérations de gestion des identités | SSPR : réinitialisation auditée, 2 méthodes requises (le SSPR et ses journaux y contribuent, sans que la loi les prescrive nommément) | Partie 10 |
| **art. 8 al. 1** | Authentification forte : résistance au phishing | FIDO2/Passkeys + Authentication Strength | Partie 1 |
| **art. 8 al. 1** | Continuité d'accès sécurisée | Deux comptes break-glass (FIDO2, Administrateur général permanent, alerte de connexion) | §0.2 |
| **art. 8 al. 2** | Éviter les violations de la sécurité des données (la loi ne prescrit pas de mesure nommée) | CAE (Continuous Access Evaluation) contribue à cette finalité : révocation en temps réel | Partie 3 (natif) |
| **art. 24** | Annonce des violations de la sécurité des données au PFPDT (et aux personnes concernées si nécessaire) | Les journaux de connexion Entra ID et les alertes du SIEM (par exemple règles UTMStack M14 et M3) facilitent la détection et la documentation d'un incident, mais l'obligation d'annonce reste organisationnelle | Parties 0, 8 et 11 (T7) |

---

## Annexe D : Tableau récapitulatif des politiques CA {#annexe-d}

| Politique | Lic. | Cible | Condition | Action |
|-----------|------|-------|-----------|--------|
| **CA-01-MFA-Tous-Utilisateurs** | P1 | Tous (sauf BG) | Toutes ressources | MFA niveau 1 |
| **CA-02-Blocage-Auth-Heritee** | P1 | Tous (sauf BG) | Auth héritée | Bloquer |
| **CA-03-Blocage-Pays-Non-Autorises** | P1 | Tous (sauf BG) | Hors pays autorisés | Bloquer |
| **CA-04-Token-Protection-Windows** | P1 | Pilote Direction + admins (sauf BG) | Exchange + SharePoint + Teams, Windows, applications natives | Session liée à l'appareil |
| **CA-05-Session-Limitee** | P1 | Tous | SPO + appareils non gérés | Accès web uniquement |
| **CA-06-Hors-Horaires-Experimental** | P1 | Tous (sauf BG) | Hors heures ouvrables (via Graph beta, expérimental) | Rapport uniquement ; blocage optionnel |
| **CA-08-Exiger-Appareil-Conforme** | P1 | Tous (sauf BG) | Toutes ressources | Appareil conforme |
| **CA-09-MFA-Phishing-Resistant-Administrateurs** | P1 | Rôles d'administration (sauf BG) | Toutes ressources | MFA anti-hameçonnage |

> **ℹ️ INFO** : CA-04 et CA-08 restent en mode Rapport uniquement jusqu'au déploiement du MVC Intune + Defender. C'est dans le guide Intune + Defender qu'ils passent en Application. CA-06 est créée en mode Rapport ; son passage en Application est une décision du client après revue des journaux. Il n'existe pas de politique CA-07 dans le MVC.

---

## Annexe E : Adaptations sectorielles {#annexe-e}

Les adaptations ci-dessous s'appliquent en supplément du MVC standard. Le reste du guide reste valide sans modification.

| Secteur | Point de rupture | Adaptation recommandée |
|---------|------------------|------------------------|
| **PME générique** | Aucun | MVC tel quel. Aucune adaptation requise. |
| **Fiduciaire itinérante** | Connexions depuis les bureaux de clients (IP variables) | CA-03 : remplacer Bloquer par Exiger MFA. Les connexions hors Suisse sont autorisées après MFA. |
| **Cabinet médical / Avocats** | Confidentialité maximale exigée | CA-04 Token Protection : priorité haute, à déployer dès que Intune est actif. CA-01 : Authentication Strength niveau 2 (sans mot de passe) plutôt que niveau 1. |
| **Agence de communication (nomades)** | Collaborateurs en télétravail depuis l'étranger | CA-03 : mode MFA plutôt que blocage. Ajouter les pays de télétravail habituels à `Pays-Autorises-[Client]`. |
| **Architecture / Ingénierie** | Chantiers en Suisse et pays voisins | Vérifier que CH + DE + FR + IT sont dans `Pays-Autorises-[Client]`. Aucune autre adaptation requise. |

---

## Annexe F : Différences POC et production {#annexe-f}

| Point | POC (test) | Production (recommandé) |
|-------|------------|-------------------------|
| **Comptes break-glass** | 1 compte admin testé | 2 comptes cloud-only, FIDO2, Administrateur général permanent, alerte de connexion |
| **Méthodes MFA** | Authenticator + SMS | Authenticator (priorité) + FIDO2 pour Direction et admins |
| **CA-01 mode** | Rapport 7 jours puis Application | Application après validation sur un groupe pilote |
| **CA-03 mode** | Rapport 14 jours puis Application | Application après revue des journaux de connexion |
| **CA-04 Token Protection** | Rapport (Intune non déployé) | Application après déploiement MVC Intune + Defender |
| **SSPR écriture différée** | Optionnelle (cloud-only) | Obligatoire en environnement hybride AD |
| **Test break-glass** | Manuel lors du déploiement | Tous les 90 jours et à chaque changement de personnel, documenté dans le registre de sécurité |
| **Alertes connexions suspectes** | Vérification manuelle hebdomadaire | Alertes automatisées (SIEM, MDCA ou Sentinel) |

---

[🏠 Retour au portail principal](https://doit4everyone.github.io/)

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
