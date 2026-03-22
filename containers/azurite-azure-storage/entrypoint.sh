#!/bin/bash
set -e

# Default connection string points to local Azurite with well-known dev credentials
export AZURE_STORAGE_CONNECTIONSTRING="${AZURE_STORAGE_CONNECTIONSTRING:-DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;}"

mkdir -p /data

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
