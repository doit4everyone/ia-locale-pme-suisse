"""
auth.py : résolution de l'identité utilisateur Open WebUI vers les groupes AD.

Flux :
  1. main.py reçoit l'identité signée par Open WebUI
  2. get_user_groups(email) fait un bind LDAP avec svc-rag
  3. Retourne les SID de l'utilisateur : le SID du compte, puis ceux de tous ses
     groupes de sécurité, lus dans l'attribut tokenGroups (2.22.0)
  4. main.py filtre Qdrant : autorisés[] ∩ SID_utilisateur != ∅

Depuis la 2.22.0, la comparaison se fait sur des SID, plus sur des noms :
tokenGroups donne en une lecture les groupes directs, les groupes imbriqués
et le groupe principal (« Utilisateurs du domaine »), que memberOf omettait.
Si tokenGroups ne peut pas être lu, aucun groupe n'est retourné (accès refusé) :
pas de retour à une résolution partielle.

Groupes intégrés (BUILTIN, S-1-5-32-...) : tokenGroups renvoie ceux de
l'annuaire, qui ne valent que sur les contrôleurs de domaine. Sur un serveur de
fichiers, le même SID désigne un groupe LOCAL, aux membres différents. Ils sont
donc retirés par défaut. ACL_SID_ETENDUS=1 les garde, et ajoute « Tout le monde »
(S-1-1-0) et « Utilisateurs authentifiés » (S-1-5-11) à tout compte trouvé :
plus fidèle à Windows dans le cas courant, mais à décider en connaissance de cause.

Le cloisonnement repose sur autorisés[] (données constatées depuis les ACL NTFS)
et non sur org_name (données déduites). Cette distinction est documentée dans
la section §5 du guide de déploiement.

Variables d'environnement :
  LDAP_HOST      : hôte du contrôleur de domaine (ex: <NOM-DC>.votre-domaine.ch)
  LDAP_PORT      : port LDAP (636 pour LDAPS, 389 pour LDAP)
  LDAP_USE_TLS   : true pour LDAPS, false pour LDAP (défaut: true)
  LDAP_BASE_DN   : base de recherche (ex: DC=votre-domaine,DC=ch)
  LDAP_BIND_DN   : DN du compte de service (ex: CN=svc-rag,OU=...)
  LDAP_BIND_PWD  : mot de passe du compte de service
  LDAP_DOMAIN    : nom court du domaine, pour les journaux (ex: VOTRE-DOMAINE)
  ACL_SID_ETENDUS : 1 pour garder les groupes BUILTIN et ajouter S-1-1-0 et
                   S-1-5-11 (défaut : 0)

Validé sur VM-RAG-LAB, septembre 2026

Extension Entra ID (Partie 3, désactivée par défaut) :
  Si ENTRA_ENABLED=true, get_user_groups() ajoute aux groupes AD les
  identifiants Entra de l'utilisateur, obtenus via Microsoft Graph :
    entra:usr:<object-id>   le compte lui-même
    entra:grp:<object-id>   chaque groupe, imbrications comprises
                            (transitiveMemberOf)
    entra:tous-internes     si le compte est membre du locataire (pas invité)
  Ces identifiants correspondent au format autorisés[] des chunks SharePoint.
  Les chunks SMB utilisent des SID (2.22.0) : ils ne sont pas affectés par
  l'extension.

  Authentification de l'application par certificat (pas de secret client).
  Permissions Graph (application) : User.Read.All, GroupMember.Read.All.

  Si Graph échoue, les groupes AD sont conservés : l'utilisateur garde
  l'accès aux documents SMB et n'a simplement aucun accès SharePoint.
  Ce résultat partiel n'est pas mis en cache, la requête suivante réessaie.

Variables d'environnement de l'extension :
  ENTRA_ENABLED          : true pour activer (défaut : false)
  ENTRA_TENANT_ID        : ID de l'annuaire (locataire)
  ENTRA_CLIENT_ID        : ID d'application (client)
  ENTRA_CERT_PATH        : certificat public PEM
  ENTRA_KEY_PATH         : clé privée PEM
  ENTRA_CERT_THUMBPRINT  : empreinte SHA-1 affichée dans Entra
"""

import os


def _env_nombre(nom: str, defaut, conv=int):
    """Lit une variable numérique ; absente OU vide = valeur par défaut. Une
    variable transmise vide par le Compose ne doit pas empêcher le démarrage."""
    valeur = os.getenv(nom, "").strip()
    return conv(valeur) if valeur else conv(defaut)
import logging
import ssl
import urllib.parse

import httpx
from ldap3 import Server, Connection, ALL, SUBTREE, Tls, BASE
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Configuration LDAP
# ─────────────────────────────────────────

LDAP_HOST    = os.getenv("LDAP_HOST",    "<NOM-DC>.votre-domaine.ch")
LDAP_PORT    = _env_nombre("LDAP_PORT", "636")
LDAP_USE_TLS = os.getenv("LDAP_USE_TLS", "true").lower() == "true"
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "DC=votre-domaine,DC=ch")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN",
    "CN=svc-rag,OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch")
LDAP_BIND_PWD = os.getenv("LDAP_BIND_PWD", "")
LDAP_DOMAIN  = os.getenv("LDAP_DOMAIN",  "VOTRE-DOMAINE")
ACL_SID_ETENDUS = os.getenv("ACL_SID_ETENDUS", "0").strip() == "1"
SID_TOUT_LE_MONDE = "S-1-1-0"
SID_UTILISATEURS_AUTHENTIFIES = "S-1-5-11"
PREFIXE_BUILTIN = "S-1-5-32-"
PREFIXE_DOMAINE = "S-1-5-21-"
# Identités de service, jamais présentes dans le jeton d'un utilisateur :
# Système, Service local, Service réseau, services (NT SERVICE\...).
SID_SERVICES = {"S-1-5-18", "S-1-5-19", "S-1-5-20"}
PREFIXES_SERVICES = ("S-1-5-80-",)


def refus_applicable(sid: str, sids_utilisateur: set[str], domaines: set[str]) -> bool:
    """Un refus (entrée de type refus d'une ACL SMB) s'applique-t-il à l'utilisateur ? (2.22.1)

    Windows applique un refus à toute identité du jeton d'accès. Le jeton d'un
    accès SMB contient aussi « Tout le monde », « Utilisateurs authentifiés »,
    « Réseau », et des groupes locaux du serveur de fichiers que tokenGroups ne
    donne pas. Règle, du côté prudent :
      - SID retenu pour l'utilisateur : refus appliqué ;
      - SID d'un domaine de l'utilisateur, absent de ses SID : non appliqué
        (autre compte, groupe dont il n'est pas membre) ;
      - SID d'un autre domaine ou d'une machine (S-1-5-21-... de préfixe inconnu,
        par exemple un groupe local du serveur de fichiers) : appliqué ;
      - identité de service (Système, services) : non appliqué ;
      - toute autre identité (S-1-1-0, S-1-5-11, groupes intégrés S-1-5-32-...,
        identités bien connues) : appliqué, l'appartenance n'étant pas lisible.
    Les autorisations ne suivent pas cette règle : « Tout le monde » et les
    groupes intégrés n'accordent l'accès qu'avec ACL_SID_ETENDUS."""
    if sid in sids_utilisateur:
        return True
    if sid.startswith(PREFIXE_DOMAINE):
        return sid.rsplit("-", 1)[0] not in domaines
    return sid not in SID_SERVICES and not sid.startswith(PREFIXES_SERVICES)


def sid_texte(b: bytes) -> str:
    """SID binaire (format de l'annuaire) vers sa forme texte S-1-5-21-..."""
    if not isinstance(b, (bytes, bytearray)) or len(b) < 8 or b[0] != 1 or len(b) != 8 + 4 * b[1]:
        raise ValueError("SID binaire mal formé")
    autorite = int.from_bytes(b[2:8], "big")
    sous = [int.from_bytes(b[8 + 4 * i:12 + 4 * i], "little") for i in range(b[1])]
    return f"S-{b[0]}-{autorite}" + "".join(f"-{x}" for x in sous)


def sids_retenus(sid_compte: str, sids_groupes: list[str], etendus: bool = False) -> list[str]:
    """SID utilisés pour l'accès : le compte, puis ses groupes ; groupes BUILTIN
    retirés sauf avec ACL_SID_ETENDUS ; S-1-1-0 et S-1-5-11 ajoutés seulement
    avec ACL_SID_ETENDUS. Ordre stable, sans doublon."""
    retenus = [sid_compte] + [s for s in sids_groupes if etendus or not s.startswith(PREFIXE_BUILTIN)]
    if etendus:
        retenus += [SID_TOUT_LE_MONDE, SID_UTILISATEURS_AUTHENTIFIES]
    return list(dict.fromkeys(retenus))


def lire_sids_utilisateur(conn, dn: str) -> list[str]:
    """SID de tous les groupes de sécurité du compte (attribut calculé tokenGroups,
    lisible seulement en portée BASE). Lève une exception si la lecture échoue ou
    ne renvoie rien : tout compte a au moins son groupe principal."""
    if not conn.search(dn, "(objectClass=*)", BASE, attributes=["tokenGroups"]) or not conn.entries:
        raise RuntimeError(f"lecture de tokenGroups refusée ou impossible ({conn.result.get('description')})")
    brut = conn.entries[0].entry_raw_attributes.get("tokenGroups") or []
    if not brut:
        raise RuntimeError("tokenGroups vide : droit de lecture du compte de service à vérifier")
    return [sid_texte(b) for b in brut]


def noms_des_sids(conn, sids: list[str]) -> dict[str, str]:
    """Pour les journaux seulement : SID → nom pré-Windows 2000. Jamais pour décider."""
    noms = {}
    try:
        cherches = [s for s in sids if s.startswith("S-1-5-21-")]
        if cherches:
            filtre = "(|" + "".join(f"(objectSid={s})" for s in cherches) + ")"
            conn.search(LDAP_BASE_DN, filtre, SUBTREE, attributes=["objectSid", "sAMAccountName"])
            for e in conn.entries:
                try:
                    noms[sid_texte(e.entry_raw_attributes["objectSid"][0])] = str(e.sAMAccountName)
                except Exception:
                    continue
    except Exception:
        pass
    return noms

# ─────────────────────────────────────────
# Configuration Entra ID (extension Partie 3)
# ─────────────────────────────────────────

ENTRA_ENABLED         = os.getenv("ENTRA_ENABLED", "false").lower() == "true"
ENTRA_TENANT_ID       = os.getenv("ENTRA_TENANT_ID", "")
ENTRA_CLIENT_ID       = os.getenv("ENTRA_CLIENT_ID", "")
ENTRA_CERT_PATH       = os.getenv("ENTRA_CERT_PATH", "/etc/rag-certs/rag-identity.crt")
ENTRA_KEY_PATH        = os.getenv("ENTRA_KEY_PATH", "/etc/rag-certs/rag-identity.key")
ENTRA_CERT_THUMBPRINT = os.getenv("ENTRA_CERT_THUMBPRINT", "")
GRAPH_URL             = "https://graph.microsoft.com/v1.0"
GRAPH_TIMEOUT         = 10  # secondes

# TTL du cache des groupes en secondes (évite un appel LDAP par requête)
# Un utilisateur dont les groupes changent devra attendre ce délai
GROUPS_CACHE_TTL = _env_nombre("GROUPS_CACHE_TTL", "300")  # 5 minutes

# ─────────────────────────────────────────
# Cache simple avec expiration
# ─────────────────────────────────────────

_groups_cache: dict[str, tuple[list[str], datetime]] = {}
# Note : ce cache grandit avec le nombre d'utilisateurs distincts sans purge
# des entrées expirées autrement qu'à la lecture. Acceptable à l'échelle PME
# (quelques dizaines d'utilisateurs). Pour un service à haute charge, remplacer
# par un TTLCache (cachetools) ou une purge périodique.


def _get_from_cache(email: str) -> list[str] | None:
    """Retourne les groupes depuis le cache si non expirés."""
    if email in _groups_cache:
        groups, cached_at = _groups_cache[email]
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if age < GROUPS_CACHE_TTL:
            return groups
        del _groups_cache[email]
    return None


def _set_cache(email: str, groups: list[str]):
    """Stocke les groupes dans le cache avec horodatage."""
    _groups_cache[email] = (groups, datetime.now(timezone.utc))


# ─────────────────────────────────────────
# Résolution Entra ID via Microsoft Graph
# ─────────────────────────────────────────

_msal_app = None


def _get_graph_token() -> str:
    """
    Jeton d'application Graph, authentification par certificat.
    MSAL met le jeton en cache et ne le renouvelle qu'à expiration.
    """
    global _msal_app
    if _msal_app is None:
        import msal  # importé ici : inutile si l'extension est désactivée
        with open(ENTRA_KEY_PATH, "r", encoding="utf-8") as f:
            private_key = f.read()
        _msal_app = msal.ConfidentialClientApplication(
            client_id=ENTRA_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}",
            client_credential={
                "private_key": private_key,
                "thumbprint": ENTRA_CERT_THUMBPRINT,
            },
        )
    result = _msal_app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(
            f"Jeton Graph refusé : {result.get('error')} : "
            f"{result.get('error_description', '')[:200]}"
        )
    return result["access_token"]


def get_entra_groups(email: str) -> list[str]:
    """
    Retourne les identifiants Entra d'un utilisateur au format autorisés[] :
      entra:usr:<object-id> puis entra:grp:<object-id> pour chaque groupe.

    transitiveMemberOf inclut les groupes imbriqués, comme la récursion
    memberOf faite côté LDAP. Seuls les groupes sont retenus : les rôles
    d'annuaire et unités administratives sont ignorés.

    Lève une exception en cas d'échec : l'appelant décide de la suite.
    """
    token = _get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}
    upn = urllib.parse.quote(email, safe="@")

    with httpx.Client(timeout=GRAPH_TIMEOUT, headers=headers) as client:
        r = client.get(f"{GRAPH_URL}/users/{upn}", params={"$select": "id,userType"})
        if r.status_code == 404:
            logger.warning(f"[AUTH] Utilisateur '{email}' non trouvé dans Entra ID")
            return []
        r.raise_for_status()
        user_id = r.json()["id"]

        ids = [f"entra:usr:{user_id.lower()}"]
        # Membre du locataire (pas invité) : correspond à « tous les utilisateurs
        # internes » de SharePoint (spo-grid-all-users), traduit par sp_indexer.py
        if r.json().get("userType") == "Member":
            ids.append("entra:tous-internes")
        url = f"{GRAPH_URL}/users/{user_id}/transitiveMemberOf"
        params = {"$select": "id", "$top": "999"}
        while url:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            for obj in data.get("value", []):
                if obj.get("@odata.type") == "#microsoft.graph.group":
                    ids.append(f"entra:grp:{obj['id'].lower()}")
            # nextLink contient déjà les paramètres de la page suivante
            url = data.get("@odata.nextLink")
            params = None

    return ids


# ─────────────────────────────────────────
# Résolution LDAP
# ─────────────────────────────────────────

# Comptes dont la dernière résolution Entra a échoué : leurs documents SharePoint
# sont inaccessibles (refus par défaut). La RAG API le signale dans la réponse,
# au lieu de laisser croire que l'information n'existe pas.
_entra_echec: set[str] = set()


def entra_en_echec(email: str) -> bool:
    """Vrai si la dernière résolution Entra de ce compte a échoué."""
    return email.lower() in _entra_echec


def _serveur_ldap():
    """Serveur LDAP ou LDAPS (validation du certificat si LDAP_CA_CERT est fourni)."""
    if LDAP_USE_TLS:
        # Chemin du certificat CA du DC (export depuis Cert:\LocalMachine\Root)
        # Absent en lab (certificat auto-signé) : CERT_NONE acceptable
        # En production : exporter le certificat CA et le pointer ici
        ca_certs = os.getenv("LDAP_CA_CERT", "")
        # Trois cas :
        # 1. Fichier présent et non vide  → CERT_REQUIRED (production)
        # 2. Fichier absent ou vide        → CERT_NONE avec avertissement (lab)
        # 3. LDAP_CA_CERT non défini       → CERT_NONE avec avertissement (lab)
        # Le fichier vide permet le démarrage du conteneur sans bloquer le montage
        # Docker, même quand le certificat AD n'est pas encore exporté.
        cert_valide = (
            ca_certs
            and os.path.exists(ca_certs)
            and os.path.getsize(ca_certs) > 0
        )
        if cert_valide:
            tls_config = Tls(
                ca_certs_file=ca_certs,
                validate=ssl.CERT_REQUIRED,
                version=ssl.PROTOCOL_TLS_CLIENT,
            )
            logger.info(f"[AUTH] TLS avec certificat CA : {ca_certs}")
        else:
            tls_config = Tls(
                validate=ssl.CERT_NONE,
                version=ssl.PROTOCOL_TLS_CLIENT,
            )
            raison = "fichier vide" if (ca_certs and os.path.exists(ca_certs)) else "fichier absent ou variable non définie"
            logger.warning(
                f"[AUTH] TLS sans validation du certificat (CERT_NONE) : {raison}. "
                "Lab uniquement : installer le certificat CA du DC et redémarrer le conteneur."
            )
        return Server(
            LDAP_HOST,
            port=LDAP_PORT,
            use_ssl=True,
            tls=tls_config,
            get_info=ALL
        )
    else:
        return Server(LDAP_HOST, port=LDAP_PORT, get_info=ALL)


_sid_domaine_cache = None


def sid_domaine() -> str:
    """SID du domaine (objectSid du contexte de nommage par défaut), lu une fois.
    Sert au rapport de acl_resolver.py (documents_refus_pour_tous, 2.22.2), jamais
    à une décision d'accès. Chaîne vide si l'annuaire ne répond pas."""
    global _sid_domaine_cache
    if _sid_domaine_cache:
        return _sid_domaine_cache
    try:
        server = _serveur_ldap()
        conn = Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PWD, auto_bind=True)
        nc = ""
        try:
            nc = str(server.info.other.get("defaultNamingContext", [""])[0])
        except Exception:
            pass
        nc = nc or LDAP_BASE_DN
        conn.search(nc, "(objectClass=*)", BASE, attributes=["objectSid"])
        brut = conn.entries[0].entry_raw_attributes.get("objectSid", []) if conn.entries else []
        conn.unbind()
        if brut:
            _sid_domaine_cache = sid_texte(brut[0])
            return _sid_domaine_cache
        logger.warning(f"[AUTH] SID du domaine introuvable sous '{nc}'")
    except Exception as e:
        logger.warning(f"[AUTH] SID du domaine illisible : {e}")
    return ""


def get_user_groups(email: str) -> list[str]:
    """
    Résout les groupes AD d'un utilisateur à partir de son email (userPrincipalName).

    Retourne les SID de l'utilisateur (compte et groupes de sécurité, via
    tokenGroups), compatibles avec le champ autorisés[] écrit par acl_resolver.py,
    puis, si l'extension Entra est active, ses identifiants Entra.

    En cas d'erreur LDAP, retourne une liste vide : l'utilisateur ne verra
    aucun document plutôt que tous les documents. C'est le comportement sécurisé
    par défaut (deny by default).

    Résultats mis en cache GROUPS_CACHE_TTL secondes pour éviter un appel LDAP
    à chaque requête RAG.
    """
    if not email:
        logger.warning("[AUTH] Email vide, aucun groupe retourné")
        return []

    # Vérifier le cache
    cached = _get_from_cache(email)
    if cached is not None:
        logger.debug(f"[AUTH] Groupes depuis cache pour '{email}' : {len(cached)} groupes")
        return cached

    groups = []
    try:
        server = _serveur_ldap()

        # Connexion avec le compte de service
        conn = Connection(
            server,
            user=LDAP_BIND_DN,
            password=LDAP_BIND_PWD,
            auto_bind=True
        )

        # Échapper l'email pour éviter l'injection LDAP
        clean_email = escape_filter_chars(email)

        # Trouver le DN de l'utilisateur depuis son UPN (email)
        conn.search(
            search_base=LDAP_BASE_DN,
            search_filter=f"(&(objectClass=user)(userPrincipalName={clean_email}))",
            search_scope=SUBTREE,
            attributes=["distinguishedName", "sAMAccountName", "objectSid"]
        )

        if not conn.entries:
            logger.warning(f"[AUTH] Utilisateur '{email}' non trouvé dans l'AD")
            conn.unbind()
            return []

        entry = conn.entries[0]
        sam = str(entry.sAMAccountName) if entry.sAMAccountName else ""
        logger.info(f"[AUTH] Utilisateur trouvé : '{sam}' ({email})")

        # SID du compte et de tous ses groupes de sécurité (2.22.0). Échec de
        # lecture : aucun groupe, donc aucun accès, jamais une liste partielle.
        sid_compte = sid_texte(entry.entry_raw_attributes["objectSid"][0])
        try:
            sids_groupes = lire_sids_utilisateur(conn, str(entry.distinguishedName))
        except Exception as eg:
            logger.error(f"[AUTH] SID des groupes de '{email}' illisibles ({eg}) : accès refusé")
            conn.unbind()
            return []
        groups = sids_retenus(sid_compte, sids_groupes, ACL_SID_ETENDUS)
        noms = noms_des_sids(conn, groups)
        retires = 0 if ACL_SID_ETENDUS else len({s for s in sids_groupes if s.startswith(PREFIXE_BUILTIN)})
        logger.info(f"[AUTH] SID retenus pour '{email}' : {len(groups)} (groupes intégrés retirés : {retires}) "
                    f": " + ", ".join(f"{g} ({noms[g]})" if g in noms else g for g in groups))

        conn.unbind()

    except LDAPException as e:
        logger.error(f"[AUTH] Erreur LDAP pour '{email}' : {e}")
        # Deny by default : en cas d'erreur, pas d'accès
        return []
    except Exception as e:
        logger.error(f"[AUTH] Erreur inattendue pour '{email}' : {e}")
        return []

    # Extension Entra ID : ajout des identifiants cloud aux groupes AD
    if ENTRA_ENABLED:
        try:
            entra_ids = get_entra_groups(email)
            groups.extend(entra_ids)
            _entra_echec.discard(email.lower())
            logger.info(f"[AUTH] Entra : {len(entra_ids)} identifiant(s) pour '{email}'")
        except Exception as e:
            # Groupes AD conservés : accès SMB intact, aucun accès SharePoint.
            # Pas de mise en cache : la requête suivante réessaiera Graph.
            logger.error(f"[AUTH] Résolution Entra échouée pour '{email}' : {e}")
            _entra_echec.add(email.lower())
            return groups

    _set_cache(email, groups)
    return groups


def check_access(user_groups: list[str], autorisés: list[str], interdits: list[str]) -> bool:
    """
    Vérifie l'accès selon la logique NTFS :
      accès accordé si :
        (user_groups ∩ autorisés != ∅) AND (user_groups ∩ interdits == ∅)

    Les DENY sont prioritaires sur les ALLOW, comme en NTFS Windows.
    Les groupes sont comparés sans tenir compte de la casse.

    Refus en SID (partages SMB, 2.22.1) : appliqué selon refus_applicable, qui
    couvre les identités du jeton Windows absentes de user_groups (« Tout le
    monde », « Utilisateurs authentifiés », groupes intégrés ou locaux). Refus
    en identifiants Entra (SharePoint) : correspondance exacte, comme avant.
    """
    if not autorisés:
        return False

    user_lower = {g.lower() for g in user_groups}
    autorisés_lower = {g.lower() for g in autorisés}
    interdits_lower = {g.lower() for g in interdits}

    # Vérifier les DENY d'abord
    if user_lower & interdits_lower:
        return False
    sids_utilisateur = {g.upper() for g in user_groups if g.upper().startswith("S-1-")}
    domaines = {s.rsplit("-", 1)[0] for s in sids_utilisateur if s.startswith(PREFIXE_DOMAINE)}
    for refus in interdits:
        r = str(refus).upper()
        if r.startswith("S-1-") and refus_applicable(r, sids_utilisateur, domaines):
            return False

    # Vérifier les ALLOW
    return bool(user_lower & autorisés_lower)
