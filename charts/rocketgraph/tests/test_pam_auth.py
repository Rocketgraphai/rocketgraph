"""Verify that token deployments cannot retain passwordless PAM login."""
import unittest

from test_render import component, render


class PamAuthTests(unittest.TestCase):
  def assert_pam_denied(self, values):
    objects = render(values)
    config = next(obj for obj in objects if obj["kind"] == "ConfigMap"
                  and "xgtd" in obj.get("data", {}))
    self.assertIn("auth requisite pam_deny.so", config["data"]["xgtd"])
    pod = component(objects, "Deployment", "xgt")["spec"]["template"]
    self.assertIn("checksum/pam", pod["metadata"]["annotations"])
    container = pod["spec"]["containers"][0]
    mount = next(item for item in container["volumeMounts"]
                 if item["mountPath"] == "/etc/pam.d/xgtd")
    self.assertTrue(mount["readOnly"])
    volume = next(item for item in pod["spec"]["volumes"]
                  if item["name"] == mount["name"])
    self.assertEqual(volume["configMap"]["name"],
                     config["metadata"]["name"])
    self.assertEqual(mount["subPath"], "xgtd")

  def test_oidc_issuer_blocks_pam_for_supported_config_forms(self):
    for config in [
      {"security.oidc": {"issuer": "https://idp.example.com"}},
      {"security": {"oidc": {"issuer": "https://idp.example.com"}}},
      {"security": {"oidc.issuer": "https://idp.example.com"}},
      {"security.oidc.issuer": "https://idp.example.com"}
    ]:
      with self.subTest(config = config):
        self.assert_pam_denied({"xgt": {"extraConfig": config}})

  def test_external_config_and_custom_startup_default_to_denial(self):
    for values in [
      {"config": {"existingConfigMap": "company-config"}},
      {"files": {"existingClaim": "company-files"}},
      {"command": ["/opt/xgtd/bin/xgtd"]},
      {"args": ["-Dsecurity.oidc.issuer=https://idp.example.com"]},
      {"env": [{"name": "CUSTOM_CONFIG", "value": "/custom/conf"}]}
    ]:
      with self.subTest(values = values):
        self.assert_pam_denied({"xgt": values})

  def test_explicit_false_and_restricted_profile_mount_deny_policy(self):
    values = {"xgt": {"auth": {"pam": {"enabled": False}}}}
    self.assert_pam_denied(values)
    values.update({"openshift": {"enabled": True, "scc": "restricted-v2"},
                   "fips": {"enabled": True}})
    values["xgt"]["license"] = {"existingSecret": "test-license"}
    self.assert_pam_denied(values)

  def test_default_and_explicit_opt_in_keep_image_pam_configuration(self):
    for values in [{}, {"xgt": {
      "extraConfig": {"security.oidc": {"issuer": "https://idp.example.com"}},
      "auth": {"pam": {"enabled": True}}
    }}]:
      with self.subTest(values = values):
        objects = render(values)
        self.assertFalse(any("xgtd" in obj.get("data", {})
                             for obj in objects if obj["kind"] == "ConfigMap"))
        pod = component(objects, "Deployment", "xgt")["spec"]["template"]
        self.assertNotIn("checksum/pam", pod["metadata"]["annotations"])
        self.assertFalse(any(item["mountPath"] == "/etc/pam.d/xgtd"
                             for item in pod["spec"]["containers"][0]
                             ["volumeMounts"]))

  def test_disabled_xgt_omits_pam_resources(self):
    objects = render({"missionControl": {"enabled": False},
                      "xgt": {"enabled": False,
                              "auth": {"pam": {"enabled": False}}}})
    self.assertFalse(any("xgtd" in obj.get("data", {}) for obj in objects
                         if obj["kind"] == "ConfigMap"))

  def test_pam_denial_rejects_sssd_ldap_configuration(self):
    message = render({"xgt": {
      "auth": {"pam": {"enabled": False}},
      "ldap": {"enabled": True, "uri": "ldaps://ldap.example.com",
               "baseDn": "dc=example,dc=com"}
    }}, fails = True)
    self.assertIn("xgt.auth.pam.enabled=true", message)

  def test_existing_ldap_configuration_can_explicitly_enable_pam(self):
    objects = render({"xgt": {
      "auth": {"pam": {"enabled": True}},
      "config": {"existingConfigMap": "company-config"},
      "ldap": {"enabled": True, "uri": "ldaps://ldap.example.com",
               "baseDn": "dc=example,dc=com"}
    }})
    self.assertFalse(any("xgtd" in obj.get("data", {}) for obj in objects
                         if obj["kind"] == "ConfigMap"))

  def test_pam_policy_cannot_be_shadowed_by_extra_mounts(self):
    for path in ["/", "/etc", "/etc/pam.d", "/etc/pam.d/xgtd"]:
      with self.subTest(path = path):
        message = render({"xgt": {
          "auth": {"pam": {"enabled": False}},
          "extraVolumes": [{"name": "custom", "emptyDir": {}}],
          "extraVolumeMounts": [{"name": "custom", "mountPath": path}]
        }}, fails = True)
        self.assertIn("PAM", message)

  def test_equivalent_pam_mount_paths_are_rejected(self):
    for path in ["//", "/etc/", "/etc//pam.d", "/etc/pam.d/.",
                 "/etc/pam.d/xgtd/.", "/etc/ssh/../pam.d",
                 "/etc/pam.d/../.."]:
      with self.subTest(path = path):
        message = render({"xgt": {
          "extraVolumes": [{"name": "custom", "emptyDir": {}}],
          "extraVolumeMounts": [{"name": "custom", "mountPath": path}]
        }}, fails = True)
        self.assertIn("PAM", message)

  def test_administrator_pam_volume_name_is_allowed_only_with_opt_in(self):
    values = {"xgt": {
      "auth": {"pam": {"enabled": True}},
      "extraVolumes": [{"name": "xgt-pam",
                        "configMap": {"name": "company-pam"}}],
      "extraVolumeMounts": [{"name": "xgt-pam",
                             "mountPath": "/etc/pam.d/xgtd",
                             "subPath": "xgtd", "readOnly": True}]
    }}
    objects = render(values)
    pod = component(objects, "Deployment", "xgt")["spec"]["template"]
    volumes = [volume for volume in pod["spec"]["volumes"]
               if volume["name"] == "xgt-pam"]
    self.assertEqual(volumes, values["xgt"]["extraVolumes"])
    self.assertNotIn("checksum/pam", pod["metadata"]["annotations"])
    self.assertFalse(any("xgtd" in obj.get("data", {}) for obj in objects
                         if obj["kind"] == "ConfigMap"))
    for enabled in [False, None]:
      values["xgt"]["auth"]["pam"]["enabled"] = enabled
      self.assertIn("volume names", render(values, fails = True))

  def test_equivalent_custom_mount_paths_cannot_collide(self):
    message = render({"xgt": {
      "extraVolumes": [{"name": "custom", "emptyDir": {}}],
      "extraVolumeMounts": [
        {"name": "custom", "mountPath": "/custom/config"},
        {"name": "custom", "mountPath": "/custom//config/."}
      ]
    }}, fails = True)
    self.assertIn("unique mount paths", message)

  def test_string_boolean_is_rejected(self):
    message = render({"xgt": {
      "auth": {"pam": {"enabled": "false"}}
    }}, fails = True)
    self.assertIn("enabled", message)

  def test_obsolete_basic_setting_is_rejected(self):
    message = render({"xgt": {
      "auth": {"basic": {"enabled": False}}
    }}, fails = True)
    self.assertIn("basic", message)
