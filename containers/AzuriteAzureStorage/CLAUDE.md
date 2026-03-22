# AzuriteAzureStorage

Local Azure Storage emulator with a built-in web UI. Runs Azurite (Blob/Queue/Table services) and the sebagomez/azurestorageexplorer web dashboard in a single container.

## Architecture

```
entrypoint.sh → supervisord
                  ├→ azurite (Node.js, ports 10000/10001/10002)
                  │    Blob, Queue, and Table storage APIs
                  └→ AzureStorageExplorer (ASP.NET/Blazor, port 8080)
                       Web UI for browsing blobs, queues, tables, file shares
```

- **Azurite** is the official Microsoft Azure Storage emulator, installed via npm.
- **Storage Explorer** is `sebagomez/azurestorageexplorer`, a .NET Blazor web app pulled via multi-stage Docker build.
- **supervisord** manages both processes.

## Ports

| Port  | Service |
|-------|---------|
| 10000 | Blob Storage API |
| 10001 | Queue Storage API |
| 10002 | Table Storage API |
| 8080  | Storage Explorer Web UI |

## Connecting from other containers

Use the well-known Azurite development connection string, replacing `127.0.0.1` with the container's IP or hostname:

```
DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://<host>:10000/devstoreaccount1;QueueEndpoint=http://<host>:10001/devstoreaccount1;TableEndpoint=http://<host>:10002/devstoreaccount1;
```

## Data persistence

All Azurite data is stored in `/data` (mapped to `/mnt/user/appdata/AzuriteAzureStorage` on Unraid). This includes blob contents, queue messages, table entities, and Azurite's metadata files.
