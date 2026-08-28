import os

import psycopg


def get_connection() -> psycopg.Connection:
    host = os.environ["QUANTLAB_DB_HOST"]
    port = os.environ.get("QUANTLAB_DB_PORT", "5432")
    dbname = os.environ["QUANTLAB_DB_NAME"]
    user = os.environ["QUANTLAB_DB_USER"]
    password = os.environ["QUANTLAB_DB_PASSWORD"]

    return psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        sslmode="require",
    )
