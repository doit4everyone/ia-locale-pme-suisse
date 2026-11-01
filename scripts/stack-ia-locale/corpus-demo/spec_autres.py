"""Dossiers COMPTABILITE, SERVICE INFO, PRODUCTION et COMMUN."""
from spec_base import *

DOCS = []
A = DOCS.append
C = "COMPTABILITE/"

A(doc(C + "20_Budget_Previsionnel_2026.docx",
      H1("Budget prévisionnel 2026"),
      P("Axonix SA, approuvé par le CA le 15 mars 2026. Document interne."),
      H2("1. Produits"),
      T(("Poste", "Budget 2026 (CHF)", "Réalisé 2025 (CHF)", "Variation"),
        ("Infogérance et maintenance", "1 850 000", "1 560 000", "+18.6%"),
        ("Projets d'intégration", "1 200 000", "900 000", "+33.3%"),
        ("Conseil et formation", "450 000", "380 000", "+18.4%"),
        ("Licences et renouvellements", "400 000", "360 000", "+11.1%"),
        ("Total produits", "3 900 000", "3 200 000", "+21.9%")),
      H2("2. Charges"),
      T(("Poste", "Budget 2026 (CHF)", "Réalisé 2025 (CHF)", "Variation"),
        ("Masse salariale (27 ETP)", "2 340 000", "1 980 000", "+18.2%"),
        ("Sous-traitance", "320 000", "280 000", "+14.3%"),
        ("Locaux et frais généraux", "185 000", "162 000", "+14.2%"),
        ("Licences logicielles", "220 000", "195 000", "+12.8%"),
        ("Investissements IT", "95 000", "48 000", "+97.9%"),
        ("Formation", "81 000", "69 000", "+17.4%"),
        ("Total charges", "3 241 000", "2 734 000", "+18.5%")),
      H2("3. Résultat prévisionnel"),
      P("Résultat brut d'exploitation : CHF 659 000 (marge : 16.9%). Après amortissements et impôts estimés : "
        "résultat net estimé à CHF 390 000, soit 10% du CA. La hausse des investissements IT reflète l'acquisition "
        "de serveurs pour l'offre IA locale."),
      P(MENTION)))

A(doc(C + "21_Bouclement_Comptes_2025.docx",
      H1("Comptes annuels 2025 : synthèse"),
      P("Axonix SA, exercice du 1er janvier au 31 décembre 2025. Révisés par Fiduciaire Matthey & Associés, Fribourg."),
      T(("Rubrique", "2025 (CHF)", "2024 (CHF)"),
        ("Chiffre d'affaires", "3 200 000", "2 857 000"),
        ("Charges d'exploitation", "2 734 000", "2 480 000"),
        ("Résultat net", "287 000", "231 000"),
        ("Fonds propres au 31 décembre", "1 140 000", "903 000")),
      P("Provision pour litiges : CHF 4 000 (client Transports Ruchonnet), constituée au 31 décembre 2025."),
      P(MENTION)))

BAU = ("Baumont Industries SA", "rue de l'Industrie 45, 1450 Sainte-Croix", "AX-2025-MAINT-003", 4200)
ROC = ("Étude Rochat & Associés", "rue du Grand-Chêne 8, 1003 Lausanne", "AX-2026-MAINT-007", 3840)
CLI = ("Clinique dentaire du Léman Sàrl", "avenue de Marcelin 5, 1110 Morges", "AX-2026-MAINT-011", 2150)
PER = ("Boulangerie Perrin & Fils SA", "rue de Gruyères 30, 1630 Bulle", "AX-2025-MAINT-009", 1480)
HOT = ("Hôtel Lac-Azur SA", "avenue des Alpes 70, 1820 Montreux", "AX-2026-MAINT-014", 2980)
BRU = ("Brügger Präzisionsteile AG", "Bözingenstrasse 120, 2502 Biel/Bienne", "AX-2026-MAINT-016", 3350)

F = C + "FACTURES/"
A(facture(F + "FA-2026-031_Baumont_Mars.docx", "FA-2026-031", "1er mars 2026", BAU[0], BAU[1], BAU[2], "mars 2026",
          [("Forfait de maintenance mensuel", "mars 2026", BAU[3]),
           ("Avenant n° 1 : installation WiFi halle B", "unique", 3800)], "31 mars 2026"))
A(facture(F + "FA-2026-032_Rochat_Mars.docx", "FA-2026-032", "1er mars 2026", ROC[0], ROC[1], ROC[2], "mars 2026",
          [("Forfait de maintenance mensuel", "mars 2026", ROC[3])], "31 mars 2026"))
A(facture(F + "FA-2026-047_Clinique_Leman_Avril.docx", "FA-2026-047", "1er avril 2026", CLI[0], CLI[1], CLI[2], "avril 2026",
          [("Forfait de maintenance mensuel", "avril 2026", CLI[3])], "1er mai 2026"))
A(facture(F + "FA-2026-048_Perrin_T2.docx", "FA-2026-048", "1er avril 2026", PER[0], PER[1], PER[2], "2e trimestre 2026",
          [("Forfait de maintenance (3 mois)", "avril à juin 2026", PER[3] * 3)], "1er mai 2026"))
A(facture(F + "FA-2026-066_Hotel_Lac-Azur_Mai.docx", "FA-2026-066", "1er mai 2026", HOT[0], HOT[1], HOT[2], "mai 2026",
          [("Forfait de maintenance mensuel", "mai 2026", HOT[3])], "31 mai 2026"))
A(facture(F + "FA-2026-071_Sarrasin_Migration.docx", "FA-2026-071", "30 juin 2026", "Sarrasin Fiduciaire SA",
          "boulevard de Pérolles 21, 1700 Fribourg", "AX-2026-PRJ-012", "projet de migration",
          [("Migration et configuration (forfait)", "avril à juin 2026", 18500),
           ("Formation utilisateurs (2 demi-journées)", "juin 2026", 2400)], "30 juillet 2026"))
A(doc(F + "FA-2026-075_Bruegger_Juni.docx",
      H1("Rechnung FA-2026-075"),
      P(f"{AX_NOM}, {AX_ADR}. Datum: 1. Juni 2026."),
      P(f"Empfängerin: {BRU[0]}, {BRU[1]}. Vertrag: {BRU[2]}. Periode: Juni 2026."),
      T(("Bezeichnung", "Periode", "Betrag exkl. MWST (CHF)"), ("Monatliche Wartungspauschale", "Juni 2026", "3 350")),
      P("Total exkl. MWST: CHF 3 350. MWST 8.1%: CHF 271.35. Total inkl. MWST: CHF 3 621.35. Zahlbar innert 30 Tagen."),
      P("Fiktives Dokument des Demonstrationskorpus der Axonix SA.")))

A(doc(C + "22_Decompte_TVA_T1_2026.docx",
      H1("Décompte TVA, 1er trimestre 2026"),
      P("Méthode effective. Établi le 20 avril 2026."),
      T(("Rubrique", "Montant (CHF)"),
        ("Chiffre d'affaires imposable (taux normal 8.1%)", "902 000"),
        ("TVA due", "73 062"),
        ("Impôt préalable déductible", "18 940"),
        ("Montant à verser à l'AFC", "54 122")),
      P("Délai de versement : 31 mai 2026."),
      P(MENTION)))

A(doc(C + "23_Procedure_Notes_de_Frais.docx",
      H1("Procédure : traitement des notes de frais"),
      P("1. La personne saisit sa note de frais avant le 5 du mois suivant, justificatifs joints. "
        "2. Le responsable valide dans les 5 jours ouvrés. 3. La comptabilité contrôle les plafonds du règlement "
        "des frais professionnels et rembourse avec le salaire du mois. Les notes de plus de CHF 1 000 sont "
        "validées en plus par la directrice générale."),
      P(MENTION)))

A(doc(C + "24_Relances_Debiteurs_2026.docx",
      H1("Suivi des débiteurs : relances 2026"),
      P("État au 30 juin 2026."),
      T(("Client", "Facture", "Montant TTC (CHF)", "Statut"),
        ("Transports Ruchonnet SA", "FA-2026-012", "2 810.60", "Contestée, réglée par la conciliation du 18 juin 2026"),
        ("Boulangerie Perrin & Fils SA", "FA-2026-048", "4 799.64", "Payée le 28 mai 2026"),
        ("Hôtel Lac-Azur SA", "FA-2026-066", "3 221.38", "Premier rappel envoyé le 10 juin 2026")),
      P(MENTION)))

# Sous-dossier réservé (héritage coupé existant) : GRP-Finances-Purview seulement
A(doc(C + "DIRECTION COMPTA/25_Masse_Salariale_2026.docx",
      H1("Masse salariale 2026 : budget détaillé"),
      P("Document réservé à la direction financière."),
      T(("Rubrique", "Montant annuel (CHF)"),
        ("Salaires bruts (27 ETP prévus)", "1 960 000"),
        ("Charges sociales employeur (AVS, AC, LPP, LAA)", "312 000"),
        ("Primes et bonus", "48 000"),
        ("Indemnités de télétravail", "20 000"),
        ("Total masse salariale", "2 340 000")),
      P("Enveloppe de révision salariale 2026 : 3,5% de la masse des salaires bruts, soit CHF 68 600, répartie "
        "selon les évaluations annuelles."),
      P(MENTION)))

A(doc(C + "Test_RAG_Depot.docx", P("Code de dépôt : DEPOT-8462")))

# ─────────────────────────── SERVICE INFO ───────────────────────────
S = "SERVICE INFO/SUPPORT/"
A(doc(S + "07_Guide_Depannage_Helpdesk.docx",
      H1("Guide de dépannage du helpdesk"),
      P("Axonix SA, support informatique, version 2.0 du 1er mars 2026. Usage interne et pour les clients sous contrat."),
      H2("1. Avant tout diagnostic"),
      P("Identifier le client, le contrat et la priorité selon la grille SLA du contrat. Ouvrir un ticket avant "
        "toute intervention, même par téléphone."),
      H2("2. Problèmes fréquents"),
      T(("Symptôme", "Vérification", "Solution"),
        ("Le VPN ne se connecte pas", "Connexion internet, date et heure du poste", "Réinstaller le profil VPN depuis le portail d'entreprise"),
        ("Code MFA refusé", "Heure du téléphone, application à jour", "Réinitialisation MFA selon la procédure dédiée"),
        ("Outlook ne s'ouvre pas", "Mode sans échec (outlook /safe)", "Recréer le profil, voir KB-001"),
        ("OneDrive ne synchronise plus", "Espace disque, nom de fichier trop long", "Voir KB-002"),
        ("Imprimante hors ligne", "Câble réseau, file d'attente", "Redémarrer le spouleur, voir la procédure imprimantes")),
      H2("3. Escalade"),
      P("Sans solution après 30 minutes, escalader au niveau 2 (ingénieurs). Tout incident de sécurité est "
        "escaladé immédiatement à Thomas Müller."),
      P(MENTION)))

A(doc(S + "33_FAQ_VPN.docx",
      H1("FAQ : accès à distance par VPN"),
      P("Le VPN de l'entreprise utilise le client Azure VPN, avec authentification Entra ID et MFA. Il est "
        "obligatoire hors des bureaux d'Yverdon-les-Bains, Lausanne, Fribourg et Neuchâtel."),
      P("Erreur fréquente : « certificat non valide » quand la date du poste est fausse. Synchroniser l'heure, "
        "puis relancer la connexion. Si l'erreur persiste, réinstaller le profil VPN depuis le portail d'entreprise."),
      P(MENTION)))

A(doc(S + "34_Procedure_Reinitialisation_MFA.docx",
      H1("Procédure : réinitialisation de l'authentification multifacteur"),
      P("1. Vérifier l'identité de la personne par rappel sur le numéro du registre interne, jamais sur un numéro "
        "donné pendant l'appel. 2. Dans Entra ID, supprimer les méthodes d'authentification enregistrées. "
        "3. Demander un nouvel enregistrement à la prochaine connexion."),
      P("Seuls Thomas Müller et Marco Ferrara peuvent réinitialiser la MFA d'un collaborateur d'Axonix. Pour les "
        "clients, la demande doit venir du référent désigné dans le contrat."),
      P(MENTION)))

A(doc(S + "35_Procedure_Imprimantes.docx",
      H1("Procédure : imprimantes réseau"),
      P("Les imprimantes des bureaux sont déployées par Intune. En cas d'impression bloquée : vider la file "
        "d'attente, redémarrer le service Spouleur d'impression, puis vérifier l'adresse IP réservée de "
        "l'imprimante dans le DHCP. Les toners sont commandés par Ana Pereira."),
      P(MENTION)))

A(doc(S + "36_Procedure_Nouvel_Arrivant.docx",
      H1("Procédure : arrivée d'un nouveau collaborateur"),
      P("J-10 : création du compte Entra ID et de la boîte aux lettres, ajout aux groupes du poste. "
        "J-5 : préparation du poste par Autopilot. J0 : remise du matériel, enregistrement MFA en présence du "
        "support, signature de la charte informatique."),
      P(MENTION)))

A(doc(S + "37_KB-001_Profil_Outlook.docx",
      H1("KB-001 : recréer un profil Outlook"),
      P("Panneau de configuration, Courrier, Afficher les profils, Ajouter. Nommer le profil avec la date, le "
        "définir par défaut, puis supprimer l'ancien après vérification. Durée : 10 minutes."),
      P(MENTION)))

A(doc(S + "38_KB-002_Synchronisation_OneDrive.docx",
      H1("KB-002 : OneDrive ne synchronise plus"),
      P("Causes fréquentes : chemin de plus de 400 caractères, caractères interdits, espace disque insuffisant. "
        "Mettre la synchronisation en pause, corriger le fichier en cause, puis reprendre."),
      P(MENTION)))

A(doc(S + "39_KB-003_Audio_Teams.docx",
      H1("KB-003 : pas de son dans Teams"),
      P("Vérifier le périphérique choisi dans les paramètres de Teams, puis dans Windows. Mettre à jour le pilote "
        "audio. Un casque USB défectueux est remplacé sur le stock du support."),
      P(MENTION)))

A(doc(S + "40_Statistiques_Tickets_T3_2026.docx",
      H1("Statistiques du support, T3 2026"),
      T(("Catégorie", "Tickets", "Part"),
        ("Postes de travail", "171", "38%"),
        ("Messagerie et Teams", "96", "21%"),
        ("VPN et MFA", "68", "15%"),
        ("Imprimantes", "41", "9%"),
        ("Serveurs et réseau", "52", "11%"),
        ("Sécurité", "27", "6%")),
      P("Total : 455 tickets. Délai moyen de première réponse : 22 minutes."),
      P(MENTION)))

A(doc(S + "41_Astreinte_et_Escalade.docx",
      H1("Organisation de l'astreinte"),
      P("Astreinte hebdomadaire tournante entre Claude Zbinden, Élodie Sarrasin et Valérie Beraz, du lundi 08h00 "
        "au lundi suivant 08h00. Numéro d'astreinte : 024 000 00 00 (fictif). Indemnité : CHF 250 par semaine "
        "d'astreinte, plus les heures d'intervention majorées de 50%."),
      P(MENTION)))

S2 = "SERVICE INFO/ADMIN/"
A(doc(S2 + "30_Procedure_Deploiement_Poste_W11.docx",
      H1("Procédure de déploiement poste de travail Windows 11"),
      P("Axonix SA, procédure interne v2.3, mise à jour : février 2026. Rédigée par Marco Ferrara, Directeur technique."),
      H2("1. Prérequis"),
      P("Matériel : PC compatible Windows 11 (TPM 2.0, Secure Boot, 8 Go RAM minimum, 256 Go SSD). Image : "
        "Windows 11 Pro 24H2, mise à jour mars 2026. Accès : compte de déploiement avec droits Intune et Entra ID."),
      H2("2. Procédure Autopilot"),
      P("Étape 1 : Enregistrer le hash matériel dans Intune. Depuis PowerShell sur le poste neuf : "
        "Install-Script -Name Get-WindowsAutoPilotInfo puis Get-WindowsAutoPilotInfo -Online."),
      P("Étape 2 : Assigner le profil Autopilot Axonix-Standard dans le portail Intune. Le profil configure : "
        "jonction Entra ID, compte administrateur local désactivé, chiffrement BitLocker, Defender for Business activé."),
      P("Étape 3 : Démarrer le poste et suivre l'OOBE. L'utilisateur final saisit ses identifiants Entra ID. "
        "La configuration s'applique automatiquement (durée : 20 à 40 minutes selon la connexion)."),
      H2("3. Applications déployées automatiquement"),
      T(("Application", "Version", "Déploiement", "Obligatoire"),
        ("Microsoft 365 Apps", "Dernière (canal mensuel)", "Intune", "Oui"),
        ("Defender for Business", "Intégré Windows 11", "GPO/Intune", "Oui"),
        ("Azure VPN Client", "3.x", "Intune", "Oui"),
        ("VS Code", "Dernière stable", "Winget/Intune", "Équipe IT uniquement"),
        ("7-Zip", "24.x", "Winget", "Oui"),
        ("Adobe Acrobat Reader", "DC", "Winget", "Oui")),
      H2("4. Vérifications post-déploiement"),
      P("Checklist obligatoire : BitLocker activé et clé sauvegardée dans Entra ID, Defender for Business en "
        "protection active, connexion VPN fonctionnelle, accès SharePoint et Teams, synchronisation OneDrive, "
        "imprimante réseau configurée. Durée de vérification estimée : 15 minutes."),
      P(MENTION)))

A(doc(S2 + "31_Runbook_Backup_Restauration.docx",
      H1("Runbook : procédure de sauvegarde et restauration"),
      P("Axonix SA, procédure interne v1.4, mise à jour : janvier 2026."),
      H2("1. Architecture de sauvegarde"),
      P("Axonix SA utilise une stratégie de sauvegarde 3-2-1 : 3 copies des données, sur 2 types de supports "
        "différents, dont 1 hors site."),
      T(("Niveau", "Support", "Fréquence", "Rétention"),
        ("Primaire", "NAS Synology DS923+ (2×8 To RAID-1)", "Continue (snapshots toutes les heures)", "30 jours"),
        ("Secondaire", "NAS Synology hors site (bureau de Fribourg)", "Nuit (rsync 02h00)", "90 jours"),
        ("Tertiaire", "Stockage objet chiffré, datacenter en Suisse", "Nuit (02h30)", "1 an")),
      H2("2. Procédure de restauration partielle (fichiers)"),
      P("Étape 1 : Identifier le fichier et la version souhaitée. Accéder à l'interface Synology Hyper Backup "
        "sur nas.axonix.local."),
      P("Étape 2 : Naviguer dans l'historique des snapshots. Sélectionner la version antérieure à l'incident."),
      P("Étape 3 : Restaurer vers un dossier temporaire. Vérifier l'intégrité du fichier avant de le remettre en production."),
      P("Délai moyen de restauration d'un fichier : 5 à 15 minutes selon la taille."),
      H2("3. Procédure de restauration complète (PRA)"),
      P("En cas de sinistre majeur (incendie, rançongiciel), le Plan de Reprise d'Activité prévoit : RTO (Recovery "
        "Time Objective) de 4 heures pour les services critiques, RPO (Recovery Point Objective) de 24 heures maximum."),
      P("Séquence de restauration : 1. Provisionner le nouveau serveur (VMware ou cloud). 2. Restaurer depuis le "
        "NAS hors site (priorité 1) ou le stockage objet (priorité 2). 3. Valider l'intégrité des données. "
        "4. Reconfigurer les services réseau. 5. Tester les accès utilisateurs."),
      H2("4. Tests de restauration"),
      P("Les tests de restauration sont effectués trimestriellement. Dernier test réalisé : 15 décembre 2025. "
        "Résultat : restauration complète en 3h42, dans les objectifs RTO. Prochain test planifié : 15 mars 2026."),
      P(MENTION)))

A(doc(S2 + "32_Politique_Securite_Informatique.docx",
      H1("Politique de sécurité informatique"),
      P("Axonix SA, version 2.1, approuvée par la direction le 1er janvier 2026. Applicable à tous les collaborateurs."),
      H2("1. Gestion des accès"),
      P("Principe du moindre privilège : chaque collaborateur dispose uniquement des droits nécessaires à sa "
        "fonction. Les comptes administrateurs sont nominatifs et distincts des comptes utilisateurs standard. "
        "L'authentification multifacteur (MFA) est obligatoire pour tous les accès aux ressources cloud et au VPN."),
      P("Mots de passe : longueur minimale 12 caractères, complexité requise. Le gestionnaire de mots de passe "
        "Bitwarden est fourni à tous les collaborateurs. La réutilisation de mots de passe entre comptes "
        "professionnels et personnels est interdite."),
      H2("2. Protection des postes de travail"),
      P("Tous les postes sont équipés de Microsoft Defender for Business (EDR). Le chiffrement BitLocker est "
        "activé sur tous les disques. Les mises à jour Windows sont appliquées automatiquement dans les 72 heures "
        "suivant leur publication (politique Intune). L'installation de logiciels non approuvés est interdite."),
      H2("3. Protection des données clients"),
      P("Les données clients sont classifiées et traitées selon la politique de protection des données, en "
        "conformité avec la nLPD. Aucune donnée client ne peut être stockée sur des supports personnels. Le "
        "transfert de données clients par courriel non chiffré est interdit. Tout incident de sécurité impliquant "
        "des données clients doit être signalé dans l'heure à la direction."),
      H2("4. Télétravail et accès distants"),
      P("L'accès aux ressources internes en télétravail se fait exclusivement via le VPN Azure (client officiel). "
        "Les réseaux WiFi publics sont interdits sans VPN actif. Le verrouillage automatique du poste est "
        "obligatoire après 5 minutes d'inactivité."),
      H2("5. Sensibilisation et formation"),
      P("Chaque collaborateur suit une formation de sensibilisation à la sécurité lors de son intégration et "
        "annuellement. Des simulations d'hameçonnage sont réalisées trimestriellement. Les résultats sont anonymisés "
        "et utilisés pour améliorer la formation."),
      H2("6. Incidents de sécurité"),
      T(("Type d'incident", "Délai de signalement", "Responsable", "Escalade"),
        ("Hameçonnage (clic ou réponse)", "1 heure", "Collaborateur → IT", "Si données saisies : DG immédiatement"),
        ("Rançongiciel / logiciel malveillant", "Immédiat", "IT → DG", "Isolation réseau, PRA"),
        ("Perte ou vol de matériel", "1 heure", "Collaborateur → IT → DG", "Effacement à distance par Intune"),
        ("Violation de la sécurité des données", "Immédiat", "IT → DG → avocat",
         "Annonce au PFPDT si risque élevé pour les personnes concernées (art. 24 nLPD) ; "
         "information du client responsable du traitement")),
      P(MENTION)))

A(doc(S2 + "42_Inventaire_Materiel_2026.docx",
      H1("Inventaire du matériel interne 2026"),
      T(("Catégorie", "Quantité", "Remarque"),
        ("Portables Windows 11", "26", "Renouvellement de 8 portables prévu en 2026"),
        ("Serveurs", "3", "Dont le serveur GPU de démonstration acheté en juillet 2026"),
        ("NAS Synology", "2", "Yverdon-les-Bains et Fribourg"),
        ("Téléphones mobiles", "24", "Gérés par Intune")),
      P(MENTION)))

A(doc(S2 + "43_Comptes_a_Privileges.docx",
      H1("Gestion des comptes à privilèges"),
      P("Les comptes d'administration sont distincts des comptes de travail et portent le préfixe adm-. "
        "Ils n'ont ni messagerie ni accès internet. Revue trimestrielle des membres des groupes d'administration "
        "par Thomas Müller ; dernière revue : 30 septembre 2026, deux comptes inactifs désactivés."),
      P(MENTION)))

A(doc(S2 + "44_Procedure_Depart_Collaborateur.docx",
      H1("Procédure : départ d'un collaborateur"),
      P("Le jour du départ : blocage du compte à 17h00, révocation des sessions, retrait des appareils mobiles "
        "dans Intune, transfert de la boîte aux lettres au responsable pour 30 jours. Le matériel est restitué "
        "et réinitialisé avant réattribution."),
      P(MENTION)))

# ───────────────────────────── PRODUCTION ─────────────────────────────
PR = "PRODUCTION/"
def fiche(fichier, titre, *paras):
    return doc(PR + fichier, H1(titre), *[P(x) for x in paras], P(MENTION))

A(fiche("50_Fiche_Projet_Migration_Sarrasin.docx", "Fiche projet : migration Azure de Sarrasin Fiduciaire",
        "Référence AX-2026-PRJ-012. Chef de projet : Pierre Dupont. Statut : terminé le 19 juin 2026.",
        "Charge réelle : 142 heures pour 136 heures prévues. Point d'attention retenu : le débit internet du "
        "bureau du client a dû être augmenté avant la migration de production."))
A(fiche("51_Fiche_Projet_IA_Locale_Clinique.docx", "Fiche projet : pilote d'IA locale à la Clinique dentaire du Léman",
        "Objectif : assistant de recherche dans les protocoles internes de la clinique, sans aucune donnée de patient. "
        "Modèle exécuté localement sur le serveur GPU de démonstration.",
        "Statut au 30 septembre 2026 : pilote en test auprès de 3 assistantes dentaires, décision de mise en "
        "production prévue en décembre 2026."))
A(fiche("52_Fiche_Projet_WiFi_Hotel_Lac-Azur.docx", "Fiche projet : WiFi 6E de l'Hôtel Lac-Azur",
        "Référence AX-2026-OF-016. Installation de 24 bornes pendant la fermeture annuelle, du 2 au 27 novembre 2026.",
        "Ressources : Claude Zbinden et un sous-traitant pour le câblage."))
A(fiche("53_Fiche_Projet_Caisses_Perrin.docx", "Fiche projet : remplacement des caisses Perrin",
        "Offre AX-2026-OF-019 en attente de décision du client. Si elle est acceptée, déploiement magasin par magasin "
        "en janvier 2027, hors des jours de forte affluence."))
A(fiche("54_Planning_Ressources_T4_2026.docx", "Planning des ressources, T4 2026",
        "Octobre : renouvellement des postes de l'atelier Baumont (Claude Zbinden). Novembre : WiFi de l'Hôtel "
        "Lac-Azur (Claude Zbinden, Élodie Sarrasin). Décembre : bilan du pilote d'IA locale (Valérie Beraz). "
        "Astreinte de fin d'année : Thomas Müller du 24 décembre 2026 au 4 janvier 2027."))
A(fiche("55_Retour_Experience_Incident_Baumont.docx", "Retour d'expérience : incident critique Baumont du 3 mars 2026",
        "Ce qui a fonctionné : alerte de supervision immédiate, prise en charge en 25 minutes, contrôleur RAID "
        "de rechange disponible en stock.",
        "À améliorer : l'onduleur n'était plus testé depuis 18 mois. Un test de basculement trimestriel est "
        "désormais planifié pour tous les clients industriels."))
A(fiche("56_Checklist_Mise_en_Service_Serveur.docx", "Checklist : mise en service d'un serveur",
        "Mises à jour installées, sauvegarde configurée et testée par une restauration, supervision active, "
        "onduleur raccordé et testé, documentation remise au client, mot de passe d'administration enregistré "
        "dans le coffre Bitwarden de l'équipe."))
A(fiche("57_Fiche_Projet_Bureau_Neuchatel.docx", "Fiche projet interne : équipement du bureau de Neuchâtel",
        "Câblage, 4 postes de travail, imprimante, raccordement VPN au siège. Mise en service le 28 août 2026, "
        "trois jours avant l'ouverture."))
A(fiche("58_Fiche_Projet_MFA_Bruegger.docx", "Fiche projet : MFA chez Brügger Präzisionsteile",
        "Mise en place de l'authentification multifacteur pour les 22 comptes du client, terminée le 28 avril 2026, "
        "deux jours avant l'échéance fixée lors du lancement."))
A(fiche("59_Modele_Rapport_Intervention.docx", "Modèle de rapport d'intervention",
        "Rubriques : client, numéro de ticket, date et heure de prise en charge, description, cause, actions, "
        "durée, signature du client. Le rapport est joint au ticket dans les 24 heures."))

# ─────────────────────────────── COMMUN ───────────────────────────────
CO = "COMMUN/"
A(doc(CO + "60_Charte_Informatique.docx",
      H1("Charte informatique d'Axonix SA"),
      P("Applicable à tous les collaborateurs, signée à l'arrivée."),
      P("Le matériel et les comptes sont confiés pour un usage professionnel ; un usage privé raisonnable est "
        "toléré. Il est interdit de contourner les mesures de sécurité, de partager ses identifiants, ou de "
        "copier des données clients vers un service non approuvé, y compris un service d'intelligence artificielle "
        "en ligne. Les journaux techniques peuvent être consultés en cas d'incident, dans le respect de la nLPD."),
      P(MENTION)))
A(doc(CO + "61_Annuaire_Interne.docx",
      H1("Annuaire interne"),
      T(("Nom", "Fonction", "Bureau", "Téléphone interne"),
        ("Nadia Vaucher", "Directrice générale", "Yverdon-les-Bains", "201"),
        ("Marco Ferrara", "Directeur technique", "Yverdon-les-Bains", "202"),
        ("Ana Pereira", "Assistante de direction", "Yverdon-les-Bains", "200"),
        ("Pierre Dupont", "Chef de projet senior", "Yverdon-les-Bains", "210"),
        ("Valérie Beraz", "Ingénieure systèmes", "Neuchâtel", "401"),
        ("Thomas Müller", "Ingénieur sécurité", "Lausanne", "301"),
        ("Élodie Sarrasin", "Technicienne IT", "Fribourg", "501"),
        ("Claude Zbinden", "Technicien IT junior", "Yverdon-les-Bains", "220")),
      P(MENTION)))
A(doc(CO + "62_Calendrier_Fermetures_2026.docx",
      H1("Calendrier des fermetures 2026"),
      P("Les bureaux d'Axonix SA sont fermés du 24 décembre 2026 à midi au 4 janvier 2027 inclus. "
        "L'astreinte reste assurée pour les clients sous contrat."),
      P("Ponts accordés en 2026 : vendredi 15 mai (Ascension) et lundi 21 septembre (Lundi du Jeûne, bureaux "
        "vaudois)."),
      P(MENTION)))
A(doc(CO + "63_Organisation_des_Bureaux.docx",
      H1("Organisation des bureaux"),
      T(("Bureau", "Adresse", "Personnes"),
        ("Yverdon-les-Bains (siège)", AX_ADR, "Direction, projets, support"),
        ("Lausanne", "avenue de la Gare 40, 1003 Lausanne", "Sécurité, projets"),
        ("Fribourg", "route des Arsenaux 9, 1700 Fribourg", "Support, sauvegarde hors site"),
        ("Neuchâtel", "faubourg du Lac 31, 2000 Neuchâtel", "Ouvert le 1er septembre 2026")),
      P(MENTION)))
A(doc(CO + "64_Guide_Accueil_Nouveaux.docx",
      H1("Guide d'accueil des nouveaux collaborateurs"),
      P("Bienvenue chez Axonix SA. Votre premier jour : accueil par Ana Pereira à 08h30, remise du matériel, "
        "enregistrement de l'authentification multifacteur avec le support, lecture et signature de la charte "
        "informatique. Votre parrain ou marraine vous accompagne pendant la période d'essai."),
      P(MENTION)))
A(doc(CO + "65_Note_de_Service_Fin_Annee.docx",
      H1("Note de service : fin d'année 2026"),
      P("Le repas de fin d'année aura lieu le vendredi 11 décembre 2026 à Yverdon-les-Bains. Les collaborateurs "
        "des bureaux de Lausanne, Fribourg et Neuchâtel sont invités ; les frais de transport sont remboursés."),
      P(MENTION)))
