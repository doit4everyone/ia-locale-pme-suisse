"""Dossiers DIRECTION et RH."""
from spec_base import *

DOCS = []
A = DOCS.append
D = "DIRECTION/"

A(doc(D + "01_Plan_Strategique_Axonix_2026-2028.docx",
      H1("Plan stratégique Axonix SA 2026-2028"),
      P("Document classifié Interne. Axonix SA, Yverdon-les-Bains (VD), Suisse. Validé par le Conseil "
        "d'administration le 15 mars 2026."),
      H2("1. Présentation de l'entreprise"),
      P("Axonix SA est une PME spécialisée dans l'intégration de systèmes informatiques pour les PME romandes. "
        "Fondée en 2018, elle emploie 23 collaborateurs répartis entre Yverdon-les-Bains (siège), Lausanne et "
        "Fribourg. Le chiffre d'affaires 2025 s'établit à CHF 3,2 millions, en hausse de 12% par rapport à 2024."),
      H2("2. Orientations stratégiques 2026-2028"),
      P("Axonix SA poursuit trois axes stratégiques pour la période 2026-2028 :"),
      P("Axe 1 : Développement de l'offre IA locale pour PME suisses. Axonix SA ambitionne de devenir la "
        "référence romande en matière de déploiement d'IA locale respectueuse de la nLPD, avec un objectif de "
        "15 clients PME accompagnés d'ici fin 2026 et 40 d'ici fin 2028."),
      P("Axe 2 : Renforcement de la practice cybersécurité. Recrutement de deux ingénieurs sécurité d'ici "
        "septembre 2026. Objectif de certification ISO 27001 pour le service infogérance d'ici 2027."),
      P("Axe 3 : Expansion géographique. Ouverture d'un bureau à Neuchâtel au T3 2026 pour couvrir le canton "
        "de Neuchâtel et la région biennoise."),
      H2("3. Objectifs financiers"),
      T(("Indicateur", "2025 (réalisé)", "2026 (objectif)", "2028 (objectif)"),
        ("Chiffre d'affaires", "CHF 3,2 M", "CHF 3,9 M", "CHF 5,5 M"),
        ("Marge brute", "42%", "45%", "48%"),
        ("Effectif", "23 ETP", "27 ETP", "35 ETP"),
        ("Clients actifs", "31", "42", "65")),
      H2("4. Risques identifiés"),
      P("Risque 1 : Tension sur le marché de l'emploi IT en Suisse romande. Mitigation : programme de formation "
        "interne et partenariat avec la HEIG-VD."),
      P("Risque 2 : Évolution réglementaire nLPD et EU AI Act. Mitigation : veille juridique mensuelle, "
        "partenariat avec un cabinet d'avocats spécialisé."),
      P("Risque 3 : Dépendance à trois clients majeurs représentant 45% du CA. Mitigation : programme de "
        "diversification clients, objectif < 30% de concentration d'ici 2027."),
      P(MENTION)))

PV_PART = T(("Nom", "Fonction", "Présence"),
            ("Bernard Chollet", "Président du CA", "Présent"),
            ("Sophie Etienne", "Administratrice", "Présente"),
            ("Luc Bonvin", "Administrateur indépendant", "Présent"),
            ("Nadia Vaucher", "Directrice générale", "Présente (sans droit de vote)"))

A(doc(D + "02_PV_CA_Mars_2026.docx",
      H1("Procès-verbal du Conseil d'administration"),
      P("Axonix SA, séance du 15 mars 2026, siège social, Yverdon-les-Bains."),
      H2("Participants"), PV_PART,
      H2("1. Approbation des comptes 2025"),
      P("Le CA approuve les comptes annuels 2025 à l'unanimité. Le chiffre d'affaires 2025 s'établit à "
        "CHF 3,2 millions (budget : CHF 3,0 millions). Le résultat net est de CHF 287 000, soit 9% du CA. "
        "Les comptes sont soumis à l'organe de révision (Fiduciaire Matthey & Associés, Fribourg)."),
      H2("2. Validation du plan stratégique 2026-2028"),
      P("Le CA valide le plan stratégique présenté par la direction. Les trois axes sont approuvés. Le budget "
        "d'investissement de CHF 280 000 pour 2026 est accordé, dont CHF 120 000 pour le recrutement et "
        "CHF 95 000 pour l'équipement informatique (serveurs IA)."),
      H2("3. Décisions"),
      P("Décision 1 : Approbation des comptes 2025. Vote : 3 pour, 0 contre, 0 abstention."),
      P("Décision 2 : Validation plan stratégique 2026-2028 et budget d'investissement. Vote : 3 pour, 0 contre, 0 abstention."),
      P("Décision 3 : Autorisation d'ouverture du bureau de Neuchâtel au T3 2026. Vote : 3 pour, 0 contre, 0 abstention."),
      H2("4. Prochaine séance"),
      P("La prochaine séance du CA est fixée au 20 juin 2026."),
      P("Fait à Yverdon-les-Bains, le 15 mars 2026. Signé : Bernard Chollet, Président du CA."),
      P(MENTION)))

A(doc(D + "03_PV_CA_Decembre_2025.docx",
      H1("Procès-verbal du Conseil d'administration"),
      P("Axonix SA, séance du 12 décembre 2025, siège social, Yverdon-les-Bains."),
      H2("Participants"), PV_PART,
      H2("1. Budget 2026"),
      P("Présentation du budget prévisionnel 2026 : chiffre d'affaires visé de CHF 3,9 millions. Le CA demande "
        "une version révisée intégrant le recrutement de deux ingénieurs sécurité, pour approbation en mars 2026."),
      H2("2. Litige Transports Ruchonnet"),
      P("La direction informe le CA de la réclamation du client Transports Ruchonnet. Le CA charge la direction "
        "d'une analyse juridique et d'une provision prudente."),
      H2("3. Décisions"),
      P("Décision 1 : Report de l'approbation du budget 2026 au 15 mars 2026. Vote : 3 pour."),
      P("Décision 2 : Octroi d'une prime de fin d'année de 3% de la masse salariale. Vote : 2 pour, 1 abstention."),
      P(MENTION)))

A(doc(D + "04_PV_CA_Juin_2026.docx",
      H1("Procès-verbal du Conseil d'administration"),
      P("Axonix SA, séance du 20 juin 2026, siège social, Yverdon-les-Bains."),
      H2("Participants"), PV_PART,
      H2("1. Offre IA locale"),
      P("La direction présente le premier projet pilote d'IA locale, réalisé pour la Clinique dentaire du Léman. "
        "Le CA approuve l'achat d'un serveur GPU de démonstration pour CHF 68 000, imputé sur le budget "
        "d'investissement 2026."),
      H2("2. Bureau de Neuchâtel"),
      P("Bail signé pour des locaux de 140 m² au faubourg du Lac 31, Neuchâtel. Ouverture fixée au "
        "1er septembre 2026, avec deux collaborateurs."),
      H2("3. Litige Ruchonnet"),
      P("La conciliation du 18 juin 2026 a abouti à un règlement de CHF 3 500, dans la limite de la "
        "provision de CHF 4 000. Le CA en prend acte."),
      H2("4. Décisions"),
      P("Décision 1 : Achat du serveur GPU, CHF 68 000. Vote : 3 pour."),
      P("Décision 2 : Ouverture du bureau de Neuchâtel le 1er septembre 2026. Vote : 3 pour."),
      P(MENTION)))

A(doc(D + "05_PV_CA_Septembre_2026.docx",
      H1("Procès-verbal du Conseil d'administration"),
      P("Axonix SA, séance du 25 septembre 2026, siège social, Yverdon-les-Bains."),
      H2("Participants"), PV_PART,
      H2("1. Résultats du premier semestre 2026"),
      P("Chiffre d'affaires du premier semestre : CHF 1,86 million, soit 48% du budget annuel. Résultat "
        "intermédiaire conforme aux prévisions."),
      H2("2. Recrutement"),
      P("Un ingénieur sécurité a rejoint l'entreprise le 1er septembre 2026 ; le second poste reste ouvert. "
        "Le poste d'ingénieur IA / MLOps est pourvu au 1er novembre 2026."),
      H2("3. Décisions"),
      P("Décision 1 : Lancement de la démarche ISO 27001 avec un organisme de certification, budget CHF 22 000. "
        "Vote : 3 pour."),
      P(MENTION)))

A(doc(D + "06_Rapport_Trimestriel_T1_2026.docx",
      H1("Rapport trimestriel de direction, T1 2026"),
      P("Rédigé par Nadia Vaucher, 10 avril 2026. Diffusion : Conseil d'administration."),
      T(("Indicateur", "T1 2026", "Objectif T1"),
        ("Chiffre d'affaires", "CHF 902 000", "CHF 920 000"),
        ("Nouveaux contrats", "2 (Clinique dentaire du Léman, Brügger Präzisionsteile)", "2"),
        ("Tickets traités", "412", "-"),
        ("Respect des délais SLA", "96%", "95%")),
      P("Faits marquants : incident critique chez Baumont Industries le 3 mars 2026, tentative de rançongiciel "
        "bloquée chez la Boulangerie Perrin & Fils le 14 février 2026, signature du projet de migration de "
        "Sarrasin Fiduciaire le 20 mars 2026."),
      P(MENTION)))

A(doc(D + "07_Rapport_Trimestriel_T2_2026.docx",
      H1("Rapport trimestriel de direction, T2 2026"),
      P("Rédigé par Nadia Vaucher, 8 juillet 2026."),
      T(("Indicateur", "T2 2026", "Objectif T2"),
        ("Chiffre d'affaires", "CHF 958 000", "CHF 960 000"),
        ("Nouveaux contrats", "1 (Hôtel Lac-Azur)", "2"),
        ("Tickets traités", "438", "-"),
        ("Respect des délais SLA", "97%", "95%")),
      P("Faits marquants : migration de Sarrasin Fiduciaire terminée le 19 juin 2026, une semaine avant "
        "l'échéance ; règlement du litige Ruchonnet par conciliation ; offre envoyée à l'atelier Kessler & Morand, "
        "sans réponse à ce jour."),
      P(MENTION)))

A(doc(D + "08_Rapport_Trimestriel_T3_2026.docx",
      H1("Rapport trimestriel de direction, T3 2026"),
      P("Rédigé par Nadia Vaucher, 6 octobre 2026."),
      T(("Indicateur", "T3 2026", "Objectif T3"),
        ("Chiffre d'affaires", "CHF 941 000", "CHF 990 000"),
        ("Nouveaux contrats", "0", "2"),
        ("Tickets traités", "455", "-"),
        ("Respect des délais SLA", "95%", "95%")),
      P("Faits marquants : ouverture du bureau de Neuchâtel le 1er septembre 2026 ; l'offre Kessler & Morand "
        "a expiré sans signature ; retard commercial à rattraper au quatrième trimestre."),
      P(MENTION)))

A(doc(D + "09_Portefeuille_Clients_2026.docx",
      H1("Portefeuille clients 2026"),
      P("Liste des contrats de maintenance actifs au 1er octobre 2026. Document interne de la direction."),
      T(("Client", "Lieu", "Référence", "Forfait mensuel HT (CHF)", "Échéance initiale"),
        ("Baumont Industries SA", "Sainte-Croix", "AX-2025-MAINT-003", "4 200", "30 juin 2027"),
        ("Étude Rochat & Associés", "Lausanne", "AX-2026-MAINT-007", "3 840", "31 décembre 2027"),
        ("Boulangerie Perrin & Fils SA", "Bulle", "AX-2025-MAINT-009", "1 480", "30 septembre 2027"),
        ("Clinique dentaire du Léman Sàrl", "Morges", "AX-2026-MAINT-011", "2 150", "31 janvier 2029"),
        ("Brügger Präzisionsteile AG", "Biel/Bienne", "AX-2026-MAINT-016", "3 350", "28 février 2028"),
        ("Hôtel Lac-Azur SA", "Montreux", "AX-2026-MAINT-014", "2 980", "30 avril 2028")),
      P("Projet hors maintenance : Sarrasin Fiduciaire SA (migration Azure, terminée en juin 2026). "
        "Contrat résilié : Transports Ruchonnet SA (31 mars 2026). Prospect : atelier Kessler & Morand "
        "(offre expirée)."),
      P(MENTION)))

A(doc(D + "10_Note_Ouverture_Bureau_Neuchatel.docx",
      H1("Note de direction : ouverture du bureau de Neuchâtel"),
      P("Diffusion : direction. Date : 1er juillet 2026."),
      P("Adresse : faubourg du Lac 31, 2000 Neuchâtel. Surface : 140 m². Loyer : CHF 3 150 par mois charges "
        "comprises. Ouverture le 1er septembre 2026. Équipe : Valérie Beraz (responsable du bureau, 3 jours par "
        "semaine) et un technicien recruté localement."),
      P("Objectifs : 6 nouveaux clients dans le canton de Neuchâtel et la région biennoise d'ici fin 2027."),
      P(MENTION)))

A(doc(D + "11_Politique_Tarifaire_2026.docx",
      H1("Politique tarifaire 2026"),
      P("Approuvée par la direction le 15 janvier 2026."),
      T(("Prestation", "Tarif HT (CHF)"),
        ("Heure d'ingénieur", "165"),
        ("Heure de technicien", "125"),
        ("Intervention d'urgence hors heures ouvrées (majoration)", "+50%"),
        ("Forfait maintenance par poste et par mois (base)", "95")),
      P("Les remises sur forfait sont limitées à 10% sans accord de la directrice générale. Toute remise liée "
        "à un engagement plus long (par exemple 36 mois) doit être validée par la direction."),
      P(MENTION)))

A(doc(D + "12_Analyse_Concurrence_2026.docx",
      H1("Analyse de la concurrence"),
      P("Note interne, mars 2026."),
      P("Le marché romand de l'infogérance pour PME compte une quarantaine d'acteurs comparables. Axonix se "
        "distingue par ses délais de prise en charge contractuels et son offre d'IA locale. Points faibles : "
        "notoriété limitée hors du canton de Vaud et absence de certification ISO 27001."),
      P(MENTION)))

# ─────────────────────────────── RH ───────────────────────────────
R = "RH/"
A(doc(R + "POLITIQUE RH/10_Politique_RH_Axonix_v3.1.docx",
      H1("Politique des ressources humaines"),
      P("Axonix SA, version 3.1, validée par la direction le 1er janvier 2026. Document interne, ne pas diffuser."),
      H2("1. Recrutement"),
      P("Tout recrutement fait l'objet d'une validation par la direction avant publication. Les postes sont publiés "
        "sur le site Axonix SA, Jobs.ch et LinkedIn. La procédure standard comprend : analyse des candidatures "
        "(J+7), entretien téléphonique de présélection (30 min), entretien technique avec le responsable d'équipe, "
        "entretien final avec la direction."),
      P("Délai moyen de recrutement : 6 semaines. Période d'essai standard : 3 mois."),
      H2("2. Rémunération"),
      P("Les salaires sont révisés chaque janvier selon les performances individuelles (évaluation annuelle) et "
        "l'évolution du marché. L'enveloppe de révision salariale est définie par le CA lors de l'approbation du budget."),
      T(("Fonction", "Salaire annuel brut (fourchette)", "Révision annuelle"),
        ("Technicien IT junior", "CHF 65 000 à 75 000", "Janvier"),
        ("Ingénieur systèmes", "CHF 85 000 à 100 000", "Janvier"),
        ("Chef de projet", "CHF 95 000 à 115 000", "Janvier"),
        ("Directeur technique", "CHF 120 000 à 140 000", "Janvier")),
      H2("3. Temps de travail et congés"),
      P("Durée hebdomadaire : 42 heures. Solde annuel de vacances : 25 jours (dès 5 ans d'ancienneté : 27 jours). "
        "Jours fériés : ceux du canton du lieu de travail (Vaud, Fribourg ou Neuchâtel). Compensation des heures "
        "supplémentaires : en temps dans les 3 mois ou rémunération au taux horaire majoré de 25%."),
      H2("4. Formation continue"),
      P("Budget formation annuel par collaborateur : CHF 3 000. Les certifications Microsoft, AWS et cybersécurité "
        "sont prioritaires. Chaque collaborateur établit son plan de formation en début d'année avec son responsable. "
        "Les formations validées par la direction sont prises en charge à 100%."),
      H2("5. Télétravail"),
      P("Le télétravail est autorisé jusqu'à 2 jours par semaine après la période d'essai, selon le règlement "
        "du télétravail. Une présence minimale de 3 jours au bureau est requise."),
      P(MENTION)))

A(doc(R + "POLITIQUE RH/12_Reglement_Teletravail.docx",
      H1("Règlement du télétravail"),
      P("Axonix SA, en vigueur dès le 1er mars 2026."),
      P("Le télétravail est possible jusqu'à 2 jours par semaine, après la période d'essai et avec l'accord du "
        "responsable. Une indemnité forfaitaire de CHF 40 par mois couvre les frais de connexion. L'accès se fait "
        "exclusivement par le VPN de l'entreprise, avec authentification multifacteur. Les documents clients ne "
        "sont jamais imprimés au domicile."),
      P(MENTION)))

A(doc(R + "POLITIQUE RH/13_Reglement_Frais_Professionnels.docx",
      H1("Règlement des frais professionnels"),
      P("Axonix SA, en vigueur dès le 1er janvier 2026."),
      T(("Frais", "Remboursement"),
        ("Kilomètre en véhicule privé", "CHF 0.70"),
        ("Repas lors d'une intervention hors du lieu de travail", "CHF 30 au maximum"),
        ("Nuitée", "CHF 180 au maximum, sur justificatif")),
      P("Les notes de frais sont saisies avant le 5 du mois suivant et validées par le responsable."),
      P(MENTION)))

A(doc(R + "14_Registre_Personnel_2026.docx",
      H1("Registre du personnel 2026"),
      P("Axonix SA, document interne confidentiel. Mise à jour : 1er janvier 2026. Responsable : Nadia Vaucher, DG."),
      H2("Effectif au 1er janvier 2026 (extrait)"),
      T(("Nom", "Fonction", "Entrée", "Taux", "Statut"),
        ("Vaucher Nadia", "Directrice générale", "01.01.2018", "100%", "CDI"),
        ("Ferrara Marco", "Directeur technique", "15.03.2019", "100%", "CDI"),
        ("Beraz Valérie", "Ingénieure systèmes", "01.03.2023", "100%", "CDI"),
        ("Dupont Pierre", "Chef de projet senior", "01.06.2020", "100%", "CDI"),
        ("Sarrasin Élodie", "Technicienne IT", "01.09.2022", "80%", "CDI"),
        ("Müller Thomas", "Ingénieur sécurité", "01.01.2025", "100%", "CDI"),
        ("Pereira Ana", "Assistante de direction", "15.04.2021", "60%", "CDI"),
        ("Zbinden Claude", "Technicien IT junior", "01.08.2024", "100%", "CDI")),
      H2("Mouvements 2025"),
      P("Départs : Romain Favre (Technicien IT, départ volontaire le 30.06.2025). Entrées : Thomas Müller "
        "(Ingénieur sécurité, 01.01.2025). Claude Zbinden (Technicien IT junior, entré le 01.08.2024) figure "
        "désormais dans l'effectif."),
      H2("Absences et congés spéciaux 2025"),
      P("Congé maternité : Pereira Ana (16 semaines, T3 2025). Maladie longue durée : aucun cas en 2025. "
        "Formation longue durée : Müller Thomas (CAS Cybersécurité, HEIG-VD, 2025-2026, 20% du temps de travail)."),
      H2("Prévisions recrutement 2026"),
      P("Poste 1 : Ingénieur IA / MLOps (ouverture T1 2026, budget CHF 95 000 à 110 000). Poste 2 : Commercial IT "
        "(ouverture T2 2026, budget CHF 80 000 à 95 000 + commission). Les deux postes sont conditionnés à "
        "l'atteinte des objectifs CA T1 2026."),
      P(MENTION)))

def contrat_travail(fichier, nom_inverse, prenom_nom, ne_le, domicile, fonction, resp, lieu, entree,
                    salaire, taux="100%", conclu=None, f=False):
    ne = "née" if f else "né"; dom = "domiciliée" if f else "domicilié"
    mensuel = round(salaire / 12, 2)
    return doc(R + "CONTRATS DE TRAVAIL/" + fichier,
               H1("Contrat de travail individuel"),
               P(f"Entre Axonix SA (employeur) et {nom_inverse} (personne employée). Conclu à Yverdon-les-Bains le {conclu or entree}."),
               H2("1. Parties"),
               P(f"Employeur : Axonix SA, {AX_ADR}. Représentée par {DG}, Directrice générale."),
               P(f"Personne employée : {prenom_nom}, {ne} le {ne_le}, {dom} à {domicile}."),
               H2("2. Fonction et lieu de travail"),
               P(f"Fonction : {fonction}. Responsable hiérarchique : {resp}. Lieu principal de travail : {lieu}. "
                 "Télétravail : jusqu'à 2 jours par semaine autorisé."),
               H2("3. Entrée en service et durée"),
               P(f"Date d'entrée : {entree}. Contrat à durée indéterminée. Taux d'activité : {taux}. "
                 "Période d'essai : 3 mois."),
               H2("4. Rémunération"),
               P(f"Salaire annuel brut : CHF {chf(salaire)}. Versement mensuel : CHF {chf(mensuel)} (12 mensualités). "
                 "Révision salariale annuelle en janvier selon les modalités de la politique RH."),
               H2("5. Temps de travail"),
               P("Durée hebdomadaire : 42 heures (au prorata du taux d'activité). Horaire flexible entre 07h00 et "
                 "19h00, avec plage fixe 09h00-16h00. Vacances : 25 jours par année civile."),
               H2("6. Obligations de confidentialité"),
               P("La personne employée s'engage à respecter la confidentialité des informations clients et internes "
                 "d'Axonix SA pendant et après la durée du contrat."),
               H2("7. Résiliation"),
               P("Délai de congé : 1 mois pendant la période d'essai, 2 mois jusqu'à la fin de la 2e année de service, "
                 "3 mois dès la 3e année de service. La résiliation se fait par écrit pour la fin d'un mois."),
               P(MENTION))

A(contrat_travail("11_Contrat_Travail_Beraz_Valerie_RH.docx", "Beraz Valérie", "Valérie Beraz", "14 juin 1988",
                  "Yverdon-les-Bains (VD)", "Ingénieure systèmes et réseaux", "Directeur technique",
                  "siège Axonix SA, Yverdon-les-Bains", "1er mars 2023", 92000, f=True))
A(contrat_travail("15_Contrat_Travail_Ferrara_Marco_RH.docx", "Ferrara Marco", "Marco Ferrara", "3 février 1980",
                  "Lausanne (VD)", "Directeur technique", "Directrice générale", "siège Axonix SA, Yverdon-les-Bains",
                  "15 mars 2019", 132000))
A(contrat_travail("16_Contrat_Travail_Dupont_Pierre_RH.docx", "Dupont Pierre", "Pierre Dupont", "22 octobre 1984",
                  "Grandson (VD)", "Chef de projet senior", "Directeur technique", "siège Axonix SA, Yverdon-les-Bains",
                  "1er juin 2020", 108000))
A(contrat_travail("17_Contrat_Travail_Sarrasin_Elodie_RH.docx", "Sarrasin Élodie", "Élodie Sarrasin", "9 avril 1995",
                  "Fribourg (FR)", "Technicienne IT", "Directeur technique", "bureau de Fribourg",
                  "1er septembre 2022", 70400, taux="80%", f=True))
A(contrat_travail("18_Contrat_Travail_Muller_Thomas_RH.docx", "Müller Thomas", "Thomas Müller", "17 décembre 1990",
                  "Biel/Bienne (BE)", "Ingénieur sécurité", "Directeur technique", "bureau de Lausanne",
                  "1er janvier 2025", 104000))
A(contrat_travail("19_Contrat_Travail_Zbinden_Claude_RH.docx", "Zbinden Claude", "Claude Zbinden", "30 mai 2001",
                  "Yverdon-les-Bains (VD)", "Technicien IT junior", "Directeur technique",
                  "siège Axonix SA, Yverdon-les-Bains", "1er août 2024", 69500))

A(doc(R + "20_Plan_Formation_2026.docx",
      H1("Plan de formation 2026"),
      P("Document à usage interne. Validé par la direction le 20 janvier 2026. Budget total : CHF 81 000."),
      T(("Collaborateur", "Formation", "Échéance", "Coût (CHF)"),
        ("Müller Thomas", "CAS Cybersécurité, HEIG-VD (2e année)", "Juin 2026", "6 500"),
        ("Zbinden Claude", "Certification Microsoft MD-102 (Endpoint Administrator)", "Juin 2026", "2 800"),
        ("Beraz Valérie", "Certification Azure AZ-104", "Septembre 2026", "2 600"),
        ("Dupont Pierre", "Formation gestion de projet agile", "Avril 2026", "2 200"),
        ("Sarrasin Élodie", "Certification CompTIA Security+", "Novembre 2026", "1 900")),
      P(MENTION)))

A(doc(R + "21_Offre_Emploi_Ingenieur_IA.docx",
      H1("Offre d'emploi : ingénieur IA / MLOps (100%)"),
      P("Copie à usage interne de l'annonce publiée le 10 février 2026. Lieu : Yverdon-les-Bains, télétravail partiel possible."),
      P("Missions : déployer des modèles de langage locaux chez les clients PME, industrialiser les pipelines "
        "de recherche documentaire, documenter la conformité à la nLPD. Profil : 3 ans d'expérience en Python et "
        "en exploitation Linux, connaissance de Docker. Entrée en fonction : dès que possible."),
      P(MENTION)))

A(doc(R + "22_Certificat_Travail_Favre_Romain.docx",
      H1("Certificat de travail"),
      P("Copie à usage interne, dossier du personnel."),
      P("Axonix SA certifie que Monsieur Romain Favre a travaillé en qualité de technicien IT du 1er mai 2021 au "
        "30 juin 2025, à 100%."),
      P("Il a assuré le support aux utilisateurs et la maintenance des postes de nos clients. Il s'est acquitté "
        "de ses tâches à notre entière satisfaction. Il nous quitte de son plein gré, libre de tout engagement."),
      P("Yverdon-les-Bains, le 30 juin 2025. Nadia Vaucher, Directrice générale."),
      P(MENTION)))

# Évaluations : héritage coupé, lecture réservée au compte DRH (RH/EVALUATIONS)
def evaluation(fichier, nom, fonction, appreciation, objectifs):
    return doc(R + "EVALUATIONS/" + fichier,
               H1(f"Entretien annuel d'évaluation 2025 : {nom}"),
               P(f"Fonction : {fonction}. Entretien du 15 décembre 2025, conduit par Marco Ferrara. "
                 "Document confidentiel, accès réservé aux ressources humaines."),
               H2("1. Appréciation"), P(appreciation),
               H2("2. Objectifs 2026"), P(objectifs),
               P(MENTION))

A(evaluation("30_Evaluation_2025_Zbinden_Claude.docx", "Claude Zbinden", "Technicien IT junior",
             "Très bonne progression technique. Réactivité appréciée lors des astreintes de l'automne 2025. "
             "Documentation des interventions à améliorer.",
             "Obtenir la certification Microsoft MD-102 d'ici juin 2026. Rédiger trois articles de la base de "
             "connaissances du support. Révision salariale proposée : +4%."))
A(evaluation("31_Evaluation_2025_Beraz_Valerie.docx", "Valérie Beraz", "Ingénieure systèmes",
             "Pilier technique de l'équipe, très appréciée des clients. Charge de travail élevée au deuxième semestre.",
             "Se préparer à diriger un nouveau bureau, si son ouverture est décidée en 2026. "
             "Certification Azure AZ-104. "
             "Révision salariale proposée : +5%."))
A(evaluation("32_Evaluation_2025_Muller_Thomas.docx", "Thomas Müller", "Ingénieur sécurité",
             "Première année réussie. A mis en place les simulations d'hameçonnage trimestrielles.",
             "Terminer le CAS Cybersécurité. Préparer la démarche ISO 27001. Révision salariale proposée : +3%."))
