"""
sonde_sharepoint.py : vérifie ce que l'application RAG-SharePoint-Indexer
peut réellement lire avec Sites.Selected, avant d'écrire l'indexeur.

Lecture seule. À exécuter DANS le conteneur rag-api (msal et httpx y sont
installés, /etc/rag-certs y est monté) :

  docker exec -e PYTHONPATH=/app -w /app rag-api python3 /rag-pipeline/sonde_sharepoint.py \
    --client-id <ID-APPLICATION> --thumbprint <EMPREINTE> \
    --site https://<tenant>.sharepoint.com/sites/RH --site https://<tenant>.sharepoint.com/

Pour chaque site :
  1. jetons Graph et SharePoint (certificat)
  2. résolution du site via Graph
  3. bibliothèques et fichiers à la racine
  4. permissions des fichiers Test_RAG_* (à défaut, des 3 premiers fichiers)
  5. contenu d'un fichier : .docx lisible (PK) ou chiffré (conteneur OLE)
  6. groupes SharePoint et leurs membres, via l'API REST de SharePoint

Lancé AVANT l'accord Sites.Selected, chaque site doit être refusé : c'est
la preuve que la permission seule ne donne accès à rien.
"""
import argparse
import os
import sys
from urllib.parse import urlparse

import httpx
import msal

GRAPH = "https://graph.microsoft.com/v1.0"
TIMEOUT = 30


def jeton(tenant, client_id, cle, thumbprint, scope):
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant}",
        client_credential={"private_key": cle, "thumbprint": thumbprint},
    )
    r = app.acquire_token_for_client(scopes=[scope])
    if "access_token" not in r:
        raise RuntimeError(f"{r.get('error')} : {r.get('error_description', '')[:200]}")
    return r["access_token"]


def erreur(r):
    try:
        d = r.json()
        # Format d'erreur de l'API REST de SharePoint
        if "odata.error" in d:
            e = d["odata.error"]
            msg = e.get("message", {})
            msg = msg.get("value", "") if isinstance(msg, dict) else str(msg)
            return f"HTTP {r.status_code} {e.get('code', '')} {msg[:160]}".strip()
        e = d.get("error", {})
        if isinstance(e, dict):
            return f"HTTP {r.status_code} {e.get('code', '')} {str(e.get('message', ''))[:120]}".strip()
        return f"HTTP {r.status_code} {str(e)[:120]}"
    except Exception:
        return f"HTTP {r.status_code}"


def tout(c, url):
    elements = []
    while url:
        r = c.get(url)
        if r.status_code != 200:
            raise RuntimeError(erreur(r))
        d = r.json()
        elements.extend(d.get("value", []))
        url = d.get("@odata.nextLink")
    return elements


def decrire_permission(p):
    if p.get("link"):
        return f"lien {p['link'].get('scope')} ({', '.join(p.get('roles', []))})"
    g = p.get("grantedToV2") or {}
    for cle in ("siteGroup", "group", "user", "siteUser"):
        if g.get(cle):
            o = g[cle]
            return f"{cle} {o.get('displayName')} [{o.get('id')}] ({', '.join(p.get('roles', []))})"
    return f"autre : {list(p.keys())}"


def sonder_site(url, jg, tenant, args, cle):
    u = urlparse(url)
    chemin = u.path.rstrip("/")
    print(f"\n=== {url}")

    with httpx.Client(timeout=TIMEOUT, headers={"Authorization": f"Bearer {jg}"}) as c:
        # 2. Site
        r = c.get(f"{GRAPH}/sites/{u.hostname}:{chemin}" if chemin else f"{GRAPH}/sites/{u.hostname}")
        if r.status_code != 200:
            print(f"  2. Site : REFUSÉ, {erreur(r)}")
            return
        site = r.json()
        print(f"  2. Site : OK ({site.get('displayName')})")

        # 3. Bibliothèques et fichiers
        try:
            drives = tout(c, f"{GRAPH}/sites/{site['id']}/drives")
        except RuntimeError as e:
            print(f"  3. Bibliothèques : ÉCHEC, {e}")
            return
        print(f"  3. Bibliothèques : {', '.join(d['name'] for d in drives)}")
        fichiers = []
        for d in drives:
            try:
                enfants = tout(c, f"{GRAPH}/drives/{d['id']}/root/children")
            except RuntimeError as e:
                print(f"     {d['name']} : ÉCHEC, {e}")
                continue
            f = [e for e in enfants if "file" in e]
            print(f"     {d['name']} : {len(enfants)} élément(s) à la racine, dont {len(f)} fichier(s)")
            fichiers.extend((d, e) for e in f)

        # 4. Permissions
        cibles = [(d, e) for d, e in fichiers if e["name"].startswith("Test_RAG")] or fichiers[:3]
        for d, e in cibles:
            try:
                perms = tout(c, f"{GRAPH}/drives/{d['id']}/items/{e['id']}/permissions")
                print(f"  4. Permissions de {e['name']} :")
                for p in perms:
                    print(f"       - {decrire_permission(p)}")
            except RuntimeError as err:
                print(f"  4. Permissions de {e['name']} : ÉCHEC, {err}")

        # 5. Contenu : lisible ou chiffré
        bureautique = (".docx", ".xlsx", ".pptx", ".pdf")
        essais = cibles[:1] + [(d, e) for d, e in fichiers
                               if not e["name"].startswith("Test_RAG")
                               and e["name"].lower().endswith(bureautique)
                               and d["name"] != "Preservation Hold Library"][:2]
        for d, e in essais:
            r = c.get(f"{GRAPH}/drives/{d['id']}/items/{e['id']}/content", follow_redirects=True)
            if r.status_code != 200:
                print(f"  5. Contenu de {e['name']} : ÉCHEC, {erreur(r)}")
                continue
            debut = r.content[:8]
            if debut.startswith(b"PK"):
                etat = "lisible (format Office ouvert)"
            elif debut.startswith(b"\xd0\xcf\x11\xe0"):
                etat = "conteneur OLE : chiffré par une étiquette, ou ancien format Office"
            elif debut.startswith(b"%PDF"):
                etat = "PDF"
            else:
                etat = f"autre format ({debut[:4]!r})"
            print(f"  5. Contenu de {e['name']} : {len(r.content)} octets, {etat}")

    # 6. Groupes SharePoint via l'API REST
    try:
        js = jeton(tenant, args.client_id, cle, args.thumbprint, f"https://{u.hostname}/.default")
    except RuntimeError as e:
        print(f"  6. Jeton SharePoint : ÉCHEC, {e}")
        return
    base = f"https://{u.hostname}{chemin}"
    with httpx.Client(timeout=TIMEOUT, headers={"Authorization": f"Bearer {js}",
                                                "Accept": "application/json;odata=nometadata"}) as c:
        # Liste des groupes, sans les membres
        r = c.get(f"{base}/_api/web/sitegroups",
                  params={"$select": "Id,Title,OnlyAllowMembersViewMembership"})
        if r.status_code != 200:
            print(f"  6. Groupes SharePoint : ÉCHEC, {erreur(r)}")
            return
        print("  6. Groupes SharePoint :")
        for g in r.json().get("value", []):
            restreint = " [membres visibles par les membres seulement]" if g.get("OnlyAllowMembersViewMembership") else ""
            # Membres de chaque groupe, séparément : un groupe restreint ne bloque pas les autres
            rm = c.get(f"{base}/_api/web/sitegroups/GetById({g['Id']})/users",
                       params={"$select": "LoginName,Title,PrincipalType"})
            if rm.status_code != 200:
                print(f"       {g['Title']} [{g['Id']}]{restreint} : membres ILLISIBLES, {erreur(rm)}")
                continue
            membres = rm.json().get("value", [])
            print(f"       {g['Title']} [{g['Id']}]{restreint} : {len(membres)} membre(s)")
            for m in membres:
                print(f"         - {m.get('LoginName')}  ({m.get('Title')}, type {m.get('PrincipalType')})")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--thumbprint", required=True)
    ap.add_argument("--key", default="/etc/rag-certs/rag-sharepoint.key")
    ap.add_argument("--tenant", default=os.getenv("ENTRA_TENANT_ID", ""))
    ap.add_argument("--site", action="append", required=True)
    args = ap.parse_args()
    if not args.tenant:
        sys.exit("ENTRA_TENANT_ID absent : passer --tenant")

    with open(args.key, "r", encoding="utf-8") as f:
        cle = f.read()

    print("1. Jeton Graph")
    try:
        jg = jeton(args.tenant, args.client_id, cle, args.thumbprint, "https://graph.microsoft.com/.default")
    except RuntimeError as e:
        sys.exit(f"   ÉCHEC : {e}")
    print("   OK")

    for url in args.site:
        sonder_site(url, jg, args.tenant, args, cle)


if __name__ == "__main__":
    main()
