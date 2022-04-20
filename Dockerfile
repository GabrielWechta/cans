FROM python:3.8 AS server

WORKDIR /usr/src/app

# Copy required modules
COPY server server
COPY common common

# Install the modules
RUN pip install -e server
RUN pip install -e common

# Make the log directory
RUN mkdir log

# Copy resources
COPY resources/certs/CansCert.pem resources/certs/CansCert.pem
COPY resources/certs/CansKey.pem resources/certs/CansKey.pem

CMD ["python", "-u", "-m", "server"]

FROM python:3.8 AS client_dev

WORKDIR /usr/src/app

# Copy required modules
COPY client client
COPY common common

# Install the modules
RUN pip install -e client
RUN pip install -e common

# Copy resources
COPY resources/certs/CansCert.pem resources/certs/CansCert.pem
