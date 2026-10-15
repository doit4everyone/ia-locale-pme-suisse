#!/usr/bin/env bash
# =============================================================================
# deploy.sh : Déploiement de la stack IA locale (conçue pour faciliter la conformité à la nLPD)
# DoIt4Everyone | https://doit4everyone.github.io
# Version : beta
#
# Usage : cloner le dépôt, puis depuis scripts/stack-ia-locale/ :
#   chmod +x deploy.sh && sudo ./deploy.sh
#
# Prérequis avant de lancer ce script :
#   - Docker et Docker Compose installés (voir §1.4 du guide)
#   - Compte svc-rag créé dans l'AD avec les bons groupes (voir §5.2)
#   - Certificat CA du DC exporté si disponible (voir §9.2)
#   - Serveur de modèles prêt et joignable depuis la VM (voir §2 du guide) :
#     Ollama  : ollama pull nomic-embed-text && ollama pull qwen3:14b && ollama pull qwen3:4b-instruct
#     vLLM    : serveurs de génération (port 8000) et d'embedding (port 8001)
#               lancés, clé d'API VLLM_API_KEY à portée de main
# =============================================================================

set -euo pipefail

# ─────────────────────────────────────────
# Couleurs
# ─────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERREUR]${NC} $*"; exit 1; }
ask()   { echo -e "${YELLOW}[?]${NC} $*"; }
# Une réponse affirmative : la lettre o, « oui » ou y (majuscules acceptées).
# Le chiffre zéro, voisin de la lettre o sur le clavier, n'est pas reconnu.
est_oui() { [[ "$1" =~ ^([oO]|[oO][uU][iI]|[yY]|[yY][eE][sS])$ ]]; }

# ─────────────────────────────────────────
# Vérifications préalables (avant toute modification du système)
# ─────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || error "Ce script doit être lancé en root (sudo ./deploy.sh)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

[ -f "env.example" ]          || error "env.example introuvable. Lancer depuis scripts/stack-ia-locale/"
[ -f "docker-compose.yml" ]   || error "docker-compose.yml introuvable."
[ -d "api" ]                  || error "Dossier api/ introuvable."

for cmd in docker openssl curl python3; do
    command -v "$cmd" >/dev/null 2>&1 || error "$cmd introuvable. Voir §1.4 du guide pour l'installation de Docker."
done
docker compose version >/dev/null 2>&1 || error "Plugin docker compose absent. Installer docker-compose-plugin."

echo ""
echo "============================================================"
echo "  Déploiement de la stack IA locale (conformité nLPD facilitée)"
echo "  DoIt4Everyone | $(date '+%Y-%m-%d')"
echo "============================================================"
echo ""

# ─────────────────────────────────────────
# Collecte des paramètres
# ─────────────────────────────────────────
echo -e "${BLUE}-- Paramètres de l'organisation --${NC}"

ask "Nom de l'organisation (ex: Axonix SA) :"
read -r ORG_NAME

echo ""
echo -e "${BLUE}-- Serveur de modèles (§2 du guide) --${NC}"
echo "  1) Ollama : installation simple, une question à la fois (un à deux utilisateurs simultanés)"
echo "  2) vLLM   : plusieurs questions en même temps (plusieurs utilisateurs simultanés)"
ask "Moteur [1 ou 2] :"
read -r MOTEUR_CHOIX
[[ "$MOTEUR_CHOIX" == "1" || "$MOTEUR_CHOIX" == "2" ]] || error "Répondre 1 (Ollama) ou 2 (vLLM)."

ask "IP ou nom DNS de la machine qui porte la carte graphique (ex: 192.168.1.10) :"
read -r MODELES_HOST
[[ -n "$MODELES_HOST" ]] || error "L'adresse du serveur de modèles ne peut pas etre vide."

if [ "$MOTEUR_CHOIX" = "1" ]; then
    MOTEUR="Ollama"
    LLM_API=ollama
    LLM_URL="http://${MODELES_HOST}:11434"
    EMBED_URL="$LLM_URL"
    JUDGE_MODEL=qwen3:4b-instruct
    VLLM_API_KEY=""

    # Tester Ollama avant de continuer
    info "Test de connectivite Ollama sur ${LLM_URL}..."
    TAGS=$(curl -s -m 10 "${LLM_URL}/api/tags") \
        || error "Ollama injoignable sur ${LLM_URL}. Vérifier OLLAMA_HOST=0.0.0.0 et le pare-feu de la machine (§2.3)."

    for m in "nomic-embed-text" "qwen3:14b" "qwen3:4b-instruct"; do
        if echo "$TAGS" | grep -qE "\"${m}[\":]"; then
            ok "Modele $m present"
        else
            warn "Modele $m absent : ollama pull ${m} (sur la machine qui porte la carte)"
        fi
    done
else
    MOTEUR="vLLM"
    LLM_API=openai
    LLM_URL="http://${MODELES_HOST}:8000"
    EMBED_URL="http://${MODELES_HOST}:8001"
    JUDGE_MODEL=qwen3:14b

    ask "Clé d'API vLLM (valeur de VLLM_API_KEY dans /etc/vllm/vllm.env, saisie masquée) :"
    read -rs VLLM_API_KEY
    echo ""
    [[ -n "$VLLM_API_KEY" ]] || error "La clé d'API vLLM ne peut pas etre vide (§2.4.4)."

    # Tester les deux serveurs vLLM : sans clé (refus attendu), puis avec la clé
    for couple in "de génération|${LLM_URL}|qwen3:14b" "d'embedding|${EMBED_URL}|nomic-embed-text"; do
        IFS='|' read -r ROLE URL MODELE <<< "$couple"
        info "Test du serveur vLLM ${ROLE} sur ${URL}..."
        CODE_SANS=$(curl -s -o /dev/null -w "%{http_code}" -m 10 "${URL}/v1/models" || true)
        [[ "$CODE_SANS" == "000" ]] && error "Serveur vLLM ${ROLE} injoignable sur ${URL}. Vérifier qu'il tourne et le pare-feu (§2.4)."
        [[ "$CODE_SANS" == "401" ]] || error "Le serveur ${ROLE} répond sans clé (code ${CODE_SANS}) : il n'exige pas de clé d'API. Le relancer avec --api-key (§2.4.5), puis refaire ce déploiement."
        MODELES=$(curl -s -m 10 -H "Authorization: Bearer ${VLLM_API_KEY}" "${URL}/v1/models" || true)
        if echo "$MODELES" | grep -q "\"${MODELE}\""; then
            ok "Serveur ${ROLE} : modèle ${MODELE} servi"
        else
            error "Serveur ${ROLE} : modèle ${MODELE} absent, ou clé refusée. Réponse : ${MODELES:0:200}"
        fi
    done
fi

echo ""
echo -e "${BLUE}-- Paramètres réseau de la VM --${NC}"

ask "IP de la VM Ubuntu (ex: 10.0.0.20) :"
read -r VM_IP

echo ""
echo -e "${BLUE}-- Active Directory --${NC}"

ask "Nom DNS du controleur de domaine (ex: DC01.votre-domaine.ch, pas une IP) :"
read -r DC_HOST
if [[ "$DC_HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    warn "Une IP a ete saisie pour le DC. Le guide recommande un nom DNS pour que la validation TLS LDAP fonctionne."
fi

ask "Nom NetBIOS du domaine (ex: DOMAINE) :"
read -r DOMAIN_NETBIOS

ask "Suffixe DNS du domaine (ex: votre-domaine.ch) :"
read -r DOMAIN_DNS

ask "DN complet de l'OU du compte svc-rag (ex: OU=COMPTES-SERVICE,DC=votre-domaine,DC=ch) :"
read -r SVC_RAG_OU

ask "Mot de passe du compte svc-rag (sans apostrophe) :"
read -rs SVC_RAG_PWD
echo ""
[[ "$SVC_RAG_PWD" == *"'"* ]] && error "Le mot de passe ne doit pas contenir d'apostrophe (limitation du .env)."
[[ -z "$SVC_RAG_PWD" ]] && error "Le mot de passe ne peut pas etre vide."

echo ""
echo -e "${BLUE}-- File server (partage SMB) --${NC}"

ask "Nom du file server (ex: FILESERVER, sans espaces) :"
read -r FILESERVER
[[ "$FILESERVER" == *" "* ]] && error "Le nom du file server ne doit pas contenir d'espaces."

ask "Nom du partage SMB (ex: FileService, sans espaces) :"
read -r SMB_SHARE_NAME
[[ "$SMB_SHARE_NAME" == *" "* ]] && error "Le nom du partage ne doit pas contenir d'espaces (probleme fstab)."

SMB_SHARE="//${FILESERVER}/${SMB_SHARE_NAME}"
SMB_MOUNT="/mnt/corpus-root"

echo ""
echo -e "${BLUE}-- Tokens d'authentification --${NC}"
echo "(Appuyer sur Entree pour générér automatiquement)"

ask "API_TOKEN (token utilisateurs RAG) :"
read -r API_TOKEN_INPUT
API_TOKEN="${API_TOKEN_INPUT:-$(openssl rand -hex 32)}"
[ -z "$API_TOKEN_INPUT" ] && ok "API_TOKEN généré automatiquement"

ask "ADMIN_TOKEN (token administration, distinct du precedent) :"
read -r ADMIN_TOKEN_INPUT
ADMIN_TOKEN="${ADMIN_TOKEN_INPUT:-$(openssl rand -hex 32)}"
[ "$ADMIN_TOKEN" = "$API_TOKEN" ] && error "ADMIN_TOKEN et API_TOKEN doivent etre differents."
[ -z "$ADMIN_TOKEN_INPUT" ] && ok "ADMIN_TOKEN généré automatiquement"

WEBUI_SECRET_KEY="$(openssl rand -hex 32)"
QDRANT_API_KEY="$(openssl rand -hex 32)"
LOG_HMAC_KEY="$(openssl rand -hex 32)"
MIP_TOKEN="$(openssl rand -hex 32)"

echo ""
echo -e "${BLUE}-- Documentation technique --${NC}"

ask "Dossier de documentation technique a la racine du partage (ex: DOIT4EVERYONE, laisser vide = DOIT4EVERYONE) :"
read -r DOC_PATHS_INPUT
DOCUMENTATION_PATHS="${DOC_PATHS_INPUT:-DOIT4EVERYONE}"
[ -z "$DOC_PATHS_INPUT" ] && warn "DOCUMENTATION_PATHS fixe a DOIT4EVERYONE. Adapter si aucun dossier de ce nom n'existe sur le partage : la collection documentation resterait vide."

echo ""
echo "============================================================"
echo "  Recapitulatif"
echo "============================================================"
echo "  Organisation    : $ORG_NAME"
echo "  Moteur          : $MOTEUR (génération : $LLM_URL ; embedding : $EMBED_URL)"
echo "  VM IP           : $VM_IP"
echo "  DC              : $DC_HOST"
echo "  Domaine         : $DOMAIN_NETBIOS / $DOMAIN_DNS"
echo "  svc-rag OU      : $SVC_RAG_OU"
echo "  Partage SMB     : $SMB_SHARE -> $SMB_MOUNT"
echo "  Documentation   : $DOCUMENTATION_PATHS"
echo "  Tokens          : générés (consulter /root/rag-stack/.env apres le deploiement)"
echo "============================================================"
echo ""
ask "Confirmer le deploiement ? [o/N] (la lettre o pour oui)"
read -r CONFIRM
if ! est_oui "$CONFIRM"; then
    case "$CONFIRM" in
        ""|[nN]|[nN][oO]|[nN][oO][nN]) info "Annulé." ;;
        *) warn "Réponse « $CONFIRM » non reconnue (la lettre o confirme). Déploiement annulé." ;;
    esac
    exit 0
fi

# ─────────────────────────────────────────
# Étape 1 : renommer les fichiers anon_*
# ─────────────────────────────────────────
echo ""
info "Étape 1 : renommage des fichiers..."

declare -A RENAMES=(
    ["api/anon_main.py"]="api/main.py"
    ["api/anon_auth.py"]="api/auth.py"
    ["anon_acl_resolver.py"]="acl_resolver.py"
    ["anon_indexer.py"]="indexer.py"
)

for src in "${!RENAMES[@]}"; do
    dst="${RENAMES[$src]}"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        ok "$src -> $dst"
    elif [ -f "$dst" ]; then
        warn "$dst deja present, conservé"
    else
        warn "$src introuvable, ignore"
    fi
done

# ─────────────────────────────────────────
# Étape 2 : créer les répertoires
# ─────────────────────────────────────────
info "Étape 2 : creation des répertoires..."

# Le disque de données chiffré doit être prêt AVANT le déploiement (§1.5) :
# sinon, .env, clés et données sont écrits en clair sur le disque système.
if ! mountpoint -q /srv/rag-donnees 2>/dev/null || [ ! -L /root/rag-stack/.env ]; then
    warn "Disque de données chiffré non préparé (/srv/rag-donnees non monté, ou liens de §1.5 absents)."
    warn "Les secrets et les données seraient écrits en clair sur le disque système."
    printf "Continuer quand même ? (o/N, la lettre o pour oui) : "
    read -r CONTINUER_SANS_CHIFFREMENT
    est_oui "$CONTINUER_SANS_CHIFFREMENT" || error "Déploiement interrompu : préparer d'abord le disque chiffré (§1.5)."
else
    ok "Disque de données chiffré monté, liens en place"
fi

mkdir -p /root/rag-stack/{qdrant_data,n8n_data,openwebui_data}
# n8n tourne sous l'utilisateur node (uid 1000) : sans ce chown, le dossier reste
# la propriété de root et n8n redémarre en boucle (EACCES sur /home/node/.n8n).
# On vise la cible réelle (disque chiffré du §1.5) : n8n_data est un lien.
chown -R 1000:1000 "$(readlink -f /root/rag-stack/n8n_data)"
mkdir -p /root/rag-pipeline
mkdir -p /var/log/rag
mkdir -p /etc/smbcredentials
# Certificats des applications Microsoft 365 (Partie 3, §11 et §12).
# Monté en lecture seule dans rag-api : créé ici avec des droits restreints,
# sinon Docker le créerait au démarrage avec des droits par défaut.
mkdir -p /etc/rag-certs
chmod 700 /etc/rag-certs

ok "Répertoires créés"

# ─────────────────────────────────────────
# Étape 3 : copier les fichiers dans /root/rag-stack
# ─────────────────────────────────────────
info "Étape 3 : copie des fichiers dans /root/rag-stack..."

cp docker-compose.yml /root/rag-stack/docker-compose.yml
# api/. copie le contenu du dossier, pas le dossier lui-meme.
# Evite le probleme d'imbrication api/api/ lors d'une relance.
mkdir -p /root/rag-stack/api
cp -r api/. /root/rag-stack/api/

cp acl_resolver.py /root/rag-pipeline/acl_resolver.py
if [ -f "indexer.py" ]; then
    cp indexer.py /root/rag-pipeline/indexer.py
else
    warn "indexer.py introuvable, a copier manuellement dans /root/rag-pipeline/"
fi
if [ -f "sp_indexer.py" ]; then
    cp sp_indexer.py /root/rag-pipeline/sp_indexer.py
fi
# Test de cloisonnement (§16) : l'exemple de cas est à adapter, puis à copier
# en cas_cloisonnement.json pour activer le contrôle après chaque synchronisation.
if [ -f "test_cloisonnement.py" ]; then
    cp test_cloisonnement.py /root/rag-pipeline/test_cloisonnement.py
    [ -f cas_cloisonnement.exemple.json ] && cp cas_cloisonnement.exemple.json /root/rag-pipeline/
fi
# Service de déchiffrement Purview (§14), construit seulement avec le profil « purview »
if [ -d "mip-service" ]; then
    mkdir -p /root/rag-stack/mip-service
    cp -r mip-service/. /root/rag-stack/mip-service/
fi

ok "Fichiers copies"

# ─────────────────────────────────────────
# Étape 4 : générer le .env
# ─────────────────────────────────────────
info "Étape 4 : generation du fichier .env..."

LDAP_BIND_DN="CN=svc-rag,${SVC_RAG_OU}"
LDAP_BASE_DN="DC=$(echo "$DOMAIN_DNS" | sed 's/\./,DC=/g')"

# Les valeurs avec caracteres speciaux sont entre guillemets simples.
# Restriction : pas d'apostrophe dans les valeurs (verifie a la saisie).
cat > /root/rag-stack/.env << ENVEOF
# -- Genere par deploy.sh le $(date '+%Y-%m-%d %H:%M') -------------------

# Organisation
ORG_NAME='${ORG_NAME}'

# Serveur de modèles : ${MOTEUR} (§2 du guide)
LLM_API=${LLM_API}
EMBED_API=${LLM_API}
LLM_BASE_URL=${LLM_URL}
EMBED_BASE_URL=${EMBED_URL}
JUDGE_BASE_URL=
LLM_MODEL=qwen3:14b
EMBED_MODEL=nomic-embed-text
JUDGE_MODEL=${JUDGE_MODEL}
VLLM_API_KEY=${VLLM_API_KEY}
# Avec Ollama seulement
JUDGE_KEEP_ALIVE=2h

# Qdrant
QDRANT_HOST=http://qdrant:6333
QDRANT_COLLECTION=documents
QDRANT_API_KEY=${QDRANT_API_KEY}
LOG_HMAC_KEY=${LOG_HMAC_KEY}
CAS_CLOISONNEMENT=/rag-pipeline/cas_cloisonnement.json
DOCUMENTATION_COLLECTION=documentation
DOCUMENTATION_PATHS=${DOCUMENTATION_PATHS}

# Tokens d'authentification
API_TOKEN=${API_TOKEN}
ADMIN_TOKEN=${ADMIN_TOKEN}

# Open WebUI
WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}
JWT_EXPIRES_IN=4h

# LDAP / Active Directory
LDAP_HOST=${DC_HOST}
LDAP_PORT=636
LDAP_USE_TLS=true
LDAP_BASE_DN='${LDAP_BASE_DN}'
LDAP_BIND_DN='${LDAP_BIND_DN}'
LDAP_BIND_PWD='${SVC_RAG_PWD}'
LDAP_DOMAIN=${DOMAIN_NETBIOS}
LDAP_CA_CERT=/etc/ssl/certs/ad-chain.pem

# Partage SMB
SMB_SHARE=${SMB_SHARE}
SMB_MOUNT=${SMB_MOUNT}
SMB_USER=svc-rag
SMB_PASSWORD='${SVC_RAG_PWD}'
SMB_DOMAIN=${DOMAIN_NETBIOS}

# Variables pour les lancements manuels d'indexer.py et acl_resolver.py
# (indexer.py lit OLLAMA_URL et ORG_OWNER, pas LLM_BASE_URL ni ORG_NAME ;
# OLLAMA_URL désigne le serveur d'embedding, avec Ollama comme avec vLLM)
OLLAMA_URL=${EMBED_URL}
QDRANT_URL=http://localhost:6333
ORG_OWNER='${ORG_NAME}'

# Logs nLPD
LOG_FILE=/var/log/rag/rag-queries.jsonl
REPORT_DIR=/var/log/rag

# Parametres RAG (valides en lab sur VM-RAG-LAB, septembre 2026)
TOP_K=20
CONTEXT_THRESHOLD=0.01
MAX_CONTEXT_CHUNKS=14
CHUNK_SIZE=150
CHUNK_OVERLAP=20
MIN_CHUNK_WORDS=8

# Scripts de synchronisation
SYNC_SCRIPTS_DIR=/rag-pipeline
SYNC_PYTHON=python3
SYNC_TIMEOUT_INDEXER=600
SYNC_TIMEOUT_ACL=300

# Cache des groupes AD en secondes (auth.py)
GROUPS_CACHE_TTL=300

# Extension Entra ID (Partie 3, désactivée par défaut, voir §11)
ENTRA_ENABLED=false
ENTRA_TENANT_ID=
ENTRA_CLIENT_ID=
ENTRA_CERT_PATH=/etc/rag-certs/rag-identity.crt
ENTRA_KEY_PATH=/etc/rag-certs/rag-identity.key
ENTRA_CERT_THUMBPRINT=

# Synthèse des réunions Teams (Partie 3, inactive tant que les variables sont vides)
TEAMS_CLIENT_ID=
TEAMS_CERT_PATH=/etc/rag-certs/rag-teams.crt
TEAMS_KEY_PATH=/etc/rag-certs/rag-teams.key
TEAMS_CERT_THUMBPRINT=
TEAMS_GROUP_ID=
TEAMS_LOOKBACK_HOURS=48
TEAMS_MAX_PAR_SYNC=3
TEAMS_STATE_FILE=/var/log/rag/teams_state.json

# Indexation SharePoint Online (Partie 3, inactive tant que SP_SITES est vide)
SP_CLIENT_ID=
SP_CERT_THUMBPRINT=
SP_KEY_PATH=/etc/rag-certs/rag-sharepoint.key
SP_SITES=
SP_EXCLUDE_DRIVES='Preservation Hold Library'
SP_MAX_FILE_MB=50
SYNC_TIMEOUT_SHAREPOINT=900

# Fenêtres de contexte demandées à Ollama (sans effet avec vLLM : --max-model-len)
# La fenêtre du juge doit couvrir celle du modèle principal (§10.6)
LLM_NUM_CTX=16384
JUDGE_NUM_CTX=16384

# Documents protégés par Purview (§14), inactif tant que COMPOSE_PROFILES et MIP_URL sont vides
COMPOSE_PROFILES=
MIP_URL=
MIP_TOKEN=${MIP_TOKEN}
MIP_TENANT_DOMAINE=
MIP_CLIENT_ID=
MIP_ETIQUETTES_EXCLUES=
MIP_CACHE_TTL=3600

# n8n
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=$(openssl rand -hex 16)
N8N_WEBHOOK_URL=http://${VM_IP}:5678
N8N_SECURE_COOKIE=false
ENVEOF

chmod 600 /root/rag-stack/.env
ok ".env généré dans /root/rag-stack/.env"

# ─────────────────────────────────────────
# Étape 5 : fichier de credentials SMB
# ─────────────────────────────────────────
info "Étape 5 : creation du fichier de credentials SMB..."

cat > /etc/smbcredentials/svc-rag << CREDSEOF
username=svc-rag
password=${SVC_RAG_PWD}
domain=${DOMAIN_NETBIOS}
CREDSEOF

chmod 600 /etc/smbcredentials/svc-rag
chown root:root /etc/smbcredentials/svc-rag
ok "/etc/smbcredentials/svc-rag créé"

# ─────────────────────────────────────────
# Étape 6 : certificat CA du DC
# ─────────────────────────────────────────
info "Étape 6 : certificat CA du controleur de domaine..."

if [ -f "/etc/ssl/certs/ad-chain.pem" ] && [ -s "/etc/ssl/certs/ad-chain.pem" ]; then
    ok "ad-chain.pem present et non vide"
else
    warn "ad-chain.pem absent ou vide de /etc/ssl/certs/"
    echo ""
    echo "  Exporter le certificat CA depuis le DC Windows :"
    echo "  1. Copier le fichier .cer sur la VM (ex: /tmp/ad-root-ca.cer)"
    echo "  2. Convertir : openssl x509 -inform DER -in /tmp/ad-root-ca.cer -out /etc/ssl/certs/ad-chain.pem"
    echo "  3. Relancer ce script, ou continuer en lab sans validation TLS :"
    echo "     sudo touch /etc/ssl/certs/ad-chain.pem"
    echo ""
    ask "Continuer sans certificat (lab : connexion LDAPS sans validation) ? [o/N]"
    read -r SKIP_CERT
    if est_oui "$SKIP_CERT"; then
        touch /etc/ssl/certs/ad-chain.pem
        warn "Fichier vide créé. auth.py passera en CERT_NONE : connexion LDAPS active, certificat non verifie (lab uniquement)."
    else
        error "Deploiement interrompu. Installer le certificat et relancer."
    fi
fi

# ─────────────────────────────────────────
# Étape 7 : montage SMB
# ─────────────────────────────────────────
info "Étape 7 : montage du partage SMB..."

apt-get update -qq >/dev/null 2>&1 || error "apt-get update a echoue. Vérifier la connexion reseau."
apt-get install -y -qq cifs-utils smbclient >/dev/null 2>&1 \
    || error "Installation de cifs-utils / smbclient echouee."

mkdir -p "$SMB_MOUNT"

if mount | grep -q "$SMB_MOUNT"; then
    ok "$SMB_MOUNT deja monte"
else
    if mount -t cifs "$SMB_SHARE" "$SMB_MOUNT" \
        -o credentials=/etc/smbcredentials/svc-rag,vers=3.1.1,uid=1000,gid=1000,ro 2>/dev/null; then
        ok "$SMB_SHARE monte sur $SMB_MOUNT"
    else
        warn "Montage SMB echoue. Vérifier que svc-rag existe dans l'AD et que le partage est accessible."
        warn "Continuer sans partage monte (a monter manuellement avant l'indexation)."
    fi
fi

# fstab en ro : le corpus n'est jamais ecrit par la stack
if ! grep -q "$SMB_MOUNT" /etc/fstab; then
    {
        echo ""
        echo "# Partage SMB corpus RAG (svc-rag, lecture seule)"
        echo "${SMB_SHARE} ${SMB_MOUNT} cifs credentials=/etc/smbcredentials/svc-rag,vers=3.1.1,uid=1000,gid=1000,ro,soft,nofail 0 0"
    } >> /etc/fstab
    ok "Entree fstab ajoutee (ro)"
fi

# ─────────────────────────────────────────
# Étape 8 : lancement Docker
# ─────────────────────────────────────────
info "Étape 8 : lancement de la stack Docker..."

cd /root/rag-stack

docker compose build --no-cache rag-api
docker compose up -d

sleep 15
docker compose ps

ok "Stack Docker lancee"

# ─────────────────────────────────────────
# Étape 9 : environnement Python
# ─────────────────────────────────────────
info "Étape 9 : environnement Python pour les scripts..."

apt-get install -y -qq python3-venv python3-pip >/dev/null 2>&1 \
    || error "Installation de python3-venv echouee."

cd /root/rag-pipeline
python3 -m venv .venv
source .venv/bin/activate

# Dépendances de indexer.py et acl_resolver.py, lancés aussi depuis l'hôte (§0, étapes 12 et 13).
# Même liste que l'étape 11 du §0 : sans ldap3, impacket et smbprotocol, acl_resolver.py échoue.
# httpx est importé directement par indexer.py (non garanti comme dépendance transitive).
pip install -q qdrant-client python-docx pdfplumber python-pptx httpx \
    ldap3 impacket rank-bm25 smbprotocol

ok "Environnement Python prêt"

# ─────────────────────────────────────────
# Étape 10 : validation rapide
# ─────────────────────────────────────────
info "Étape 10 : validation..."

PROBLEMES=""

# La RAG API met quelques dizaines de secondes à démarrer : on attend sa réponse
# jusqu'à 120 secondes, depuis son propre conteneur (le contrôle ne doit pas
# dépendre de n8n, qui peut lui-même être en panne).
HEALTH=""
for i in $(seq 1 24); do
    HEALTH=$(docker exec rag-api python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/health', timeout=5).read().decode())" 2>/dev/null || echo "")
    echo "$HEALTH" | grep -q '"status":"ok"' && break
    sleep 5
done

if echo "$HEALTH" | grep -q '"status":"ok"'; then
    ok "RAG API répond : $HEALTH"
else
    PROBLEMES="${PROBLEMES}  - RAG API sans réponse après 120 s (docker logs rag-api --tail 30)\n"
fi

# Les quatre conteneurs doivent tourner, sans redémarrage. Un conteneur qui plante
# au démarrage (n8n sans droits sur son dossier, par exemple) redémarre en boucle
# sans que « docker compose up -d » le signale.
sleep 20
for C in qdrant rag-api open-webui n8n; do
    ETAT=$(docker inspect -f '{{.State.Status}} {{.RestartCount}}' "$C" 2>/dev/null || echo "absent 0")
    if [ "$ETAT" = "running 0" ]; then
        ok "Conteneur $C démarré"
    else
        PROBLEMES="${PROBLEMES}  - conteneur $C : état « ${ETAT} » (état et nombre de redémarrages ; docker logs $C --tail 30)\n"
    fi
done

# Le serveur de modèles doit être joint DEPUIS le conteneur, pas seulement depuis la VM
for VAR_URL in LLM_BASE_URL EMBED_BASE_URL; do
    CODE=$(docker exec rag-api python3 -c "
import os, httpx
api = os.environ.get('LLM_API', 'ollama')
cle = os.environ.get('VLLM_API_KEY', '')
h = {'Authorization': 'Bearer ' + cle} if cle else {}
u = os.environ['${VAR_URL}'] + ('/v1/models' if api == 'openai' else '/api/tags')
print(httpx.get(u, headers=h, timeout=10).status_code)
" 2>/dev/null || echo "injoignable")
    if [ "$CODE" = "200" ]; then
        ok "Serveur de modèles joint depuis le conteneur (${VAR_URL})"
    else
        warn "Serveur de modèles non joint depuis le conteneur (${VAR_URL} : ${CODE}). Voir « En cas de problème » au §0."
    fi
done

QDRANT=$(curl -s -H "api-key: ${QDRANT_API_KEY}" http://localhost:6333/collections 2>/dev/null || echo "")
if echo "$QDRANT" | grep -q '"status":"ok"'; then
    ok "Qdrant accessible"
else
    PROBLEMES="${PROBLEMES}  - Qdrant ne répond pas (docker logs qdrant --tail 30)\n"
fi

# Un déploiement incomplet ne doit pas se terminer par « Déploiement terminé »
if [ -n "$PROBLEMES" ]; then
    echo ""
    echo -e "${RED}[ERREUR]${NC} Déploiement incomplet :"
    printf "%b" "$PROBLEMES"
    echo "  Corriger la cause, puis relancer : cd /root/rag-stack && docker compose up -d"
    exit 1
fi

# ─────────────────────────────────────────
# Résumé final
# ─────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Déploiement terminé"
echo "============================================================"
echo ""
echo "  Open WebUI   : http://${VM_IP}:3001"
echo "  n8n          : http://${VM_IP}:5678"
echo "  Logs nLPD    : /var/log/rag/rag-queries.jsonl"
echo "  Tokens       : /root/rag-stack/.env (chmod 600)"
echo ""
echo "  Partie 3 (Microsoft 365) : inactive par défaut."
echo "    Extension Entra ID     : ENTRA_* dans le .env, voir §11 du guide"
echo "    Synthèse Teams         : TEAMS_* dans le .env, voir §12 du guide"
echo ""
echo "  Etapes suivantes :"
echo "  1. Configurer Open WebUI (§0, étape 14) : connexion à la RAG API dans la section"
echo "     API compatibles OpenAI, authentification LDAP (attribut pour le courriel :"
echo "     userPrincipalName ; attribut pour le nom d'utilisateur : sAMAccountName), puis"
echo "     puis vérifier que la génération de titre, d'étiquettes et de questions de suivi"
echo "     est désactivée (le Compose le fait au premier démarrage ; sinon : Settings >"
echo "     Admin > Interface, et enregistrer). Sans cela, chaque question en déclenche d'autres"
echo "  2. Lancer la premiere indexation :"
echo "     cd /root/rag-pipeline && source .venv/bin/activate"
echo "     set -a && source /root/rag-stack/.env && set +a"
echo "     python indexer.py --corpus ${SMB_MOUNT}"
echo "  3. Lancer la resolution des ACL :"
echo "     python acl_resolver.py --share ${SMB_SHARE} --mount ${SMB_MOUNT}"
echo "  4. Prendre un snapshot Qdrant (voir §3.7)"
echo "  5. Configurer les workflows n8n (http://${VM_IP}:5678) :"
echo "     a. Creer le credential SMTP : Settings > Credentials > Add > SMTP"
echo "     b. Importer scripts/N8N/n8n-sync-corpus.json"
echo "     c. Importer scripts/N8N/n8n-rappel-rotation-svc-rag.json"
echo "     d. Rattacher le credential SMTP sur chaque noeud email"
echo "     e. Activer les deux workflows et executer une validation manuelle"
echo "     f. Optionnel, apres la configuration de la §12 : importer scripts/N8N/n8n-teams-sync.json"
echo ""
echo "  Consultez /root/rag-stack/.env pour les tokens générés."
echo "============================================================"
