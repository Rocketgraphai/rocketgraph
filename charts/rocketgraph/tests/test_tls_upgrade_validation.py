"""Upgrade compatibility and invalid TLS Secret key regressions."""
import itertools
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml

from test_render import CHART, component, render


TLS_FIELDS = {'frontend': 'tls', 'backend': 'tls', 'xgt': 'ssl'}
LEGACY_KEYS = {
    'frontend': {'cert': 'public.pem', 'key': 'private.pem', 'caCert': 'chain.pem'},
    'backend': {'cert': 'proxy-client-cert.pem', 'key': 'proxy-client-key.pem',
                'caCert': 'xgt-server.pem'},
    'xgt': {'cert': 'server.cert.pem', 'key': 'server.key.pem',
            'caCert': 'ca-chain.cert.pem'},
}


def inline_tls(app):
    return {
        'frontend': {'mtls': True, 'publicCert': 'cert', 'privateKey': 'key',
                     'certChain': 'ca'},
        'backend': {'mtls': True, 'proxyClientCert': 'cert', 'proxyClientKey': 'key',
                    'xgtServerCert': 'ca'},
        'xgt': {'enabled': True, 'mtls': True, 'cert': 'cert', 'key': 'key',
                'caCert': 'ca'},
    }[app]


class TlsUpgradeValidationTests(unittest.TestCase):
    def legacy_chart(self, directory):
        # --reuse-values uses the previous chart's defaults rather than new ones.
        # Remove the new maps from chart defaults so normal coalescing cannot hide
        # a missing fallback, unlike simply omitting secretKeys from an overlay.
        chart = Path(directory) / 'rocketgraph'
        shutil.copytree(CHART, chart)
        path = chart / 'values.yaml'
        defaults = yaml.safe_load(path.read_text())
        for app, field in TLS_FIELDS.items():
            defaults[app][field].pop('secretKeys')
        defaults['backend']['tls'].pop('xgtServerCertConfigMapKey')
        path.write_text(yaml.safe_dump(defaults))
        return chart

    def assert_keys(self, objects, expected, inline):
        for app, keys in expected.items():
            pod = component(objects, 'Deployment', app)['spec']['template']['spec']
            if app == 'xgt':
                volume = next(v for v in pod['volumes'] if v['name'] == 'xgt-tls')
                actual = {item['key'] for item in volume['secret']['items']}
            else:
                actual = {mount['subPath'] for mount in
                          pod['containers'][0]['volumeMounts']
                          if mount['name'] == 'tls-certs'}
            self.assertEqual(actual, set(keys.values()))
            if inline:
                secret = component(objects, 'Secret', app)
                self.assertEqual(secret['stringData'],
                                 {keys['cert']: 'cert', keys['key']: 'key',
                                  keys['caCert']: 'ca'})

    def test_reused_values_without_key_maps_keep_legacy_mounts_and_inline_data(self):
        with tempfile.TemporaryDirectory() as directory:
            chart = self.legacy_chart(directory)
            for inline in (False, True):
                with self.subTest(inline=inline):
                    values = {app: {field: inline_tls(app) if inline else {
                        'existingSecret': app + '-tls', 'mtls': True,
                        **({'enabled': True} if app == 'xgt' else {})}}
                        for app, field in TLS_FIELDS.items()}
                    self.assert_keys(render(values, chart=chart), LEGACY_KEYS, inline)

    def test_partial_key_maps_without_new_defaults_keep_unspecified_legacy_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            chart = self.legacy_chart(directory)
            values = {app: {field: dict(inline_tls(app), secretKeys={'cert': 'tls.crt'})}
                      for app, field in TLS_FIELDS.items()}
            expected = {app: dict(keys, cert='tls.crt')
                        for app, keys in LEGACY_KEYS.items()}
            self.assert_keys(render(values, chart=chart), expected, True)

    def test_reused_values_keep_configmap_ca_key_default_and_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            chart = self.legacy_chart(directory)
            for key in (None, 'company-ca.pem', '123'):
                with self.subTest(key=key):
                    tls = {'xgtServerCertConfigMap': 'true'}
                    if key is not None:
                        tls['xgtServerCertConfigMapKey'] = key
                    objects = render({'backend': {'tls': tls}}, chart=chart)
                    pod = component(objects, 'Deployment', 'backend')
                    volumes = pod['spec']['template']['spec']['volumes']
                    volume = next(v for v in volumes
                                  if v['name'] == 'xgt-server-ca')
                    self.assertEqual(volume['configMap'], {
                        'name': 'true',
                        'items': [{'key': key or 'service-ca.crt',
                                   'path': 'xgt-server.pem'}],
                    })

    def test_reserved_names_are_rejected_for_every_component_and_key(self):
        for app, field in TLS_FIELDS.items():
            for key in ('cert', 'key', 'caCert'):
                for invalid in ('.', '..', '..data', '...pem'):
                    with self.subTest(app=app, key=key, invalid=invalid):
                        values = {app: {field: dict(inline_tls(app),
                                                   secretKeys={key: invalid})}}
                        self.assertIn('secretKeys/' + key, render(values, fails=True))

    def test_configmap_ca_keys_reject_invalid_names_and_preserve_valid_names(self):
        for key in ('', 'ca/bundle.crt', '.', '..', '..data', 'a' * 254):
            with self.subTest(invalid=key):
                values = {'backend': {'tls': {
                    'xgtServerCertConfigMap': 'xgt-service-ca',
                    'xgtServerCertConfigMapKey': key,
                }}}
                self.assertIn('xgtServerCertConfigMapKey',
                              render(values, fails=True))
        for key in ('service-ca.crt', '.ca.pem', '-ca_bundle', 'ca..pem',
                    '123', 'a' * 253):
            with self.subTest(valid=key):
                objects = render({'backend': {'tls': {
                    'xgtServerCertConfigMap': 'xgt-service-ca',
                    'xgtServerCertConfigMapKey': key,
                }}})
                pod = component(objects, 'Deployment', 'backend')
                volumes = pod['spec']['template']['spec']['volumes']
                volume = next(v for v in volumes
                              if v['name'] == 'xgt-server-ca')
                self.assertEqual(volume['configMap']['items'],
                                 [{'key': key, 'path': 'xgt-server.pem'}])

    def test_valid_dot_and_punctuation_names_remain_supported(self):
        keys = {'cert': '.cert.pem', 'key': '-private_key', 'caCert': 'ca..pem'}
        values = {app: {field: dict(inline_tls(app), secretKeys=keys)}
                  for app, field in TLS_FIELDS.items()}
        self.assert_keys(render(values), {app: keys for app in TLS_FIELDS}, True)

    def test_inline_collisions_fail_with_the_conflicting_settings(self):
        for app, field in TLS_FIELDS.items():
            for pair in itertools.combinations(('cert', 'key', 'caCert'), 2):
                with self.subTest(app=app, pair=pair):
                    values = {app: {field: dict(inline_tls(app),
                        secretKeys={key: 'same.pem' for key in pair})}}
                    error = render(values, fails=True)
                    self.assertIn('distinct Secret key names', error)
                    for key in pair:
                        self.assertIn(f'{app}.{field}.secretKeys.{key}', error)

    def test_unused_inline_ca_key_can_match_the_certificate_key(self):
        values = {}
        for app, field in TLS_FIELDS.items():
            tls = inline_tls(app)
            tls.pop({'frontend': 'certChain', 'backend': 'xgtServerCert',
                     'xgt': 'caCert'}[app])
            tls['mtls'] = False
            tls['secretKeys'] = {'cert': 'same.pem', 'caCert': 'same.pem'}
            values[app] = {field: tls}
        objects = render(values)
        for app in TLS_FIELDS:
            data = component(objects, 'Secret', app)['stringData']
            self.assertEqual(data['same.pem'], 'cert')
            self.assertEqual(len(data), 2)

    def test_existing_secret_bundles_and_disabled_components_are_not_rejected(self):
        keys = {'cert': 'bundle.pem', 'key': 'bundle.pem', 'caCert': 'bundle.pem'}
        values = {app: {field: {'existingSecret': app + '-tls', 'mtls': True,
                    'secretKeys': keys, **({'enabled': True} if app == 'xgt' else {})}}
                  for app, field in TLS_FIELDS.items()}
        objects = render(values)
        self.assertFalse(any(obj['kind'] == 'Secret' for obj in objects))
        values['missionControl'] = {'enabled': False}
        for app, field in TLS_FIELDS.items():
            values[app][field] = dict(inline_tls(app), secretKeys=keys)
        values['xgt']['ssl']['enabled'] = False
        objects = render(values)
        self.assertFalse(any(obj['kind'] == 'Secret' for obj in objects))


if __name__ == '__main__':
    unittest.main()
