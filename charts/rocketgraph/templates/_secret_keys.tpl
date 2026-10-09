{{/* Keep historical keys when --reuse-values omits new chart defaults. */}}
{{- define "rocketgraph.backendOidcKeys" -}}
{{- merge (deepCopy (.Values.backend.oidc.secretKeys | default dict)) (dict
  "clientSecret" "MC_OIDC_CLIENT_SECRET" "caCert" "oidc-ca.pem") | toYaml -}}
{{- end -}}

{{- define "rocketgraph.xgtLicenseKey" -}}
{{- .Values.xgt.license.secretKey | default "xgtd.lic" -}}
{{- end -}}
