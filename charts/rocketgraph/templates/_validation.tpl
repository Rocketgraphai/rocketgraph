{{/*
Validate configuration — fail early instead of broken pods.
Call via: {{- include "rocketgraph.validate" . }}
*/}}
{{- define "rocketgraph.validate" -}}

{{- if and .Values.frontend.tls.publicCert (not .Values.frontend.tls.privateKey) }}
  {{- fail "frontend.tls.publicCert is set but frontend.tls.privateKey is missing" }}
{{- end }}
{{- if and .Values.frontend.tls.privateKey (not .Values.frontend.tls.publicCert) }}
  {{- fail "frontend.tls.privateKey is set but frontend.tls.publicCert is missing" }}
{{- end }}

{{- if and .Values.backend.tls.proxyClientCert (not .Values.backend.tls.proxyClientKey) }}
  {{- fail "backend.tls.proxyClientCert is set but backend.tls.proxyClientKey is missing" }}
{{- end }}
{{- if and .Values.backend.tls.proxyClientKey (not .Values.backend.tls.proxyClientCert) }}
  {{- fail "backend.tls.proxyClientKey is set but backend.tls.proxyClientCert is missing" }}
{{- end }}
{{- if and .Values.backend.tls.mtls (not .Values.backend.tls.existingSecret) (not .Values.backend.tls.proxyClientCert) (not .Values.backend.tls.proxyClientKey) }}
  {{- fail "backend.tls.mtls is true but no existingSecret or inline proxyClientCert/proxyClientKey provided" }}
{{- end }}

{{- if and .Values.xgt.enabled .Values.xgt.ssl.enabled .Values.xgt.ssl.mtls (not .Values.xgt.ssl.existingSecret) (not .Values.xgt.ssl.caCert) }}
  {{- fail "xgt.ssl.mtls is true but no existingSecret or inline caCert provided for ca-chain.cert.pem" }}
{{- end }}
{{- if and .Values.xgt.enabled .Values.xgt.ssl.enabled .Values.xgt.ssl.mtls .Values.xgt.ssl.existingSecret .Values.xgt.ssl.caCert }}
  {{- fail "xgt.ssl.caCert is ignored when existingSecret is set — include ca-chain.cert.pem in the existing secret instead" }}
{{- end }}

{{- if and .Values.xgt.enabled .Values.xgt.ssl.enabled (not .Values.xgt.ssl.existingSecret) }}
  {{- if and .Values.xgt.ssl.cert (not .Values.xgt.ssl.key) }}
    {{- fail "xgt.ssl.cert is set but xgt.ssl.key is missing" }}
  {{- end }}
  {{- if and .Values.xgt.ssl.key (not .Values.xgt.ssl.cert) }}
    {{- fail "xgt.ssl.key is set but xgt.ssl.cert is missing" }}
  {{- end }}
  {{- if and (not .Values.xgt.ssl.cert) (not .Values.xgt.ssl.key) }}
    {{- fail "xgt.ssl.enabled is true but no cert/key provided and no existingSecret set" }}
  {{- end }}
{{- end }}

{{- if and .Values.xgt.enabled .Values.xgt.ldap.enabled (not .Values.xgt.ldap.existingSecret) (not .Values.xgt.ldap.sssdConfig) }}
  {{- if not .Values.xgt.ldap.uri }}
    {{- fail "xgt.ldap.enabled is true but xgt.ldap.uri is not set" }}
  {{- end }}
  {{- if not .Values.xgt.ldap.baseDn }}
    {{- fail "xgt.ldap.enabled is true but xgt.ldap.baseDn is not set" }}
  {{- end }}
{{- end }}

{{- if and .Values.openshift.enabled (not (has .Values.openshift.scc (list "anyuid" "nonroot"))) }}
  {{- fail (printf "openshift.scc %q is not valid — must be \"anyuid\" or \"nonroot\"" .Values.openshift.scc) }}
{{- end }}

{{- if and .Values.mongodb.enabled (gt (.Values.mongodb.replicas | int) 1) }}
  {{- fail "mongodb.replicas > 1 is not supported — this chart deploys standalone MongoDB with no replica set. To use a MongoDB cluster, set mongodb.enabled: false and point mongodb.externalUri at your cluster." }}
{{- end }}

{{- if and .Values.xgt.enabled (gt (.Values.xgt.replicas | int) 1) }}
  {{- fail "xgt.replicas > 1 is not supported — multiple xgt instances would have no shared state in this configuration." }}
{{- end }}

{{- if and (not .Values.xgt.enabled) (not .Values.backend.env.MC_DEFAULT_XGT_HOST) }}
  {{- fail "xgt.enabled is false but backend.env.MC_DEFAULT_XGT_HOST is not set" }}
{{- end }}

{{- if and (not .Values.mongodb.enabled) (not .Values.mongodb.externalUri) (not .Values.mongodb.externalUriSecret) }}
  {{- fail "mongodb.enabled is false but neither mongodb.externalUri nor mongodb.externalUriSecret is set" }}
{{- end }}

{{- if and .Values.mongodb.enabled .Values.mongodb.encryption.enabled }}
  {{- $repo := .Values.mongodb.image.repository }}
  {{- if and (not .Values.fips.enabled) (or (eq $repo "mongo") (eq $repo "library/mongo") (eq $repo "docker.io/library/mongo")) }}
    {{- fail "mongodb.encryption.enabled requires an image that supports encryption at rest. Set fips.enabled=true, or set mongodb.image.repository to docker.io/percona/percona-server-mongodb." }}
  {{- end }}
  {{- if and (not .Values.mongodb.encryption.existingSecret) (not .Values.mongodb.encryption.key) }}
    {{- fail "mongodb.encryption.enabled is true but no key source provided — set mongodb.encryption.key or mongodb.encryption.existingSecret" }}
  {{- end }}
{{- end }}

{{- if and .Values.mongodb.enabled .Values.mongodb.tls.enabled (not .Values.mongodb.tls.existingSecret) }}
  {{- if not .Values.mongodb.tls.caCert }}
    {{- fail "mongodb.tls: ca.pem is required when using inline TLS certs (set mongodb.tls.caCert). Use mongodb.tls.existingSecret to supply certs in a pre-created secret." }}
  {{- end }}
  {{- if and (not .Values.mongodb.tls.cert) (not .Values.mongodb.tls.key) }}
    {{- fail "mongodb.tls: cert and key are required when using inline TLS (set mongodb.tls.cert and mongodb.tls.key). Use mongodb.tls.existingSecret to supply certs in a pre-created secret." }}
  {{- end }}
  {{- if and .Values.mongodb.tls.cert (not .Values.mongodb.tls.key) }}
    {{- fail "mongodb.tls.cert is set but mongodb.tls.key is missing" }}
  {{- end }}
  {{- if and .Values.mongodb.tls.key (not .Values.mongodb.tls.cert) }}
    {{- fail "mongodb.tls.key is set but mongodb.tls.cert is missing" }}
  {{- end }}
  {{- if and .Values.mongodb.tls.mtls (or (not .Values.mongodb.tls.clientCert) (not .Values.mongodb.tls.clientKey)) }}
    {{- fail "mongodb.tls.mtls is true but inline clientCert or clientKey is missing. Provide both, or use mongodb.tls.existingSecret with a client.pem key." }}
  {{- end }}
  {{- if and .Values.mongodb.tls.clientCert (not .Values.mongodb.tls.clientKey) }}
    {{- fail "mongodb.tls.clientCert is set but mongodb.tls.clientKey is missing" }}
  {{- end }}
  {{- if and .Values.mongodb.tls.clientKey (not .Values.mongodb.tls.clientCert) }}
    {{- fail "mongodb.tls.clientKey is set but mongodb.tls.clientCert is missing" }}
  {{- end }}
{{- end }}


{{- if and .Values.mongodb.enabled .Values.mongodb.auth.enabled (not .Values.mongodb.auth.existingSecret) }}
  {{- if not .Values.mongodb.auth.rootPassword }}
    {{- fail "mongodb.auth.enabled is true but mongodb.auth.rootPassword is not set and no existingSecret provided" }}
  {{- end }}
{{- end }}

{{- if gt (.Values.backend.replicas | int) 1 }}
  {{- fail "backend.replicas > 1 is not supported — session state is not shared across instances." }}
{{- end }}

{{- range $name := list "frontend" "backend" "xgt" "mongodb" }}
  {{- if hasKey $.Values $name }}
    {{- $component := index $.Values $name }}
    {{- if hasKey $component "podDisruptionBudget" }}
      {{- $pdb := $component.podDisruptionBudget }}
      {{- if and (hasKey $pdb "minAvailable") (hasKey $pdb "maxUnavailable") }}
        {{- fail (printf "%s.podDisruptionBudget: set minAvailable or maxUnavailable, not both" $name) }}
      {{- end }}
    {{- end }}
  {{- end }}
{{- end }}

{{- end -}}
