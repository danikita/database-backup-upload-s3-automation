FROM public.ecr.aws/lambda/python:3.11

RUN yum install -y \
    unixODBC \
    unixODBC-devel \
    curl \
    tar \
    gzip \
    && yum clean all

RUN curl -L https://go.microsoft.com/fwlink/?linkid=2249006 \
    -o msodbcsql17.tar.gz \
    && mkdir -p /opt/microsoft \
    && tar -xzf msodbcsql17.tar.gz -C /opt/microsoft \
    && rm msodbcsql17.tar.gz

RUN echo "[ODBC Driver 17 for SQL Server]" > /etc/odbcinst.ini \
    && echo "Driver = /opt/microsoft/msodbcsql17/lib64/libmsodbcsql-17.so" >> /etc/odbcinst.ini

RUN pip install --no-cache-dir pyodbc boto3

COPY app.py ${LAMBDA_TASK_ROOT}
COPY config.txt ${LAMBDA_TASK_ROOT}

CMD ["app.lambda_handler"]
