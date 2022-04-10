FROM python:3.8 AS server_dev

WORKDIR /usr/src/app

COPY server/requirements.txt .

RUN pip install -r requirements.txt
RUN mkdir log

COPY server .
COPY common common
COPY resources/certs/CansCert.pem certs/CansCert.pem
COPY resources/certs/CansKey.pem certs/CansKey.pem

FROM python:3.8 AS client_dev

WORKDIR /usr/src/app

COPY client/requirements.txt .

RUN pip install -r requirements.txt

COPY client .
COPY common common
COPY resources/certs/CansCert.pem certs/CansCert.pem

FROM python:3.8 AS server

WORKDIR /usr/src/app

COPY server/requirements.txt .

RUN pip install -r requirements.txt

COPY server .
COPY resources/certs/CansCert.pem certs/CansCert.pem
COPY resources/certs/CansKey.pem certs/CansKey.pem

CMD ["python", "main"]
