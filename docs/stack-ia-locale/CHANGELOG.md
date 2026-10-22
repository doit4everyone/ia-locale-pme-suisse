# Changelog

Toutes les modifications notables de ce repo sont documentées ici.

---

## [2.22.1] : Octobre 2026

Correctif de cloisonnement de la 2.22.0, relevé par une revue externe (point 159, §16.5.3). Un refus sur une identité absente des SID de l'utilisateur était ignoré : un document autorisé à un groupe et refusé à « Tout le monde » ou à « Utilisateurs authentifiés » restait lisible par les membres du groupe, alors que Windows le refuse. Validé le 22 octobre 2026 sur la VM de test avec un vrai refus à « Tout le monde » (lecture de données seule) sur un contrat client : même ACL, même compte membre du groupe autorisé, `accès True` en 2.22.0, `accès False` en 2.22.1 ; tests 28, 46 et 14 OK ; refus retiré, test de non-divulgation 79 OK, 2 INFO.

### Sécurité

- `api/anon_auth.py` : `check_access` applique un refus en SID à toute identité dont l'appartenance ne se lit pas dans `tokenGroups` (« Tout le monde », « Utilisateurs authentifiés », groupes intégrés, SID d'une autre machine ou d'un autre domaine) ; jamais aux identités de service ni aux autres comptes du domaine. Autorisations inchangées. Refus en identifiants Entra (SharePoint) inchangés.
- `anon_acl_resolver.py` : tous les refus conservés, y compris aux Administrateurs intégrés (avant : écartés avec leurs autorisations) ; rapport `documents_refus_pour_tous`.

### Tests

- `test_sid.py` : 28 tests (12 de plus), dont 5 échouent sur le code de la 2.22.0.

### Documentation

- `section-16-cloisonnement.md` (§16.5.3), `section-00-quickstart.md`, `tests-apres-modification.md`, `scripts/stack-ia-locale/index.md`, `suivi-corrections.md` (point 159 ; point ouvert 34, commande du courriel de quarantaine).

---

## [2.22.0] : Octobre 2026

Les droits SMB sont comparés par **SID**, plus par noms de groupes (point 158, §16.5.3). Règle trois points ouverts du suivi (14, auth.1, auth.2). Validé sur la VM de test le 22 octobre 2026 : `tokenGroups` lu par le compte de service sans droit supplémentaire ; synchronisation `success=True`, 1 692 extraits migrés en SID, aucun document non migré ; `test_sid.py` 16, `test_echec_droits.py` 46, `test_revalidation_bm25.py` 14 tests OK ; droit retiré `Bilan : OK` ; test de non-divulgation 79 OK, 2 INFO, dont un compte réduit au groupe principal qui voit désormais un document autorisé à « Utilisateurs du domaine ».

### Sécurité

- `anon_acl_resolver.py` : `smbcacls --numeric`, droits enregistrés en SID ; une ligne d'ACL non reconnue rend le fichier illisible (avant : ignorée, au risque d'ignorer un refus) ; type d'entrée inconnu traité comme un refus ; contrôle de migration en fin de passage (`documents_non_migres_sid`, comptés en échec).
- `api/anon_auth.py` : SID du compte et de ses groupes par `tokenGroups` (groupes imbriqués et groupe principal) ; `tokenGroups` illisible, aucun groupe (accès refusé), sans repli ; groupes intégrés (`S-1-5-32-…`) ignorés par défaut ; `ACL_SID_ETENDUS` ; noms des groupes dans le journal pour le dépannage seulement.
- `docker-compose.yml`, `env.example` : `ACL_SID_ETENDUS` (0 par défaut).
- `deploy.sh` : `test_sid.py` exigé dans le dépôt, copie contrôlée, obligatoire et bloquant ; en-tête en 2.22.0.

### Comportement modifié

- **Un document lisible par « Utilisateurs du domaine » devient visible pour tous les comptes du domaine** : c'est le droit du partage, que la RAG ignorait. Commande pour lister ces documents : §16.5.3. Dans le lab, 54 documents, la documentation publique du dossier `DOIT4EVERYONE`.

### Tests et outils

- `test_sid.py` (nouveau, 16 tests) : sorties réelles de `smbcacls --numeric`, `tokenGroups`, décision d'accès.
- `test_echec_droits.py` : contrôle de migration, 46 tests ; `test_revalidation_bm25.py` : groupes de test en SID.
- `diag_sid.py` (nouveau) : SID d'un compte, lecture de `tokenGroups`, SID retenus.
- `cas_cloisonnement.exemple.json` : cas `SMB-DOMAINE`.

### Documentation

- `section-16-cloisonnement.md` : §16.5.3 (nouveau), checklist.
- `section-05-connecteurs.md` : §5.4 et §5.5 en SID.
- `section-00-quickstart.md`, `section-03-docker-compose.md`, `section-09-securite.md`, `tests-apres-modification.md`, `scripts/stack-ia-locale/index.md`.
- `suivi-corrections.md` : point 158 ; points ouverts 14, auth.1 et auth.2 retirés.

---

## [2.21.11] : Octobre 2026

Pas de Release propre : cette version est publiée avec la 2.22.0.

Suite de la septième revue externe : un échec du retrait du marqueur de synchronisation n'apparaissait pas dans le rapport (point 157), et deux précisions de documentation. Validé sur la VM de test le 22 octobre 2026 : 45 et 20 tests unitaires OK, dont l'enchaînement complet du marqueur non retiré (signalé, questions servies, refus au redémarrage, levée par la synchronisation suivante) ; test de non-divulgation inchangé (70 OK, 2 INFO).

### Fiabilité

- `api/anon_main.py` : un marqueur de synchronisation impossible à retirer en fin de passage est signalé comme erreur de `/admin/sync` : l'alerte habituelle part. Les droits sont à jour et les questions restent servies ; au redémarrage, le marqueur fait refuser les questions jusqu'à une synchronisation terminée, comme avant (point 157).

### Tests

- `test_echec_droits.py` : 1 test ajouté, 45 au total.
- `deploy.sh` : en-tête en 2.21.11.

### Documentation

- `section-16-cloisonnement.md` : §16.5.2, tolérance de 5 minutes sur un horodatage dans le futur ; §16.10, ce que `ok` ne dit pas (origine suspendue après un passage incomplet) ; checklist (45 tests).
- `scripts/stack-ia-locale/index.md` : installer la dernière Release ; v2.12.0 présentée comme référence historique.
- `tests-apres-modification.md` : 45 tests.
- `suivi-corrections.md` : point 157.

---

## [2.21.10] : Octobre 2026

Correctif de sécurité, à la suite d'une septième revue externe du code (points 154 à 156). Validé sur la VM de test le 22 octobre 2026 : 20, 44 et 14 tests unitaires OK ; test de non-divulgation inchangé (70 OK, 2 INFO) ; mesure du juge 4B : aucune réponse incomplète du juge, ni sur les réponses réelles ni sur les falsifiées, la règle ne bloque donc aucune réponse ; faits inventés 30/30 détectés. Au passage, la protection de la 2.21.8 a joué en conditions réelles : workflow de synchronisation resté désactivé après des mesures, questions refusées au-delà de 3 heures (`droits_perimes`), reprise après une synchronisation.

### Sécurité

- `api/anon_main.py` : « ancrée » exige un schéma complet (booléen `true` et liste vide) ; une réponse du juge sans liste, ou avec une liste `null`, vide en texte, `0`, objet ou éléments non textuels, vaut « non ancrée » (point 154).
- `api/anon_main.py` : `ACL_AGE_MAX_HEURES` lu strictement : 0, ou nombre fini strictement positif ; `nan`, `inf`, négatif ou texte appliquent la limite de 3 heures, avec une alerte au journal ; le contrôle refuse toute limite invalide qui lui parviendrait (point 156).
- `deploy.sh` : `test_citations.py` exigé dans le dépôt, copie contrôlée, test obligatoire et bloquant comme les tests de sécurité des droits (point 155) ; en-tête en 2.21.10.

### Tests et mesures

- `test_citations.py` : 7 tests ajoutés (schéma de la réponse du juge), 20 au total.
- `test_echec_droits.py` : 2 tests ajoutés (valeurs invalides de `ACL_AGE_MAX_HEURES`), 44 au total.
- `s10/mesure_juge.py` : compte les réponses incomplètes du juge, sur les réponses réelles et falsifiées.

### Documentation

- `section-16-cloisonnement.md` : §16.5.2 (valeurs de `ACL_AGE_MAX_HEURES`), §16.6 (réponse du juge incomplète), checklist (44 tests).
- `section-00-quickstart.md`, `tests-apres-modification.md` : 20 et 44 tests.
- `suivi-corrections.md` : points 154 à 156 ; point 73 (charge) mis à jour.

---

## [2.21.9] : Octobre 2026

Correctif de sécurité : avec la configuration Ollama recommandée, le juge laissait passer un fait inventé sur trois, qu'il avait pourtant repéré (points 151 à 153, §10.12). Première mesure de ce que le juge détecte. La piste du juge partagé, qui devait réduire la charge de vLLM, a été mesurée puis abandonnée. Validé sur la VM de test le 22 octobre 2026 : 13, 42 et 14 tests unitaires OK ; droit retiré OK ; test de non-divulgation inchangé (70 OK, 2 INFO) ; mesure du juge 4B avec la règle : 39 réponses réelles sur 42 acceptées, 33 faits inventés sur 33 détectés.

### Sécurité

- `api/anon_main.py` : verdict du juge incohérent (« ancrée » avec des affirmations non sourcées) traité comme non ancré, avec `[JUGE] Verdict incohérent` au journal (point 151) ; liste du juge normalisée.
- `api/anon_main.py` : seule la phrase de refus exacte est acceptée sans juge (point 152).
- `api/anon_main.py` : verdict de Purview lu strictement (booléen `true` seulement) ; valeur par défaut « non ancrée » dans la lecture du résultat du juge (point 153).
- `deploy.sh` : en-tête en 2.21.9.

### Tests et mesures

- `test_citations.py` : 9 tests ajoutés (lecture du verdict, phrase de refus), 13 au total.
- `s10/mesure_juge.py` (nouveau) : réponses réelles et versions volontairement fausses (chiffre modifié, fait inventé, documents intervertis), verdicts, localisation de la faute, stabilité.

### Documentation

- `section-10-gpu.md` : §10.12, le juge partagé (mesuré, abandonné) et ce que le juge détecte.
- `section-16-cloisonnement.md` : §16.6, verdict incohérent, phrase de refus, verdict de Purview ; §16.5.2, valeurs par défaut précisées.
- `section-00-quickstart.md`, `scripts/stack-ia-locale/index.md` : 13 tests de citations ; `mesure_juge.py`.
- `suivi-corrections.md` : points 151 à 153.

---

## [2.21.8] : Octobre 2026

Correctif de sécurité, à la suite d'une sixième revue externe : si les synchronisations s'arrêtaient (n8n arrêté, workflow désactivé), les derniers droits connus restaient appliqués sans limite de durée, sans alerte (points 144 à 148, §5.4, §16.5.2). Compte rendu du test de charge de vLLM, de une à huit questions simultanées (point 149, §10.12). Procédure de mise à jour complétée : le `docker-compose.yml` est aussi remplacé (point 150). Validé sur la VM de test le 21 octobre 2026 : 42 et 14 tests unitaires OK ; droits périmés refusés puis questions servies après retour à la limite de 3 heures ; droit retiré OK ; test de non-divulgation inchangé (70 OK, 2 INFO).

### Sécurité

- `api/anon_main.py` : âge maximal des droits (`ACL_AGE_MAX_HEURES`, 3 heures par défaut, 0 désactive ce seul contrôle) ; date de la dernière synchronisation complète enregistrée dans le registre (version 3), mise à jour seulement si toutes les origines configurées ont abouti (code 0 ou 2) sans passage incertain et si le registre a été écrit ; au-delà de l'âge, date absente ou dans le futur, questions refusées (503).
- `api/anon_main.py` : marqueur « synchronisation des droits en cours » posé avant l'indexation ; droits non garantis, indexation sautée.
- `api/anon_main.py` : `/health` renvoie l'état des droits (`ok`, `droits_perimes`, `droits_inconnus`), toujours en HTTP 200.
- `docker-compose.yml`, `env.example` : `ACL_AGE_MAX_HEURES`.
- `deploy.sh` : registre créé en version 3 à la date du jour sur une installation neuve seulement ; installation existante sans registre, arrêt en erreur ; tests de sécurité obligatoires dans le dossier source et contrôlés après la copie ; en-tête en 2.21.8.

### Tests

- `test_echec_droits.py` : 11 tests ajoutés, 42 au total.
- `test_revalidation_bm25.py` : date de synchronisation récente posée dans le test ; 14 tests.
- `test_revocation_bm25.py` : contrôle de l'âge désactivé dans son seul processus.
- `s10/charge_s10.py` : mesure de référence de chaque question seule, gain de chaque série, débit en questions par minute.

### Documentation

- `section-05-connecteurs.md` : §5.4, fenêtre de péremption des droits réécrite (latence normale, fenêtre supplémentaire bornée à 3 heures).
- `section-16-cloisonnement.md` : §16.5.2, compléments de la 2.21.8, mise à jour, synchronisation manuelle, limites ; §16.10 ; checklist.
- `section-10-gpu.md` : §10.12, mesure de charge et verdict nuancé.
- `section-03-docker-compose.md` : `ACL_AGE_MAX_HEURES` dans l'extrait.
- `tests-apres-modification.md`, `scripts/stack-ia-locale/index.md` : 42 tests ; `charge_s10.py`.
- `section-16-cloisonnement.md` : mise à jour, remplacement du `docker-compose.yml`, omis depuis la 2.21.2.
- `suivi-corrections.md` : points 144 à 150.

---

## [2.21.7] : Octobre 2026

Correctif de sécurité, à la suite d'une cinquième revue externe : un registre des documents retirés qui n'avait pas pu être écrit était perdu au redémarrage, et les documents retirés depuis redevenaient visibles (points 141 à 143, §16.5.2). Validé sur la VM de test le 20 octobre 2026 : 31 et 14 tests unitaires OK ; synchronisation interrompue simulée, questions refusées puis servies après une synchronisation ; droit retiré OK ; test de non-divulgation inchangé (70 OK, 2 INFO).

### Sécurité

- `api/anon_main.py` : questions refusées tant que le registre n'est pas écrit ; marqueur « synchronisation des droits en cours » posé avant les étapes des droits, retiré après l'écriture du résultat, et contrôlé au démarrage ; marqueur impossible à écrire, droits non synchronisés ; validation stricte du registre ; dossier synchronisé après le renommage ; refus levé par une synchronisation terminée (code 0 ou 2).
- `api/anon_main.py`, `docker-compose.yml`, `env.example` : `ACL_INCERTAIN_FERME` à 1 par défaut.
- `deploy.sh` : en-tête en 2.21.7.

### Tests

- `test_echec_droits.py` : 8 tests ajoutés, 31 au total.

### Documentation

- `section-16-cloisonnement.md` : §16.5.2, compléments de la 2.21.7 et limites ; checklist.
- `section-03-docker-compose.md` : nouvelle valeur par défaut.
- `tests-apres-modification.md`, `scripts/stack-ia-locale/index.md` : 31 tests.
- `suivi-corrections.md` : points 141 à 143.

---

## [2.21.6] : Octobre 2026

Correctif de sécurité, à la suite d'une quatrième revue externe : deux chemins rendaient encore visibles des documents aux droits périmés, dont un introduit par la 2.21.5 (points 138 à 140, §16.5.2). Validé sur la VM de test le 20 octobre 2026 : 23 et 14 tests unitaires OK ; registre absent, questions refusées au démarrage (Open WebUI : « Vérification des droits en cours ») puis servies après une synchronisation complète ; registre relu après redémarrage ; droit retiré OK ; test de non-divulgation inchangé (70 OK, 2 INFO).

### Sécurité

- `sp_indexer.py` : fichier devenu trop volumineux, extraits supprimés au lieu d'être conservés avec leurs anciens droits ; périmètres incomplets (site ou bibliothèque illisible) nommés dans le rapport.
- `api/anon_main.py` : seul un passage complet retire des documents de la liste ; un passage incomplet ajoute (orphelins probables, tout le partage si leur inventaire échoue, périmètres SharePoint incomplets) ; registre écrit de façon atomique, échec signalé ; registre absent ou illisible au démarrage, questions refusées (503) jusqu'à une synchronisation complète ; option `ACL_INCERTAIN_FERME`.
- `deploy.sh` : registre créé vide à l'installation ; en-tête en 2.21.6.
- `docker-compose.yml`, `env.example` : `ACL_INCERTAIN_FERME` (0 par défaut).

### Tests

- `test_echec_droits.py` : 11 tests ajoutés, 23 au total.

### Documentation

- `section-16-cloisonnement.md` : §16.5.2, compléments et limites ; checklist.
- `index.md` du guide : dernière Release à utiliser ; v2.12.0 en référence historique.
- `section-03-docker-compose.md`, `section-13-sharepoint.md` : nouvelle variable, limite de taille.
- `tests-apres-modification.md`, `scripts/stack-ia-locale/index.md` : 23 tests.
- `suivi-corrections.md` : points 138 à 140.

---

## [2.21.5] : Octobre 2026

Correctif de sécurité, à la suite d'une troisième revue externe du code : un échec d'écriture des droits dans Qdrant passait pour un fichier non indexé, sans alerte, et le document gardait ses anciens droits (points 135 à 137, §16.5.2). Validé sur la VM de test le 20 octobre 2026 : 12 et 14 tests unitaires OK, synchronisation réelle réussie sans document retiré, droit retiré sur le vrai Qdrant OK, test de non-divulgation inchangé (70 OK, 2 INFO).

### Sécurité

- `anon_acl_resolver.py` : trois issues par document (mis à jour, non indexé, échec d'écriture) ; seconde tentative ; échecs de fermeture, de suppression et de lecture des orphelins traités de même ; code de sortie 2 et liste des échecs dans le rapport.
- `api/anon_main.py` : documents dont les droits n'ont pas pu être écrits retirés de la recherche et du contrôle d'accès jusqu'au prochain passage sans échec ; liste gardée dans `/var/log/rag/acl_bloques.json` ; même règle pour les fichiers SharePoint en erreur ; synchronisation en échec avec le nombre de documents retirés.
- `api/anon_main.py` : statut `non_indexe` reconnu pour la quarantaine (point 136).
- `deploy.sh` : `test_revalidation_bm25.py` et `test_echec_droits.py` obligatoires ; absent ou en échec, RAG API arrêtée et déploiement en erreur (point 137). En-tête en 2.21.5.

### Tests

- `test_echec_droits.py` (nouveau) : 12 tests unitaires, Qdrant simulé (résolveur et RAG API).

### Documentation

- `section-16-cloisonnement.md` : §16.5.2 (nouveau), checklist.
- `section-08-fiabilite.md` : encadré « principes et essais historiques », renvoi au §10.
- `index.md` du guide : plus de consigne pour retirer le filtre des droits dans le code.
- `section-05-connecteurs.md` : renvoi au §16.5.2.
- `tests-apres-modification.md`, `scripts/stack-ia-locale/index.md` : nouveau test.
- `suivi-corrections.md` : points 135 à 137.

---

## [2.21.4] : Octobre 2026

Durcissement complémentaire, à la suite d'une seconde revue externe du correctif 2.21.3. Validé sur la VM de test le 20 octobre 2026 : 14 tests unitaires OK, test sur le vrai Qdrant OK, test de non-divulgation inchangé (70 OK, 2 INFO) ; blocage de `deploy.sh` vérifié en simulation.

### Sécurité

- `deploy.sh` : un échec de `test_revalidation_bm25.py` bloque le déploiement ; la RAG API est arrêtée et le script se termine en erreur (point 133). En-tête en 2.21.4.
- `api/anon_main.py` : sans groupes, `search_qdrant` refuse avant toute recherche (403), `revalider_bm25` et `etendre_complements` ne renvoient rien ; les contrôles d'accès ne sont plus jamais sautés faute d'identité (point 134).

### Tests

- `test_revalidation_bm25.py` : trois tests ajoutés (sans groupes), 14 au total ; sur le code de la 2.21.2, les 14 échouent.

### Documentation

- `section-16-cloisonnement.md` : §16.5.1, compléments de la 2.21.4 et limite de la correction (fenêtre de péremption du §5.4) ; checklist.
- `tests-apres-modification.md`, `scripts/stack-ia-locale/index.md` : 14 tests.
- `suivi-corrections.md` : points 133 et 134.

---

## [2.21.3] : Octobre 2026

Correctif de sécurité, à la suite d'une revue externe du code : un droit retiré restait valable par la recherche par mots-clés jusqu'à la reconstruction de son index (point 10, §16.5.1). Validé sur la VM de test le 20 octobre 2026 : fuite reproduite sur le vrai Qdrant en 2.21.2, absente en 2.21.3, test de non-divulgation inchangé (70 OK, 2 INFO).

### Sécurité

- `api/anon_main.py` : chaque candidat de la recherche par mots-clés (BM25) est relu dans Qdrant par son identifiant, en un appel par collection, et ses droits (ALLOW, puis DENY) sont contrôlés sur cette lecture (`revalider_bm25`) ; texte, source et étiquette Purview en sont repris. Un point disparu ou une lecture en erreur écarte le candidat. Les droits mémorisés dans l'index ne servent plus qu'à présélectionner.
- `api/anon_main.py` : `etendre_complements` ne remet plus l'extrait d'origine quand la relecture des voisins revient vide ou en erreur ; le document est écarté.

### Tests

- `test_revalidation_bm25.py` (nouveau) : 11 tests unitaires, Qdrant simulé ; sur le code de la 2.21.2, les 11 tests échouent, dont les deux recherches de bout en bout (fuite reproduite).
- `test_revocation_bm25.py` (nouveau) : test sur le vrai Qdrant, droit retiré quelques secondes sans reconstruction de l'index, question composée avec les mots les plus rares du document, droits remis et contrôlés ensuite.
- `deploy.sh` : copie des deux tests, tests unitaires lancés à l'étape 10 ; en-tête en 2.21.3.
- `tests-apres-modification.md` : §9.3.

### Documentation

- `section-08-fiabilite.md` : §8.6, droits relus dans Qdrant.
- `section-16-cloisonnement.md` : statut ; §16.2, ce que le test de non-divulgation ne voit pas ; §16.5.1 (nouveau) ; checklist.
- `suivi-corrections.md` : point 10 corrigé, gravité sous-estimée jusqu'ici.
- Page d'accueil (`index.md`), `README.md`, sommaire du guide : présentation mise à jour (18 sections, validation sur GPU, sécurité de la 2.21, lab et non production, rejeu du 19 octobre, prochaines étapes).

---

## [2.21.2] : Octobre 2026

Rejeu complet du §0 avec la version 2.21.1 sur une VM Ubuntu 26.04 neuve, le 19 octobre 2026, avec Ollama : déploiement, certificat auto-signé puis certificat de l'autorité interne, indexation (70 fichiers, 1 692 extraits), droits, Open WebUI, n8n, cloisonnement (72 verdicts, aucune fuite), usurpation refusée, garde-fou par un partage inexistant, ports exposés, redémarrage et supervision. Corrections issues de ce rejeu.

### Scripts

- `deploy.sh` : garde-fou du `.env` existant placé au début, avant les questions ; résumé final ouvert par la création du compte propriétaire de n8n ; `--rapport /var/log/rag/...` dans les commandes d'indexation et de droits ; en-tête en 2.21.2.
- `docker-compose.yml` : `N8N_UNVERIFIED_PACKAGES_ENABLED=false`.

### Documentation

- `section-00-quickstart.md` : statut du rejeu ; étape 4, intermédiaire gardé en `ad-subca.pem` ; garde-fou des droits validé ; `--rapport` dans la checklist.
- `section-09-securite.md` : statuts ; §9.8.1, liaison vers le serveur de modèles sur un serveur unique, l'exposition plutôt que le chiffrement ; §9.8.4, intermédiaire et autorité à un seul niveau ; §9.8.6, procédure rejouée.
- `section-16-cloisonnement.md` : contrôle d'usurpation rejoué tel qu'écrit.
- `section-03-docker-compose.md`, `section-07-n8n.md` : paquets communautaires.
- `suivi-corrections.md` : points 127 à 131 corrigés ; points 106, 114, 72 et doc.5 mis à jour ; point 132 ouvert.

---

## [2.21.1] : Octobre 2026

Corrections à la suite d'une revue externe du dépôt publié en 2.21.0 : variables de n8n, contrôle du certificat en fin de déploiement, portée du chiffrement, formulation sur les images figées.

### Scripts

- `docker-compose.yml` : `N8N_WEBHOOK_URL` à la place de `WEBHOOK_URL`, dépréciée depuis n8n 2.35 (la 2.20.4 avait fait le changement inverse, à tort) ; `N8N_BASIC_AUTH_*` retirées, sans effet depuis n8n 1.0 ; reranker signalé comme seule image non figée par empreinte.
- `env.example`, `deploy.sh` : `N8N_BASIC_AUTH_*` retirées.
- `deploy.sh` : en-tête en 2.21.1 ; `.env` existant signalé avant toute modification, confirmation demandée (refus par défaut) et copie datée ; avec un certificat de l'autorité interne, `/sante` vérifié aussi avec la chaîne de l'autorité (`--cacert`), et non plus seulement avec `-k`.

### Documentation

- `section-09-securite.md` : §9.8.1, `N8N_WEBHOOK_URL` ; tableau de ce que le frontal chiffre et ne chiffre pas (le TLS s'arrête à Nginx ; liaison vers le serveur de modèles en clair).
- `section-07-n8n.md`, `section-00-quickstart.md` : compte propriétaire de n8n à créer dès la première ouverture ; `N8N_BASIC_AUTH_*` retirées.
- `section-03-docker-compose.md`, `section-16-cloisonnement.md` : extraits du `.env` et du Compose ; images du déploiement standard figées, reranker excepté.
- `section-17-gouvernance.md` : §17.9, « A/R » sans retour à la ligne.
- `s10/mesure_s10.py`, `s10/charge_s10.py` : identité signée (les deux scripts recevaient 403 depuis la 2.21.0).
- `suivi-corrections.md` : points 117 à 120, 125 et 126 corrigés, point 98 rectifié, doc.3 clos ; points 121 à 124 ouverts.

---

## [2.21.0] : Octobre 2026

Sécurisation de la stack, validée élément par élément sur la VM de test en service (Ubuntu 26.04), du 17 au 18 octobre 2026 : frontal HTTPS Nginx, identité signée entre Open WebUI et la RAG API, refus de démarrer sur un secret d'exemple, versions figées par empreinte, supervision externe. Procédure de renouvellement du certificat et matrice RACI. La procédure complète du §0 avec cette version reste à rejouer sur une VM neuve.

### Scripts

- `nginx/rag.conf` (nouveau) : frontal TLS (1.2 et 1.3) ; Open WebUI sur le port 443, n8n sur le port 5678, `/sante` pour la supervision ; redirection de HTTP vers HTTPS ; WebSocket, réponses non mises en tampon, délai de 600 s ; requêtes par adresse IP ou par un autre nom refusées (`return 444`, `ssl_reject_handshake`) ; HSTS prévu, commenté.
- `docker-compose.yml` : service `nginx` (1.30.6), seul à publier des ports ; Open WebUI et n8n sans port publié ; n8n derrière le frontal (`N8N_HOST`, `N8N_PROTOCOL=https`, `N8N_PROXY_HOPS`, `WEBHOOK_URL` construits depuis `RAG_FQDN`, cookie sécurisé) ; identité signée (`FORWARD_USER_INFO_HEADER_JWT_SECRET`, `OWUI_JWT_SECRET`) ; `ENABLE_VERSION_UPDATE_CHECK=false` ; images du déploiement standard figées par empreinte (le reranker facultatif excepté, précision de la 2.21.1).
- `api/anon_main.py` : démarrage refusé sur un secret vide, une valeur d'exemple, un jeton de moins de 32 caractères ou deux jetons identiques ; identité de l'utilisateur lue dans le jeton signé par Open WebUI (`X-OpenWebUI-User-Jwt`), en-têtes simples refusés ; `/query` réservé à `ADMIN_TOKEN`.
- `api/Dockerfile` : image de base figée par empreinte. `api/requirements.txt` : toutes les dépendances figées (`pip freeze` du conteneur validé), PyJWT cité comme dépendance directe.
- `deploy.sh` : nom de la stack demandé et contrôlé ; certificat fourni contrôlé (clé, nom, échéance) ou auto-signé généré, auto-signé existant signalé ; `/etc/rag-tls` sur le disque chiffré ; configuration de Nginx au nom de la stack ; `OWUI_JWT_SECRET` généré, jeton saisi trop court refusé ; cinq conteneurs et `/sante` contrôlés à travers Nginx ; adresses finales en HTTPS.
- `env.example` : `OWUI_JWT_SECRET`, `RAG_FQDN` (remplace `N8N_WEBHOOK_URL`).
- `test_cloisonnement.py` : `/query` par `ADMIN_TOKEN`. `tests-apres-modification.md` : questions de test avec une identité signée.
- `N8N/n8n-sync-corpus.json` : nœud « Signal supervision (Push) », désactivé par défaut, sans effet sur le courriel d'erreur en cas d'échec. `N8N/index.md` : adresse HTTPS, nom complet de la machine de supervision.
- `index.md` des scripts : architecture avec Nginx, `nginx/rag.conf`, dépendances figées, identité signée.

### Documentation

- `section-09-securite.md` : §9.8 nouvelle, frontal HTTPS et certificats (nom DNS de la stack, auto-signé ou autorité interne, obtention par `certreq` avec le modèle Serveur Web, chaîne, postes clients, **renouvellement pas à pas avec retour arrière**, refus par adresse IP, HSTS, noms multiples, exposition réseau) ; §9.1.2 et §9.1.5 mis à jour ; checklist devenue §9.9.
- `section-16-cloisonnement.md` : §16.6 (secrets refusés, identité signée, contrôle d'usurpation, `/query`) ; §16.7 ; §16.8 (empreintes, mise à jour d'une image, branche stable de Nginx, revue des versions) ; §16.10 nouvelle, supervision externe (contrôles, signal de synchronisation, exemple Uptime Kuma validé en lab et ses limites) ; checklist devenue §16.11.
- `section-17-gouvernance.md` : §17.3 (identité signée, certificat de la stack, certificats de l'autorité) ; §17.6 (revue des versions, essai de la supervision) ; §17.7 en tableau d'état ; **§17.9 nouvelle, matrice RACI**, modèle à adapter.
- `section-15-securite-donnees.md` : §15.5, sauvegarde laissée à l'outil de l'organisation (choix assumé, restauration non testée) ; certificat de Nginx.
- `section-00-quickstart.md` : prérequis (nom DNS, certificat) ; étapes 6, 7 (point 5 : nom de la stack, configuration de Nginx, certificat), 9, 14, 15 (signal de supervision), 16 et checklist.
- `section-01-prerequis.md`, `section-03-docker-compose.md`, `section-05-connecteurs.md`, `section-07-n8n.md`, `section-08-fiabilite.md`, `section-14-purview.md`, `index.md` : adresses HTTPS, identité signée, extraits du `.env` et du Compose.
- `suivi-corrections.md` : points 44 et 105 à 113 corrigés ; points 114 à 116 ouverts ; points doc.3, doc.5 et 34 mis à jour.

---

## [2.20.4] : Octobre 2026

Second rejeu complet du §0 sur une VM Ubuntu 26.04 neuve, du 15 au 17 octobre 2026 (disque chiffré, `deploy.sh`, indexation, droits, Open WebUI, n8n, cloisonnement, deux redémarrages, sauvegarde et restauration de Qdrant). Corrections du script, du Compose, de deux outils et du guide ; procédure de restauration de Qdrant réécrite et validée.

### Scripts

- `deploy.sh` : contrôle de la résolution DNS du contrôleur de domaine et du serveur de fichiers, avertissement en cas de DNS public ; installation des paquets Python avec reprises (`--retries 10 --timeout 60`) et message d'erreur explicite ; dossier de documentation vide par défaut, finalité des deux collections expliquée, présence du dossier contrôlée ; montage existant en écriture signalé ; tests des citations lancés ; première indexation et synchronisation des droits proposées en fin de déploiement (facultatives, journalisées) ; résumé final corrigé (étapes n8n, snapshot).
- `docker-compose.yml` : `QDRANT__STORAGE__SNAPSHOTS_PATH` (snapshots dans le volume) ; fuseau `Europe/Zurich` pour n8n ; `WEBHOOK_URL`, variable lue par n8n ; contrôle de santé de `rag-api`.
- `anon_acl_resolver.py` : arrêt au premier refus d'authentification, pour ne pas verrouiller `svc-rag` ; contrôle DNS du serveur de fichiers ; messages `[GARDE-FOU]` aussi sur la sortie d'erreur ; en-tête avec les deux collections ; liste des fichiers dont une entrée ALLOWED a été ignorée.
- `api/anon_main.py` : citations dont seul un accent ou la casse diffère du nom réel corrigées quand la correspondance est unique (faux avertissement constaté) ; contrôle qui a conclu inscrit au journal (`controle_echoue`) pour les réponses non ancrées.
- `test_citations.py` (nouveau) : quatre tests unitaires du contrôle des citations.
- `api/anon_main.py`, `anon_indexer.py`, `anon_acl_resolver.py`, `sp_indexer.py`, `test_cloisonnement.py` : journaux et rapports créés en `640` ; dossier de documentation vide par défaut.
- `env.example` : `DOCUMENTATION_PATHS` vide par défaut, commentaire réécrit.
- `N8N/n8n-rappel-rotation-svc-rag.json` : mention publicitaire de n8n retirée du courriel. `N8N/index.md` : options SMTP, expéditeur, destinataire interne, fuseau.

### Documentation

- `section-00-quickstart.md` : statut ; étapes 2, 4 (DNS), 5 (lecture seule), 6, 7, 9, 11, 14 (libellés LDAP en français, réglages personnels), 15 (n8n, réécrite), 16 (garde-fou sans verrouillage, contrôle des citations, redémarrage, snapshot à froid) ; dépannage (noms du domaine introuvables après un redémarrage, compte verrouillé, téléchargement Python).
- `section-03-docker-compose.md` : §3.4 extrait du Compose ; §3.7 réécrite et validée (snapshots dans le volume, copie avant suppression, restauration en `PUT`).
- `section-05-connecteurs.md` : §5.3 DNS et lecture seule ; §5.4.2b arrêt au premier refus d'authentification, contrôle DNS, test du garde-fou ; §5.9 collection `documentation` et règle 1 corrigée.
- `section-15-securite-donnees.md` : §15.3.5 contrôle des noms et état de santé.
- `suivi-corrections.md` : points 89 et 93 à 104 corrigés ; points 31 et doc.5 mis à jour.

---

## [2.20.3] : Octobre 2026

Rejeu complet du §0 sur une VM Ubuntu 26.04 neuve : corrections de `deploy.sh`, du Compose et du guide ; section sur les sauvegardes réécrite ; lecture paginée de l'index BM25 ; points de suivi ouverts.

### Scripts

- `deploy.sh` : confirmation par « o » ou « oui » avec message en cas de réponse non reconnue ; `chown` de `n8n_data` sur le vrai dossier (n8n tourne sous l'utilisateur 1000) ; dossier de documentation par défaut aligné sur l'indexeur ; `SP_EXCLUDE_DRIVES` entre apostrophes ; liste complète des paquets Python ; contrôles de fin de déploiement (RAG API joignable depuis son conteneur, quatre conteneurs en `running` sans redémarrage), liste des problèmes et sortie en erreur au lieu de « Déploiement terminé » ; résumé final décrivant les attributs LDAP et les tâches d'Open WebUI.
- `docker-compose.yml` : tâches d'arrière-plan d'Open WebUI (titre, étiquettes, questions de suivi, autocomplétion) désactivées par variables d'environnement, état initial d'une base neuve.
- `docker-compose.yml`, `env.example` : variable `N8N_WEBHOOK_URL` (adresse annoncée par n8n) ; valeur de `SP_EXCLUDE_DRIVES` entre apostrophes. `index.md` : exemple aligné.
- `s10/charge_s10.py` (nouveau) : mesure de la charge, 1, 2, 4 puis 8 questions posées en même temps à la RAG API, avec durées médiane, P95 et maximale, erreurs et écarts de réponse par palier. Essayé contre un serveur simulé ; pas encore lancé sur la stack.
- `api/anon_main.py` : index BM25 vide avant la première indexation signalé par un message clair au lieu de « division by zero ».
- `api/anon_main.py` : le chargement des chunks pour l'index BM25 se fait par pages jusqu'à épuisement. Auparavant, un seul appel plafonnait la lecture à 100 000 chunks par collection, sans avertissement. Sans effet sur les corpus actuels.

### Documentation

- `section-00-quickstart.md` : statut du rejeu sur VM neuve ; étape 2 (certificats listés, exportés par empreinte, PKI à deux niveaux) ; étape 4 (fichier de chaîne, contrôle `s_client`) ; étape 6 (`chown` de `n8n_data`, encadré `deploy.sh`) ; étape 7 (`.env` derrière un lien, `up -d` et non `restart`, apostrophes, `N8N_WEBHOOK_URL`) ; étape 11 (`smbclient -W`) ; étape 14 (section « API compatibles OpenAI », attributs LDAP, tâches d'arrière-plan, contrôle du journal) ; étape 16 ; dépannage (n8n, `source .env`, santé de la RAG API, `smbclient`, index vide).
- `section-01-prerequis.md` : §1.4 versions relevées sur VM neuve ; §1.5 statut et deux conséquences du `.env` en lien.
- `section-03-docker-compose.md` : `WEBHOOK_URL=${N8N_WEBHOOK_URL}` ; `chown` sur le vrai dossier.
- `section-14-purview.md` : §14.8.2 quatre appels par question avant réglage, appel résiduel.
- `section-15-securite-donnees.md` : §15.3.3 contrôle `luksDump` qui affiche les deux emplacements et le jeton ; §15.3.5 redémarrage validé sur VM neuve.
- `section-16-cloisonnement.md` : §16.3 rejeu sur déploiement neuf (72 verdicts, 0 fuite) ; §16.8 tâches d'arrière-plan.
- `section-10-gpu.md` : §10.1, note sur la mémoire de la carte et le processeur graphique qui rend le bureau, avec la commande de mesure de base.
- `section-15-securite-donnees.md` : §15.5 réécrite autour de la sauvegarde de la VM entière par l'outil de l'organisation (par exemple Veeam), avec chiffrement : ce qui se reconstruit (index Qdrant, index BM25) et ce qui ne se reconstruit pas (Open WebUI, n8n, secrets, phrase du disque), quatre points propres à la stack (cohérence de la sauvegarde, disque chiffré et TPM à la restauration, éléments hors de la VM, chiffrement et rétention), test de restauration à rejouer. Statut inchangé : non validé en lab. Checklist §15.6 alignée.
- `suivi-corrections.md` : points 77 à 88 corrigés ; point 34 précisé ; points 75 (échelle de l'index), 76 (erreur d'Ollama sans message lisible), 89 (appel résiduel d'Open WebUI), 90 (refus non déterministe), 91 (rotation du mot de passe à valider) et 92 ouverts ; doc.5 mis à jour.

---

## [2.20.2] : Octobre 2026

Juge d'Ollama remplacé après mesure, et mesures d'Ollama avec plusieurs questions simultanées.

### Scripts

- `env.example`, `deploy.sh`, `api/anon_main.py`, `s10/mesure_s10.py`, `index.md` : juge par défaut `qwen3:4b-instruct` avec Ollama (l'étiquette `qwen3:4b` raisonne toujours). `deploy.sh` vérifie et demande ce modèle.

### Documentation

- `section-10-gpu.md` : §10.12, trois juges mesurés (26 sur 30 en 4,8 min avec `qwen3:4b-instruct`, contre 24 sur 30 en 5,4 min et 26 sur 30 en 6,8 min), `OLLAMA_NUM_PARALLEL=2` écarté sur 16 Go, deux séries simultanées avec Ollama (8,1 à 8,2 min contre 4,8 min seule) comparées à vLLM ; §10.2 et §10.11 alignés.
- `section-00-quickstart.md`, `section-02-vllm.md`, `section-03-docker-compose.md` : téléchargement et réglage du juge `qwen3:4b-instruct`, réserve du §2.2 appuyée par les chiffres.
- `suivi-corrections.md` : points 68 et 69 corrigés, point 74 ouvert (I1 sous charge).

---

## [2.20.1] : Octobre 2026

Corrections après relecture du dépôt : un contrôle de sécurité de `deploy.sh` et des extraits du §3 qui ne correspondaient plus aux fichiers.

### Scripts

- `deploy.sh` : le test de la clé d'API vLLM est bloquant. Un serveur qui répond sans clé (code autre que 401) arrête le déploiement au lieu d'émettre un avertissement.

### Documentation

- `section-03-docker-compose.md` : `QDRANT_API_KEY` ajouté aux extraits du `.env` et du Compose, comme dans les fichiers du dépôt. Les contrôles de §3.6, les snapshots et la restauration envoient la clé de Qdrant et le jeton d'administration, lus dans le `.env` ; les jetons d'exemple (`changeme-api-token`) sont retirés des commandes.
- `section-02-vllm.md` : §2.4.10, avant une mise en production (transport en HTTP, modèles et code distant non figés, charge non mesurée). Ces trois points ne sont pas testés en lab.
- `suivi-corrections.md` : points 70 et 71 corrigés, points 72 et 73 ouverts.

---

## [2.20.0] : Octobre 2026

Deux moteurs pour le serveur de modèles : Ollama, pour un à deux utilisateurs simultanés, et vLLM, pour plusieurs. Le démarrage rapide est réécrit pour partir de l'un ou de l'autre.

### Documentation

- `section-00-quickstart.md` : réécrit pour des lecteurs non spécialistes. Les trois machines, le choix du moteur, les conventions (où lancer chaque commande, valeurs à remplacer, résultat attendu à chaque étape), l'installation d'Ollama (3A) ou de vLLM (3B), les scripts récupérés par `git clone`, tous les secrets générés automatiquement, le bloc du serveur de modèles dans le `.env`, un contrôle depuis le conteneur (la VM qui joint le serveur ne suffit pas), le test de cloisonnement en contrôle final, et un dépannage étendu (pare-feu, réseau Docker sans adresse, serveur d'embedding arrêté, synchronisation en cours).
- `section-02-vllm.md` : réécrit, « Le serveur de modèles : Ollama ou vLLM ». Rôle du serveur, choix du moteur, Ollama sous Windows et sous Linux, vLLM dans WSL2 (préparation, installation, modèles, clé d'API, lancement, vérifications, services systemd validés dans WSL2, WSL2 non adapté à un service permanent, raccordement), onze pièges rencontrés en lab, bascule sans réindexation, DGX Spark (documentaire). Le contenu sur vLLM en mode CPU est retiré.
- `section-10-gpu.md` : §10.12, Ollama contre vLLM mesurés sur la même carte (score 61 et 65 sur 75, une question seule plus lente avec vLLM, deux séries simultanées servies presque aussi vite qu'une seule, index réutilisable sans réindexation, juge `qwen3:4b` en variante qui raisonne toujours) ; §10.3, le piège d'une synchronisation pendant une mesure ; §10.4, durées actuelles ; §10.11, le moteur dans la configuration recommandée.
- `index.md`, `section-01-prerequis.md`, `section-03-docker-compose.md` : les deux moteurs, mémoire de la VM sans vLLM, extraits du `.env` et du Compose.
- `suivi-corrections.md` : points 63 et 64 corrigés, points 65 à 69 ouverts, doc.5 complété.
- `README.md`, `index.md`, `docs/index.md` : description de la stack et environnement de référence, avec les deux moteurs.

### Scripts

- `api/anon_main.py`, `api/teams.py` : protocole du serveur de modèles réglable, `LLM_API` et `EMBED_API` (`ollama` par défaut, `openai` pour vLLM), `JUDGE_BASE_URL` (vide : le serveur de génération), `VLLM_API_KEY`. Avec vLLM : juge et synthèse Teams en JSON contraint, vecteurs d'embedding ramenés à une longueur de 1, refus du serveur écrit au journal. Variables transmises aux indexeurs lancés par `/admin/sync`. Sans ces réglages, le comportement est inchangé.
- `anon_indexer.py` : embedding et contrôle de démarrage par l'API de vLLM ; un texte trop long pour le serveur est raccourci avec un avertissement.
- `s10/mesure_s10.py` : moteur noté dans le rapport, déchargement des modèles sans objet avec vLLM.
- `docker-compose.yml` : `LLM_API`, `EMBED_API`, `JUDGE_BASE_URL`, `VLLM_API_KEY`, avec leurs valeurs par défaut.
- `env.example` : bloc du serveur de modèles en deux variantes (Ollama, vLLM) ; `JUDGE_NUM_CTX` porté de 8 192 à 16 384 (règle du §10.6) ; contrôle de Qdrant avec la clé d'API ; repères du lab retirés de l'en-tête.
- `deploy.sh` : choix du moteur, contrôle des deux serveurs vLLM (refus sans clé, modèles servis), `.env` adapté, `JUDGE_NUM_CTX=16384`, contrôle du serveur de modèles depuis le conteneur. Testé sur des serveurs simulés ; pas encore rejoué sur une VM neuve (suivi doc.5).

---

## [2.19.0] : Octobre 2026

Refonte du plan d'apprentissage.

### Guides

- `guides/plan-apprentissage-rag-2026.docx` et `.pdf` : refonte complète, 17 phases au lieu de 14, en trois ensembles. Phases 1 à 12 : le pipeline sur file server Windows, sur CPU. Phases 13 à 15 : connecteurs Microsoft 365 (SharePoint Online, documents protégés par Purview, synthèse des réunions Teams), qui demandent un tenant actif. Phases 16 et 17 : contrôle automatisé du cloisonnement, puis passage sur GPU et méthode de mesure reproductible.
- Modèle principal `qwen3:14b` au lieu de `qwen2.5:14b`, cohérent avec §10.
- Corrections de fond : la phase Purview remplace la piste du coffre de clés par le service de déchiffrement réellement validé ; la synthèse Teams part en brouillon à l'organisateur et non dans un canal ; la phase NTFS intègre la lecture du masque des droits ; la phase Docker Compose intègre le piège des variables non transmises au conteneur.
- Chaque phase porte désormais les enseignements mesurés en lab, y compris les décisions renversées par la mesure.

### Documentation

- `docs/index.md` : §10 publiée au lieu de « à venir », environnement de référence avec GPU, renvoi au plan en 17 phases.
- `index.md`, `README.md`, `guides/index.md` : dates et description du plan.

---

## [2.18.2] : Octobre 2026

Trois points d'une revue externe : deux corrigés, un mesuré puis écarté.

### Scripts

- `api/anon_main.py` : le test d'accès (`/admin/verifier-acces`) distingue une collection absente d'une panne de Qdrant (HTTP 503) ; correspondance exacte du document par défaut (nom de fichier ou chemin complet), cas ambigu refusé (HTTP 400), correspondance partielle sur demande.
- `test_cloisonnement.py` : même règle de correspondance, y compris en mode complet ; option `correspondance` par cas.
- `cas_cloisonnement.exemple.json` : règle de désignation des documents.

### Documentation

- `section-16-cloisonnement.md` : verdict ERREUR, correspondance exacte, le cas du guide en deux exemplaires révélé par ce contrôle, 44 sur 44.
- `section-10-gpu.md` §10.6 : identité des extraits dans la fusion des classements, mesurée et écartée.
- `suivi-corrections.md` : point 60 corrigé, points 61 et 62 ouverts.

---

## [2.18.1] : Octobre 2026

### Documentation

- `section-10-gpu.md` §10.5 : test d'Apertus 8B, le modèle suisse de l'EPFL, de l'ETH Zurich et du CSCS. Conversion communautaire, gabarit de conversation à vérifier, résultats sur le jeu de questions (4 sur 15 : refus avec le bon document, extraits recopiés, code inventé pour un compte sans droit, aucune fuite) et conclusion : non adapté à ce RAG dans cette version.

---

## [2.18.0] : Octobre 2026

Passage sur GPU (NVIDIA RTX 5060 Ti 16 Go) et campagne de mesures.

### Documentation

- `section-10-gpu.md` : nouvelle section. Mise en place de la carte et d'Ollama (réglages vérifiés dans son journal), placement des modèles, méthode de mesure, gains CPU contre GPU, choix du modèle principal (`qwen3:14b`) et de l'embedding (`nomic-embed-text`), construction du contexte, reranker (optionnel, désactivé), prompt et forme des réponses, pièges de configuration, limites qui relèvent du corpus, configuration recommandée et checklist.
- Modèle principal recommandé : `qwen3:14b` au lieu de `qwen2.5:14b` (§0, §3, index, scripts).
- `section-08-fiabilite.md`, `section-03-docker-compose.md` : nouveaux réglages ; extraits consécutifs pour les documents complémentaires.
- `section-09-securite.md`, `section-11-prerequis-ms365.md`, `index.md`, `README.md` : §10 publiée, navigation.
- `suivi-corrections.md` : points 53 à 58 corrigés, point 59 ouvert.

### Scripts

- `api/anon_main.py` : placement des modèles et graine (`JUDGE_NUM_GPU`, `EMBED_NUM_GPU`, `LLM_SEED`) ; document court en entier et fenêtre décalée ; extraits consécutifs pour les documents complémentaires ; fenêtre du juge égale par défaut à celle du modèle ; reranker optionnel avec fusion des classements ; règles de prompt complémentaires ; nettoyage des réponses et normalisation des citations ; valeurs vides traitées comme absentes.
- `api/anon_auth.py`, `anon_indexer.py` : valeurs vides traitées comme absentes ; placement de l'embedding transmis à l'indexeur.
- `api/teams.py` : maintien en mémoire limité pour un modèle de synthèse distinct ; modèle par défaut `qwen3:14b`.
- `test_cloisonnement.py` : attend que la RAG API réponde avant de commencer.
- `docker-compose.yml`, `env.example` : nouveaux réglages avec leurs valeurs par défaut ; service reranker optionnel (profil `reranker`).
- `deploy.sh` : modèle `qwen3:14b`.
- `s10/mesure_s10.py`, `s10/jeu_questions_s10.json` : outils de mesure du §10.

---

## [2.17.4] : Octobre 2026

### Documentation

- Navigation harmonisée dans toutes les sections, de §0 à §17 : en haut et en bas de chaque page, retour au sommaire, section précédente et section suivante, avec leur titre complet. Le bas de §13 annonçait encore §14 « à venir ».
- `section-05-connecteurs.md` : retrait d'un lien de navigation placé au milieu de la page ; dans §5.9, la commande de synchronisation utilise `--post-data` et lit le jeton dans le `.env` (la commande précédente envoyait un GET, refusé par la RAG API).
- `section-11-prerequis-ms365.md` : la mention de bas de page renvoie à §14 au lieu d'annoncer Purview « à venir ».
- `section-09-securite.md` : la section suivante est §11 ; §10 (validation et benchmarks) paraîtra après les mesures sur GPU.

---

## [2.17.3] : Octobre 2026

### Documentation

- `index.md` du guide : retrait de la ligne « Gouvernance Microsoft 365, À venir », restée dans le tableau des sections alors que §17 est publiée.
- `README.md` : la Partie 3 est présentée comme publiée (§11 à §17), et non plus « en cours de publication ».

---

## [2.17.2] : Octobre 2026

Questions larges : diversité des sources et réponses partielles.

### Documentation

- `section-08-fiabilite.md` : §8.9, diversité des sources et réponses partielles, avec les deux tests de refus qui protègent la correction et les limites constatées ; paramètres de §8.6 mis à jour ; formulations recommandées pour les questions larges (§8.8).
- `section-03-docker-compose.md` : nouveaux réglages dans le `.env` et le Compose ; `TOP_K` obsolète.
- `section-17-gouvernance.md` : une seule version de chaque document dans les dossiers indexés, avec le cas observé en lab.
- `suivi-corrections.md` : points 50 et 51 corrigés, point 52 ouvert pour le §10.

### Scripts

- `api/anon_main.py` : 30 candidats ; document principal limité à 9 extraits ; 6 documents complémentaires de 2 extraits, regroupés, copies écartées ; prompt avec réponse partielle explicite, synthèse document par document et noms de fichiers complets.
- `docker-compose.yml`, `env.example` : `CANDIDATS`, `PRINCIPAL_MAX`, `CONTEXT_OTHER_DOCS`, `EXTRAITS_PAR_COMPLEMENT`.
- `tests-apres-modification.md` : nouvelle procédure de tests après toute modification.

---

## [2.17.1] : Octobre 2026

### Documentation

- `section-17-gouvernance.md` : nouvelle section, qui clôt la Partie 3. Limites de la conformité technique face aux obligations nLPD, matrice des responsabilités, rotation des secrets et certificats avec leurs échéances, politique de corpus, droit d'accès et à l'effacement (jusqu'aux sauvegardes), audit périodique, exigences relevant du passage en production.
- Index du guide, accueil, `README.md` : §17, Partie 3 complète.
- `section-03-docker-compose.md` : versions figées et empreintes validées des images (§3.4).
- `section-16-cloisonnement.md` : §16.8, une mise à jour d'Open WebUI revalidée (réponse en flux exigée) ; §16.9, une perte d'accès doit se dire (échec de la résolution Entra), deux jetons et deux usages ; checklist complétée.
- `suivi-corrections.md` : points 47 à 49 ; point 45 complété (deux jetons restés à leur valeur d'exemple dans le lab).

### Scripts

- `docker-compose.yml` : Qdrant `v1.19.0`, n8n `2.36.9`, Open WebUI `v0.11.3`, au lieu de `latest` et `main`.
- `api/anon_main.py` : réponse en flux quand le client la demande (un seul fragment, après les contrôles) ; mention dans la réponse en cas d'échec de la résolution Entra.
- `api/anon_auth.py` : suivi des comptes dont la résolution Entra a échoué (`entra_en_echec`).
- `.github/workflows/controles.yml` : contrôles automatiques à chaque publication (syntaxe Python et shell, YAML et JSON, liens internes, typographie, motifs de secrets).

---

## [2.17.0] : Octobre 2026

Durcissement de la stack, à la suite d'une revue externe du dépôt.

### Documentation

- `section-16-cloisonnement.md` : nouvelle section. Test de non-divulgation automatisé, endpoint de vérification d'accès, contrôle après chaque synchronisation avec alerte (contre-épreuve faite), faille du masque des droits NTFS reproduite puis corrigée, ordre des corrections avec le groupe principal, permissions du partage, durcissement de la RAG API, d'Open WebUI, du moteur d'inférence et de n8n.
- `section-01-prerequis.md` : §1.5, disque de données chiffré et liens préparés **avant** le déploiement ; parallèle VM, serveur physique et DGX Spark (non validé) ; le groupe `docker` équivaut à root.
- `section-15-securite-donnees.md` : `.env` et clés privées dans ce qu'il faut protéger ; §15.3.6 déplacement des secrets et des clés sur le disque chiffré ; piège de `docker compose restart`, qui ne relit pas le `.env`.
- `section-09-securite.md` : format du journal (empreinte HMAC, `verification: erreur`).
- Index, accueil, `README.md`, index des scripts et des workflows : §16.
- `suivi-corrections.md` : points 14 (masque), 26, 37 à 43, 45 et 46 corrigés ; 14 (SID) et auth.1 restent ouverts, avec leur ordre.

### Scripts

- `api/anon_main.py` : `/admin/verifier-acces` ; contrôle de cloisonnement en fin de `/admin/sync` (`CAS_CLOISONNEMENT`) ; juge en échec = non vérifié ; mention dans `/v1` si la réponse n'est pas vérifiée ou pas ancrée ; citations exactes, documents de même nom signalés ; erreur 503 en cas de panne de la recherche ; `/stats` sous jeton d'administration, `/health` minimal ; empreinte HMAC (`LOG_HMAC_KEY`) ; avertissement au démarrage pour les valeurs d'exemple.
- `anon_acl_resolver.py` : masque des droits lu (lecture du contenu exigée), entrées « héritables seulement » ignorées, refus tous conservés, identifiants SMB par fichier en mémoire, compteur des entrées ignorées.
- `test_cloisonnement.py`, `cas_cloisonnement.exemple.json` : nouveaux.
- `Set-AccesIndexationRAG.ps1` : affiche les permissions du partage et signale un partage restreint (code de sortie 3).
- `docker-compose.yml`, `env.example`, `deploy.sh` : `LOG_HMAC_KEY`, `CAS_CLOISONNEMENT`, `ENABLE_OLLAMA_API=false` ; `deploy.sh` vérifie le disque chiffré de §1.5 et copie le test.
- Workflows n8n : identifiant Header Auth au lieu du jeton en clair ; alerte de cloisonnement dans le workflow de synchronisation ; importés désactivés.

---

## [2.16.1] : Octobre 2026

### Documentation

- `index.md` du guide : « Ce qui vient ensuite » mis à jour. La Partie 3 était présentée comme entièrement à venir, alors que §11 à §15 sont publiées. Restent la gouvernance, le durcissement v2.17.0, les mesures de §10, le RAG visuel et une section « Du lab à la production ».

---

## [2.16.0] : Octobre 2026

### Documentation

- `section-14-purview.md` : nouvelle section. Indexation des documents SharePoint chiffrés par une étiquette Purview : mise en garde, comparaison avec Copilot, service de déchiffrement interne, double condition (permissions SharePoint et droits de l'étiquette évalués par Purview au nom de l'utilisateur, à la question), autorisations `Content.SuperUser`, `Content.DelegatedReader` et `UnifiedPolicy.Tenant.Read` avec leurs identifiants d'application, audit des applications détenant `Content.SuperUser`, pièges du SDK MIP sous Linux, matrice de validation 12 sur 12, limites et constats.
- `section-15-securite-donnees.md` : nouvelle section. Clé d'API Qdrant, chiffrement des données au repos sur un disque dédié LUKS2 avec déverrouillage par TPM et phrase secrète de secours, migration des données (`rsync -S`), pièges rencontrés, composants abandonnés, sauvegardes chiffrées (exigence, non validée).
- `section-13-sharepoint.md` : constats de gouvernance (§13.8.3) présentés avec leur origine dans le lab.
- Index du guide, index des scripts, accueil, `README.md` : §14, §15 et dossier `scripts/purview/`.
- `suivi-corrections.md` : points 23, 24 et 25 corrigés, points 30 à 36 ouverts.
- Formulation « nLPD-compliant » retirée (index du guide, §8, page des procédures, `deploy.sh`) : la stack est **conçue pour faciliter la conformité à la nLPD**. Un déploiement technique ne garantit pas à lui seul la conformité, qui dépend aussi de la gouvernance et de l'organisation.
- `section-09-securite.md` : journal des requêtes archivé en `640` au lieu de `644`, avec la commande pour les fichiers existants.
- Revue externe du dépôt (v2.15.4) prise en compte : points retenus pour la v2.17.0 dans `suivi-corrections.md`.

### Scripts

- `mip-service/` : nouveau service de déchiffrement (.NET 8, SDK MIP `Microsoft.InformationProtection.File.Ubuntu2404`, image Ubuntu 24.04), points d'accès `/dechiffrer` et `/droits`, utilisateur 10001, système de fichiers en lecture seule.
- `docker-compose.yml` : clé d'API Qdrant ; service `mip-service` dans le profil `purview` (inactif par défaut) ; variables `MIP_*` transmises à `rag-api`.
- `env.example`, `deploy.sh` : `QDRANT_API_KEY` et `MIP_TOKEN` générés, variables Purview vides par défaut, copie de `mip-service/`, contrôle de Qdrant avec la clé.
- `api/anon_main.py` : client Qdrant avec clé ; seconde condition Purview (`filtrer_purview`) sur la recherche et l'extension de contexte, cache des décisions, refus par défaut.
- `anon_indexer.py`, `anon_acl_resolver.py` : client Qdrant avec clé.
- `sp_indexer.py` : déchiffrement par `mip-service` si `MIP_URL` est renseignée, champs `chiffre`, `mip_etiquette_id`, `mip_etiquette_nom`, `mip_proprietaire` ; fichiers temporaires dans `/dev/shm` ; client Qdrant avec clé.
- `scripts/purview/` : sonde de déchiffrement, `test_mip_service.py`, `test_droits.py`.

---

## [2.15.4] : Septembre 2026

### Scripts

- `N8N/n8n-sync-corpus.json` : le courriel de quarantaine indiquait « présents sur le partage mais non indexés » et conseillait de relancer l'indexation. C'était inexact pour les fichiers dont les permissions sont illisibles : ils sont indexés, mais invisibles pour tous, et relancer l'indexation ne résout rien. Le message distingue désormais les deux causes (`acl_illisible`, `non_indexé`), avec l'action propre à chacune et la commande qui donne le statut exact de chaque fichier. Le rapport d'erreur indique aussi le code de retour de `sp_indexer.py`. Mention « sent automatically with n8n » désactivée.

### Documentation

- `section-13-sharepoint.md` : §13.8.1 corrigée. L'échec de la question générale sur la politique RH était attribué au titre du document absent des chunks. Or le test avait eu lieu pendant la panne de lecture du partage (§13.8.3), qui rendait la copie SMB du document invisible ; après correction, la même question a obtenu une réponse complète. L'hypothèse du titre reste à mesurer au §10.

---

## [2.15.3] : Septembre 2026

### Documentation

- `section-11-prerequis-ms365.md` : §11.4.1 présentait deux App Registrations, avec SharePoint en §12. Il y en a trois : `RAG-Identity-Resolver` (§11), `RAG-Teams-Reader` (§12) et `RAG-SharePoint-Indexer` (§13), avec leurs permissions exactes. Renvois périmés corrigés (SharePoint en §13, Purview à venir, libellé de log corrigé en §12, traduction de « tous les utilisateurs internes » en §13.4.4).
- Graphie harmonisée : « compte rendu », sans trait d'union, dans le texte courant (§7, §12, index du guide, index des scripts, fichiers de test). Les blocs de code, l'objet des emails produits par le pipeline et les adresses d'exemple ne sont pas modifiés.

---

## [2.15.2] : Septembre 2026

### Documentation et scripts

- Anonymisation complétée : le nom de domaine du lab apparaissait encore dans §9 (tests DENY et groupes imbriqués) et §11 (prérequis et sorties de validation). Remplacé par les repères génériques.
- Repères de domaine harmonisés dans tout le dépôt : `votre-domaine.ch` pour le nom DNS et les UPN, `DC=votre-domaine,DC=ch` pour les DN, `DOMAINE` pour le nom NetBIOS. Les variantes `domaine.ch`, `<domaine>` et `DC=domaine,DC=ch` sont remplacées dans §4, §5, §7, §9, §11, §12, `deploy.sh` et l'index des scripts.

---

## [2.15.1] : Septembre 2026

### Documentation

- `section-00-quickstart.md` : étape 1 corrigée, elle ajoutait encore `svc-rag` aux groupes métier, en contradiction avec §5.2.4 : lecture par le groupe dédié `GRP-RAG-Indexation` et `Set-AccesIndexationRAG.ps1`. Liste des fichiers à déposer mise à jour (noms `anon_`, scripts de la Partie 3). Nouvelle étape 14, facultative : mise en place condensée de la Partie 3 (Entra ID, Teams, SharePoint), avec renvois vers §11 à §13. Checklist complétée.
- `index.md` : description de §0 corrigée (« redéployer en 30 minutes » ne correspondait pas à la procédure, estimée à 2 à 3 heures).

---

## [2.15.0] : Septembre 2026

### Documentation

- `section-13-sharepoint.md` : nouvelle section. Connecteur SharePoint Online : inventaire préalable des permissions, application `RAG-SharePoint-Indexer` en `Sites.Selected` accordée site par site, sonde avant et après l'accord, règles de traduction des permissions (groupes SharePoint, groupes Microsoft 365 et leurs propriétaires, groupes AD synchronisés, « tous les internes », partages, liens), documents chiffrés détectés et non indexés, matrice de cloisonnement validée (18/18), limites et constats de gouvernance.
- `section-12-teams.md` : lien vers §13.
- `index.md` : §13 ajoutée au sommaire de la Partie 3.

### Scripts

- `sp_indexer.py` : nouveau script. Indexation SharePoint, réutilisant l'extraction et le découpage d'`indexer.py` ; permissions recalculées à chaque passage, contenu retéléchargé seulement si modifié ; fichiers chiffrés ignorés ; bibliothèque de conservation exclue ; orphelins supprimés seulement après un parcours complet ; mode simulation.
- `sharepoint/` : nouveau dossier. `Inventaire-Permissions-SharePoint.ps1`, `Inventaire-GroupesSharePoint.ps1` (authentification moderne), `Resoudre-Identifiants.ps1`, `Accorder-SitesSelected.ps1`, `sonde_sharepoint.py`.
- `api/anon_auth.py` : identifiant `entra:tous-internes` pour les comptes membres du tenant.
- `api/anon_main.py` : étape SharePoint dans `/admin/sync` (environnement restreint), index BM25 reconstruit même après une erreur partielle, citations SharePoint avec lien vers le document, fenêtres de contexte explicites pour la génération et le juge (`LLM_NUM_CTX`, `JUDGE_NUM_CTX`).
- `docker-compose.yml`, `env.example`, `deploy.sh` : variables `SP_*`, `SYNC_TIMEOUT_SHAREPOINT`, `LLM_NUM_CTX`, `JUDGE_NUM_CTX` ; `deploy.sh` copie `sp_indexer.py`.
- `N8N/n8n-sync-corpus.json` : délai d'attente de la synchronisation porté à 30 minutes.

### Relecture complète du dépôt avant publication

- Liens corrigés : les dossiers `scripts/sharepoint/` et `scripts/teams-test/` sont à la racine de `scripts/` (§12, §13, index des scripts, README).
- `section-07-n8n.md` : le résumé Teams renvoie à §12 (validé), statut et tableau mis à jour ; mention de l'étape SharePoint de `/admin/sync` et du délai de 30 minutes.
- `section-03-docker-compose.md`, `section-11-prerequis-ms365.md` : mentions « à venir » périmées remplacées par des liens vers §11 à §13.
- `index.md` (guide) : tableau de référence complété (scripts Teams, SharePoint, groupe d'indexation, workflow Teams).
- `index.md` (accueil) : « Ce qui vient ensuite » mis à jour (§11 à §13 publiées, Purview et gouvernance à venir, GPU) ; titre sans tiret cadratin.
- `docs/index.md` : page réécrite. Elle présentait des procédures unitaires par phase du plan d'apprentissage (12 phases, toutes « à venir ») qui n'ont jamais été publiées sous cette forme : elle présente maintenant le guide de déploiement par parties, et son lien avec le plan d'apprentissage en 14 phases. Ubuntu Server 26.04 au lieu de 24.04.
- `section-08-fiabilite.md` : tiret cadratin retiré d'un exemple de citation.
- `scripts/index.md` : dossiers `sharepoint` et `teams-test` ajoutés.
- Pages `index.md` ajoutées dans `scripts/N8N/`, `scripts/sharepoint/`, `scripts/teams-test/` et `guides/` : sur GitHub Pages, un lien vers un dossier sans page d'index renvoyait une erreur 404.
- Fichiers supprimés : `docs/stack-ia-locale/docker-compose.yml` (ancienne copie, non référencée, différente de `scripts/stack-ia-locale/docker-compose.yml`), `guides/toto.txt` et `scripts/teams-test/toto.md` (fichiers vides de création de dossier).

---

## [2.14.2] : Septembre 2026

### Documentation

- `section-05-connecteurs.md` : §5.2.4 réécrite. Le compte `svc-rag` n'est plus ajouté aux groupes métier : la lecture est accordée à un groupe dédié, `GRP-RAG-Indexation`, sur les dossiers à indexer, y compris les sous-dossiers et fichiers à héritage coupé. Encadré sur le cas réel du lab : retrait de `svc-rag` d'un groupe utilisé à la fois pour les droits Purview et les ACL NTFS, six fichiers devenus illisibles pour l'indexation, `autorises[]` vidés par refus par défaut, sans fuite. Remontage du partage après toute modification des groupes du compte. §5.2.1 : partage racine accordé en lecture au groupe dédié. §5.2.3 : avertissement sur l'héritage coupé.

### Scripts

- `Set-AccesIndexationRAG.ps1` : nouveau script. Création du groupe dédié, lecture seule sur les dossiers de premier niveau et sur les éléments à héritage coupé, contrôle fichier par fichier, mode vérification, liste des autres groupes du compte de service. Idempotent.

---

## [2.14.1] : Septembre 2026

### Documentation

- `section-12-teams.md` : statut passé à « validé en lab ». Déclenchement planifié validé : une nouvelle réunion a été détectée et traitée par le passage horaire du workflow n8n, sans intervention. Réserve de §12.8 retirée.
- `scripts/stack-ia-locale/index.md` : statut de la synthèse Teams mis à jour.

---

## [2.14.0] : Septembre 2026

### Documentation

- `section-12-teams.md` : nouvelle section. Synthèse des réunions Teams : réglages du tenant (dont le blocage « Transcript API access », désactivé par défaut), groupe d'adhésion à extension messagerie, application `RAG-Teams-Reader` et stratégie d'accès applicatif attribuée au groupe, code, workflow n8n, évaluation (comparatif de quatre prompts sur transcription fictive, réunion réelle), limites.
- `index.md` : §12 ajoutée au sommaire de la Partie 3.

### Scripts

- `api/teams.py` : nouveau module. Lecture des transcriptions VTT, contrôle de longueur (fenêtre de contexte explicite, refus plutôt que troncature), synthèse par le modèle local, contrôles déterministes (chiffres, responsables, données de santé), complément des échéances à partir du texte des actions, brouillon d'email.
- `api/teams_graph.py` : nouveau module. Membres du groupe d'adhésion, `getAllTranscripts`, téléchargement du VTT, fichier d'état des transcriptions traitées (identifiants seulement).
- `api/anon_main.py` : endpoints `/teams/summarize` et `/teams/sync`, journalisation `teams_summary`. Libellé du log d'authentification corrigé (« groupe(s) et identité(s) » au lieu de « groupes AD »).
- `api/Dockerfile` : copie de `teams.py` et `teams_graph.py`.
- `docker-compose.yml`, `env.example`, `deploy.sh` : variables `TEAMS_*`.
- `N8N/n8n-teams-sync.json` : nouveau workflow (synchronisation horaire, envoi du brouillon à l'organisateur, alerte administrateur). Mention n8n désactivée dans les emails.
- `teams-test/` : transcription fictive et corrigé, script de réunion à lire à deux et corrigé, scripts `test_teams_summary.py` et `test_teams_graph.py`.

---

## [2.13.0] : Septembre 2026

Début de la Partie 3 (Microsoft 365). Les scripts partagés sont modifiés de façon compatible : sans document SharePoint et avec `ENTRA_ENABLED=false`, la stack SMB se comporte exactement comme en 2.12.0. La version validée des Parties 1 et 2 reste disponible dans la Release v2.12.0.

### Documentation

- `section-11-prerequis-ms365.md` : nouvelle section. Architecture de la Partie 3, prérequis tenant et réseau, certificat, App Registration `RAG-Identity-Resolver`, mise à niveau compatible des scripts, validation en lab (non-régression SMB, protection des chunks SharePoint, résolution Entra ID).

### Scripts

- `acl_resolver.py` v4 : la détection des chunks orphelins ne concerne que les chunks `source_type` `smb` (ou sans ce champ, indexés avant la v4). Les futurs chunks SharePoint ne sont plus supprimés comme orphelins. Suppression par filtre au lieu d'un parcours limité à 500 points : un fichier orphelin de plus de 500 chunks n'était supprimé que partiellement.
- `auth.py` : extension Entra ID, désactivée par défaut (`ENTRA_ENABLED`). Résolution des groupes de l'utilisateur via Microsoft Graph (`transitiveMemberOf`), authentification de l'application par certificat (MSAL). Identifiants ajoutés au format `entra:usr:<id>` et `entra:grp:<id>`. En cas d'échec de Graph, les groupes AD sont conservés et le résultat n'est pas mis en cache. Tiret cadratin retiré d'un message de log.
- `requirements.txt` : ajout de `msal`.
- `docker-compose.yml` : variables `ENTRA_*` transmises au conteneur `rag-api`, montage en lecture seule de `/etc/rag-certs`.
- `env.example` : bloc de configuration de l'extension Entra ID.

### Corrigé

- `deploy.sh` : le `.env` généré ne contenait pas `GROUPS_CACHE_TTL`, `SYNC_PYTHON`, `SYNC_TIMEOUT_INDEXER` ni `SYNC_TIMEOUT_ACL`, transmises au conteneur depuis la 2.12.0. Docker les transmettait vides et `rag-api` échouait au démarrage (conversion d'une chaîne vide en entier). Défaut présent dans la Release v2.12.0 : un déploiement neuf par `deploy.sh` doit utiliser la version actuelle du script. Variables `ENTRA_*` ajoutées (extension désactivée).
- `deploy.sh` : le contrôle de présence porte sur `env.example` (et non plus `env_example`), seul fichier d'exemple conservé dans le dépôt.

---

## [2.12.0] : Septembre 2026

### Documentation

- `section-03` §3.6 : encadré "collection vide" corrigé : `/query` retourne HTTP 422 (aucun chunk), pas une réponse LLM sans sources. 401 vs 403 clarifiés. Adresse de test : email d'un compte AD existant requis.
- `section-03` §3.2 et `section-08` §8.6 : borne RRF corrigée de 0,016 à ~0,033 (deux listes, k=60).
- `section-05` §5.4.2 : `QDRANT_URL` (pas `QDRANT_HOST`). `SMB_SHARE` et `SMB_MOUNT` lus par `main.py`, pas par `acl_resolver.py`.
- `section-08` §8.7 : accents graves imbriqués dans l'exemple de citation UNC corrigés.
- `section-00` étape 3 : `python3.11` remplacé par `python3` (python3.11 absent des dépôts Ubuntu 26.04).
- `suivi-corrections.md` : justification du point 10 corrigée (les chunks BM25 ne repassent pas par Qdrant).
- `index.md` scripts : `fileservice-root` → `corpus-root`.
- `docker-compose.yml` : `WEBHOOK_URL` → `N8N_WEBHOOK_URL`.
- `section-09` §9.1 réécrit : Docker contourne UFW pour les ports publiés. Règles UFW 8080, 6333 et `172.18.0.0/16` supprimées (inutiles depuis 2.4.0), tableau d'exposition réelle des services, procédure de nettoyage pour les installations antérieures. Sous-sections renumérotées §9.1.1 à §9.1.6.
- `section-09` §9.1.5 : suppression des règles UFW validée en lab (chaîne interne fonctionnelle, test d'exposition des ports depuis le segment réseau de la VM).
- `section-09` §9.3.4 : port 8080 non publié (et non « restreint par UFW »).
- `section-09` §9.5.1 étape 6 : `--post-data=''` ajouté (`/admin/sync` n'accepte que POST, un GET retourne 405). Token lu depuis le `.env` au lieu d'être copié à la main.
- `section-09` §9.8 : vérifications Qdrant sur `127.0.0.1` et absence de règles UFW obsolètes ajoutées.
- `section-03` §3.7 et `section-07` §7.2.2 : commande de test de `/admin/sync` corrigée (`--post-data=''`, token lu depuis le `.env`). Renvoi du commentaire Qdrant en §3.4 mis à jour vers §9.1.2.
- `section-07` §7.2.2 : résultat attendu aligné sur la réponse réelle de l'endpoint (`indexer` et `acl_resolver` ne contiennent que `returncode`). §7.3.2 : renvoi vers la commande de §9.5.1. §7.2.7 : exemple d'email d'erreur aligné sur le contenu réel.
- `CHANGELOG.md` [2.0.0] : récursion `memberOf` attribuée à `auth.py` (et non à `acl_resolver.py`).

### Scripts

- `n8n-rappel-rotation-svc-rag.json` : étape 6 corrigée (plus de `localhost:8080`, POST depuis le réseau Compose, token lu depuis le `.env`), étape 7 alignée sur §9.5.1, renvoi vers §9.5.1. Tirets cadratins retirés de l'objet et de l'en-tête du mail.
- `n8n-sync-corpus.json` : tirets cadratins retirés des objets et en-têtes de mail. Email d'erreur : les blocs « Détail indexeur » et « Détail acl_resolver » affichaient toujours « (aucune sortie) », l'endpoint ne renvoyant pas la sortie des scripts ; remplacés par les codes de retour et les commandes pour consulter les logs et les rapports JSON.
- `docker-compose.yml` : `GROUPS_CACHE_TTL`, `SYNC_PYTHON`, `SYNC_TIMEOUT_INDEXER` et `SYNC_TIMEOUT_ACL` transmises au conteneur `rag-api` (définies dans `.env` mais ignorées jusqu'ici).
- `env.example` : `MAX_CONTEXT_CHUNKS` corrigé de 12 à 14 (valeur validée en 2.2.0), variables rangées par bloc avec commentaires, renvoi vers §9.5.1 pour la rotation de `svc-rag`.

---

## [2.11.0] : Septembre 2026

### Sécurité

**`main.py` : A1 neutralisation des délimiteurs dans `build_context`**
- `neutraliser_delimiteurs()` : neutralise `[FIN DES DONNÉES]` et variantes (accents, espaces, sans accent) en les remplaçant par des parenthèses. Remplace `→` en début de ligne par `->` pour empêcher les en-têtes de source factices.
- `_BALISE` compilé au niveau du module pour la performance.
- `import re` ajouté au niveau du module, requis par `_BALISE` (l'ancienne version importait `re` localement dans chaque fonction).

**Limite documentée :** la neutralisation ne protège pas contre les instructions en texte libre. Protection renforcée prévue après installation du GPU (modèle Qwen3 30B+).

**`main.py` : A2 ordre des contrôles dans `groundedness_check`**
- Le refus standard est testé avant l'absence de chunks. Les refus légitimes ne polluent plus le journal avec `ancree: false`.

**`main.py` : A3 validation stricte du verdict du juge**
- `result.get("ancree") is not True` : une chaîne `"false"` ou une clé absente est maintenant traitée comme `False`.

**`acl_resolver.py` : A4 exclusion des répertoires système**
- `EXCLUDE_DIR_PATTERNS` : `DfsrPrivate`, `System Volume Information`, `$RECYCLE.BIN` exclus par égalité insensible à la casse. Plus de faux positifs dans le garde-fou 20%.

### Documentation

- Point de montage `/mnt/corpus-root` et nom de partage `FileService` alignés dans `section-00`, `section-03`, `section-05`, `section-07`, `section-09`.
- Note de quarantaine corrigée dans §0, §5 et §9.6.3 : distinction entre statut `quarantaine` (organisation non identifiable) et statut `vide` (PDF scanné ou corrompu).
- §5.6.3 : rôle par défaut `en attente` (pas `utilisateur`), cohérent avec §4.2.4.
- Renvois `§9.3` corrigés en `§9.2` dans §3.4 et §3.5 (certificat CA du DC).
- §5 l.222 : `EXCLUDE_PATTERNS` corrigé en `EXCLUDE_DIR_PATTERNS`.
- `section-00` §0 étape 12 : `userPrincipalName` obligatoire (pas `sAMAccountName`) dans la configuration LDAP Open WebUI, avec note explicative.
- `section-09` §9.4.1 : `"verification": "effectuee"` ajouté à l'exemple de log. Note sur les cas où `non_effectuee` apparaît.
- `section-09` §9.5.2 : comportement corrigé sur svc-rag désactivé (garde-fou, bind LDAP, fichiers inchangés).
- `section-09` §9.6.1 : limites de la neutralisation documentées.

---

## [2.10.0] : Septembre 2026

### Documentation : corrections et mises à jour complètes

**Corrections de fond (affirmations incorrectes) :**
- `section-07-n8n.md` §7.2.3 : encadré port 8080 corrigé (non publié depuis v2.4.0).
- `section-07-n8n.md` §7.2.4 : section remplacée par renvoi vers §3.3/§3.4 (Dockerfile et volumes documentés là).
- `section-07-n8n.md` §7.2.5 : MD5 → SHA-256 tronqué. Ligne "fichier inchangé : aucun traitement" ajoutée.
- `section-05-connecteurs.md` §5.4.2 : `SMB_CREDENTIALS` supprimée (variable inexistante). `DOCUMENTATION_COLLECTION` et `DOCUMENTATION_PATHS` ajoutées.
- `section-05-connecteurs.md` §5.7.1 : extrait de code mis à jour (403 si résolution échoue).
- `section-05-connecteurs.md` §5.9 : collection `documentation` : accès selon ACL NTFS, pas accès universel.
- `section-08-fiabilite.md` §8.5 doublon → §8.6. `MAX_CONTEXT_CHUNKS` corrigé de 12 à 14.
- `section-09-securite.md` §9.8 : checklist corrigée (ligne 172.18 et port 8080 UFW).

**6 commandes `localhost:8080` remplacées** dans `section-00`, `section-03`, `section-07`, `section-09` par `docker compose exec n8n wget -qO- http://rag-api:8080/...`

**Ajouts :**
- `section-05-connecteurs.md` §5.4.2b : garde-fou 20% ACL illisibles documenté.
- `section-08-fiabilite.md` §8.7 : citations enrichies avec chemin UNC documentées.
- `section-09-securite.md` §9.7.1b : garde-fou ACL documenté avec validation lab.
- `suivi-corrections.md` : remis à jour, statuts corrigés, points ouverts précisés.

---

## [2.9.0] : Septembre 2026

### Sécurité

**Point 18 de l'audit : séparation structurelle instructions/données (main.py)**

- `get_system_prompt()` : ajout d'une règle explicite sur les balises `[DONNÉES DOCUMENTAIRES]` et `[FIN DES DONNÉES]`.
- `generate_answer()` : le contexte est désormais injecté entre ces balises dans le `prompt_user`. Toute instruction hostile dans un document indexé est traitée comme du contenu, jamais comme une instruction.
- **Validé en lab, septembre 2026 :** fichier `test.txt` contenant une instruction hostile indexé dans le corpus. La RAG API a ignoré l'instruction et répondu normalement.

### Documentation

- `section-08-fiabilite.md` : §8.3 et §8.4 corrigés. Comportement différencié `/v1` (affichage) vs `/query` (HTTP 422). Référence à Onyx CE supprimée.
- `section-09-securite.md` : §9.6.1 mis à jour avec l'implémentation réelle des balises. §9.6.2 corrigé : le juge vérifie l'ancrage, pas les URLs ni les injections. §9.6.3 corrigé : `indexer.py` ne fait pas de contrôle de contenu.

---

## [2.8.0] : Septembre 2026

### Nettoyage

**`main.py` :**
- Variables mortes supprimées : `owui_user`, `owui_email`, `owui_token`, `owui_user2`. `owui_id` conservé avec commentaire pour future corrélation dans le journal nLPD.
- Lecture redondante de `owui_email2` supprimée (doublon ligne 749).
- `except Exception as e` → `except Exception` dans `/stats` (`e` non utilisé).

**`acl_resolver.py` :**
- 5 f-strings sans variable converties en strings normales.
- `if not dry_run` redondant en phase 2 supprimé : `mettre_a_jour_qdrant` gère déjà le cas.
- Logs phase 2 enrichis avec `source_name` pour faciliter le diagnostic.

---

## [2.7.0] : Septembre 2026

### Corrigé

**`main.py` : 5 corrections suite au second audit**

- Branche fallback `search_qdrant` : `idx_min = idx_max = None` initialisés explicitement pour éviter un `NameError` sur les chunks sans `chunk_index` (indexés avant v2.3.0). Le `limit` adapté : `(idx_max - idx_min + 1) if idx_min is not None else MAX_CONTEXT_CHUNKS`.
- `enrichir_citations` déplacé après `groundedness_check` et `log_query` dans `/query` et `/v1`. Avant ce correctif, le juge et `verifier_citations` voyaient la citation enrichie `[nom.docx : \\\\serveur\\...]` au lieu de `[nom.docx]`, produisant des faux positifs `ancree: false` sur des réponses correctement sourcées.
- Docstring `build_context` mise à jour : suppression de la référence au lien cliquable et au commentaire chemin UNC devenus obsolètes.

**`acl_resolver.py` : réécriture en deux phases**

- Phase 1 : lecture complète de toutes les ACL en mémoire, sans aucune écriture dans Qdrant.
- Garde-fou 20% évalué AVANT toute écriture. Dans la version précédente, le garde-fou était placé après la boucle d'écriture : il se déclenchait après avoir déjà vidé les ACL de tout le corpus, rendant le message "abandon sans modification" faux.
- Phase 2 : écriture dans Qdrant uniquement si le seuil 20% n'est pas atteint.

---

## [2.6.0] : Septembre 2026

### Ajouté

**Chemin UNC dans les citations (`main.py`) :**
- Nouvelle fonction `enrichir_citations()` : post-traitement côté API qui remplace
  chaque citation `[nom.docx]` par `[nom.docx : `\\\\SERVEUR\\Partage\\Dossier\\`]`.
- Le chemin UNC est injecté dans un bloc code inline Markdown : non interprété par
  Open WebUI, copiable en un clic dans le presse-papiers.
- L'utilisateur colle le chemin dans la barre d'adresse de l'Explorateur Windows
  pour ouvrir directement le dossier source du document.
- Opère côté API après la génération, sans modifier le prompt ni dépendre du LLM.
- Variable `SMB_SHARE` déjà présente dans le conteneur (transmise via `docker-compose.yml`).

---

## [2.5.0] : Septembre 2026

### Sécurité

**Point 2 : `/query` laisse passer sans filtre ACL**
- `main.py` : `/query` refuse avec 403 si `user_id` ne contient pas `@`.
- `main.py` : `/query` refuse avec 403 si la résolution LDAP échoue ou retourne zéro groupe.
- `main.py` : `skip_groundedness` réservé à `ADMIN_TOKEN`. Un appelant avec `API_TOKEN` ne peut plus court-circuiter le groundedness check.

**Point 4 : token et données personnelles en clair dans les logs Docker**
- `main.py` : suppression des blocs `logger.info` de debug (en-têtes, token `Authorization`, noms, emails, `request.user`). Ces données personnelles étaient hors politique de rétention nLPD.

**Point 13 : `interdits[]` jamais vidé, ACL illisibles restent actives**
- `acl_resolver.py` : `interdits` toujours écrit dans le payload Qdrant, même vide. Un DENY retiré sur le file server est maintenant écrasé au prochain passage du résolveur.
- `acl_resolver.py` : fichier avec ACL illisible → `autorises` vidé dans Qdrant (deny by default). Avant cette correction, le fichier conservait ses anciennes ACL indéfiniment.

---

## [2.4.0] : Septembre 2026

### Sécurité

**Point 1 de l'audit : exposition LAN de Qdrant et de la RAG API (Docker bypass UFW)**

- `docker-compose.yml` : Qdrant lié à `127.0.0.1:6333` au lieu de `0.0.0.0:6333`. Le corpus n'est plus accessible depuis le LAN sans passer par la RAG API.
- `docker-compose.yml` : port 8080 (RAG API) supprimé de la section `ports`. La RAG API est joignable uniquement depuis le réseau Compose interne (`http://rag-api:8080`). L'en-tête `X-OpenWebUI-User-Email` ne peut plus être forgé depuis le LAN.
- Open WebUI : URL de connexion OpenAI mise à jour de `http://<IP-VM>:8080/v1` vers `http://rag-api:8080/v1`.
- n8n : URL du nœud `/admin/sync` déjà correcte (`http://rag-api:8080/admin/sync`).

### Modifié
- `section-03-docker-compose.md` : §3.4 mis à jour avec binding `127.0.0.1` et suppression du port 8080, note sur le contournement UFW par Docker.
- `section-09-securite.md` : §9.1 mis à jour, règles UFW corrigées (8080 et 6333 retirés), note explicite sur le fait que Docker bypass UFW via iptables.

---

## [2.3.0] : Septembre 2026

### Ajouté

**Indexation incrémentale (`indexer.py`) :**
- Comparaison `content_hash` + `embed_model` + `chunk_size` + `chunk_overlap` + `min_chunk_words` + `chunker_version` : les fichiers non modifiés sont ignorés sans appel Ollama.
- Report des ACL (`autorises`, `interdits`, `acl_updated_at`) sur les fichiers modifiés : plus de fenêtre sans ACL entre indexeur et résolveur.
- IDs de chunks déterministes + upsert : plus de fenêtre d'indisponibilité.
- `supprimer_chunks_excedentaires` via `Range(gte=nb_chunks)` sur `chunk_index` : les chunks de l'ancienne version qui n'existent plus sont supprimés proprement.
- Index de payload Qdrant créés dans `init_collection` : `source` (keyword) + `chunk_index` (integer). Idempotent, créé une seule fois par collection.
- `CHUNKER_VERSION=2` : réindexation automatique si `chunk_blocks()` est modifié.
- `MIN_CHUNK_WORDS` lu depuis l'environnement (défaut 8, corrigé de 15).
- `SUPPORTED_EXTENSIONS` partagée entre `indexer.py` et `acl_resolver.py`.
- Gestion erreurs par fichier : code de sortie 2 si erreur, pas plantage global.
- Répertoires exclus réellement élagués via `dirs[:]=` dans `os.walk` (DfsrPrivate, etc.).

**Correctifs `main.py` :**
- `chunk_index` ajouté dans `_load_collection_chunks` : l'extension de contexte fonctionne désormais quand un chunk BM25 gagne le RRF.
- Nettoyage des suites de points répétitifs dans `get_embedding()` : corrige l'erreur 500 Ollama sur les PDF avec tables des matières.

### Modifié
- `section-03-docker-compose.md` : note sur `chunk_index` dans l'index BM25.
- `section-08-fiabilite.md` : note sur `chunk_index` BM25 et nettoyage PDF.

---

## [2.2.0] : Septembre 2026

### Ajouté

**Deux collections Qdrant (documents + documentation) :**
- `indexer.py` : `get_collection_for_path()` route les fichiers vers la collection correcte selon le préfixe de chemin.
- `acl_resolver.py` : même logique, scan des orphelins sur les deux collections.
- `main.py` : recherche vectorielle sur les deux collections, fusion avant RRF, scroll d'extension de contexte dans la bonne collection.
- `section-05-connecteurs.md` : §5.8 ajouté, règles de gouvernance des collections.

**Correctifs retrieval (bugs identifiés en session) :**
- Clé RRF unique par chunk (`chunk_key = md5(text)`) au lieu du `source_id` (hash du fichier). Permet à plusieurs chunks du même fichier d'entrer dans le classement indépendamment.
- Scroll d'extension de contexte dans la bonne collection (`best_collection` déduit du chunk, non hardcodé à `documents`).
- `DOCUMENTATION_COLLECTION` et `DOCUMENTATION_PATHS` transmis aux sous-processus `indexer.py` et `acl_resolver.py` via `/admin/sync`.

**Paramètres ajustés (validés en lab) :**
- `TOP_K=20` : améliore le recall sur les gros fichiers .md.
- `CONTEXT_THRESHOLD=0.01` : adapté à l'échelle des scores RRF ([0, 0.016] avec k=60).
- `MAX_CONTEXT_CHUNKS=14` : validé en lab sur CPU (12 était insuffisant pour les documents denses).

### Modifié
- `section-03-docker-compose.md` : nouvelles variables `.env` documentées, `requirements.txt` mis à jour avec `rank-bm25`.
- `section-08-fiabilite.md` : §8.5 ajouté (retrieval hybride BM25, paramètres validés, limite sur les gros fichiers).

---

## [2.1.0] : Septembre 2026

### Ajouté

**Retrieval hybride BM25 + vectoriel :**
- `main.py` : index BM25 construit en mémoire au démarrage depuis Qdrant, fusionné avec la recherche vectorielle par Reciprocal Rank Fusion (RRF). Améliore le retrieval sur les termes exacts (noms de fichiers, acronymes, commandes, termes techniques) là où la recherche vectorielle seule échoue sur les reformulations.
- `main.py` : reconstruction automatique de l'index BM25 après chaque synchronisation réussie via `/admin/sync`.
- `requirements.txt` : ajout de `rank-bm25`.

**Plan d'apprentissage RAG local refondu (`guides/plan-apprentissage-rag-2026.docx`) :**
- Document entièrement réécrit pour refléter la stack validée en lab (septembre 2026).
- 14 phases : 12 validées sur CPU, 2 optionnelles nécessitant un tenant MS 365.
- Choix techniques réels documentés : pipeline Python custom, chunking par blocs de paragraphes, `MIN_CHUNK_WORDS=8`, `JUDGE_KEEP_ALIVE`, `warmup_judge()`, Open WebUI comme interface finale.
- Note sur la migration BM42 (Qdrant sparse vectors) au-delà de 200 000 chunks.

### Modifié
- `main.py` : prompt système corrigé (suppression de la règle contradictoire "cite le document même hors sujet"), prompt juge enrichi avec deux règles d'attribution pour détecter les hallucinations par mauvaise attribution de contexte.
- `section-03-docker-compose.md` : `requirements.txt` documenté aligné sur la version réelle (`rank-bm25`, `pdfplumber`, `python-pptx`).
- `section-08-fiabilite.md` : nouvelles règles du prompt juge documentées, note sur les limites du juge `qwen3:4b` sur CPU et stratégie GPU (`JUDGE_MODEL=qwen2.5:14b`), footer mis à jour (970 chunks).
- `index.md` (racine du repo) : stack technique mise à jour avec "retrieval hybride BM25+vectoriel (RRF)".
- `scripts/stack-ia-locale/index.md` : fonctionnalités BM25 documentées, dépendances alignées.
- `docs/stack-ia-locale/index.md` : section Scripts ajoutée avec tableau des fichiers et lien vers `scripts/stack-ia-locale/`.

---

## [2.0.0] : Septembre 2026

### Ajouté

**Guide de déploiement stack IA locale (§1 à §9) :**
- §1 Prérequis et création de la VM Ubuntu Server 26.04
- §2 Installation et configuration de vLLM (mode CPU et référence DGX Spark)
- §3 Infrastructure Docker Compose : Qdrant, n8n, RAG API FastAPI, Open WebUI
- §4 Interfaces utilisateur : Onyx CE (validation) et Open WebUI (stack finale)
- §5 Connecteurs SMB et cloisonnement documentaire par ACL NTFS
- §6 Cline : agent de codage IA connecté à Ollama
- §7 Pipelines n8n : synchronisation corpus, rappel rotation svc-rag
- §8 Fiabilité : contrôles déterministes, groundedness check, formation utilisateurs
- §9 Sécurité et durcissement : UFW, TLS LDAP, journalisation nLPD, rotation svc-rag

**Scripts Python du pipeline RAG local (répertoire `scripts/stack-ia-locale/`) :**
- `indexer.py` : indexeur v5, cascade de détection org à 5 niveaux, support `.docx`, `.pdf`, `.pptx`, `.txt`, `.md`, exclusion `DfsrPrivate`, seuil minimal chunk configurable (`MIN_CHUNK_WORDS`)
- `acl_resolver.py` : v3 avec détection des chunks orphelins, DENY explicites
- `main.py` : RAG API FastAPI complète, filtrage Qdrant par ACL NTFS, groundedness check (`qwen3:4b`), `warmup_judge()`, journalisation nLPD, endpoint `/admin/sync`
- `auth.py` : résolution LDAP email → groupes AD, récursion `memberOf`, `CERT_REQUIRED`, cache TTL
- `docker-compose.yml` : stack complète Qdrant + n8n + RAG API + Open WebUI
- `.env.example` : template de configuration commenté
- `Dockerfile` et `requirements.txt` : image `rag-api` basée sur Python 3.11-slim

**Stack validée en lab :**
- Authentification LDAP Active Directory sur port 636 (LDAPS)
- Cloisonnement documentaire par ACL NTFS : propagation des SIDs jusqu'aux chunks Qdrant, filtrage à la requête par groupes AD de l'utilisateur
- DENY explicites NTFS prioritaires sur les ALLOW (cas validé en lab)
- Groupes imbriqués AD résolus par récursion `memberOf` (3 niveaux validés)
- Journalisation nLPD : hash de la question, identité utilisateur, sources consultées
- Groundedness check : juge `qwen3:4b` avec règles d'attribution pour détecter les hallucinations par mauvaise attribution de contexte

### Modifié
- `index.md` (racine) : description de la stack opérationnelle, liens corrigés vers les index de docs et scripts, section "Ce qui vient ensuite" (MS 365, Purview)

---

## [1.0.0] : Août 2026

### Ajouté
- Guide décisionnel « IA locale pour PME suisse » v1.0 (août 2026) : 25 pages, sources vérifiées
- Plan d'apprentissage RAG local : 12 phases, architecture LABO-G9 + VM-RAG-LAB
- Structure initiale du repo : `docs/`, `guides/`, `scripts/`
- Index des procédures opérationnelles à venir

---

*Les prochaines entrées seront ajoutées au fur et à mesure des publications.*
