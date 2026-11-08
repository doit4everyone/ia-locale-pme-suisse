---
title: "Entra ID P1 : Identité et accès, MVC nLPD"
description: "Guide Entra ID P1 pour PME suisses de 5 à 25 utilisateurs sur Microsoft 365 Business Premium : comptes break-glass, MFA, accès conditionnel, SSPR. Mesures techniques nLPD art. 8."
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

<h1>Entra ID P1 : Identité et accès</h1>
<h2>Minimum Viable de Conformité · nLPD RS 235.1 · v3.5</h2>

> [← Retour au bundle MVC nLPD](../index.html)

Ce guide déploie la couche **identité et accès** du bundle : comptes de secours, authentification multifacteur, accès conditionnel et réinitialisation de mot de passe en libre-service. La nLPD art. 8 exige des mesures techniques adaptées au risque, et le contrôle des identités en est la première : un mot de passe volé contourne tous les autres contrôles.

| | |
|---|---|
| **Licence** | Microsoft 365 Business Premium (Entra ID P1 inclus) |
| **Portail** | `entra.microsoft.com` |
| **Durée** | 2 à 3 heures de travail technique (hors périodes en mode Rapport de 7 à 14 jours) |
| **Prérequis** | Aucun pour l'étape 0 (Parties 0 à 3). Suite du guide (Parties 4 à 10) après le MVC Purview (ou au minimum Audit actif) |
| **Version** | 3.5 |

---

## 📘 Contenu du guide

| Document | Contenu |
|----------|---------|
| [Procédure de déploiement](procedure-deploiement.html) | Parties 0 à 11 : prérequis, méthodes d'authentification, emplacements nommés, politiques CA-01 à CA-09, SSPR, tests, checklist de remise client |
| [Annexes](annexes.html) | Glossaire, checklist complète, références nLPD, récapitulatif des politiques CA, adaptations sectorielles, différences POC et production |

---

## 🧱 Ce que le guide met en place

| Pilier | Ce que ça apporte |
|--------|-------------------|
| **Deux comptes break-glass** | Accès de secours exclu de toutes les politiques CA |
| **Emplacements nommés** | Zone géographique légitime pour le filtrage `[nLPD art. 8]` |
| **MFA obligatoire (CA-01)** | Première barrière contre la compromission de compte `[nLPD art. 8]` |
| **MFA anti-hameçonnage admins (CA-09)** | Protège les comptes à privilèges `[nLPD art. 8]` |
| **Blocage auth. héritée (CA-02)** | Ferme le contournement du MFA `[nLPD art. 8]` |
| **Filtrage géographique (CA-03)** | Applique les restrictions géographiques définies par l'entreprise `[nLPD art. 8]` |
| **Token Protection (CA-04)** | Réduit le risque de rejeu de jetons de session sur les plateformes compatibles `[nLPD art. 8]` |
| **Session limitée (CA-05)** | Restreint les sessions sur appareils non gérés `[nLPD art. 8]` |
| **Hors horaires (CA-06, expérimental)** | Signale les connexions hors heures ouvrables, optionnel `[nLPD art. 8]` |
| **Appareil conforme (CA-08)** | Rapport ici, Application après le guide Intune + Defender `[nLPD art. 8]` |
| **SSPR** | Réinitialisation autonome et auditée `[nLPD art. 8]` |

> **ℹ️ INFO** : hors périmètre MVC : Entra ID P2 (Identity Protection, PIM, Access Reviews). Il n'existe pas de politique CA-07 : la numérotation est conservée pour rester identique dans tous les guides du bundle.

### Étape 0 du bundle et niveaux

Les **Parties 0 à 3** de ce guide (prérequis, break-glass, méthodes d'authentification, emplacements nommés, CA-01 et CA-09) forment l'**étape 0** du bundle, à réaliser avant Purview. Les Parties 4 à 10 se déploient ensuite.

| Niveau | Contenu |
|--------|---------|
| **Niveau 1, socle** | Break-glass, CA-01, CA-09, CA-02, SSPR |
| **Niveau 2, renforcement** | CA-08, CA-05, CA-04, CA-03 |
| **Niveau 3, expérimental** | CA-06 (hors horaires), optionnel |

---

## 🔗 Liens avec les autres guides

- **Purview** : [guide Purview](../purview/index.html), à déployer après l'étape 0 de ce guide (Parties 0 à 3).
- **Intune + Defender** : [guide Intune + Defender](../intune-defender/index.html). CA-04 et CA-08 sont créées ici en mode Rapport, puis passées en Application après le déploiement du guide Intune + Defender.
- **AiTM** : [annexe AiTM / Cookie Hijacking](../aitm-cookie-hijacking/index.html), contexte de la protection contre le vol de session (CA-04, CAE).

---

## ⬇️ Téléchargements

| Format | Fichier |
|--------|---------|
| Word (.docx) | [MVC-nLPD_02-Entra-ID-P1_Procedure_v3.5.docx]({{ '/downloads/docx/MVC-nLPD_02-Entra-ID-P1_Procedure_v3.5.docx' | relative_url }}) |
| PDF | [MVC-nLPD_02-Entra-ID-P1_Procedure_v3.5.pdf]({{ '/downloads/pdf/MVC-nLPD_02-Entra-ID-P1_Procedure_v3.5.pdf' | relative_url }}) |

---

[🏠 Retour au portail principal](https://doit4everyone.github.io/)

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
