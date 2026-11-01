import glob, json, os, re, sys, unicodedata
from docx import Document
R = sys.argv[1]
def texte(f):
    d = Document(f); t = [p.text for p in d.paragraphs]
    for tb in d.tables:
        for row in tb.rows: t += [c.text for c in row.cells]
    return "\n".join(t)
def norm(s):
    s = unicodedata.normalize("NFKD", s.lower()); s = "".join(c for c in s if not unicodedata.combining(c))
    for c in (" ", " ", " ", "'", "’"): s = s.replace(c, "")
    return s
docs = {os.path.relpath(f, R + "/corpus-axonix").replace(os.sep, "/"): texte(f)
        for f in glob.glob(R + "/corpus-axonix/**/*.docx", recursive=True)}
# ajouter les deux non redistribués (contenu connu)
docs["CLIENTS/test-deny-explicite.docx"] = "forfait mensuel de CHF 9 999"
docs["COMPTABILITE/Test_RAG_Depot.docx"] = "Code de dépôt : DEPOT-8462"
pb = 0
interdits_lieux = ["genevez", "delémont", "delemont", "porrentruy", "bassecourt", "jura", " ju)", "(ju", "aiges", "esserts", "saignel", "franches"]
for c, t in docs.items():
    tl = t.lower()
    if "\u2014" in t or "\u2013" in t: print("TIRET", c); pb += 1
    for l in interdits_lieux:
        if l in tl and not (l == "jura" and "jurassien" not in tl and False):
            print("LIEU", l, c); pb += 1
    if "·" in t: print("POINT MÉDIAN", c); pb += 1
jeu = json.load(open(R + "/jeu_questions_s10_lab.json"))
for q in jeu["questions"]:
    if q["id"][0] in "LIR" and q["id"] in ("L4-UTMSTACK-YAML","I1-LISTE-YAML","I2-YAML-DOCUMENTATION","L5-PURVIEW-MVC","R1-CAPITALE","R2-DUPONT"): continue
    cands = [c for c in docs if q["document_attendu"] and q["document_attendu"].lower() in c.lower()]
    if q["document_attendu"] and not cands: print("DOC ABSENT", q["id"], q["document_attendu"]); pb += 1
    pool = [docs[c] for c in cands] if cands else list(docs.values())
    for a in ([] if q["type"] == "multilingue" else q["attendus"]):  # réponse traduite : non vérifiable mot pour mot
        if not any(norm(a) in norm(t) for t in pool): print("ATTENDU INTROUVABLE", q["id"], a); pb += 1
    if q.get("refus_attendu") and q["id"].startswith("R3"):
        if any("vaucher" in norm(t) and "salaire" in norm(t) and re.search(r"vaucher[^\n]{0,80}chf", t.lower()) for t in docs.values()):
            print("R3 : salaire de la DG trouvable ?"); pb += 1
cas = json.load(open(R + "/cas_cloisonnement_lab.json"))
for k in cas["cas"]:
    if k["document"] not in docs and not k["document"].startswith(("DOIT4EVERYONE", "SERVICE INFO/ADMIN/TLS", "SERVICE INFO/test")):
        print("CAS DOC ABSENT", k["id"]); pb += 1
    if k["secret"]:
        if norm(k["secret"]) not in norm(docs[k["document"]]): print("SECRET ABSENT DU DOC", k["id"]); pb += 1
        if norm(k["secret"]) in norm(k["question"]): print("SECRET DANS LA QUESTION", k["id"]); pb += 1
print(f"{len(docs)} documents contrôlés, {pb} problème(s)")
