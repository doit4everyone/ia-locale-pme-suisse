"""
test_echec_droits.py : tests unitaires des échecs d'écriture des droits (2.21.5, 2.21.6, §16.5.2).

Jusqu'à la 2.21.4, une erreur de Qdrant pendant l'écriture des droits d'un
document le faisait passer pour « non indexé » : acl_resolver.py se terminait
avec le code 0, la synchronisation réussissait, aucune alerte ne partait, et le
document gardait ses anciens droits dans Qdrant.

Vérifie, avec un Qdrant simulé, sans partage SMB ni modèle :
  - acl_resolver.py : trois issues distinctes (mis à jour, non indexé, échec),
    une seconde tentative, le code de sortie 2 et le rapport ;
  - la RAG API : liste des documents retirés de la recherche (code 0, 2, autre),
    conservation sur disque, exclusion de la recherche et du contrôle d'accès ;
  - 2.21.6 : un passage incomplet ne vide jamais la liste (orphelins illisibles,
    site SharePoint en erreur, passage interrompu), option ACL_INCERTAIN_FERME,
    registre atomique, refus des questions si le registre est absent ou illisible,
    fichier SharePoint devenu trop volumineux retiré de l'index ;
  - 2.21.7 : échec d'écriture du registre puis redémarrage, marqueur de
    synchronisation inachevée, validation stricte du registre ;
  - 2.21.8 : âge maximal des droits (récent, limite exacte, périmé, inconnu, dans
    le futur), passage partiel, marqueur impossible puis redémarrage, workflow
    arrêté, désactivation du seul contrôle d'âge, état signalé par /health.

Lancement, depuis la VM, dans le conteneur de la RAG API :
  docker exec -w /app rag-api python3 /rag-pipeline/test_echec_droits.py

Attendu : « 42 tests OK », code de sortie 0.
"""

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

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
        filtre = getattr(points_selector, "filter", None) or points_selector
        source = filtre.must[0].match.value
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
def ecrire_json(donnees) -> str:
    chemin = tempfile.mktemp(suffix=".json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(donnees, f)
    return chemin


def il_y_a(heures: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=heures)).isoformat()


def remise_a_zero():
    main._etat = main._etat_vide()
    main._etat["derniere_synchro_complete"] = il_y_a(0)   # synchronisation récente
    main._registre_incertain = False
    main._persistance_ko = False
    main.ACL_INCERTAIN_FERME = False
    main.ACL_AGE_MAX_HEURES = 3.0
    if os.path.exists(main.fichier_marqueur()):
        os.remove(main.fichier_marqueur())


def tests_api():
    main.FICHIER_BLOQUES = tempfile.mktemp(suffix=".json")
    remise_a_zero()
    rapport_acl = ecrire_json({"echecs_ecriture": ["RH/Salaires.xlsx"], "echecs_suppression": ["RH/Supprime.docx"],
                               "echecs_lecture_orphelins": []})
    main.appliquer_resultat_droits("smb", 2, rapport_acl)
    ok_2 = main.sources_bloquees() == {"RH/Salaires.xlsx", "RH/Supprime.docx"}
    main.appliquer_resultat_droits("smb", 1, rapport_acl + ".absent")
    ok_1 = main.sources_bloquees() == {"RH/Salaires.xlsx", "RH/Supprime.docx"}
    main._etat = main._etat_vide()
    main.charger_bloques()
    ok_disque = main.sources_bloquees() == {"RH/Salaires.xlsx", "RH/Supprime.docx"} and not main._registre_incertain
    verifier("API : code 2 retire, code 1 garde, liste relue du disque", ok_2 and ok_1 and ok_disque,
             f"code 2 {ok_2}, code 1 {ok_1}, disque {ok_disque}")

    rapport_sp = ecrire_json({"sites": [{"fichiers": [{"source": "SharePoint/RH/Docs/Grille.xlsx", "statut": "erreur"},
                                                      {"source": "SharePoint/RH/Docs/Note.docx", "statut": "inchangé"}],
                                         "erreurs": [], "prefixes_incomplets": []}]})
    main.appliquer_resultat_droits("sharepoint", 2, rapport_sp)
    verifier("API : SharePoint, fichier en erreur retiré",
             main.est_bloque("SharePoint/RH/Docs/Grille.xlsx") and not main.est_bloque("SharePoint/RH/Docs/Note.docx"))
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

    # ── 2.21.6 : un passage incomplet ne vide jamais la liste ──
    remise_a_zero()
    main.appliquer_resultat_droits("smb", 2, rapport_acl)            # Salaires et Supprime retirés
    q.points[main.COLLECTION][50] = tb.payload("RH/Efface.docx", 0, "fichier effacé du partage", [G])
    incomplet = ecrire_json({"echecs_ecriture": [], "echecs_suppression": [], "echecs_lecture_orphelins": ["documents"],
                             "documents": [{"source_name": s} for s in
                                           ["RH/Salaires.xlsx", "DIRECTION/Budget.docx"] + [f"DIVERS/Note_{i}.docx" for i in range(20)]]})
    main.appliquer_resultat_droits("smb", 2, incomplet)
    verifier("2.21.6 : orphelins illisibles, liste gardée et orphelin probable retiré",
             {"RH/Salaires.xlsx", "RH/Supprime.docx", "RH/Efface.docx"} <= main.sources_bloquees()
             and main._etat["incertain"]["smb"], f"liste {sorted(main.sources_bloquees())}")

    remise_a_zero()
    main.qdrant = QdrantPannes({main.COLLECTION: {}})
    main.qdrant.erreur = True
    main.appliquer_resultat_droits("smb", 2, incomplet)
    verifier("2.21.6 : orphelins illisibles et Qdrant illisible, tout le partage retiré",
             main.est_bloque("RH/Note.docx") and not main.est_bloque("SharePoint/RH/Docs/Note.docx"))
    main.qdrant = q

    remise_a_zero()
    main.appliquer_resultat_droits("sharepoint", 2, rapport_sp)       # Grille.xlsx retiré
    site_ko = ecrire_json({"sites": [{"site": "https://x/sites/RH", "fichiers": [], "erreurs": ["site inaccessible"],
                                      "prefixes_incomplets": ["SharePoint/RH/"]}]})
    main.appliquer_resultat_droits("sharepoint", 2, site_ko)
    verifier("2.21.6 : site SharePoint en erreur, site retiré et liste gardée",
             main.est_bloque("SharePoint/RH/Docs/Autre.docx") and main.est_bloque("SharePoint/RH/Docs/Grille.xlsx")
             and not main.est_bloque("SharePoint/Direction/Docs/Plan.docx"))
    main.appliquer_resultat_droits("sharepoint", 0, site_ko)
    verifier("2.21.6 : passage SharePoint complet, site rétabli", not main.est_bloque("SharePoint/RH/Docs/Autre.docx"))

    remise_a_zero()
    main.appliquer_resultat_droits("smb", 2, rapport_acl)
    main.appliquer_resultat_droits("smb", None, "")
    garde = main.sources_bloquees() == {"RH/Salaires.xlsx", "RH/Supprime.docx"} and not main.est_bloque("RH/Note.docx")
    main.ACL_INCERTAIN_FERME = True
    main.appliquer_resultat_droits("smb", 1, "")
    ferme = main.est_bloque("RH/Note.docx")
    main.appliquer_resultat_droits("smb", 0, "")
    rouvert = not main.est_bloque("RH/Note.docx") and main.sources_bloquees() == set()
    verifier("2.21.6 : passage interrompu, liste gardée ; ACL_INCERTAIN_FERME ferme le partage ; code 0 rétablit",
             garde and ferme and rouvert, f"gardée {garde}, fermé {ferme}, rétabli {rouvert}")

    # ── 2.21.6 : registre ──
    remise_a_zero()
    with open(main.FICHIER_BLOQUES, "w", encoding="utf-8") as f:
        f.write('{"smb": ["RH/Sal')          # écriture interrompue
    main.charger_bloques()
    refus = False
    try:
        asyncio.run(main.search_qdrant("grille salaires", user_groups=[G], user_email="t@x.ch"))
    except main.HTTPException as e:
        refus = e.status_code == 503
    verifier("2.21.6 : registre tronqué au démarrage, questions refusées (503)", main._registre_incertain and refus)

    os.remove(main.FICHIER_BLOQUES)
    main.charger_bloques()
    verifier("2.21.6 : registre absent au démarrage, état inconnu", main._registre_incertain)
    main.finaliser_synchronisation(True, {"smb": 0}, {"smb"})   # synchronisation complète
    chunks = asyncio.run(main.search_qdrant("grille salaires", user_groups=[G], user_email="t@x.ch"))
    verifier("2.21.6 : après une synchronisation complète, questions servies", not main._registre_incertain and bool(chunks))

    remise_a_zero()
    main._etat["smb"] = {"RH/Salaires.xlsx"}
    main.enregistrer_bloques()
    os.makedirs(main.FICHIER_BLOQUES + ".tmp", exist_ok=True)   # écriture impossible
    main._etat["smb"] = set()
    ok_retour = main.enregistrer_bloques() is False and main._registre_ok is False
    with open(main.FICHIER_BLOQUES, encoding="utf-8") as f:
        intact = json.load(f).get("smb") == ["RH/Salaires.xlsx"]
    os.rmdir(main.FICHIER_BLOQUES + ".tmp")
    verifier("2.21.6 : écriture du registre impossible, incident signalé, ancienne version intacte",
             ok_retour and intact, f"signalé {ok_retour}, intacte {intact}")

    # ── 2.21.7 : un échec d'écriture ne doit jamais redevenir une fuite ──
    def question_refusee():
        try:
            asyncio.run(main.search_qdrant("grille salaires", user_groups=[G], user_email="t@x.ch"))
            return False
        except main.HTTPException as e:
            return e.status_code == 503

    remise_a_zero()
    main.enregistrer_bloques()                                   # registre sain, vide
    main.poser_marqueur()                                        # début de synchronisation
    os.makedirs(main.FICHIER_BLOQUES + ".tmp", exist_ok=True)    # disque qui refuse l'écriture
    main.appliquer_resultat_droits("smb", 2, rapport_acl)        # Salaires à retirer, non enregistré
    refus_en_cours = question_refusee()
    os.rmdir(main.FICHIER_BLOQUES + ".tmp")
    main._persistance_ko = False                                  # redémarrage simulé :
    main.charger_bloques()                                        # ancien registre + marqueur présent
    refus_apres_redemarrage = main._registre_incertain and question_refusee()
    verifier("2.21.7 : registre non enregistré, questions refusées, et encore après redémarrage",
             refus_en_cours and refus_apres_redemarrage,
             f"en cours {refus_en_cours}, après redémarrage {refus_apres_redemarrage}")

    main.appliquer_resultat_droits("smb", 2, rapport_acl)        # synchronisation suivante, terminée
    if main.enregistrer_bloques():
        main.retirer_marqueur()
        main.lever_incertitude_registre()
    main.charger_bloques()                                        # nouveau redémarrage
    verifier("2.21.7 : synchronisation terminée et enregistrée, Salaires retiré et questions servies",
             not main._registre_incertain and main.est_bloque("RH/Salaires.xlsx") and not question_refusee())

    remise_a_zero()
    main.enregistrer_bloques()
    os.makedirs(main.fichier_marqueur() + ".tmp", exist_ok=True)
    pose = main.poser_marqueur()
    os.rmdir(main.fichier_marqueur() + ".tmp")
    verifier("2.21.7 : marqueur impossible à écrire, questions refusées", pose is False and question_refusee())

    for nom, contenu in (("vide {}", "{}"),
                         ("smb en chaîne", '{"version": 2, "smb": "RH/Salaires.xlsx", "sharepoint": [], "prefixes": [], '
                                           '"smb_tout": false, "sharepoint_tout": false, "incertain": {"smb": false, "sharepoint": false}}'),
                         ("version inconnue", '{"version": 9, "smb": [], "sharepoint": [], "prefixes": [], '
                                              '"smb_tout": false, "sharepoint_tout": false, "incertain": {"smb": false, "sharepoint": false}}'),
                         ("indicateur non booléen", '{"version": 2, "smb": [], "sharepoint": [], "prefixes": [], '
                                                    '"smb_tout": "non", "sharepoint_tout": false, "incertain": {"smb": false, "sharepoint": false}}')):
        remise_a_zero()
        with open(main.FICHIER_BLOQUES, "w", encoding="utf-8") as f:
            f.write(contenu)
        main.charger_bloques()
        verifier(f"2.21.7 : registre mal formé ({nom}), état inconnu", main._registre_incertain)

    remise_a_zero()
    with open(main.FICHIER_BLOQUES, "w", encoding="utf-8") as f:
        f.write('{"version": 2, "smb": ["RH/Salaires.xlsx"], "sharepoint": [], "prefixes": [], '
                '"smb_tout": false, "sharepoint_tout": false, "incertain": {"smb": false, "sharepoint": false}}')
    main.charger_bloques()
    verifier("2.21.7 : registre conforme accepté", not main._registre_incertain and main.est_bloque("RH/Salaires.xlsx"))

    remise_a_zero()
    for f in (main.FICHIER_BLOQUES, rapport_acl, rapport_sp, incomplet, site_ko):
        if os.path.exists(f):
            os.remove(f)


# ─────────────────────────────────────────
# 2.21.8 : âge maximal des droits
# ─────────────────────────────────────────
def tests_age():
    main.FICHIER_BLOQUES = tempfile.mktemp(suffix=".json")
    points = {1: tb.payload("DIRECTION/Budget.docx", 0, "budget direction 2027 salaires", [G])}
    for i in range(20):
        points[10 + i] = tb.payload(f"DIVERS/Note_{i}.docx", 0, f"procédure archivage courrier note {i}", [G])
    main.qdrant = QdrantPannes({main.COLLECTION: points, main.DOCUMENTATION_COLLECTION: {}})
    main._bm25_chunks = [tb.candidat(i, v) for i, v in points.items()]
    main._bm25_index = tb.BM25Okapi([c["text"].lower().split() for c in main._bm25_chunks])

    def servie():
        try:
            asyncio.run(main.search_qdrant("budget direction", user_groups=[G], user_email="t@x.ch"))
            return True
        except main.HTTPException as e:
            return False if e.status_code == 503 else None

    remise_a_zero()
    main._etat["derniere_synchro_complete"] = il_y_a(1)
    verifier("2.21.8 : synchronisation complète il y a 1 h, question servie, /health ok",
             servie() is True and main.etat_droits() == "ok")

    t0 = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    main._etat["derniere_synchro_complete"] = t0.isoformat()
    a_la_limite = main.droits_frais(t0 + timedelta(hours=3))[0]
    juste_apres = main.droits_frais(t0 + timedelta(hours=3, seconds=1))[0]
    verifier("2.21.8 : âge égal à la limite accepté, une seconde de plus refusée",
             a_la_limite is True and juste_apres is False)

    main._etat["derniere_synchro_complete"] = il_y_a(4)
    verifier("2.21.8 : synchronisation complète il y a 4 h, question refusée, /health droits_perimes",
             servie() is False and main.etat_droits() == "droits_perimes")

    main._etat["derniere_synchro_complete"] = None
    inconnu = servie() is False and main.etat_droits() == "droits_inconnus"
    main._etat["derniere_synchro_complete"] = il_y_a(-1)
    futur = servie() is False
    verifier("2.21.8 : horodatage absent ou dans le futur, question refusée", inconnu and futur,
             f"absent {inconnu}, futur {futur}")

    remise_a_zero()
    with open(main.FICHIER_BLOQUES, "w", encoding="utf-8") as f:
        f.write('{"version": 3, "smb": [], "sharepoint": [], "prefixes": [], "smb_tout": false, '
                '"sharepoint_tout": false, "incertain": {"smb": false, "sharepoint": false}, '
                '"derniere_synchro_complete": "hier soir"}')
    main.charger_bloques()
    verifier("2.21.8 : horodatage illisible dans le registre, état inconnu", main._registre_incertain)

    remise_a_zero()
    with open(main.FICHIER_BLOQUES, "w", encoding="utf-8") as f:
        f.write('{"version": 2, "smb": [], "sharepoint": [], "prefixes": [], "smb_tout": false, '
                '"sharepoint_tout": false, "incertain": {"smb": false, "sharepoint": false}}')
    main.charger_bloques()
    verifier("2.21.8 : registre de la 2.21.7 accepté, mais droits non datés, question refusée",
             not main._registre_incertain and servie() is False)

    # Passage partiel : l'horodatage ne bouge pas
    remise_a_zero()
    ancien = il_y_a(2)
    main._etat["derniere_synchro_complete"] = ancien
    main.poser_marqueur()
    main._etat["incertain"]["smb"] = True
    main.finaliser_synchronisation(True, {"smb": 2}, {"smb"})
    verifier("2.21.8 : passage incomplet, horodatage inchangé",
             main._etat["derniere_synchro_complete"] == ancien)

    # Marqueur impossible, puis redémarrage, puis le délai expire
    remise_a_zero()
    main._etat["derniere_synchro_complete"] = il_y_a(2.5)
    main.enregistrer_bloques()
    os.makedirs(main.fichier_marqueur() + ".tmp", exist_ok=True)
    pose = main.poser_marqueur()
    main.finaliser_synchronisation(pose, {}, {"smb"})
    os.rmdir(main.fichier_marqueur() + ".tmp")
    main._persistance_ko = False                    # redémarrage simulé
    main.charger_bloques()
    servie_avant_delai = servie()
    main._etat["derniere_synchro_complete"] = il_y_a(3.5)   # une heure plus tard, sans synchronisation
    verifier("2.21.8 : marqueur impossible puis redémarrage, ancien horodatage gardé, refus après le délai",
             pose is False and servie_avant_delai is True and servie() is False)

    # Synchronisation complète suivante : nouvel horodatage écrit, reprise
    remise_a_zero()
    main._etat["derniere_synchro_complete"] = il_y_a(4)
    main.poser_marqueur()
    main.finaliser_synchronisation(True, {"smb": 0}, {"smb"})
    main.charger_bloques()                          # redémarrage simulé
    verifier("2.21.8 : synchronisation complète, horodatage écrit, marqueur retiré, questions servies",
             servie() is True and not os.path.exists(main.fichier_marqueur()))

    # Workflow n8n arrêté : aucune tentative, le délai expire quand même
    remise_a_zero()
    main._etat["derniere_synchro_complete"] = il_y_a(3.02)
    verifier("2.21.8 : aucune synchronisation depuis plus de 3 h, question refusée, /health droits_perimes",
             servie() is False and main.etat_droits() == "droits_perimes")

    # 0 désactive le seul contrôle d'âge
    main.ACL_AGE_MAX_HEURES = 0
    age_ignore = servie() is True
    main._registre_incertain = True
    incertain_garde = servie() is False and main.etat_droits() == "droits_inconnus"
    verifier("2.21.8 : ACL_AGE_MAX_HEURES=0, âge ignoré, registre inconnu toujours refusé",
             age_ignore and incertain_garde, f"âge ignoré {age_ignore}, registre {incertain_garde}")

    remise_a_zero()
    for f in (main.FICHIER_BLOQUES, main.fichier_marqueur()):
        if os.path.exists(f):
            os.remove(f)


# ─────────────────────────────────────────
# sp_indexer.py : fichier devenu trop volumineux
# ─────────────────────────────────────────
def charger_sp():
    """sp_indexer.py importe indexer et auth : dépôt ou conteneur."""
    if not os.path.exists(os.path.join(ICI, "indexer.py")) and os.path.exists(os.path.join(ICI, "anon_indexer.py")):
        spec = importlib.util.spec_from_file_location("indexer", os.path.join(ICI, "anon_indexer.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules["indexer"] = mod
    spec = importlib.util.spec_from_file_location("sp_indexer", os.path.join(ICI, "sp_indexer.py"))
    sp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sp)
    return sp


def tests_sharepoint():
    import argparse
    sp = charger_sp()
    source = "SharePoint/RH/Docs/Grille.docx"
    coll = sp.idx.COLLECTION
    e = {"name": "Grille.docx", "size": sp.SP_MAX_BYTES + 1, "id": "x"}
    args = argparse.Namespace(dry_run=False, force=False)
    q = QdrantPannes({coll: {1: p(source, ["BSCULIER\\RH"]), 2: p("SharePoint/RH/Docs/Autre.docx", [G])}})
    entree = sp.traiter_fichier(None, q, None, {}, set(), "https://x/sites/RH", {"id": "d"}, "Grille.docx", e, source, args)
    restants = {v["source"] for v in q.points[coll].values()}
    verifier("2.21.6 : SharePoint, fichier devenu trop volumineux retiré de l'index",
             source not in restants and "SharePoint/RH/Docs/Autre.docx" in restants
             and entree["statut"].startswith("trop volumineux"), f"statut {entree.get('statut')}, restants {restants}")

    q = QdrantPannes({coll: {1: p(source, [G])}}, suppression_refusee={source})
    try:
        sp.traiter_fichier(None, q, None, {}, set(), "https://x/sites/RH", {"id": "d"}, "Grille.docx", e, source, args)
        remonte = False
    except RuntimeError:
        remonte = True   # indexer_site en fait un fichier « erreur », retiré de la recherche
    verifier("2.21.6 : SharePoint, suppression refusée remontée en erreur", remonte)


if __name__ == "__main__":
    qdrant_reel, fichier_reel = main.qdrant, main.FICHIER_BLOQUES
    etat_reel, incertain_reel, ferme_reel = main._etat, main._registre_incertain, main.ACL_INCERTAIN_FERME
    persistance_reelle, age_reel = main._persistance_ko, main.ACL_AGE_MAX_HEURES
    try:
        tests_resolveur()
        tests_passage()
        tests_api()
        tests_age()
        tests_sharepoint()
    finally:
        main.qdrant, main.FICHIER_BLOQUES = qdrant_reel, fichier_reel
        main._etat, main._registre_incertain, main.ACL_INCERTAIN_FERME = etat_reel, incertain_reel, ferme_reel
        main._persistance_ko, main.ACL_AGE_MAX_HEURES = persistance_reelle, age_reel
    total, ok = len(RESULTATS), sum(RESULTATS)
    print(f"{ok} tests OK" if ok == total else f"{total - ok} test(s) en échec sur {total}")
    sys.exit(0 if ok == total else 1)
