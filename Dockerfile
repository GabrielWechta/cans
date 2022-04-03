FROM python:3.8 AS server_dev

WORKDIR /usr/src/app

COPY requirements_dev.txt .

RUN pip install -r requirements_dev.txt

COPY src/server .
COPY certs/CansCert.pem .
COPY certs/CansKey.pem .

FROM python:3.8 AS client_dev

WORKDIR /usr/src/app

COPY requirements_dev.txt .

RUN pip install -r requirements_dev.txt

COPY src/client .
COPY certs/CansCert.pem .

FROM python:3.8 AS server

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install -r requirements.txt

# TODO: Add directory structure to the server image
COPY src/server .
COPY certs/CansCert.pem .
COPY certs/CansKey.pem .

CMD ["python", "main"]

FROM python:3.8 AS client

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY src/client .

CMD ["python", "main"]
