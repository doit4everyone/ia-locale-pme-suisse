"""
test_citations.py : tests unitaires du contrôle des citations (2.20.4).

Vérifie normaliser_citations (correction des accents) et verifier_citations
(contrôle exact, inchangé) de la RAG API, sans modèle ni Qdrant.

Lancement, depuis la VM, dans le conteneur de la RAG API :
  docker exec -w /app rag-api python3 /rag-pipeline/test_citations.py

Attendu : « 4 tests OK », code de sortie 0.
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

if all(resultats):
    print(f"{len(resultats)} tests OK")
    sys.exit(0)
print(f"{resultats.count(False)} test(s) en échec")
sys.exit(1)
