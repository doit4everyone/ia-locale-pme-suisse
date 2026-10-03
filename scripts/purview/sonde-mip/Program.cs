// Sonde de déchiffrement Purview (§14, étape 4).
// Déchiffre UN document de test avec l'application RAG-Purview-Decrypt,
// affiche son étiquette, ses détenteurs de droits et le début de son texte.
// Le contenu déchiffré reste en mémoire : aucun fichier en clair n'est écrit.
using System.Security.Cryptography.X509Certificates;
using System.Text;
using DocumentFormat.OpenXml.Packaging;
using Microsoft.Identity.Client;
using Microsoft.InformationProtection;
using Microsoft.InformationProtection.File;

static string Env(string nom) =>
    Environment.GetEnvironmentVariable(nom) ?? throw new Exception($"Variable {nom} manquante");

var tenantId = Env("TENANT_ID");
var tenantDomaine = Env("TENANT_DOMAINE");          // ex. contoso.onmicrosoft.com
var clientId = Env("CLIENT_ID");
var certCrt = Env("CERT_CRT");
var certKey = Env("CERT_KEY");
var fichier = Env("FICHIER");
var codeAttendu = Environment.GetEnvironmentVariable("CODE_ATTENDU") ?? "";

Console.WriteLine($"[SONDE] Fichier : {fichier}");
var entete = new byte[8];
using (var fs = File.OpenRead(fichier)) fs.Read(entete, 0, 8);
Console.WriteLine($"[SONDE] En-tête : {Convert.ToHexString(entete)} "
    + (entete[0] == 0xD0 && entete[1] == 0xCF ? "(conteneur OLE : document chiffré)" : "(pas un conteneur OLE)"));

var cert = X509Certificate2.CreateFromPemFile(certCrt, certKey);
Console.WriteLine($"[SONDE] Certificat chargé : {cert.Subject}, empreinte {cert.Thumbprint}");

MIP.Initialize(MipComponent.File);
var appInfo = new ApplicationInfo
{
    ApplicationId = clientId,
    ApplicationName = "RAG-Purview-Decrypt",
    ApplicationVersion = "0.1"
};
var config = new MipConfiguration(appInfo, "/tmp/mip_data", Microsoft.InformationProtection.LogLevel.Warning, false, CacheStorageType.InMemory);
var contexte = MIP.CreateMipContext(config);

var auth = new AuthDelegateCertificat(clientId, tenantId, cert);
var profilSettings = new FileProfileSettings(contexte, CacheStorageType.InMemory, new ConsentementAccepte());
var profil = await MIP.LoadFileProfileAsync(profilSettings);

var engineSettings = new FileEngineSettings("sonde", auth, "", "fr-FR")
{
    Identity = new Identity($"rag-purview-decrypt@{tenantDomaine}")
};
var moteur = await profil.AddEngineAsync(engineSettings);
Console.WriteLine("[SONDE] Moteur MIP initialisé (authentification et découverte du service : OK)");

var handler = await moteur.CreateFileHandlerAsync(fichier, fichier, true);

var etiquette = handler.Label;
Console.WriteLine(etiquette?.Label != null
    ? $"[SONDE] Étiquette : {etiquette.Label.Name} ({etiquette.Label.Id})"
    : "[SONDE] Étiquette : aucune lue");

var protection = handler.Protection;
if (protection == null)
{
    Console.WriteLine("[SONDE] Le document n'est pas protégé : rien à déchiffrer.");
    return 0;
}

var desc = protection.ProtectionDescriptor;
Console.WriteLine($"[SONDE] Protection : type {desc.ProtectionType}, modèle {desc.TemplateId}");
Console.WriteLine($"[SONDE] Propriétaire : {desc.Owner}");
Console.WriteLine($"[SONDE] Valable jusqu'au : {(desc.ContentValidUntil?.ToString("u") ?? "sans expiration")}");
Console.WriteLine($"[SONDE] Entrées de droits : {desc.UserRights?.Count ?? 0} (vide pour une protection par modèle)");
if (desc.UserRights != null)
{
    foreach (var ur in desc.UserRights)
        Console.WriteLine($"[SONDE] Droits : {string.Join(", ", ur.Users)} → {string.Join(",", ur.Rights)}");
}
if (desc.UserRoles != null)
{
    foreach (var r in desc.UserRoles)
        Console.WriteLine($"[SONDE] Rôles : {string.Join(", ", r.Users)} → {string.Join(",", r.Roles)}");
}

// Déchiffrement en mémoire
using var flux = await handler.GetDecryptedTemporaryStreamAsync();
if (flux.CanSeek) flux.Position = 0;
using var memoire = new MemoryStream();
await flux.CopyToAsync(memoire);
memoire.Position = 0;
Console.WriteLine($"[SONDE] Déchiffrement : {memoire.Length} octets en mémoire");

var texte = new StringBuilder();
using (var doc = WordprocessingDocument.Open(memoire, false))
{
    texte.Append(doc.MainDocumentPart?.Document?.Body?.InnerText ?? "");
}
var t = texte.ToString();
Console.WriteLine($"[SONDE] Texte extrait : {t.Length} caractères");
Console.WriteLine($"[SONDE] Début : {t.Substring(0, Math.Min(200, t.Length))}");
if (codeAttendu != "")
    Console.WriteLine(t.Contains(codeAttendu)
        ? $"[SONDE] RÉSULTAT : code {codeAttendu} trouvé, déchiffrement validé"
        : $"[SONDE] RÉSULTAT : code {codeAttendu} ABSENT du texte déchiffré");
return 0;

class AuthDelegateCertificat : IAuthDelegate
{
    private readonly string _clientId, _tenantId;
    private readonly X509Certificate2 _cert;
    public AuthDelegateCertificat(string clientId, string tenantId, X509Certificate2 cert)
    { _clientId = clientId; _tenantId = tenantId; _cert = cert; }

    public string AcquireToken(Identity identity, string authority, string resource, string claims)
    {
        var hote = new Uri(authority).Host;
        var app = ConfidentialClientApplicationBuilder.Create(_clientId)
            .WithCertificate(_cert)
            .WithAuthority($"https://{hote}/{_tenantId}")
            .Build();
        var scope = resource.EndsWith("/") ? $"{resource}.default" : $"{resource}/.default";
        Console.WriteLine($"[SONDE] Jeton demandé pour : {scope}");
        var res = app.AcquireTokenForClient(new[] { scope }).ExecuteAsync().GetAwaiter().GetResult();
        return res.AccessToken;
    }
}

class ConsentementAccepte : IConsentDelegate
{
    public Consent GetUserConsent(string url) => Consent.Accept;
}
