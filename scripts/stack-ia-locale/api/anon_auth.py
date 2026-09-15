"""
auth.py : résolution de l'identité utilisateur Open WebUI vers les groupes AD.

Flux :
  1. main.py reçoit le header x-openwebui-user-email depuis Open WebUI
  2. get_user_groups(email) fait un bind LDAP avec svc-rag
  3. Retourne la liste des groupes AD de l'utilisateur au format DOMAINE\\Groupe
  4. main.py filtre Qdrant : autorisés[] ∩ groupes_utilisateur != ∅

Le cloisonnement repose sur autorisés[] (données constatées depuis les ACL NTFS)
et non sur org_name (données déduites). Cette distinction est documentée dans
la section §5 du guide de déploiement.

Variables d'environnement :
  LDAP_HOST      : hôte du contrôleur de domaine (ex: <IP-DC>)
  LDAP_PORT      : port LDAP (636 pour LDAPS, 389 pour LDAP)
  LDAP_USE_TLS   : true pour LDAPS, false pour LDAP (défaut: true)
  LDAP_BASE_DN   : base de recherche (ex: DC=votre-domaine,DC=ch)
  LDAP_BIND_DN   : DN du compte de service (ex: CN=svc-rag,OU=...)
  LDAP_BIND_PWD  : mot de passe du compte de service
  LDAP_DOMAIN    : préfixe du domaine pour les groupes (ex: VOTRE-DOMAINE)

Validé sur VM-RAG-LAB avec AD VOTRE-DOMAINE.CH, septembre 2026
"""

import os
import logging
import ssl
from ldap3 import Server, Connection, ALL, SUBTREE, Tls, BASE
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Configuration LDAP
# ─────────────────────────────────────────

LDAP_HOST    = os.getenv("LDAP_HOST",    "<IP-DC>")
LDAP_PORT    = int(os.getenv("LDAP_PORT", "636"))
LDAP_USE_TLS = os.getenv("LDAP_USE_TLS", "true").lower() == "true"
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "DC=votre-domaine,DC=ch")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN",
    "CN=svc-rag,OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch")
LDAP_BIND_PWD = os.getenv("LDAP_BIND_PWD", "")
LDAP_DOMAIN  = os.getenv("LDAP_DOMAIN",  "VOTRE-DOMAINE")

# TTL du cache des groupes en secondes (évite un appel LDAP par requête)
# Un utilisateur dont les groupes changent devra attendre ce délai
GROUPS_CACHE_TTL = int(os.getenv("GROUPS_CACHE_TTL", "300"))  # 5 minutes

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
# Résolution LDAP
# ─────────────────────────────────────────

def get_user_groups(email: str) -> list[str]:
    """
    Résout les groupes AD d'un utilisateur à partir de son email (userPrincipalName).

    Retourne une liste de groupes au format 'DOMAINE\\NomGroupe',
    compatible avec le champ autorisés[] stocké dans Qdrant par acl_resolver.py.

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
        # Configurer la connexion LDAP/LDAPS
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
                    f"[AUTH] TLS sans validation du certificat (CERT_NONE) — {raison}. "
                    "Lab uniquement : installer le certificat CA du DC et redémarrer le conteneur."
                )
            server = Server(
                LDAP_HOST,
                port=LDAP_PORT,
                use_ssl=True,
                tls=tls_config,
                get_info=ALL
            )
        else:
            server = Server(LDAP_HOST, port=LDAP_PORT, get_info=ALL)

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
            attributes=["distinguishedName", "sAMAccountName", "memberOf"]
        )

        if not conn.entries:
            logger.warning(f"[AUTH] Utilisateur '{email}' non trouvé dans l'AD")
            conn.unbind()
            return []

        entry = conn.entries[0]
        sam = str(entry.sAMAccountName) if entry.sAMAccountName else ""
        logger.info(f"[AUTH] Utilisateur trouvé : '{sam}' ({email})")

        # Résoudre les groupes avec récursivité pour les groupes imbriqués
        # memberOf ne remonte que les appartenances directes.
        # On résout récursivement jusqu'à ce qu'il n'y ait plus de nouveaux groupes.
        member_of_dns = set(str(dn) for dn in (entry.memberOf.values if entry.memberOf else []))
        dns_a_resoudre = set(member_of_dns)
        groupes_resolus_dns = set()

        while dns_a_resoudre:
            dn = dns_a_resoudre.pop()
            if dn in groupes_resolus_dns:
                continue
            groupes_resolus_dns.add(dn)

            # Extraire le nom du groupe depuis le DN
            parts = str(dn).split(",")
            for part in parts:
                if part.strip().upper().startswith("CN="):
                    group_name = part.strip()[3:]
                    groups.append(f"{LDAP_DOMAIN}\\{group_name}")
                    break

            # Chercher les groupes parents de ce groupe (imbrication)
            try:
                clean_dn = escape_filter_chars(dn)
                conn.search(
                    search_base=LDAP_BASE_DN,
                    search_filter=f"(&(objectClass=group)(distinguishedName={clean_dn}))",
                    search_scope=SUBTREE,
                    attributes=["memberOf"]
                )
                if conn.entries and conn.entries[0].memberOf:
                    for parent_dn in conn.entries[0].memberOf.values:
                        parent_str = str(parent_dn)
                        if parent_str not in groupes_resolus_dns:
                            dns_a_resoudre.add(parent_str)
            except Exception as eg:
                logger.debug(f"[AUTH] Résolution groupe parent '{dn}' échouée : {eg}")
                continue

        # Ajouter aussi le compte nominatif (pour les ACL posées directement sur le compte)
        if sam:
            groups.append(f"{LDAP_DOMAIN}\\{sam}")

        conn.unbind()
        logger.info(f"[AUTH] Groupes résolus pour '{email}' : {groups}")

    except LDAPException as e:
        logger.error(f"[AUTH] Erreur LDAP pour '{email}' : {e}")
        # Deny by default : en cas d'erreur, pas d'accès
        return []
    except Exception as e:
        logger.error(f"[AUTH] Erreur inattendue pour '{email}' : {e}")
        return []

    _set_cache(email, groups)
    return groups


def check_access(user_groups: list[str], autorisés: list[str], interdits: list[str]) -> bool:
    """
    Vérifie l'accès selon la logique NTFS :
      accès accordé si :
        (user_groups ∩ autorisés != ∅) AND (user_groups ∩ interdits == ∅)

    Les DENY sont prioritaires sur les ALLOW, comme en NTFS Windows.
    Les groupes sont comparés sans tenir compte de la casse.
    """
    if not autorisés:
        return False

    user_lower = {g.lower() for g in user_groups}
    autorisés_lower = {g.lower() for g in autorisés}
    interdits_lower = {g.lower() for g in interdits}

    # Vérifier les DENY d'abord
    if user_lower & interdits_lower:
        return False

    # Vérifier les ALLOW
    return bool(user_lower & autorisés_lower)
