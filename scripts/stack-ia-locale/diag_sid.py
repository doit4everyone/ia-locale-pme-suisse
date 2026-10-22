"""
diag_sid.py : contrôle des SID d'un compte (2.22.0, §16.5.3). Ne modifie rien.

Pour un compte, affiche ce que donne l'attribut tokenGroups de l'annuaire (SID de
tous les groupes de sécurité, imbriqués et groupe principal compris), avec leur
nom, et indique lesquels la RAG API retient pour décider de l'accès. Sert à
vérifier que le compte de service lit tokenGroups, et à dépanner un document
invisible ou visible de façon inattendue.

Lancement, dans le conteneur de la RAG API :
  docker exec -w /app rag-api python3 /rag-pipeline/diag_sid.py <compte@domaine>
"""
import os
import ssl
import sys

sys.path.insert(0, "/app")
import auth  # module d'authentification de la RAG API
from ldap3 import Server, Connection, Tls, SUBTREE, BASE, ALL
from ldap3.utils.conv import escape_filter_chars


def sid_texte(b: bytes) -> str:
    """SID binaire (format AD) vers S-1-5-21-..."""
    rev, nb = b[0], b[1]
    autorite = int.from_bytes(b[2:8], "big")
    sous = [int.from_bytes(b[8 + 4 * i:12 + 4 * i], "little") for i in range(nb)]
    return f"S-{rev}-{autorite}" + "".join(f"-{s}" for s in sous)


def connexion() -> Connection:
    if auth.LDAP_USE_TLS:
        ca = os.getenv("LDAP_CA_CERT", "")
        if ca and os.path.exists(ca) and os.path.getsize(ca) > 0:
            tls = Tls(ca_certs_file=ca, validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLS_CLIENT)
        else:
            tls = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLS_CLIENT)
        serveur = Server(auth.LDAP_HOST, port=auth.LDAP_PORT, use_ssl=True, tls=tls, get_info=ALL)
    else:
        serveur = Server(auth.LDAP_HOST, port=auth.LDAP_PORT, get_info=ALL)
    return Connection(serveur, user=auth.LDAP_BIND_DN, password=auth.LDAP_BIND_PWD, auto_bind=True)


def principal() -> int:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        print("Usage : diag_sid.py <compte@domaine>")
        return 1
    compte = sys.argv[1]
    c = connexion()
    c.search(auth.LDAP_BASE_DN, f"(&(objectClass=user)(userPrincipalName={escape_filter_chars(compte)}))",
             SUBTREE, attributes=["distinguishedName", "sAMAccountName", "objectSid", "primaryGroupID"])
    if not c.entries:
        print(f"Compte {compte} introuvable")
        return 1
    e = c.entries[0]
    dn = str(e.distinguishedName)
    sid_compte = sid_texte(e.entry_raw_attributes["objectSid"][0])
    pgid = str(e.primaryGroupID) if e.primaryGroupID else "?"
    print(f"Compte : {e.sAMAccountName} ; SID {sid_compte} ; groupe principal (RID) {pgid}")

    # tokenGroups : attribut calculé, lisible seulement en recherche de portée BASE
    ok = c.search(dn, "(objectClass=*)", BASE, attributes=["tokenGroups"])
    brut = c.entries[0].entry_raw_attributes.get("tokenGroups", []) if (ok and c.entries) else []
    print(f"Lecture de tokenGroups : {'OK' if brut else 'ÉCHEC ou vide'} "
          f"(résultat LDAP : {c.result.get('description')}, {len(brut)} SID)")
    if not brut:
        print("→ le compte de service ne peut peut-être pas lire tokenGroups (voir « Groupe d'accès "
              "d'autorisation Windows ») ; rien d'autre à comparer.")
        return 2

    domaine = sid_compte.rsplit("-", 1)[0]
    sid_principal = f"{domaine}-{pgid}" if pgid != "?" else ""
    lignes = []
    for b in brut:
        s = sid_texte(b)
        c.search(auth.LDAP_BASE_DN, f"(objectSid={s})", SUBTREE, attributes=["sAMAccountName", "cn"])
        sam = str(c.entries[0].sAMAccountName) if c.entries else "?"
        cn = str(c.entries[0].cn) if c.entries else "?"
        lignes.append((s, sam, cn))

    if not hasattr(auth, "sids_retenus"):
        # RAG API antérieure à la 2.22.0 : seule la lecture de tokenGroups est contrôlée
        print(f"\n{len(lignes)} groupes via tokenGroups. RAG API antérieure à la 2.22.0 : "
              "le compte de service lit tokenGroups, la mise à jour peut continuer.")
        for s, sam, cn in sorted(lignes, key=lambda x: x[1].lower()):
            print(f"{s:48} {sam}{' (groupe principal)' if s == sid_principal else ''}")
        return 0

    retenus = set(auth.get_user_groups(compte))
    print(f"\nGroupes via tokenGroups : {len(lignes)} ; SID retenus par la RAG API : {len(retenus)} "
          f"(compte compris ; ACL_SID_ETENDUS={'1' if auth.ACL_SID_ETENDUS else '0'})\n")
    print(f"{'SID':48} {'nom pré-2000 (sAM)':32} retenu")
    for s, sam, cn in sorted(lignes, key=lambda x: x[1].lower()):
        note = " (groupe principal)" if s == sid_principal else ""
        integre = " (groupe intégré)" if s.startswith(auth.PREFIXE_BUILTIN) else ""
        print(f"{s:48} {sam:32} {'oui' if s in retenus else 'NON'}{note}{integre}")
    print("\nNON : groupe ignoré pour l'accès (groupes intégrés BUILTIN, sauf ACL_SID_ETENDUS=1, §16.5.3).")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
