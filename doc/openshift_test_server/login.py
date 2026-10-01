#!/usr/bin/env python3
"""Browser or service-account login over the test server's localhost tunnel."""
import argparse
from pathlib import Path

import xgt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--port', type=int, default=14367)
    parser.add_argument('--server-name', default='rocketgraph-xgt',
                        help='XGT service DNS name to verify against its TLS certificate')
    parser.add_argument('--demo', choices=['create', 'read', 'cleanup'],
                        help='Create, read or remove the XgtDemo admin-only table')
    args = parser.parse_args()
    private = Path(__file__).resolve().parent / '.private'
    if args.token_file:
        auth = xgt.BearerTokenAuth(args.token_file.read_text().strip())
    else:
        auth = xgt.OidcAuth(
            flow='auth_code',
            client_secret=(private / 'oauth-client-secret').read_text().strip(),
            ca_cert_path=str(private / 'oidc-ca.pem'))
    conn = xgt.Connection(
        host='127.0.0.1', port=args.port, auth=auth,
        flags={'ssl': True,
               'ssl_server_cert': str(private / 'xgt-ca.pem'),
               'ssl_server_cn': args.server_name})
    print('Identity:', conn.userid)
    print('XGT administrator:', conn.is_admin)
    print('Labels:', conn.get_user_labels())
    result = conn.run_job('RETURN 1 AS ok').get_data()
    if result != [[1]]:
        raise RuntimeError(f'Unexpected query result: {result!r}')
    print('Query:', result)
    if args.demo == 'create':
        if not conn.is_admin:
            raise SystemExit('Log in as the XGT administrator to create demo data.')
        conn.create_namespace('XgtDemo')
        frame = conn.create_table_frame(
            'XgtDemo__AdminOnly', [['value', xgt.INT]],
            frame_labels={'read': ['xgtadmin']})
        frame.insert([[42]])
        print('Created XgtDemo__AdminOnly with read label xgtadmin.')
    elif args.demo == 'read':
        try:
            data = conn.get_frame('XgtDemo__AdminOnly').get_data()
        except xgt.XgtSecurityError:
            if conn.is_admin:
                raise
            print('PASS: non-admin identity was denied access to admin-only data.')
        else:
            if not conn.is_admin or data != [[42]]:
                raise RuntimeError('Unexpected access to demo data or contents.')
            print('PASS: administrator read admin-only data:', data)
    elif args.demo == 'cleanup':
        if not conn.is_admin:
            raise SystemExit('Log in as the XGT administrator to remove demo data.')
        conn.drop_namespace('XgtDemo', force_drop=True)
        print('Removed the XgtDemo namespace and its demo table.')


if __name__ == '__main__':
    main()
