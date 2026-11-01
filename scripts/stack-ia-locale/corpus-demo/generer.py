"""Génère le corpus Axonix, le jeu de questions du §10 et les cas du test de non-divulgation.

Usage : python3 generer.py <dossier de sortie>
Produit :
  <sortie>/corpus-axonix/...             documents .docx, arborescence du partage
  <sortie>/jeu_questions_s10_lab.json    jeu du lab (comptes @bsculier.ch)
  <sortie>/jeu_questions_s10.json        jeu du dépôt (comptes génériques)
  <sortie>/cas_cloisonnement_lab.json    cas du lab
  <sortie>/liste-documents.csv           chemin ; dossier ; comptes autorisés
"""
import csv
import json
import os
import sys

from docx import Document
from docx.shared import Pt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec_clients
import spec_direction_rh
import spec_autres
import spec_tests as st

# Fichiers déjà corrects sur le partage, non redistribués (droits explicites à préserver)
NON_REDISTRIBUES = {"CLIENTS/test-deny-explicite.docx", "COMPTABILITE/Test_RAG_Depot.docx"}
DOMAINE_LAB = "bsculier.ch"


def ecrire_docx(d: dict, chemin: str):
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    for type_, contenu in d["blocs"]:
        if type_ == "h1":
            doc.add_heading(contenu, level=1)
        elif type_ == "h2":
            doc.add_heading(contenu, level=2)
        elif type_ == "p":
            doc.add_paragraph(contenu)
        elif type_ == "table":
            t = doc.add_table(rows=len(contenu), cols=len(contenu[0]))
            t.style = "Table Grid"
            for i, ligne in enumerate(contenu):
                for j, cellule in enumerate(ligne):
                    t.cell(i, j).text = str(cellule)
                    if i == 0:
                        for r in t.cell(i, j).paragraphs[0].runs:
                            r.bold = True
            doc.add_paragraph("")
    doc.core_properties.author = "Axonix SA (corpus fictif)"
    doc.core_properties.title = next((c for t, c in d["blocs"] if t == "h1"), os.path.basename(chemin))
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    doc.save(chemin)


def main(sortie: str):
    docs = spec_clients.DOCS + spec_direction_rh.DOCS + spec_autres.DOCS
    chemins = [d["chemin"] for d in docs]
    doublons = {c for c in chemins if chemins.count(c) > 1}
    assert not doublons, f"chemins en double : {doublons}"
    racine = os.path.join(sortie, "corpus-axonix")
    lignes = []
    for d in docs:
        comptes = st.autorises(d["chemin"])
        lignes.append((d["chemin"], d["chemin"].split("/")[0], ", ".join(c for c in st.COMPTES if c in comptes)))
        if d["chemin"] in NON_REDISTRIBUES:
            continue
        ecrire_docx(d, os.path.join(racine, *d["chemin"].split("/")))
    with open(os.path.join(sortie, "liste-documents.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(("Chemin", "Dossier", "Comptes autorisés"))
        w.writerows(lignes)

    # Cas du test de non-divulgation (lab)
    cas = []
    for id_, question, document, secret in st.CAS:
        ok = st.autorises(document)
        attendu = {}
        for c in st.COMPTES:
            v = c in ok
            if c in st.INCERTAIN and v:
                v = "?"
            attendu[f"{c}@{DOMAINE_LAB}"] = v
        cas.append({"id": id_, "question": question, "document": document, "secret": secret, "attendu": attendu})
    with open(os.path.join(sortie, "cas_cloisonnement_lab.json"), "w", encoding="utf-8") as f:
        json.dump({"_commentaire": "Cas du test de cloisonnement, VM de test, corpus Axonix enrichi (2.23.0). "
                   "attendu : true (accès), false (refus). Appartenances imbriquées vérifiées le 25 octobre 2026.",
                   "comptes": [f"{c}@{DOMAINE_LAB}" for c in st.COMPTES], "cas": cas},
                  f, ensure_ascii=False, indent=2)

    # Jeu de questions du §10 : lab et dépôt
    def jeu(compte_defaut, map_compte, description):
        qs = []
        for q in st.QUESTIONS:
            e = {"id": q["id"], "type": q["type"]}
            if "compte" in q:
                e["compte"] = map_compte(q["compte"])
            e.update(question=q["question"], document_attendu=q.get("document_attendu", ""),
                     attendus=q.get("attendus", []), interdits=q.get("interdits", []),
                     refus_attendu=q.get("refus_attendu", False))
            if q.get("principal_attendu"):
                e["principal_attendu"] = q["principal_attendu"]
            if q.get("note"):
                e["note"] = q["note"]
            qs.append(e)
        return {"version": "2026-10-25", "description": description, "compte_par_defaut": compte_defaut, "questions": qs}

    desc = ("Jeu de questions du §10, sur le corpus de démonstration Axonix SA (fictif, 2.23.0). Chaque question est "
            "posée avec un compte et évaluée sur des critères vérifiables : document attendu dans les sources, "
            "éléments attendus dans la réponse, éléments interdits (pièges), refus attendu. principal_attendu : le "
            "document doit être le document principal du contexte (première source).")
    with open(os.path.join(sortie, "jeu_questions_s10_lab.json"), "w", encoding="utf-8") as f:
        json.dump(jeu(f"blaise@{DOMAINE_LAB}", lambda c: f"{c}@{DOMAINE_LAB}", desc), f, ensure_ascii=False, indent=2)
    generique = {"test-client": "client", "toto": "utilisateur", "compta01": "comptabilite"}
    with open(os.path.join(sortie, "jeu_questions_s10.json"), "w", encoding="utf-8") as f:
        json.dump(jeu("direction@votre-domaine.ch", lambda c: f"{generique.get(c, c)}@votre-domaine.ch",
                      desc + " À adapter à votre corpus et à vos comptes."), f, ensure_ascii=False, indent=2)

    n = len([d for d in docs if d["chemin"] not in NON_REDISTRIBUES])
    print(f"{len(docs)} documents décrits, {n} générés dans {racine}")
    print(f"{len(cas)} cas de non-divulgation, {len(st.QUESTIONS)} questions")


if __name__ == "__main__":
    main(sys.argv[1])
