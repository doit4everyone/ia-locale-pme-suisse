"""
teams_graph.py : récupération des transcriptions Teams via Microsoft Graph.

Partie 3 du guide de déploiement. Module importé par main.py, utilisé par
l'endpoint POST /teams/sync, appelé périodiquement par n8n.

Flux :
  1. Membres du groupe d'adhésion (TEAMS_GROUP_ID), lus avec l'application
     RAG-Identity-Resolver (auth.py, permission GroupMember.Read.All).
  2. Pour chaque membre : getAllTranscripts (réunions planifiées dont il est
     l'organisateur), avec l'application RAG-Teams-Reader
     (OnlineMeetingTranscript.Read.All + stratégie d'accès applicatif
     attribuée au même groupe).
  3. Téléchargement du VTT des transcriptions non encore traitées.
  4. La synthèse est faite par main.py (module teams.py).

Le groupe joue un double rôle : il limite ce que l'application a le droit
de lire (stratégie d'accès applicatif) et il définit qui le pipeline
interroge. Retirer une personne du groupe arrête le traitement de ses
réunions.

Les identifiants des transcriptions déjà traitées sont conservés dans
TEAMS_STATE_FILE (jamais leur contenu), pour ne pas traiter deux fois la
même réunion.

Variables d'environnement :
  TEAMS_CLIENT_ID        : ID d'application de RAG-Teams-Reader
  TEAMS_CERT_PATH        : certificat public PEM
  TEAMS_KEY_PATH         : clé privée PEM
  TEAMS_CERT_THUMBPRINT  : empreinte SHA-1 affichée dans Entra
  TEAMS_GROUP_ID         : ID d'objet du groupe d'adhésion
  TEAMS_LOOKBACK_HOURS   : fenêtre de recherche en heures (défaut : 48)
  TEAMS_MAX_PAR_SYNC     : nombre maximal de synthèses par passage (défaut : 3)
  TEAMS_STATE_FILE       : fichier d'état (défaut : /var/log/rag/teams_state.json)
  ENTRA_TENANT_ID        : partagé avec auth.py
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

import auth

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.microsoft.com/v1.0"
GRAPH_TIMEOUT = 30

TENANT_ID        = os.getenv("ENTRA_TENANT_ID", "")
TEAMS_CLIENT_ID  = os.getenv("TEAMS_CLIENT_ID", "")
TEAMS_CERT_PATH  = os.getenv("TEAMS_CERT_PATH", "") or "/etc/rag-certs/rag-teams.crt"
TEAMS_KEY_PATH   = os.getenv("TEAMS_KEY_PATH", "") or "/etc/rag-certs/rag-teams.key"
TEAMS_THUMBPRINT = os.getenv("TEAMS_CERT_THUMBPRINT", "")
TEAMS_GROUP_ID   = os.getenv("TEAMS_GROUP_ID", "")
LOOKBACK_HOURS   = int(os.getenv("TEAMS_LOOKBACK_HOURS", "") or "48")
MAX_PAR_SYNC     = int(os.getenv("TEAMS_MAX_PAR_SYNC", "") or "3")
STATE_FILE       = os.getenv("TEAMS_STATE_FILE", "") or "/var/log/rag/teams_state.json"

# Au-delà, une transcription a expiré côté Teams (120 jours par défaut) :
# inutile de garder son identifiant dans le fichier d'état.
RETENTION_ETAT_JOURS = 130


class ConfigurationManquante(Exception):
    pass


def verifier_configuration():
    manquants = [nom for nom, val in (
        ("ENTRA_TENANT_ID", TENANT_ID), ("TEAMS_CLIENT_ID", TEAMS_CLIENT_ID),
        ("TEAMS_CERT_THUMBPRINT", TEAMS_THUMBPRINT), ("TEAMS_GROUP_ID", TEAMS_GROUP_ID),
    ) if not val]
    if manquants:
        raise ConfigurationManquante("Variables manquantes : " + ", ".join(manquants))


# ─────────────────────────────────────────
# Jeton de l'application RAG-Teams-Reader
# ─────────────────────────────────────────

_msal_app = None


def _jeton_teams() -> str:
    global _msal_app
    if _msal_app is None:
        import msal
        with open(TEAMS_KEY_PATH, "r", encoding="utf-8") as f:
            cle = f.read()
        _msal_app = msal.ConfidentialClientApplication(
            client_id=TEAMS_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{TENANT_ID}",
            client_credential={"private_key": cle, "thumbprint": TEAMS_THUMBPRINT},
        )
    r = _msal_app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in r:
        raise RuntimeError(f"Jeton Graph (RAG-Teams-Reader) refusé : {r.get('error')} : "
                           f"{r.get('error_description', '')[:200]}")
    return r["access_token"]


def _erreur_graph(r: httpx.Response) -> str:
    """Message lisible, en s'appuyant sur innerError.code comme le recommande Microsoft."""
    try:
        err = r.json().get("error", {})
        code = (err.get("innerError") or {}).get("code") or err.get("code", "")
    except Exception:
        code = ""
    if code == "GraphAccessToTranscriptsDisabled":
        return ("403 GraphAccessToTranscriptsDisabled : l'accès Graph aux transcriptions "
                "est désactivé dans le centre d'administration Teams (Transcript API access)")
    return f"HTTP {r.status_code} {code}".strip()


# ─────────────────────────────────────────
# 1. Membres du groupe d'adhésion
# ─────────────────────────────────────────

def membres_groupe() -> list[dict]:
    """
    Membres directs du groupe (utilisateurs uniquement), lus avec
    RAG-Identity-Resolver. Retourne id, UPN, mail et nom affiché.
    """
    jeton = auth._get_graph_token()
    membres, url = [], f"{GRAPH_URL}/groups/{TEAMS_GROUP_ID}/members"
    params = {"$select": "id,userPrincipalName,mail,displayName", "$top": "999"}
    with httpx.Client(timeout=GRAPH_TIMEOUT, headers={"Authorization": f"Bearer {jeton}"}) as c:
        while url:
            r = c.get(url, params=params)
            if r.status_code != 200:
                raise RuntimeError(f"Lecture du groupe impossible : {_erreur_graph(r)}")
            data = r.json()
            for m in data.get("value", []):
                if m.get("@odata.type") == "#microsoft.graph.user":
                    membres.append(m)
            url, params = data.get("@odata.nextLink"), None
    return membres


# ─────────────────────────────────────────
# 2. et 3. Transcriptions
# ─────────────────────────────────────────

def transcriptions_recentes(user_id: str, jeton: str) -> list[dict]:
    """Transcriptions des réunions organisées par user_id, sur la fenêtre configurée."""
    debut = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = (f"{GRAPH_URL}/users/{user_id}/onlineMeetings/getAllTranscripts"
           f"(meetingOrganizerUserId='{user_id}',startDateTime={debut})")
    resultats = []
    with httpx.Client(timeout=GRAPH_TIMEOUT, headers={"Authorization": f"Bearer {jeton}"}) as c:
        while url:
            r = c.get(url)
            if r.status_code != 200:
                raise RuntimeError(_erreur_graph(r))
            data = r.json()
            resultats.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
    return resultats


def telecharger_vtt(transcription: dict, jeton: str) -> str | None:
    """
    Contenu VTT d'une transcription. Retourne None si le contenu n'est pas
    encore disponible (la transcription peut être listée avant d'être prête).
    """
    url = transcription["transcriptContentUrl"]
    with httpx.Client(timeout=GRAPH_TIMEOUT, headers={"Authorization": f"Bearer {jeton}"}) as c:
        r = c.get(url, params={"$format": "text/vtt"})
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise RuntimeError(_erreur_graph(r))
    return r.text


# ─────────────────────────────────────────
# État : transcriptions déjà traitées
# ─────────────────────────────────────────

def charger_etat() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def enregistrer_etat(etat: dict):
    limite = (datetime.now(timezone.utc) - timedelta(days=RETENTION_ETAT_JOURS)).isoformat()
    etat = {k: v for k, v in etat.items() if v >= limite}
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(etat, f)
    os.replace(tmp, STATE_FILE)


def date_locale(iso: str) -> str:
    """Date et heure de la transcription, heure de Zurich, pour l'objet de l'email."""
    try:
        from zoneinfo import ZoneInfo
        d = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return d.astimezone(ZoneInfo("Europe/Zurich")).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso[:16]


def a_traiter() -> tuple[list[dict], list[str]]:
    """
    Liste des transcriptions nouvelles, dans la limite de MAX_PAR_SYNC.
    Chaque élément contient : id, organisateur (dict), cree_le, vtt.
    Retourne aussi la liste des erreurs rencontrées, par organisateur.
    """
    verifier_configuration()
    etat = charger_etat()
    jeton = _jeton_teams()
    nouvelles, erreurs = [], []

    for membre in membres_groupe():
        try:
            for t in transcriptions_recentes(membre["id"], jeton):
                if t["id"] in etat or len(nouvelles) >= MAX_PAR_SYNC:
                    continue
                vtt = telecharger_vtt(t, jeton)
                if vtt is None:
                    logger.info(f"[TEAMS] Contenu pas encore disponible, prochain passage : {t['id'][:16]}")
                    continue
                nouvelles.append({"id": t["id"], "organisateur": membre,
                                  "cree_le": t.get("createdDateTime", ""), "vtt": vtt})
        except Exception as e:
            nom = membre.get("userPrincipalName", membre["id"])
            erreurs.append(f"{nom} : {e}")
            logger.error(f"[TEAMS] Récupération échouée pour {nom} : {e}")
    return nouvelles, erreurs


def marquer_traitee(transcription_id: str):
    etat = charger_etat()
    etat[transcription_id] = datetime.now(timezone.utc).isoformat()
    enregistrer_etat(etat)
