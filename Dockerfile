FROM python:3.8 AS server_dev

WORKDIR /usr/src/app

COPY requirements_dev.txt .

RUN pip install -r requirements_dev.txt

COPY src/server .

FROM python:3.8 AS client_dev

WORKDIR /usr/src/app

COPY requirements_dev.txt .

RUN pip install -r requirements_dev.txt

COPY src/client .


FROM python:3.8 AS server

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY src/server .

CMD ["python", "main"]

FROM python:3.8 AS client

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY src/client .

CMD ["python", "main"]
