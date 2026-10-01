#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
umask 077
mkdir -p .private
for name in test-ca.key test-ca.pem xgt-key.pem xgt-cert.pem xgt-ca.pem \
            mongodb-key.pem mongodb-cert.pem mongodb-ca.pem; do
  if [ -e ".private/$name" ]; then
    echo "Refusing to overwrite .private/$name; use existing certificates." >&2
    exit 1
  fi
done

# Test-only CA. For a FIPS validation, use an approved certificate/key workflow
# and verify the generating OpenSSL runtime is operating as required.
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 30 \
  -keyout .private/test-ca.key -out .private/test-ca.pem \
  -subj '/CN=XGT demo CA' \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign'

for service in xgt mongodb; do
  extra_sans=''
  if [ "$service" = xgt ]; then
    for extra in xgt-dev-xgt xgt-prod-xgt; do
      extra_sans+=",DNS:$extra,DNS:$extra.xgt-demo.svc,DNS:$extra.xgt-demo.svc.cluster.local"
    done
  fi
  openssl req -new -newkey rsa:3072 -sha256 -nodes \
    -keyout ".private/$service-key.pem" \
    -out ".private/$service.csr" -subj "/CN=rocketgraph-$service"
  cat > ".private/$service.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth,clientAuth
subjectAltName=DNS:rocketgraph-$service,DNS:rocketgraph-$service.xgt-demo.svc,DNS:rocketgraph-$service.xgt-demo.svc.cluster.local,DNS:localhost,IP:127.0.0.1$extra_sans
EOF
  openssl x509 -req -sha256 -days 30 -in ".private/$service.csr" \
    -CA .private/test-ca.pem -CAkey .private/test-ca.key -CAcreateserial \
    -extfile ".private/$service.ext" -out ".private/$service-cert.pem"
  cp .private/test-ca.pem ".private/$service-ca.pem"
done
echo 'Created test certificates valid for 30 days. This does not establish FIPS compliance.'
