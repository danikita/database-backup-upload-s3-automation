
import os
import json
import pyodbc
import boto3
import datetime
from zoneinfo import ZoneInfo

# Variáveis de ambiente
DB_HOST = os.getenv("DB_HOST","sqlserver-backup-test.csrqpahbegrw.us-east-1.rds.amazonaws.com")
DB_PORT = os.getenv("DB_PORT", "1433")
SECRET_ARN = os.getenv("SECRET_ARN","arn:aws:secretsmanager:us-east-1:909203251240:secret:secret-rds-sqlserver-hQqEr9")
S3_BUCKET = os.getenv("S3_BUCKET","backup-teste-lambda")
S3_PREFIX = os.getenv("S3_PREFIX", "sqlserver/")


# Timestamp para nome do arquivo
timestamp = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y%m%d%H%M%S")

# Função para buscar credenciais no Secrets Manager
def get_db_credentials(secret_arn):
    secrets_client = boto3.client("secretsmanager", region_name="us-east-1")
    response = secrets_client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response["SecretString"])
    return secret["username"], secret["password"]

# Função principal do Lambda
def lambda_handler(event, context):
    results = []

    try:
        db_user, db_password = get_db_credentials(SECRET_ARN)

        conn_str = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={DB_HOST},{DB_PORT};"
            f"UID={db_user};"
            f"PWD={db_password};"
            f"Encrypt=no;"
        )

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sys.databases WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb', 'rdsadmin')")
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
                results.append(f"✅ Backup iniciado para {db} → {s3_arn}")
            except Exception as e:
                results.append(f"❌ Erro ao iniciar backup de {db}: {str(e)}")

    except Exception as e:
        results.append(f"❌ Erro de conexão ou credenciais: {str(e)}")

    return {
        "statusCode": 200 if all("✅" in r for r in results) else 500,
        "body": results
    }
