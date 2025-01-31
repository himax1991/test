tee ci/.helm/templates/configmap.yaml << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: release-channels-data
data:
  channels.yaml: |
{{ $.Files.Get "channels.yaml" | indent 4 }}
EOF
