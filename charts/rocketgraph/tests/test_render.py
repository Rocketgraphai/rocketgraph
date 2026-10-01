"""Render checks: HELM_BIN=/path/to/helm python -m unittest discover -s tests.

Requires PyYAML; no cluster access or Helm plugins are needed.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

CHART = Path(__file__).resolve().parents[1]
HELM = os.environ.get('HELM_BIN', 'helm')


def render(values, release='test', fails=False, chart=CHART):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'values.yaml'
        path.write_text(yaml.safe_dump(values))
        result = subprocess.run(
            [HELM, 'template', release, str(chart), '-n', 'test', '-f', str(path)],
            capture_output=True, text=True)
    if fails:
        if result.returncode == 0:
            raise AssertionError('Invalid values unexpectedly rendered')
        return result.stderr
    if result.returncode:
        raise AssertionError(result.stderr)
    return [obj for obj in yaml.safe_load_all(result.stdout) if obj]


def component(objects, kind, app):
    return next(obj for obj in objects if obj['kind'] == kind
                and obj['metadata']['labels'].get('app') == app)


class ReleaseTests(unittest.TestCase):
    def test_default_keeps_full_stack_and_generated_hostname(self):
        objects = render({})
        apps = {obj['metadata']['labels']['app'] for obj in objects
                if obj['kind'] == 'Deployment'}
        self.assertEqual(apps, {'frontend', 'backend', 'mongodb', 'xgt'})
        self.assertNotIn('hostname', component(objects, 'Deployment', 'xgt')
                         ['spec']['template']['spec'])

    def test_three_releases_have_isolated_storage_and_fixed_hostnames(self):
        seen = set()
        for environment in ['dev', 'test', 'prod']:
            release = 'xgt-' + environment
            objects = render({
                'missionControl': {'enabled': False},
                'mongodb': {'enabled': False},
                'openshift': {'enabled': True},
                'fips': {'enabled': True},
                'xgt': {'hostname': release + '-0',
                        'license': {'existingSecret': release + '-license'},
                        'ssl': {'enabled': True, 'existingSecret': release + '-tls'},
                        'extraConfig': {'security.oidc': {'client_id': release}}},
                'backend': {'oidc': {'caCertExistingSecret': 'oidc-ca'}}}, release)
            deployments = [obj for obj in objects if obj['kind'] == 'Deployment']
            self.assertEqual(len(deployments), 1)
            pod = deployments[0]['spec']['template']['spec']
            self.assertEqual(pod['hostname'], release + '-0')
            self.assertEqual(pod['containers'][0]['image'],
                             'docker.io/rocketgraph/xgt:2.7.1-fips')
            secrets = {v['secret']['secretName'] for v in pod['volumes'] if 'secret' in v}
            self.assertEqual(secrets, {release + '-license', release + '-tls', 'oidc-ca'})
            claims = {v['persistentVolumeClaim']['claimName'] for v in pod['volumes']
                      if 'persistentVolumeClaim' in v}
            self.assertEqual(claims, {release + '-xgt-data', release + '-xgt-log'})
            self.assertTrue(claims.isdisjoint(seen))
            seen.update(claims)
            created = {o['metadata']['name'] for o in objects
                       if o['kind'] == 'PersistentVolumeClaim'}
            self.assertEqual(claims, created)
            config = component(objects, 'ConfigMap', 'xgt')
            self.assertEqual(json.loads(config['data']['xgtd.conf'])
                             ['security.oidc']['client_id'], release)

    def test_disabled_mission_control_omits_all_its_resources(self):
        objects = render({
            'missionControl': {'enabled': False}, 'mongodb': {'enabled': False},
            'ingress': {'enabled': True},
            'frontend': {'tls': {'publicCert': 'unused'},
                         'podDisruptionBudget': {'enabled': True}},
            'backend': {'replicas': 2, 'siteConfig': {'yml': 'unused'},
                        'tls': {'xgtServerCert': 'unused'},
                        'odbc': {'enabled': True}, 'iaccess': {'enabled': True},
                        'oidc': {'clientSecret': 'unused'},
                        'podDisruptionBudget': {'enabled': True}}})
        self.assertFalse(any(o['metadata']['labels'].get('app') in ['frontend', 'backend']
                             for o in objects))
        self.assertFalse(any(o['kind'] == 'Ingress' for o in objects))
        policies = [o['metadata']['name'] for o in objects if o['kind'] == 'NetworkPolicy']
        self.assertEqual(policies, ['test-xgt'])

    def test_xgt_only_keeps_inline_oidc_ca_without_client_secret(self):
        objects = render({'missionControl': {'enabled': False},
                          'mongodb': {'enabled': False},
                          'backend': {'oidc': {'caCert': 'test-ca',
                                               'clientSecret': 'unused'}}})
        secrets = [o for o in objects if o['kind'] == 'Secret']
        self.assertEqual([s['stringData'] for s in secrets], [{'oidc-ca.pem': 'test-ca'}])
        pod = component(objects, 'Deployment', 'xgt')['spec']['template']['spec']
        ca = next(v for v in pod['volumes'] if v['name'] == 'oidc-ca-cert')
        self.assertEqual(ca['secret']['secretName'], secrets[0]['metadata']['name'])

    def test_shared_mission_control_requires_external_endpoints(self):
        self.assertIn('MC_DEFAULT_XGT_HOST', render({'xgt': {'enabled': False}}, fails=True))
        self.assertIn('externalUri', render({'mongodb': {'enabled': False}}, fails=True))
        objects = render({'xgt': {'enabled': False},
                          'backend': {'env': {'MC_DEFAULT_XGT_HOST': 'xgt-test-xgt'},
                                      'oidc': {'xgtAllowedHosts': 'xgt-dev-xgt:4367,xgt-test-xgt:4367,xgt-prod-xgt:4367'}}})
        self.assertEqual({o['metadata']['labels']['app'] for o in objects
                          if o['kind'] == 'Deployment'}, {'frontend', 'backend', 'mongodb'})
        env = component(objects, 'Deployment', 'backend')['spec']['template']['spec']['containers'][0]['env']
        hosts = next(e['value'] for e in env if e['name'] == 'MC_XGT_ALLOWED_HOSTS')
        self.assertIn('xgt-prod-xgt:4367', hosts)

    def test_invalid_hostnames_and_multiple_replicas_fail(self):
        for hostname in ['BAD', 'host.example', '-host', 'host-', 'x' * 64]:
            with self.subTest(hostname=hostname):
                self.assertIn('hostname', render({'xgt': {'hostname': hostname}}, fails=True))
        self.assertIn('replicas > 1', render({'xgt': {'replicas': 2, 'hostname': 'fixed'}}, fails=True))

    def test_explicit_claims_remain_supported(self):
        objects = render({'missionControl': {'enabled': False},
                          'mongodb': {'enabled': False},
                          'xgt': {'hostname': 'licensed', 'persistence': {
                              'data': {'existingClaim': 'existing-data'},
                              'log': {'existingClaim': 'existing-log'}}}})
        self.assertFalse(any(o['kind'] == 'PersistentVolumeClaim' for o in objects))
        pod = component(objects, 'Deployment', 'xgt')['spec']['template']['spec']
        self.assertEqual({v['persistentVolumeClaim']['claimName'] for v in pod['volumes']
                          if 'persistentVolumeClaim' in v}, {'existing-data', 'existing-log'})

    def test_documented_openshift_values_share_one_mission_control(self):
        path = CHART.parents[1] / 'doc/openshift_test_server/values.yaml'
        for release, hostname in [('rocketgraph', 'xgt-test-0'),
                                  ('xgt-dev', 'xgt-dev-0'), ('xgt-prod', 'xgt-prod-0')]:
            with self.subTest(release=release):
                values = yaml.safe_load(path.read_text())
                if release != 'rocketgraph':
                    values['missionControl'] = {'enabled': False}
                    values['mongodb']['enabled'] = False
                    values['xgt']['hostname'] = hostname
                objects = render(values, release)
                deployments = [o for o in objects if o['kind'] == 'Deployment']
                self.assertEqual(len(deployments), 4 if release == 'rocketgraph' else 1)
                pod = component(objects, 'Deployment', 'xgt')['spec']['template']['spec']
                self.assertEqual(pod['hostname'], hostname)
                self.assertEqual(pod['containers'][0]['image'],
                                 'docker.io/rocketgraph/xgt:2.7.1-fips')
                config = component(objects, 'ConfigMap', 'xgt')
                self.assertEqual(json.loads(config['data']['xgtd.conf'])
                                 ['security.oidc']['validation_mode'], 'openshift_userapi')
                if release == 'rocketgraph':
                    env = component(objects, 'Deployment', 'backend')['spec']['template']['spec']['containers'][0]['env']
                    hosts = next(e['value'] for e in env if e['name'] == 'MC_XGT_ALLOWED_HOSTS')
                    self.assertEqual(set(hosts.split(',')), {
                        'rocketgraph-xgt:4367', 'xgt-dev-xgt:4367', 'xgt-prod-xgt:4367'})
                    self.assertFalse(next(e['value'] for e in env if e['name'] == 'XGT_SERVER_CN'))


class CustomizationTests(unittest.TestCase):
    def restricted(self, **xgt):
        return {'missionControl': {'enabled': False}, 'mongodb': {'enabled': False},
                'openshift': {'enabled': True, 'scc': 'restricted-v2'},
                'xgt': xgt}

    def test_restricted_xgt_has_no_elevated_binding_and_uses_direct_startup(self):
        values = yaml.safe_load((CHART / 'examples/xgt_openshift_restricted.yaml').read_text())
        objects = render(values)
        self.assertFalse(any(o['kind'] == 'ClusterRoleBinding' for o in objects))
        self.assertEqual(sum(o['kind'] == 'ServiceAccount' for o in objects), 1)
        pod = component(objects, 'Deployment', 'xgt')['spec']['template']['spec']
        container = pod['containers'][0]
        self.assertEqual(pod['hostname'], 'xgt-test-0')
        self.assertEqual(pod['securityContext']['seccompProfile']['type'], 'RuntimeDefault')
        self.assertTrue(container['securityContext']['runAsNonRoot'])
        self.assertFalse(container['securityContext']['allowPrivilegeEscalation'])
        self.assertEqual(container['securityContext']['capabilities']['drop'], ['ALL'])
        self.assertNotIn('runAsUser', container['securityContext'])
        self.assertNotIn('fsGroup', pod['securityContext'])
        self.assertEqual(container['command'], ['/opt/xgtd/bin/xgtd'])
        self.assertIn('-Dsystem.health_port=4366', container['args'])
        config = json.loads(component(objects, 'ConfigMap', 'xgt')['data']['xgtd.conf'])
        self.assertEqual(config['license.location'], '/license/xgtd.lic')
        self.assertEqual(config['security.oidc']['ca_cert'], '/etc/ssl/certs/oidc-ca.pem')
        tls = next(v for v in pod['volumes'] if v['name'] == 'xgt-tls')
        key = next(item for item in tls['secret']['items'] if item['key'] == 'server.key.pem')
        self.assertEqual(key['mode'], 0o440)

    def test_existing_files_use_only_supplied_claim_and_no_generated_files(self):
        values = yaml.safe_load((CHART / 'examples/xgt_existing_files.yaml').read_text())
        objects = render(values)
        self.assertFalse(any(o['kind'] in ['ConfigMap', 'Secret', 'PersistentVolumeClaim',
                                           'ClusterRoleBinding'] for o in objects))
        pod = component(objects, 'Deployment', 'xgt')['spec']['template']['spec']
        self.assertEqual(pod['volumes'], [{'name': 'xgt-files', 'persistentVolumeClaim':
                                          {'claimName': 'xgt-files'}}])
        mounts = pod['containers'][0]['volumeMounts']
        self.assertEqual({m['mountPath']: m['subPath'] for m in mounts},
                         {'/'+d: 'xgt-prod/'+d for d in ['conf', 'license', 'data', 'log']})
        self.assertTrue(all(m['readOnly'] for m in mounts if m['mountPath'] in ['/conf','/license']))
        annotations = component(objects, 'Deployment', 'xgt')['spec']['template']['metadata'].get('annotations') or {}
        self.assertNotIn('checksum/config', annotations)
        values['xgt']['files']['subPath'] = ''
        pod = component(render(values), 'Deployment', 'xgt')['spec']['template']['spec']
        self.assertEqual({m['subPath'] for m in pod['containers'][0]['volumeMounts']},
                         {'conf', 'license', 'data', 'log'})

    def test_existing_files_allow_separate_data_and_log_claims(self):
        for separate in [('data',), ('log',), ('data', 'log')]:
            for prefix in ['', 'xgt-prod']:
                with self.subTest(separate=separate, prefix=prefix):
                    values = self.restricted(
                        files={'existingClaim': 'files', 'subPath': prefix},
                        persistence={d: {'existingClaim': 'separate-' + d} for d in separate})
                    objects = render(values)
                    self.assertFalse(any(o['kind'] in ['ConfigMap', 'Secret', 'PersistentVolumeClaim']
                                         for o in objects))
                    pod = component(objects, 'Deployment', 'xgt')['spec']['template']['spec']
                    volumes = {v['name']: v['persistentVolumeClaim']['claimName'] for v in pod['volumes']}
                    self.assertEqual(volumes, {'xgt-files': 'files',
                                               **{'xgt-' + d: 'separate-' + d for d in separate}})
                    mounts = pod['containers'][0]['volumeMounts']
                    self.assertEqual(len(mounts), 4)
                    for mount in mounts:
                        directory = mount['mountPath'].lstrip('/')
                        if directory in separate:
                            self.assertEqual(mount['name'], 'xgt-' + directory)
                            self.assertNotIn('subPath', mount)
                        else:
                            self.assertEqual(mount['name'], 'xgt-files')
                            self.assertEqual(mount['subPath'], '/'.join(filter(None, [prefix, directory])))
                        self.assertEqual(mount.get('readOnly', False), directory in ['conf', 'license'])

    def test_separate_data_example_keeps_logs_on_files_claim(self):
        values = yaml.safe_load((CHART / 'examples/xgt_files_separate_data.yaml').read_text())
        pod = component(render(values), 'Deployment', 'xgt')['spec']['template']['spec']
        mounts = {m['mountPath']: m for m in pod['containers'][0]['volumeMounts']}
        self.assertEqual(mounts['/data'], {'name': 'xgt-data', 'mountPath': '/data'})
        self.assertEqual(mounts['/log']['subPath'], 'xgt-prod/log')
        self.assertEqual({v['persistentVolumeClaim']['claimName'] for v in pod['volumes']},
                         {'xgt-files', 'xgt-data'})

    def test_existing_configmap_and_external_license(self):
        objects = render(self.restricted(config={'existingConfigMap': 'customer-config'}))
        self.assertFalse(any(o['kind'] == 'ConfigMap' for o in objects))
        pod = component(objects, 'Deployment', 'xgt')['spec']['template']['spec']
        self.assertEqual(next(v for v in pod['volumes'] if v['name']=='xgt-config')
                         ['configMap']['name'], 'customer-config')
        objects = render(self.restricted(extraConfig={'license.location': '6200@licenses.example.com'}))
        cfg=json.loads(component(objects,'ConfigMap','xgt')['data']['xgtd.conf'])
        self.assertEqual(cfg['license.location'], '6200@licenses.example.com')

    def test_native_startup_env_and_mount_overrides(self):
        values = self.restricted(license={'existingSecret':'license'},
            command=['/custom/start'], args=['--site'], env=[{'name':'SITE','value':'customer'}],
            extraVolumes=[{'name':'inputs','persistentVolumeClaim':{'claimName':'customer-input'}}],
            extraVolumeMounts=[{'name':'inputs','mountPath':'/inputs','readOnly':True}])
        pod=component(render(values),'Deployment','xgt')['spec']['template']['spec']
        container=pod['containers'][0]
        self.assertEqual(container['command'],['/custom/start'])
        self.assertEqual(container['args'],['--site'])
        self.assertEqual(container['env'],[{'name':'SITE','value':'customer'}])
        self.assertEqual(container['volumeMounts'][-1]['mountPath'],'/inputs')
        self.assertEqual(pod['volumes'][-1]['persistentVolumeClaim']['claimName'],'customer-input')

    def test_restricted_rejects_unsupported_or_conflicting_settings(self):
        cases=[(self.restricted(),'readable license'),
               (self.restricted(license={'existingSecret':'license'},ldap={'enabled':True}),'SSSD'),
               (self.restricted(license={'existingSecret':'license'},podSecurityContext={'fsGroup':1001}),'fsGroup'),
               (self.restricted(license={'existingSecret':'license'},containerSecurityContext={'runAsUser':0}),'runAsUser'),
               (self.restricted(license={'existingSecret':'license'},containerSecurityContext={'privileged':True}),'privileged'),
               (self.restricted(license={'existingSecret':'license'},containerSecurityContext={'capabilities':{'add':['SYS_ADMIN']}}),'capabilities')]
        values = self.restricted(licenseManager={'enabled': True})
        cases.append((values, 'License Manager'))
        for values,message in cases:
            with self.subTest(message=message):self.assertIn(message,render(values,fails=True))

    def test_file_modes_reject_silently_ignored_settings_and_bad_mounts(self):
        for override in [{'extraConfig':{'system.max_memory':'1'}},
                         {'license':{'existingSecret':'unused'}},
                         {'ssl':{'existingSecret':'unused'}},
                         {'config':{'existingConfigMap':'unused'}}]:
            values=self.restricted(files={'existingClaim':'files'},**override)
            self.assertIn('xgt.files.existingClaim',render(values,fails=True))
        for path in ['../prod','/prod','prod/../dev','prod/']:
            self.assertIn('subPath',render(self.restricted(files={'existingClaim':'files','subPath':path}),fails=True))
        self.assertIn('extraVolumes',render({'xgt':{'extraVolumes':[{'name':'xgt-data','emptyDir':{}}]}},fails=True))
        self.assertIn('extraVolumeMounts',render({'xgt':{'extraVolumeMounts':[{'name':'xgt-data','mountPath':'/data'}]}},fails=True))

    def test_disabled_xgt_ignores_unused_file_and_mount_conflicts(self):
        cases = [
            ({'files': {'existingClaim': 'files'}, 'extraConfig': {'system.max_memory': '1'}}, 'xgt.files'),
            ({'files': {'existingClaim': 'files'}, 'license': {'existingSecret': 'license'}}, 'xgt.files'),
            ({'files': {'existingClaim': 'files'}, 'ssl': {'existingSecret': 'tls'}}, 'xgt.files'),
            ({'config': {'existingConfigMap': 'config'}, 'extraConfig': {'system.max_memory': '1'}}, 'existingConfigMap'),
            ({'files': {'subPath': 'prod'}}, 'subPath'),
            ({'extraVolumes': [{'name': 'xgt-data', 'emptyDir': {}}]}, 'extraVolumes'),
            ({'extraVolumeMounts': [{'name': 'xgt-data', 'mountPath': '/data'}]}, 'extraVolumeMounts'),
        ]
        base = {'backend': {'env': {'MC_DEFAULT_XGT_HOST': 'external-xgt'}}}
        expected = render(dict(base, xgt={'enabled': False}))
        for override, message in cases:
            with self.subTest(override=override):
                self.assertIn(message, render(dict(base, xgt=dict(override, enabled=True)), fails=True))
                self.assertEqual(render(dict(base, xgt=dict(override, enabled=False))), expected)

    def test_explicit_oidc_ca_is_preserved_and_companion_has_ca(self):
        values={'xgt':{'extraConfig':{'security.oidc':{'issuer':'https://issuer','ca_cert':'/custom/ca.pem'}}},
                'backend':{'oidc':{'caCertExistingSecret':'cluster-ca'}}}
        cfg=json.loads(component(render(values),'ConfigMap','xgt')['data']['xgtd.conf'])
        self.assertEqual(cfg['security.oidc']['ca_cert'],'/custom/ca.pem')
        companion=yaml.safe_load((CHART.parents[1]/'doc/openshift_fips_values.example.yaml').read_text())
        self.assertEqual(companion['xgt']['extraConfig']['security.oidc']['ca_cert'],'/etc/ssl/certs/oidc-ca.pem')

    def test_mongodb_warning_survives_disabled_mission_control(self):
        # Render NOTES as ConfigMap data to keep this check offline on Helm 3 and 4.
        with tempfile.TemporaryDirectory() as directory:
            chart = Path(directory) / 'chart'
            shutil.copytree(CHART, chart)
            (chart / 'templates/notes-check.yaml').write_text(
                'apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: notes-check\n'
                'data:\n  notes: {{ include (print $.Template.BasePath "/NOTES.txt") . | quote }}\n')
            for enabled in [False, True]:
                objects = render({'missionControl': {'enabled': enabled}}, chart=chart)
                notes = next(o['data']['notes'] for o in objects
                             if o['metadata']['name'] == 'notes-check')
                self.assertIn('MongoDB auth is DISABLED', notes)
                self.assertIn('\n\nxGT Service:', notes)
                if enabled:
                    self.assertIn('\n\nTo access the frontend:', notes)
                else:
                    self.assertIn('MongoDB is still enabled', notes)
                    self.assertNotIn('To access the frontend:', notes)


class RestrictedStackTests(unittest.TestCase):
    def values(self):
        return {'openshift': {'enabled': True, 'scc': 'restricted-v2'},
                'fips': {'enabled': True}, 'xgt': {'license': {'existingSecret': 'license'}}}

    def test_restricted_mission_control_requires_fips(self):
        values = self.values()
        del values['fips']  # Default image selection must fail early too.
        self.assertIn('Mission Control requires fips.enabled=true', render(values, fails=True))
        values['fips'] = {'enabled': False}
        self.assertIn('Mission Control requires fips.enabled=true', render(values, fails=True))
        values['missionControl'] = {'enabled': False}
        self.assertTrue(render(values))
        values['missionControl']['enabled'] = True
        values['openshift']['scc'] = 'anyuid'
        self.assertTrue(render(values))
        values['openshift'] = {'enabled': False, 'scc': 'restricted-v2'}
        self.assertTrue(render(values))

    def test_full_stack_has_assigned_id_contexts_without_scc_grant(self):
        objects = render(self.values())
        self.assertFalse(any(o['kind'] == 'ClusterRoleBinding' for o in objects))
        deployments = [o for o in objects if o['kind'] == 'Deployment']
        self.assertEqual(len(deployments), 4)
        for deployment in deployments:
            pod = deployment['spec']['template']['spec']
            self.assertEqual(pod['serviceAccountName'], 'test-rocketgraph')
            self.assertEqual(pod['securityContext']['seccompProfile']['type'], 'RuntimeDefault')
            for context in [pod['securityContext'], pod['containers'][0]['securityContext']]:
                for field in ['runAsUser', 'runAsGroup', 'fsGroup', 'supplementalGroups']:
                    self.assertNotIn(field, context)
            security = pod['containers'][0]['securityContext']
            self.assertTrue(security['runAsNonRoot'])
            self.assertFalse(security['allowPrivilegeEscalation'])
            self.assertEqual(security['capabilities']['drop'], ['ALL'])
            self.assertEqual(security['seccompProfile']['type'], 'RuntimeDefault')

    def test_frontend_ports_mounts_and_tls_routing(self):
        for tls in [{}, {'existingSecret': 'tls'},
                    {'existingSecret': 'tls', 'mtls': True},
                    {'publicCert': 'cert', 'privateKey': 'key'}]:
            with self.subTest(tls=tls):
                values = self.values()
                values['frontend'] = {'tls': tls, 'service': {'httpPort': 9080, 'httpsPort': 9443}}
                objects = render(values)
                pod = component(objects, 'Deployment', 'frontend')['spec']['template']['spec']
                container = pod['containers'][0]
                self.assertEqual([p['containerPort'] for p in container['ports']], [8080, 8443])
                self.assertEqual(container['readinessProbe']['httpGet']['port'], 'http')
                self.assertEqual(container['command'], ['/bin/sh', '-ec'])
                script = container['args'][0]
                self.assertIn('/usr/local/bin/docker-entrypoint-ssl.sh', script)
                self.assertIn('X-Forwarded-Port '+('9443' if tls else '9080')+';', script)
                self.assertEqual(next(e['value'] for e in container['env'] if e['name']=='MC_SSL_PORT'), '9443')
                mounts = {m['mountPath']: m for m in container['volumeMounts']}
                for path in ['/etc/nginx/conf.d', '/run', '/var/log/nginx', '/var/lib/nginx/tmp']:
                    self.assertIn(path, mounts)
                self.assertEqual(sum('emptyDir' in v for v in pod['volumes']), 4)
                self.assertEqual('/etc/ssl/private/td.pem' in mounts, bool(tls))
                self.assertEqual('/etc/ssl/certs/ca-chain.pem' in mounts, bool(tls.get('mtls')))
                service = component(objects, 'Service', 'frontend')
                self.assertEqual([(p['port'], p['targetPort']) for p in service['spec']['ports']],
                                 [(9080, 8080), (9443, 8443)])
                policy = next(o for o in objects if o['kind']=='NetworkPolicy' and o['metadata']['name']=='test-frontend')
                self.assertEqual([p['port'] for p in policy['spec']['ingress'][0]['ports']], [8080, 8443])

    def test_frontend_startup_rewrites_inline_and_included_headers(self):
        # Execute the rendered shell transformations, not a second implementation
        # of the rewrite. Image setup/nginx launch are outside this unit test.
        for layout in ['inline', 'include']:
            for tls in [{}, {'existingSecret': 'tls'}, {'existingSecret': 'tls', 'mtls': True}]:
                with self.subTest(layout=layout, tls=tls), tempfile.TemporaryDirectory() as directory:
                    values = self.values()
                    values['frontend'] = {'tls': tls, 'service': {'httpPort': 9080, 'httpsPort': 9443}}
                    container = component(render(values), 'Deployment', 'frontend')['spec']['template']['spec']['containers'][0]
                    nginx = Path(directory) / 'nginx'
                    conf_dir = nginx / 'conf.d'
                    conf_dir.mkdir(parents=True)
                    header = 'proxy_set_header X-Forwarded-Port $server_port;\nproxy_set_header Host $host;\n'
                    source = nginx / 'api_proxy_headers.inc'
                    if layout == 'include':
                        source.write_text(header)
                        source.chmod(0o444)
                        proxy = 'include /etc/nginx/api_proxy_headers.inc;\n'
                    else:
                        proxy = header
                    client_cert = '$ssl_client_escaped_cert' if tls.get('mtls') else '""'
                    config = ('server {\nlisten 80;\nlisten [::]:80;\n'
                              + ('listen 443 ssl;\nlisten [::]:443 ssl;\n' if tls else '')
                              + 'location /api {\n' + proxy
                              + f'proxy_set_header X-Client-Cert {client_cert};\n'
                              + '}\nlocation /docs {\n' + proxy + '}\n}\n')
                    active = conf_dir / 'nginx.conf'
                    active.write_text(config.replace('/etc/nginx', str(nginx)))
                    script = container['args'][0].replace('/etc/nginx', str(nginx))
                    script = script.replace('/usr/local/bin/docker-entrypoint-ssl.sh', ':')
                    script = script.replace("exec nginx -g 'daemon off;'", ':')
                    result = subprocess.run(['/bin/sh', '-ec', script], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    rewritten = active.read_text()
                    self.assertIn('listen 8080;', rewritten)
                    self.assertIn('listen [::]:8080;', rewritten)
                    if tls:
                        self.assertIn('listen 8443 ssl;', rewritten)
                        self.assertIn('listen [::]:8443 ssl;', rewritten)
                    self.assertIn(f'proxy_set_header X-Client-Cert {client_cert};', rewritten)
                    if layout == 'include':
                        adjusted = conf_dir / 'api_proxy_headers.inc'
                        self.assertEqual(rewritten.count(f'include {adjusted};'), 2)
                        self.assertEqual(source.read_text(), header)
                        self.assertEqual(source.stat().st_mode & 0o777, 0o444)
                        rewritten = adjusted.read_text()
                    self.assertIn('X-Forwarded-Port '+('9443' if tls else '9080')+';', rewritten)
                    self.assertNotIn('X-Forwarded-Port $server_port;', rewritten)
                    self.assertIn('proxy_set_header Host $host;', rewritten)
                    self.assertEqual(list(conf_dir.glob('*.conf')), [active])

    def test_mongodb_encryption_does_not_inject_fixed_ids(self):
        values = self.values()
        values['mongodb'] = {'encryption': {'enabled': True, 'existingSecret': 'encryption'}}
        pod = component(render(values), 'Deployment', 'mongodb')['spec']['template']['spec']
        self.assertNotIn('fsGroup', pod['securityContext'])
        init = pod['initContainers'][0]
        self.assertNotIn('runAsUser', init['securityContext'])
        self.assertTrue(init['securityContext']['runAsNonRoot'])
        self.assertIn('chmod 400', init['command'][-1])
        values['openshift']['scc'] = 'anyuid'
        pod = component(render(values), 'Deployment', 'mongodb')['spec']['template']['spec']
        self.assertEqual(pod['securityContext']['fsGroup'], 1001)
        self.assertEqual(pod['initContainers'][0]['securityContext']['runAsUser'], 1001)

    def test_rejects_fixed_ids_and_elevated_contexts_on_each_component(self):
        for name in ['frontend', 'backend', 'mongodb', 'xgt']:
            for context in [{'runAsUser': 0}, {'runAsGroup': 1001}, {'fsGroup': 1001},
                            {'supplementalGroups': [1001]}, {'privileged': True},
                            {'capabilities': {'add': ['NET_BIND_SERVICE']}}]:
                with self.subTest(component=name, context=context):
                    values = self.values()
                    values.setdefault(name, {})['containerSecurityContext'] = context
                    self.assertIn(name, render(values, fails=True))
        values = self.values()
        values['missionControl'] = {'enabled': False}
        values['frontend'] = {'containerSecurityContext': {'runAsUser': 0}}
        self.assertTrue(render(values))


if __name__ == '__main__':
    unittest.main()
