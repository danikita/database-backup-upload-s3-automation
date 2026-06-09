FROM public.ecr.aws/lambda/python:3.11

# Instala dependências necessárias para ODBC + SQL Server
RUN yum install -y \
    curl \
    gnupg2 \
    unixODBC-devel \
    && curl https://packages.microsoft.com/config/rhel/7/prod.repo \
       -o /etc/yum.repos.d/mssql-release.repo \
    && ACCEPT_EULA=Y yum install -y msodbcsql18 \
    && yum clean all \
    && rm -rf /var/cache/yum

# Instala dependências Python
RUN pip install --no-cache-dir pyodbc boto3

# Copia o código
COPY app.py ${LAMBDA_TASK_ROOT}

# Define handler
CMD ["app.lambda_handler"]
