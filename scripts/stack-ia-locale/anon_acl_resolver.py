"""
acl_resolver.py : lecture des ACL NTFS depuis un partage SMB
et mise à jour du payload Qdrant avec la liste des groupes autorisés.

Ce script est distinct de indexer.py et tourne séparément, typiquement
toutes les heures, parce que les permissions peuvent changer sans que
le contenu des fichiers ne change. Les deux synchronisations sont indépendantes.

Architecture :
  smbcacls → groupes AD autorisés → SIDs → payload Qdrant (autorisés[])

Le champ autorisés[] est une donnée CONSTATÉE (lu depuis les ACL réelles),
contrairement à org_name qui est une donnée déduite. C'est autorisés[] qui
sert au cloisonnement dans auth.py. org_name ne sert qu'à la navigation.

Usage :
  python acl_resolver.py --share //<NOM-FILESERVER>/CLIENTS --mount /mnt/fileservice
  python acl_resolver.py --share //<NOM-FILESERVER>/CLIENTS --mount /mnt/fileservice --dry-run

Variables d'environnement :
  SMB_USER       : compte AD avec accès lecture des ACL (ex: svc-rag)
  SMB_PASSWORD   : mot de passe du compte
  SMB_DOMAIN     : domaine AD (ex: VOTRE-DOMAINE)
  QDRANT_URL     : URL Qdrant
  COLLECTION     : nom de la collection Qdrant

Validé sur VM-RAG-LAB avec <NOM-FILESERVER> (VOTRE-DOMAINE.CH), septembre 2026
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# ─────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────

SMB_USER     = os.getenv("SMB_USER",     "administrateur")
SMB_PASSWORD = os.getenv("SMB_PASSWORD", "")
SMB_DOMAIN   = os.getenv("SMB_DOMAIN",   "VOTRE-DOMAINE")
QDRANT_URL   = os.getenv("QDRANT_URL",   "http://localhost:6333")
COLLECTION   = os.getenv("QDRANT_COLLECTION", "documents")
DOCUMENTATION_COLLECTION = os.getenv("DOCUMENTATION_COLLECTION", "documentation")
DOCUMENTATION_PATHS = [
    p.strip() for p in
    os.getenv("DOCUMENTATION_PATHS", "DOIT4EVERYONE").split(",")
    if p.strip()
]

# Groupes à exclure des autorisés[] : comptes système, pas des utilisateurs métier
GROUPES_EXCLUS = {
    "autorite nt\\système",
    "autorite nt\\system",
    "nt authority\\system",
    "builtin\\administrateurs",
    "builtin\\administrators",
}

# ─────────────────────────────────────────
# Lecture des ACL via smbcacls
# ─────────────────────────────────────────

def lire_acl_fichier(share: str, chemin_relatif: str) -> tuple[list[str], list[str]]:
    """
    Lit les ACL d'un fichier via smbcacls.
    Retourne (autorisés, interdits) : deux listes de groupes/utilisateurs.

    En NTFS, un DENY explicite surpasse toujours un ALLOW.
    Les deux listes sont nécessaires pour le cloisonnement dans auth.py :
      accès accordé si : (user_groups ∩ autorisés != ∅) AND (user_groups ∩ interdits == ∅)

    Le /I indique une règle héritée. On prend toutes les règles ALLOWED et DENIED.
    """
    cmd = [
        "smbcacls",
        share,
        chemin_relatif,
        "-U", SMB_USER,
        "-W", SMB_DOMAIN,
        f"--password={SMB_PASSWORD}",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(f"  Erreur smbcacls sur '{chemin_relatif}' : {result.stderr.strip()}")
            return []

        autorisés = []
        interdits = []
        for line in result.stdout.splitlines():
            # Règles ALLOWED
            m = re.match(r'^ACL:(.+):ALLOWED/', line, re.IGNORECASE)
            if m:
                identite = m.group(1).strip()
                if identite.lower() not in GROUPES_EXCLUS:
                    autorisés.append(identite)
                continue
            # Règles DENIED : prioritaires sur ALLOWED en NTFS
            m = re.match(r'^ACL:(.+):DENIED/', line, re.IGNORECASE)
            if m:
                identite = m.group(1).strip()
                if identite.lower() not in GROUPES_EXCLUS:
                    interdits.append(identite)

        return autorisés, interdits

    except subprocess.TimeoutExpired:
        print(f"  Timeout smbcacls sur '{chemin_relatif}'")
        return [], []
    except Exception as e:
        print(f"  Erreur inattendue smbcacls : {e}")
        return [], []


def lister_fichiers_montes(mount_point: str) -> list[tuple[str, str]]:
    """
    Liste récursivement les fichiers depuis le point de montage.
    Retourne une liste de (chemin_relatif_smb, chemin_absolu_local).

    Le chemin relatif SMB utilise des backslashes (format Windows).
    """
    supported = ('.docx', '.txt', '.md', '.pdf', '.xlsx')
    fichiers = []

    for root, dirs, files in os.walk(mount_point):
        for f in sorted(files):
            ext = os.path.splitext(f)[1].lower()
            if ext not in supported:
                continue
            # Chemin absolu local
            chemin_local = os.path.join(root, f)
            # Chemin relatif depuis le point de montage, en backslash pour SMB
            chemin_relatif = os.path.relpath(chemin_local, mount_point)
            chemin_smb = chemin_relatif.replace('/', '\\')
            fichiers.append((chemin_smb, chemin_local))

    return fichiers


# ─────────────────────────────────────────
# Mise à jour Qdrant
# ─────────────────────────────────────────

def get_collection_for_path(source_name: str) -> str:
    """Retourne la collection Qdrant pour ce fichier."""
    for prefix in DOCUMENTATION_PATHS:
        if source_name.startswith(prefix + "/") or source_name.startswith(prefix + "\\"):
            return DOCUMENTATION_COLLECTION
    return COLLECTION


def mettre_a_jour_qdrant(
    qdrant: QdrantClient,
    source_name: str,
    collection_name: str,
    autorisés: list[str],
    interdits: list[str],
    dry_run: bool = False
) -> int:
    """
    Met à jour le champ autorisés[] dans le payload de tous les chunks
    dont le champ source correspond à source_name.
    Retourne le nombre de chunks mis à jour.
    """
    try:
        # Chercher TOUS les chunks du document par pagination
        # limit=100 raterait les documents de plus de 100 chunks
        all_points = []
        next_offset = None
        while True:
            batch, next_offset = qdrant.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(must=[
                    FieldCondition(key="source", match=MatchValue(value=source_name))
                ]),
                limit=100,
                offset=next_offset,
                with_payload=True
            )
            all_points.extend(batch)
            if next_offset is None:
                break
        points = all_points

        if not points:
            return 0

        if dry_run:
            print(f"    [DRY-RUN] {len(points)} chunks")
            print(f"      autorisés  : {autorisés}")
            if interdits:
                print(f"      interdits  : {interdits}")
            return len(points)

        # Mettre à jour le payload de chaque chunk
        ids = [p.id for p in points]
        payload = {
            "autorises": autorisés,
            "acl_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if interdits:
            payload["interdits"] = interdits
        qdrant.set_payload(
            collection_name=collection_name,
            payload=payload,
            points=ids
        )
        return len(points)

    except Exception as e:
        print(f"  Erreur Qdrant sur '{source_name}' : {e}")
        return 0


# ─────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────

def resoudre_acl(
    share: str,
    mount_point: str,
    dry_run: bool = False,
    rapport_path: str = ""
):
    """
    Pipeline complet :
    1. Lister les fichiers depuis le point de montage
    2. Lire les ACL via smbcacls pour chaque fichier
    3. Mettre à jour autorisés[] dans Qdrant
    """
    print(f"Partage SMB  : {share}")
    print(f"Point montage: {mount_point}")
    print(f"Qdrant       : {QDRANT_URL}")
    print(f"Collection   : {COLLECTION}")
    print(f"Compte SMB   : {SMB_DOMAIN}\\{SMB_USER}")
    if dry_run:
        print("Mode         : DRY-RUN (aucune écriture Qdrant)")
    print()

    # Connexion Qdrant
    qdrant = QdrantClient(url=QDRANT_URL)
    try:
        collections = [c.name for c in qdrant.get_collections().collections]
        for col in [COLLECTION, DOCUMENTATION_COLLECTION]:
            if col not in collections:
                print(f"Avertissement : collection '{col}' absente (sera ignorée).")
    except Exception as e:
        print(f"Erreur connexion Qdrant : {e}")
        sys.exit(1)

    # Lister les fichiers
    fichiers = lister_fichiers_montes(mount_point)
    if not fichiers:
        print(f"Aucun fichier supporté trouvé dans {mount_point}")
        sys.exit(1)

    print(f"{len(fichiers)} fichiers à traiter :\n")

    rapport = []
    total_chunks_mis_a_jour = 0
    fichiers_sans_chunks = []
    fichiers_sans_acl = []

    for i, (chemin_smb, chemin_local) in enumerate(fichiers, 1):
        # source_name doit correspondre exactement au champ "source" dans Qdrant,
        # qui est le chemin relatif depuis le corpus (= depuis le point de montage).
        # os.path.basename() ne fonctionnerait que pour les fichiers à la racine.
        source_name = os.path.relpath(chemin_local, mount_point).replace('\\', '/')
        print(f"  [{i}/{len(fichiers)}] {chemin_smb}")

        # Lire les ACL
        autorisés, interdits = lire_acl_fichier(share, chemin_smb)
        if not autorisés and not interdits:
            print(f"  → Aucune ACL lisible, fichier ignoré.")
            fichiers_sans_acl.append(chemin_smb)
            rapport.append({
                "fichier": chemin_smb,
                "statut": "acl_illisible",
                "autorises": [],
                "interdits": []
            })
            continue

        print(f"  Autorisés ({len(autorisés)}) : {', '.join(autorisés)}")
        if interdits:
            print(f"  Interdits ({len(interdits)}) : {', '.join(interdits)}")

        # Mettre à jour Qdrant
        col = get_collection_for_path(source_name)
        nb = mettre_a_jour_qdrant(qdrant, source_name, col, autorisés, interdits, dry_run)
        if nb == 0:
            print(f"  → Aucun chunk trouvé dans Qdrant pour '{source_name}'")
            fichiers_sans_chunks.append(source_name)
            statut = "non_indexé"
        else:
            print(f"  → {nb} chunks mis à jour")
            total_chunks_mis_a_jour += nb
            statut = "mis_à_jour"

        rapport.append({
            "fichier": chemin_smb,
            "source_name": source_name,
            "statut": statut,
            "autorises": autorisés,
            "interdits": interdits,
            "chunks_mis_a_jour": nb
        })

    # Résumé
    print(f"\n{'='*60}")
    print(f"RAPPORT ACL RESOLVER")
    print(f"{'='*60}")
    print(f"Fichiers traités        : {len(fichiers)}")
    print(f"Chunks mis à jour       : {total_chunks_mis_a_jour}")
    print(f"Fichiers sans ACL       : {len(fichiers_sans_acl)}")
    print(f"Fichiers non indexés    : {len(fichiers_sans_chunks)}")

    if fichiers_sans_chunks:
        print(f"\nFichiers présents sur le partage mais absents de Qdrant :")
        print("  (à indexer avec indexer.py)")
        for f in fichiers_sans_chunks:
            print(f"  {f}")

    if fichiers_sans_acl:
        print(f"\nFichiers sans ACL lisible :")
        for f in fichiers_sans_acl:
            print(f"  {f}")

    # ── Détection et suppression des chunks orphelins ─────────────────────
    # Un chunk orphelin est présent dans Qdrant mais absent du partage SMB.
    # Causes : fichier supprimé, déplacé, ou renommé sur le file server.
    # Sans cette étape, les chunks orphelins restent interrogeables indéfiniment.

    print(f"\n{'='*60}")
    print(f"NETTOYAGE DES CHUNKS ORPHELINS")
    print(f"{'='*60}")

    # Construire la liste des source_names présents sur le partage
    sources_partage = set()
    for _, chemin_local in fichiers:
        source_name = os.path.relpath(chemin_local, mount_point).replace('\\', '/')
        sources_partage.add(source_name)

    # Récupérer tous les source_names présents dans les deux collections
    sources_qdrant = set()
    for col in [COLLECTION, DOCUMENTATION_COLLECTION]:
        next_offset = None
        while True:
            try:
                batch, next_offset = qdrant.scroll(
                    collection_name=col,
                    limit=100,
                    offset=next_offset,
                    with_payload=["source"]
                )
                for point in batch:
                    src = point.payload.get("source", "")
                    if src:
                        sources_qdrant.add(src)
                if next_offset is None:
                    break
            except Exception:
                break

    # Orphelins : dans Qdrant mais absents du partage
    orphelins = sources_qdrant - sources_partage

    if not orphelins:
        print("Aucun chunk orphelin détecté.")
    else:
        print(f"{len(orphelins)} source(s) orpheline(s) détectée(s) :")
        for src in sorted(orphelins):
            print(f"  {src}")

        if not dry_run:
            nb_supprimes = 0
            for src in orphelins:
                try:
                    # Compter les chunks avant suppression
                    col_src = get_collection_for_path(src)
                    points_orphelins, _ = qdrant.scroll(
                        collection_name=col_src,
                        scroll_filter=Filter(must=[
                            FieldCondition(key="source", match=MatchValue(value=src))
                        ]),
                        limit=500,
                        with_payload=False
                    )
                    ids_a_supprimer = [p.id for p in points_orphelins]
                    if ids_a_supprimer:
                        qdrant.delete(
                            collection_name=col_src,
                            points_selector=ids_a_supprimer
                        )
                        nb_supprimes += len(ids_a_supprimer)
                        print(f"  → {len(ids_a_supprimer)} chunks supprimés : {src}")
                except Exception as e:
                    print(f"  Erreur suppression '{src}' : {e}")
            print(f"\nTotal chunks orphelins supprimés : {nb_supprimes}")
        else:
            print("  [DRY-RUN] Aucune suppression effectuée.")

    # Sauvegarder le rapport.
    # Si --rapport n'est pas fourni, le rapport est écrit à côté du script.
    # Depuis le conteneur rag-api, /rag-pipeline est monté en lecture seule :
    # admin_sync passe explicitement --rapport /var/log/rag/rapport_acl.json.
    if not rapport_path:
        rapport_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"rapport_acl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
    os.makedirs(os.path.dirname(os.path.abspath(rapport_path)), exist_ok=True)
    with open(rapport_path, 'w', encoding='utf-8') as f:
        json.dump({
            "date": datetime.now(timezone.utc).isoformat(),
            "share": share,
            "collections": [COLLECTION, DOCUMENTATION_COLLECTION],
            "dry_run": dry_run,
            "statistiques": {
                "fichiers_traités": len(fichiers),
                "chunks_mis_à_jour": total_chunks_mis_a_jour,
                "fichiers_sans_acl": len(fichiers_sans_acl),
                "fichiers_non_indexés": len(fichiers_sans_chunks),
                "sources_orphelines": len(orphelins),
            },
            "documents": rapport,
            "orphelins": sorted(orphelins),
        }, f, ensure_ascii=False, indent=2)
    print(f"\nRapport sauvegardé : {rapport_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Résolveur d'ACL NTFS SMB vers Qdrant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  # Tester sans écrire dans Qdrant
  SMB_PASSWORD=xxx python acl_resolver.py \\
    --share //<NOM-FILESERVER>/CLIENTS --mount /mnt/fileservice --dry-run

  # Exécution réelle
  SMB_PASSWORD=xxx python acl_resolver.py \\
    --share //<NOM-FILESERVER>/CLIENTS --mount /mnt/fileservice

Variables d'environnement :
  SMB_USER       Compte AD (défaut: administrateur)
  SMB_PASSWORD   Mot de passe (requis)
  SMB_DOMAIN     Domaine AD (défaut: VOTRE-DOMAINE)
  QDRANT_URL     URL Qdrant (défaut: http://localhost:6333)
        """
    )
    parser.add_argument("--share",    required=True, help="Partage SMB (ex: //<NOM-FILESERVER>/CLIENTS)")
    parser.add_argument("--mount",    required=True, help="Point de montage local")
    parser.add_argument("--dry-run",  action="store_true", help="Simuler sans écrire dans Qdrant")
    parser.add_argument("--rapport",  default="",    help="Chemin du rapport JSON (défaut : dossier du script)")
    args = parser.parse_args()

    if not SMB_PASSWORD:
        import getpass
        SMB_PASSWORD = getpass.getpass(f"Mot de passe pour {SMB_DOMAIN}\\{SMB_USER} : ")

    resoudre_acl(args.share, args.mount, dry_run=args.dry_run, rapport_path=args.rapport)
