FROM public.ecr.aws/lambda/python:3.11

RUN yum install -y yum-utils unixODBC unixODBC-devel \
    && yum-config-manager --add-repo https://packages.microsoft.com/config/rhel/7/prod.repo \
    && yum clean all

RUN ACCEPT_EULA=Y yum install -y --nogpgcheck --skip-broken msodbcsql17 \
    && yum clean all \
    && rm -rf /var/cache/yum

RUN pip install --no-cache-dir pyodbc boto3

COPY app.py ${LAMBDA_TASK_ROOT}
COPY config.txt ${LAMBDA_TASK_ROOT}

CMD ["app.lambda_handler"]
