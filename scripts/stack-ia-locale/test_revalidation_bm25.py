"""
test_revalidation_bm25.py : tests unitaires des droits sur le chemin BM25 (2.21.3, point 10 ; 2.23.0).

Depuis la 2.23.0, la recherche par mots-clés est faite par Qdrant (index plein
texte, score BM25), avec le filtre d'accès de la recherche vectorielle. Ces
tests vérifient qu'un droit retiré dans Qdrant n'est jamais contourné par ce
chemin, et que l'index plein texte est mis en place sans jamais ouvrir de
recherche sans droits :
  - revalider_bm25 : relecture du payload actuel, refus par défaut ;
  - etendre_complements : plus de repli sur des extraits non relus ;
  - search_qdrant, de bout en bout, avec et sans extension du contexte ;
  - sans groupes : aucun résultat, jamais de contrôle désactivé (2.21.4) ;
  - recherche_mots_cles : filtre d'accès transmis, refus appliqués, erreur
    de Qdrant sans effet sur la recherche vectorielle, collections classées
    par rang et non par score (2.23.0) ;
  - preparer_index_texte : Qdrant trop ancien, index absent, conforme ou à
    recréer, collection absente, champ inconnu ajouté par Qdrant (2.23.0).

Sans Qdrant, sans modèle, sans annuaire : Qdrant est simulé en mémoire.
Ces tests ne remplacent pas le test en lab (test_revocation_bm25.py), qui
travaille sur le vrai Qdrant.

Lancement, depuis la VM, dans le conteneur de la RAG API :
  docker exec -w /app rag-api python3 /rag-pipeline/test_revalidation_bm25.py

Attendu : « 27 tests OK », code de sortie 0.
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

from qdrant_client.models import TextQuery

COLL = main.COLLECTION
GROUPE = "S-1-5-21-1111-2222-3333-1105"   # SID depuis la 2.22.0
AUTRE = "S-1-5-21-1111-2222-3333-1201"


# ─────────────────────────────────────────
# Qdrant simulé
# ─────────────────────────────────────────
class Point:
    def __init__(self, pid, payload, score=0.5):
        self.id = pid
        self.payload = payload
        self.score = score


class QdrantSimule:
    """retrieve, scroll, count et query_points sur des payloads en mémoire.
    erreur=True : toutes les lectures échouent (Qdrant indisponible).
    erreur_texte=True : seule la recherche par mots-clés échoue (index absent).
    requetes_texte : (collection, filtre) de chaque recherche par mots-clés."""

    def __init__(self, points: dict, erreur: bool = False, erreur_texte: bool = False):
        self.points = points  # {collection: {id: payload}}
        self.erreur = erreur
        self.erreur_texte = erreur_texte
        self.requetes_texte = []

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

    def query_points(self, collection_name, query=None, query_filter=None, limit=10,
                     with_payload=True, using=None):
        self._verifier()
        if isinstance(query, TextQuery):
            # Mots-clés : extraits qui contiennent au moins un mot de la question,
            # dans l'état actuel et avec le filtre reçu, comme le vrai Qdrant.
            self.requetes_texte.append((collection_name, query_filter))
            if self.erreur_texte:
                raise RuntimeError("index plein texte absent (simulé)")
            mots = set(str(query.text).lower().split())
            res = []
            for i, p in self.points.get(collection_name, {}).items():
                n = len(mots & set(p["text"].lower().split()))
                if n and self._accepte(p, query_filter):
                    res.append(Point(i, dict(p), score=float(n)))
            res.sort(key=lambda x: x.score, reverse=True)
            return type("Resultat", (), {"points": res[:limit]})()
        # Branche vectorielle : lit l'état actuel, comme le vrai Qdrant.
        res = self.scroll(collection_name, query_filter, limit=limit)[0]
        return type("Resultat", (), {"points": res})()


def payload(source, idx, texte, autorises, interdits=None, chiffre=False):
    return {"source": source, "chunk_index": idx, "text": texte,
            "autorises": autorises, "interdits": interdits or [],
            "chiffre": chiffre, "mip_etiquette_id": "lbl-1" if chiffre else "",
            "mip_proprietaire": ""}


def candidat(pid, p):
    """Candidat BM25 tel que recherche_mots_cles le construit."""
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
    """Deux documents trouvés par mots-clés. Le droit sur Salaires.xlsx est
    retiré dans Qdrant : Salaires.xlsx ne doit plus jamais revenir, ni par les
    mots-clés ni par l'extension du contexte."""
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
    # Synchronisation complète récente : sinon la règle d'âge des droits (2.21.8)
    # refuserait toutes les questions, et ce test ne vérifierait rien d'autre.
    if hasattr(main, "_etat") and "derniere_synchro_complete" in main._etat:
        from datetime import datetime, timezone
        main._etat["derniere_synchro_complete"] = datetime.now(timezone.utc).isoformat()

    for seuil, nom in ((main.CONTEXT_THRESHOLD, "avec extension du contexte"),
                       (2.0, "sans extension du contexte")):
        main.qdrant = QdrantSimule({COLL: {i: dict(p) for i, p in points.items()},
                                    main.DOCUMENTATION_COLLECTION: {}})
        main._collections_texte = {COLL}
        # Droit retiré dans Qdrant
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


# ─────────────────────────────────────────
# recherche_mots_cles (2.23.0)
# ─────────────────────────────────────────
def filtre_groupes(filtre) -> list:
    """Groupes du filtre ALLOW (autorises) d'une requête, [] s'il n'y en a pas."""
    for cond in (getattr(filtre, "must", None) or []):
        if cond.key == "autorises" and hasattr(cond.match, "any"):
            return list(cond.match.any)
    return []


def tests_mots_cles():
    if not hasattr(main, "recherche_mots_cles"):
        for nom in ("mots-clés : document trouvé", "mots-clés : filtre d'accès transmis à Qdrant",
                    "mots-clés : sans filtre, aucune requête", "mots-clés : refus appliqué",
                    "mots-clés : erreur de Qdrant, recherche vectorielle seule",
                    "mots-clés : collections alternées par rang"):
            verifier(nom, False, "recherche_mots_cles absent (code antérieur à la 2.23.0)")
        return
    points = {
        1: payload("DIRECTION/Budget.docx", 0, "budget direction 2027", [GROUPE]),
        2: payload("DIRECTION/Prime.docx", 0, "prime direction 2027 confidentielle", [GROUPE], [GROUPE]),
        3: payload("RH/Salaires.xlsx", 0, "salaires 2027 direction grille", [AUTRE]),
    }
    for i in range(20):
        points[10 + i] = payload(f"DIVERS/Note_{i}.docx", 0, f"procédure archivage courrier note {i}", [GROUPE])
    main._collections_texte = {COLL}
    filtre = main.Filter(must=[main.FieldCondition(key="autorises", match=main.MatchAny(any=[GROUPE]))])

    q = QdrantSimule({COLL: {i: dict(p) for i, p in points.items()}, main.DOCUMENTATION_COLLECTION: {}})
    main.qdrant = q
    r = main.recherche_mots_cles("budget", filtre, 10)
    verifier("mots-clés : document trouvé",
             [c["source"] for c in r] == ["DIRECTION/Budget.docx"] and r[0]["point_id"] == 1
             and r[0]["collection"] == COLL, f"obtenu : {[(c['source'], c.get('point_id')) for c in r]}")

    q.requetes_texte.clear()
    chunks = asyncio.run(main.search_qdrant("salaires direction 2027", user_groups=[GROUPE],
                                            user_email="test@exemple.ch"))
    transmis = [filtre_groupes(f) for _, f in q.requetes_texte]
    verifier("mots-clés : filtre d'accès transmis à Qdrant",
             bool(transmis) and all(g == [GROUPE] for g in transmis)
             and "RH/Salaires.xlsx" not in {c["source"] for c in chunks},
             f"filtres reçus par Qdrant : {transmis}")
    verifier("mots-clés : refus appliqué", "DIRECTION/Prime.docx" not in {c["source"] for c in chunks},
             "FUITE : document refusé au groupe (interdits) renvoyé")

    q.requetes_texte.clear()
    verifier("mots-clés : sans filtre, aucune requête",
             main.recherche_mots_cles("budget", None, 10) == [] and not q.requetes_texte)

    main.qdrant = QdrantSimule({COLL: {i: dict(p) for i, p in points.items()},
                                main.DOCUMENTATION_COLLECTION: {}}, erreur_texte=True)
    try:
        chunks = asyncio.run(main.search_qdrant("budget direction", user_groups=[GROUPE],
                                                user_email="test@exemple.ch"))
        ok = bool(chunks) and "RH/Salaires.xlsx" not in {c["source"] for c in chunks}
        detail = f"{len(chunks)} extrait(s)"
    except Exception as e:
        ok, detail = False, f"{type(e).__name__} : la recherche entière échoue"
    verifier("mots-clés : erreur de Qdrant, recherche vectorielle seule", ok, detail)

    # Scores BM25 de deux collections non comparables : le premier de chaque
    # collection passe avant le deuxième de l'autre, quel que soit son score.
    docu = main.DOCUMENTATION_COLLECTION
    main._collections_texte = {COLL, docu}
    main.qdrant = QdrantSimule({
        COLL: {1: payload("CLIENTS/Contrat_Rochat.docx", 0, "contrat clients axonix", [GROUPE])},
        docu: {7: payload("DOC/annexes.md", 0, "clients axonix axonix démonstration clients", [GROUPE]),
               8: payload("DOC/guide.md", 0, "clients axonix démonstration", [GROUPE])}})
    r = main.recherche_mots_cles("clients axonix démonstration", filtre, 10)
    # En-tête du document (indexer.py, 2.23.0) : sans effet sur l'empreinte de l'extrait
    if hasattr(main, "cle_extrait"):
        corps = "Forfait mensuel : CHF 4 200 HT."
        verifier("empreinte : en-tête du document ignoré",
                 main.cle_extrait("Extrait de « a.docx », dossier CLIENTS/A : Contrat.\n" + corps)
                 == main.cle_extrait("Extrait de « b.docx », dossier CLIENTS/B : Contrat.\n" + corps)
                 == hashlib.md5(corps.encode()).hexdigest())
    else:
        verifier("empreinte : en-tête du document ignoré", False, "cle_extrait absent (code antérieur à la 2.23.0)")
    verifier("mots-clés : collections alternées par rang",
             [c["source"] for c in r][:2] == ["DOC/annexes.md", "CLIENTS/Contrat_Rochat.docx"]
             and [c["rang"] for c in r] == [0, 0, 1],
             f"ordre obtenu : {[(c['source'], c.get('rang'), c['score']) for c in r]}")


# ─────────────────────────────────────────
# preparer_index_texte (2.23.0)
# ─────────────────────────────────────────
class QdrantIndex:
    """Qdrant simulé pour la mise en place de l'index plein texte."""

    def __init__(self, version, schemas):
        self.version = version
        self.schemas = schemas  # {collection: {champ: params}} ; collection absente = inexistante
        self.crees, self.supprimes = [], []

    def info(self):
        return type("V", (), {"version": self.version})()

    def collection_exists(self, collection_name):
        return collection_name in self.schemas

    def get_collection(self, collection_name):
        schema = {k: type("S", (), {"params": v})() for k, v in self.schemas[collection_name].items()}
        return type("C", (), {"payload_schema": schema})()

    def create_payload_index(self, collection_name, field_name, field_schema, wait=True):
        self.crees.append((collection_name, field_name, field_schema))
        self.schemas[collection_name][field_name] = field_schema

    def delete_payload_index(self, collection_name, field_name, wait=True):
        self.supprimes.append((collection_name, field_name))
        del self.schemas[collection_name][field_name]


def tests_index():
    if not hasattr(main, "preparer_index_texte"):
        for nom in ("index : Qdrant 1.19, mots-clés désactivés", "index : absent, créé",
                    "index : conforme, inchangé", "index : réglage différent, recréé",
                    "index : collection absente ignorée",
                    "index : champ ajouté par Qdrant, inchangé"):
            verifier(nom, False, "preparer_index_texte absent (code antérieur à la 2.23.0)")
        return
    attendu = main.params_index_texte()
    doc, docu = COLL, main.DOCUMENTATION_COLLECTION

    main.qdrant = q = QdrantIndex("1.19.2", {doc: {}})
    main.preparer_index_texte()
    verifier("index : Qdrant 1.19, mots-clés désactivés", main._collections_texte == set() and not q.crees)

    main.qdrant = q = QdrantIndex("1.20.0", {doc: {}, docu: {}})
    main.preparer_index_texte()
    verifier("index : absent, créé",
             main._collections_texte == {doc, docu} and len(q.crees) == 2
             and all(c[1] == main.CHAMP_TEXTE and c[2] == attendu for c in q.crees),
             f"créés : {[(c[0], c[1]) for c in q.crees]}")

    q.crees.clear()
    main.preparer_index_texte()
    verifier("index : conforme, inchangé", not q.crees and not q.supprimes and main._collections_texte == {doc, docu})

    autre = attendu.model_copy(update={"stemmer": main.SnowballParams(
        type=main.Snowball.SNOWBALL, language=main.SnowballLanguage.FRENCH)
        if attendu.stemmer is None else None})
    main.qdrant = q = QdrantIndex("1.20.1", {doc: {main.CHAMP_TEXTE: autre}})
    main.preparer_index_texte()
    verifier("index : réglage différent, recréé",
             q.supprimes == [(doc, main.CHAMP_TEXTE)] and len(q.crees) == 1 and q.crees[0][2] == attendu)
    verifier("index : collection absente ignorée", main._collections_texte == {doc})

    # Version future de Qdrant : un champ de plus, à sa valeur par défaut
    plus = attendu.model_copy(update={"on_disk": False})
    main.qdrant = q = QdrantIndex("1.21.0", {doc: {main.CHAMP_TEXTE: plus}})
    main.preparer_index_texte()
    verifier("index : champ ajouté par Qdrant, inchangé", not q.crees and not q.supprimes,
             f"index recréé : supprimés {q.supprimes}, créés {len(q.crees)}")


if __name__ == "__main__":
    qdrant_reel = main.qdrant
    try:
        tests_revalidation()
        tests_extension()
        tests_recherche()
        tests_mots_cles()
        tests_index()
    finally:
        main.qdrant = qdrant_reel
    total, ok = len(RESULTATS), sum(RESULTATS)
    print(f"{ok} tests OK" if ok == total else f"{total - ok} test(s) en échec sur {total}")
    sys.exit(0 if ok == total else 1)
