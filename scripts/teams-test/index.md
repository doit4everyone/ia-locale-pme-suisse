---
title: "Tests de la synthèse Teams | IA locale pour PME suisse | DoIt4Everyone"
description: "Fichiers et scripts de test de la synthèse des réunions Teams."
---

<style>
  header, footer { display: none !important; }
  .wrapper { max-width: 900px !important; margin: 0 auto !important; float: none !important; position: relative !important; padding: 40px 20px !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; font-size: 1.1em !important; }
  section { width: 100% !important; float: none !important; margin: 0 !important; }
  h1, h2, h3 { text-align: center; }
  table { width: 100%; display: table; margin: 20px 0; }
  code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.95em; }
</style>

# Tests de la synthèse Teams

[Retour aux scripts](../) | [§12 Synthèse des réunions Teams](../../docs/stack-ia-locale/section-12-teams.html)

| Fichier | Rôle |
|---|---|
| [reunion-test-2026-09-29.vtt](reunion-test-2026-09-29.vtt) | Transcription fictive à quatre intervenants, au format Teams |
| [corrige-reunion-test.md](corrige-reunion-test.md) | Corrigé et grille sur 14 points de la transcription fictive |
| [script-reunion-live.md](script-reunion-live.md) | Script de réunion à lire à deux, avec son corrigé sur 13 points |
| [test_teams_summary.py](test_teams_summary.py) | Envoie une transcription à `/teams/summarize` et contrôle le compte-rendu |
| [test_teams_graph.py](test_teams_graph.py) | Vérifie la chaîne Graph : jeton, groupe, transcriptions, contenu |

Fichiers de test uniquement : ils ne sont pas nécessaires au fonctionnement du pipeline (voir §12.7).

---

ℹ️ *Références, structuration et aide à la rédaction assistées par IA, avec validation humaine finale.*
