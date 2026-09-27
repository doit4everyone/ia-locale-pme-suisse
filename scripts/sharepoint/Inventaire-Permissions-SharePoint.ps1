<#
.SYNOPSIS
  Inventaire en lecture seule des permissions des bibliothèques de documents
  SharePoint Online, via Microsoft Graph.

.DESCRIPTION
  Pour chaque site : bibliothèques de documents, dossiers et fichiers, et
  permissions de chaque élément telles que Graph les expose (utilisateur,
  groupe Entra, groupe SharePoint, lien de partage). C'est la vue qu'aura
  l'indexeur SharePoint du pipeline RAG.

  Aucune modification n'est faite. Résultat : un fichier CSV (séparateur ;)
  ouvrable dans Excel.

  Les membres des groupes SharePoint (Propriétaires, Membres, Visiteurs)
  ne sont pas exposés par Graph : voir Inventaire-GroupesSharePoint.ps1.

.PARAMETER Sites
  URL complètes des sites à inventorier.

.PARAMETER Sortie
  Chemin du fichier CSV produit.

.PARAMETER ProfondeurMax
  Profondeur maximale de parcours des dossiers (défaut : 10).

.EXAMPLE
  .\Inventaire-Permissions-SharePoint.ps1 `
    -Sites "https://contoso.sharepoint.com/sites/Direction","https://contoso.sharepoint.com/" `
    -Sortie "C:\Temp\permissions-sharepoint.csv"

.NOTES
  Module requis : Microsoft.Graph.Authentication
    Install-Module Microsoft.Graph.Authentication -Scope AllUsers
  Connexion déléguée, compte administrateur, portées Sites.Read.All et Files.Read.All.
#>
param(
    [Parameter(Mandatory = $true)][string[]]$Sites,
    [Parameter(Mandatory = $true)][string]$Sortie,
    [int]$ProfondeurMax = 10
)

$ErrorActionPreference = "Stop"
Import-Module Microsoft.Graph.Authentication

Connect-MgGraph -Scopes "Sites.Read.All", "Files.Read.All" -NoWelcome | Out-Null

$resultats = New-Object System.Collections.Generic.List[object]

function Get-GraphTout([string]$Uri) {
    # Parcourt toutes les pages d'une réponse Graph
    $elements = @()
    while ($Uri) {
        $r = Invoke-MgGraphRequest -Method GET -Uri $Uri
        if ($r.value) { $elements += $r.value }
        $Uri = $r.'@odata.nextLink'
    }
    return $elements
}

function Get-TypeAccord($p) {
    if ($p.link) { return "Lien de partage" }
    $g = $p.grantedToV2
    if ($g) {
        if ($g.siteGroup) { return "Groupe SharePoint" }
        if ($g.group)     { return "Groupe Entra" }
        if ($g.user)      { return "Utilisateur" }
        if ($g.siteUser)  { return "Utilisateur SharePoint" }
    }
    if ($p.grantedToIdentitiesV2) { return "Plusieurs identités" }
    return "Inconnu"
}

function Get-Identite($p) {
    $g = $p.grantedToV2
    if ($g) {
        foreach ($cle in "siteGroup", "group", "user", "siteUser") {
            if ($g.$cle) {
                return [pscustomobject]@{
                    Nom   = $g.$cle.displayName
                    Id    = $g.$cle.id
                    Email = $g.$cle.email
                    Login = $g.$cle.loginName
                }
            }
        }
    }
    if ($p.grantedToIdentitiesV2) {
        $noms = ($p.grantedToIdentitiesV2 | ForEach-Object {
            if ($_.user) { $_.user.displayName } elseif ($_.group) { $_.group.displayName } elseif ($_.siteUser) { $_.siteUser.displayName }
        }) -join ", "
        return [pscustomobject]@{ Nom = $noms; Id = ""; Email = ""; Login = "" }
    }
    return [pscustomobject]@{ Nom = ""; Id = ""; Email = ""; Login = "" }
}

function Add-Permissions($Site, $Bibliotheque, $DriveId, $Element, $Chemin) {
    $type = if ($Element.root) { "Racine" } elseif ($Element.folder) { "Dossier" } else { "Fichier" }
    try {
        $perms = Get-GraphTout "https://graph.microsoft.com/v1.0/drives/$DriveId/items/$($Element.id)/permissions"
    } catch {
        $resultats.Add([pscustomobject]@{
            Site = $Site; Bibliotheque = $Bibliotheque; Chemin = $Chemin; Type = $type
            TypeAccord = "ERREUR"; Identite = $_.Exception.Message; Id = ""; Email = ""; Login = ""
            Roles = ""; PorteeLien = ""; HeriteDe = ""
        })
        return
    }
    foreach ($p in $perms) {
        $id = Get-Identite $p
        $resultats.Add([pscustomobject]@{
            Site         = $Site
            Bibliotheque = $Bibliotheque
            Chemin       = $Chemin
            Type         = $type
            TypeAccord   = Get-TypeAccord $p
            Identite     = $id.Nom
            Id           = $id.Id
            Email        = $id.Email
            Login        = $id.Login
            Roles        = ($p.roles -join ", ")
            PorteeLien   = $(if ($p.link) { $p.link.scope } else { "" })
            HeriteDe     = $(if ($p.inheritedFrom) { $p.inheritedFrom.path } else { "" })
        })
    }
}

function Explorer($Site, $Bibliotheque, $DriveId, $ElementId, $Chemin, $Profondeur) {
    if ($Profondeur -gt $ProfondeurMax) { return }
    $enfants = Get-GraphTout "https://graph.microsoft.com/v1.0/drives/$DriveId/items/$ElementId/children"
    foreach ($e in $enfants) {
        $cheminEnfant = "$Chemin/$($e.name)"
        Add-Permissions $Site $Bibliotheque $DriveId $e $cheminEnfant
        if ($e.folder) {
            Explorer $Site $Bibliotheque $DriveId $e.id $cheminEnfant ($Profondeur + 1)
        }
    }
}

foreach ($url in $Sites) {
    $u = [Uri]$url
    $chemin = $u.AbsolutePath.TrimEnd("/")
    $siteUri = if ($chemin) { "https://graph.microsoft.com/v1.0/sites/$($u.Host):$chemin" } else { "https://graph.microsoft.com/v1.0/sites/$($u.Host)" }
    Write-Host "Site : $url" -ForegroundColor Cyan
    try {
        $site = Invoke-MgGraphRequest -Method GET -Uri $siteUri
    } catch {
        Write-Warning "  Site inaccessible : $($_.Exception.Message)"
        continue
    }
    $drives = Get-GraphTout "https://graph.microsoft.com/v1.0/sites/$($site.id)/drives"
    foreach ($d in $drives) {
        Write-Host "  Bibliothèque : $($d.name)"
        $racine = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/drives/$($d.id)/root"
        Add-Permissions $url $d.name $d.id $racine "/"
        Explorer $url $d.name $d.id $racine.id "" 1
    }
}

$encodage = if ($PSVersionTable.PSVersion.Major -ge 6) { "utf8BOM" } else { "UTF8" }
$resultats | Export-Csv -Path $Sortie -Delimiter ";" -NoTypeInformation -Encoding $encodage
Write-Host ""
Write-Host "$($resultats.Count) permission(s) exportée(s) dans $Sortie" -ForegroundColor Green

Disconnect-MgGraph | Out-Null
