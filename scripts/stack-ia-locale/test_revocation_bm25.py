"""
test_revocation_bm25.py : test en lab d'un droit retiré sur le chemin BM25 (2.21.3, point 10 ; 2.23.0).

Vérifie, sur le vrai Qdrant, qu'un droit retiré dans Qdrant est respecté aussitôt
par la recherche par mots-clés. Jusqu'à la 2.22, cette recherche passait par un
index en mémoire, instantané des droits (corrigé en 2.21.3 par la relecture
revalider_bm25). Depuis la 2.23.0, elle est faite par Qdrant avec le filtre
d'accès : il n'y a plus d'instantané, et la relecture reste en seconde barrière.

Déroulement :
  1. met en place l'index plein texte, comme la RAG API au démarrage ;
  2. pose la question au nom du compte : le document doit être renvoyé, et
     trouvé par la recherche par mots-clés ;
  3. retire le droit dans Qdrant : les extraits du document ne sont plus
     autorisés qu'à un groupe fictif (« test-revocation-bm25 ») ;
  4. repose la question, avec puis sans extension du contexte : le document ne
     doit plus être renvoyé, ni par la recherche par mots-clés seule ;
  5. remet les droits d'origine, dans tous les cas, puis les contrôle.

Le test ne fait que RETIRER un droit, pendant quelques secondes : il ne donne
accès à rien. Pendant ce temps, le document est invisible pour tous.

Demande la RAG API 2.23.0 ou plus, et Qdrant 1.20 ou plus.

Lancement, depuis la VM, dans le conteneur de la RAG API, hors de l'heure
pleine (la synchronisation horaire réécrit les droits) :
  docker exec -w /app rag-api python3 /rag-pipeline/test_revocation_bm25.py --compte <compte> --document <nom du fichier>

Sans --question, le test compose lui-même la question avec les mots les plus
rares du document (ceux que la recherche par mots-clés distingue le mieux) et
l'affiche. --question permet d'imposer d'autres mots.

Code de retour : 0 OK, 2 FUITE, 3 non concluant, 4 droits non restaurés.
Si les droits n'ont pas pu être restaurés, les recalculer avec acl_resolver.py
(§0, étape 13).
"""

import argparse
import asyncio
import sys

sys.path.insert(0, "/app")
import main  # code de la RAG API, dans le conteneur

from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny, MatchText

GROUPE_FICTIF = "test-revocation-bm25"
COLLECTIONS = (main.COLLECTION, main.DOCUMENTATION_COLLECTION)


def correspond(source: str, document: str) -> bool:
    """Chemin complet ou nom de fichier identique, comme test_cloisonnement.py."""
    return source == document or source.rsplit("/", 1)[-1] == document


def sources_trouvees(chunks: list[dict], document: str) -> list[str]:
    return sorted({c["source"] for c in chunks if correspond(c.get("source", ""), document)})


def filtre_acces(groupes: list[str]) -> Filter:
    """Le filtre ALLOW de search_qdrant."""
    return Filter(must=[FieldCondition(key="autorises", match=MatchAny(any=groupes))])


def trouve_par_mots_cles(question: str, document: str, groupes: list[str]) -> bool:
    """Le document figure-t-il parmi les candidats de la recherche par mots-clés ?"""
    candidats = main.recherche_mots_cles(question, filtre_acces(groupes), main.CANDIDATS)
    return any(correspond(c["source"], document) for c in candidats)


def trouver_source(document: str) -> tuple[str, str] | None:
    """(collection, chemin complet) du document, d'après les sources indexées."""
    for collection in COLLECTIONS:
        offset = None
        while True:
            try:
                page, offset = main.qdrant.scroll(collection_name=collection, limit=2_000, offset=offset,
                                                  with_payload=["source"])
            except Exception:
                break  # collection absente
            for p in page:
                if correspond(p.payload.get("source", ""), document):
                    return collection, p.payload["source"]
            if offset is None:
                break
    return None


def question_automatique(collection: str, source: str, nombre: int = 4) -> str:
    """Les mots les plus rares du document dans sa collection (le moins d'extraits
    qui les contiennent, d'après l'index plein texte). Mots de cinq lettres au
    moins, sans chiffres, pris dans ses premiers extraits."""
    page, _ = main.qdrant.scroll(
        collection_name=collection, limit=3, with_payload=["text"],
        scroll_filter=Filter(must=[FieldCondition(key="source", match=MatchValue(value=source))]))
    mots = {m.strip(".,;:!?()«»\"'").lower() for p in page for m in p.payload.get("text", "").split()}
    rarete = {}
    for m in mots:
        if len(m) >= 5 and m.isalpha():
            try:
                rarete[m] = main.qdrant.count(
                    collection_name=collection, exact=True,
                    count_filter=Filter(must=[FieldCondition(key=main.CHAMP_TEXTE, match=MatchText(text=m))])).count
            except Exception:
                continue
    choisis = sorted((m for m in rarete if rarete[m] > 0), key=lambda m: rarete[m])[:nombre]
    return " ".join(choisis)


def rechercher(question: str, groupes: list[str], compte: str, seuil: float) -> list[dict]:
    main.CONTEXT_THRESHOLD = seuil
    return asyncio.run(main.search_qdrant(question, user_groups=groupes, user_email=compte))


def lire_droits(source: str) -> list[tuple]:
    """(collection, identifiant, autorises, interdits) de chaque extrait du document."""
    droits = []
    for collection in COLLECTIONS:
        offset = None
        while True:
            try:
                page, offset = main.qdrant.scroll(
                    collection_name=collection, limit=500, offset=offset, with_payload=True,
                    scroll_filter=Filter(must=[FieldCondition(key="source", match=MatchValue(value=source))]))
            except Exception:
                break  # collection absente
            for p in page:
                droits.append((collection, p.id, list(p.payload.get("autorises", [])),
                               list(p.payload.get("interdits", []))))
            if offset is None:
                break
    return droits


def restaurer(droits: list[tuple]) -> bool:
    """Remet les droits d'origine, puis vérifie point par point."""
    groupes: dict[tuple, list] = {}
    for collection, pid, autorises, interdits in droits:
        groupes.setdefault((collection, tuple(autorises), tuple(interdits)), []).append(pid)
    for (collection, autorises, interdits), ids in groupes.items():
        main.qdrant.set_payload(collection_name=collection, points=ids,
                                payload={"autorises": list(autorises), "interdits": list(interdits)})
    for collection, pid, autorises, interdits in droits:
        p = main.qdrant.retrieve(collection_name=collection, ids=[pid], with_payload=True)
        if not p or p[0].payload.get("autorises") != autorises or p[0].payload.get("interdits") != interdits:
            return False
    return True


def principal() -> int:
    ap = argparse.ArgumentParser(description="Droit retiré sur le chemin BM25 (point 10)")
    ap.add_argument("--compte", required=True, help="adresse du compte qui a accès au document")
    ap.add_argument("--document", required=True, help="nom du fichier ou chemin complet")
    ap.add_argument("--question", default="", help="facultatif : mots rares du document")
    a = ap.parse_args()

    if not hasattr(main, "recherche_mots_cles"):
        print("NON CONCLUANT : RAG API antérieure à la 2.23.0 (index BM25 en mémoire). "
              "Utiliser le test_revocation_bm25.py de sa version.")
        return 3
    groupes = main.get_user_groups(a.compte)
    if not groupes:
        print(f"NON CONCLUANT : droits de {a.compte} introuvables dans l'annuaire")
        return 3
    seuil_config = main.CONTEXT_THRESHOLD

    # Ce processus n'a jamais synchronisé : la règle d'âge des droits (2.21.8)
    # refuserait toute question. Le test porte sur la recherche par mots-clés,
    # pas sur l'âge des droits (testé par test_echec_droits.py) : ce seul
    # contrôle est désactivé ici, dans ce processus de test uniquement.
    if hasattr(main, "ACL_AGE_MAX_HEURES"):
        main.ACL_AGE_MAX_HEURES = 0
    main.preparer_index_texte()
    trouve = trouver_source(a.document)
    if not trouve:
        print(f"NON CONCLUANT : aucun extrait de « {a.document} » dans Qdrant. Vérifier le nom du fichier.")
        return 3
    collection, source = trouve
    if collection not in main._collections_texte:
        print(f"NON CONCLUANT : index plein texte absent dans '{collection}' (Qdrant 1.20 ou plus requis, "
              "voir le journal [BM25])")
        return 3
    if not a.question:
        a.question = question_automatique(collection, source)
    print(f"Question : {a.question}")
    if not trouve_par_mots_cles(a.question, source, groupes):
        print("NON CONCLUANT : la recherche par mots-clés ne trouve pas ce document. "
              "Choisir des mots plus rares du document.")
        return 3
    avant = sources_trouvees(rechercher(a.question, groupes, a.compte, seuil_config), source)
    if not avant:
        print("NON CONCLUANT : le document n'est pas renvoyé avant le retrait du droit. "
              "Choisir une autre question.")
        return 3
    droits = lire_droits(source)
    print(f"Document : {source} ({len(droits)} extrait(s)), renvoyé avant le retrait : oui")

    verdicts = []
    restaure = False
    try:
        par_collection: dict[str, list] = {}
        for coll, pid, _, _ in droits:
            par_collection.setdefault(coll, []).append(pid)
        for coll, ids in par_collection.items():
            main.qdrant.set_payload(collection_name=coll, points=ids,
                                    payload={"autorises": [GROUPE_FICTIF], "interdits": []})
        print(f"Droit retiré dans Qdrant (autorisé à « {GROUPE_FICTIF} » seulement)")
        mots_cles = trouve_par_mots_cles(a.question, source, groupes)
        verdicts.append("FUITE" if mots_cles else "OK")
        print(f"{verdicts[-1]:6} recherche par mots-clés seule : document "
              f"{'trouvé' if mots_cles else 'non trouvé'}")
        for seuil, libelle in ((seuil_config, "avec extension du contexte (réglage actuel)"),
                               (2.0, "sans extension du contexte")):
            apres = sources_trouvees(rechercher(a.question, groupes, a.compte, seuil), source)
            verdict = "FUITE" if apres else "OK"
            verdicts.append(verdict)
            print(f"{verdict:6} {libelle} : document {'renvoyé' if apres else 'non renvoyé'}")
    finally:
        try:
            restaure = restaurer(droits)
        except Exception as e:
            print(f"Restauration en erreur : {type(e).__name__} {e}")
        print("Droits d'origine restaurés et contrôlés" if restaure else
              "ATTENTION : droits NON restaurés. Lancer acl_resolver.py (§0, étape 13).")

    if not restaure:
        return 4
    print(f"Bilan : {'FUITE' if 'FUITE' in verdicts else 'OK'}")
    return 2 if "FUITE" in verdicts else 0


if __name__ == "__main__":
    sys.exit(principal())
