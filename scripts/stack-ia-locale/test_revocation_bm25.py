"""
test_revocation_bm25.py : test en lab d'un droit retiré sur le chemin BM25 (2.21.3, point 10).

Reproduit, sur le vrai Qdrant, le cas corrigé en 2.21.3 : un droit retiré dans
Qdrant après la construction de l'index BM25, sans reconstruction de l'index.

Déroulement :
  1. construit un index BM25 dans ce processus, comme la RAG API au démarrage ;
  2. pose la question au nom du compte : le document doit être renvoyé ;
  3. retire le droit dans Qdrant : les extraits du document ne sont plus
     autorisés qu'à un groupe fictif (« test-revocation-bm25 ») ;
  4. repose la question SANS reconstruire l'index, avec puis sans extension
     du contexte : le document ne doit plus être renvoyé ;
  5. remet les droits d'origine, dans tous les cas, puis les contrôle.

Le test ne fait que RETIRER un droit, pendant quelques secondes : il ne donne
accès à rien. Pendant ce temps, le document est invisible pour tous.

Sur une installation en 2.21.2 ou avant : FUITE attendue (le défaut).
Après la 2.21.3 : OK attendu.

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

from qdrant_client.models import Filter, FieldCondition, MatchValue

GROUPE_FICTIF = "test-revocation-bm25"


def correspond(source: str, document: str) -> bool:
    """Chemin complet ou nom de fichier identique, comme test_cloisonnement.py."""
    return source == document or source.rsplit("/", 1)[-1] == document


def sources_trouvees(chunks: list[dict], document: str) -> list[str]:
    return sorted({c["source"] for c in chunks if correspond(c.get("source", ""), document)})


def trouve_par_bm25(question: str, document: str) -> bool:
    """Le document figure-t-il parmi les candidats BM25 de la question ?"""
    if main._bm25_index is None:
        return False
    scores = main._bm25_index.get_scores(question.lower().split())
    classes = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:main.CANDIDATS * 2]
    return any(s >= 0.01 and correspond(main._bm25_chunks[i]["source"], document) for i, s in classes)


def question_automatique(document: str, nombre: int = 4) -> str:
    """Les mots les plus rares du document, d'après l'index BM25 (idf le plus élevé).
    Mots de cinq lettres au moins, sans chiffres, pris dans ses premiers extraits."""
    if main._bm25_index is None:
        return ""
    idf = main._bm25_index.idf
    mots: dict[str, float] = {}
    extraits = [c for c in main._bm25_chunks if correspond(c["source"], document)][:3]
    for c in extraits:
        for m in c["text"].lower().split():
            if len(m) >= 5 and m.isalpha():
                mots[m] = idf.get(m, 0.0)
    choisis = sorted(mots, key=lambda m: mots[m], reverse=True)[:nombre]
    return " ".join(choisis)


def rechercher(question: str, groupes: list[str], compte: str, seuil: float) -> list[dict]:
    main.CONTEXT_THRESHOLD = seuil
    return asyncio.run(main.search_qdrant(question, user_groups=groupes, user_email=compte))


def lire_droits(source: str) -> list[tuple]:
    """(collection, identifiant, autorises, interdits) de chaque extrait du document."""
    droits = []
    for collection in (main.COLLECTION, main.DOCUMENTATION_COLLECTION):
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
    main.build_bm25_index()
    if not any(correspond(c["source"], a.document) for c in main._bm25_chunks):
        print(f"NON CONCLUANT : aucun extrait de « {a.document} » dans l'index. Vérifier le nom du fichier.")
        return 3
    if not a.question:
        a.question = question_automatique(a.document)
    print(f"Question : {a.question}")
    if not trouve_par_bm25(a.question, a.document):
        print("NON CONCLUANT : la recherche par mots-clés ne trouve pas ce document. "
              "Choisir des mots plus rares du document.")
        return 3
    avant = sources_trouvees(rechercher(a.question, groupes, a.compte, seuil_config), a.document)
    if not avant:
        print("NON CONCLUANT : le document n'est pas renvoyé avant le retrait du droit. "
              "Choisir une autre question.")
        return 3
    source = avant[0]
    droits = lire_droits(source)
    print(f"Document : {source} ({len(droits)} extrait(s)), renvoyé avant le retrait : oui")

    verdicts = []
    restaure = False
    try:
        par_collection: dict[str, list] = {}
        for collection, pid, _, _ in droits:
            par_collection.setdefault(collection, []).append(pid)
        for collection, ids in par_collection.items():
            main.qdrant.set_payload(collection_name=collection, points=ids,
                                    payload={"autorises": [GROUPE_FICTIF], "interdits": []})
        print(f"Droit retiré dans Qdrant (autorisé à « {GROUPE_FICTIF} » seulement), index BM25 inchangé")
        for seuil, libelle in ((seuil_config, "avec extension du contexte (réglage actuel)"),
                               (2.0, "sans extension du contexte")):
            apres = sources_trouvees(rechercher(a.question, groupes, a.compte, seuil), a.document)
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
