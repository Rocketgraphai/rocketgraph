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

{{- if and (not .Values.xgt.enabled) (not .Values.backend.env.MC_DEFAULT_XGT_HOST) }}
  {{- fail "xgt.enabled is false but backend.env.MC_DEFAULT_XGT_HOST is not set" }}
{{- end }}

{{- if and (not .Values.mongodb.enabled) (not .Values.mongodb.externalUri) (not .Values.mongodb.externalUriSecret) }}
  {{- fail "mongodb.enabled is false but neither mongodb.externalUri nor mongodb.externalUriSecret is set" }}
{{- end }}

{{- if and .Values.mongodb.enabled .Values.mongodb.auth.enabled (not .Values.mongodb.auth.existingSecret) }}
  {{- if not .Values.mongodb.auth.rootUsername }}
    {{- fail "mongodb.auth.enabled is true but mongodb.auth.rootUsername is not set and no existingSecret provided" }}
  {{- end }}
  {{- if not .Values.mongodb.auth.rootPassword }}
    {{- fail "mongodb.auth.enabled is true but mongodb.auth.rootPassword is not set and no existingSecret provided" }}
  {{- end }}
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
