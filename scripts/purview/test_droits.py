"""Test du point d'accès /droits de mip-service, depuis le conteneur rag-api.
Usage : docker exec -e MIP_TOKEN=... rag-api python3 /rag-pipeline/test_droits.py \
          <etiquette_id> <proprietaire> <utilisateur1> [<utilisateur2> ...]"""
import json, os, sys, urllib.request

url = os.environ.get("MIP_URL", "http://mip-service:8080")
jeton = os.environ["MIP_TOKEN"]
etiquette, proprietaire, utilisateurs = sys.argv[1], sys.argv[2], sys.argv[3:]

print(f"Étiquette {etiquette}, propriétaire {proprietaire}")
for u in utilisateurs:
    corps = json.dumps({"utilisateur": u, "etiquette_id": etiquette, "proprietaire": proprietaire}).encode()
    req = urllib.request.Request(f"{url}/droits", data=corps, method="POST",
                                 headers={"Authorization": f"Bearer {jeton}", "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=60))
        print(f"  {u:40} {'AUTORISÉ' if r['autorise'] else 'refusé  '}  droits : {','.join(r['droits']) or '(aucun)'}")
    except urllib.error.HTTPError as e:
        print(f"  {u:40} ERREUR HTTP {e.code} : {e.read().decode()[:200]}")
