"""Open a browser to log in to xGT with a normal Keycloak or LDAP account."""
import xgt

conn = xgt.Connection(
  host = "xgt.example.com",
  port = 4367,
  # For xGT TLS, add the connection flags described in the SSL guide.
  auth = xgt.OidcAuth(
    flow = "auth_code",
    # Set if Python needs a Keycloak CA bundle, including when xGT TLS
    # supplies a different ssl_server_cert.
    # ca_cert_path = "~/.config/rocketgraph/keycloak-ca.pem",
    force_login = True))

print("User:", conn.userid)
print("Labels:", conn.get_user_labels())
print("Test query:", conn.run_job("RETURN 1 AS ok").get_data())
