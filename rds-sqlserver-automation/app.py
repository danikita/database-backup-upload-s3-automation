import json
import time
import pyodbc
import boto3
import datetime
from zoneinfo import ZoneInfo


VALID_BACKUP_TYPES = {"FULL", "DIFFERENTIAL"}

POLL_INTERVAL_SEC = 15
POLL_TIMEOUT_SEC  = 600  # 10 minutos


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


def extract_task_id(cursor):
    """
    rds_backup_database retorna múltiplos result sets via pyodbc.
    Itera com nextset() até encontrar uma linha com task_id numérico.
    Retorna o task_id (int) ou None se não encontrar.
    """
    while True:
        try:
            row = cursor.fetchone()
            if row is not None:
                # O task_id é sempre um inteiro na primeira coluna
                val = row[0]
                if isinstance(val, int):
                    return val
                # Algumas versões retornam como string numérica
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass  # não é task_id, continua para próximo result set
        except Exception:
            pass

        # Avança para o próximo result set
        try:
            has_more = cursor.nextset()
        except Exception:
            has_more = False

        if not has_more:
            break

    return None


def wait_for_task(cursor, task_id, timeout=POLL_TIMEOUT_SEC):
    """
    Aguarda conclusão da task assíncrona do RDS.
    Retorna (success: bool, message: str).
    """
    deadline  = time.time() + timeout
    lifecycle = "UNKNOWN"

    while time.time() < deadline:
        cursor.execute(
            "exec msdb.dbo.rds_task_status @task_id=?",
            task_id
        )

        row = cursor.fetchone()
        if row is None:
            return False, f"Task {task_id} não encontrada em rds_task_status."

        # Colunas de rds_task_status (posições documentadas pela AWS):
        # 0: task_id  1: task_type  2: lifecycle  3: created_at  4: last_updated
        # 5: database_name  6: S3_object_arn  7: overwrite_s3_backup_file
        # 8: KMS_master_key_arn  9: filepath  10: error_message
        lifecycle = (row[2] or "").strip().upper()
        error_msg = row[10] if len(row) > 10 else None

        print(f"[poll] task_id={task_id} lifecycle={lifecycle}")

        if lifecycle == "SUCCESS":
            return True, f"Task {task_id} concluída com sucesso."

        if lifecycle in ("ERROR", "CANCELLED", "FAILED"):
            detail = error_msg or lifecycle
            return False, f"Task {task_id} falhou ({lifecycle}): {detail}"

        # Drena result sets extras antes do próximo poll
        while cursor.nextset():
            pass

        time.sleep(POLL_INTERVAL_SEC)

    return False, f"Task {task_id} excedeu o timeout de {timeout}s (lifecycle={lifecycle})."


def lambda_handler(event, context):
    results = []

    try:
        DB_HOST     = event.get("DB_HOST")
        DB_PORT     = event.get("DB_PORT", "1433")
        S3_BUCKET   = event.get("S3_BUCKET")
        S3_PREFIX   = event.get("S3_PREFIX", "")
        BACKUP_TYPE = event.get("BACKUP_TYPE", "FULL").upper()
        WAIT        = event.get("WAIT_FOR_COMPLETION", True)

        if not DB_HOST or not S3_BUCKET:
            raise ValueError("DB_HOST and S3_BUCKET are required in the event.")

        if BACKUP_TYPE not in VALID_BACKUP_TYPES:
            raise ValueError(
                f"Invalid BACKUP_TYPE '{BACKUP_TYPE}'. Must be FULL or DIFFERENTIAL."
            )

        db_user, db_password = get_db_credentials(event)

        timestamp = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y%m%d%H%M%S")

        ext_map  = {"FULL": "bak", "DIFFERENTIAL": "diff.bak"}
        file_ext = ext_map[BACKUP_TYPE]

        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_HOST},{DB_PORT};"
            f"UID={db_user};"
            f"PWD={db_password};"
            f"Encrypt=no;"
        )

        conn   = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Garante que existe FULL backup antes do DIFFERENTIAL
        if BACKUP_TYPE == "DIFFERENTIAL":
            cursor.execute("""
                SELECT TOP 1 database_name
                FROM msdb.dbo.backupset
                WHERE type = 'D'
                  AND database_name NOT IN ('master','tempdb','model','msdb','rdsadmin')
                ORDER BY backup_finish_date DESC
            """)
            if cursor.fetchone() is None:
                raise ValueError(
                    "Nenhum FULL backup encontrado no backupset. "
                    "Execute um FULL backup antes do DIFFERENTIAL."
                )

        cursor.execute("""
            SELECT name
            FROM sys.databases
            WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb', 'rdsadmin')
        """)
        databases = [row[0] for row in cursor.fetchall()]

        for db in databases:
            s3_arn = (
                f"arn:aws:s3:::{S3_BUCKET}/{S3_PREFIX}"
                f"{db}_{BACKUP_TYPE}_{timestamp}.{file_ext}"
            )

            sql = (
                "exec msdb.dbo.rds_backup_database "
                f"  @source_db_name=N'{db}', "
                f"  @s3_arn_to_backup_to=N'{s3_arn}', "
                f"  @type=N'{BACKUP_TYPE}', "
                "   @overwrite_S3_backup_file=1;"
            )

            try:
                cursor.execute(sql)
                conn.commit()

                task_id = extract_task_id(cursor)
                print(f"[backup] db={db} task_id={task_id}")

                if task_id is None:
                    results.append(
                        f"[{BACKUP_TYPE}][WARN] {db} → task_id não obtido. "
                        f"Verifique rds_task_status manualmente. s3={s3_arn}"
                    )
                    continue

                if WAIT:
                    success, msg = wait_for_task(cursor, task_id)
                    status = "OK" if success else "FAILED"
                    results.append(
                        f"[{BACKUP_TYPE}][{status}] {db} | task_id={task_id} | {msg} | s3={s3_arn}"
                    )
                else:
                    results.append(
                        f"[{BACKUP_TYPE}][STARTED] {db} | task_id={task_id} | s3={s3_arn}"
                    )

            except Exception as e:
                results.append(f"[{BACKUP_TYPE}][ERROR] {db}: {str(e)}")

    except Exception as e:
        results.append(f"Error: {str(e)}")

    all_ok = results and all(
        "[ERROR]" not in r and "[FAILED]" not in r and "Error:" not in r
        for r in results
    )

    return {
        "statusCode": 200 if all_ok else 500,
        "body": results,
    }
