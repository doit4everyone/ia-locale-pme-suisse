// mip-service : service interne de déchiffrement des documents protégés par Purview (§14).
//
// Joignable uniquement depuis le réseau Docker de la stack (aucun port publié).
// POST /dechiffrer : reçoit un document (corps brut, nom dans l'en-tête X-Nom-Fichier),
// renvoie ses métadonnées de protection et, si les règles le permettent, son contenu
// déchiffré encodé en base64. Rien n'est écrit sur disque : le contenu reste en mémoire.
//
// Règles appliquées AVANT tout déchiffrement :
//   - protection par modèle uniquement (TemplateBased) : les permissions définies
//     par l'utilisateur sont exclues, comme le fait Copilot pour ses agents ;
//   - contenu expiré : jamais déchiffré (un super-utilisateur le pourrait, pas le RAG) ;
//   - étiquettes listées dans MIP_ETIQUETTES_EXCLUES : jamais déchiffrées.
// Le contenu des documents n'est jamais journalisé.
//
// POST /droits : renvoie les droits d'un utilisateur (au nom duquel l'application interroge
// le service de protection, en mode délégué) pour une étiquette et un propriétaire donnés.
// Sert à la double condition : SharePoint décide de l'accès au site, Purview des droits
// sur le contenu chiffré, évalués au moment de la question.
using System.Security.Cryptography.X509Certificates;
using Microsoft.Identity.Client;
using Microsoft.InformationProtection;
using Microsoft.InformationProtection.File;
using Microsoft.InformationProtection.Protection;

static string Env(string nom) =>
    Environment.GetEnvironmentVariable(nom) ?? throw new Exception($"Variable {nom} manquante");

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls("http://0.0.0.0:8080");
builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = 100L * 1024 * 1024);
builder.Logging.ClearProviders();
builder.Logging.AddSimpleConsole(o => { o.SingleLine = true; o.TimestampFormat = "yyyy-MM-dd HH:mm:ss "; });

var moteur = new MoteurMip(
    Env("ENTRA_TENANT_ID"), Env("MIP_TENANT_DOMAINE"), Env("MIP_CLIENT_ID"),
    Env("MIP_CERT_CRT"), Env("MIP_CERT_KEY"));
var jeton = Env("MIP_TOKEN");
var etiquettesExclues = (Environment.GetEnvironmentVariable("MIP_ETIQUETTES_EXCLUES") ?? "")
    .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
    .Select(e => e.ToLowerInvariant()).ToHashSet();

var app = builder.Build();
var log = app.Logger;

bool Autorise(HttpRequest r) =>
    r.Headers.Authorization.ToString() == $"Bearer {jeton}";

app.MapPost("/droits", async (HttpRequest req) =>
{
    if (!Autorise(req)) return Results.StatusCode(401);
    var demande = await req.ReadFromJsonAsync<DemandeDroits>();
    if (demande == null || string.IsNullOrWhiteSpace(demande.utilisateur) || string.IsNullOrWhiteSpace(demande.etiquette_id))
        return Results.BadRequest(new { erreur = "utilisateur et etiquette_id requis" });
    try
    {
        var droits = await moteur.DroitsAsync(demande.utilisateur, demande.etiquette_id, demande.proprietaire ?? "");
        var majuscules = droits.Select(d => d.ToUpperInvariant()).ToHashSet();
        var autorise = majuscules.Contains("OWNER") || (majuscules.Contains("VIEW") && majuscules.Contains("EXTRACT"));
        log.LogInformation("[MIP] droits {Utilisateur} sur {Etiquette} : {Droits} → {Decision}",
            demande.utilisateur, demande.etiquette_id, string.Join(",", droits), autorise ? "autorise" : "refuse");
        return Results.Ok(new { utilisateur = demande.utilisateur, etiquette_id = demande.etiquette_id,
            proprietaire = demande.proprietaire, droits, autorise });
    }
    catch (Exception e) when (e.GetType().Name == "NoPermissionsException")
    {
        // Réponse normale du service de protection : l'utilisateur n'a aucun droit sur cette étiquette
        log.LogInformation("[MIP] droits {Utilisateur} sur {Etiquette} : aucun → refuse", demande.utilisateur, demande.etiquette_id);
        return Results.Ok(new { utilisateur = demande.utilisateur, etiquette_id = demande.etiquette_id,
            proprietaire = demande.proprietaire, droits = new List<string>(), autorise = false });
    }
    catch (Exception e)
    {
        log.LogWarning("[MIP] droits {Utilisateur} : échec ({Type}) {Message}", demande.utilisateur, e.GetType().Name, e.Message);
        return Results.Json(new { erreur = e.GetType().Name, message = e.Message }, statusCode: 502);
    }
});

app.MapGet("/sante", () => Results.Ok(new { statut = "ok", moteur = moteur.Pret }));

app.MapPost("/dechiffrer", async (HttpRequest req) =>
{
    if (!Autorise(req)) return Results.StatusCode(401);
    var nom = req.Headers["X-Nom-Fichier"].ToString();
    if (string.IsNullOrWhiteSpace(nom) || !Path.HasExtension(nom))
        return Results.BadRequest(new { erreur = "En-tête X-Nom-Fichier avec extension requis" });

    using var entree = new MemoryStream();
    await req.Body.CopyToAsync(entree);
    entree.Position = 0;

    try
    {
        var r = await moteur.TraiterAsync(entree, Path.GetFileName(nom), etiquettesExclues);
        log.LogInformation("[MIP] {Fichier} : protege={Protege} etiquette={Etiquette} type={Type} decision={Decision}",
            Path.GetFileName(nom), r.protege, r.etiquette_nom ?? "-", r.type_protection ?? "-", r.decision);
        return Results.Ok(r);
    }
    catch (Exception e)
    {
        log.LogWarning("[MIP] {Fichier} : échec ({Type}) {Message}", Path.GetFileName(nom), e.GetType().Name, e.Message);
        return Results.Json(new { erreur = e.GetType().Name, message = e.Message }, statusCode: 502);
    }
});

await moteur.InitialiserAsync();
log.LogInformation("[MIP] Moteur initialisé, service prêt");
app.Run();

record DemandeDroits(string utilisateur, string etiquette_id, string proprietaire);

record Resultat(
    bool protege, string etiquette_id, string etiquette_nom, string modele_id,
    string type_protection, string proprietaire, string expire_le,
    string decision, string contenu_base64);

class MoteurMip
{
    private readonly string _tenantId, _domaine, _clientId, _crt, _key;
    private IFileEngine _moteur;
    private IProtectionEngine _protection;
    private readonly SemaphoreSlim _verrou = new(1, 1);
    public bool Pret => _moteur != null;

    public MoteurMip(string tenantId, string domaine, string clientId, string crt, string key)
    { _tenantId = tenantId; _domaine = domaine; _clientId = clientId; _crt = crt; _key = key; }

    public async Task InitialiserAsync()
    {
        var cert = X509Certificate2.CreateFromPemFile(_crt, _key);
        MIP.Initialize(MipComponent.File);
        var appInfo = new ApplicationInfo
        { ApplicationId = _clientId, ApplicationName = "RAG-Purview-Decrypt", ApplicationVersion = "1.0" };
        var config = new MipConfiguration(appInfo, "/tmp/mip_data",
            Microsoft.InformationProtection.LogLevel.Warning, false, CacheStorageType.InMemory);
        var contexte = MIP.CreateMipContext(config);
        var profil = await MIP.LoadFileProfileAsync(
            new FileProfileSettings(contexte, CacheStorageType.InMemory, new ConsentementAccepte()));
        var reglages = new FileEngineSettings("mip-service", new AuthCertificat(_clientId, _tenantId, cert), "", "fr-FR")
        { Identity = new Identity($"rag-purview-decrypt@{_domaine}") };
        _moteur = await profil.AddEngineAsync(reglages);

        // Moteur de protection, pour l'évaluation des droits d'un utilisateur délégué
        var auth = new AuthCertificat(_clientId, _tenantId, cert);
        var profilProtection = await MIP.LoadProtectionProfileAsync(
            new ProtectionProfileSettings(contexte, CacheStorageType.InMemory, new ConsentementAccepte()));
        var reglagesProtection = new ProtectionEngineSettings("mip-service-droits", auth, "", "fr-FR")
        { Identity = new Identity($"rag-purview-decrypt@{_domaine}") };
        _protection = await profilProtection.AddEngineAsync(reglagesProtection);
    }

    public async Task<List<string>> DroitsAsync(string utilisateur, string etiquetteId, string proprietaire)
    {
        await _verrou.WaitAsync();
        try
        {
            return await _protection.GetRightsForLabelIdAsync(
                Guid.NewGuid().ToString(), etiquetteId, proprietaire, utilisateur);
        }
        finally { _verrou.Release(); }
    }

    public async Task<Resultat> TraiterAsync(Stream entree, string nom, HashSet<string> exclues)
    {
        await _verrou.WaitAsync();
        try
        {
            var handler = await _moteur.CreateFileHandlerAsync(entree, nom, true);
            var etiquette = handler.Label?.Label;
            var protection = handler.Protection;
            if (protection == null)
                return new Resultat(false, etiquette?.Id, etiquette?.Name, null, null, null, null,
                    "non_protege", null);

            var d = protection.ProtectionDescriptor;
            var type = d.ProtectionType.ToString();
            var expire = d.ContentValidUntil;
            var expireTxt = expire?.ToString("u");

            string refus = null;
            if (type != "TemplateBased") refus = "permissions_definies_par_utilisateur";
            else if (expire.HasValue && expire.Value.ToUniversalTime() < DateTime.UtcNow) refus = "contenu_expire";
            else if (etiquette != null && exclues.Contains(etiquette.Id.ToLowerInvariant())) refus = "etiquette_exclue";

            if (refus != null)
                return new Resultat(true, etiquette?.Id, etiquette?.Name, d.TemplateId, type, d.Owner, expireTxt,
                    refus, null);

            using var flux = await handler.GetDecryptedTemporaryStreamAsync();
            if (flux.CanSeek) flux.Position = 0;
            using var memoire = new MemoryStream();
            await flux.CopyToAsync(memoire);
            return new Resultat(true, etiquette?.Id, etiquette?.Name, d.TemplateId, type, d.Owner, expireTxt,
                "dechiffre", Convert.ToBase64String(memoire.ToArray()));
        }
        finally { _verrou.Release(); }
    }
}

class AuthCertificat : IAuthDelegate
{
    private readonly string _clientId, _tenantId;
    private readonly X509Certificate2 _cert;
    public AuthCertificat(string clientId, string tenantId, X509Certificate2 cert)
    { _clientId = clientId; _tenantId = tenantId; _cert = cert; }

    public string AcquireToken(Identity identity, string authority, string resource, string claims)
    {
        var app = ConfidentialClientApplicationBuilder.Create(_clientId)
            .WithCertificate(_cert)
            .WithAuthority($"https://{new Uri(authority).Host}/{_tenantId}")
            .Build();
        var scope = resource.EndsWith("/") ? $"{resource}.default" : $"{resource}/.default";
        return app.AcquireTokenForClient(new[] { scope }).ExecuteAsync().GetAwaiter().GetResult().AccessToken;
    }
}

class ConsentementAccepte : IConsentDelegate
{
    public Consent GetUserConsent(string url) => Consent.Accept;
}
