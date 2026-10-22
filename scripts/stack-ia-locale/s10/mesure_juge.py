#!/usr/bin/env python3
"""
mesure_juge.py : que détecte vraiment le juge ? (2.21.9)

Le juge vérifie que chaque affirmation d'une réponse est tirée des sources.
Ce script mesure ce qu'il détecte, en lui présentant des réponses réelles et
des réponses volontairement faussées. À relancer après toute modification du
juge (prompt, modèle, fenêtre) ou du modèle de rédaction.

Pour chaque question du jeu qui attend une réponse :
  1. recherche et rédaction, UNE fois, comme la RAG API (au nom du compte) ;
  2. trois versions FAUSSES de la réponse, fabriquées automatiquement :
       chiffre      un nombre de la réponse, présent dans les sources, est
                    changé (les numéros de liste ne sont pas touchés) ;
       invente      une phrase avec un fait absent des sources est insérée,
                    avec une vraie citation ;
       attribution  les deux premiers documents cités sont intervertis (pas
                    toujours une faute : deux documents peuvent dire la même
                    chose) ;
     (une version est sautée si la réponse ne s'y prête pas) ;
  3. la réponse réelle et chaque version fausse sont jugées plusieurs fois
     (température 0 : les verdicts doivent être stables).

Le script mesure : les réponses réelles acceptées, les versions fausses
refusées, si la faute figure dans la liste du juge (localisée), combien
d'affirmations justes il signale en plus, et la stabilité des verdicts.

Historique (§10.12) : écrit pour comparer le juge en service à un « juge
partagé » qui reprenait le prompt de la rédaction pour gagner du temps avec
vLLM. Deux versions de ce juge partagé ont été mesurées le 22 octobre 2026 et
abandonnées : elles refusaient des réponses justes longues, et la seconde a
laissé passer une faute que le juge en service détectait.

À lancer DANS le conteneur rag-api, hors de l'heure pleine (synchronisation) :

  docker exec -w /app rag-api python3 /rag-pipeline/s10/mesure_juge.py \\
      /rag-pipeline/s10/jeu_questions_s10.json --compte <compte> --etiquette reference

Options :
  --compte X        compte au nom duquel les questions sont posées (défaut :
                    compte_par_defaut du jeu)
  --passages N      nombre de passages du juge (défaut : 3)
  --modele-juge X   modèle du juge dans ce processus (défaut : JUDGE_MODEL de
                    la stack) ; la configuration de la stack n'est pas modifiée
  --questions A,B   identifiants des questions à poser (défaut : toutes celles
                    qui attendent une réponse pour ce compte)
  --etiquette X     nom de la configuration (figure dans le rapport)

Rapport JSON complet (réponses, versions fausses, verdicts) dans /var/log/rag.
Code de retour : 0 mesure faite, 3 non concluant.
"""
import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime

sys.path.insert(0, "/app")
import main  # code de la RAG API, dans le conteneur

VARIANTES = ("chiffre", "invente", "attribution")
FAIT_INVENTE = "une pénalité de CHF 12 517 par jour de retard"
RE_CITATION = re.compile(r"\[([^\[\]]+?\.\w{2,4})\]")
RE_NOMBRE = re.compile(r"(?<![\w\[./-])(\d{1,4})(?![\w\]/])")


# ─── Versions fausses ────────────────────────────────────────────────────────

def hors_citations(texte: str) -> list[tuple[int, int]]:
    """Plages du texte qui ne sont pas des citations [fichier.ext]."""
    plages, debut = [], 0
    for m in RE_CITATION.finditer(texte):
        plages.append((debut, m.start()))
        debut = m.end()
    plages.append((debut, len(texte)))
    return plages


def faux_chiffre(reponse: str, contexte: str) -> tuple[str, str] | None:
    """Change le premier nombre de la réponse qui figure aussi dans les sources ;
    la nouvelle valeur est absente des sources. Renvoie (texte faux, valeur)."""
    for debut, fin in hors_citations(reponse):
        for m in RE_NOMBRE.finditer(reponse, debut, fin):
            n = int(m.group(1))
            # Numéro de liste (« 1. », « 2) ») : pas un fait, ne pas le changer
            ligne = reponse[reponse.rfind("\n", 0, m.start()) + 1:m.start()]
            if not ligne.strip(" *-#") and reponse[m.end():m.end() + 1] in (".", ")"):
                continue
            if not re.search(rf"(?<!\d){n}(?!\d)", contexte):
                continue
            for nouveau in ((n + 2) if 1900 <= n <= 2100 else n + 12, n + 7, n + 31, n + 113):
                if not re.search(rf"(?<!\d){nouveau}(?!\d)", contexte):
                    return reponse[:m.start()] + str(nouveau) + reponse[m.end():], str(nouveau)
    return None


def faux_invente(reponse: str, contexte: str) -> str | None:
    """Insère, après la première phrase citée, un fait absent des sources, cité
    avec le premier document de la réponse."""
    citations = RE_CITATION.findall(reponse)
    if not citations or "12 517" in contexte or "12517" in contexte:
        return None
    phrase = f" Le document prévoit également {FAIT_INVENTE} [{citations[0]}]."
    m = re.search(r"\]\s*\.", reponse)
    if m:
        return reponse[:m.end()] + phrase + reponse[m.end():]
    return reponse.rstrip() + phrase


def faux_attribution(reponse: str) -> str | None:
    """Intervertit les deux premiers documents cités, partout dans la réponse."""
    distincts = list(dict.fromkeys(RE_CITATION.findall(reponse)))
    if len(distincts) < 2:
        return None
    a, b = distincts[0], distincts[1]
    jeton = "\x00"
    return (reponse.replace(f"[{a}]", jeton).replace(f"[{b}]", f"[{a}]")
            .replace(jeton, f"[{b}]"))


# ─── Juge ────────────────────────────────────────────────────────────────────

def juger(reponse: str, chunks: list) -> dict:
    debut = time.monotonic()
    r = asyncio.run(main.groundedness_check(reponse, chunks))
    return {"ancree": r.get("ancree") is True,
            "erreur": r.get("juge_error", ""),
            "controle": r.get("controle", ""),
            "incoherent": bool(r.get("verdict_incoherent")),
            "non_sourcees": r.get("affirmations_non_sourcees", []),
            "jetons": r.get("juge_jetons"),
            "duree_s": round(time.monotonic() - debut, 1)}


def verdict(j: dict) -> str:
    if j["erreur"]:
        return "erreur"
    return "acceptee" if j["ancree"] else "refusee"


# ─── Programme ───────────────────────────────────────────────────────────────

def principal() -> int:
    ap = argparse.ArgumentParser(description="Ce que détecte le juge")
    ap.add_argument("jeu")
    ap.add_argument("--compte", default="")
    ap.add_argument("--passages", type=int, default=3)
    ap.add_argument("--modele-juge", default="")
    ap.add_argument("--questions", default="")
    ap.add_argument("--etiquette", default="sans-etiquette")
    a = ap.parse_args()

    with open(a.jeu, encoding="utf-8") as f:
        jeu = json.load(f)
    compte = a.compte or jeu.get("compte_par_defaut", "")
    ids = {x.strip() for x in a.questions.split(",") if x.strip()}
    questions = [q for q in jeu["questions"]
                 if not q.get("refus_attendu") and q.get("compte", compte) == compte
                 and (not ids or q["id"] in ids)]
    if not questions:
        print("NON CONCLUANT : aucune question à poser pour ce compte")
        return 3

    if a.modele_juge:
        main.JUDGE_MODEL = a.modele_juge
    main.charger_bloques()
    main.build_bm25_index()
    motif = main.refus_droits()
    if motif:
        print(f"NON CONCLUANT : questions refusées par la RAG API ({motif}). "
              "Lancer une synchronisation, puis relancer.")
        return 3
    groupes = main.get_user_groups(compte)
    if not groupes:
        print(f"NON CONCLUANT : droits de {compte} introuvables dans l'annuaire")
        return 3

    print(f"Moteur : {main.LLM_API}, rédaction {main.LLM_MODEL}, juge {main.JUDGE_MODEL} "
          f"(fenêtre {main.JUDGE_NUM_CTX}) ; compte {compte} ; {len(questions)} question(s), "
          f"{a.passages} passage(s)\n")
    resultats = []
    for q in questions:
        print(f"=== {q['id']} : {q['question']}")
        chunks = asyncio.run(main.search_qdrant(q["question"], user_groups=groupes, user_email=compte))
        contexte = main.build_context(chunks)
        reponse = main.normaliser_citations(
            main.nettoyer_reponse(asyncio.run(main.generate_answer(q["question"], contexte))), chunks)
        fc = faux_chiffre(reponse, contexte)
        versions = {"reelle": reponse,
                    "chiffre": fc[0] if fc else None,
                    "invente": faux_invente(reponse, contexte),
                    "attribution": faux_attribution(reponse)}
        # Marque de la faute, pour savoir si le juge la LOCALISE (et combien
        # d'affirmations justes il signale en plus) : chiffre et invente seulement.
        marques = {"chiffre": fc[1] if fc else None, "invente": "12 517"}
        res = {"id": q["id"], "question": q["question"], "reponse": reponse,
               "versions": {k: v for k, v in versions.items() if k != "reelle"},
               "marques": marques, "jugements": {}}
        for nom, texte in versions.items():
            if texte is None:
                print(f"  {nom:12} (sans objet pour cette réponse)")
                continue
            js = [juger(texte, chunks) for _ in range(a.passages)]
            res["jugements"][nom] = js
            dur = statistics.median(j["duree_s"] for j in js)
            print(f"  {nom:12} {'/'.join(verdict(j) for j in js)} ({dur} s, {js[0]['jetons']} jetons, "
                  f"contrôle {js[0]['controle']})")
        resultats.append(res)

    # ─── Synthèse ───
    def compte_verdicts(nom: str, cible: str) -> tuple[int, int]:
        n = ok = 0
        for r in resultats:
            for j in r["jugements"].get(nom, []):
                n += 1
                ok += verdict(j) == cible
        return ok, n

    print("\n=== Synthèse")
    synthese = {}
    ok, n = compte_verdicts("reelle", "acceptee")
    print(f"Réponses réelles acceptées : {ok}/{n}")
    synthese["reelles_acceptees"] = [ok, n]
    for nom in VARIANTES:
        ok, n = compte_verdicts(nom, "refusee")
        synthese[f"{nom}_detectees"] = [ok, n]
        print(f"Versions « {nom} » détectées : {ok}/{n}" if n else
              f"Versions « {nom} » : aucune (réponses qui ne s'y prêtent pas)")
    erreurs = sum(verdict(j) == "erreur" for r in resultats for js in r["jugements"].values() for j in js)
    incoherents = sum(j["incoherent"] for r in resultats for js in r["jugements"].values() for j in js)
    print(f"Erreurs du juge : {erreurs} ; verdicts incohérents (« ancrée » avec une liste) : {incoherents}")
    synthese["erreurs"], synthese["incoherents"] = erreurs, incoherents

    trouvees = total = en_trop = 0
    for r in resultats:
        for nom in ("chiffre", "invente"):
            m = r["marques"].get(nom)
            for j in r["jugements"].get(nom, []):
                if not m or verdict(j) != "refusee":
                    continue
                total += 1
                items = [str(x) for x in j["non_sourcees"]]
                trouvees += any(m in x for x in items)
                en_trop += sum(m not in x for x in items)
    synthese["precision"] = {"faute_localisee": trouvees, "sur": total, "mentions_en_trop": en_trop}
    if total:
        print(f"Faute localisée dans la liste du juge : {trouvees}/{total} ; "
              f"{en_trop} autre(s) affirmation(s) signalée(s) en plus ({en_trop / total:.1f} par réponse fausse)")

    instables = [f"{r['id']} {nom}" for r in resultats for nom, js in r["jugements"].items()
                 if len({verdict(j) for j in js}) > 1]
    print(f"Verdicts instables d'un passage à l'autre : {len(instables)}"
          + (f" ({', '.join(instables)})" if instables else ""))
    synthese["instables"] = instables

    manquees = [(r["id"], nom) for r in resultats for nom in VARIANTES
                if r["jugements"].get(nom) and
                statistics.mode(verdict(j) for j in r["jugements"][nom]) == "acceptee"]
    if manquees:
        print("Versions fausses acceptées (verdict majoritaire), à lire dans le rapport : "
              + ", ".join(f"{i} {n}" for i, n in manquees))
    refusees = [r["id"] for r in resultats if r["jugements"].get("reelle") and
                statistics.mode(verdict(j) for j in r["jugements"]["reelle"]) != "acceptee"]
    if refusees:
        print("Réponses réelles refusées (verdict majoritaire), à lire : " + ", ".join(refusees))
    synthese["fausses_acceptees"] = [{"id": i, "version": n} for i, n in manquees]
    synthese["reelles_refusees"] = refusees

    durees = [j["duree_s"] for r in resultats for js in r["jugements"].values() for j in js
              if j["controle"] == "juge"]
    if durees:
        print(f"Juge : durée médiane {statistics.median(durees)} s (indicative)")

    fautes = sum(synthese[f"{n}_detectees"][1] for n in VARIANTES)
    code = 0 if fautes else 3
    rapport = {"etiquette": a.etiquette, "date": datetime.now().isoformat(timespec="seconds"),
               "moteur": main.LLM_API, "redaction": main.LLM_MODEL, "juge": main.JUDGE_MODEL,
               "compte": compte, "passages": a.passages, "synthese": synthese,
               "questions": resultats}
    dossier = os.environ.get("REPORT_DIR", "/var/log/rag")
    chemin = os.path.join(dossier, f"mesure_juge_{a.etiquette}_{datetime.now():%Y%m%d_%H%M%S}.json")
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(rapport, f, ensure_ascii=False, indent=1)
        print(f"Rapport : {chemin}")
    except OSError as e:
        print(f"Rapport non écrit ({e})")
    if code == 3:
        print("NON CONCLUANT : aucune version fausse fabriquée")
    return code


if __name__ == "__main__":
    sys.exit(principal())
