<#
.SYNOPSIS
    Dépose le corpus Axonix enrichi sur le partage et pose les droits des nouveaux dossiers.

.DESCRIPTION
    Sans -Appliquer : simulation, rien n'est modifié ; le script affiche ce qu'il ferait.
    Avec -Appliquer :
      1. crée trois dossiers à héritage coupé et y pose leurs droits, AVANT d'y copier quoi que ce soit :
           COMMUN                : Utilisateurs du domaine en lecture
           CLIENTS\_Confidentiel : GRP-Direction-Purview en modification
           RH\EVALUATIONS        : compte DRH seul, en modification
         (plus, pour chacun : Système, Administrateurs, Admins du domaine en contrôle total,
          GRP-RAG-Indexation en lecture) ;
      2. copie les documents ; un fichier existant est écrasé en place et garde ses droits,
         un nouveau fichier hérite des droits de son dossier ;
      3. ajoute un refus de lecture explicite au compte toto sur COMMUN\62_Calendrier_Fermetures_2026.docx.
    Les droits des dossiers existants ne sont pas modifiés. Identités désignées par SID (indépendant de la langue).

.EXAMPLE
    .\Droits-Corpus-Axonix.ps1 -Racine 'D:\FileService' -Source 'C:\Temp\corpus-axonix'
    .\Droits-Corpus-Axonix.ps1 -Racine 'D:\FileService' -Source 'C:\Temp\corpus-axonix' -Appliquer
#>
param(
    [Parameter(Mandatory = $true)] [string] $Racine,
    [Parameter(Mandatory = $true)] [string] $Source,
    [switch] $Appliquer,
    [string] $GroupeIndexation = 'GRP-RAG-Indexation',
    [string] $GroupeDirection = 'GRP-Direction-Purview',
    [string] $CompteRH = 'DRH',
    [string] $CompteRefus = 'toto'
)
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
$mode = if ($Appliquer) { 'APPLICATION' } else { 'SIMULATION (rien n''est modifié)' }
Write-Host "Mode : $mode"

$racine = (Resolve-Path -LiteralPath $Racine).ProviderPath.TrimEnd('\')
$source = (Resolve-Path -LiteralPath $Source).ProviderPath.TrimEnd('\')
$sidDom = (Get-ADDomain).DomainSID.Value
$SID = @{
    Systeme      = 'S-1-5-18'
    Admins       = 'S-1-5-32-544'
    AdminsDom    = "$sidDom-512"
    UtilDom      = "$sidDom-513"
    Indexation   = (Get-ADGroup $GroupeIndexation).SID.Value
    Direction    = (Get-ADGroup $GroupeDirection).SID.Value
    DRH          = (Get-ADUser $CompteRH).SID.Value
    Refus        = (Get-ADUser $CompteRefus).SID.Value
}

function Nom($sid) {
    try { (New-Object System.Security.Principal.SecurityIdentifier($sid)).Translate([System.Security.Principal.NTAccount]).Value }
    catch { $sid }
}

function Poser-Droits-Proteges([string] $chemin, [array] $regles) {
    $txt = ($regles | ForEach-Object { "$(Nom $_[0]) : $($_[1])" }) -join ' ; '
    Write-Host "  Héritage coupé : $chemin"
    Write-Host "    $txt"
    if (-not $Appliquer) { return }
    if (-not (Test-Path -LiteralPath $chemin)) { New-Item -ItemType Directory -Path $chemin | Out-Null }
    # DACL construite de zéro, héritage coupé sans copie des droits hérités ;
    # SetAccessControl n'écrit que la DACL (le propriétaire n'est pas touché)
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($r in $regles) {
        $id = New-Object System.Security.Principal.SecurityIdentifier($r[0])
        $regle = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $id, $r[1], 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($regle)
    }
    (Get-Item -LiteralPath $chemin).SetAccessControl($acl)
}

$base = @(@($SID.Systeme, 'FullControl'), @($SID.Admins, 'FullControl'), @($SID.AdminsDom, 'FullControl'),
          @($SID.Indexation, 'ReadAndExecute'))

Write-Host "`n1. Dossiers à héritage coupé"
Poser-Droits-Proteges "$racine\COMMUN" ($base + ,@($SID.UtilDom, 'ReadAndExecute'))
Poser-Droits-Proteges "$racine\CLIENTS\_Confidentiel" ($base + ,@($SID.Direction, 'Modify'))
Poser-Droits-Proteges "$racine\RH\EVALUATIONS" ($base + ,@($SID.DRH, 'Modify'))

Write-Host "`n2. Copie des documents depuis $source"
$fichiers = Get-ChildItem -LiteralPath $source -Recurse -File
$nouveaux = 0; $remplaces = 0
foreach ($f in $fichiers) {
    $rel = $f.FullName.Substring($source.Length + 1)
    $cible = Join-Path $racine $rel
    if (Test-Path -LiteralPath $cible) { $remplaces++ } else { $nouveaux++ }
    if ($Appliquer) {
        $dossier = Split-Path $cible
        if (-not (Test-Path -LiteralPath $dossier)) { New-Item -ItemType Directory -Path $dossier -Force | Out-Null }
        Copy-Item -LiteralPath $f.FullName -Destination $cible -Force
    }
}
Write-Host "  $($fichiers.Count) document(s) : $nouveaux nouveau(x), $remplaces remplacé(s) en place (droits conservés)"

Write-Host "`n3. Refus explicite"
$cal = "$racine\COMMUN\62_Calendrier_Fermetures_2026.docx"
Write-Host "  Refus de lecture à $(Nom $SID.Refus) sur $cal"
if ($Appliquer) {
    $acl = Get-Acl -LiteralPath $cal
    $id = New-Object System.Security.Principal.SecurityIdentifier($SID.Refus)
    $acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($id, 'Read', 'None', 'None', 'Deny')))
    Set-Acl -LiteralPath $cal -AclObject $acl
    Write-Host "`n4. Contrôle"
    foreach ($c in "$racine\COMMUN", "$racine\CLIENTS\_Confidentiel", "$racine\RH\EVALUATIONS", $cal) { icacls $c }
}
Write-Host "`nTerminé ($mode)."
