FROM public.ecr.aws/lambda/python:3.11

# Dependências básicas
RUN yum install -y gcc gcc-c++ make yum-utils \
    && yum-config-manager --add-repo https://packages.microsoft.com/config/rhel/7/prod.repo \
    && yum install -y --nogpgcheck unixODBC-devel \
    && ACCEPT_EULA=Y yum install -y --nogpgcheck msodbcsql17 \
    && yum clean all \
    && rm -rf /var/cache/yum

# Python deps
RUN pip install --no-cache-dir pyodbc boto3

COPY app.py ${LAMBDA_TASK_ROOT}
COPY config.txt ${LAMBDA_TASK_ROOT}

CMD ["app.lambda_handler"]
