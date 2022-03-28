FROM python:3.8 AS development

WORKDIR /usr/src/app

COPY requirements_dev.txt .

RUN pip install -r requirements_dev.txt

COPY src/ .
