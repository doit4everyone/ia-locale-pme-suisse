#!/usr/bin/env python3
"""
mesure_s10.py : campagne de mesure du §10 (qualité et durée des réponses).

Pose chaque question du jeu à la RAG API (comme Open WebUI, par /v1), au nom
du compte indiqué, et évalue la réponse sur des critères vérifiables :
  - refus attendu ou non ;
  - document attendu présent dans les sources (journal des requêtes) ;
  - éléments attendus présents dans la réponse ;
  - éléments interdits absents (pièges) ;
  - réponse ancrée selon le juge, sans mention d'avertissement.

À lancer DANS le conteneur rag-api (variables API_TOKEN, LLM_BASE_URL, etc.) :

  docker exec -it rag-api python3 /rag-pipeline/s10/mesure_s10.py \\
      /rag-pipeline/s10/jeu_questions_s10.json --passages 5 --etiquette gpu-reference

Options :
  --passages N     nombre de passages complets du jeu (défaut : 1)
  --etiquette X    nom de la configuration mesurée (figure dans le rapport)
  --ids A,B        ne poser que ces questions
  --decharger      décharger les modèles avant chaque question (mesure à froid)

Les questions sont posées dans l'ordre du jeu, passage après passage : une même
question n'est jamais posée deux fois de suite, ce qui évite de mesurer l'effet
du cache d'Ollama (qui ne garde que le dernier contexte lu).

Pour des réponses reproductibles, fixer LLM_SEED dans le .env avant la campagne
(docker compose up -d rag-api), puis le vider après.
"""
import argparse
import json
import os
import statistics
import sys
import time
import unicodedata
from datetime import datetime, timezone

import httpx

API_URL = "http://localhost:8080/v1/chat/completions"
API_TOKEN = os.environ.get("API_TOKEN", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "qwen3:4b")
LOG_FILE = os.environ.get("LOG_FILE", "/var/log/rag/rag-queries.jsonl")
REFUS = "ne figure pas dans les documents disponibles"
AVERTISSEMENT = "le contrôle automatique n'a pas pu rattacher"


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, sans espaces ni apostrophes (4 200 = 4'200 = 4200)."""
    t = unicodedata.normalize("NFKD", texte.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    for c in (" ", "\u00a0", "\u202f", "'", "\u2019"):
        t = t.replace(c, "")
    return t


def attendre_api(delai: int = 60):
    """Attend que la RAG API réponde (utile juste après un redémarrage)."""
    for _ in range(delai):
        try:
            if httpx.get("http://localhost:8080/health", timeout=2).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    sys.exit("La RAG API ne répond pas après une minute : vérifier docker logs rag-api.")


def decharger():
    for modele in (LLM_MODEL, JUDGE_MODEL):
        if not modele:
            continue
        try:
            httpx.post(f"{LLM_BASE_URL}/api/generate",
                       json={"model": modele, "keep_alive": 0}, timeout=60)
        except Exception as e:
            print(f"  (déchargement de {modele} impossible : {e})")


def derniere_entree(compte: str, depuis: str) -> dict:
    """Entrée du journal des requêtes pour ce compte, postérieure au début de la question."""
    try:
        with open(LOG_FILE, encoding="utf-8") as f:
            lignes = f.readlines()[-50:]
    except OSError:
        return {}
    for ligne in reversed(lignes):
        try:
            e = json.loads(ligne)
        except ValueError:
            continue
        if e.get("user_id") == compte and e.get("timestamp", "") >= depuis:
            return e
    return {}


def evaluer(q: dict, reponse: str, entree: dict) -> list:
    """Renvoie la liste des écarts (vide = conforme)."""
    ecarts = []
    rep_n = normaliser(reponse)
    refus = REFUS in reponse.lower() and len(reponse) < 300
    sources = entree.get("sources_accessed", [])

    if q.get("refus_attendu"):
        if not refus:
            ecarts.append("refus attendu, réponse donnée")
    else:
        if refus:
            ecarts.append("refus à tort")
        principal = q.get("principal_attendu", "")
        if principal and not (sources and principal.lower() in sources[0].lower()):
            ecarts.append(f"document principal : {(sources or ['aucun'])[0].split('/')[-1]} au lieu de {principal}")
        doc = q.get("document_attendu", "")
        if doc:
            if not any(doc.lower() in s.lower() for s in sources):
                ecarts.append(f"document absent des sources : {doc}")
            elif doc.lower() not in reponse.lower():
                ecarts.append(f"document non cité : {doc}")
        for a in q.get("attendus", []):
            if normaliser(a) not in rep_n:
                ecarts.append(f"attendu manquant : {a}")
        if AVERTISSEMENT in reponse:
            ecarts.append("avertissement d'ancrage")
        elif entree and entree.get("ancree") is False:
            ecarts.append("non ancrée selon le juge")
    for i in q.get("interdits", []):
        if normaliser(i) in rep_n:
            ecarts.append(f"INTERDIT présent : {i}")
    return ecarts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jeu")
    ap.add_argument("--passages", type=int, default=1)
    ap.add_argument("--etiquette", default="sans-etiquette")
    ap.add_argument("--ids", default="")
    ap.add_argument("--decharger", action="store_true")
    args = ap.parse_args()

    if not API_TOKEN:
        sys.exit("API_TOKEN absent : lancer ce script dans le conteneur rag-api.")
    jeu = json.load(open(args.jeu, encoding="utf-8"))
    questions = jeu["questions"]
    if args.ids:
        voulus = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in voulus]
    compte_defaut = jeu.get("compte_par_defaut", "")

    config = {
        "etiquette": args.etiquette,
        "date": datetime.now(timezone.utc).isoformat(),
        "llm_model": LLM_MODEL,
        "judge_model": JUDGE_MODEL,
        "embed_model": os.environ.get("EMBED_MODEL", ""),
        "llm_seed": os.environ.get("LLM_SEED", ""),
        "judge_num_gpu": os.environ.get("JUDGE_NUM_GPU", ""),
        "embed_num_gpu": os.environ.get("EMBED_NUM_GPU", ""),
        "candidats": os.environ.get("CANDIDATS", ""),
        "principal_max": os.environ.get("PRINCIPAL_MAX", ""),
        "doc_complet_max": os.environ.get("DOC_COMPLET_MAX", ""),
        "passages": args.passages,
        "a_froid": args.decharger,
    }
    print(f"Configuration : {json.dumps(config, ensure_ascii=False)}\n")
    attendre_api()

    resultats = []
    debut_campagne = time.time()
    for p in range(1, args.passages + 1):
        print(f"=== Passage {p}/{args.passages}")
        for q in questions:
            compte = q.get("compte", compte_defaut)
            if args.decharger:
                decharger()
            depuis = datetime.now(timezone.utc).isoformat()
            t0 = time.time()
            try:
                r = httpx.post(API_URL, timeout=900,
                               headers={"Authorization": f"Bearer {API_TOKEN}",
                                        "X-OpenWebUI-User-Email": compte},
                               json={"model": "rag-api",
                                     "messages": [{"role": "user", "content": q["question"]}]})
                r.raise_for_status()
                reponse = r.json()["choices"][0]["message"]["content"]
                erreur = ""
            except Exception as e:
                reponse, erreur = "", str(e)
            duree = round(time.time() - t0, 1)
            time.sleep(0.5)
            entree = derniere_entree(compte, depuis)
            ecarts = [f"erreur : {erreur}"] if erreur else evaluer(q, reponse, entree)
            statut = "OK" if not ecarts else "ÉCHEC"
            print(f"  {statut:5} {q['id']:22} {duree:6.1f} s  {'; '.join(ecarts)}")
            resultats.append({
                "passage": p, "id": q["id"], "type": q["type"], "compte": compte,
                "statut": statut, "ecarts": ecarts, "duree_s": duree,
                "sources": entree.get("sources_accessed", []),
                "ancree": entree.get("ancree"), "reponse": reponse,
            })

    # Synthèse par question
    print("\n=== Synthèse")
    synthese = {}
    for q in questions:
        rq = [r for r in resultats if r["id"] == q["id"]]
        ok = sum(1 for r in rq if r["statut"] == "OK")
        durees = [r["duree_s"] for r in rq]
        synthese[q["id"]] = {
            "type": q["type"], "conformes": ok, "passages": len(rq),
            "duree_mediane_s": round(statistics.median(durees), 1) if durees else None,
        }
        print(f"  {q['id']:22} {ok}/{len(rq)} conformes, durée médiane "
              f"{synthese[q['id']]['duree_mediane_s']} s")
    total_ok = sum(1 for r in resultats if r["statut"] == "OK")
    interdits = sum(1 for r in resultats for e in r["ecarts"] if e.startswith("INTERDIT"))
    print(f"\nTotal : {total_ok}/{len(resultats)} réponses conformes, "
          f"{interdits} élément(s) interdit(s) présent(s), "
          f"{round((time.time() - debut_campagne) / 60, 1)} min")

    rapport = f"/var/log/rag/mesure_s10_{args.etiquette}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(rapport, "w", encoding="utf-8") as f:
        json.dump({"configuration": config, "synthese": synthese, "resultats": resultats},
                  f, ensure_ascii=False, indent=2)
    print(f"Rapport : {rapport}")


if __name__ == "__main__":
    main()
