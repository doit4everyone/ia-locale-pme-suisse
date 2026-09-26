"""
test_teams_graph.py : vérification de l'accès Graph aux transcriptions,
sans synthèse ni envoi d'email.

À exécuter DANS le conteneur rag-api :
  docker exec rag-api python3 /rag-pipeline/test_teams_graph.py

Étapes testées, dans l'ordre :
  1. Jeton de RAG-Teams-Reader (certificat, empreinte, ID client)
  2. Membres du groupe d'adhésion (RAG-Identity-Resolver, GroupMember.Read.All)
  3. getAllTranscripts pour chaque membre (permission + stratégie d'accès
     applicatif + Transcript API access)
  4. Téléchargement du VTT le plus récent (attribution des intervenants)
Le contenu des transcriptions n'est pas affiché en entier : seulement
les premières répliques, pour vérifier le format.
"""
import teams
import teams_graph as tg

print("1. Configuration et jeton RAG-Teams-Reader")
tg.verifier_configuration()
jeton = tg._jeton_teams()
print("   OK\n")

print("2. Membres du groupe d'adhésion")
membres = tg.membres_groupe()
for m in membres:
    print(f"   - {m.get('displayName')} ({m.get('userPrincipalName')})")
print(f"   {len(membres)} membre(s)\n")

print(f"3. Transcriptions des {tg.LOOKBACK_HOURS} dernières heures")
etat = tg.charger_etat()
plus_recente = None
for m in membres:
    try:
        liste = tg.transcriptions_recentes(m["id"], jeton)
    except Exception as e:
        print(f"   {m.get('userPrincipalName')} : ÉCHEC {e}")
        continue
    print(f"   {m.get('userPrincipalName')} : {len(liste)} transcription(s)")
    for t in liste:
        deja = "déjà traitée" if t["id"] in etat else "nouvelle"
        print(f"     {tg.date_locale(t.get('createdDateTime', ''))}  {deja}")
        if not plus_recente or t.get("createdDateTime", "") > plus_recente.get("createdDateTime", ""):
            plus_recente = t
print()

print("4. Contenu de la transcription la plus récente")
if not plus_recente:
    print("   Aucune transcription dans la fenêtre. Élargir TEAMS_LOOKBACK_HOURS ou tenir une réunion planifiée.")
else:
    vtt = tg.telecharger_vtt(plus_recente, jeton)
    if vtt is None:
        print("   Contenu pas encore disponible (404) : réessayer plus tard.")
    else:
        rep = teams.parse_vtt(vtt)
        print(f"   {len(vtt)} caractères, {len(rep)} répliques, intervenants : {teams.participants(rep)}")
        sans_nom = sum(1 for n, _ in rep if n == "Inconnu")
        if sans_nom:
            print(f"   ATTENTION : {sans_nom} réplique(s) sans intervenant (attribution désactivée ?)")
        for nom, texte in rep[:4]:
            print(f"   {nom} : {texte[:90]}")
