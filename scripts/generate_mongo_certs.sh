#!/usr/bin/env bash

set -euo pipefail

# Generate a CA chain and a MongoDB server certificate (with a subjectAltName)
# for the docker-compose MongoDB TLS option.  Produces two files in the output
# directory:
#
#   server.pem          server cert + private key, concatenated
#                       (point MC_MONGO_TLS_SERVER_PEM at this)
#   ca-chain.cert.pem   intermediate + root CA certs
#                       (point MC_MONGO_TLS_CA_PEM at this)
#   client.pem          client cert + private key, concatenated, for
#                       mTLS (the backend presents this when mongod is
#                       configured to require client certs)
#
# The server cert carries a subjectAltName so TLS clients (the backend's
# pymongo, mongosh, mongodump) verify the hostname strictly — no
# tlsAllowInvalidHostnames needed.  The default SAN covers the compose
# service name "mongodb" plus localhost / 127.0.0.1 for in-container and
# dev-mode access.
#
# Based on the xGT cert generator (apps/xgt/test/test_ssl/create_certs.sh)
# but trimmed to the single server cert MongoDB needs, with SAN support
# added and the cert+key emitted as one concatenated server.pem.

usage() {
  cat <<'EOF'
Usage: generate_mongo_certs.sh [output_dir]

Generate MongoDB TLS certs (CA chain + SAN server cert) for compose.

Arguments:
  output_dir   Where to write server.pem and ca-chain.cert.pem.
               Defaults to ./mongo_tls.

Environment:
  MONGO_TLS_SAN   subjectAltName list in openssl format.  Defaults to
                  "DNS:mongodb, DNS:localhost, IP:127.0.0.1".  Override
                  to add hostnames/IPs, e.g.:
                    MONGO_TLS_SAN="DNS:mongodb, DNS:db.internal, IP:10.0.0.5"

Example:
  scripts/generate_mongo_certs.sh ~/.rocketgraph/mongo_tls
EOF
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
esac

out_dir="${1:-./mongo_tls}"
mongo_tls_san="${MONGO_TLS_SAN:-DNS:mongodb, DNS:localhost, IP:127.0.0.1}"

country="US"
state="WA"
locality="Seattle"
organization="Rocketgraph"

die() {
  echo "error: $*" >&2
  exit 1
}

command -v openssl >/dev/null 2>&1 || die "openssl not found on PATH"

mkdir -p "$out_dir"
out_dir="$(cd "$out_dir" && pwd)"

# All CA scratch state lives in a temp dir removed on exit; only the two
# output files survive.
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

# Emit an openssl.cnf whose [CA_default] points at the given CA dir.
# The same [server_cert] block (with the SAN) is written into both the
# root and intermediate configs; only the intermediate's is used to sign
# the server, so the root copy is harmless.
write_ca_cnf() {
  local ca_dir="$1"
  local cnf="$2"
  cat > "$cnf" <<EOF
[ ca ]
default_ca = CA_default

[ CA_default ]
dir               = ${ca_dir}
new_certs_dir     = \$dir/newcerts
database          = \$dir/index.txt
serial            = \$dir/serial
private_key       = \$dir/private/ca.key.pem
certificate       = \$dir/certs/ca.cert.pem
default_md        = sha256
policy            = policy_loose
email_in_dn       = no
unique_subject    = no

[ policy_loose ]
countryName             = optional
stateOrProvinceName     = optional
localityName            = optional
organizationName        = optional
organizationalUnitName  = optional
commonName              = supplied
emailAddress            = optional

[ req ]
default_bits        = 2048
distinguished_name  = req_distinguished_name
string_mask         = utf8only
default_md          = sha256
x509_extensions     = v3_ca

[ req_distinguished_name ]
commonName          = Common Name

[ v3_ca ]
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints = critical, CA:true
keyUsage = critical, digitalSignature, cRLSign, keyCertSign

[ v3_intermediate_ca ]
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints = critical, CA:true, pathlen:0
keyUsage = critical, digitalSignature, cRLSign, keyCertSign

[ server_cert ]
basicConstraints = CA:FALSE
nsCertType = server
nsComment = "OpenSSL Generated Server Certificate"
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer:always
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = ${mongo_tls_san}

[ client_cert ]
basicConstraints = CA:FALSE
nsCertType = client
nsComment = "OpenSSL Generated Client Certificate"
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
keyUsage = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth
EOF
}

# Initialise the directory skeleton an `openssl ca` database needs.
init_ca_dir() {
  local ca_dir="$1"
  mkdir -p "$ca_dir/certs" "$ca_dir/csr" "$ca_dir/private" \
    "$ca_dir/newcerts"
  touch "$ca_dir/index.txt"
  echo 1000 > "$ca_dir/serial"
}

subj() {
  printf "/C=%s/ST=%s/L=%s/O=%s/CN=%s" \
    "$country" "$state" "$locality" "$organization" "$1"
}

root_dir="$work_dir/root"
int_dir="$work_dir/intermediate"
init_ca_dir "$root_dir"
init_ca_dir "$int_dir"
write_ca_cnf "$root_dir" "$root_dir/openssl.cnf"
write_ca_cnf "$int_dir" "$int_dir/openssl.cnf"

echo "Generating root CA..."
openssl genrsa -out "$root_dir/private/ca.key.pem" 4096
openssl req -config "$root_dir/openssl.cnf" \
  -key "$root_dir/private/ca.key.pem" \
  -new -x509 -days 7300 -sha256 -extensions v3_ca \
  -out "$root_dir/certs/ca.cert.pem" -subj "$(subj RocketgraphRoot)"

echo "Generating intermediate CA..."
openssl genrsa -out "$int_dir/private/ca.key.pem" 2048
openssl req -config "$int_dir/openssl.cnf" -new -sha256 \
  -key "$int_dir/private/ca.key.pem" \
  -out "$int_dir/csr/intermediate.csr.pem" \
  -subj "$(subj RocketgraphIntermediate)"
openssl ca -config "$root_dir/openssl.cnf" -batch \
  -extensions v3_intermediate_ca -days 3650 -notext -md sha256 \
  -in "$int_dir/csr/intermediate.csr.pem" \
  -out "$int_dir/certs/ca.cert.pem"

echo "Generating server certificate (SAN: ${mongo_tls_san})..."
openssl genrsa -out "$work_dir/server.key.pem" 2048
openssl req -config "$int_dir/openssl.cnf" -new -sha256 \
  -key "$work_dir/server.key.pem" \
  -out "$int_dir/csr/server.csr.pem" -subj "$(subj RocketgraphServer)"
openssl ca -config "$int_dir/openssl.cnf" -batch -extensions server_cert \
  -days 825 -notext -md sha256 \
  -in "$int_dir/csr/server.csr.pem" \
  -out "$work_dir/server.cert.pem"

echo "Generating client certificate (for mTLS)..."
openssl genrsa -out "$work_dir/client.key.pem" 2048
openssl req -config "$int_dir/openssl.cnf" -new -sha256 \
  -key "$work_dir/client.key.pem" \
  -out "$int_dir/csr/client.csr.pem" -subj "$(subj mongodb-client)"
openssl ca -config "$int_dir/openssl.cnf" -batch -extensions client_cert \
  -days 825 -notext -md sha256 \
  -in "$int_dir/csr/client.csr.pem" \
  -out "$work_dir/client.cert.pem"

# server.pem = cert + key (mongod's --tlsCertificateKeyFile wants both).
cat "$work_dir/server.cert.pem" "$work_dir/server.key.pem" \
  > "$out_dir/server.pem"
# ca-chain = intermediate + root (the trust file for --tlsCAFile).
cat "$int_dir/certs/ca.cert.pem" "$root_dir/certs/ca.cert.pem" \
  > "$out_dir/ca-chain.cert.pem"
# client.pem = cert + key, for mTLS (the backend presents this).
cat "$work_dir/client.cert.pem" "$work_dir/client.key.pem" \
  > "$out_dir/client.pem"

chmod 600 "$out_dir/server.pem" "$out_dir/client.pem"
chmod 644 "$out_dir/ca-chain.cert.pem"

cat <<EOF

Done.  Wrote:
  ${out_dir}/server.pem          (set MC_MONGO_TLS_SERVER_PEM to this)
  ${out_dir}/ca-chain.cert.pem   (set MC_MONGO_TLS_CA_PEM to this)
  ${out_dir}/client.pem          (for mTLS, when mongod requires client certs)

Verify the SAN with:
  openssl x509 -in ${out_dir}/server.pem -noout -text \\
    | grep -A1 'Subject Alternative Name'
EOF
