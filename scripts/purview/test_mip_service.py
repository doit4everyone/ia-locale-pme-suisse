"""Test de mip-service depuis le conteneur rag-api (réseau Docker interne).
Usage : docker exec -e MIP_TOKEN=... rag-api python3 /rag-pipeline/test_mip_service.py <fichier>"""
import base64, io, json, os, sys, urllib.request

url = os.environ.get("MIP_URL", "http://mip-service:8080")
jeton = os.environ["MIP_TOKEN"]
chemin = sys.argv[1]

# 1. Sans jeton : refus attendu
req = urllib.request.Request(f"{url}/dechiffrer", data=b"x", method="POST",
                             headers={"X-Nom-Fichier": "a.docx"})
try:
    urllib.request.urlopen(req); print("ÉCHEC : appel sans jeton accepté")
except urllib.error.HTTPError as e:
    print(f"Sans jeton : HTTP {e.code} (attendu : 401)")

# 2. Avec jeton : déchiffrement
with open(chemin, "rb") as f:
    donnees = f.read()
req = urllib.request.Request(f"{url}/dechiffrer", data=donnees, method="POST",
                             headers={"Authorization": f"Bearer {jeton}",
                                      "X-Nom-Fichier": os.path.basename(chemin)})
r = json.load(urllib.request.urlopen(req, timeout=120))
contenu = r.pop("contenu_base64")
print(json.dumps(r, ensure_ascii=False, indent=2))
if contenu:
    brut = base64.b64decode(contenu)
    print(f"Contenu déchiffré : {len(brut)} octets, en-tête {brut[:4]!r} (attendu : b'PK\\x03\\x04', format Office ouvert)")
    try:
        from docx import Document
        texte = "\n".join(p.text for p in Document(io.BytesIO(brut)).paragraphs)
        print(f"Texte : {texte[:200]}")
    except Exception as e:
        print(f"Extraction du texte non testée ici ({e.__class__.__name__})")
