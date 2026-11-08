---
title: "MVC nLPD : Microsoft 365 Business Premium | DoIt4Everyone"
description: "Bundle Minimum Viable de Conformité (MVC) nLPD pour PME suisses de 5 à 25 utilisateurs sur Microsoft 365 Business Premium + Purview Suite. Quatre guides de déploiement et d'exploitation, précédés d'une étape 0 identité."
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

<h1>Bundle MVC nLPD : Microsoft 365 Business Premium</h1>
<h2>Minimum Viable de Conformité · nLPD RS 235.1 · PME suisses 🇨🇭</h2>

Beaucoup de petites PME suisses peinent à traduire les exigences de la nLPD en mesures techniques et organisationnelles concrètes, faute de temps, de ressources et d'expertise spécialisée. Les guides disponibles supposent souvent des licences et une expertise IT qu'elles n'ont pas.

Ce bundle change ça. Il est conçu pour **Microsoft 365 Business Premium + Purview Suite** (pas E3, pas E5) et s'installe en quelques sessions de travail, sans consultant permanent. L'objectif n'est pas la perfection technique : c'est la capacité de démontrer devant le [PFPDT](https://www.edoeb.admin.ch/) une démarche **proportionnée, documentée et maintenue**.

> Un MVC déployé et maintenu vaut mieux qu'un projet de conformité parfait qui ne démarre jamais.

---

## 🗂️ Les quatre guides du bundle

| # | Guide | Objet principal | Portail | Statut |
|---|-------|-----------------|---------|--------|
| 1 | [Microsoft Purview](purview/index.html) | Classification, étiquetage, DLP, rétention | `purview.microsoft.com` | v1.2, publié |
| 2 | [Entra ID P1](entra-id-p1/index.html) | Accès conditionnel, MFA, SSPR, break-glass (Parties 0 à 3 = étape 0, avant Purview) | `entra.microsoft.com` | v3.5 |
| 3 | [Intune + Defender for Business](intune-defender/index.html) | Conformité des appareils, durcissement ASR | `intune.microsoft.com` | v3.1, validation terrain |
| 4 | [Copilot Governance](copilot-governance/index.html) | Gouvernance Copilot, DSPM for AI (dashboard), DLP-Protection-Copilot | `purview.microsoft.com` | v1.0 |

---

## 🔐 Durcissement et sécurité

Documents techniques autonomes publiés en complément du bundle, couvrant des vecteurs d'attaque spécifiques ou des configurations avancées. D'autres annexes seront ajoutées au fil des publications.

| Annexe | Objet | Statut |
|--------|-------|--------|
| [AiTM / Cookie Hijacking](aitm-cookie-hijacking/index.html) | Détection et mitigation des attaques adversary-in-the-middle contournant le MFA : incidents, IoC, protection structurelle (WHfB, CAE, FIDO2) | Publication prochaine |

---

## 🔢 Séquence de déploiement recommandée

| Session | Guide | Durée de travail technique |
|---------|-------|----------------------------|
| 0 | Entra ID P1, Parties 0 à 3 : break-glass, méthodes d'authentification, MFA (CA-01), MFA des administrateurs (CA-09) | 1 h 30 à 2 h |
| 1 | Purview : Classification + DLP + Rétention | 4–6 h |
| 2 | Entra ID P1, Parties 4 à 10 : suite de l'accès conditionnel + SSPR | 1 h à 1 h 30 |
| 3 | Intune + Defender : Conformité appareils + ASR | 4–5 h |
| 4 | Copilot Governance : Gouvernance IA | 2–3 h |

> Les durées sont du temps de travail technique. Les périodes en mode Rapport (7 à 14 jours selon la politique d'accès conditionnel) sont du temps calendaire à prévoir dans le planning du client.

---

## 🏷️ Périmètre de licence

| Licence | Requis |
|---------|--------|
| Microsoft 365 Business Premium | Oui |
| Microsoft Purview Suite for Microsoft 365 Business Premium (add-on) | Oui. Prix : voir la page officielle Microsoft Suisse et le revendeur, les tarifs évoluent |

Aucune licence E3 ou E5 n'est requise. Les fonctionnalités hors périmètre sont signalées explicitement dans chaque guide. Pour aller plus loin sur la gouvernance IA (blocage Shadow AI, Insider Risk Management, Endpoint DLP, DSPM with policies), ces fonctionnalités requièrent l'add-on **Defender and Purview Suites** et sont documentées dans le [Guide Shadow AI Microsoft 365](https://doit4everyone.github.io/shadow-ai-governance-microsoft-365-nLPD/).

---

## 🔗 Cohérence transverse

Les noms de groupes de sécurité et de stratégies d'accès conditionnel sont **identiques d'un guide à l'autre**. Toute modification doit être répercutée dans tous les guides concernés.

| Objet | Nom exact | Créé dans |
|-------|-----------|-----------|
| Groupe chiffrement Purview | `GRP-Confidentiel-Purview` | Guide Purview |
| Groupe Break-glass | `GRP-CA-BreakGlass` | Guide Entra ID P1 |
| Groupe SSPR | `GRP-SSPR-Utilisateurs` | Guide Entra ID P1 |
| Groupe Defender | `GRP-Appareils-Defender` | Guide Intune + Defender |
| Groupe USB | `GRP-USB-Autorises` | Guide Intune + Defender |
| Stratégie conformité appareils | `CA-08` | Entra ID P1 (Report) → Intune (Enforcement) |

---

## 🇨🇭 Conformité nLPD

| Article | Exigence | Mesure MVC |
|---------|----------|------------|
| Art. 8 | Mesures techniques et organisationnelles | Chiffrement RMS, DLP, MFA, conformité appareils |
| Art. 12 | Registre des activités de traitement (modèle à utiliser lorsque légalement requis ou adopté volontairement ; les entreprises de moins de 250 collaborateurs bénéficient d'une exception, sous réserve notamment du traitement à grande échelle de données sensibles ou du profilage à risque élevé) | Modèle pré-rempli, Annexe I du guide Purview |
| Art. 24 | Annonce des violations de la sécurité des données | Journaux d'audit et alertes qui facilitent la détection et la documentation d'un incident ; l'annonce au PFPDT reste une démarche organisationnelle |

---

[🏠 Retour au portail principal](https://doit4everyone.github.io/)

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
