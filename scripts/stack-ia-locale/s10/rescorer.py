"""
rescorer.py : réévalue des rapports de mesure_s10 (mêmes réponses, mêmes sources)
avec le mesure_s10.py et le jeu de questions installés. Sert après une correction
de l'évaluation, sans refaire les questions.

  docker exec rag-api python3 /rag-pipeline/s10/rescorer.py /rag-pipeline/s10/jeu_questions_s10.json '/var/log/rag/mesure_s10_emb-*_3p_*.json' ...

Pour chaque motif, le rapport le plus récent. Affiche le total, les éléments
interdits et les questions qui ne sont pas conformes aux trois passages.
"""
import collections
import glob
import json
import sys

sys.path.insert(0, "/rag-pipeline/s10")
import mesure_s10 as m  # noqa: E402

jeu = json.load(open(sys.argv[1]))
qs = {q["id"]: q for q in jeu["questions"]}
for motif in sys.argv[2:]:
    fichiers = sorted(glob.glob(motif))
    if not fichiers:
        print(f"{motif} : aucun rapport")
        continue
    d = json.load(open(fichiers[-1]))
    ok, n, interdits = collections.Counter(), collections.Counter(), collections.Counter()
    for r in d["resultats"]:
        q = qs.get(r["id"])
        if not q:
            continue
        ec = m.evaluer(q, r["reponse"], {"sources_accessed": r["sources"], "ancree": r["ancree"]})
        n[r["id"]] += 1
        ok[r["id"]] += not ec
        interdits[r["id"]] += sum(e.startswith("INTERDIT") for e in ec)
    print(f"{fichiers[-1].split('/')[-1]} : {sum(ok.values())}/{sum(n.values())} conformes, "
          f"{sum(interdits.values())} élément(s) interdit(s)")
    print("   " + ", ".join(f"{i} {ok[i]}/{n[i]}" + (f" (interdit x{interdits[i]})" if interdits[i] else "")
                            for i in qs if n[i] and ok[i] != n[i]))
