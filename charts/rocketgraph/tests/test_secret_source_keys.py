"""Secret source mappings, legacy upgrades and ConfigMap scalar names."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml

from test_render import CHART, component, render

class SecretSourceKeyTests(unittest.TestCase):
  def test_configmap_names_and_keys_remain_strings(self) -> None:
    for name, key in [("true", "123"), ("123", "false")]:
      with self.subTest(name = name, key = key):
        objects = render({ "backend": { "tls": {
          "xgtServerCertConfigMap": name,
          "xgtServerCertConfigMapKey": key } } })
        pod = component(objects, "Deployment", "backend")["spec"]["template"]
        volume = next(v for v in pod["spec"]["volumes"]
                      if v["name"] == "xgt-server-ca")
        self.assertEqual(volume["configMap"]["name"], name)
        self.assertEqual(volume["configMap"]["items"][0]["key"], key)

  def values(self, inline: bool) -> dict:
    return {
      "xgt": {
        "license": { "data": "license" } if inline else
          { "existingSecret": "customer-license" },
        "extraConfig": { "security.oidc": {
          "issuer": "https://idp.example.com", "audience": "xgt" } }
      },
      "backend": { "oidc": {
        "clientSecret": "password", "caCert": "ca" } if inline else {
        "existingSecret": "customer-oidc",
        "caCertExistingSecret": "customer-ca" } }
    }

  def assert_sources(self, objects: list, keys: dict, inline: bool,
                     mc: bool = True) -> None:
    for app in (["backend", "xgt"] if mc else ["xgt"]):
      spec = component(objects, "Deployment", app)["spec"]["template"]["spec"]
      mounts = spec["containers"][0]["volumeMounts"]
      ca = next(m for m in mounts if m["name"] == "oidc-ca-cert")
      self.assertEqual(ca["subPath"], keys["caCert"])
      self.assertEqual(ca["mountPath"], "/etc/ssl/certs/oidc-ca.pem")
      self.assertTrue(ca["readOnly"])
      if app == "xgt":
        license_mount = next(m for m in mounts if m["name"] == "xgt-license")
        self.assertEqual(license_mount["subPath"], keys["license"])
        self.assertEqual(license_mount["mountPath"], "/license/xgtd.lic")
        self.assertTrue(license_mount["readOnly"])
      else:
        env = spec["containers"][0]["env"]
        secret = next(e for e in env if e["name"] == "MC_OIDC_CLIENT_SECRET")
        ref = secret["valueFrom"]["secretKeyRef"]
        self.assertEqual(ref["key"], keys["clientSecret"])
        self.assertEqual(ref["name"],
                         "test-backend-oidc" if inline else "customer-oidc")
    conf = json.loads(component(objects, "ConfigMap", "xgt")
                      ["data"]["xgtd.conf"])
    self.assertEqual(conf["security.oidc"]["ca_cert"],
                     "/etc/ssl/certs/oidc-ca.pem")
    secrets = { o["metadata"]["name"]: o["stringData"]
                for o in objects if o["kind"] == "Secret" }
    if inline:
      self.assertEqual(secrets["test-xgt-license"],
                       { keys["license"]: "license" })
      self.assertEqual(secrets["test-backend-oidc-ca"],
                       { keys["caCert"]: "ca" })
      if mc:
        self.assertEqual(secrets["test-backend-oidc"],
                         { keys["clientSecret"]: "password" })
      else:
        self.assertNotIn("test-backend-oidc", secrets)
    else:
      self.assertEqual(secrets, {})

  def test_custom_keys_preserve_application_paths_and_env_names(self) -> None:
    keys = { "license": "123", "clientSecret": "false", "caCert": "true" }
    for inline in [False, True]:
      for restricted in [False, True]:
        with self.subTest(inline = inline, restricted = restricted):
          values = self.values(inline)
          values["xgt"]["license"]["secretKey"] = keys["license"]
          values["backend"]["oidc"]["secretKeys"] = {
            k: keys[k] for k in ["clientSecret", "caCert"] }
          if restricted:
            values["openshift"] = {
              "enabled": True, "scc": "restricted-v2" }
            values["fips"] = { "enabled": True }
          self.assert_sources(render(values), keys, inline)

  def test_xgt_only_can_use_a_custom_oidc_ca_key(self) -> None:
    values = self.values(True)
    values["missionControl"] = { "enabled": False }
    values["mongodb"] = { "enabled": False }
    values["backend"]["oidc"]["secretKeys"] = { "caCert": "root-ca.pem" }
    keys = { "license": "xgtd.lic", "clientSecret": "MC_OIDC_CLIENT_SECRET",
             "caCert": "root-ca.pem" }
    self.assert_sources(render(values), keys, True, mc = False)

  def test_reused_values_keep_defaults_and_allow_partial_overrides(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
      chart = Path(directory) / "rocketgraph"
      shutil.copytree(CHART, chart)
      path = chart / "values.yaml"
      defaults = yaml.safe_load(path.read_text())
      # Normal coalescing otherwise hides missing --reuse-values fallbacks.
      defaults["xgt"]["license"].pop("secretKey")
      defaults["backend"]["oidc"].pop("secretKeys")
      path.write_text(yaml.safe_dump(defaults))
      for inline in [False, True]:
        for partial in [False, True]:
          with self.subTest(inline = inline, partial = partial):
            values = self.values(inline)
            keys = { "license": "xgtd.lic",
                     "clientSecret": "MC_OIDC_CLIENT_SECRET",
                     "caCert": "oidc-ca.pem" }
            if partial:
              keys["clientSecret"] = "client-password"
              values["backend"]["oidc"]["secretKeys"] = {
                "clientSecret": keys["clientSecret"] }
            self.assert_sources(render(values, chart = chart), keys, inline)

  def test_invalid_source_keys_are_rejected(self) -> None:
    for field in ["license", "clientSecret", "caCert"]:
      for key in ["", ".", "..data", "bad/key", "a" * 254]:
        with self.subTest(field = field, key = key):
          values = self.values(True)
          if field == "license":
            values["xgt"]["license"]["secretKey"] = key
            path = "secretKey"
          else:
            values["backend"]["oidc"]["secretKeys"] = { field: key }
            path = "secretKeys/" + field
          self.assertIn(path, render(values, fails = True))

class XgtOidcCaTests(unittest.TestCase):
  def values(self) -> dict:
    return {
      "missionControl": { "enabled": False },
      "mongodb": { "enabled": False },
      "xgt": { "extraConfig": { "security.oidc": {
        "issuer": "https://keycloak.example.com", "audience": "xgt" } } }
    }

  def assert_ca(self, objects: list, app: str, name: str, key: str) -> None:
    spec = component(objects, "Deployment", app)["spec"]["template"]["spec"]
    volume = next(v for v in spec["volumes"] if v["name"] == "oidc-ca-cert")
    self.assertEqual(volume["secret"]["secretName"], name)
    mount = next(m for m in spec["containers"][0]["volumeMounts"]
                 if m["name"] == "oidc-ca-cert")
    self.assertEqual(mount["subPath"], key)
    self.assertEqual(mount["mountPath"], "/etc/ssl/certs/oidc-ca.pem")
    self.assertTrue(mount["readOnly"])

  def test_xgt_only_ca_is_mounted_and_automatically_configured(self) -> None:
    for inline in [False, True]:
      values = self.values()
      values["xgt"]["oidc"] = { "caCert": "ca" } if inline else {
        "caCertExistingSecret": "true" }
      values["xgt"]["oidc"]["secretKeys"] = { "caCert": "123" }
      if inline:
        values["openshift"] = { "enabled": True, "scc": "restricted-v2" }
        values["fips"] = { "enabled": True }
        values["xgt"]["license"] = { "existingSecret": "license" }
      objects = render(values)
      name = "test-xgt-oidc-ca" if inline else "true"
      self.assert_ca(objects, "xgt", name, "123")
      conf = json.loads(component(objects, "ConfigMap", "xgt")
                        ["data"]["xgtd.conf"])
      self.assertEqual(conf["security.oidc"]["ca_cert"],
                       "/etc/ssl/certs/oidc-ca.pem")
      secrets = [o for o in objects if o["kind"] == "Secret"]
      if inline:
        self.assertEqual(secrets[0]["stringData"], { "123": "ca" })
      self.assertEqual(len(secrets), int(inline))

  def test_xgt_and_backend_can_trust_different_ca_bundles(self) -> None:
    for inline in [False, True]:
      values = self.values()
      values["missionControl"]["enabled"] = True
      values["mongodb"]["enabled"] = True
      values["xgt"]["oidc"] = { "caCert": "xgt-ca" } if inline else {
        "caCertExistingSecret": "xgt-issuer-ca" }
      values["xgt"]["oidc"]["secretKeys"] = { "caCert": "root.crt" }
      values["backend"] = { "oidc": { "caCert": "backend-ca" } if inline
                            else { "caCertExistingSecret": "backend-ca" } }
      values["backend"]["oidc"]["secretKeys"] = { "caCert": "ca.crt" }
      objects = render(values)
      self.assert_ca(objects, "xgt",
                     "test-xgt-oidc-ca" if inline else "xgt-issuer-ca",
                     "root.crt")
      self.assert_ca(objects, "backend",
                     "test-backend-oidc-ca" if inline else "backend-ca",
                     "ca.crt")
      if inline:
        secrets = { o["metadata"]["name"]: o["stringData"]
                    for o in objects if o["kind"] == "Secret" }
        self.assertEqual(secrets["test-xgt-oidc-ca"], { "root.crt": "xgt-ca" })
        self.assertEqual(secrets["test-backend-oidc-ca"],
                         { "ca.crt": "backend-ca" })

  def test_external_config_and_explicit_ca_path_are_preserved(self) -> None:
    values = self.values()
    values["xgt"]["oidc"] = { "caCertExistingSecret": "keycloak-ca" }
    values["xgt"]["extraConfig"]["security.oidc"]["ca_cert"] = \
      "/conf/company-ca.pem"
    objects = render(values)
    conf = json.loads(component(objects, "ConfigMap", "xgt")
                      ["data"]["xgtd.conf"])
    self.assertEqual(conf["security.oidc"]["ca_cert"], "/conf/company-ca.pem")
    values["xgt"].pop("extraConfig")
    values["xgt"]["config"] = { "existingConfigMap": "mounted-config" }
    objects = render(values)
    self.assert_ca(objects, "xgt", "keycloak-ca", "oidc-ca.pem")
    self.assertFalse(any(o["kind"] == "ConfigMap" and
                        "xgtd.conf" in o.get("data", {}) for o in objects))
    values["xgt"].pop("config")
    values["xgt"]["files"] = { "existingClaim": "all-files" }
    self.assert_ca(render(values), "xgt", "keycloak-ca", "oidc-ca.pem")

  def test_ca_secret_is_not_created_for_a_disabled_xgt(self) -> None:
    values = self.values()
    values["xgt"].update(enabled = False, oidc = { "caCert": "ca" })
    objects = render(values)
    self.assertFalse(any(o["kind"] == "Secret" for o in objects))

  def test_existing_xgt_secret_takes_precedence_over_inline_ca(self) -> None:
    values = self.values()
    values["xgt"]["oidc"] = {
      "caCertExistingSecret": "keycloak-ca", "caCert": "ignored" }
    objects = render(values)
    self.assert_ca(objects, "xgt", "keycloak-ca", "oidc-ca.pem")
    self.assertFalse(any(o["kind"] == "Secret" for o in objects))

  def test_legacy_backend_fallback_works_without_the_new_defaults(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
      chart = Path(directory) / "rocketgraph"
      shutil.copytree(CHART, chart)
      path = chart / "values.yaml"
      defaults = yaml.safe_load(path.read_text())
      defaults["xgt"].pop("oidc")
      path.write_text(yaml.safe_dump(defaults))
      values = self.values()
      values["backend"] = { "oidc": {
        "caCertExistingSecret": "legacy-ca",
        "secretKeys": { "caCert": "legacy.pem" } } }
      objects = render(values, chart = chart)
      self.assert_ca(objects, "xgt", "legacy-ca", "legacy.pem")

  def test_invalid_xgt_ca_key_is_rejected(self) -> None:
    values = self.values()
    values["xgt"]["oidc"] = {
      "caCert": "ca", "secretKeys": { "caCert": "..data" } }
    self.assertIn("secretKeys/caCert", render(values, fails = True))

if __name__ == "__main__":
  unittest.main()
