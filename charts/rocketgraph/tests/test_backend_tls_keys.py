"""Backend TLS key mapping preserves application paths and existing defaults."""
import unittest

from test_render import component, render


class BackendTlsKeysTests(unittest.TestCase):
    def profiles(self):
        return [{}, {'openshift': {'enabled': True, 'scc': 'restricted-v2'},
                     'fips': {'enabled': True}}]

    def values(self, profile, tls):
        return dict(profile, xgt={'license': {'existingSecret': 'license'}},
                    backend={'tls': tls})

    def mounts(self, objects):
        pod = component(objects, 'Deployment', 'backend')['spec']['template']['spec']
        return {m['mountPath']: m for m in pod['containers'][0]['volumeMounts']}, pod

    def test_custom_secret_keys_keep_application_paths_and_mtls_environment(self):
        for profile in self.profiles():
            for mtls in (False, True):
                with self.subTest(profile=profile, mtls=mtls):
                    values = self.values(profile, {'existingSecret': 'custom-client',
                        'mtls': mtls, 'secretKeys': {
                            'cert': 'tls.crt', 'key': 'tls.key', 'caCert': 'ca.crt'}})
                    objects = render(values)
                    mounts, pod = self.mounts(objects)
                    self.assertEqual(mounts['/etc/ssl/certs/xgt-server.pem']['subPath'], 'ca.crt')
                    paths = {'/etc/ssl/certs/proxy-client-cert.pem': 'tls.crt',
                             '/etc/ssl/private/proxy-client-key.pem': 'tls.key'}
                    for path, key in paths.items():
                        if mtls:
                            self.assertEqual(mounts[path]['subPath'], key)
                            self.assertTrue(mounts[path]['readOnly'])
                        else:
                            self.assertNotIn(path, mounts)
                    tls = next(v for v in pod['volumes'] if v['name'] == 'tls-certs')
                    self.assertEqual(tls['secret']['secretName'], 'custom-client')
                    self.assertFalse(any(o['kind'] == 'Secret' and
                        o['metadata']['labels'].get('app') == 'backend' for o in objects))
                    env = {e['name']: e.get('value') for e in pod['containers'][0]['env']}
                    if mtls:
                        self.assertEqual(env['MC_SSL_PROXY_PUBLIC_CERT'],
                                         '/etc/ssl/certs/proxy-client-cert.pem')
                        self.assertEqual(env['MC_SSL_PROXY_PRIVATE_KEY'],
                                         '/etc/ssl/private/proxy-client-key.pem')
                    else:
                        self.assertNotIn('MC_SSL_PROXY_PUBLIC_CERT', env)

    def test_configmap_ca_and_secret_client_credentials_are_independent(self):
        for profile in self.profiles():
            values = self.values(profile, {'existingSecret': 'client', 'mtls': True,
                'xgtServerCertConfigMap': 'service-ca',
                'xgtServerCertConfigMapKey': 'custom-service-ca.pem',
                'secretKeys': {'cert': 'tls.crt', 'key': 'tls.key', 'caCert': 'unused.pem'}})
            mounts, pod = self.mounts(render(values))
            self.assertEqual(mounts['/etc/ssl/certs/xgt-server.pem'], {
                'name': 'xgt-server-ca', 'mountPath': '/etc/ssl/certs/xgt-server.pem',
                'subPath': 'xgt-server.pem', 'readOnly': True})
            self.assertEqual(mounts['/etc/ssl/certs/proxy-client-cert.pem']['subPath'], 'tls.crt')
            ca = next(v for v in pod['volumes'] if v['name'] == 'xgt-server-ca')
            self.assertEqual(ca['configMap']['items'], [
                {'key': 'custom-service-ca.pem', 'path': 'xgt-server.pem'}])

    def test_generated_secret_and_mounts_use_matching_keys(self):
        for keys in ({'cert': 'tls.crt', 'key': 'tls.key', 'caCert': 'ca.crt'},
                     {'cert': 'true', 'key': '123', 'caCert': 'null'}):
            values = self.values({}, {'mtls': True, 'proxyClientCert': 'client',
                'proxyClientKey': 'private', 'xgtServerCert': 'server-ca', 'secretKeys': keys})
            objects = render(values)
            secret = component(objects, 'Secret', 'backend')
            self.assertEqual(secret['stringData'], {
                keys['cert']: 'client', keys['key']: 'private', keys['caCert']: 'server-ca'})
            mounts, _ = self.mounts(objects)
            self.assertEqual(mounts['/etc/ssl/certs/xgt-server.pem']['subPath'], keys['caCert'])
            self.assertEqual(mounts['/etc/ssl/certs/proxy-client-cert.pem']['subPath'], keys['cert'])
            self.assertEqual(mounts['/etc/ssl/private/proxy-client-key.pem']['subPath'], keys['key'])

    def test_legacy_defaults_and_partial_overrides(self):
        for overrides in ({}, {'cert': 'custom-client.pem'}):
            values = self.values({}, {'mtls': True, 'proxyClientCert': 'client',
                'proxyClientKey': 'private', 'xgtServerCert': 'ca', 'secretKeys': overrides})
            objects = render(values)
            cert = overrides.get('cert', 'proxy-client-cert.pem')
            secret = component(objects, 'Secret', 'backend')
            self.assertEqual(secret['stringData'], {
                cert: 'client', 'proxy-client-key.pem': 'private', 'xgt-server.pem': 'ca'})
            mounts, _ = self.mounts(objects)
            self.assertEqual(mounts['/etc/ssl/certs/proxy-client-cert.pem']['subPath'], cert)

    def test_invalid_secret_keys_are_rejected(self):
        for field in ('cert', 'key', 'caCert'):
            for key in ('', 'nested/file.pem', 'bad key', 'x' * 254):
                values = self.values({}, {'secretKeys': {field: key}})
                self.assertIn('secretKeys/' + field, render(values, fails=True))


if __name__ == '__main__':
    unittest.main()
