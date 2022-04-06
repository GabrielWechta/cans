FROM python:3.8 AS server_dev

WORKDIR /usr/src/app

COPY requirements.txt .
COPY requirements_dev.txt .

RUN pip install -r requirements.txt
RUN pip install -r requirements_dev.txt
RUN mkdir log

COPY src/server .
COPY src/common common
COPY certs/CansCert.pem certs/CansCert.pem
COPY certs/CansKey.pem certs/CansKey.pem

FROM python:3.8 AS client_dev

WORKDIR /usr/src/app

COPY requirements.txt .
COPY requirements_dev.txt .

RUN pip install -r requirements.txt
RUN pip install -r requirements_dev.txt

COPY src/client .
COPY src/common common
COPY certs/CansCert.pem certs/CansCert.pem

FROM python:3.8 AS server

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY src/server .
COPY certs/CansCert.pem certs/CansCert.pem
COPY certs/CansKey.pem certs/CansKey.pem

CMD ["python", "main"]
