<#
.SYNOPSIS
  Accorde à une application disposant de Sites.Selected un accès en lecture
  seule à une liste précise de sites SharePoint, puis affiche les accès
  applicatifs de chaque site.

.DESCRIPTION
  Sites.Selected ne donne accès à aucun site tant qu'un accès n'est pas
  accordé site par site. Ce script fait cet accord, via Microsoft Graph,
  avec le rôle « read » uniquement.

  Avec -Lister, le script n'accorde rien et affiche seulement les accès
  applicatifs existants de chaque site.

.EXAMPLE
  .\Accorder-SitesSelected.ps1 -AppId "<ID-APPLICATION>" -AppNom "RAG-SharePoint-Indexer" `
    -Sites "https://contoso.sharepoint.com/sites/RH","https://contoso.sharepoint.com/"

.EXAMPLE
  .\Accorder-SitesSelected.ps1 -AppId "<ID-APPLICATION>" -AppNom "RAG-SharePoint-Indexer" `
    -Sites "https://contoso.sharepoint.com/sites/RH" -Lister

.NOTES
  Module requis : Microsoft.Graph.Authentication. Connexion déléguée avec un
  compte administrateur, portée Sites.FullControl.All (nécessaire pour gérer
  les accès des applications à un site). À lancer dans une session où le
  module SharePoint Online n'a pas été chargé.
#>
param(
    [Parameter(Mandatory = $true)][string]$AppId,
    [Parameter(Mandatory = $true)][string]$AppNom,
    [Parameter(Mandatory = $true)][string[]]$Sites,
    [switch]$Lister
)

$ErrorActionPreference = "Stop"
Import-Module Microsoft.Graph.Authentication
Connect-MgGraph -Scopes "Sites.FullControl.All" -NoWelcome | Out-Null

foreach ($url in $Sites) {
    $u = [Uri]$url
    $chemin = $u.AbsolutePath.TrimEnd("/")
    $siteUri = if ($chemin) { "https://graph.microsoft.com/v1.0/sites/$($u.Host):$chemin" } else { "https://graph.microsoft.com/v1.0/sites/$($u.Host)" }
    Write-Host "Site : $url" -ForegroundColor Cyan
    try {
        $site = Invoke-MgGraphRequest -Method GET -Uri $siteUri
    } catch {
        Write-Warning "  Site introuvable : $($_.Exception.Message)"
        continue
    }

    $existants = (Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/sites/$($site.id)/permissions").value
    $dejaAccorde = $existants | Where-Object {
        $_.grantedToIdentitiesV2.application.id -contains $AppId -or $_.grantedToIdentities.application.id -contains $AppId
    }

    if (-not $Lister) {
        if ($dejaAccorde) {
            Write-Host "  Accès déjà accordé à $AppNom" -ForegroundColor Yellow
        } else {
            $corps = @{
                roles = @("read")
                grantedToIdentities = @(@{ application = @{ id = $AppId; displayName = $AppNom } })
            } | ConvertTo-Json -Depth 5
            Invoke-MgGraphRequest -Method POST -Uri "https://graph.microsoft.com/v1.0/sites/$($site.id)/permissions" `
                -Body $corps -ContentType "application/json" | Out-Null
            Write-Host "  Lecture accordée à $AppNom" -ForegroundColor Green
        }
        $existants = (Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/sites/$($site.id)/permissions").value
    }

    if (-not $existants) {
        Write-Host "  Aucun accès applicatif"
    }
    foreach ($p in $existants) {
        $apps = @($p.grantedToIdentitiesV2.application) + @($p.grantedToIdentities.application) |
            Where-Object { $_ } | ForEach-Object { "$($_.displayName) ($($_.id))" } | Select-Object -Unique
        Write-Host "  - $($apps -join ', ') : $($p.roles -join ', ')"
    }
}

Disconnect-MgGraph | Out-Null
