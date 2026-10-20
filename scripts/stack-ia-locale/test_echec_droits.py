"""
test_echec_droits.py : tests unitaires des échecs d'écriture des droits (2.21.5, §16.5.2).

Jusqu'à la 2.21.4, une erreur de Qdrant pendant l'écriture des droits d'un
document le faisait passer pour « non indexé » : acl_resolver.py se terminait
avec le code 0, la synchronisation réussissait, aucune alerte ne partait, et le
document gardait ses anciens droits dans Qdrant.

Vérifie, avec un Qdrant simulé, sans partage SMB ni modèle :
  - acl_resolver.py : trois issues distinctes (mis à jour, non indexé, échec),
    une seconde tentative, le code de sortie 2 et le rapport ;
  - la RAG API : liste des documents retirés de la recherche (code 0, 2, autre),
    conservation sur disque, exclusion de la recherche et du contrôle d'accès.

Lancement, depuis la VM, dans le conteneur de la RAG API :
  docker exec -w /app rag-api python3 /rag-pipeline/test_echec_droits.py

Attendu : « 12 tests OK », code de sortie 0.
"""

import asyncio
import importlib.util
import json
import os
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
# Qdrant simulé et accès à la RAG API (main) : repris des tests BM25
import test_revalidation_bm25 as tb  # noqa: E402

main = tb.main
G = tb.GROUPE


def charger_resolveur():
    """acl_resolver.py dans le conteneur, anon_acl_resolver.py dans le dépôt."""
    for nom in ("acl_resolver.py", "anon_acl_resolver.py"):
        chemin = os.path.join(ICI, nom)
        if os.path.exists(chemin):
            spec = importlib.util.spec_from_file_location("acl_resolver", chemin)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError("acl_resolver.py introuvable à côté du test")


ar = charger_resolveur()
ar.PAUSE_NOUVELLE_TENTATIVE = 0
COLL = ar.COLLECTION


class QdrantPannes(tb.QdrantSimule):
    """Qdrant simulé dont l'écriture ou la suppression échoue pour certaines sources."""

    def __init__(self, points, ecriture_refusee=(), suppression_refusee=(), echecs_avant_succes=99):
        super().__init__(points)
        self.ecriture_refusee = set(ecriture_refusee)
        self.suppression_refusee = set(suppression_refusee)
        self.restants = echecs_avant_succes

    def get_collections(self):
        cols = [type("C", (), {"name": n})() for n in self.points]
        return type("R", (), {"collections": cols})()

    def scroll(self, collection_name, scroll_filter=None, limit=10, with_payload=True, offset=None, **_):
        return super().scroll(collection_name, scroll_filter, limit=10_000)

    def set_payload(self, collection_name, payload, points):
        ids = list(points)
        sources = {self.points[collection_name][i]["source"] for i in ids}
        if sources & self.ecriture_refusee and self.restants > 0:
            self.restants -= 1
            raise RuntimeError("No space left on device (simulé)")
        for i in ids:
            self.points[collection_name][i].update(payload)

    def delete(self, collection_name, points_selector):
        source = points_selector.filter.must[0].match.value
        if source in self.suppression_refusee:
            raise RuntimeError("No space left on device (simulé)")
        for i in [i for i, p in self.points[collection_name].items() if p["source"] == source]:
            del self.points[collection_name][i]


def p(source, autorises):
    return {"source": source, "chunk_index": 0, "text": source, "autorises": autorises,
            "interdits": [], "source_type": "smb"}


RESULTATS = tb.RESULTATS


def verifier(nom, ok, detail=""):
    tb.verifier(nom, ok, detail)


# ─────────────────────────────────────────
# acl_resolver.py
# ─────────────────────────────────────────
def tests_resolveur():
    q = QdrantPannes({COLL: {1: p("RH/Salaires.xlsx", [G])}}, ecriture_refusee={"RH/Salaires.xlsx"})
    nb = ar.mettre_a_jour_qdrant(q, "RH/Salaires.xlsx", COLL, ["BSCULIER\\RH"], [])
    verifier("résolveur : écriture refusée, échec distinct", nb == ar.ECHEC_ECRITURE, f"retour {nb}")

    nb = ar.mettre_a_jour_qdrant(q, "RH/Absent.docx", COLL, ["BSCULIER\\RH"], [])
    verifier("résolveur : aucun extrait, non indexé", nb == 0, f"retour {nb}")

    q = QdrantPannes({COLL: {1: p("RH/Salaires.xlsx", [G])}}, ecriture_refusee={"RH/Salaires.xlsx"},
                     echecs_avant_succes=1)
    nb = ar.mettre_a_jour_qdrant(q, "RH/Salaires.xlsx", COLL, ["BSCULIER\\RH"], [])
    verifier("résolveur : seconde tentative réussie", nb == 1 and q.points[COLL][1]["autorises"] == ["BSCULIER\\RH"],
             f"retour {nb}")

    q = QdrantPannes({COLL: {1: p("RH/Salaires.xlsx", [G]), 2: p("DIRECTION/Plan.docx", [G])}},
                     ecriture_refusee={"RH/Salaires.xlsx", "DIRECTION/Plan.docx"})
    lectures = [("//srv/RH/Salaires.xlsx", "RH/Salaires.xlsx", ["BSCULIER\\RH"], [], False),
                ("//srv/DIRECTION/Plan.docx", "DIRECTION/Plan.docx", [], [], True),
                ("//srv/RH/Absent.docx", "RH/Absent.docx", ["BSCULIER\\RH"], [], False)]
    r = ar.ecrire_droits(q, lectures)
    statuts = {d["source_name"]: d["statut"] for d in r["rapport"]}
    verifier("résolveur : échec, fermeture en échec et non indexé distingués",
             statuts == {"RH/Salaires.xlsx": "echec_ecriture", "DIRECTION/Plan.docx": "echec_ecriture",
                         "RH/Absent.docx": "non_indexe"}
             and sorted(r["echecs"]) == ["DIRECTION/Plan.docx", "RH/Salaires.xlsx"], f"statuts {statuts}")


def passage_complet(q, fichiers):
    """resoudre_acl de bout en bout, partage et ACL simulés. Renvoie (code, rapport)."""
    sauve = (ar.QdrantClient, ar.lister_fichiers_montes, ar.lire_acl_fichier, ar.socket.getaddrinfo)
    ar.QdrantClient = lambda url=None, api_key=None: q
    ar.lister_fichiers_montes = lambda m: [(f"//srv/{f}", f"/mnt/x/{f}") for f in fichiers]
    ar.lire_acl_fichier = lambda share, chemin: (["BSCULIER\\RH"], [])
    ar.socket.getaddrinfo = lambda *a, **k: [None]
    chemin = tempfile.mktemp(suffix=".json")
    code = 0
    try:
        ar.resoudre_acl("//srv/Partage", "/mnt/x", rapport_path=chemin)
    except SystemExit as e:
        code = e.code
    finally:
        ar.QdrantClient, ar.lister_fichiers_montes, ar.lire_acl_fichier, ar.socket.getaddrinfo = sauve
    with open(chemin, encoding="utf-8") as f:
        rapport = json.load(f)
    os.remove(chemin)
    return code, rapport


def tests_passage():
    q = QdrantPannes({COLL: {1: p("RH/Salaires.xlsx", [G]), 2: p("RH/Note.docx", [G])}, "documentation": {}},
                     ecriture_refusee={"RH/Salaires.xlsx"})
    code, r = passage_complet(q, ["RH/Salaires.xlsx", "RH/Note.docx"])
    verifier("passage : échec d'écriture, code 2 et rapport", code == 2 and r.get("echecs_ecriture") == ["RH/Salaires.xlsx"],
             f"code {code}, échecs {r.get('echecs_ecriture')}")

    q = QdrantPannes({COLL: {1: p("RH/Salaires.xlsx", [G])}, "documentation": {}})
    code, r = passage_complet(q, ["RH/Salaires.xlsx"])
    verifier("passage : sans échec, code 0", code == 0 and r.get("echecs_ecriture") == [], f"code {code}")

    q = QdrantPannes({COLL: {1: p("RH/Salaires.xlsx", [G]), 2: p("RH/Supprime.docx", [G])}, "documentation": {}},
                     suppression_refusee={"RH/Supprime.docx"})
    code, r = passage_complet(q, ["RH/Salaires.xlsx"])
    verifier("passage : suppression d'un fichier effacé refusée, code 2",
             code == 2 and r.get("echecs_suppression") == ["RH/Supprime.docx"],
             f"code {code}, suppressions {r.get('echecs_suppression')}")


# ─────────────────────────────────────────
# RAG API
# ─────────────────────────────────────────
def tests_api():
    main.FICHIER_BLOQUES = tempfile.mktemp(suffix=".json")
    rapport_acl = tempfile.mktemp(suffix=".json")
    with open(rapport_acl, "w", encoding="utf-8") as f:
        json.dump({"echecs_ecriture": ["RH/Salaires.xlsx"], "echecs_suppression": ["RH/Supprime.docx"]}, f)

    main._bloques["smb"] = set()
    main.appliquer_resultat_droits("smb", 2, rapport_acl)
    ok_2 = main.sources_bloquees() == {"RH/Salaires.xlsx", "RH/Supprime.docx"}
    main.appliquer_resultat_droits("smb", 1, rapport_acl + ".absent")
    ok_1 = main.sources_bloquees() == {"RH/Salaires.xlsx", "RH/Supprime.docx"}
    main._bloques["smb"] = set()
    main.charger_bloques()
    ok_disque = main.sources_bloquees() == {"RH/Salaires.xlsx", "RH/Supprime.docx"}
    verifier("API : code 2 retire, code 1 garde, liste relue du disque", ok_2 and ok_1 and ok_disque,
             f"code 2 {ok_2}, code 1 {ok_1}, disque {ok_disque}")

    rapport_sp = tempfile.mktemp(suffix=".json")
    with open(rapport_sp, "w", encoding="utf-8") as f:
        json.dump({"sites": [{"fichiers": [{"source": "SharePoint/RH/Docs/Grille.xlsx", "statut": "erreur"},
                                            {"source": "SharePoint/RH/Docs/Note.docx", "statut": "inchangé"}]}]}, f)
    main.appliquer_resultat_droits("sharepoint", 2, rapport_sp)
    verifier("API : SharePoint, fichier en erreur retiré",
             "SharePoint/RH/Docs/Grille.xlsx" in main.sources_bloquees()
             and "SharePoint/RH/Docs/Note.docx" not in main.sources_bloquees())
    main.appliquer_resultat_droits("sharepoint", 0, rapport_sp)

    # Recherche : Salaires.xlsx autorisé dans Qdrant, mais retiré de la recherche
    points = {1: tb.payload("RH/Salaires.xlsx", 0, "grille salaires 2027 direction", [G]),
              2: tb.payload("DIRECTION/Budget.docx", 0, "budget direction 2027 salaires", [G])}
    for i in range(20):
        points[10 + i] = tb.payload(f"DIVERS/Note_{i}.docx", 0, f"procédure archivage courrier note {i}", [G])

    async def embedding_simule(_):
        return [0.0]
    main.get_embedding = embedding_simule
    main.RERANKER_URL = ""
    q = QdrantPannes({main.COLLECTION: {i: dict(v) for i, v in points.items()}, main.DOCUMENTATION_COLLECTION: {}})
    main.qdrant = q
    main._bm25_chunks = [tb.candidat(i, v) for i, v in points.items()]
    main._bm25_index = tb.BM25Okapi([c["text"].lower().split() for c in main._bm25_chunks])
    sources = set()
    for seuil in (0.01, 2.0):
        main.CONTEXT_THRESHOLD = seuil
        chunks = asyncio.run(main.search_qdrant("grille salaires 2027", user_groups=[G], user_email="t@x.ch"))
        sources |= {c["source"] for c in chunks}
    verifier("API : document retiré absent de la recherche", "RH/Salaires.xlsx" not in sources,
             f"FUITE : sources {sorted(sources)}")

    main.get_user_groups = lambda u: [G]
    r = asyncio.run(main.calculer_acces("t@x.ch", "RH/Salaires.xlsx"))
    verifier("API : contrôle d'accès, document retiré inaccessible", r["chunks_accessibles"] == 0,
             f"{r['chunks_accessibles']} extrait(s) accessible(s)")

    main.appliquer_resultat_droits("smb", 0, rapport_acl)
    verifier("API : code 0, liste vidée", main.sources_bloquees() == set())

    for f in (main.FICHIER_BLOQUES, rapport_acl, rapport_sp):
        if os.path.exists(f):
            os.remove(f)


if __name__ == "__main__":
    qdrant_reel, fichier_reel = main.qdrant, main.FICHIER_BLOQUES
    bloques_reels = {k: set(v) for k, v in main._bloques.items()}
    try:
        tests_resolveur()
        tests_passage()
        tests_api()
    finally:
        main.qdrant, main.FICHIER_BLOQUES = qdrant_reel, fichier_reel
        main._bloques.update(bloques_reels)
    total, ok = len(RESULTATS), sum(RESULTATS)
    print(f"{ok} tests OK" if ok == total else f"{total - ok} test(s) en échec sur {total}")
    sys.exit(0 if ok == total else 1)
