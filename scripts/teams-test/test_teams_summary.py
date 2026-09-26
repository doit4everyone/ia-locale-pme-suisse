"""
test_teams_summary.py : test de l'endpoint /teams/summarize avec la
transcription fictive reunion-test-2026-09-29.vtt.

À exécuter DANS le conteneur rag-api (ADMIN_TOKEN y est défini) :
  docker cp reunion-test-2026-09-29.vtt rag-api:/tmp/
  docker exec rag-api python3 /rag-pipeline/test_teams_summary.py /tmp/reunion-test-2026-09-29.vtt

Pour la réunion réelle enregistrée à partir de script-reunion-live.md :
  docker exec rag-api python3 /rag-pipeline/test_teams_summary.py /tmp/reunion-live.vtt live

Affiche le brouillon produit, puis vérifie automatiquement les éléments
du corrigé qui se prêtent à un contrôle par mots-clés. Les autres critères
de la grille (formulation des décisions, complétude) restent à évaluer
à la lecture.
"""
import os
import sys
import time

import httpx

vtt = open(sys.argv[1], encoding="utf-8").read()
debut = time.time()
r = httpx.post(
    "http://localhost:8080/teams/summarize",
    headers={"Authorization": f"Bearer {os.environ['ADMIN_TOKEN']}"},
    json={"vtt": vtt, "organisateur": "organisateur@exemple.ch",
          "titre": "Réunion de test", "date": "29.09.2026"},
    timeout=1200,
)
duree = time.time() - debut
print(f"HTTP {r.status_code} en {duree:.0f} s")
if r.status_code != 200:
    print(r.text)
    sys.exit(1)

d = r.json()
print(f"Tokens estimés : {d['tokens_estimes']} | tokens prompt réels : {d['tokens_prompt']}\n")
print(d["objet"])
print(d["corps"])

cr = d["compte_rendu"]
decisions = " ".join(x.get("texte", "") for x in cr["decisions"]).lower()
tout = (decisions + " " + " ".join(
    " ".join(str(v) for v in a.values()) for a in cr["actions"]) + " " +
    " ".join(x.get("texte", "") for x in cr["points_ouverts"])).lower()
tout_sans_espaces = tout.replace(" ", "")

def ech(mot_action, attendu):
    """Vrai si l'action contenant mot_action a une échéance contenant attendu."""
    return any(mot_action in str(a.get("action", "")).lower()
               and attendu in str(a.get("echeance", "")).lower() for a in cr["actions"])


points = " ".join(x.get("texte", "") for x in cr["points_ouverts"]).lower()

verifs_live = [
    ("Atelier au 13 octobre dans les décisions", "13 octobre" in decisions),
    ("Date écartée du 8 octobre absente des décisions", "8 octobre" not in decisions),
    ("Montant retenu 2 100 dans les décisions", "2100" in decisions.replace(" ", "")),
    ("Devis initial 2 350 absent des décisions", "2350" not in decisions.replace(" ", "")),
    ("Idée de filmer absente", "film" not in tout),
    ("Aucune donnée de santé (hôpital, dos)", not any(t in tout for t in ("hôpital", "hopital", " dos", "maladie"))),
    ("Question de l'allemand en point ouvert", "allemand" in points),
    ("Permanence du vendredi mentionnée (décision ou point ouvert)", "permanence" in decisions + " " + points),
    ("Au moins 4 actions", len(cr["actions"]) >= 4),
    ("Échéance des supports : 9 octobre", ech("support", "9 octobre")),
    ("Échéance de la facture : fin du mois", ech("facture", "fin du mois")),
    ("Échéance des statistiques : 5 octobre", ech("statistique", "5 octobre")),
]

verifs = [
    ("Montant décidé 3 900 présent dans les décisions", "3900" in decisions.replace(" ", "")),
    ("Montant initial 4 200 absent des décisions", "4200" not in decisions.replace(" ", "")),
    ("Date du 26 octobre présente", "26" in tout),
    ("Date abandonnée du 12 octobre absente", "12octobre" not in tout_sans_espaces),
    ("Idée des écrans absente", "écran" not in tout and "ecran" not in tout),
    ("Aucune donnée de santé", not any(t in tout for t in ("maladie", "malade", "arrêt"))),
    ("Question des stagiaires en point ouvert",
     any("stagiaire" in x.get("texte", "").lower() for x in cr["points_ouverts"])),
    ("Au moins 4 actions", len(cr["actions"]) >= 4),
    ("Échéance de l'avenant (vendredi 2 octobre) renseignée",
     any("avenant" in str(a.get("action", "")).lower()
         and ("2 octobre" in str(a.get("echeance", "")).lower()
              or "vendredi" in str(a.get("echeance", "")).lower())
         for a in cr["actions"])),
    ("Échéance du test logiciel (vendredi) renseignée",
     any(("logiciel" in str(a.get("action", "")).lower() or "test" in str(a.get("action", "")).lower())
         and "vendredi" in str(a.get("echeance", "")).lower()
         for a in cr["actions"])),
    ("Report à la prochaine réunion classé en décision (sujet : administration)",
     ("prochaine réunion" in decisions or "ordre du jour" in decisions) and "administ" in decisions),
    ("Stagiaires absents des décisions (question laissée ouverte, non reportée)",
     "stagiaire" not in decisions),
    ("Date de formation classée en point ouvert",
     any("formation" in x.get("texte", "").lower() or "date" in x.get("texte", "").lower()
         for x in cr["points_ouverts"])),
    ("Aucune action classée en décision (pas de décision « doit proposer », « prépare »)",
     not any(m in decisions for m in ("doit proposer", "prépare", "prepare", "envoie"))),
]
if len(sys.argv) > 2 and sys.argv[2] == "live":
    verifs = verifs_live
print("CONTRÔLES AUTOMATIQUES")
for libelle, ok in verifs:
    print(f"  [{'OK' if ok else 'ÉCHEC'}] {libelle}")
print(f"\n{sum(ok for _, ok in verifs)}/{len(verifs)} contrôles réussis. "
      "Compléter l'évaluation avec la grille du corrigé.")
