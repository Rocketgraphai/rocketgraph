{{/*
Validate configuration — fail early instead of broken pods.
Call via: {{- include "rocketgraph.validate" . }}
*/}}
{{- define "rocketgraph.validate" -}}

{{- if and .Values.openshift.enabled (eq .Values.openshift.scc "restricted-v2") }}
  {{- if and .Values.missionControl.enabled (not .Values.fips.enabled) }}
    {{- fail "restricted-v2 with Mission Control requires fips.enabled=true; the non-FIPS frontend image has different startup and writable paths" }}
  {{- end }}
  {{- if .Values.xgt.licenseManager.enabled }}
    {{- fail "restricted-v2 does not support the bundled License Manager; use an external license server or a license file" }}
  {{- end }}
  {{- if and .Values.xgt.enabled .Values.xgt.ldap.enabled }}
    {{- fail "restricted-v2 direct startup does not run in-container SSSD; use OpenShift OAuth or Keycloak authentication" }}
  {{- end }}
  {{- range $name := list "frontend" "backend" "mongodb" "xgt" }}
    {{- $component := index $.Values $name }}
    {{- $active := ternary $.Values.missionControl.enabled $component.enabled (has $name (list "frontend" "backend")) }}
    {{- if $active }}
      {{- range $context := list $component.podSecurityContext $component.containerSecurityContext }}
        {{- range $field := list "runAsUser" "runAsGroup" "fsGroup" "supplementalGroups" }}
          {{- if and (hasKey $context $field) (ne (index $context $field) nil) }}
            {{- fail (printf "restricted-v2 assigns the namespace UID/group: remove %s security context %s" $name $field) }}
          {{- end }}
        {{- end }}
        {{- if $context.privileged }}{{- fail (printf "restricted-v2 does not permit privileged %s containers" $name) }}{{- end }}
        {{- if dig "capabilities" "add" (list) $context }}{{- fail (printf "restricted-v2 profile does not add capabilities for %s" $name) }}{{- end }}
      {{- end }}
    {{- end }}
  {{- end }}
  {{- if and .Values.xgt.enabled (not .Values.xgt.files.existingClaim) (not .Values.xgt.config.existingConfigMap) (not .Values.xgt.license.existingSecret) (not .Values.xgt.license.data) (not (index .Values.xgt.extraConfig "license.location")) }}
    {{- fail "restricted-v2 needs a readable license: set xgt.license.existingSecret (or data), xgt.files.existingClaim, or xgt.extraConfig.license.location. The bundled image license is not readable by an arbitrary UID." }}
  {{- end }}
{{- end }}

{{- if .Values.xgt.enabled }}
{{- if .Values.xgt.files.existingClaim }}
  {{- if or .Values.xgt.config.existingConfigMap .Values.xgt.config.grouplabelCsv .Values.xgt.config.labelCsv .Values.xgt.config.proxyList .Values.xgt.extraConfig }}
    {{- fail "xgt.files.existingClaim uses configuration files on the PVC; remove xgt.config overrides and xgt.extraConfig and edit the PVC files instead" }}
  {{- end }}
  {{- if or .Values.xgt.license.existingSecret .Values.xgt.license.data .Values.xgt.licenseManager.enabled .Values.xgt.ldap.enabled .Values.xgt.ssl.existingSecret .Values.xgt.ssl.cert .Values.xgt.ssl.key .Values.xgt.ssl.caCert }}
    {{- fail "xgt.files.existingClaim supplies license and TLS files on the PVC; remove separate license/TLS/LDAP sources and the bundled license manager" }}
  {{- end }}
{{- end }}
{{- if and .Values.xgt.config.existingConfigMap (or .Values.xgt.config.grouplabelCsv .Values.xgt.config.labelCsv .Values.xgt.config.proxyList .Values.xgt.extraConfig) }}
  {{- fail "xgt.config.existingConfigMap supplies complete configuration; remove inline xgt.config overrides and xgt.extraConfig" }}
{{- end }}
{{- if and .Values.xgt.files.subPath (not .Values.xgt.files.existingClaim) }}
  {{- fail "xgt.files.subPath requires xgt.files.existingClaim" }}
{{- end }}
{{- $volumeNames := list "xgt-config" "xgt-data" "xgt-log" "xgt-tls" "xgt-license" "sssd-config" "oidc-ca-cert" "xgt-files" }}
{{- range .Values.xgt.extraVolumes }}
  {{- if or (not .name) (has .name $volumeNames) }}{{- fail "xgt.extraVolumes names must be unique and must not replace chart volume names" }}{{- end }}
  {{- $volumeNames = append $volumeNames .name }}
{{- end }}
{{- $mountPaths := list "/data" "/log" "/etc/ssl/certs/oidc-ca.pem" }}
{{- if .Values.xgt.files.existingClaim }}
  {{- $mountPaths = concat $mountPaths (list "/conf" "/license") }}
{{- else }}
  {{- $mountPaths = concat $mountPaths (list "/conf/xgtd.conf" "/conf/audit.xml" "/conf/grouplabel.csv" "/conf/label.csv") }}
  {{- if .Values.xgt.ssl.enabled }}{{- $mountPaths = append $mountPaths "/conf/ssl" }}{{- end }}
  {{- if or .Values.xgt.license.existingSecret .Values.xgt.license.data }}{{- $mountPaths = append $mountPaths "/license/xgtd.lic" }}{{- end }}
  {{- if .Values.xgt.ldap.enabled }}{{- $mountPaths = append $mountPaths "/etc/sssd-config" }}{{- end }}
  {{- if .Values.xgt.config.proxyList }}{{- $mountPaths = append $mountPaths "/conf/proxy_list" }}{{- end }}
{{- end }}
{{- range .Values.xgt.extraVolumeMounts }}
  {{- if or (not .mountPath) (has .mountPath $mountPaths) }}{{- fail "xgt.extraVolumeMounts must use unique mount paths and must not replace chart mounts" }}{{- end }}
  {{- $mountPaths = append $mountPaths .mountPath }}
{{- end }}
{{- end }}


{{- if .Values.missionControl.enabled }}
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

{{- end }}

{{- if and .Values.xgt.enabled (not .Values.xgt.files.existingClaim) .Values.xgt.ssl.enabled .Values.xgt.ssl.mtls (not .Values.xgt.ssl.existingSecret) (not .Values.xgt.ssl.caCert) }}
  {{- fail "xgt.ssl.mtls is true but no existingSecret or inline caCert provided for ca-chain.cert.pem" }}
{{- end }}
{{- if and .Values.xgt.enabled (not .Values.xgt.files.existingClaim) .Values.xgt.ssl.enabled .Values.xgt.ssl.mtls .Values.xgt.ssl.existingSecret .Values.xgt.ssl.caCert }}
  {{- fail "xgt.ssl.caCert is ignored when existingSecret is set — include ca-chain.cert.pem in the existing secret instead" }}
{{- end }}

{{- if and .Values.xgt.enabled (not .Values.xgt.files.existingClaim) .Values.xgt.ssl.enabled (not .Values.xgt.ssl.existingSecret) }}
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

{{- if and .Values.xgt.enabled (not .Values.xgt.files.existingClaim) .Values.xgt.ldap.enabled (not .Values.xgt.ldap.existingSecret) (not .Values.xgt.ldap.sssdConfig) }}
  {{- if not .Values.xgt.ldap.uri }}
    {{- fail "xgt.ldap.enabled is true but xgt.ldap.uri is not set" }}
  {{- end }}
  {{- if not .Values.xgt.ldap.baseDn }}
    {{- fail "xgt.ldap.enabled is true but xgt.ldap.baseDn is not set" }}
  {{- end }}
{{- end }}

{{- if and .Values.openshift.enabled (not (has .Values.openshift.scc (list "anyuid" "nonroot" "restricted-v2"))) }}
  {{- fail (printf "openshift.scc %q is not valid — must be \"anyuid\", \"nonroot\" or \"restricted-v2\"" .Values.openshift.scc) }}
{{- end }}

{{- if and .Values.mongodb.enabled (gt (.Values.mongodb.replicas | int) 1) }}
  {{- fail "mongodb.replicas > 1 is not supported — this chart deploys standalone MongoDB with no replica set. To use a MongoDB cluster, set mongodb.enabled: false and point mongodb.externalUri at your cluster." }}
{{- end }}

{{- if and .Values.xgt.enabled (gt (.Values.xgt.replicas | int) 1) }}
  {{- fail "xgt.replicas > 1 is not supported — multiple xgt instances would have no shared state in this configuration." }}
{{- end }}

{{- if and .Values.missionControl.enabled (not .Values.xgt.enabled) (not .Values.backend.env.MC_DEFAULT_XGT_HOST) }}
  {{- fail "xgt.enabled is false but backend.env.MC_DEFAULT_XGT_HOST is not set" }}
{{- end }}

{{- if and .Values.missionControl.enabled (not .Values.mongodb.enabled) (not .Values.mongodb.externalUri) (not .Values.mongodb.externalUriSecret) }}
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

{{- if and .Values.missionControl.enabled (gt (.Values.backend.replicas | int) 1) }}
  {{- fail "backend.replicas > 1 is not supported — session state is not shared across instances." }}
{{- end }}

{{- range $name := list "frontend" "backend" "xgt" "mongodb" }}
  {{- $active := ternary $.Values.missionControl.enabled ((index $.Values $name).enabled) (has $name (list "frontend" "backend")) }}
  {{- if and $active (hasKey $.Values $name) }}
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
