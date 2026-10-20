"""
test_revalidation_bm25.py : tests unitaires des droits sur le chemin BM25 (2.21.3, point 10).

L'index BM25 est un instantané construit au démarrage et en fin de
synchronisation. Ces tests vérifient qu'un droit retiré dans Qdrant APRÈS la
construction de l'index n'est plus contourné par ce chemin :
  - revalider_bm25 : relecture du payload actuel, refus par défaut ;
  - etendre_complements : plus de repli sur des extraits non relus ;
  - search_qdrant, de bout en bout, avec et sans extension du contexte ;
  - sans groupes : aucun résultat, jamais de contrôle désactivé (2.21.4).

Sans Qdrant, sans modèle, sans annuaire : Qdrant est simulé en mémoire.
Ces tests ne remplacent pas le test en lab (test_revocation_bm25.py), qui
travaille sur le vrai Qdrant.

Lancement, depuis la VM, dans le conteneur de la RAG API :
  docker exec -w /app rag-api python3 /rag-pipeline/test_revalidation_bm25.py

Attendu : « 14 tests OK », code de sortie 0.
"""

import asyncio
import hashlib
import os
import sys

sys.path.insert(0, "/app")
try:
    if os.getenv("RAG_MAIN"):
        raise ImportError  # fichier imposé (comparaison avant et après correctif)
    import main  # code de la RAG API, dans le conteneur
except ImportError:  # hors conteneur : fichier du dépôt
    import importlib.util
    chemin = os.getenv("RAG_MAIN") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "api", "anon_main.py")
    spec = importlib.util.spec_from_file_location("main", chemin)
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)

from rank_bm25 import BM25Okapi

COLL = main.COLLECTION
GROUPE = "BSCULIER\\Direction"
AUTRE = "BSCULIER\\RH"


# ─────────────────────────────────────────
# Qdrant simulé
# ─────────────────────────────────────────
class Point:
    def __init__(self, pid, payload):
        self.id = pid
        self.payload = payload
        self.score = 0.5


class QdrantSimule:
    """retrieve, scroll, count et query_points sur des payloads en mémoire.
    erreur=True : toutes les lectures échouent (Qdrant indisponible)."""

    def __init__(self, points: dict, erreur: bool = False):
        self.points = points  # {collection: {id: payload}}
        self.erreur = erreur

    def _verifier(self):
        if self.erreur:
            raise ConnectionError("Qdrant simulé indisponible")

    @staticmethod
    def _accepte(payload: dict, filtre) -> bool:
        for cond in (filtre.must if filtre else []) or []:
            valeur = payload.get(cond.key)
            if cond.match is not None and hasattr(cond.match, "any"):
                if not any(v in (valeur or []) for v in cond.match.any):
                    return False
            elif cond.match is not None:
                if valeur != cond.match.value:
                    return False
            if cond.range is not None:
                if valeur is None or valeur < cond.range.gte or valeur > cond.range.lte:
                    return False
        return True

    def retrieve(self, collection_name, ids, with_payload=True, with_vectors=False):
        self._verifier()
        coll = self.points.get(collection_name, {})
        return [Point(i, dict(coll[i])) for i in ids if i in coll]

    def scroll(self, collection_name, scroll_filter=None, limit=10, with_payload=True, offset=None):
        self._verifier()
        coll = self.points.get(collection_name, {})
        res = [Point(i, dict(p)) for i, p in coll.items() if self._accepte(p, scroll_filter)]
        return res[:limit], None

    def count(self, collection_name, count_filter=None, exact=True):
        self._verifier()
        n = len(self.scroll(collection_name, count_filter, limit=10_000)[0])
        return type("Compte", (), {"count": n})()

    def query_points(self, collection_name, query=None, query_filter=None, limit=10, with_payload=True):
        # Branche vectorielle : lit l'état actuel, comme le vrai Qdrant.
        self._verifier()
        res = self.scroll(collection_name, query_filter, limit=limit)[0]
        return type("Resultat", (), {"points": res})()


def payload(source, idx, texte, autorises, interdits=None, chiffre=False):
    return {"source": source, "chunk_index": idx, "text": texte,
            "autorises": autorises, "interdits": interdits or [],
            "chiffre": chiffre, "mip_etiquette_id": "lbl-1" if chiffre else "",
            "mip_proprietaire": ""}


def candidat(pid, p):
    """Candidat BM25 tel que _load_collection_chunks le construit."""
    return {"chunk_key": hashlib.md5(p["text"].encode()).hexdigest(), "point_id": pid,
            "text": p["text"], "source": p["source"], "source_id": "", "web_url": "",
            "collection": COLL, "chunk_index": p["chunk_index"],
            "autorises": p["autorises"], "interdits": p["interdits"],
            **main.champs_purview(p), "score": 1.0}


RESULTATS = []


def verifier(nom, ok, detail=""):
    RESULTATS.append(ok)
    print(f"{'OK    ' if ok else 'ECHEC '} {nom}")
    if not ok and detail:
        print(f"       {detail}")


# ─────────────────────────────────────────
# revalider_bm25
# ─────────────────────────────────────────
def tests_revalidation():
    if not hasattr(main, "revalider_bm25"):
        for nom in ("revalider : sans groupes", "revalider : droit inchangé", "revalider : droit retiré",
                    "revalider : refus ajouté", "revalider : point supprimé",
                    "revalider : Qdrant indisponible", "revalider : sans identifiant",
                    "revalider : payload actuel repris"):
            verifier(nom, False, "revalider_bm25 absent (code antérieur à la 2.21.3)")
        return
    instantane = payload("DIRECTION/Budget.docx", 0, "budget direction 2027", [GROUPE])
    c = candidat(1, instantane)

    q = QdrantSimule({COLL: {1: dict(instantane)}})
    main.qdrant = q
    verifier("revalider : sans groupes",
             main.revalider_bm25([c], []) == [] and main.revalider_bm25([c], None) == [])
    verifier("revalider : droit inchangé", len(main.revalider_bm25([c], [GROUPE])) == 1)

    q.points[COLL][1]["autorises"] = [AUTRE]
    verifier("revalider : droit retiré", main.revalider_bm25([c], [GROUPE]) == [])

    q.points[COLL][1] = payload("DIRECTION/Budget.docx", 0, "budget direction 2027", [GROUPE], [GROUPE])
    verifier("revalider : refus ajouté", main.revalider_bm25([c], [GROUPE]) == [])

    del q.points[COLL][1]
    verifier("revalider : point supprimé", main.revalider_bm25([c], [GROUPE]) == [])

    main.qdrant = QdrantSimule({COLL: {1: dict(instantane)}}, erreur=True)
    verifier("revalider : Qdrant indisponible", main.revalider_bm25([c], [GROUPE]) == [])

    main.qdrant = QdrantSimule({COLL: {1: dict(instantane)}})
    sans_id = {k: v for k, v in c.items() if k != "point_id"}
    verifier("revalider : sans identifiant", main.revalider_bm25([sans_id], [GROUPE]) == [])

    main.qdrant = QdrantSimule({COLL: {1: payload("DIRECTION/Budget.docx", 0,
                                                  "budget direction 2027 révisé", [GROUPE], chiffre=True)}})
    r = main.revalider_bm25([c], [GROUPE])
    verifier("revalider : payload actuel repris",
             len(r) == 1 and r[0]["chiffre"] is True and r[0]["text"].endswith("révisé"),
             f"obtenu : {r}")


# ─────────────────────────────────────────
# etendre_complements
# ─────────────────────────────────────────
def tests_extension():
    instantane = payload("DIRECTION/Budget.docx", 0, "budget direction 2027", [GROUPE])
    c = candidat(1, instantane)
    ancien = main.COMPLEMENT_VOISINS

    main.qdrant = QdrantSimule({COLL: {1: payload("DIRECTION/Budget.docx", 0, "budget direction 2027", [AUTRE])}})
    r = asyncio.run(main.etendre_complements([c], [GROUPE], "test@exemple.ch"))
    verifier("extension : fenêtre vide, document écarté", r == [],
             f"{len(r)} extrait(s) réinjecté(s) : repli sur l'extrait d'origine")

    main.qdrant = QdrantSimule({}, erreur=True)
    r = asyncio.run(main.etendre_complements([c], [GROUPE], "test@exemple.ch"))
    verifier("extension : erreur Qdrant, document écarté", r == [],
             f"{len(r)} extrait(s) réinjecté(s) : repli sur l'extrait d'origine")

    main.qdrant = QdrantSimule({COLL: {1: dict(instantane)}})
    r = asyncio.run(main.etendre_complements([c], [], "test@exemple.ch"))
    verifier("extension : sans groupes, aucun extrait", r == [],
             f"{len(r)} extrait(s) renvoyé(s) sans contrôle des droits")
    main.COMPLEMENT_VOISINS = ancien


# ─────────────────────────────────────────
# search_qdrant de bout en bout
# ─────────────────────────────────────────
def tests_recherche():
    """Deux documents trouvés par mots-clés. Index construit pendant que les deux
    sont autorisés, puis le droit sur Salaires.xlsx est retiré dans Qdrant, sans
    reconstruire l'index. Salaires.xlsx ne doit plus jamais revenir."""
    q_budget = "budget salaires direction 2027"
    points = {
        1: payload("DIRECTION/Budget.docx", 0, "budget direction 2027 budget salaires direction", [GROUPE]),
        2: payload("DIRECTION/Budget.docx", 1, "suite du budget direction 2027", [GROUPE]),
        3: payload("RH/Salaires.xlsx", 0, "salaires 2027 direction grille", [GROUPE]),
    }
    # Documents sans rapport : sans eux, les mots de la question figurent dans
    # presque tous les extraits et BM25 leur donne un poids nul.
    for i in range(20):
        points[10 + i] = payload(f"DIVERS/Note_{i}.docx", 0, f"procédure archivage courrier note {i}", [GROUPE])

    async def embedding_simule(_):
        return [0.0]

    main.get_embedding = embedding_simule
    main.RERANKER_URL = ""

    for seuil, nom in ((main.CONTEXT_THRESHOLD, "avec extension du contexte"),
                       (2.0, "sans extension du contexte")):
        main.qdrant = QdrantSimule({COLL: {i: dict(p) for i, p in points.items()},
                                    main.DOCUMENTATION_COLLECTION: {}})
        main._bm25_chunks = [candidat(i, p) for i, p in points.items()]
        main._bm25_index = BM25Okapi([c["text"].lower().split() for c in main._bm25_chunks])
        # Droit retiré après la construction de l'index
        main.qdrant.points[COLL][3]["autorises"] = [AUTRE]
        main.CONTEXT_THRESHOLD = seuil
        chunks = asyncio.run(main.search_qdrant(q_budget, user_groups=[GROUPE], user_email="test@exemple.ch"))
        sources = sorted({c["source"] for c in chunks})
        verifier(f"recherche {nom} : droit retiré respecté",
                 "RH/Salaires.xlsx" not in sources,
                 f"FUITE : sources renvoyées {sources}")

    # Sans groupes : refus avant toute recherche, jamais une recherche sans filtre
    try:
        chunks = asyncio.run(main.search_qdrant(q_budget, user_groups=None, user_email="test@exemple.ch"))
        verifier("recherche sans groupes : refus", False,
                 f"recherche servie sans contrôle des droits ({len(chunks)} extraits)")
    except main.HTTPException as e:
        verifier("recherche sans groupes : refus", e.status_code == 403, f"code {e.status_code}")


if __name__ == "__main__":
    qdrant_reel = main.qdrant
    try:
        tests_revalidation()
        tests_extension()
        tests_recherche()
    finally:
        main.qdrant = qdrant_reel
    total, ok = len(RESULTATS), sum(RESULTATS)
    print(f"{ok} tests OK" if ok == total else f"{total - ok} test(s) en échec sur {total}")
    sys.exit(0 if ok == total else 1)
