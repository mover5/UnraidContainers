FROM sebagomez/azurestorageexplorer:latest AS explorer

FROM node:22-alpine

LABEL maintainer="mover5"
LABEL org.opencontainers.image.source="https://github.com/mover5/UnraidContainers"

RUN apk add --no-cache \
    supervisor \
    bash \
    icu-libs \
    libstdc++

# .NET 10 ASP.NET Core runtime (needed for the storage explorer web UI)
COPY --from=mcr.microsoft.com/dotnet/aspnet:10.0-alpine /usr/share/dotnet /usr/share/dotnet
RUN ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet

# Azurite
RUN npm install -g azurite

# Azure Storage Explorer web UI (app lives at /app with web.dll as entrypoint)
COPY --from=explorer /app /opt/azure-storage-explorer

COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME /data
EXPOSE 10000 10001 10002 8080

ENTRYPOINT ["/entrypoint.sh"]
