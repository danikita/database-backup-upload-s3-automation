FROM public.ecr.aws/lambda/python:3.11

# Instala dependências base
RUN yum install -y \
    unixODBC \
    unixODBC-devel \
    curl \
    && yum clean all

# Importa a chave GPG da Microsoft antecipadamente e adiciona o repositório
RUN curl -L https://packages.microsoft.com/keys/microsoft.asc | rpm --import - \
    && curl -L https://packages.microsoft.com/config/rhel/7/prod.repo \
        -o /etc/yum.repos.d/mssql-release.repo

# Instala o driver sem prompt interativo de GPG
RUN ACCEPT_EULA=Y yum install -y --nogpgcheck msodbcsql17 \
    && yum clean all

RUN pip install --no-cache-dir pyodbc boto3

COPY app.py ${LAMBDA_TASK_ROOT}
COPY config.txt ${LAMBDA_TASK_ROOT}

CMD ["app.lambda_handler"]
