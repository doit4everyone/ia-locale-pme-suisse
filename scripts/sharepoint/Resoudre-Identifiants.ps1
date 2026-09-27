<#
.SYNOPSIS
  Résout en noms lisibles les identifiants Entra (GUID) trouvés dans les
  inventaires SharePoint. Lecture seule.

.EXAMPLE
  .\Resoudre-Identifiants.ps1 -Ids "<GUID-1>","<GUID-2>_o"

.NOTES
  Module requis : Microsoft.Graph.Authentication. À lancer dans une session
  PowerShell où le module SharePoint Online n'a pas été chargé.
#>
param([Parameter(Mandatory = $true)][string[]]$Ids)

$ErrorActionPreference = "Stop"
Import-Module Microsoft.Graph.Authentication
Connect-MgGraph -Scopes "Directory.Read.All" -NoWelcome | Out-Null

$resultats = foreach ($brut in $Ids) {
    # Le suffixe _o désigne les propriétaires d'un groupe Microsoft 365
    $id = $brut -replace "_o$", ""
    $proprietaires = $brut -match "_o$"
    try {
        $o = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/directoryObjects/$id"
        $type = $o.'@odata.type' -replace "#microsoft.graph.", ""
        $details = ""
        if ($type -eq "group") {
            $details = if ($o.groupTypes -contains "Unified") { "Microsoft 365" } elseif ($o.onPremisesSyncEnabled) { "sécurité, synchronisé AD" } else { "sécurité, cloud" }
        }
        [pscustomobject]@{
            Identifiant = $brut
            Type        = $type
            Nom         = $o.displayName
            Details     = $details
            Portee      = $(if ($proprietaires) { "propriétaires du groupe" } else { "" })
        }
    } catch {
        [pscustomobject]@{ Identifiant = $brut; Type = "introuvable"; Nom = ""; Details = $_.Exception.Message; Portee = "" }
    }
}
$resultats | Format-Table -AutoSize

Disconnect-MgGraph | Out-Null
