"""Corpus de démonstration Axonix SA (fictif), base commune : entreprise, personnes,
helpers de mise en forme. Chaque document est un dict :
  chemin : chemin relatif sous la racine du partage
  blocs  : liste de ("h1"|"h2"|"p"|"table", contenu)
"""

AX_NOM = "Axonix SA"
AX_ADR = "rue des Uttins 12, 1400 Yverdon-les-Bains"
AX_IBAN = "CH93 0076 2011 6238 5295 7"  # IBAN d'exemple publié (format), fictif ici
MENTION = "Document fictif du corpus de démonstration Axonix SA."

DG = "Nadia Vaucher"
DT = "Marco Ferrara"


def chf(n: float) -> str:
    """Montant suisse : 4 540 ou 3 845.50 (espace insécable fine remplacée par espace)."""
    if abs(n - round(n)) < 0.005:
        s = f"{int(round(n)):,}".replace(",", " ")
    else:
        s = f"{n:,.2f}".replace(",", " ")
    return s


def ttc(ht: float) -> float:
    return round(ht * 1.081 + 1e-9, 0)


def doc(chemin, *blocs):
    return {"chemin": chemin, "blocs": list(blocs)}


def H1(t): return ("h1", t)
def H2(t): return ("h2", t)
def P(t): return ("p", t)
def T(*rows): return ("table", [list(r) for r in rows])


def contrat_maintenance(chemin, ref, date, client, adresse, representant, activite,
                        services, forfait_ht, conditions, sla, duree, clauses=None,
                        titre="Contrat de maintenance informatique", statut=None):
    """Contrat de maintenance au format du corpus d'origine."""
    blocs = [H1(titre),
             P(f"Entre {AX_NOM} (prestataire) et {client} (client). Référence : {ref}. Date : {date}.")]
    if statut:
        blocs.append(P(statut))
    blocs += [
        H2("1. Parties"),
        P(f"Prestataire : {AX_NOM}, {AX_ADR}. Représentée par {DG}, Directrice générale."),
        P(f"Client : {client}, {adresse}. Représenté par {representant}. Activité : {activite}."),
        H2("2. Périmètre de la prestation"),
        T(("Service", "Détail", "Inclus"), *services),
        H2("3. Conditions financières"),
        P(f"Forfait mensuel : CHF {chf(forfait_ht)} HT (CHF {chf(ttc(forfait_ht))} TTC, TVA 8.1%). " + conditions),
        H2("4. Niveaux de service (SLA)"),
        T(("Priorité", "Définition", "Délai de prise en charge", "Délai de résolution"), *sla),
        H2("5. Durée et résiliation"),
        P(duree),
    ]
    if clauses:
        blocs += [H2("6. Clauses spécifiques"), P(clauses)]
    blocs.append(P(MENTION))
    return doc(chemin, *blocs)


def facture(chemin, numero, date, client, adresse, ref_contrat, periode, lignes, echeance):
    total_ht = sum(l[2] for l in lignes)
    tva = round(total_ht * 0.081, 2)
    rows = [("Désignation", "Période", "Montant HT (CHF)")] + [(l[0], l[1], chf(l[2])) for l in lignes]
    return doc(chemin,
               H1(f"Facture {numero}"),
               P(f"{AX_NOM}, {AX_ADR}. Date : {date}."),
               P(f"Destinataire : {client}, {adresse}. Contrat : {ref_contrat}. Période facturée : {periode}."),
               T(*rows),
               P(f"Total HT : CHF {chf(total_ht)}. TVA 8.1% : CHF {chf(tva)}. "
                 f"Total TTC : CHF {chf(round(total_ht + tva, 2))}."),
               P(f"Paiement à 30 jours, échéance le {echeance}, sur le compte {AX_IBAN}, en indiquant le numéro de facture."),
               P(MENTION))
