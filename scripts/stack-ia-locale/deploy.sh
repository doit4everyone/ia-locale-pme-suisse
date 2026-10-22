#!/usr/bin/env bash
# =============================================================================
# deploy.sh : Déploiement de la stack IA locale (conçue pour faciliter la conformité à la nLPD)
# DoIt4Everyone | https://doit4everyone.github.io
# Version : beta (2.22.2)
#
# Usage : cloner le dépôt, puis depuis scripts/stack-ia-locale/ :
#   chmod +x deploy.sh && sudo ./deploy.sh
#
# Prérequis avant de lancer ce script :
#   - Docker et Docker Compose installés (voir §1.4 du guide)
#   - Compte svc-rag créé dans l'AD avec les bons groupes (voir §5.2)
#   - Certificat CA du DC exporté si disponible (voir §9.2)
#   - DNS de la VM : uniquement les serveurs DNS du domaine (§0, étape 4)
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

# Un nom du domaine (contrôleur, serveur de fichiers) doit se résoudre par le DNS
# du domaine. Sans cela, LDAP et la lecture des droits échouent plus tard avec
# des messages trompeurs (« invalid server address », NT_STATUS_INVALID_PARAMETER).
verifier_nom() {
    local nom="$1" role="$2" adresse
    adresse=$(getent hosts "$nom" 2>/dev/null | awk '{print $1; exit}' || true)
    if [[ -n "$adresse" ]]; then
        ok "$role : $nom → $adresse"
    else
        error "$role : « $nom » ne se résout pas. La VM doit interroger le DNS du domaine (§0, étape 4 ; contrôle : resolvectl status)."
    fi
}

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

# Un .env existe déjà : installation précédente. Le déploiement le remplace en
# entier (nouveaux jetons, réglages Microsoft 365 perdus). Avant toute
# modification et avant les questions : confirmation explicite, puis copie
# datée (point 125 du suivi).
ENV_EXISTANT=$(readlink -f /root/rag-stack/.env 2>/dev/null || true)
INSTALLATION_EXISTANTE=non   # utilisé plus bas pour le registre des documents retirés
if [ -n "$ENV_EXISTANT" ] && [ -s "$ENV_EXISTANT" ]; then
    INSTALLATION_EXISTANTE=oui
    warn "Un fichier .env existe déjà : ${ENV_EXISTANT}"
    warn "Le déploiement va le REMPLACER : tous les jetons changent (identifiant n8n et"
    warn "clé de la connexion rag-api d'Open WebUI à refaire), réglages Microsoft 365 perdus."
    warn "Sur une installation en service, ne pas relancer deploy.sh : mettre à jour à la main."
    ask "Remplacer le .env existant (une copie datée sera conservée) ? [o/N]"
    read -r REMPLACER_ENV
    est_oui "$REMPLACER_ENV" || { info "Annulé : le .env existant est conservé, rien n'a été modifié."; exit 0; }
    SAUVEGARDE_ENV="${ENV_EXISTANT}.$(date +%Y%m%d-%H%M%S)"
    cp -p "$ENV_EXISTANT" "$SAUVEGARDE_ENV"
    chmod 600 "$SAUVEGARDE_ENV"
    ok "Copie du .env existant : ${SAUVEGARDE_ENV} (contient des secrets : la supprimer une fois inutile)"
fi

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

# Nom de la stack : celui que les utilisateurs tapent, inscrit dans le certificat
# de Nginx (§9.8). Un nom de service plutôt que le nom de la VM : la VM peut être
# remplacée sans changer l'adresse des utilisateurs ni le certificat.
ask "Nom DNS complet de la stack, pour les utilisateurs (ex: rag.votre-domaine.ch) :"
read -r RAG_FQDN
RAG_FQDN=$(echo "$RAG_FQDN" | tr '[:upper:]' '[:lower:]')
[[ "$RAG_FQDN" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$ ]] \
    || error "Nom de la stack invalide : un nom DNS complet est attendu (ex: rag.votre-domaine.ch)."
ADRESSE_FQDN=$(getent hosts "$RAG_FQDN" 2>/dev/null | awk '{print $1; exit}' || true)
if [[ -z "$ADRESSE_FQDN" ]]; then
    warn "« $RAG_FQDN » ne se résout pas encore : créer l'enregistrement DNS vers $VM_IP"
    warn "(sur le DC : Add-DnsServerResourceRecordA, §9.8). Le déploiement continue."
elif [[ "$ADRESSE_FQDN" != "$VM_IP" ]]; then
    warn "« $RAG_FQDN » pointe vers $ADRESSE_FQDN, et non vers la VM ($VM_IP) : corriger l'enregistrement DNS."
else
    ok "Nom de la stack : $RAG_FQDN → $VM_IP"
fi

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

verifier_nom "$DC_HOST" "Contrôleur de domaine"

# Un DNS public (8.8.8.8, 1.1.1.1...) à côté du DNS du domaine provoque des pannes
# AU HASARD DES REDÉMARRAGES : systemd-resolved bascule sur le serveur public dès
# que celui du domaine tarde une fois, et n'en revient pas. Les noms du domaine
# deviennent alors introuvables (cas vécu en lab, §0 « En cas de problème »).
DNS_PUBLICS=$(resolvectl dns 2>/dev/null \
    | grep -oE '(^|[[:space:]])(8\.8\.8\.8|8\.8\.4\.4|1\.1\.1\.1|1\.0\.0\.1|9\.9\.9\.9|149\.112\.112\.112|208\.67\.222\.222|208\.67\.220\.220)([[:space:]]|$)' \
    | tr -d ' ' | sort -u | tr '\n' ' ' || true)
if [[ -n "$DNS_PUBLICS" ]]; then
    warn "DNS public configuré sur la VM : ${DNS_PUBLICS}"
    warn "Seuls les DNS du domaine doivent figurer dans la configuration réseau (netplan, §0 étape 4)."
    warn "Sinon, LDAP et la lecture des droits tombent en panne au hasard d'un redémarrage."
    ask "Continuer quand même ? [o/N] (corriger d'abord est recommandé)"
    read -r CONTINUER_DNS
    est_oui "$CONTINUER_DNS" || error "Déploiement interrompu : retirer le DNS public de /etc/netplan/*.yaml, puis netplan apply."
fi

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
verifier_nom "$FILESERVER" "Serveur de fichiers"

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
# La RAG API refuse de démarrer avec un jeton de moins de 32 caractères
[ "${#API_TOKEN}" -ge 32 ] || error "API_TOKEN trop court (32 caractères au moins) : laisser vide pour le générer."
[ -z "$API_TOKEN_INPUT" ] && ok "API_TOKEN généré automatiquement"

ask "ADMIN_TOKEN (token administration, distinct du precedent) :"
read -r ADMIN_TOKEN_INPUT
ADMIN_TOKEN="${ADMIN_TOKEN_INPUT:-$(openssl rand -hex 32)}"
[ "${#ADMIN_TOKEN}" -ge 32 ] || error "ADMIN_TOKEN trop court (32 caractères au moins) : laisser vide pour le générer."
[ "$ADMIN_TOKEN" = "$API_TOKEN" ] && error "ADMIN_TOKEN et API_TOKEN doivent etre differents."
[ -z "$ADMIN_TOKEN_INPUT" ] && ok "ADMIN_TOKEN généré automatiquement"

WEBUI_SECRET_KEY="$(openssl rand -hex 32)"
QDRANT_API_KEY="$(openssl rand -hex 32)"
LOG_HMAC_KEY="$(openssl rand -hex 32)"
OWUI_JWT_SECRET="$(openssl rand -hex 32)"
MIP_TOKEN="$(openssl rand -hex 32)"

echo ""
echo -e "${BLUE}-- Documentation technique (facultatif) --${NC}"
echo "  La stack range les documents dans deux collections de l'index :"
echo "    documents     : le corpus de l'entreprise (tout le partage, par défaut) ;"
echo "    documentation : la documentation technique (guides, procédures, manuels de"
echo "                    logiciels), si elle est rangée dans un dossier dédié À LA"
echo "                    RACINE du partage."
echo "  Les droits NTFS s'appliquent de la même façon aux deux collections. Changer ce"
echo "  choix plus tard demande une réindexation complète (§5.9)."
ask "Dossier(s) de documentation à la racine du partage, séparés par des virgules (vide = aucun) :"
read -r DOC_PATHS_INPUT
# Espaces autour des virgules retirés ; un chemin avec / ou \ n'est pas à la racine
DOCUMENTATION_PATHS=$(echo "$DOC_PATHS_INPUT" | sed 's/[[:space:]]*,[[:space:]]*/,/g; s/^[[:space:]]*//; s/[[:space:]]*$//')
[[ "$DOCUMENTATION_PATHS" == *"/"* || "$DOCUMENTATION_PATHS" == *"\\"* ]] \
    && error "Un dossier de documentation doit être à la racine du partage : indiquer son nom seul, sans / ni \\."
[[ "$DOCUMENTATION_PATHS" == *"'"* ]] && error "Le nom du dossier ne doit pas contenir d'apostrophe (limitation du .env)."

echo ""
echo "============================================================"
echo "  Recapitulatif"
echo "============================================================"
echo "  Organisation    : $ORG_NAME"
echo "  Moteur          : $MOTEUR (génération : $LLM_URL ; embedding : $EMBED_URL)"
echo "  VM IP           : $VM_IP"
echo "  Nom de la stack : https://$RAG_FQDN (n8n : https://$RAG_FQDN:5678)"
echo "  DC              : $DC_HOST"
echo "  Domaine         : $DOMAIN_NETBIOS / $DOMAIN_DNS"
echo "  svc-rag OU      : $SVC_RAG_OU"
echo "  Partage SMB     : $SMB_SHARE -> $SMB_MOUNT"
echo "  Documentation   : ${DOCUMENTATION_PATHS:-(aucun dossier : tout le partage va dans documents)}"
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
# Registre des documents retirés de la recherche (§16.5.2). Créé vide, et daté,
# sur une installation NEUVE seulement : le corpus est vide ou ses droits viennent
# d'être résolus. Sur une installation existante, un registre absent est anormal :
# en recréer un vide effacerait la protection qu'il porte (2.21.8). Jamais écrasé.
QDRANT_COLLECTIONS="$(readlink -f /root/rag-stack/qdrant_data 2>/dev/null)/collections"
if [ ! -f /var/log/rag/acl_bloques.json ]; then
    if [ "$INSTALLATION_EXISTANTE" = "oui" ] || [ -n "$(ls -A "$QDRANT_COLLECTIONS" 2>/dev/null)" ]; then
        echo -e "${RED}[ERREUR]${NC} Installation existante sans /var/log/rag/acl_bloques.json :"
        echo "  le registre des documents retirés de la recherche a disparu. Ne pas en créer un vide."
        echo "  Redémarrer la stack existante (cd /root/rag-stack && docker compose up -d), puis lancer"
        echo "  une synchronisation complète : elle reconstruit le registre (§16.5.2)."
        exit 1
    fi
    echo "{\"version\": 3, \"smb\": [], \"sharepoint\": [], \"prefixes\": [], \"smb_tout\": false, \"sharepoint_tout\": false, \"incertain\": {\"smb\": false, \"sharepoint\": false}, \"derniere_synchro_complete\": \"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)\"}" > /var/log/rag/acl_bloques.json
    chmod 640 /var/log/rag/acl_bloques.json
fi
mkdir -p /etc/smbcredentials
# Certificats des applications Microsoft 365 (Partie 3, §11 et §12).
# Monté en lecture seule dans rag-api : créé ici avec des droits restreints,
# sinon Docker le créerait au démarrage avec des droits par défaut.
mkdir -p /etc/rag-certs
chmod 700 /etc/rag-certs
# Certificat et clé de Nginx (§9.8) : sur le disque chiffré quand il est prêt,
# comme les autres secrets (§15.3.6), avec un lien depuis /etc/rag-tls.
if [ ! -e /etc/rag-tls ]; then
    if mountpoint -q /srv/rag-donnees 2>/dev/null; then
        mkdir -p /srv/rag-donnees/secrets/rag-tls
        chmod 700 /srv/rag-donnees/secrets /srv/rag-donnees/secrets/rag-tls
        ln -s /srv/rag-donnees/secrets/rag-tls /etc/rag-tls
    else
        mkdir -p /etc/rag-tls
    fi
fi
chmod 700 "$(readlink -f /etc/rag-tls)"

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
# Configuration de Nginx, avec le nom de la stack
mkdir -p /root/rag-stack/nginx
sed "s/<NOM-STACK>/${RAG_FQDN}/g" nginx/rag.conf > /root/rag-stack/nginx/rag.conf

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
# Tests unitaires du contrôle des citations et des droits sur la recherche par
# mots-clés (lancés à l'étape 10), test en lab d'un droit retiré (§16.5.1)
# Les tests de sécurité sont exigés dans le dépôt (2.21.8 ; test_citations.py,
# qui contrôle aussi la lecture du verdict du juge, depuis la 2.21.10) : sinon,
# une ancienne copie restée dans /root/rag-pipeline serait lancée à leur place.
for f in test_citations.py test_sid.py test_revalidation_bm25.py test_echec_droits.py; do
    if [ ! -f "$f" ]; then
        echo -e "${RED}[ERREUR]${NC} Test de sécurité $f absent du dépôt ($(pwd)) : déploiement arrêté (§16.5)."
        exit 1
    fi
done
for f in test_citations.py test_sid.py test_revalidation_bm25.py test_revocation_bm25.py test_echec_droits.py; do
    [ -f "$f" ] && cp "$f" "/root/rag-pipeline/$f"
done
for f in test_citations.py test_sid.py test_revalidation_bm25.py test_echec_droits.py; do
    if ! cmp -s "$f" "/root/rag-pipeline/$f"; then
        echo -e "${RED}[ERREUR]${NC} /root/rag-pipeline/$f diffère de la version du dépôt : déploiement arrêté (§16.5)."
        exit 1
    fi
done
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
DOCUMENTATION_PATHS='${DOCUMENTATION_PATHS}'

# Tokens d'authentification
API_TOKEN=${API_TOKEN}
ADMIN_TOKEN=${ADMIN_TOKEN}
# Identité des utilisateurs signée par Open WebUI, vérifiée par la RAG API
OWUI_JWT_SECRET=${OWUI_JWT_SECRET}

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

# Nom de la stack (§9.8) : certificat de Nginx, adresse annoncée par n8n
RAG_FQDN=${RAG_FQDN}
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
# Étape 6b : certificat de la stack (Nginx, §9.8)
# ─────────────────────────────────────────
info "Étape 6b : certificat de la stack (${RAG_FQDN})..."

CRT=/etc/rag-tls/rag.crt
KEY=/etc/rag-tls/rag.key
if [ -s "$CRT" ] && [ -s "$KEY" ]; then
    # Certificat fourni (autorité interne) : contrôles, sans le modifier
    EMPREINTE_CRT=$(openssl x509 -in "$CRT" -noout -pubkey 2>/dev/null | sha256sum | cut -d' ' -f1)
    EMPREINTE_KEY=$(openssl pkey -in "$KEY" -pubout 2>/dev/null | sha256sum | cut -d' ' -f1)
    [ "$EMPREINTE_CRT" = "$EMPREINTE_KEY" ] \
        || error "rag.crt et rag.key ne correspondent pas (/etc/rag-tls). Voir §9.8.4."
    openssl x509 -in "$CRT" -noout -ext subjectAltName 2>/dev/null | grep -q "DNS:${RAG_FQDN}" \
        || warn "Le certificat fourni ne porte pas le nom ${RAG_FQDN} : le navigateur affichera un avertissement."
    openssl x509 -in "$CRT" -noout -checkend 2592000 >/dev/null \
        || warn "Le certificat fourni expire dans moins de 30 jours : le renouveler (§9.8.6)."
    # Émetteur identique au sujet : certificat auto-signé (déploiement précédent)
    if [ "$(openssl x509 -in "$CRT" -noout -issuer | sed 's/^issuer=//')" = "$(openssl x509 -in "$CRT" -noout -subject | sed 's/^subject=//')" ]; then
        CERT_AUTOSIGNE=oui
        warn "Certificat existant conservé, mais AUTO-SIGNÉ : le remplacer pour la production (§9.8.6)."
    else
        CERT_AUTOSIGNE=non
        ok "Certificat fourni utilisé : $(openssl x509 -in "$CRT" -noout -issuer | sed 's/^issuer=//')"
    fi
else
    # Aucun certificat : auto-signé, pour un essai. Les connexions sont chiffrées,
    # mais le navigateur affichera un avertissement jusqu'à son remplacement.
    openssl req -x509 -newkey rsa:3072 -nodes -days 825 \
        -keyout "$KEY" -out "$CRT" \
        -subj "/CN=${RAG_FQDN}" -addext "subjectAltName=DNS:${RAG_FQDN}" >/dev/null 2>&1 \
        || error "Génération du certificat auto-signé échouée."
    chmod 600 "$KEY"
    warn "Aucun certificat fourni : certificat AUTO-SIGNÉ généré pour ${RAG_FQDN}."
    warn "Les navigateurs afficheront un avertissement. Pour la production, le remplacer"
    warn "par un certificat de l'autorité interne (§9.8.4, §9.8.6), sans redéployer."
    CERT_AUTOSIGNE=oui
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

# Le corpus n'est jamais écrit par la stack : lecture seule (ro). Un montage déjà
# fait à la main en écriture (rw) fonctionne, mais donne plus de droits que nécessaire.
if findmnt -no OPTIONS "$SMB_MOUNT" 2>/dev/null | grep -qE '(^|,)rw(,|$)'; then
    warn "$SMB_MOUNT est monté en écriture (rw). La stack n'écrit jamais sur le partage :"
    warn "passer l'option rw en ro dans /etc/fstab, puis umount $SMB_MOUNT && mount $SMB_MOUNT."
fi

# Dossiers de documentation : présents à la racine du partage ?
if [[ -n "$DOCUMENTATION_PATHS" ]] && mountpoint -q "$SMB_MOUNT"; then
    IFS=',' read -ra DOSSIERS_DOC <<< "$DOCUMENTATION_PATHS"
    for d in "${DOSSIERS_DOC[@]}"; do
        if [ -d "$SMB_MOUNT/$d" ]; then
            ok "Dossier de documentation présent : $d"
        else
            warn "Dossier de documentation « $d » absent de la racine du partage : la collection documentation restera vide."
        fi
    done
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
# --retries et --timeout : une coupure passagère vers pypi.org faisait échouer le
# déploiement (rejeu en lab). Le script reste relançable après une erreur.
pip install -q --retries 10 --timeout 60 qdrant-client python-docx pdfplumber python-pptx httpx \
    ldap3 impacket rank-bm25 smbprotocol \
    || error "Installation des paquets Python échouée (réseau vers pypi.org ?). Relancer deploy.sh : il reprend sans dommage. Ne pas ajouter de DNS public pour contourner (§0, « En cas de problème »)."

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

# Les cinq conteneurs doivent tourner, sans redémarrage. Un conteneur qui plante
# au démarrage (n8n sans droits sur son dossier, par exemple) redémarre en boucle
# sans que « docker compose up -d » le signale.
sleep 20
for C in qdrant rag-api open-webui n8n nginx; do
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

# Accès par Nginx, sous le nom de la stack, sans dépendre du DNS (--resolve) :
# la RAG API doit répondre par l'adresse de santé de la supervision (§16.10).
SANTE=$(curl -sk -m 10 --resolve "${RAG_FQDN}:443:127.0.0.1" "https://${RAG_FQDN}/sante" 2>/dev/null || echo "")
if echo "$SANTE" | grep -q '"status":"ok"'; then
    ok "Accès HTTPS par Nginx : https://${RAG_FQDN}/sante répond"
else
    PROBLEMES="${PROBLEMES}  - Nginx : https://${RAG_FQDN}/sante sans réponse (docker logs nginx --tail 30)\n"
fi
# -k ci-dessus ne vérifie pas le certificat. Certificat de l'autorité interne :
# contrôle complet avec la chaîne de l'autorité, comme le ferait un poste client.
if [ "$CERT_AUTOSIGNE" = "non" ] && [ -s /etc/ssl/certs/ad-chain.pem ]; then
    if curl -s -m 10 --cacert /etc/ssl/certs/ad-chain.pem --resolve "${RAG_FQDN}:443:127.0.0.1" \
            "https://${RAG_FQDN}/sante" 2>/dev/null | grep -q '"status":"ok"'; then
        ok "Certificat de la stack vérifié avec la chaîne de l'autorité interne"
    else
        warn "Certificat de la stack NON vérifiable avec /etc/ssl/certs/ad-chain.pem : chaîne incomplète ou autre autorité (§9.8.4)"
    fi
fi

# Tests de sécurité (§16.5.1, §16.5.2) : obligatoires (2.21.5) ; contrôle des
# citations et lecture du verdict du juge (test_citations.py) depuis la 2.21.10 ;
# contrôle d'accès par SID (test_sid.py) depuis la 2.22.0.
# Absent ou en échec : la RAG API est arrêtée, pour qu'aucune question ne soit
# servie par un code non vérifié, et le déploiement se termine en erreur.
# Rien n'est supprimé : corriger, puis redémarrer la RAG API.
ECHEC_SECURITE=0
for t in test_citations.py test_sid.py test_revalidation_bm25.py test_echec_droits.py; do
    if [ ! -f "/root/rag-pipeline/$t" ]; then
        ECHEC_SECURITE=1
        PROBLEMES="${PROBLEMES}  - Test de sécurité $t ABSENT de /root/rag-pipeline (copier le fichier du dépôt ; §16.5)\n"
    elif docker exec -w /app rag-api python3 "/rag-pipeline/$t" >/dev/null 2>&1; then
        ok "Test de sécurité $t : OK"
    else
        ECHEC_SECURITE=1
        PROBLEMES="${PROBLEMES}  - Test de sécurité $t en ÉCHEC (détail : docker exec -w /app rag-api python3 /rag-pipeline/$t ; §16.5)\n"
    fi
done
if [ "$ECHEC_SECURITE" = 1 ]; then
    ( cd /root/rag-stack && docker compose stop rag-api ) >/dev/null 2>&1
    PROBLEMES="${PROBLEMES}  - RAG API ARRÊTÉE à cause du test de sécurité ci-dessus ; après correction : cd /root/rag-stack && docker compose start rag-api\n"
fi

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
# Étape 11 (facultative) : première indexation et droits d'accès
# ─────────────────────────────────────────
# Facultative : un échec ici ne remet pas en cause le déploiement, qui est
# terminé. Les commandes manuelles restent au §0 (étapes 12 et 13).
INDEXATION_FAITE=non
echo ""
ask "Lancer maintenant la première indexation et la résolution des droits ? [o/N]"
echo "    (de quelques minutes à plus d'une heure selon le volume du partage)"
read -r LANCER_INDEXATION
if est_oui "$LANCER_INDEXATION"; then
    if ! mountpoint -q "$SMB_MOUNT"; then
        warn "Partage non monté sur $SMB_MOUNT : indexation non lancée (§0, étape 5)."
    else
        HORODATAGE=$(date '+%Y%m%d_%H%M%S')
        JOURNAL="/var/log/rag/deploy_indexation_${HORODATAGE}.log"
        info "Indexation en cours, journal : ${JOURNAL}"
        if ( cd /root/rag-pipeline && source .venv/bin/activate \
             && set -a && source /root/rag-stack/.env && set +a \
             && python indexer.py --corpus "$SMB_MOUNT" \
                    --rapport "/var/log/rag/rapport_indexation_initial_${HORODATAGE}.json" ) >>"$JOURNAL" 2>&1; then
            ok "Indexation terminée"
            info "Résolution des droits d'accès..."
            if ( cd /root/rag-pipeline && source .venv/bin/activate \
                 && set -a && source /root/rag-stack/.env && set +a \
                 && python acl_resolver.py --share "$SMB_SHARE" --mount "$SMB_MOUNT" \
                        --rapport "/var/log/rag/rapport_acl_initial_${HORODATAGE}.json" ) >>"$JOURNAL" 2>&1; then
                ok "Droits d'accès recopiés dans l'index"
                INDEXATION_FAITE=oui
            else
                warn "Résolution des droits en échec : voir ${JOURNAL} (fin du fichier)."
                warn "Tant qu'elle n'a pas réussi, les documents restent invisibles pour tous (refus par défaut)."
            fi
        else
            warn "Indexation en échec : voir ${JOURNAL} (fin du fichier). Le déploiement lui-même est terminé."
        fi
        chmod 640 "$JOURNAL" 2>/dev/null || true
    fi
fi

# ─────────────────────────────────────────
# Résumé final
# ─────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Déploiement terminé"
echo "============================================================"
echo ""
echo "  Open WebUI   : https://${RAG_FQDN}"
echo "  n8n          : https://${RAG_FQDN}:5678"
if [ "$CERT_AUTOSIGNE" = "oui" ]; then
    echo "  Certificat   : AUTO-SIGNÉ (avertissement du navigateur). Remplacement : §9.8.6"
else
    echo "  Certificat   : fourni ($(openssl x509 -in /etc/rag-tls/rag.crt -noout -enddate | sed 's/notAfter=/échéance /'))"
fi
echo "  Supervision  : https://${RAG_FQDN}/sante (§16.10)"
echo "  Logs nLPD    : /var/log/rag/rag-queries.jsonl"
echo "  Tokens       : /root/rag-stack/.env (chmod 600)"
echo ""
echo "  Partie 3 (Microsoft 365) : inactive par défaut."
echo "    Extension Entra ID     : ENTRA_* dans le .env, voir §11 du guide"
echo "    Synthèse Teams         : TEAMS_* dans le .env, voir §12 du guide"
echo ""
echo "  Étapes suivantes :"
echo "  0. TOUT DE SUITE : ouvrir https://${RAG_FQDN}:5678 et créer le compte propriétaire"
echo "     de n8n (§7.1.1). Tant qu'il n'existe pas, n'importe quel poste peut le créer."
echo "  1. Configurer Open WebUI (§0, étape 14) : connexion à la RAG API dans la section"
echo "     API compatibles OpenAI, authentification LDAP (« Attribut pour l'e-mail » :"
echo "     userPrincipalName ; « Attribut pour le nom d'utilisateur » : sAMAccountName),"
echo "     puis vérifier que la génération de titre, d'étiquettes et de questions de suivi"
echo "     est désactivée (le Compose le fait au premier démarrage ; sinon : réglages"
echo "     d'administration, Interface, et enregistrer). Sans cela, chaque question en"
echo "     déclenche d'autres."
if [ "$INDEXATION_FAITE" = "oui" ]; then
    echo "  2. Indexation et droits : faits (journal : ${JOURNAL})."
    echo "     Contrôler les extraits indexés : §0, étape 12."
    N=3
else
    echo "  2. Lancer la première indexation (§0, étape 12) :"
    echo "     cd /root/rag-pipeline && source .venv/bin/activate"
    echo "     set -a && source /root/rag-stack/.env && set +a"
    echo "     python indexer.py --corpus ${SMB_MOUNT} --rapport /var/log/rag/rapport_indexation_initial.json"
    echo "  3. Lancer la résolution des droits (§0, étape 13) :"
    echo "     python acl_resolver.py --share ${SMB_SHARE} --mount ${SMB_MOUNT} --rapport /var/log/rag/rapport_acl_initial.json"
    N=4
fi
echo "  ${N}. Configurer n8n (§0, étape 15, https://${RAG_FQDN}:5678), compte propriétaire créé :"
echo "     a. Créer l'identifiant Header Auth « RAG API - ADMIN_TOKEN »"
echo "        (Name : Authorization ; Value : Bearer <ADMIN_TOKEN du .env> ;"
echo "        domaine autorisé : rag-api), puis l'identifiant SMTP."
echo "     b. Importer scripts/N8N/n8n-sync-corpus.json et n8n-rappel-rotation-svc-rag.json."
echo "     c. Dans CHAQUE nœud HTTP et courriel, sélectionner à nouveau l'identifiant :"
echo "        ceux du fichier importé ne correspondent à rien chez vous."
echo "     d. Renseigner les adresses : expéditeur = la boîte authentifiée par SMTP,"
echo "        destinataire = une boîte interne."
echo "     e. Publier les deux workflows, puis lancer une exécution manuelle."
echo "        Sans synchronisation complète pendant 3 h (ACL_AGE_MAX_HEURES), la RAG API refuse"
echo "        les questions (droits trop anciens, §16.5.2) : configurer n8n sans tarder."
echo "     f. Facultatif, après le §12 : importer scripts/N8N/n8n-teams-sync.json."
echo "  $((N + 1)). Contrôles finaux (§0, étape 16), puis snapshot de la VM arrêtée et snapshot"
echo "     Qdrant (§3.7)."
echo ""
echo "  Consulter /root/rag-stack/.env pour les tokens générés."
echo "============================================================"
