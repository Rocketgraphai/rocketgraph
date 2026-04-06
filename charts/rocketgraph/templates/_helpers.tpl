{{/*
Chart label string
*/}}
{{- define "rocketgraph.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rocketgraph.labels" -}}
helm.sh/chart: {{ include "rocketgraph.chart" . }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Resource name helpers — prefix every name with the release name.
*/}}
{{- define "rocketgraph.fullname.frontend" -}}
{{- printf "%s-frontend" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "rocketgraph.fullname.backend" -}}
{{- printf "%s-backend" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "rocketgraph.fullname.mongodb" -}}
{{- printf "%s-mongodb" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "rocketgraph.fullname.xgt" -}}
{{- printf "%s-xgt" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "rocketgraph.fullname.serviceaccount" -}}
{{- printf "%s-rocketgraph" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Frontend TLS secret name
*/}}
{{- define "rocketgraph.frontendTlsSecret" -}}
{{- .Values.frontend.tls.existingSecret | default (printf "%s-frontend-tls" .Release.Name) }}
{{- end }}

{{/*
Backend TLS secret name
*/}}
{{- define "rocketgraph.backendTlsSecret" -}}
{{- .Values.backend.tls.existingSecret | default (printf "%s-backend-tls" .Release.Name) }}
{{- end }}


{{/*
MongoDB auth secret name
*/}}
{{- define "rocketgraph.mongodbAuthSecret" -}}
{{- .Values.mongodb.auth.existingSecret | default (printf "%s-mongodb-auth" .Release.Name) }}
{{- end }}

{{/*
XGT TLS secret name
*/}}
{{- define "rocketgraph.xgtTlsSecret" -}}
{{- .Values.xgt.ssl.existingSecret | default (printf "%s-xgt-tls" .Release.Name) }}
{{- end }}

{{/*
XGT license secret name
*/}}
{{- define "rocketgraph.xgtLicenseSecret" -}}
{{- .Values.xgt.license.existingSecret | default (printf "%s-xgt-license" .Release.Name) }}
{{- end }}

{{/*
XGT LDAP secret name
*/}}
{{- define "rocketgraph.xgtLdapSecret" -}}
{{- .Values.xgt.ldap.existingSecret | default (printf "%s-xgt-ldap" .Release.Name) }}
{{- end }}

{{/*
Backend OIDC client secret name
*/}}
{{- define "rocketgraph.backendOidcSecret" -}}
{{- .Values.backend.oidc.existingSecret | default (printf "%s-backend-oidc" .Release.Name) }}
{{- end }}

{{/*
Backend OIDC CA cert secret name
*/}}
{{- define "rocketgraph.backendOidcCaSecret" -}}
{{- .Values.backend.oidc.caCertExistingSecret | default (printf "%s-backend-oidc-ca" .Release.Name) }}
{{- end }}

{{/*
PodDisruptionBudget — usage: {{ include "rocketgraph.pdb" (list "frontend" .) }}
*/}}
{{- define "rocketgraph.pdb" -}}
{{- $componentName := index . 0 -}}
{{- $root := index . 1 -}}
{{- $componentValues := index $root.Values $componentName -}}
{{- if $componentValues.podDisruptionBudget.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include (printf "rocketgraph.fullname.%s" $componentName) $root }}
  labels:
    app: {{ $componentName }}
    {{- include "rocketgraph.labels" $root | nindent 4 }}
spec:
  {{- if hasKey $componentValues.podDisruptionBudget "maxUnavailable" }}
  maxUnavailable: {{ $componentValues.podDisruptionBudget.maxUnavailable }}
  {{- else }}
  minAvailable: {{ ternary $componentValues.podDisruptionBudget.minAvailable 1 (hasKey $componentValues.podDisruptionBudget "minAvailable") }}
  {{- end }}
  selector:
    matchLabels:
      app: {{ $componentName }}
      app.kubernetes.io/instance: {{ $root.Release.Name }}
{{- end }}
{{- end -}}
