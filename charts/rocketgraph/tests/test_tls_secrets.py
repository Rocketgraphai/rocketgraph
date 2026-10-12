"""TLS Secret compatibility checks for legacy, Kubernetes and OpenShift keys."""
import json
import unittest

import yaml

from test_render import CHART, component, render


class TlsSecretTests(unittest.TestCase):
    def profiles(self):
        return [{}, {'openshift': {'enabled': True, 'scc': 'restricted-v2'},
                     'fips': {'enabled': True}}]

    def values(self, profile):
        return dict(profile, xgt={'license': {'existingSecret': 'license'}})

    def volume(self, objects, app, name):
        pod = component(objects, 'Deployment', app)['spec']['template']['spec']
        return next(v for v in pod['volumes'] if v['name'] == name), pod

    def test_standard_secret_keys_keep_fixed_container_paths(self):
        for profile in self.profiles():
            with self.subTest(profile=profile):
                values = self.values(profile)
                values['xgt']['ssl'] = {'enabled': True, 'existingSecret': 'xgt-serving',
                    'secretKeys': {'cert': 'tls.crt', 'key': 'tls.key'}}
                values['xgt']['service'] = {'annotations': {
                    'service.beta.openshift.io/serving-cert-secret-name': 'xgt-serving'}}
                values['frontend'] = {'tls': {'existingSecret': 'frontend-serving',
                    'secretKeys': {'cert': 'tls.crt', 'key': 'tls.key'}}}
                objects = render(values)
                volume, pod = self.volume(objects, 'xgt', 'xgt-tls')
                items = volume['secret']['items']
                self.assertEqual({i['key']: i['path'] for i in items},
                    {'tls.crt': 'certs/server.cert.pem',
                     'tls.key': 'private/server.key.pem'})
                self.assertEqual(items[1]['mode'], 0o440 if profile else 0o400)
                self.assertEqual(volume['secret']['secretName'], 'xgt-serving')
                self.assertEqual(json.loads(component(objects, 'ConfigMap', 'xgt')
                    ['data']['xgtd.conf'])['system.usessl'], 'true')
                self.assertEqual(component(objects, 'Service', 'xgt')['metadata']['annotations'],
                    values['xgt']['service']['annotations'])
                frontend, pod = self.volume(objects, 'frontend', 'tls-certs')
                self.assertEqual(frontend['secret']['secretName'], 'frontend-serving')
                mounts = {m['mountPath']: m for m in pod['containers'][0]['volumeMounts']}
                self.assertEqual(mounts['/etc/ssl/certs/td.pem']['subPath'], 'tls.crt')
                self.assertEqual(mounts['/etc/ssl/private/td.pem']['subPath'], 'tls.key')
                self.assertFalse(any(o['kind'] == 'Secret' and o['metadata']['labels']
                    .get('app') in ['frontend', 'xgt'] for o in objects))

    def test_separate_client_ca_supports_external_and_inline_server_certificates(self):
        for profile in self.profiles():
            for external in [True, False]:
                with self.subTest(profile=profile, external=external):
                    values = self.values(profile)
                    ssl = {'enabled': True, 'mtls': True, 'caCertExistingSecret': 'clients-ca',
                           'secretKeys': {'caCert': 'client-ca.pem'}}
                    ssl.update({'existingSecret': 'serving',
                                'secretKeys': {'cert': 'tls.crt', 'key': 'tls.key',
                                                       'caCert': 'client-ca.pem'}}
                               if external else {'cert': 'server', 'key': 'private'})
                    values['xgt']['ssl'] = ssl
                    objects = render(values)
                    volume, _ = self.volume(objects, 'xgt', 'xgt-tls')
                    sources = volume['projected']['sources']
                    self.assertEqual(len(sources), 2)
                    cert, ca = [s['secret'] for s in sources]
                    self.assertEqual(ca, {'name': 'clients-ca', 'items': [
                        {'key': 'client-ca.pem', 'path': 'certs/ca-chain.cert.pem'}]})
                    self.assertEqual(cert['name'], 'serving' if external else 'test-xgt-tls')
                    self.assertEqual([i['key'] for i in cert['items']],
                                     ['tls.crt', 'tls.key'] if external else
                                     ['server.cert.pem', 'server.key.pem'])
                    config = json.loads(component(objects, 'ConfigMap', 'xgt')
                                        ['data']['xgtd.conf'])
                    self.assertEqual(config['system.usemtls'], 'true')

    def test_legacy_secret_keys_and_same_secret_mtls_are_preserved(self):
        for profile in self.profiles():
            values = self.values(profile)
            values['xgt']['ssl'] = {'enabled': True, 'existingSecret': 'legacy', 'mtls': True}
            values['frontend'] = {'tls': {'existingSecret': 'frontend-legacy', 'mtls': True}}
            objects = render(values)
            volume, _ = self.volume(objects, 'xgt', 'xgt-tls')
            self.assertEqual([i['key'] for i in volume['secret']['items']],
                             ['server.cert.pem', 'server.key.pem', 'ca-chain.cert.pem'])
            _, pod = self.volume(objects, 'frontend', 'tls-certs')
            self.assertEqual([m['subPath'] for m in pod['containers'][0]['volumeMounts']
                              if m['name'] == 'tls-certs'],
                             ['public.pem', 'private.pem', 'chain.pem'])

    def test_custom_same_secret_client_ca_and_yaml_scalar_keys(self):
        values = self.values({})
        values['xgt']['ssl'] = {'enabled': True, 'existingSecret': 'custom', 'mtls': True,
            'secretKeys': {'cert': 'true', 'key': '123', 'caCert': 'null'}}
        values['frontend'] = {'tls': {'existingSecret': 'frontend-custom', 'mtls': True,
            'secretKeys': {'cert': 'true', 'key': '123', 'caCert': 'null'}}}
        objects = render(values)
        volume, _ = self.volume(objects, 'xgt', 'xgt-tls')
        self.assertEqual([i['key'] for i in volume['secret']['items']], ['true', '123', 'null'])
        _, pod = self.volume(objects, 'frontend', 'tls-certs')
        self.assertEqual([m['subPath'] for m in pod['containers'][0]['volumeMounts']
                          if m['name'] == 'tls-certs'], ['true', '123', 'null'])

    def test_inline_certificates_and_mounts_use_selected_secret_keys(self):
        values = self.values({})
        values['xgt']['ssl'] = {'enabled': True, 'mtls': True, 'cert': 'cert', 'key': 'key',
            'caCert': 'ca', 'secretKeys': {'cert': 'tls.crt', 'key': 'tls.key'}}
        values['frontend'] = {'tls': {'publicCert': 'cert', 'privateKey': 'key',
            'secretKeys': {'cert': 'tls.crt', 'key': 'tls.key'}}}
        objects = render(values)
        volume, _ = self.volume(objects, 'xgt', 'xgt-tls')
        self.assertEqual([i['key'] for i in volume['secret']['items']],
                         ['tls.crt', 'tls.key', 'ca-chain.cert.pem'])
        _, pod = self.volume(objects, 'frontend', 'tls-certs')
        self.assertEqual([m['subPath'] for m in pod['containers'][0]['volumeMounts']
                          if m['name'] == 'tls-certs'], ['tls.crt', 'tls.key'])

        generated = {o['metadata']['labels']['app']: o['stringData']
                     for o in objects if o['kind'] == 'Secret'
                     and o['metadata']['labels'].get('app') in ['xgt', 'frontend']}
        self.assertEqual(generated['xgt'],
                         {'tls.crt': 'cert', 'tls.key': 'key', 'ca-chain.cert.pem': 'ca'})
        self.assertEqual(generated['frontend'], {'tls.crt': 'cert', 'tls.key': 'key'})

    def test_rejects_invalid_key_names_and_conflicting_ca_sources(self):
        for component_name, field in [('xgt', 'ssl'), ('frontend', 'tls')]:
            for key in ['', 'nested/tls.crt', 'bad key']:
                values = self.values({})
                values.setdefault(component_name, {})[field] = {
                    'existingSecret': 'tls', 'secretKeys': {'cert': key}}
                self.assertIn('secretKeys/cert', render(values, fails=True))
        values = self.values({})
        values['xgt']['ssl'] = {'enabled': True, 'cert': 'cert', 'key': 'key',
            'mtls': True, 'caCert': 'inline', 'caCertExistingSecret': 'other'}
        self.assertIn('one source for the client CA', render(values, fails=True))
        values['xgt'] = {'files': {'existingClaim': 'files'},
                        'ssl': {'caCertExistingSecret': 'other'}}
        self.assertIn('xgt.files.existingClaim', render(values, fails=True))

    def test_generated_secrets_preserve_scalar_like_keys_and_frontend_client_ca(self):
        values = self.values({})
        keys = {'cert': 'true', 'key': '123', 'caCert': 'null'}
        values['xgt']['ssl'] = {'enabled': True, 'mtls': True,
            'cert': 'server', 'key': 'private', 'caCert': 'clients', 'secretKeys': keys}
        values['frontend'] = {'tls': {'mtls': True,
            'publicCert': 'server', 'privateKey': 'private', 'certChain': 'clients',
            'secretKeys': keys}}
        objects = render(values)
        generated = [o for o in objects if o['kind'] == 'Secret'
                     and o['metadata']['labels'].get('app') in ['xgt', 'frontend']]
        self.assertEqual(len(generated), 2)
        for secret in generated:
            self.assertEqual(secret['stringData'],
                             {'true': 'server', '123': 'private', 'null': 'clients'})
        _, pod = self.volume(objects, 'frontend', 'tls-certs')
        self.assertEqual([m['subPath'] for m in pod['containers'][0]['volumeMounts']
                          if m['name'] == 'tls-certs'], ['true', '123', 'null'])

    def test_existing_configmap_is_not_replaced_and_disabled_components_ignore_tls(self):
        values = self.values({})
        values['xgt']['config'] = {'existingConfigMap': 'existing'}
        values['xgt']['auth'] = {'pam': {'enabled': True}}
        values['xgt']['ssl'] = {'enabled': True, 'existingSecret': 'serving',
            'secretKeys': {'cert': 'tls.crt', 'key': 'tls.key'}}
        values['missionControl'] = {'enabled': False}
        values['mongodb'] = {'enabled': False}
        objects = render(values)
        self.assertFalse(any(o['kind'] == 'ConfigMap' for o in objects))
        volume, pod = self.volume(objects, 'xgt', 'xgt-tls')
        self.assertEqual(next(v for v in pod['volumes'] if v['name'] == 'xgt-config')
                         ['configMap']['name'], 'existing')
        self.assertEqual(volume['secret']['items'][0]['key'], 'tls.crt')

    def test_shipped_service_ca_example(self):
        values = yaml.safe_load((CHART / 'examples/xgt_openshift_service_tls.yaml').read_text())
        objects = render(values)
        volume, _ = self.volume(objects, 'xgt', 'xgt-tls')
        self.assertEqual(volume['secret']['secretName'], 'xgt-serving-tls')
        self.assertEqual(volume['secret']['items'][0]['key'], 'tls.crt')
        self.assertEqual(component(objects, 'Service', 'xgt')['metadata']['annotations'][
            'service.beta.openshift.io/serving-cert-secret-name'], 'xgt-serving-tls')


if __name__ == '__main__':
    unittest.main()
