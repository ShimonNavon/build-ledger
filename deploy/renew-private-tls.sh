#!/bin/sh
set -eu
docker run --rm -v /home/simon/build-ledger-private/letsencrypt:/etc/letsencrypt -v /home/simon/build-ledger-private/secrets:/secrets:ro certbot/dns-cloudflare renew --quiet
docker exec build-ledger-private nginx -s reload
