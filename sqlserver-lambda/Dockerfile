FROM public.ecr.aws/lambda/python:3.11

RUN yum install -y \
    unixODBC \
    unixODBC-devel \
    curl \
    && yum clean all

RUN curl -L https://packages.microsoft.com/rhel/7/prod/msodbcsql17-17.10.6.1-1.x86_64.rpm \
    -o msodbcsql17.rpm \
    && rpm -i --nodeps msodbcsql17.rpm \
    && rm msodbcsql17.rpm

RUN pip install --no-cache-dir pyodbc boto3

COPY app.py ${LAMBDA_TASK_ROOT}
COPY config.txt ${LAMBDA_TASK_ROOT}

CMD ["app.lambda_handler"]
