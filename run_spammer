#!/usr/bin/env bash

docker-compose build cans-spammer-service

docker-compose run cans-spammer-service python -u -m client.spammer_client $1
