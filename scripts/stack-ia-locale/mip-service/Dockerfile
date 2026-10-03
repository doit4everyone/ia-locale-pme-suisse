# mip-service : image Ubuntu 24.04 (noble), version prise en charge par le SDK MIP pour Linux,
# indépendamment de la version d'Ubuntu de l'hôte.
FROM mcr.microsoft.com/dotnet/sdk:8.0-noble AS build
WORKDIR /src
COPY MipService.csproj .
RUN dotnet restore
COPY Program.cs .
RUN dotnet publish -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0-noble
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgsf-1-114 libgmime-3.0-0t64 libsecret-1-0 libglib2.0-0 libcurl4 libssl3 libuuid1 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    # Le SDK cherche libdl.so ; depuis la bibliothèque C 2.34, seul libdl.so.2 existe
    && ln -s /usr/lib/x86_64-linux-gnu/libdl.so.2 /usr/lib/x86_64-linux-gnu/libdl.so
WORKDIR /app
COPY --from=build /app .
# Utilisateur sans privilèges
# Groupe et utilisateur de même identifiant (10001), pour que la clé puisse lui appartenir
RUN groupadd --system --gid 10001 mip && useradd --system --uid 10001 --gid 10001 mip
USER mip
ENTRYPOINT ["dotnet", "MipService.dll"]
