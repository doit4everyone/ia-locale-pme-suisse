"""Dossier CLIENTS : 8 clients, plus un client en litige (CLIENTS/_Confidentiel)."""
from spec_base import *

DOCS = []
A = DOCS.append

# ─── Baumont Industries SA, Sainte-Croix (contrat d'origine, marqueurs conservés) ───
BAU = "Baumont Industries SA"
BAU_ADR = "rue de l'Industrie 45, 1450 Sainte-Croix"
BAU_D = "CLIENTS/Baumont Industries SA/"
A(contrat_maintenance(
    BAU_D + "21_Contrat_Maintenance_Baumont_Industries.docx", "AX-2025-MAINT-003", "1er juillet 2025",
    BAU, BAU_ADR, "Jean-François Baumont, Directeur général",
    "fabrication de pièces mécaniques de précision, 38 employés",
    [("Infogérance postes", "35 postes Windows 11 Pro", "Oui"),
     ("Infogérance serveurs", "1 serveur Windows Server 2022, 1 NAS Synology", "Oui"),
     ("Réseau", "Firewall OPNsense, 3 switches, WiFi industriel", "Oui"),
     ("Sauvegarde", "Backup journalier NAS + réplication hors site", "Oui"),
     ("Helpdesk", "Lundi-vendredi 07h00-17h00, délai 2h sur site", "Oui"),
     ("Sécurité", "EDR Defender for Business, pare-feu géré", "Oui")],
    4200, "Facturation le premier de chaque mois, paiement à 30 jours. Déplacement sur site inclus "
          "dans le forfait pour les interventions dans le rayon de 30 km.",
    [("Critique", "Arrêt production", "1 heure", "4 heures"),
     ("Haute", "Dégradation ligne de production", "2 heures", "8 heures"),
     ("Normale", "Incident isolé utilisateur", "4 heures", "2 jours ouvrés"),
     ("Faible", "Demande de service", "1 jour ouvré", "5 jours ouvrés")],
    "Durée initiale : 24 mois à compter du 1er juillet 2025. Reconduction tacite par période de 12 mois. "
    "Résiliation : préavis de 90 jours par lettre recommandée avant l'échéance.",
    f"{AX_NOM} s'engage à respecter les contraintes de production de {BAU}. Toute intervention planifiée "
    "sur les systèmes de production est coordonnée 48h à l'avance avec le responsable de production. "
    "Les interventions d'urgence (panne critique) peuvent avoir lieu en dehors des heures ouvrées avec "
    "astreinte téléphonique."))

A(doc(BAU_D + "22_Avenant_1_WiFi_Atelier_Baumont.docx",
      H1("Avenant n° 1 au contrat de maintenance AX-2025-MAINT-003"),
      P(f"Entre {AX_NOM} et {BAU}. Date : 12 février 2026."),
      H2("1. Objet"),
      P("Extension de la couverture WiFi industrielle au nouvel atelier d'usinage (halle B), "
        "avec deux bornes supplémentaires et un contrôleur."),
      H2("2. Conditions financières"),
      P("Installation unique : CHF 3 800 HT, facturée à la mise en service. Le forfait mensuel du contrat "
        "reste inchangé à CHF 4 200 HT. Les deux bornes entrent dans le périmètre « Réseau » du contrat."),
      H2("3. Entrée en vigueur"),
      P("Le présent avenant entre en vigueur le 1er mars 2026. Les autres clauses du contrat restent applicables."),
      P(MENTION)))

A(doc(BAU_D + "23_PV_Suivi_T1_2026_Baumont.docx",
      H1(f"Procès-verbal de séance de suivi, {BAU}"),
      P("Séance du 8 avril 2026, à Sainte-Croix. Participants : Jean-François Baumont (client), "
        "Pierre Dupont (chef de projet Axonix), Marco Ferrara (directeur technique Axonix)."),
      H2("1. Bilan du trimestre"),
      P("42 tickets traités au premier trimestre 2026, dont 1 incident critique (panne du serveur de "
        "production le 3 mars 2026, résolu en 3 heures 10). Taux de respect des délais : 97%."),
      H2("2. Renouvellement"),
      P("Le client évoque un renouvellement anticipé à CHF 3 900 HT par mois contre un engagement de 36 mois. "
        "Proposition à l'étude, rien n'est signé : le contrat AX-2025-MAINT-003 et son forfait de CHF 4 200 HT "
        "restent seuls applicables."),
      H2("3. Actions"),
      P("Axonix remet une offre de renouvellement d'ici au 30 juin 2026. Le client planifie le remplacement "
        "de 10 postes de l'atelier au quatrième trimestre."),
      P(MENTION)))

A(doc(BAU_D + "24_Rapport_Incident_Serveur_Production_Baumont.docx",
      H1("Rapport d'incident critique"),
      P(f"Client : {BAU}. Incident n° INC-2026-0117. Date : 3 mars 2026."),
      H2("1. Description"),
      P("Arrêt du serveur Windows Server 2022 qui pilote la planification de production, à 06h40. "
        "Cause : défaillance du contrôleur RAID après une coupure de courant non protégée par l'onduleur."),
      H2("2. Chronologie"),
      T(("Heure", "Action"),
        ("06h40", "Alerte de supervision, appel de l'astreinte"),
        ("07h05", "Prise en charge par Claude Zbinden (25 minutes, dans le délai d'une heure)"),
        ("08h30", "Remplacement du contrôleur, reconstruction du volume"),
        ("09h50", "Reprise de la production confirmée par le client")),
      H2("3. Mesures"),
      P("Remplacement de la batterie de l'onduleur, test de basculement trimestriel ajouté au plan de maintenance."),
      P(MENTION)))

# ─── Étude Rochat & Associés, Lausanne : deux versions du contrat ───
ROC = "Étude Rochat & Associés"
ROC_ADR = "rue du Grand-Chêne 8, 1003 Lausanne"
ROC_D = "CLIENTS/Etude Rochat Associes/"
ROC_SERV = [("Infogérance postes", "20 postes Windows 11 Pro", "Oui"),
            ("Infogérance serveurs", "2 serveurs Windows Server 2025", "Oui"),
            ("Sauvegarde", "Backup journalier sur NAS + cloud Suisse", "Oui"),
            ("Helpdesk", "Lundi-vendredi 08h00-18h00, délai 4h", "Oui"),
            ("Sécurité", "EDR Defender for Business, mises à jour", "Oui"),
            ("Gestion documentaire", "iManage Work 10, 20 licences", "Oui")]
ROC_SLA = [("Critique", "Système de production à l'arrêt", "30 minutes", "4 heures"),
           ("Haute", "Dégradation significative", "2 heures", "8 heures"),
           ("Normale", "Incident isolé", "4 heures", "2 jours ouvrés"),
           ("Faible", "Demande de service", "1 jour ouvré", "5 jours ouvrés")]
A(contrat_maintenance(
    ROC_D + "03_Contrat_Maintenance_Etude_Rochat.docx", "AX-2026-MAINT-007", "1er janvier 2026",
    ROC, ROC_ADR, "Martin Rochat, Associé gérant", "cabinet d'avocats, 8 avocats, 12 collaborateurs",
    ROC_SERV, 3840, "Facturation le premier de chaque mois, paiement à 30 jours. Indexation annuelle selon l'IPC suisse.",
    ROC_SLA,
    "Durée initiale : 24 mois à compter du 1er janvier 2026. Reconduction tacite par période de 12 mois. "
    "Résiliation : préavis de 90 jours par lettre recommandée avant l'échéance.",
    "Secret professionnel de l'avocat : les techniciens d'Axonix n'accèdent aux dossiers clients de l'Étude "
    "qu'en présence d'un collaborateur de l'Étude, et signent un engagement de confidentialité nominatif.",
    statut="Version définitive, signée le 1er janvier 2026. Elle remplace le projet AX-2025-MAINT-005."))

A(contrat_maintenance(
    ROC_D + "06_Contrat_Maintenance_Etude_Rochat_v1.docx", "AX-2025-MAINT-005", "15 novembre 2025",
    ROC, ROC_ADR, "Martin Rochat, Associé gérant", "cabinet d'avocats, 8 avocats, 12 collaborateurs",
    ROC_SERV[:5], 3600, "Facturation le premier de chaque mois, paiement à 30 jours.",
    ROC_SLA,
    "Durée initiale : 1 an à compter du 1er décembre 2025. Reconduction tacite par période de 12 mois.",
    titre="Projet de contrat de maintenance informatique (version 1)",
    statut="PROJET NON SIGNÉ, ANNULÉ : remplacé par le contrat définitif AX-2026-MAINT-007 du 1er janvier 2026."))

A(doc(ROC_D + "07_PV_Suivi_S1_2026_Rochat.docx",
      H1(f"Procès-verbal de séance de suivi, {ROC}"),
      P("Séance du 2 juillet 2026, à Lausanne. Participants : Martin Rochat (client), Pierre Dupont (Axonix)."),
      H2("1. Bilan du semestre"),
      P("61 tickets au premier semestre 2026, dont 2 incidents critiques sur iManage, pris en charge en "
        "20 et 25 minutes. Satisfaction exprimée par le client sur la réactivité."),
      H2("2. Demandes du client"),
      P("Ajout de 4 licences iManage pour deux avocats stagiaires dès septembre 2026. "
        "Étude d'un archivage des dossiers clos sur un stockage suisse à long terme."),
      P(MENTION)))

A(doc(ROC_D + "08_Rapport_Incident_iManage_Rochat.docx",
      H1("Rapport d'incident critique"),
      P(f"Client : {ROC}. Incident n° INC-2026-0203. Date : 14 avril 2026."),
      H2("1. Description"),
      P("Indisponibilité du serveur iManage Work après une mise à jour Windows, de 08h15 à 09h40. "
        "Les avocats ne pouvaient plus ouvrir les dossiers clients."),
      H2("2. Résolution"),
      P("Prise en charge en 20 minutes par Valérie Beraz. Retrait de la mise à jour KB fautive, redémarrage "
        "des services iManage, puis report des mises à jour du serveur iManage à une fenêtre mensuelle validée "
        "par l'Étude."),
      P(MENTION)))

# ─── Sarrasin Fiduciaire SA, Fribourg ───
SAR = "Sarrasin Fiduciaire SA"
SAR_D = "CLIENTS/Sarrasin Fiduciaire SA/"
A(doc(SAR_D + "04_Reponse_AO_Migration_Azure_Sarrasin.docx",
      H1("Réponse à appel d'offres"),
      P(f"Migration infrastructure vers Microsoft Azure. Client : {SAR}, Fribourg. Référence Axonix : AX-2026-AO-012. "
        "Date : 15 février 2026."),
      H2("1. Présentation de l'offre"),
      P(f"{AX_NOM} propose une migration complète de l'infrastructure de {SAR} vers Microsoft Azure, avec "
        "hébergement des données en datacenter suisse (Azure Switzerland North, Zurich). La migration est "
        "planifiée sur 12 semaines avec une disponibilité garantie de 99,9% pendant la transition."),
      H2("2. Périmètre technique"),
      T(("Composant", "Situation actuelle", "Cible Azure"),
        ("Serveur de fichiers", "Windows Server 2016 on-prem", "Azure Files + SharePoint Online"),
        ("Messagerie", "Exchange Server 2019", "Exchange Online (M365 Business Premium)"),
        ("ERP fiduciaire", "Abacus v2024 on-prem", "Abacus Cloud Suisse"),
        ("Sauvegardes", "NAS local", "Azure Backup (datacenter CH)"),
        ("Sécurité périmètre", "Firewall Fortinet", "Azure Firewall + Defender for Business")),
      H2("3. Chiffrage"),
      T(("Poste", "Coût unique (CHF)", "Coût mensuel récurrent (CHF)"),
        ("Licences M365 Business Premium (12 utilisateurs)", "", "744"),
        ("Azure Backup et stockage", "", "185"),
        ("Abacus Cloud Suisse", "", "620"),
        ("Migration et configuration (forfait)", "18 500", ""),
        ("Formation utilisateurs (2 demi-journées)", "2 400", ""),
        ("Support post-migration (6 mois)", "", "890"),
        ("Total première année", "20 900", "2 439/mois")),
      H2("4. Garanties et protection des données"),
      P("Toutes les données restent hébergées en Suisse (Azure Switzerland North). Axonix SA fournit un contrat "
        "de sous-traitance des données personnelles selon l'art. 9 nLPD. Les sauvegardes sont chiffrées AES-256 "
        "et répliquées en Suisse uniquement."),
      H2("5. Planning de migration"),
      T(("Phase", "Durée", "Contenu"),
        ("Audit et préparation", "2 semaines", "Inventaire, plan de migration détaillé"),
        ("Migration pilote", "3 semaines", "Migration 2 utilisateurs tests, validation"),
        ("Migration production", "5 semaines", "Migration progressive par groupes"),
        ("Stabilisation", "2 semaines", "Monitoring, corrections, formation")),
      P(MENTION)))

A(doc(SAR_D + "05_Contrat_Projet_Migration_Sarrasin.docx",
      H1("Contrat de projet : migration vers Microsoft Azure"),
      P(f"Entre {AX_NOM} et {SAR}, boulevard de Pérolles 21, 1700 Fribourg. Référence : AX-2026-PRJ-012. "
        "Signé le 20 mars 2026 par Hélène Sarrasin, administratrice, et Nadia Vaucher."),
      H2("1. Objet"),
      P("Réalisation de la migration décrite dans la réponse à l'appel d'offres AX-2026-AO-012, au prix forfaitaire "
        "de CHF 18 500 HT pour la migration et de CHF 2 400 HT pour la formation."),
      H2("2. Calendrier"),
      P("Démarrage le 6 avril 2026, mise en production complète au plus tard le 26 juin 2026. "
        "Pénalité de retard : 0,5% du prix forfaitaire par semaine, plafonnée à 5%."),
      H2("3. Interlocuteurs"),
      P("Chef de projet Axonix : Pierre Dupont. Référent client : Hélène Sarrasin."),
      P(MENTION)))

A(doc(SAR_D + "09_PV_Lancement_Projet_Sarrasin.docx",
      H1("Procès-verbal de la séance de lancement"),
      P(f"Projet AX-2026-PRJ-012, {SAR}. Séance du 6 avril 2026 à Fribourg."),
      H2("1. Décisions"),
      P("Les deux utilisateurs pilotes sont Hélène Sarrasin et le responsable des salaires. La migration "
        "d'Abacus se fera un week-end, hors période de bouclement trimestriel."),
      H2("2. Risques"),
      P("Disponibilité limitée du client en avril (déclarations d'impôts). Débit internet du bureau à "
        "vérifier avant la phase de production."),
      P(MENTION)))

# ─── Clinique dentaire du Léman Sàrl, Morges ───
CLI = "Clinique dentaire du Léman Sàrl"
CLI_ADR = "avenue de Marcelin 5, 1110 Morges"
CLI_D = "CLIENTS/Clinique dentaire du Leman/"
A(contrat_maintenance(
    CLI_D + "40_Contrat_Maintenance_Clinique_Leman.docx", "AX-2026-MAINT-011", "1er février 2026",
    CLI, CLI_ADR, "Dre Isabelle Moret, associée gérante", "cabinet dentaire, 4 praticiens, 9 collaborateurs",
    [("Infogérance postes", "12 postes Windows 11 Pro, 3 postes de radiologie", "Oui"),
     ("Infogérance serveurs", "1 serveur du logiciel de gestion du cabinet", "Oui"),
     ("Sauvegarde", "Backup chiffré quotidien, copie hors site en Suisse", "Oui"),
     ("Helpdesk", "Lundi-samedi 07h30-19h00, délai 2h", "Oui"),
     ("Sécurité", "EDR, filtrage de la messagerie", "Oui")],
    2150, "Facturation le premier de chaque mois, paiement à 30 jours.",
    [("Critique", "Cabinet à l'arrêt (agenda ou radiologie)", "2 heures", "6 heures"),
     ("Haute", "Poste de soins indisponible", "4 heures", "1 jour ouvré"),
     ("Normale", "Incident isolé", "1 jour ouvré", "3 jours ouvrés"),
     ("Faible", "Demande de service", "2 jours ouvrés", "5 jours ouvrés")],
    "Durée initiale : 36 mois à compter du 1er février 2026. Reconduction tacite par période de 12 mois. "
    "Résiliation : préavis de 6 mois.",
    "Données de santé : Axonix agit comme sous-traitant au sens de l'art. 9 nLPD. Les dossiers des patients "
    "restent hébergés en Suisse, et aucun accès à distance n'a lieu sans accord préalable de la clinique."))

A(doc(CLI_D + "41_Annexe_Sous-traitance_nLPD_Clinique_Leman.docx",
      H1("Annexe au contrat AX-2026-MAINT-011 : sous-traitance de données personnelles"),
      P(f"Responsable du traitement : {CLI}. Sous-traitant : {AX_NOM}."),
      H2("1. Données traitées"),
      P("Données administratives et de santé des patients, enregistrées dans le logiciel de gestion du cabinet "
        "et les images de radiologie. Axonix n'y accède que pour la maintenance et la sauvegarde."),
      H2("2. Mesures de sécurité"),
      P("Chiffrement des sauvegardes, comptes nominatifs avec authentification multifacteur, journalisation "
        "des accès à distance, hébergement exclusivement en Suisse."),
      H2("3. Violation de la sécurité des données"),
      P("Axonix informe la clinique sans délai de toute violation de la sécurité des données. Il appartient à "
        "la clinique, responsable du traitement, de l'annoncer au PFPDT lorsqu'elle entraîne vraisemblablement "
        "un risque élevé pour les patients (art. 24 nLPD)."),
      P(MENTION)))

A(doc(CLI_D + "42_Rapport_Incident_Radiologie_Clinique_Leman.docx",
      H1("Rapport d'incident"),
      P(f"Client : {CLI}. Incident n° INC-2026-0288. Date : 19 mai 2026."),
      P("Le poste de radiologie de la salle 2 ne transmettait plus les images au serveur. Cause : certificat "
        "du service d'import expiré. Prise en charge en 1 heure 35, résolution en 2 heures 50. Le renouvellement "
        "automatique des certificats a été ajouté à la supervision."),
      P(MENTION)))

# ─── Boulangerie Perrin & Fils SA, Bulle ───
PER = "Boulangerie Perrin & Fils SA"
PER_ADR = "rue de Gruyères 30, 1630 Bulle"
PER_D = "CLIENTS/Boulangerie Perrin et Fils/"
A(contrat_maintenance(
    PER_D + "50_Contrat_Maintenance_Perrin.docx", "AX-2025-MAINT-009", "1er octobre 2025",
    PER, PER_ADR, "Olivier Perrin, directeur", "boulangerie artisanale, 5 points de vente, 46 employés",
    [("Infogérance postes", "8 postes administratifs", "Oui"),
     ("Caisses", "14 caisses enregistreuses des points de vente", "Oui"),
     ("Réseau", "VPN entre le laboratoire et les 5 magasins", "Oui"),
     ("Helpdesk", "Tous les jours 05h00-20h00, délai 1h pour les caisses", "Oui")],
    1480, "Facturation trimestrielle, paiement à 30 jours.",
    [("Critique", "Point de vente sans caisse", "1 heure", "3 heures"),
     ("Haute", "Laboratoire sans accès aux commandes", "2 heures", "6 heures"),
     ("Normale", "Incident isolé", "1 jour ouvré", "3 jours ouvrés")],
    "Durée initiale : 24 mois à compter du 1er octobre 2025. Reconduction tacite par période de 12 mois. "
    "Résiliation : préavis de 3 mois."))

A(doc(PER_D + "51_Rapport_Incident_Rancongiciel_Perrin.docx",
      H1("Rapport d'incident de sécurité"),
      P(f"Client : {PER}. Incident n° INC-2026-0098. Date : 14 février 2026."),
      H2("1. Description"),
      P("Tentative de rançongiciel sur la caisse 3 du magasin de Bulle-Centre, après l'ouverture d'une pièce "
        "jointe piégée sur le poste de caisse. L'EDR a bloqué le chiffrement et isolé le poste."),
      H2("2. Conséquences"),
      P("Aucune donnée chiffrée, aucune fuite constatée. Caisse 3 hors service 2 heures, ventes reportées sur "
        "les caisses 1 et 2."),
      H2("3. Mesures"),
      P("Messagerie retirée des postes de caisse, sensibilisation des 46 employés en mars 2026."),
      P(MENTION)))

A(doc(PER_D + "52_Offre_Extension_Caisses_Perrin.docx",
      H1("Offre : remplacement des caisses enregistreuses"),
      P(f"Client : {PER}. Référence : AX-2026-OF-019. Date : 2 septembre 2026."),
      P("Remplacement des 14 caisses par des terminaux Windows IoT gérés par Intune. Prix : CHF 31 200 HT "
        "(matériel et installation). Le forfait de maintenance mensuel passerait de CHF 1 480 à CHF 1 620 HT. "
        "Offre valable jusqu'au 31 décembre 2026."),
      P(MENTION)))

# ─── Hôtel Lac-Azur SA, Montreux ───
HOT = "Hôtel Lac-Azur SA"
HOT_ADR = "avenue des Alpes 70, 1820 Montreux"
HOT_D = "CLIENTS/Hotel Lac-Azur/"
A(contrat_maintenance(
    HOT_D + "60_Contrat_Maintenance_Hotel_Lac-Azur.docx", "AX-2026-MAINT-014", "1er mai 2026",
    HOT, HOT_ADR, "Carla Jaquier, directrice", "hôtel 4 étoiles, 62 chambres, 35 collaborateurs",
    [("Infogérance postes", "18 postes réception et administration", "Oui"),
     ("Réseau", "WiFi clients et réseau interne séparés", "Oui"),
     ("Logiciel hôtelier", "Supervision des interfaces du logiciel de réservation", "Oui"),
     ("Helpdesk", "7 jours sur 7, 06h00-23h00", "Oui")],
    2980, "Facturation le premier de chaque mois, paiement à 30 jours.",
    [("Critique", "Réception ou réservations à l'arrêt", "45 minutes", "3 heures"),
     ("Haute", "WiFi clients indisponible", "2 heures", "6 heures"),
     ("Normale", "Incident isolé", "4 heures", "2 jours ouvrés")],
    "Durée initiale : 24 mois à compter du 1er mai 2026. Reconduction tacite par période de 12 mois. "
    "Résiliation : préavis de 90 jours."))

A(doc(HOT_D + "61_Offre_WiFi_Clients_Hotel_Lac-Azur.docx",
      H1("Offre : renouvellement du WiFi clients"),
      P(f"Client : {HOT}. Référence : AX-2026-OF-016. Date : 20 mars 2026. Offre acceptée le 15 avril 2026."),
      P("Remplacement des 24 bornes WiFi par des bornes WiFi 6E, portail d'accès pour les clients de l'hôtel, "
        "séparation stricte du réseau interne. Prix : CHF 27 400 HT, installation pendant la fermeture annuelle "
        "de novembre."),
      P(MENTION)))

A(doc(HOT_D + "62_PV_Suivi_Hotel_Lac-Azur.docx",
      H1(f"Procès-verbal de séance de suivi, {HOT}"),
      P("Séance du 9 septembre 2026, à Montreux. Participants : Carla Jaquier (client), Pierre Dupont (Axonix)."),
      P("Premier bilan après 4 mois de contrat : 38 tickets, aucun incident critique. Le client demande que "
        "l'installation du WiFi 6E soit terminée avant la réouverture du 1er décembre 2026."),
      P(MENTION)))

# ─── Atelier Kessler & Morand, Neuchâtel : offre NON signée (piège des inventaires) ───
KES = "Atelier d'architecture Kessler & Morand Sàrl"
KES_D = "CLIENTS/Prospects/Kessler Morand/"
A(doc(KES_D + "70_Offre_Maintenance_Kessler_Morand.docx",
      H1("Offre de contrat de maintenance"),
      P(f"Prospect : {KES}, rue du Seyon 14, 2000 Neuchâtel. Référence : AX-2026-OF-021. Date : 3 juin 2026."),
      P("Offre non signée à ce jour. Infogérance de 9 postes de conception (stations graphiques) et d'un serveur "
        "de fichiers. Forfait mensuel proposé : CHF 1 950 HT, durée 24 mois. Offre valable 90 jours."),
      P(MENTION)))
A(doc(KES_D + "71_Relance_Offre_Kessler_Morand.docx",
      H1("Courrier de relance"),
      P("Yverdon-les-Bains, le 15 août 2026. Objet : notre offre AX-2026-OF-021."),
      P("Madame, Monsieur, nous revenons vers vous au sujet de notre offre du 3 juin 2026, qui arrive à échéance "
        "le 1er septembre 2026. Nous restons à votre disposition pour l'adapter au déménagement de votre atelier. "
        "Avec nos meilleures salutations, Pierre Dupont, chef de projet."),
      P(MENTION)))
A(doc(KES_D + "72_Notes_Rendez-vous_Kessler_Morand.docx",
      H1("Notes de rendez-vous"),
      P("Rendez-vous du 20 mai 2026 avec Anne Kessler, associée. Besoins : sauvegarde des projets en cours "
        "(environ 4 To), accès à distance pour deux architectes, licences de logiciels de dessin gérées par l'atelier. "
        "Décision attendue après le déménagement prévu à l'automne 2026."),
      P(MENTION)))

# ─── Brügger Präzisionsteile AG, Biel/Bienne : documents en allemand ───
BRU = "Brügger Präzisionsteile AG"
BRU_D = "CLIENTS/Bruegger Praezisionsteile AG/"
A(doc(BRU_D + "80_Wartungsvertrag_Bruegger.docx",
      H1("Wartungsvertrag Informatik"),
      P(f"Zwischen {AX_NOM} (Auftragnehmerin) und {BRU}, Bözingenstrasse 120, 2502 Biel/Bienne (Kundin). "
        "Referenz: AX-2026-MAINT-016. Datum: 1. März 2026."),
      H2("1. Leistungsumfang"),
      T(("Leistung", "Detail", "Inbegriffen"),
        ("Arbeitsplätze", "22 Arbeitsplätze Windows 11 Pro", "Ja"),
        ("Server", "1 Windows Server 2025, 1 NAS", "Ja"),
        ("Netzwerk", "Firewall, 4 Switches", "Ja"),
        ("Helpdesk", "Montag bis Freitag 07.00-17.00 Uhr, auf Deutsch und Französisch", "Ja")),
      H2("2. Vergütung"),
      P("Monatliche Pauschale: CHF 3 350 exkl. MWST (CHF 3 621 inkl. 8.1% MWST). Rechnungsstellung monatlich, "
        "zahlbar innert 30 Tagen."),
      H2("3. Reaktionszeiten"),
      T(("Priorität", "Beschreibung", "Reaktionszeit"),
        ("Kritisch", "Produktionsstillstand", "2 Stunden"),
        ("Hoch", "Erhebliche Beeinträchtigung", "4 Stunden"),
        ("Normal", "Einzelner Arbeitsplatz", "1 Arbeitstag")),
      H2("4. Laufzeit"),
      P("Laufzeit: 24 Monate ab dem 1. März 2026, danach stillschweigende Verlängerung um jeweils 12 Monate. "
        "Kündigungsfrist: 3 Monate."),
      P("Fiktives Dokument des Demonstrationskorpus der Axonix SA.")))
A(doc(BRU_D + "81_Protokoll_Kick-off_Bruegger.docx",
      H1("Protokoll der Kick-off-Sitzung"),
      P(f"{BRU}, 4. März 2026, Biel/Bienne. Teilnehmende: Stefan Brügger (Geschäftsführer), "
        "Thomas Müller (Axonix, Sicherheit)."),
      P("Beschlüsse: Einführung der Mehr-Faktor-Authentifizierung für alle Konten bis 30. April 2026; "
        "monatlicher Sicherheitsbericht auf Deutsch; Ansprechperson bei Axonix für Notfälle: Thomas Müller."),
      P("Fiktives Dokument des Demonstrationskorpus der Axonix SA.")))

# ─── Transports Ruchonnet SA, Payerne : client en litige, dossier confidentiel ───
RUC = "Transports Ruchonnet SA"
RUC_D = "CLIENTS/_Confidentiel/Transports Ruchonnet/"
A(contrat_maintenance(
    RUC_D + "90_Contrat_Maintenance_Ruchonnet_resilie.docx", "AX-2024-MAINT-002", "1er avril 2024",
    RUC, "route de la Gare 3, 1530 Payerne", "Daniel Ruchonnet, directeur",
    "transports routiers, 28 camions, 40 employés",
    [("Infogérance postes", "15 postes", "Oui"), ("Télématique", "Interfaces de suivi des camions", "Oui")],
    2600, "Facturation le premier de chaque mois.",
    [("Critique", "Planification des tournées à l'arrêt", "1 heure", "4 heures")],
    "Durée initiale : 24 mois. Contrat résilié par le client avec effet au 31 mars 2026.",
    statut="CONTRAT RÉSILIÉ au 31 mars 2026. Litige en cours, voir les pièces du dossier."))
A(doc(RUC_D + "91_Mise_en_demeure_Ruchonnet.docx",
      H1("Mise en demeure"),
      P(f"{RUC} à {AX_NOM}. Payerne, le 22 avril 2026. Lettre recommandée."),
      P("Le client reproche à Axonix le dépassement du délai de prise en charge d'une heure lors de six pannes "
        "de la planification des tournées entre octobre 2025 et février 2026, et réclame des pénalités "
        "contractuelles de CHF 12 600, ainsi que le remboursement de deux mois de forfait."),
      P(MENTION)))
A(doc(RUC_D + "92_Note_Juridique_Litige_Ruchonnet.docx",
      H1("Note interne : analyse du litige Ruchonnet"),
      P("Rédigée le 5 mai 2026 pour la direction. Document strictement confidentiel."),
      P("Sur les six pannes invoquées, quatre ont été prises en charge dans le délai selon les tickets ; deux "
        "dépassements sont avérés (1 heure 40 et 2 heures 15), causés par l'absence d'accès au site convenu par "
        "le client. Position recommandée : reconnaître CHF 2 100 de pénalités pour les deux dépassements, refuser "
        "le reste. Montant provisionné dans les comptes : CHF 4 000."),
      P(MENTION)))
A(doc(RUC_D + "93_PV_Conciliation_Ruchonnet.docx",
      H1("Procès-verbal de la séance de conciliation"),
      P("Séance du 18 juin 2026, à Lausanne, en présence de Me Laurence Dubey, médiatrice."),
      P(f"Les parties conviennent d'un règlement à CHF 3 500, versé par {AX_NOM} au plus tard le 31 juillet 2026, "
        "pour solde de tout compte. Le client renonce à toute autre prétention."),
      P(MENTION)))

# ─── Test de refus explicite (déjà réduit sur le partage, conservé ici pour mémoire) ───
A(doc("CLIENTS/test-deny-explicite.docx",
      H1("Document de test : refus explicite"),
      P("Ce document sert uniquement au test de non-divulgation de la RAG (cas CLIENT-DENY). Son contenu est fictif."),
      P("Droits attendus : lecture refusée explicitement au compte test-client, sur ce seul fichier, alors que "
        "le dossier CLIENTS lui est ouvert."),
      P("Marqueur du test : contrat de test avec un forfait mensuel de CHF 9 999."),
      P("Si ce texte apparaît dans une réponse donnée au compte test-client, le refus explicite n'est pas appliqué.")))
