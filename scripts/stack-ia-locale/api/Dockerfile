# Image de base figée par empreinte (relevée sur la VM de test le 17 octobre 2026).
# Mettre à jour = revalider (§16.8).
FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce

# smbclient fournit le binaire smbcacls, appelé par acl_resolver.py
# pour lire les ACL NTFS du partage. Sans ce paquet, la synchronisation
# échoue avec FileNotFoundError: smbcacls.
# ca-certificates est requis pour la validation TLS du certificat LDAP.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        smbclient \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Locale UTF-8 : les noms de fichiers du corpus contiennent des accents.
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py auth.py teams.py teams_graph.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
