#!/usr/bin/env bash
# Generate self-signed TLS certificate for IP-only HTTPS (Let's Encrypt requires a hostname).
# Usage: ./scripts/oci/generate-self-signed-cert.sh 203.0.113.10

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <PUBLIC_IP>" >&2
  exit 1
fi

PUBLIC_IP="$1"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CERT_DIR="${ROOT_DIR}/nginx/certs"

mkdir -p "$CERT_DIR"

OPENSSL_CNF="$(mktemp)"
trap 'rm -f "$OPENSSL_CNF"' EXIT

cat >"$OPENSSL_CNF" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
CN = ${PUBLIC_IP}

[v3_req]
subjectAltName = @alt_names

[alt_names]
IP.1 = ${PUBLIC_IP}
EOF

openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout "${CERT_DIR}/privkey.pem" \
  -out "${CERT_DIR}/fullchain.pem" \
  -config "$OPENSSL_CNF"

chmod 600 "${CERT_DIR}/privkey.pem"
chmod 644 "${CERT_DIR}/fullchain.pem"

echo "Self-signed certificate written to ${CERT_DIR}/"
echo "Browsers will show a security warning until the cert is trusted."
echo "Optional zero-cost upgrade: use a free hostname (e.g. sslip.io) + Certbot — see OCI_DEPLOYMENT.md"
