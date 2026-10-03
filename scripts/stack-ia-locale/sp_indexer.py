"""
sp_indexer.py : indexation de bibliothèques SharePoint Online vers Qdrant,
avec propagation des permissions SharePoint dans autorises[].

Partie 3 du guide de déploiement (§13). Complète indexer.py (partage SMB),
dont il réutilise l'extraction de texte, le découpage et les embeddings :
un document SharePoint est découpé exactement comme un document SMB.

Accès :
  - RAG-SharePoint-Indexer (Sites.Selected, rôle read accordé site par site) :
    fichiers, permissions des fichiers (Graph), groupes SharePoint (API REST).
  - RAG-Identity-Resolver (§11, module auth.py) : traduction des UPN en
    identifiants, propriétaires des groupes Microsoft 365, existence des groupes.

Traduction des permissions en autorises[] :
  utilisateur                        → entra:usr:<id>
  groupe (sécurité ou Microsoft 365) → entra:grp:<id>, si le groupe existe
  propriétaires d'un groupe M365     → entra:usr:<id> de chaque propriétaire
  tous les utilisateurs internes     → entra:tous-internes (ajouté par auth.py)
  groupe SharePoint                  → traduction de chacun de ses membres
  lien « personnes précises »        → les personnes désignées
  lien « organisation » ou anonyme   → ignoré (refus par défaut)
  invité externe, compte système     → ignoré
  identifiant introuvable            → ignoré et signalé dans le rapport
  rôle d'annuaire (Global Administrator…) → ignoré, signalé comme introuvable
                                       (Graph le présente comme un groupe)
SharePoint n'a pas de refus explicite : interdits[] reste vide.

Fichiers :
  - Formats : ceux d'indexer.py (.docx, .pdf, .pptx, .txt, .md).
  - Chiffré par une étiquette Purview (conteneur OLE à la place du format
    Office ouvert) : non indexé, compté dans le rapport, anciens chunks retirés.
  - Bibliothèques exclues : SP_EXCLUDE_DRIVES (par défaut, la bibliothèque de
    conservation, qui contient d'anciennes versions et des documents supprimés).

Incrémental :
  - cTag inchangé et mêmes paramètres de découpage : le fichier n'est pas
    retéléchargé ; seules ses permissions sont recalculées et mises à jour
    si elles ont changé.
  - Fichier supprimé de SharePoint : ses chunks sont supprimés, uniquement
    pour les sites parcourus sans erreur.
  - Un fichier dont les permissions n'ont pu être lues n'est ni indexé ni
    modifié (ses chunks existants restent en place jusqu'au passage suivant).

Usage (dans le conteneur rag-api) :
  docker exec -e PYTHONPATH=/app -w /app rag-api \\
    python3 /rag-pipeline/sp_indexer.py --dry-run
  docker exec -e PYTHONPATH=/app -w /app rag-api \\
    python3 /rag-pipeline/sp_indexer.py

Variables d'environnement (les options --client-id, --thumbprint et --site
les remplacent) :
  SP_CLIENT_ID          : ID d'application de RAG-SharePoint-Indexer
  SP_CERT_THUMBPRINT    : empreinte SHA-1 du certificat
  SP_KEY_PATH           : clé privée (défaut /etc/rag-certs/rag-sharepoint.key)
  SP_SITES              : URL des sites, séparées par des virgules
  SP_EXCLUDE_DRIVES     : bibliothèques exclues (défaut : Preservation Hold Library)
  SP_MAX_FILE_MB        : taille maximale d'un fichier (défaut 50)
  ENTRA_TENANT_ID       : partagé avec auth.py
  EMBED_BASE_URL, QDRANT_HOST, QDRANT_COLLECTION, CHUNK_* : comme main.py

Codes de sortie :
  0 : terminé sans erreur
  1 : erreur bloquante (configuration, jeton, Qdrant)
  2 : terminé, avec au moins une erreur sur un site ou un fichier
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import base64
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

# indexer.py lit sa configuration à l'import : on lui transmet celle du
# conteneur rag-api (mêmes noms que main.py) avant de l'importer.
if os.getenv("EMBED_BASE_URL") and not os.getenv("OLLAMA_URL"):
    os.environ["OLLAMA_URL"] = os.environ["EMBED_BASE_URL"]
if os.getenv("QDRANT_HOST") and not os.getenv("QDRANT_URL"):
    os.environ["QDRANT_URL"] = os.environ["QDRANT_HOST"]

import httpx
import msal
from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition, Filter, MatchValue, PayloadSchemaType, PointStruct,
)

import indexer as idx      # même dossier (/rag-pipeline)
import auth                # /app (PYTHONPATH) : jeton RAG-Identity-Resolver

GRAPH = "https://graph.microsoft.com/v1.0"
TIMEOUT = 60

TENANT_ID     = os.getenv("ENTRA_TENANT_ID", "")
SP_CLIENT_ID  = os.getenv("SP_CLIENT_ID", "")
SP_THUMBPRINT = os.getenv("SP_CERT_THUMBPRINT", "")
SP_KEY_PATH   = os.getenv("SP_KEY_PATH", "") or "/etc/rag-certs/rag-sharepoint.key"
SP_SITES      = [s.strip() for s in os.getenv("SP_SITES", "").split(",") if s.strip()]
SP_EXCLUDE_DRIVES = [
    d.strip().lower() for d in
    (os.getenv("SP_EXCLUDE_DRIVES", "") or "Preservation Hold Library").split(",")
    if d.strip()
]
SP_MAX_BYTES  = int(os.getenv("SP_MAX_FILE_MB", "") or "50") * 1024 * 1024
REPORT_DIR    = os.getenv("REPORT_DIR", "") or "/var/log/rag"

TOUS_INTERNES = "entra:tous-internes"
FORMATS_OFFICE = (".docx", ".pptx", ".xlsx")
OLE = b"\xd0\xcf\x11\xe0"

# Déchiffrement Purview (§14) : service interne mip-service. Sans MIP_URL et MIP_TOKEN,
# les documents chiffrés restent ignorés, comme avant.
MIP_URL = os.getenv("MIP_URL", "")
MIP_TOKEN = os.getenv("MIP_TOKEN", "")

# Fichiers temporaires d'extraction : en mémoire (/dev/shm) plutôt que sur disque,
# indispensable pour les documents déchiffrés.
DOSSIER_TEMP = "/dev/shm" if os.path.isdir("/dev/shm") else None


def dechiffrer(contenu: bytes, nom: str) -> dict:
    """Envoie un document chiffré à mip-service. Renvoie sa réponse JSON."""
    r = httpx.post(f"{MIP_URL}/dechiffrer", content=contenu, timeout=120,
                   headers={"Authorization": f"Bearer {MIP_TOKEN}", "X-Nom-Fichier": nom})
    if r.status_code != 200:
        raise RuntimeError(f"mip-service HTTP {r.status_code} : {r.text[:200]}")
    return r.json()

# Champs de payload propres à SharePoint, en plus de ceux d'indexer.py
SP_PAYLOAD_INDEXES = {
    "source_type": PayloadSchemaType.KEYWORD,
    "sp_site": PayloadSchemaType.KEYWORD,
}


# ─────────────────────────────────────────
# HTTP : nouvelle tentative sur limitation de débit
# ─────────────────────────────────────────

def requete(client: httpx.Client, methode: str, url: str, **kw) -> httpx.Response:
    """Requête avec jusqu'à 3 nouvelles tentatives sur 429 et 503 (Retry-After respecté)."""
    for essai in range(4):
        r = client.request(methode, url, **kw)
        if r.status_code not in (429, 503) or essai == 3:
            return r
        attente = int(r.headers.get("Retry-After", "5") or "5")
        time.sleep(min(attente, 60))
    return r


def erreur_http(r: httpx.Response) -> str:
    try:
        d = r.json()
        if "odata.error" in d:
            e = d["odata.error"]
            m = e.get("message", {})
            m = m.get("value", "") if isinstance(m, dict) else str(m)
            return f"HTTP {r.status_code} {m[:160]}"
        e = d.get("error", {})
        if isinstance(e, dict):
            return f"HTTP {r.status_code} {e.get('code', '')} {str(e.get('message', ''))[:160]}".strip()
    except Exception:
        pass
    return f"HTTP {r.status_code}"


def tout(client: httpx.Client, url: str, params: dict | None = None) -> list[dict]:
    """Toutes les pages d'une réponse Graph. Lève RuntimeError en cas d'échec."""
    elements = []
    while url:
        r = requete(client, "GET", url, params=params)
        if r.status_code != 200:
            raise RuntimeError(erreur_http(r))
        d = r.json()
        elements.extend(d.get("value", []))
        url, params = d.get("@odata.nextLink"), None
    return elements


# ─────────────────────────────────────────
# Jetons de RAG-SharePoint-Indexer
# ─────────────────────────────────────────

class Jetons:
    def __init__(self, client_id: str, thumbprint: str, cle: str):
        self.app = msal.ConfidentialClientApplication(
            client_id=client_id,
            authority=f"https://login.microsoftonline.com/{TENANT_ID}",
            client_credential={"private_key": cle, "thumbprint": thumbprint},
        )

    def obtenir(self, scope: str) -> str:
        r = self.app.acquire_token_for_client(scopes=[scope])
        if "access_token" not in r:
            raise RuntimeError(f"Jeton refusé ({scope}) : {r.get('error')} : "
                               f"{r.get('error_description', '')[:200]}")
        return r["access_token"]


# ─────────────────────────────────────────
# Résolution des identités (RAG-Identity-Resolver, via auth.py)
# ─────────────────────────────────────────

class Annuaire:
    """Traduit UPN, groupes et propriétaires en identifiants entra:*, avec cache."""

    def __init__(self):
        self.client = httpx.Client(timeout=TIMEOUT)
        self._upn: dict[str, str | None] = {}
        self._groupe: dict[str, bool] = {}
        self._proprio: dict[str, list[str]] = {}
        self.introuvables: dict[str, str] = {}   # identifiant → description

    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        jeton = auth._get_graph_token()
        return requete(self.client, "GET", url, params=params,
                       headers={"Authorization": f"Bearer {jeton}"})

    def utilisateur(self, upn: str) -> str | None:
        cle = upn.lower()
        if cle not in self._upn:
            r = self._get(f"{GRAPH}/users/{quote(upn, safe='@')}", {"$select": "id"})
            if r.status_code == 200:
                self._upn[cle] = r.json()["id"].lower()
            elif r.status_code == 404:
                self._upn[cle] = None
                self.introuvables[upn] = "utilisateur introuvable"
            else:
                raise RuntimeError(f"Résolution de {upn} : {erreur_http(r)}")
        return self._upn[cle]

    def groupe_existe(self, gid: str) -> bool:
        gid = gid.lower()
        if gid not in self._groupe:
            r = self._get(f"{GRAPH}/groups/{gid}", {"$select": "id"})
            if r.status_code == 200:
                self._groupe[gid] = True
            elif r.status_code == 404:
                self._groupe[gid] = False
                self.introuvables[gid] = "groupe introuvable ou rôle d'annuaire, ignoré"
            else:
                raise RuntimeError(f"Groupe {gid} : {erreur_http(r)}")
        return self._groupe[gid]

    def proprietaires(self, gid: str) -> list[str]:
        gid = gid.lower()
        if gid not in self._proprio:
            r = self._get(f"{GRAPH}/groups/{gid}/owners", {"$select": "id"})
            if r.status_code == 404:
                self._proprio[gid] = []
                self.introuvables[gid] = "groupe introuvable (propriétaires)"
            elif r.status_code != 200:
                raise RuntimeError(f"Propriétaires de {gid} : {erreur_http(r)}")
            else:
                ids, d = [], r.json()
                while True:
                    ids += [o["id"].lower() for o in d.get("value", [])
                            if o.get("@odata.type") == "#microsoft.graph.user"]
                    suivant = d.get("@odata.nextLink")
                    if not suivant:
                        break
                    r = self._get(suivant)
                    if r.status_code != 200:
                        raise RuntimeError(f"Propriétaires de {gid} : {erreur_http(r)}")
                    d = r.json()
                self._proprio[gid] = ids
        return self._proprio[gid]


def traduire_claim(login: str, annuaire: Annuaire) -> tuple[list[str], str]:
    """
    Traduit un membre de groupe SharePoint (nom de connexion au format claim)
    en identifiants autorises[]. Retourne (identifiants, note).
    """
    l = login.lower()
    if l == "sharepoint\\system":
        return [], "compte système"
    if l.startswith("i:0#.f|membership|"):
        upn = login.split("|", 2)[2]
        if "#ext#" in upn.lower():
            return [], f"invité externe ignoré : {upn}"
        uid = annuaire.utilisateur(upn)
        return ([f"entra:usr:{uid}"], "") if uid else ([], f"utilisateur introuvable : {upn}")
    if "spo-grid-all-users" in l:
        return [TOUS_INTERNES], ""
    if l.startswith("c:0t.c|tenant|") or l.startswith("c:0o.c|federateddirectoryclaimprovider|"):
        gid = l.split("|")[-1]
        if gid.endswith("_o"):
            gid = gid[:-2]
            return [f"entra:usr:{u}" for u in annuaire.proprietaires(gid)], ""
        if annuaire.groupe_existe(gid):
            return [f"entra:grp:{gid}"], ""
        return [], f"groupe introuvable ou rôle d'annuaire, ignoré : {gid}"
    return [], f"membre non traduit : {login}"


# ─────────────────────────────────────────
# Groupes SharePoint d'un site (API REST)
# ─────────────────────────────────────────

def groupes_du_site(base: str, jeton_sp: str, annuaire: Annuaire, notes: list[str]) -> tuple[dict, set]:
    """
    Retourne ({id du groupe SharePoint: [identifiants] ou None si illisible},
              {id des groupes M365 dont les propriétaires sont membres d'un groupe}).
    """
    groupes, groupes_proprietaires = {}, set()
    entetes = {"Authorization": f"Bearer {jeton_sp}", "Accept": "application/json;odata=nometadata"}
    with httpx.Client(timeout=TIMEOUT, headers=entetes) as c:
        r = requete(c, "GET", f"{base}/_api/web/sitegroups", params={"$select": "Id,Title"})
        if r.status_code != 200:
            raise RuntimeError(f"Groupes SharePoint : {erreur_http(r)}")
        for g in r.json().get("value", []):
            rm = requete(c, "GET", f"{base}/_api/web/sitegroups/GetById({g['Id']})/users",
                         params={"$select": "LoginName"})
            if rm.status_code != 200:
                groupes[g["Id"]] = None
                continue
            ids = []
            for m in rm.json().get("value", []):
                login = m.get("LoginName", "")
                if login.lower().endswith("_o") and "federateddirectoryclaimprovider" in login.lower():
                    groupes_proprietaires.add(login.lower().split("|")[-1][:-2])
                trad, note = traduire_claim(login, annuaire)
                ids += trad
                if note and not note.startswith("compte système"):
                    notes.append(f"{g['Title']} : {note}")
            groupes[g["Id"]] = sorted(set(ids))
    return groupes, groupes_proprietaires


# ─────────────────────────────────────────
# Permissions d'un fichier (Graph)
# ─────────────────────────────────────────

def traduire_identite(ident: dict, roles: list[str], groupes: dict, groupes_prop: set,
                      annuaire: Annuaire, notes: list[str]) -> list[str]:
    if ident.get("siteGroup"):
        sg = ident["siteGroup"]
        try:
            ids = groupes.get(int(sg.get("id")))
        except (TypeError, ValueError):
            ids = None
        if ids is None:
            notes.append(f"groupe SharePoint illisible : {sg.get('displayName')}")
            return []
        return ids
    if ident.get("group"):
        gid = ident["group"].get("id", "").lower()
        # Graph présente les propriétaires d'un groupe M365 comme le groupe
        # lui-même, avec le rôle owner : on les traduit en propriétaires, pour
        # ne pas étendre l'accès à tous les membres du groupe.
        if "owner" in roles and gid in groupes_prop:
            return [f"entra:usr:{u}" for u in annuaire.proprietaires(gid)]
        if gid and annuaire.groupe_existe(gid):
            return [f"entra:grp:{gid}"]
        notes.append(f"groupe introuvable ou rôle d'annuaire, ignoré : {gid}")
        return []
    if ident.get("user"):
        uid = ident["user"].get("id", "")
        if uid:
            return [f"entra:usr:{uid.lower()}"]
        notes.append(f"utilisateur sans identifiant : {ident['user'].get('displayName')}")
        return []
    if ident.get("siteUser"):
        ids, note = traduire_claim(ident["siteUser"].get("loginName", ""), annuaire)
        if note:
            notes.append(note)
        return ids
    return []


def acl_fichier(perms: list[dict], groupes: dict, groupes_prop: set,
                annuaire: Annuaire) -> tuple[list[str], list[str]]:
    autorises, notes = set(), []
    for p in perms:
        roles = p.get("roles", [])
        if p.get("link"):
            portee = p["link"].get("scope", "")
            if portee != "users":
                notes.append(f"lien « {portee} » ignoré (refus par défaut)")
                continue
            for ident in p.get("grantedToIdentitiesV2") or p.get("grantedToIdentities") or []:
                autorises.update(traduire_identite(ident, roles, groupes, groupes_prop, annuaire, notes))
            continue
        ident = p.get("grantedToV2") or p.get("grantedTo") or {}
        autorises.update(traduire_identite(ident, roles, groupes, groupes_prop, annuaire, notes))
    return sorted(autorises), notes


# ─────────────────────────────────────────
# Qdrant
# ─────────────────────────────────────────

def filtre_source(source: str) -> Filter:
    return Filter(must=[FieldCondition(key="source", match=MatchValue(value=source))])


COLLECTION_EXISTE = True   # fixé dans main() ; False seulement en simulation sur une base vide


def etat_existant(qdrant: QdrantClient, source: str) -> dict | None:
    if not COLLECTION_EXISTE:
        return None
    points, _ = qdrant.scroll(
        collection_name=idx.COLLECTION, scroll_filter=filtre_source(source), limit=1,
        with_payload=["sp_ctag", "embed_model", "chunk_size", "chunk_overlap",
                      "min_chunk_words", "chunker_version", "autorises"],
        with_vectors=False,
    )
    return points[0].payload if points else None


def parametres_identiques(e: dict) -> bool:
    return (e.get("embed_model") == idx.EMBED_MODEL
            and e.get("chunk_size") == idx.CHUNK_SIZE
            and e.get("chunk_overlap") == idx.CHUNK_OVERLAP
            and e.get("min_chunk_words") == idx.MIN_CHUNK_WORDS
            and e.get("chunker_version") == idx.CHUNKER_VERSION)


def sources_indexees(qdrant: QdrantClient, site_url: str) -> set[str]:
    sources, offset = set(), None
    filtre = Filter(must=[
        FieldCondition(key="source_type", match=MatchValue(value="sharepoint")),
        FieldCondition(key="sp_site", match=MatchValue(value=site_url)),
    ])
    while True:
        points, offset = qdrant.scroll(
            collection_name=idx.COLLECTION, scroll_filter=filtre, limit=256,
            offset=offset, with_payload=["source"], with_vectors=False,
        )
        sources.update(p.payload["source"] for p in points)
        if offset is None:
            return sources


def creer_index_sp(qdrant: QdrantClient):
    try:
        existants = qdrant.get_collection(idx.COLLECTION).payload_schema or {}
    except Exception:
        existants = {}
    for champ, schema in SP_PAYLOAD_INDEXES.items():
        if champ not in existants:
            qdrant.create_payload_index(collection_name=idx.COLLECTION, field_name=champ,
                                        field_schema=schema, wait=True)


# ─────────────────────────────────────────
# Parcours d'un site
# ─────────────────────────────────────────

def lister_fichiers(c: httpx.Client, drive_id: str) -> list[tuple[str, dict]]:
    """(chemin relatif, élément) de tous les fichiers de la bibliothèque, sous-dossiers compris."""
    resultat, a_parcourir = [], [("", f"{GRAPH}/drives/{drive_id}/root/children")]
    champs = "id,name,file,folder,size,cTag,webUrl,lastModifiedDateTime"
    while a_parcourir:
        chemin, url = a_parcourir.pop()
        for e in tout(c, url, {"$select": champs, "$top": "200"}):
            rel = f"{chemin}/{e['name']}" if chemin else e["name"]
            if "folder" in e:
                a_parcourir.append((rel, f"{GRAPH}/drives/{drive_id}/items/{e['id']}/children"))
            elif "file" in e:
                resultat.append((rel, e))
    return resultat


def libelle_site(url: str) -> str:
    chemin = urlparse(url).path.rstrip("/")
    return chemin.split("/")[-1] if chemin else "racine"


def indexer_site(site_url: str, jetons: Jetons, annuaire: Annuaire, qdrant: QdrantClient,
                 args, rapport: dict) -> bool:
    """Indexe un site. Retourne False si une erreur empêche le nettoyage des orphelins."""
    u = urlparse(site_url)
    chemin = u.path.rstrip("/")
    base = f"https://{u.hostname}{chemin}"
    label = libelle_site(site_url)
    site_rapport = {"site": site_url, "fichiers": [], "notes_groupes": [], "erreurs": []}
    rapport["sites"].append(site_rapport)
    print(f"\n=== Site : {site_url}")

    jg = jetons.obtenir("https://graph.microsoft.com/.default")
    js = jetons.obtenir(f"https://{u.hostname}/.default")
    complet = True

    with httpx.Client(timeout=TIMEOUT, headers={"Authorization": f"Bearer {jg}"},
                      follow_redirects=True) as c:
        r = requete(c, "GET", f"{GRAPH}/sites/{u.hostname}:{chemin}" if chemin else f"{GRAPH}/sites/{u.hostname}")
        if r.status_code != 200:
            site_rapport["erreurs"].append(f"site inaccessible : {erreur_http(r)}")
            print(f"  Site inaccessible : {erreur_http(r)}")
            return False
        site = r.json()

        groupes, groupes_prop = groupes_du_site(base, js, annuaire, site_rapport["notes_groupes"])
        illisibles = [k for k, v in groupes.items() if v is None]
        print(f"  Groupes SharePoint : {len(groupes)} ({len(illisibles)} illisible(s), groupes système)")

        vus = set()
        for d in tout(c, f"{GRAPH}/sites/{site['id']}/drives", {"$select": "id,name"}):
            if d["name"].lower() in SP_EXCLUDE_DRIVES:
                print(f"  Bibliothèque exclue : {d['name']}")
                continue
            try:
                fichiers = lister_fichiers(c, d["id"])
            except RuntimeError as e:
                site_rapport["erreurs"].append(f"{d['name']} : {e}")
                complet = False
                continue
            print(f"  Bibliothèque {d['name']} : {len(fichiers)} fichier(s)")

            for rel, e in fichiers:
                source = f"SharePoint/{label}/{d['name']}/{rel}"
                vus.add(source)
                try:
                    entree = traiter_fichier(c, qdrant, annuaire, groupes, groupes_prop,
                                             site_url, d, rel, e, source, args)
                except Exception as err:
                    # Une erreur sur un fichier n'interrompt pas les autres
                    entree = {"source": source, "statut": "erreur", "erreur": str(err)[:300]}
                site_rapport["fichiers"].append(entree)
                if entree["statut"] == "erreur":
                    complet = False
                print(f"    {entree['statut']:<22} {rel}")

    # Orphelins : fichiers indexés qui n'existent plus dans les bibliothèques parcourues
    if complet and not args.dry_run:
        for source in sources_indexees(qdrant, site_url) - vus:
            qdrant.delete(collection_name=idx.COLLECTION, points_selector=filtre_source(source))
            site_rapport["fichiers"].append({"source": source, "statut": "supprimé (orphelin)"})
            print(f"    supprimé (orphelin)    {source}")
    elif not complet:
        print("  Nettoyage des orphelins non effectué : parcours incomplet")
    return complet


def traiter_fichier(c, qdrant, annuaire, groupes, groupes_prop, site_url, drive, rel, e,
                    source, args) -> dict:
    entree = {"source": source, "web_url": e.get("webUrl")}
    ext = os.path.splitext(e["name"])[1].lower()
    if ext not in idx.SUPPORTED_EXTENSIONS:
        entree["statut"] = "format ignoré"
        return entree
    if e.get("size", 0) > SP_MAX_BYTES:
        entree["statut"] = "trop volumineux"
        return entree

    # Permissions : calculées à chaque passage
    try:
        perms = tout(c, f"{GRAPH}/drives/{drive['id']}/items/{e['id']}/permissions")
        autorises, notes = acl_fichier(perms, groupes, groupes_prop, annuaire)
    except RuntimeError as err:
        entree.update(statut="erreur", erreur=f"permissions : {err}")
        return entree
    entree["autorises"] = autorises
    if notes:
        entree["notes"] = sorted(set(notes))

    existant = etat_existant(qdrant, source)
    maintenant = datetime.now(timezone.utc).isoformat()

    # Contenu inchangé : mise à jour des seules permissions
    if (existant and not args.force and existant.get("sp_ctag") == e.get("cTag")
            and parametres_identiques(existant)):
        if sorted(existant.get("autorises") or []) != autorises:
            entree["statut"] = "permissions mises à jour"
            if not args.dry_run:
                qdrant.set_payload(collection_name=idx.COLLECTION,
                                   payload={"autorises": autorises, "acl_updated_at": maintenant},
                                   points=filtre_source(source))
        else:
            entree["statut"] = "inchangé"
        return entree

    # Téléchargement
    r = requete(c, "GET", f"{GRAPH}/drives/{drive['id']}/items/{e['id']}/content")
    if r.status_code != 200:
        entree.update(statut="erreur", erreur=f"téléchargement : {erreur_http(r)}")
        return entree
    contenu = r.content

    mip = None
    if ext in FORMATS_OFFICE and contenu.startswith(OLE):
        if not (MIP_URL and MIP_TOKEN):
            entree["statut"] = "chiffré, non indexé"
            if existant and not args.dry_run:
                qdrant.delete(collection_name=idx.COLLECTION, points_selector=filtre_source(source))
            return entree
        try:
            rep_mip = dechiffrer(contenu, e["name"])
        except (RuntimeError, httpx.HTTPError) as err:
            # Erreur passagère possible : les chunks existants sont conservés,
            # les droits restant de toute façon vérifiés à chaque question.
            entree.update(statut="erreur", erreur=f"déchiffrement : {err}")
            return entree
        entree["etiquette"] = rep_mip.get("etiquette_nom")
        if rep_mip.get("decision") != "dechiffre":
            entree["statut"] = f"chiffré, non indexé ({rep_mip.get('decision')})"
            if existant and not args.dry_run:
                qdrant.delete(collection_name=idx.COLLECTION, points_selector=filtre_source(source))
            return entree
        contenu = base64.b64decode(rep_mip["contenu_base64"])
        mip = {
            "mip_etiquette_id": rep_mip.get("etiquette_id") or "",
            "mip_etiquette_nom": rep_mip.get("etiquette_nom") or "",
            "mip_proprietaire": (rep_mip.get("proprietaire") or "").lower(),
        }
        if not mip["mip_etiquette_id"]:
            # Sans étiquette, les droits ne peuvent pas être évalués à la question : refus par défaut
            entree["statut"] = "chiffré, non indexé (étiquette inconnue)"
            if existant and not args.dry_run:
                qdrant.delete(collection_name=idx.COLLECTION, points_selector=filtre_source(source))
            return entree

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False, dir=DOSSIER_TEMP) as tmp:
        tmp.write(contenu)
        chemin_tmp = tmp.name
    try:
        blocs = idx.extract_blocks(chemin_tmp)
    finally:
        os.unlink(chemin_tmp)

    if not blocs:
        entree["statut"] = "vide ou illisible"
        if existant and not args.dry_run:
            qdrant.delete(collection_name=idx.COLLECTION, points_selector=filtre_source(source))
        return entree

    chunks = idx.chunk_blocks(blocs)
    entree["chunks"] = len(chunks)
    if not autorises:
        entree.setdefault("notes", []).append("aucun accès traduit : invisible pour tous (refus par défaut)")
    if args.dry_run:
        entree["statut"] = "à indexer (simulation)"
        return entree

    content_hash = hashlib.sha256("".join(blocs).encode()).hexdigest()[:32]
    source_id = hashlib.md5(source.encode()).hexdigest()
    points = []
    for i, texte in enumerate(chunks):
        chunk_id = int(hashlib.md5(f"{source}_{i}".encode()).hexdigest()[:16], 16) % (2**63)
        points.append(PointStruct(id=chunk_id, vector=idx.get_embedding(texte), payload={
            "text": texte,
            "source": source,
            "source_id": source_id,
            "source_type": "sharepoint",
            "content_hash": content_hash,
            "org_name": idx.ORG_OWNER,
            "detection_niveau": 0,
            "detection_methode": "sharepoint",
            "embed_model": idx.EMBED_MODEL,
            "chunk_size": idx.CHUNK_SIZE,
            "chunk_overlap": idx.CHUNK_OVERLAP,
            "min_chunk_words": idx.MIN_CHUNK_WORDS,
            "chunker_version": idx.CHUNKER_VERSION,
            "chunk_index": i,
            "filepath": e.get("webUrl", ""),
            "indexed_at": maintenant,
            "autorises": autorises,
            "interdits": [],
            "acl_updated_at": maintenant,
            "sp_site": site_url,
            "sp_drive": drive["name"],
            "sp_item_id": e["id"],
            "sp_ctag": e.get("cTag"),
            "web_url": e.get("webUrl", ""),
            # Purview (§14) : les droits sur le contenu sont évalués à chaque question
            "chiffre": mip is not None,
            **(mip or {}),
        }))
    qdrant.upsert(collection_name=idx.COLLECTION, points=points)
    idx.supprimer_chunks_excedentaires(qdrant, source, idx.COLLECTION, len(points))
    entree["statut"] = "indexé (déchiffré)" if mip else "indexé"
    return entree


# ─────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────

def main() -> int:
    global TENANT_ID, COLLECTION_EXISTE
    ap = argparse.ArgumentParser(description="Indexation SharePoint Online vers Qdrant")
    ap.add_argument("--client-id", default=SP_CLIENT_ID)
    ap.add_argument("--thumbprint", default=SP_THUMBPRINT)
    ap.add_argument("--key", default=SP_KEY_PATH)
    ap.add_argument("--tenant", default=TENANT_ID)
    ap.add_argument("--site", action="append", help="URL d'un site (répétable), remplace SP_SITES")
    ap.add_argument("--dry-run", action="store_true",
                    help="Simulation : permissions et fichiers analysés, rien n'est écrit")
    ap.add_argument("--force", action="store_true", help="Retélécharge et réindexe tous les fichiers")
    ap.add_argument("--rapport", default="", help="Chemin du rapport JSON")
    args = ap.parse_args()

    TENANT_ID = args.tenant
    sites = args.site or SP_SITES
    manquants = [n for n, v in (("ENTRA_TENANT_ID", TENANT_ID), ("SP_CLIENT_ID", args.client_id),
                                ("SP_CERT_THUMBPRINT", args.thumbprint), ("SP_SITES", sites)) if not v]
    if manquants:
        print("Configuration incomplète : " + ", ".join(manquants))
        return 1

    idx.valider_configuration()
    try:
        with open(args.key, "r", encoding="utf-8") as f:
            jetons = Jetons(args.client_id, args.thumbprint, f.read())
        jetons.obtenir("https://graph.microsoft.com/.default")
    except Exception as e:
        print(f"Jeton RAG-SharePoint-Indexer impossible : {e}")
        return 1

    try:
        qdrant = QdrantClient(url=idx.QDRANT_URL, api_key=idx.QDRANT_API_KEY)
        if not args.dry_run:
            idx.init_collection(qdrant)
            creer_index_sp(qdrant)
        else:
            COLLECTION_EXISTE = idx.COLLECTION in [c.name for c in qdrant.get_collections().collections]
    except SystemExit:
        return 1
    except Exception as e:
        print(f"Qdrant inaccessible : {e}")
        return 1

    annuaire = Annuaire()
    rapport = {"debut": datetime.now(timezone.utc).isoformat(), "simulation": args.dry_run, "sites": []}
    code = 0
    for site_url in sites:
        try:
            if not indexer_site(site_url, jetons, annuaire, qdrant, args, rapport):
                code = 2
        except Exception as e:
            print(f"  ERREUR sur {site_url} : {e}")
            rapport["sites"].append({"site": site_url, "erreurs": [str(e)]})
            code = 2

    rapport["fin"] = datetime.now(timezone.utc).isoformat()
    rapport["identifiants_introuvables"] = annuaire.introuvables
    statuts = {}
    for s in rapport["sites"]:
        for f in s.get("fichiers", []):
            statuts[f["statut"]] = statuts.get(f["statut"], 0) + 1
    rapport["totaux"] = statuts

    chemin = args.rapport or os.path.join(
        REPORT_DIR, f"rapport_sharepoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(rapport, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"Rapport non écrit ({e})")
        chemin = None

    print("\n=== Totaux")
    for statut, n in sorted(statuts.items()):
        print(f"  {statut:<26} {n}")
    if annuaire.introuvables:
        print("  Identifiants introuvables :")
        for k, v in annuaire.introuvables.items():
            print(f"    {k} ({v})")
    if chemin:
        print(f"  Rapport : {chemin}")
    return code


if __name__ == "__main__":
    sys.exit(main())
