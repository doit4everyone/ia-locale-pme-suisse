#!/usr/bin/env python3
"""
charge_s10.py : mesure de la charge, N questions posées en même temps.

Complète mesure_s10.py (qui pose les questions une par une) : pour chaque
palier (1, 2, 4, 8 questions simultanées par défaut), lance N demandes en
parallèle à la RAG API, comme le feraient N utilisateurs d'Open WebUI, et
relève la durée de chaque réponse, la durée totale du palier et le nombre
d'échecs. Chaque demande pose une question différente du jeu (celles qui
doivent recevoir une réponse, pas un refus).

À lancer DANS le conteneur rag-api :

  docker exec -it rag-api python3 /rag-pipeline/s10/charge_s10.py \\
      /rag-pipeline/s10/jeu_questions_s10.json --etiquette vllm-charge

Options :
  --paliers 1,2,4,8     nombres de questions simultanées
  --repetitions N       nombre de séries par palier (défaut : 2)
  --etiquette X         nom de la configuration mesurée (figure dans le rapport)
  --pause S             pause entre deux paliers, en secondes (défaut : 20)

La mémoire de la carte ne se lit pas depuis le conteneur : relever en parallèle,
sur le serveur de modèles, `nvidia-smi --query-gpu=memory.used --format=csv -l 5`
(ou, sous Windows, `nvidia-smi.exe` dans une boucle), et noter le maximum de chaque palier.

Ne pas lancer pendant une synchronisation (/admin/sync) : elle fausserait les durées.
Les tâches d'arrière-plan d'Open WebUI ne sont pas simulées ; elles se mesurent
séparément (nombre de lignes ajoutées au journal par question).
"""
import argparse
import json
import os
import statistics
import sys
import threading
import time
import unicodedata
from datetime import datetime, timezone

import httpx

API_URL = os.environ.get("CHARGE_API_URL", "http://localhost:8080/v1/chat/completions")
API_TOKEN = os.environ.get("API_TOKEN", "")
REFUS = "ne figure pas dans les documents disponibles"
AVERTISSEMENT = "le contrôle automatique n'a pas pu rattacher"


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, sans espaces ni apostrophes (4 200 = 4'200 = 4200)."""
    t = unicodedata.normalize("NFKD", texte.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    for c in (" ", " ", " ", "'", "’"):
        t = t.replace(c, "")
    return t


def ecarts_reponse(q: dict, reponse: str) -> list:
    """Contrôle sur la seule réponse (le journal ne permet pas d'attribuer les sources
    à une demande précise quand plusieurs arrivent en même temps)."""
    ecarts = []
    rep_n = normaliser(reponse)
    if REFUS in reponse.lower() and len(reponse) < 300:
        ecarts.append("refus à tort")
    if AVERTISSEMENT in reponse:
        ecarts.append("avertissement d'ancrage")
    for a in q.get("attendus", []):
        if normaliser(a) not in rep_n:
            ecarts.append(f"attendu manquant : {a}")
    for i in q.get("interdits", []):
        if normaliser(i) in rep_n:
            ecarts.append(f"INTERDIT présent : {i}")
    return ecarts


def poser(q: dict, compte: str, sortie: list, depart: threading.Event):
    depart.wait()
    t0 = time.time()
    erreur, reponse = "", ""
    try:
        r = httpx.post(API_URL, timeout=1800,
                       headers={"Authorization": f"Bearer {API_TOKEN}",
                                "X-OpenWebUI-User-Email": compte},
                       json={"model": "rag-api",
                             "messages": [{"role": "user", "content": q["question"]}]})
        r.raise_for_status()
        reponse = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        erreur = str(e) or type(e).__name__
    duree = round(time.time() - t0, 1)
    ecarts = [f"erreur : {erreur}"] if erreur else ecarts_reponse(q, reponse)
    sortie.append({"id": q["id"], "duree_s": duree, "erreur": erreur,
                   "ecarts": ecarts, "reponse": reponse})


def percentile(valeurs, p):
    if not valeurs:
        return None
    v = sorted(valeurs)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jeu")
    ap.add_argument("--paliers", default="1,2,4,8")
    ap.add_argument("--repetitions", type=int, default=2)
    ap.add_argument("--etiquette", default="sans-etiquette")
    ap.add_argument("--pause", type=int, default=20)
    args = ap.parse_args()

    if not API_TOKEN:
        sys.exit("API_TOKEN absent : lancer ce script dans le conteneur rag-api.")
    jeu = json.load(open(args.jeu, encoding="utf-8"))
    compte = jeu.get("compte_par_defaut", "")
    questions = [q for q in jeu["questions"]
                 if not q.get("refus_attendu") and q.get("compte", compte) == compte]
    if len(questions) < 2:
        sys.exit("Le jeu ne contient pas assez de questions répondables pour le compte par défaut.")
    paliers = [int(x) for x in args.paliers.split(",")]

    config = {
        "etiquette": args.etiquette,
        "date": datetime.now(timezone.utc).isoformat(),
        "llm_api": os.environ.get("LLM_API", "") or "ollama",
        "llm_model": os.environ.get("LLM_MODEL", ""),
        "judge_model": os.environ.get("JUDGE_MODEL", ""),
        "paliers": paliers, "repetitions": args.repetitions,
        "questions_disponibles": len(questions),
    }
    print(f"Configuration : {json.dumps(config, ensure_ascii=False)}\n")

    # Échauffement : une question seule, pour que les modèles soient chargés.
    print("Échauffement (une question)...")
    tmp = []
    ev = threading.Event(); ev.set()
    poser(questions[0], compte, tmp, ev)
    print(f"  {tmp[0]['duree_s']} s\n")

    rapport_paliers, tous = [], []
    curseur = 0
    for n in paliers:
        for rep in range(1, args.repetitions + 1):
            sortie, fils = [], []
            depart = threading.Event()
            for k in range(n):
                q = questions[(curseur + k) % len(questions)]
                t = threading.Thread(target=poser, args=(q, compte, sortie, depart))
                t.start(); fils.append(t)
            curseur += n
            t0 = time.time()
            depart.set()
            for t in fils:
                t.join()
            total = round(time.time() - t0, 1)
            durees = [s["duree_s"] for s in sortie if not s["erreur"]]
            echecs = sum(1 for s in sortie if s["erreur"])
            ecarts = sum(1 for s in sortie if s["ecarts"])
            med = round(statistics.median(durees), 1) if durees else None
            mx = max(durees) if durees else None
            print(f"  {n:2} simultanées, série {rep} : médiane {med} s, max {mx} s, "
                  f"total {total} s, erreurs {echecs}, réponses avec écart {ecarts}/{len(sortie)}")
            rapport_paliers.append({"simultanees": n, "serie": rep, "mediane_s": med,
                                    "max_s": mx, "total_s": total, "erreurs": echecs,
                                    "reponses_avec_ecart": ecarts})
            tous.extend({"simultanees": n, "serie": rep, **s} for s in sortie)
            time.sleep(args.pause)

    print("\n=== Synthèse par palier")
    synthese = {}
    for n in paliers:
        d = [s["duree_s"] for s in tous if s["simultanees"] == n and not s["erreur"]]
        e = sum(1 for s in tous if s["simultanees"] == n and s["erreur"])
        a = sum(1 for s in tous if s["simultanees"] == n and s["ecarts"])
        nb = sum(1 for s in tous if s["simultanees"] == n)
        synthese[n] = {"demandes": nb, "mediane_s": round(statistics.median(d), 1) if d else None,
                       "p95_s": percentile(d, 0.95), "max_s": max(d) if d else None,
                       "erreurs": e, "reponses_avec_ecart": a}
        print(f"  {n:2} simultanées : médiane {synthese[n]['mediane_s']} s, "
              f"P95 {synthese[n]['p95_s']} s, max {synthese[n]['max_s']} s, "
              f"erreurs {e}/{nb}, écarts {a}/{nb}")
    if 1 in synthese and synthese[1]["mediane_s"]:
        base = synthese[1]["mediane_s"]
        print("\nRapport à une question seule (médiane) :")
        for n in paliers:
            if synthese[n]["mediane_s"]:
                print(f"  {n:2} simultanées : x{round(synthese[n]['mediane_s'] / base, 2)}")

    rapport = f"/var/log/rag/charge_s10_{args.etiquette}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(rapport, "w", encoding="utf-8") as f:
        json.dump({"configuration": config, "paliers": rapport_paliers,
                   "synthese": synthese, "resultats": tous}, f, ensure_ascii=False, indent=2)
    print(f"Rapport : {rapport}")


if __name__ == "__main__":
    main()
