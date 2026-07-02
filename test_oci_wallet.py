import os
import oracledb

print("connect start", flush=True)

conn = oracledb.connect(
    user=os.environ["OCI_USER"],
    password=os.environ["OCI_PASSWORD"],
    dsn=os.environ["OCI_DSN"],
    config_dir=os.environ["TNS_ADMIN"],
    wallet_location=os.environ["WALLET_LOCATION"],
    ssl_server_dn_match=True,
    tcp_connect_timeout=15,
)

print("connected", flush=True)

with conn.cursor() as cursor:
    cursor.execute("select 1 from dual")
    print(cursor.fetchone(), flush=True)

conn.close()
print("done", flush=True)
