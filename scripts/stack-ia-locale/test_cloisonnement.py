"""
test_cloisonnement.py : test de non-divulgation automatisé de la stack RAG.

Deux modes :

--mode acces (par défaut, quelques secondes) : interroge /admin/verifier-acces,
  qui applique exactement les filtres de la recherche (ACL ou permissions
  SharePoint, DENY, Purview) au document visé, sans classement ni génération.
  C'est le test du CLOISONNEMENT, déterministe.
  Verdicts : OK, FUITE (document interdit accessible), REFUS À TORT (document
  autorisé inaccessible), ABSENT (document non indexé : cas invalide).

--mode complet (plusieurs minutes par cas) : pose la question par /query,
  comme un utilisateur. Teste la chaîne complète, recherche et modèle compris.

Vérification principale, déterministe : la liste des sources renvoyée par
/query (les chunks qui ont passé TOUS les filtres : ACL NTFS ou SharePoint,
puis Purview). Un document interdit présent dans les sources est une FUITE,
même si le modèle ne l'a pas cité dans sa réponse.
Vérification secondaire : un « secret » (un code absent de la question) ne
doit pas apparaître dans la réponse d'un compte non autorisé.

Verdicts :
  OK      conforme à l'attendu
  FUITE   document interdit dans les sources, ou secret dans la réponse
  MANQUÉ  document autorisé absent des sources (limite de la recherche,
          pas de sécurité)
  INFO    attendu non renseigné ("?") : résultat observé, sans verdict

Exécution, depuis le conteneur rag-api (réseau interne, jetons déjà présents) :
  docker exec rag-api python3 /rag-pipeline/test_cloisonnement.py /rag-pipeline/cas_cloisonnement.json
Options : --mode acces|complet, --compte <adresse>, --cas <identifiant>

Code de retour : 1 si au moins une FUITE, 0 sinon.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

import httpx

URL = os.getenv("RAG_URL", "http://localhost:8080")
TOKEN = os.getenv("API_TOKEN", "")
ADMIN = os.getenv("ADMIN_TOKEN", "")
DOSSIER_RAPPORT = os.getenv("RAPPORT_DIR", "/var/log/rag")


def interroger(question: str, compte: str) -> dict:
    """Pose la question au nom du compte. Renvoie réponse et sources."""
    r = httpx.post(f"{URL}/query", timeout=900,
                   headers={"Authorization": f"Bearer {TOKEN}"},
                   json={"query": question, "user_id": compte})
    if r.status_code == 200:
        d = r.json()
        return {"statut": 200, "reponse": d.get("answer", ""),
                "sources": [s.get("source", "") for s in d.get("sources", [])]}
    if r.status_code == 422:
        # Réponse jugée non ancrée : bloquée par /query, mais son texte est
        # renvoyé dans le détail. Les sources ne le sont pas.
        detail = r.json().get("detail", {})
        return {"statut": 422, "reponse": detail.get("reponse_bloquee", ""), "sources": None}
    return {"statut": r.status_code, "reponse": r.text[:300], "sources": None}




def verifier_acces(document: str, compte: str) -> dict:
    r = httpx.post(f"{URL}/admin/verifier-acces", timeout=300,
                   headers={"Authorization": f"Bearer {ADMIN}"},
                   json={"user_id": compte, "document": document})
    if r.status_code != 200:
        return {"statut": r.status_code, "erreur": r.text[:200]}
    return {"statut": 200, **r.json()}


def evaluer_acces(attendu, res: dict) -> tuple[str, str]:
    if res["statut"] != 200:
        return "ERREUR", f"HTTP {res['statut']} {res.get('erreur', '')}"
    detail = (f"{res['chunks_accessibles']} chunk(s) accessible(s) sur {res['chunks_total']} "
              f"(après ACL : {res['chunks_apres_acl']})")
    if res["chunks_total"] == 0:
        return "ABSENT", detail
    accessible = res["chunks_accessibles"] > 0
    if attendu == "?":
        return "INFO", detail
    if attendu is False:
        return ("FUITE" if accessible else "OK"), detail
    return ("OK" if accessible else "REFUS À TORT"), detail


def evaluer(cas: dict, attendu, res: dict) -> tuple[str, str]:
    doc = cas["document"]
    secret = cas.get("secret", "")
    sources = res["sources"]
    doc_present = None if sources is None else any(doc in s for s in sources)
    secret_present = bool(secret) and secret in res["reponse"]

    if res["statut"] not in (200, 422):
        return "ERREUR", f"HTTP {res['statut']}"
    observe = []
    if doc_present is not None:
        observe.append("document dans les sources" if doc_present else "document absent des sources")
    else:
        observe.append("sources non renvoyées (réponse non ancrée)")
    if secret:
        observe.append("secret dans la réponse" if secret_present else "secret absent")
    detail = ", ".join(observe)

    if attendu == "?":
        return "INFO", detail
    if attendu is False:
        if doc_present or secret_present:
            return "FUITE", detail
        return "OK", detail
    # attendu autorisé
    if doc_present:
        return "OK", detail
    if doc_present is None and secret_present:
        return "OK", detail
    return "MANQUÉ", detail


def attendre_api(delai: int = 60):
    """Attend que la RAG API réponde : le test est souvent lancé juste après
    un redémarrage (docker compose up -d), avant qu'elle soit prête."""
    for _ in range(delai):
        try:
            if httpx.get(f"{URL}/health", timeout=2).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    sys.exit("La RAG API ne répond pas après une minute : vérifier docker logs rag-api.")


def main():
    attendre_api()
    ap = argparse.ArgumentParser()
    ap.add_argument("fichier_cas")
    ap.add_argument("--compte")
    ap.add_argument("--cas")
    ap.add_argument("--mode", choices=["acces", "complet"], default="acces")
    a = ap.parse_args()
    if a.mode == "complet" and not TOKEN:
        sys.exit("API_TOKEN absent de l'environnement")
    if a.mode == "acces" and not ADMIN:
        sys.exit("ADMIN_TOKEN absent de l'environnement")

    cfg = json.load(open(a.fichier_cas, encoding="utf-8"))
    comptes = [c for c in cfg["comptes"] if not a.compte or c == a.compte]
    resultats, fuites = [], 0
    debut = time.time()

    for cas in cfg["cas"]:
        if a.cas and cas["id"] != a.cas:
            continue
        print(f"\n=== {cas['id']} : {cas['question']}")
        for compte in comptes:
            attendu = cas["attendu"].get(compte, "?")
            t0 = time.time()
            if a.mode == "acces":
                res = verifier_acces(cas["document"], compte)
                verdict, detail = evaluer_acces(attendu, res)
            else:
                res = interroger(cas["question"], compte)
                verdict, detail = evaluer(cas, attendu, res)
            fuites += verdict == "FUITE"
            att = "?" if attendu == "?" else ("autorisé" if attendu else "refusé")
            print(f"  {verdict:7} {compte:32} attendu {att:9} | {detail} ({time.time()-t0:.0f} s)")
            resultats.append({"cas": cas["id"], "compte": compte, "attendu": attendu,
                              "verdict": verdict, "detail": detail, "statut": res["statut"],
                              "sources": res.get("sources")})

    bilan = {}
    for r in resultats:
        bilan[r["verdict"]] = bilan.get(r["verdict"], 0) + 1
    print(f"\nBilan : {bilan}  ({(time.time()-debut)/60:.1f} min)")
    nom = os.path.join(DOSSIER_RAPPORT, f"rapport_cloisonnement_{a.mode}_{datetime.now():%Y%m%d_%H%M%S}.json")
    try:
        with open(nom, "w", encoding="utf-8") as f:
            json.dump({"date": datetime.now().isoformat(), "bilan": bilan, "resultats": resultats},
                      f, ensure_ascii=False, indent=2)
        print(f"Rapport : {nom}")
    except OSError as e:
        print(f"Rapport non écrit : {e}")
    sys.exit(1 if fuites else 0)


if __name__ == "__main__":
    main()
