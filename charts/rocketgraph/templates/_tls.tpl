{{/* Keep legacy key names when --reuse-values omits new chart defaults. */}}
{{- define "rocketgraph.frontendTlsKeys" -}}
{{- merge (deepCopy (.Values.frontend.tls.secretKeys | default dict)) (dict
  "cert" "public.pem" "key" "private.pem" "caCert" "chain.pem") | toYaml -}}
{{- end -}}

{{- define "rocketgraph.backendTlsKeys" -}}
{{- merge (deepCopy (.Values.backend.tls.secretKeys | default dict)) (dict
  "cert" "proxy-client-cert.pem" "key" "proxy-client-key.pem" "caCert" "xgt-server.pem") | toYaml -}}
{{- end -}}

{{- define "rocketgraph.xgtTlsKeys" -}}
{{- merge (deepCopy (.Values.xgt.ssl.secretKeys | default dict)) (dict
  "cert" "server.cert.pem" "key" "server.key.pem" "caCert" "ca-chain.cert.pem") | toYaml -}}
{{- end -}}

{{/* Only emitted inline fields must be distinct; existing Secrets may use PEM bundles. */}}
{{- define "rocketgraph.validateInlineTlsKeys" -}}
{{- $used := dict -}}
{{- range $field, $payload := .inline -}}
  {{- if $payload -}}
    {{- $key := index $.keys $field -}}
    {{- if hasKey $used $key -}}
      {{- fail (printf "%s.secretKeys.%s and %s.secretKeys.%s both select %q; set distinct Secret key names for inline certificates" $.prefix (index $used $key) $.prefix $field $key) -}}
    {{- end -}}
    {{- $_ := set $used $key $field -}}
  {{- end -}}
{{- end -}}
{{- end -}}
