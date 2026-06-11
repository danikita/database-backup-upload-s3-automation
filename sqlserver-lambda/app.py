import os
import json
import pyodbc
import boto3
import datetime
from zoneinfo import ZoneInfo


def get_db_credentials(event):
    secret_arn = event.get("SECRET_ARN", "").strip()

    if secret_arn.startswith("arn:"):
        secrets_client = boto3.client("secretsmanager", region_name="us-east-1")
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response["SecretString"])
        return secret["username"], secret["password"]

    db_user     = event.get("DB_USER")
    db_password = event.get("DB_PASSWORD")

    if not db_user or not db_password:
        raise ValueError("Provide either SECRET_ARN or DB_USER + DB_PASSWORD in the event.")

    return db_user, db_password


def lambda_handler(event, context):
    results = []

    try:
        DB_HOST   = event.get("DB_HOST")
        DB_PORT   = event.get("DB_PORT", "1433")
        S3_BUCKET = event.get("S3_BUCKET")
        S3_PREFIX = event.get("S3_PREFIX", "")

        if not DB_HOST or not S3_BUCKET:
            raise ValueError("DB_HOST and S3_BUCKET are required in the event.")

        db_user, db_password = get_db_credentials(event)

        timestamp = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y%m%d%H%M%S")

        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_HOST},{DB_PORT};"
            f"UID={db_user};"
            f"PWD={db_password};"
            f"Encrypt=no;"
        )

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name 
            FROM sys.databases 
            WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb', 'rdsadmin')
        """)
        databases = [row[0] for row in cursor.fetchall()]

        for db in databases:
            s3_arn = f"arn:aws:s3:::{S3_BUCKET}/{S3_PREFIX}{db}_{timestamp}.bak"

            sql = f"""
            exec msdb.dbo.rds_backup_database 
                @source_db_name='{db}', 
                @s3_arn_to_backup_to='{s3_arn}', 
                @overwrite_S3_backup_file=1;
            """

            try:
                cursor.execute(sql)
                conn.commit()
                results.append(f"Backup started for {db} → {s3_arn}")
            except Exception as e:
                results.append(f"Failed to start backup for {db}: {str(e)}")

    except Exception as e:
        results.append(f"Erro: {str(e)}")

    return {
        "statusCode": 200 if results and all("Erro" not in r for r in results) else 500,
        "body": results
    }
