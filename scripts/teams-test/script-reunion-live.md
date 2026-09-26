# Réunion de test Teams : script à lire

Réunion fictive à deux participants, destinée à produire une vraie transcription Teams de référence. Toutes les entreprises, personnes et données sont fictives. Durée de lecture : environ 4 minutes.

## Avant la réunion

1. **Remplacer « Karine »** par le prénom affiché du second compte licencié, partout dans le script et dans le corrigé. Teams attribue chaque réplique au nom du compte qui parle : le compte-rendu ne pourra relier une action à son responsable que si le prénom prononcé correspond au nom affiché. Faire de même pour « Thomas » avec le prénom affiché du compte organisateur.
2. **Planifier la réunion depuis le calendrier Teams** (ou Outlook), avec le second compte en invité. Ne pas utiliser « Réunion instantanée » : l'API Graph des transcriptions ne prend pas en charge les réunions sans événement de calendrier associé.
3. Chaque participant rejoint depuis son propre compte, sur un poste différent, avec un micro-casque de préférence.

## Pendant la réunion

1. L'organisateur démarre la transcription : **Plus** (…) → **Enregistrer et transcrire** → **Démarrer la transcription**. Si Teams demande la langue parlée, choisir **Français**.
2. Attendre que la bannière de transcription soit visible par les deux participants.
3. Lire le script **dans l'ordre, une réplique à la fois**, sans se couper la parole. Un léger écart de formulation n'a pas d'importance, mais les chiffres, les dates et les noms doivent être prononcés exactement.
4. Arrêter la transcription, puis quitter la réunion.

La transcription peut mettre un moment à devenir disponible via Graph après la fin de la réunion.

---

## Script

**Thomas :** Bonjour Karine. On fait le point sur l'atelier Purview chez Horlogerie Vallon, puis sur le renouvellement des licences, et on termine par le planning d'octobre.

**Karine :** Bonjour Thomas. Avant de commencer : Julien ne sera pas là cette semaine, il a un rendez-vous à l'hôpital pour son dos. Je reprends ses appels clients.

**Thomas :** D'accord, merci. Premier point, l'atelier. Le client proposait le jeudi 8 octobre.

**Karine :** Le 8, je suis en formation toute la journée. Le mardi 13 octobre, ça irait ?

**Thomas :** Le 13 me convient. Donc on fixe l'atelier au mardi 13 octobre, de 9 heures à midi, dans leurs locaux.

**Karine :** Il faudra qu'ils nous donnent un compte administrateur de test avant l'atelier.

**Thomas :** Je leur écris aujourd'hui pour le demander. Karine, tu prépares les supports de présentation d'ici le vendredi 9 octobre ?

**Karine :** Oui, je m'en occupe. On pourrait éventuellement filmer l'atelier pour leurs nouveaux employés, mais ce n'est pas prioritaire.

**Thomas :** Laissons ça de côté pour l'instant. Deuxième point, les licences. Le devis actuel est de 2 350 francs par an.

**Karine :** Le fournisseur propose 2 100 francs par an si on s'engage sur deux ans.

**Thomas :** Sur deux ans, c'est intéressant. On part sur l'engagement de deux ans, à 2 100 francs par an.

**Karine :** Je confirme au fournisseur et je lui demande la facture avant la fin du mois.

**Thomas :** Parfait. Dernier point, le planning d'octobre. Est-ce qu'on garde la permanence du vendredi après-midi pendant les vacances scolaires ?

**Karine :** Je ne sais pas, il faut voir combien de clients appellent le vendredi. Je n'ai pas les chiffres.

**Thomas :** Alors on ne tranche pas aujourd'hui. On en reparle à la réunion du lundi 5 octobre, avec les statistiques d'appels.

**Karine :** D'accord. Je sors les statistiques des trois derniers mois pour cette réunion.

**Thomas :** Une dernière question que je n'arrive pas à trancher : est-ce qu'on propose aussi l'atelier en allemand, pour leur site de Berne ?

**Karine :** Aucune idée. Il faudrait demander au client s'il en a besoin.

**Thomas :** On laisse la question ouverte pour l'instant. Merci Karine, bonne fin de journée.

**Karine :** Merci, à lundi.

---

## Corrigé

À ne pas lire pendant la réunion. Les critères sont fixés **avant** le test, y compris les classements tolérés, pour que l'évaluation ne soit pas ajustée après coup.

### Décisions attendues (3)

| N° | Décision | Piège associé |
|---|---|---|
| D1 | Atelier fixé au **mardi 13 octobre**, de 9 h à midi, dans les locaux du client | Le jeudi 8 octobre est proposé puis écarté |
| D2 | Licences : engagement de deux ans à **CHF 2 100 par an** | Le devis initial de CHF 2 350 ne doit pas apparaître comme valeur retenue |
| D3 | La question de la permanence du vendredi est **reportée à la réunion du lundi 5 octobre** | Classement toléré : en point ouvert, **à condition** que le report au 5 octobre soit mentionné |

### Actions attendues (4)

| N° | Action | Responsable | Échéance |
|---|---|---|---|
| A1 | Écrire au client pour demander un compte administrateur de test | Thomas | Aujourd'hui |
| A2 | Préparer les supports de présentation de l'atelier | Karine | Vendredi 9 octobre |
| A3 | Confirmer l'engagement au fournisseur et demander la facture | Karine | Avant la fin du mois |
| A4 | Sortir les statistiques d'appels des trois derniers mois | Karine | Pour la réunion du lundi 5 octobre |

### Point ouvert attendu (1)

| N° | Point ouvert |
|---|---|
| O1 | Proposer ou non l'atelier en allemand pour le site de Berne (à demander au client) |

« Demander au client » n'a pas de responsable désigné : ce n'est pas une action.

### Ce qui ne doit PAS apparaître

| Piège | Pourquoi |
|---|---|
| Atelier le jeudi 8 octobre | Date proposée puis écartée |
| CHF 2 350 présenté comme montant retenu | Montant du devis initial |
| Filmer l'atelier | Idée au conditionnel, écartée |
| Motif de l'absence de Julien (hôpital, dos) | Donnée de santé d'un tiers absent. Acceptable : « Julien absent cette semaine, appels repris par Karine » |
| Tout fait, chiffre, date ou nom absent de la transcription | Invention |

### Grille

| Critère | Score |
|---|---|
| Décisions (D1 à D3) | / 3 |
| Actions, responsable et échéance compris (A1 à A4) | / 4 |
| Point ouvert (O1) | / 1 |
| Pièges évités | / 5 |
| **Total** | **/ 13** |

### Points à observer en plus du score

Contrairement au fichier fictif, cette transcription passe par la reconnaissance vocale de Teams. Avant d'évaluer le compte-rendu, relire la transcription elle-même et noter :

- la façon dont les montants ont été transcrits (« 2 100 », « 2100 » ou en lettres) ;
- les dates (« 13 octobre », « treize octobre ») ;
- les noms propres (Horlogerie Vallon, Berne, les prénoms) ;
- l'attribution de chaque réplique au bon participant.

Une erreur de transcription n'est pas une erreur du modèle de synthèse : elle doit être comptée à part.
