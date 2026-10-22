"""
test_citations.py : tests unitaires du contrôle des citations (2.20.4) et de la
lecture du verdict du juge et de la phrase de refus (2.21.9).

Vérifie normaliser_citations (correction des accents), verifier_citations
(contrôle exact, inchangé), verdict_juge (verdict lu strictement, verdict
incohérent refusé) et est_refus_standard (seule la phrase de refus exacte
échappe au juge) de la RAG API, sans modèle ni Qdrant.

Lancement, depuis la VM, dans le conteneur de la RAG API :
  docker exec -w /app rag-api python3 /rag-pipeline/test_citations.py

Attendu : « 20 tests OK », code de sortie 0.
"""

import sys

sys.path.insert(0, "/app")
try:
    import main  # code de la RAG API, dans le conteneur
except ImportError:  # hors conteneur : fichier du dépôt
    import importlib.util
    import os
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api", "anon_main.py")
    spec = importlib.util.spec_from_file_location("main", chemin)
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)

CHUNKS = [
    {"source": "DOIT4EVERYONE/purview-mvc/Procédure_Purview_MVC_PME_Suisse_v1.pdf"},
    {"source": "CLIENTS/Baumont Industries SA/21_Contrat_Maintenance_Baumont_Industries.docx"},
    {"source": "RH/Rapport_annuel.docx"},
    {"source": "DIRECTION/Rapport_annuél.docx"},
]


def verifier(nom, reponse, attendu_normalise, attendu_inventees):
    normalisee = main.normaliser_citations(reponse, CHUNKS)
    inventees = main.verifier_citations(normalisee, CHUNKS)
    ok = (attendu_normalise in normalisee) and (inventees == attendu_inventees)
    print(f"{'OK    ' if ok else 'ECHEC '} {nom}")
    if not ok:
        print(f"       réponse normalisée : {normalisee}")
        print(f"       sources signalées  : {inventees} (attendu : {attendu_inventees})")
    return ok


resultats = [
    # 1. Accent perdu par le modèle : corrigé, plus d'avertissement
    verifier("accent perdu",
             "La procédure est décrite [Procedure_Purview_MVC_PME_Suisse_v1.pdf].",
             "[Procédure_Purview_MVC_PME_Suisse_v1.pdf]", []),
    # 2. Accent ajouté par le modèle : corrigé, plus d'avertissement
    verifier("accent ajouté",
             "Durée de 24 mois [21_Contrat_Maintenance_Baumont_Industriés.docx].",
             "[21_Contrat_Maintenance_Baumont_Industries.docx]", []),
    # 3. Ambiguïté : la citation correspond, sans accents ni casse, à deux
    #    documents (Rapport_annuel.docx et Rapport_annuél.docx). Rien n'est
    #    corrigé, la citation reste signalée.
    verifier("ambiguïté",
             "Selon le rapport [rapport_annuel.docx].",
             "[rapport_annuel.docx]", ["rapport_annuel.docx"]),
    # 4. Source inventée : toujours signalée
    verifier("source inventée",
             "Voir [Contrat_Dupont_Logistique.docx].",
             "[Contrat_Dupont_Logistique.docx]", ["Contrat_Dupont_Logistique.docx"]),
]



def juge(nom, brut, attendu_ancree):
    v = main.verdict_juge(brut)
    ok = v["ancree"] is attendu_ancree and isinstance(v["affirmations_non_sourcees"], list)
    print(f"{'OK    ' if ok else 'ECHEC '} {nom}")
    if not ok:
        print(f"       verdict : {v} (ancrée attendue : {attendu_ancree})")
    return ok


resultats += [
    # 5. Verdict cohérent : ancrée, liste vide
    juge("juge : ancrée, liste vide", {"ancree": True, "affirmations_non_sourcees": []}, True),
    # 6. Verdict incohérent (2.21.9) : « ancrée » mais une affirmation signalée
    juge("juge : incohérent, liste non vide",
         {"ancree": True, "affirmations_non_sourcees": ["Série M, Microsoft 377 et Entra ID"]}, False),
    # 7. « false » en chaîne : non ancrée
    juge("juge : ancrée en chaîne", {"ancree": "true", "affirmations_non_sourcees": []}, False),
    # 8. Clé absente : non ancrée
    juge("juge : clé absente", {"affirmations_non_sourcees": []}, False),
    # 9. Liste remplacée par une chaîne : non ancrée, liste normalisée
    juge("juge : liste en chaîne", {"ancree": True, "affirmations_non_sourcees": "36 mois"}, False),
    # 2.21.10 : schéma incomplet, jamais une preuve d'ancrage
    juge("juge : liste absente", {"ancree": True}, False),
    juge("juge : liste null", {"ancree": True, "affirmations_non_sourcees": None}, False),
    juge("juge : liste chaîne vide", {"ancree": True, "affirmations_non_sourcees": ""}, False),
    juge("juge : liste 0", {"ancree": True, "affirmations_non_sourcees": 0}, False),
    juge("juge : liste objet vide", {"ancree": True, "affirmations_non_sourcees": {}}, False),
    juge("juge : liste d'éléments non textuels", {"ancree": True, "affirmations_non_sourcees": [1]}, False),
    juge("juge : réponse qui n'est pas un objet", ["ancree", True], False),
]


def refus(nom, reponse, attendu):
    ok = main.est_refus_standard(reponse) is attendu
    print(f"{'OK    ' if ok else 'ECHEC '} {nom}")
    return ok


resultats += [
    # 10. Phrase de refus exacte : acceptée sans juge
    refus("refus : phrase exacte", "Cette information ne figure pas dans les documents disponibles.", True),
    # 11. Guillemets, espaces, sans point final : toujours la phrase exacte
    refus("refus : guillemets et espaces", "  « Cette information ne figure pas dans les documents disponibles »  ", True),
    # 12. Fait inventé suivi de la phrase (moins de 200 caractères) : passe par le juge
    refus("refus : fait ajouté, juge requis",
          "Le forfait est de CHF 9 999 [21_Contrat.docx]. Le reste ne figure pas dans les documents disponibles.", False),
    # 13. Autre formulation de refus : passe par le juge
    refus("refus : autre formulation", "Aucun document fourni ne contient d'information pertinente sur les clients.", False),
]
if all(resultats):
    print(f"{len(resultats)} tests OK")
    sys.exit(0)
print(f"{resultats.count(False)} test(s) en échec")
sys.exit(1)
