
FROM public.ecr.aws/lambda/python:3.11

# Instala dependências e configura repositório da Microsoft
RUN yum install -y curl gnupg unixODBC unixODBC-devel \
    && curl https://packages.microsoft.com/config/rhel/7/prod.repo -o /etc/yum.repos.d/mssql-release.repo \
    && ACCEPT_EULA=Y yum install -y msodbcsql18

# Instala pyodbc
RUN pip install pyodbc

# Copia o script
COPY app.py ./

# Define o handler
CMD ["app.lambda_handler"]
