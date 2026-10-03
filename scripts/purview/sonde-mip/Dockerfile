# Image de construction et d'exécution de la sonde MIP, sur Ubuntu 24.04 (noble),
# version d'Ubuntu prise en charge par le SDK MIP .NET.
FROM mcr.microsoft.com/dotnet/sdk:8.0-noble AS build
WORKDIR /src
COPY SondeMip.csproj .
RUN dotnet restore
COPY Program.cs .
RUN dotnet publish -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/runtime:8.0-noble
# Dépendances natives courantes du SDK MIP sous Linux (liste à ajuster selon les erreurs)
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgsf-1-114 libgmime-3.0-0t64 libsecret-1-0 libglib2.0-0 libcurl4 libssl3 libuuid1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Le SDK cherche libdl.so ; depuis la bibliothèque C 2.34, seul libdl.so.2 existe
RUN ln -s /usr/lib/x86_64-linux-gnu/libdl.so.2 /usr/lib/x86_64-linux-gnu/libdl.so
WORKDIR /app
COPY --from=build /app .
ENTRYPOINT ["dotnet", "SondeMip.dll"]
