#!/usr/bin/env bash
# Convert a public IPv4 address to its sslip.io hostname.
# Example: 203.0.113.10 -> 203-0-113-10.sslip.io
#
# Usage: ./scripts/oci/sslip-hostname.sh 203.0.113.10

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <PUBLIC_IPv4>" >&2
  exit 1
fi

IP="$1"
if [[ ! "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: expected IPv4 address, got: $IP" >&2
  exit 1
fi

echo "${IP//./-}.sslip.io"
