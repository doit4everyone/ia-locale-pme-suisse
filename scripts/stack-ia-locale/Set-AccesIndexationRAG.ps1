<#
.SYNOPSIS
  Donne au compte d'indexation RAG un accès en lecture seule, par un groupe
  dédié, à tous les dossiers à indexer d'un partage, y compris les
  sous-dossiers et fichiers dont l'héritage est coupé.

.DESCRIPTION
  Guide de déploiement stack IA locale, §5.2.4.

  1. Crée le groupe dédié s'il n'existe pas et y ajoute le compte de service
     (nécessite le module ActiveDirectory ; sinon, le groupe doit exister).
  2. Accorde la lecture (RX) à ce groupe sur chaque dossier de premier niveau
     de la racine, sauf ceux exclus, avec héritage vers le contenu.
  3. Recherche les sous-dossiers et fichiers dont l'héritage est coupé : une
     permission posée sur le dossier parent ne les atteint pas. Accorde la
     lecture sur chacun.
  4. Vérifie, fichier par fichier, que le groupe a bien la lecture partout.
  5. Liste les autres groupes du compte de service : une fois la lecture en
     place, ils ne sont plus nécessaires à l'indexation.
  6. Affiche les permissions du partage SMB et signale un partage plus
     restrictif que les NTFS : le RAG n'applique que les NTFS.

  Le périmètre de l'indexation devient ainsi explicite : ce sont les dossiers
  où le groupe a la lecture, et rien d'autre.

  Idempotent : un droit déjà présent n'est pas ajouté une seconde fois.
  À relancer après toute création de dossier à héritage coupé (le rapport de
  synchronisation du RAG le signale par des fichiers « acl_illisible »).

.PARAMETER Racine
  Chemin local de la racine du partage indexé, par exemple D:\FileService.

.PARAMETER Exclure
  Dossiers de premier niveau à ne pas indexer (dossiers personnels, etc.).

.PARAMETER Groupe
  Nom du groupe dédié (défaut : GRP-RAG-Indexation).

.PARAMETER CompteService
  Compte d'indexation (défaut : svc-rag).

.PARAMETER OuGroupe
  OU de création du groupe. Par défaut, l'OU du compte de service.

.PARAMETER Verifier
  N'applique rien : vérifie et affiche ce qui manque.

.EXAMPLE
  .\Set-AccesIndexationRAG.ps1 -Racine "D:\FileService" -Exclure "UTILISATEURS" -Verifier

.EXAMPLE
  .\Set-AccesIndexationRAG.ps1 -Racine "D:\FileService" -Exclure "UTILISATEURS"

.NOTES
  À exécuter en administrateur sur le serveur de fichiers.
#>
param(
    [Parameter(Mandatory = $true)][string]$Racine,
    [string[]]$Exclure = @(),
    [string]$Groupe = "GRP-RAG-Indexation",
    [string]$CompteService = "svc-rag",
    [string]$OuGroupe = "",
    [switch]$Verifier
)

$ErrorActionPreference = "Stop"
$Domaine = $env:USERDOMAIN
$lecture = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute
$mode = if ($Verifier) { "VÉRIFICATION (aucune modification)" } else { "APPLICATION" }
Write-Host "Racine : $Racine  |  Groupe : $Domaine\$Groupe  |  Mode : $mode" -ForegroundColor Cyan

# ─────────────────────────────────────────
# 1. Groupe dédié
# ─────────────────────────────────────────
$moduleAD = [bool](Get-Module -ListAvailable ActiveDirectory)
if ($moduleAD) {
    Import-Module ActiveDirectory
    $g = Get-ADGroup -Filter "Name -eq '$Groupe'" -ErrorAction SilentlyContinue
    if (-not $g) {
        if ($Verifier) {
            Write-Warning "Le groupe $Groupe n'existe pas."
        } else {
            if (-not $OuGroupe) {
                $OuGroupe = (Get-ADUser $CompteService).DistinguishedName -replace '^CN=[^,]+,', ''
            }
            New-ADGroup -Name $Groupe -GroupScope Global -GroupCategory Security -Path $OuGroupe `
                -Description "Lecture seule des dossiers indexés par le RAG"
            Write-Host "Groupe créé : $Groupe ($OuGroupe)" -ForegroundColor Green
        }
    }
    $membres = @(Get-ADGroupMember $Groupe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty SamAccountName)
    if ($membres -notcontains $CompteService) {
        if ($Verifier) {
            Write-Warning "$CompteService n'est pas membre de $Groupe."
        } else {
            Add-ADGroupMember -Identity $Groupe -Members $CompteService
            Write-Host "$CompteService ajouté à $Groupe" -ForegroundColor Green
        }
    }
} else {
    Write-Warning "Module ActiveDirectory absent : le groupe $Groupe doit déjà exister, avec $CompteService comme membre."
}

try {
    $sid = (New-Object System.Security.Principal.NTAccount($Domaine, $Groupe)).Translate(
        [System.Security.Principal.SecurityIdentifier])
} catch {
    if ($Verifier) { Write-Warning "Groupe introuvable : vérification impossible."; exit 1 }
    throw "Groupe $Domaine\$Groupe introuvable. Le créer, puis relancer."
}

function Test-Lecture([string]$Chemin) {
    $regles = (Get-Acl -LiteralPath $Chemin).GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])
    foreach ($r in $regles) {
        if ($r.IdentityReference -eq $sid -and $r.AccessControlType -eq "Allow" -and
            (($r.FileSystemRights -band $lecture) -eq $lecture)) { return $true }
    }
    return $false
}

function Grant-Lecture([string]$Chemin, [bool]$EstDossier) {
    $droit = if ($EstDossier) { "(OI)(CI)RX" } else { "RX" }
    $sortie = & icacls $Chemin /grant "${Domaine}\${Groupe}:$droit" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "icacls a échoué sur $Chemin : $sortie" }
}

# ─────────────────────────────────────────
# 2. et 3. Dossiers de premier niveau et éléments à héritage coupé
# ─────────────────────────────────────────
$dossiers = Get-ChildItem -LiteralPath $Racine -Directory | Where-Object { $Exclure -notcontains $_.Name }
Write-Host "`nDossiers indexés : $(($dossiers | Select-Object -ExpandProperty Name) -join ', ')"
if ($Exclure) { Write-Host "Dossiers exclus  : $($Exclure -join ', ')" }

$cibles = New-Object System.Collections.Generic.List[object]
foreach ($d in $dossiers) {
    $cibles.Add($d)
    Get-ChildItem -LiteralPath $d.FullName -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { (Get-Acl -LiteralPath $_.FullName).AreAccessRulesProtected } |
        ForEach-Object { $cibles.Add($_) }
}

$ajouts = 0
Write-Host "`nPoints d'application du droit (dossiers de premier niveau et héritage coupé) :"
foreach ($c in $cibles) {
    $estDossier = $c.PSIsContainer
    $protege = (Get-Acl -LiteralPath $c.FullName).AreAccessRulesProtected
    $libelle = if ($protege) { "héritage coupé" } else { "hérite" }
    if (Test-Lecture $c.FullName) {
        Write-Host "  OK        $($c.FullName)  ($libelle)"
    } elseif ($Verifier) {
        Write-Host "  MANQUANT  $($c.FullName)  ($libelle)" -ForegroundColor Yellow
    } else {
        Grant-Lecture $c.FullName $estDossier
        $ajouts++
        Write-Host "  AJOUTÉ    $($c.FullName)  ($libelle)" -ForegroundColor Green
    }
}

# ─────────────────────────────────────────
# 4. Contrôle fichier par fichier
# ─────────────────────────────────────────
Write-Host "`nContrôle de tous les fichiers..."
$sansAcces = New-Object System.Collections.Generic.List[string]
$total = 0
foreach ($d in $dossiers) {
    Get-ChildItem -LiteralPath $d.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $total++
        if (-not (Test-Lecture $_.FullName)) { $sansAcces.Add($_.FullName) }
    }
}
Write-Host "  $total fichier(s) contrôlé(s), $($sansAcces.Count) sans lecture pour $Groupe"
foreach ($f in $sansAcces) { Write-Host "    $f" -ForegroundColor Yellow }

# ─────────────────────────────────────────
# 5. Autres groupes du compte de service
# ─────────────────────────────────────────
if ($moduleAD) {
    $autres = Get-ADPrincipalGroupMembership $CompteService |
        Where-Object { $_.Name -ne $Groupe -and $_.Name -notlike "Utilisateurs du domaine" -and $_.Name -ne "Domain Users" } |
        Select-Object -ExpandProperty Name
    if ($autres) {
        Write-Host "`nAutres groupes de $CompteService :" -ForegroundColor Cyan
        $autres | ForEach-Object { Write-Host "  $_" }
        Write-Host "Une fois la synchronisation du RAG validée sans « acl_illisible », ces appartenances"
        Write-Host "ne sont plus nécessaires à l'indexation et peuvent être retirées (droits hérités"
        Write-Host "au-delà du partage : sites SharePoint, étiquettes Purview, applications)."
    }
}

# ─────────────────────────────────────────
# 6. Permissions du partage (lecture seule, dans les deux modes)
# ─────────────────────────────────────────
# Le RAG ne lit que les permissions NTFS. Sous Windows, l'accès réseau exige
# AUSSI les permissions du partage. Si le partage est plus restrictif que les
# NTFS, le RAG ouvre plus que le réseau : à signaler.
Write-Host "`nPermissions du partage :"
$racineNorm = $Racine.TrimEnd('\')
# Les partages administratifs (C$, D$, ADMIN$), réservés aux administrateurs,
# couvrent tout le volume : ils sont ignorés, ils ne servent pas aux utilisateurs.
$partages = Get-SmbShare -ErrorAction SilentlyContinue | Where-Object {
    -not $_.Special -and $_.Name -notlike '*$' -and
    $_.Path -and ($racineNorm -ieq $_.Path.TrimEnd('\') -or $racineNorm -ilike ($_.Path.TrimEnd('\') + '\*'))
}
$partageRestreint = $false
if (-not $partages) {
    Write-Warning "Aucun partage SMB trouvé pour $Racine : vérifier manuellement (Get-SmbShare)."
} else {
    $ouverts = @('Everyone', 'Tout le monde', 'Authenticated Users', 'Utilisateurs authentifiés',
                 'Domain Users', 'Utilisateurs du domaine')
    foreach ($p in $partages) {
        $acces = Get-SmbShareAccess -Name $p.Name
        foreach ($a in $acces) {
            Write-Host ("  {0,-12} {1,-45} {2,-6} {3}" -f $p.Name, $a.AccountName, $a.AccessControlType, $a.AccessRight)
        }
        $large = $acces | Where-Object {
            $_.AccessControlType -eq 'Allow' -and $_.AccessRight -in @('Full', 'Change', 'Read') -and
            ($ouverts -contains ($_.AccountName -split '\\')[-1])
        }
        $refus = $acces | Where-Object { $_.AccessControlType -eq 'Deny' }
        if (-not $large -or $refus) {
            $partageRestreint = $true
            Write-Warning (("Partage {0} : restreint à certains comptes, ou avec des refus. Le RAG applique " +
                           "les seules permissions NTFS : un utilisateur exclu par le partage mais autorisé " +
                           "par les NTFS pourrait interroger ces documents. Aligner le partage sur une " +
                           "ouverture large (restriction par les NTFS), ou restreindre les NTFS d'autant.") -f $p.Name)
        } else {
            Write-Host "  → ouverture large, restriction par les NTFS : configuration attendue par le RAG." -ForegroundColor Green
        }
    }
}

Write-Host ""
if ($Verifier) {
    Write-Host "Vérification terminée : aucune modification." -ForegroundColor Cyan
} else {
    Write-Host "$ajouts droit(s) ajouté(s)." -ForegroundColor Cyan
    Write-Host "Sur la VM : remonter le partage (la session SMB garde l'ancien jeton du compte), puis /admin/sync."
}
if ($sansAcces.Count -gt 0) { exit 2 }
if ($partageRestreint) { exit 3 }
