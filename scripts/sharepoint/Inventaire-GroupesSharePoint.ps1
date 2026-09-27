<#
.SYNOPSIS
  Inventaire en lecture seule des groupes SharePoint (Propriétaires, Membres,
  Visiteurs, etc.) et de leurs membres, pour chaque site.

.DESCRIPTION
  Complète Inventaire-Permissions-SharePoint.ps1 : Graph indique qu'un groupe
  SharePoint a accès à un élément, mais pas qui en est membre. Ce script
  donne la composition de chaque groupe. Un membre peut être un utilisateur,
  un groupe Entra ou un groupe Microsoft 365 : la colonne Membre contient
  alors son nom de connexion (claim).

  Aucune modification n'est faite. Résultat : un fichier CSV (séparateur ;).

.PARAMETER AdminUrl
  URL du centre d'administration SharePoint, de la forme
  https://<tenant>-admin.sharepoint.com

.EXAMPLE
  .\Inventaire-GroupesSharePoint.ps1 -AdminUrl "https://contoso-admin.sharepoint.com" `
    -Sites "https://contoso.sharepoint.com/sites/Direction" `
    -Sortie "C:\Temp\groupes-sharepoint.csv"

.NOTES
  À exécuter dans Windows PowerShell 5.1 (le module SharePoint Online est
  prévu pour cette version).
  Module requis : Microsoft.Online.SharePoint.PowerShell
    Install-Module Microsoft.Online.SharePoint.PowerShell -Scope AllUsers
#>
param(
    [Parameter(Mandatory = $true)][string]$AdminUrl,
    [Parameter(Mandatory = $true)][string[]]$Sites,
    [Parameter(Mandatory = $true)][string]$Sortie
)

$ErrorActionPreference = "Stop"
Import-Module Microsoft.Online.SharePoint.PowerShell -DisableNameChecking
# Authentification moderne explicite : par défaut, Connect-SPOService utilise
# l'authentification héritée, refusée par la plupart des tenants actuels
# (valeurs de sécurité par défaut, accès conditionnel), avec pour seul
# message « Could not connect to SharePoint Online ».
Connect-SPOService -Url $AdminUrl -ModernAuth $true `
  -AuthenticationUrl "https://login.microsoftonline.com/organizations"

$resultats = New-Object System.Collections.Generic.List[object]

foreach ($url in $Sites) {
    Write-Host "Site : $url" -ForegroundColor Cyan
    try {
        $groupes = Get-SPOSiteGroup -Site $url
    } catch {
        Write-Warning "  Site inaccessible : $($_.Exception.Message)"
        continue
    }
    foreach ($g in $groupes) {
        $roles = ($g.Roles -join ", ")
        if (-not $g.Users -or $g.Users.Count -eq 0) {
            $resultats.Add([pscustomobject]@{ Site = $url; Groupe = $g.Title; Roles = $roles; Membre = "(vide)" })
            continue
        }
        foreach ($m in $g.Users) {
            $resultats.Add([pscustomobject]@{ Site = $url; Groupe = $g.Title; Roles = $roles; Membre = $m })
        }
    }
}

$resultats | Export-Csv -Path $Sortie -Delimiter ";" -NoTypeInformation -Encoding UTF8
Write-Host ""
Write-Host "$($resultats.Count) ligne(s) exportée(s) dans $Sortie" -ForegroundColor Green

Disconnect-SPOService
