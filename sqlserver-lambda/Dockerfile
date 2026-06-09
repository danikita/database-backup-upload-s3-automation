FROM public.ecr.aws/lambda/python:3.11

# Instala dependências mais leves possível
RUN yum install -y \
    curl \
    gnupg2 \
    unixODBC-devel \
    && curl https://packages.microsoft.com/config/rhel/7/prod.repo \
    -o /etc/yum.repos.d/mssql-release.repo \
    && ACCEPT_EULA=Y yum install -y msodbcsql18 \
    && yum clean all

# Instala Python libs
RUN pip install pyodbc

# Copia código
COPY app.py ${LAMBDA_TASK_ROOT}

# Handler
CMD ["app.lambda_handler"]
