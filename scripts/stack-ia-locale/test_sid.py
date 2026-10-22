"""
test_sid.py : tests unitaires du contrôle d'accès par SID (2.22.0).

Vérifie, sans annuaire ni partage :
  - la lecture des ACL de smbcacls --numeric par acl_resolver.py, sur des
    sorties RÉELLES relevées sur le partage du lab le 22 octobre 2026 ;
  - la conversion des SID binaires de l'annuaire et le choix des SID retenus
    par auth.py (groupes intégrés retirés, ACL_SID_ETENDUS) ;
  - le refus d'accès quand tokenGroups ne peut pas être lu, sans retour à une
    résolution partielle ;
  - la décision d'accès (refus prioritaire, boîte de dépôt).

Lancement, depuis la VM, dans le conteneur de la RAG API :
  docker exec -w /app rag-api python3 /rag-pipeline/test_sid.py

Attendu : « 16 tests OK », code de sortie 0.
"""
import importlib.util
import os
import struct
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/app")


def charger(noms, nom_module):
    for chemin in noms:
        if os.path.exists(chemin):
            spec = importlib.util.spec_from_file_location(nom_module, chemin)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError(f"{nom_module} introuvable")


ar = charger([os.path.join(ICI, "acl_resolver.py"), os.path.join(ICI, "anon_acl_resolver.py")], "acl_resolver")
auth = charger(["/app/auth.py", os.path.join(ICI, "api", "anon_auth.py")], "auth")

RESULTATS = []


def verifier(nom, ok, detail=""):
    RESULTATS.append(bool(ok))
    print(f"{'OK    ' if ok else 'ECHEC '} {nom}")
    if not ok and detail:
        print(f"       {detail}")


D = "S-1-5-21-4025434849-1489337139-750795771"

# Sorties réelles de smbcacls --numeric (lab, 22 octobre 2026)
DEPOT = f"""REVISION:1
CONTROL:0x9404
OWNER:S-1-5-32-544
GROUP:{D}-513
ACL:{D}-3665:0/0x0/0x00100116
ACL:{D}-513:0/0x0/0x00100116
ACL:{D}-22635:0/0x0/0x001200a9
ACL:{D}-512:0/0x0/0x001f01ff
ACL:S-1-5-32-544:0/0x0/0x001f01ff
"""
DENY = f"""REVISION:1
CONTROL:0x8404
OWNER:S-1-5-32-544
GROUP:{D}-513
ACL:{D}-22629:1/0x0/0x00020089
ACL:{D}-22635:0/0x10/0x001200a9
ACL:S-1-5-18:0/0x10/0x001f01ff
ACL:S-1-5-32-544:0/0x10/0x001f01ff
ACL:{D}-500:0/0x10/0x001f01ff
ACL:{D}-512:0/0x10/0x001f01ff
ACL:{D}-22624:0/0x10/0x001f01ff
"""


def tests_resolveur():
    a, i = ar.analyser_acl(DEPOT, "COMPTABILITE/Test_RAG_Depot.docx")
    verifier("ACL réelle, boîte de dépôt : écriture seule (Comptabilité, Utilisateurs du domaine) écartée",
             a == [f"{D}-22635", f"{D}-512"] and i == [], f"autorisés {a}, interdits {i}")

    a, i = ar.analyser_acl(DENY, "CLIENTS/test-deny-explicite.docx")
    verifier("ACL réelle, refus explicite (type 1) conservé, entrées héritées (0x10) lues, Système exclu",
             i == [f"{D}-22629"] and a == [f"{D}-22635", f"{D}-500", f"{D}-512", f"{D}-22624"],
             f"autorisés {a}, interdits {i}")

    a, i = ar.analyser_acl(f"ACL:{D}-1105:0/0x08/0x001200a9\nACL:{D}-1106:0/0x0/0x001200a9\n")
    verifier("entrée « héritable seulement » (0x08) ignorée", a == [f"{D}-1106"], f"autorisés {a}")

    a, i = ar.analyser_acl(f"ACL:{D}-1105:6/0x0/0x001200a9\nACL:{D}-1106:0/0x0/0x001200a9\n")
    verifier("type d'entrée inconnu traité comme un refus", i == [f"{D}-1105"] and a == [f"{D}-1106"],
             f"autorisés {a}, interdits {i}")

    a, i = ar.analyser_acl("ACL:BSCULIER\\test-client:DENIED/0x0/0x00020089\n"
                           f"ACL:{D}-22635:0/0x0/0x001200a9\n")
    verifier("ligne au format des noms : fichier illisible, rien de retenu", a == [] and i == [],
             f"autorisés {a}, interdits {i}")


def sid_binaire(texte):
    parts = texte.split("-")
    sous = [int(x) for x in parts[3:]]
    return bytes([1, len(sous)]) + int(parts[2]).to_bytes(6, "big") + b"".join(struct.pack("<I", x) for x in sous)


class ConnSimulee:
    """Connexion ldap3 simulée pour lire_sids_utilisateur."""

    def __init__(self, reussit=True, sids=()):
        self.reussit, self.sids, self.entries, self.result = reussit, list(sids), [], {"description": "success"}

    def search(self, base, filtre, portee, attributes=None):
        if not self.reussit:
            self.entries, self.result = [], {"description": "insufficientAccessRights"}
            return False
        e = type("E", (), {})()
        e.entry_raw_attributes = {"tokenGroups": [sid_binaire(s) for s in self.sids]}
        self.entries = [e]
        return True


def tests_auth():
    s = f"{D}-513"
    verifier("SID binaire de l'annuaire converti", auth.sid_texte(sid_binaire(s)) == s
             and auth.sid_texte(sid_binaire("S-1-5-11")) == "S-1-5-11")
    try:
        auth.sid_texte(b"\x01\x05\x00")
        mal = False
    except ValueError:
        mal = True
    verifier("SID binaire mal formé refusé", mal)

    groupes = [f"{D}-512", "S-1-5-32-544", "S-1-5-32-545", f"{D}-513"]
    r = auth.sids_retenus(f"{D}-1104", groupes)
    verifier("groupes intégrés (S-1-5-32-...) retirés par défaut ; compte et groupe principal gardés",
             r == [f"{D}-1104", f"{D}-512", f"{D}-513"], f"{r}")
    r = auth.sids_retenus(f"{D}-1104", groupes, etendus=True)
    verifier("ACL_SID_ETENDUS : groupes intégrés gardés, S-1-1-0 et S-1-5-11 ajoutés",
             r == [f"{D}-1104", f"{D}-512", "S-1-5-32-544", "S-1-5-32-545", f"{D}-513", "S-1-1-0", "S-1-5-11"], f"{r}")

    lus = auth.lire_sids_utilisateur(ConnSimulee(sids=[f"{D}-513", f"{D}-3665"]), "CN=x")
    verifier("tokenGroups lu : SID des groupes", lus == [f"{D}-513", f"{D}-3665"], f"{lus}")
    refus = []
    for conn in (ConnSimulee(reussit=False), ConnSimulee(sids=[])):
        try:
            auth.lire_sids_utilisateur(conn, "CN=x")
            refus.append(False)
        except Exception:
            refus.append(True)
    verifier("tokenGroups refusé ou vide : exception (get_user_groups renvoie alors une liste vide)", all(refus),
             f"{refus}")


class ConnComplete:
    """Connexion ldap3 simulée pour get_user_groups de bout en bout."""

    def __init__(self, *a, tokengroups_ok=True, **k):
        self.tokengroups_ok, self.entries, self.result = tokengroups_ok, [], {"description": "success"}

    def search(self, search_base=None, search_filter="", search_scope=None, attributes=None, **k):
        attributes = attributes or []
        e = type("E", (), {})()
        if "tokenGroups" in attributes:
            if not self.tokengroups_ok:
                self.entries, self.result = [], {"description": "insufficientAccessRights"}
                return False
            e.entry_raw_attributes = {"tokenGroups": [sid_binaire(f"{D}-513"), sid_binaire(f"{D}-3665"),
                                                      sid_binaire("S-1-5-32-545")]}
        elif "objectSid" in attributes and "distinguishedName" in attributes:
            e.entry_raw_attributes = {"objectSid": [sid_binaire(f"{D}-22634")]}
            e.distinguishedName, e.sAMAccountName = "CN=test-compta,DC=x", "test-compta"
        else:
            self.entries = []
            return True
        self.entries = [e]
        return True

    def unbind(self):
        pass


def tests_get_user_groups():
    sauve = (auth.Server, auth.Connection, auth.ENTRA_ENABLED)
    auth.Server = lambda *a, **k: None
    auth.ENTRA_ENABLED = False
    try:
        auth.Connection = lambda *a, **k: ConnComplete()
        g = auth.get_user_groups("sid-ok@test.ch")
        verifier("get_user_groups : SID du compte, groupe principal et groupes, groupe intégré retiré",
                 g == [f"{D}-22634", f"{D}-513", f"{D}-3665"], f"{g}")
        auth.Connection = lambda *a, **k: ConnComplete(tokengroups_ok=False)
        g = auth.get_user_groups("sid-refus@test.ch")
        verifier("get_user_groups : tokenGroups refusé, aucun groupe (accès refusé), pas de résolution partielle",
                 g == [], f"{g}")
    finally:
        auth.Server, auth.Connection, auth.ENTRA_ENABLED = sauve


def tests_acces():
    _, refus = ar.analyser_acl(DENY)
    autorises, _ = ar.analyser_acl(DENY)
    client = [f"{D}-22629", f"{D}-22624", f"{D}-513"]          # test-client, membre de GRP-Clients
    verifier("refus explicite prioritaire sur un groupe autorisé", auth.check_access(client, autorises, refus) is False)
    indexation = [f"{D}-30000", f"{D}-22635", f"{D}-513"]
    verifier("membre d'un groupe autorisé en lecture : accès", auth.check_access(indexation, autorises, refus) is True)
    a_depot, i_depot = ar.analyser_acl(DEPOT)
    compta = [f"{D}-22634", f"{D}-3665", f"{D}-513"]             # test-compta : Comptabilité, Utilisateurs du domaine
    verifier("boîte de dépôt : Comptabilité et Utilisateurs du domaine en écriture seule, pas d'accès",
             auth.check_access(compta, a_depot, i_depot) is False)


if __name__ == "__main__":
    tests_resolveur()
    tests_auth()
    tests_get_user_groups()
    tests_acces()
    total, ok = len(RESULTATS), sum(RESULTATS)
    print(f"{ok} tests OK" if ok == total else f"{total - ok} test(s) en échec sur {total}")
    sys.exit(0 if ok == total else 1)
