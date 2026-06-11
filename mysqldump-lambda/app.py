import os
import json
import boto3
import subprocess
import datetime
from zoneinfo import ZoneInfo

# ENVIRONMENT VARIABLES
DB_HOST = os.getenv("DB_HOST", "mysql-backup-teste.csrqpahbegrw.us-east-1.rds.amazonaws.com")
DB_PORT = os.getenv("DB_PORT", "3306")
SECRET_ARN = os.getenv("SECRET_ARN", "arn:aws:secretsmanager:us-east-1:909203251240:secret:secret-rds-mysql-2umpji")
S3_BUCKET = os.getenv("S3_BUCKET", "backup-teste-lambda")
S3_PREFIX = os.getenv("S3_PREFIX", "mysql/")

s3_client = boto3.client("s3")
secrets_client = boto3.client("secretsmanager")

def get_db_credentials(secret_arn):
    """Busca usuário e senha no Secrets Manager"""
    response = secrets_client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response["SecretString"])
    return secret["username"], secret["password"]

def list_databases(db_user, db_password):
    """Lista os bancos (exceto system schemas)"""
    env = os.environ.copy()

    cmd = [
        "mysql",
        "-h", DB_HOST,
        "-P", DB_PORT,
        "-u", db_user,
        f"-p{db_password}",
        "-N",  # remove header
        "-e", "SHOW DATABASES;"
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"mysql failed: {result.stderr}")

    dbs = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    # Exclui bancos de sistema
    exclude = {"information_schema", "performance_schema", "mysql", "sys"}
    return [db for db in dbs if db not in exclude]

def lambda_handler(event, context):
    timestamp = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y%m%d%H%M%S")
    db_user, db_password = get_db_credentials(SECRET_ARN)

    try:
        databases = list_databases(db_user, db_password)
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"❌ Failed to list databases: {str(e)}"
        }

    results = []

    for db in databases:
        filename = f"{db}_{timestamp}.sql"
        filepath = f"/tmp/{filename}"

        dump_cmd = [
            "mysqldump",
            "-h", DB_HOST,
            "-P", DB_PORT,
            "-u", db_user,
            f"-p{db_password}",
            "--databases", db,
            "-r", filepath
        ]

        result = subprocess.run(dump_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            results.append(f"❌ {db} mysqldump failed: {result.stderr.strip()}")
            continue

        try:
            s3_key = f"{S3_PREFIX}{filename}"
            s3_client.upload_file(filepath, S3_BUCKET, s3_key)
            results.append(f"✅ {db} → s3://{S3_BUCKET}/{s3_key}")
        except Exception as e:
            results.append(f"❌ {db} upload failed: {str(e)}")

    return {
        "statusCode": 200,
        "body": results
    }
