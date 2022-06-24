
default:
	docker-compose build cans-server
	docker-compose build cans-echo-service
	./bootstrap

install:
# Install the client
	pip install -e common
	pip install -e client
# Make a symbolic link
	ln -s $(PWD)/cans /home/$(USER)/.local/bin/cans || { echo "Failed to create a symbolic link to the cans executable" && exit 1; }

server-up:
# Deploy the server in a docker container
	docker-compose up --detach cans-server

server-down:
# Tear down the server
	docker stop cans-server

echo-up:
# Deploy the echo client
	docker-compose up --detach cans-echo-service

echo-down:
# Tear down the echo client
	docker stop cans-echo-service

test:
# Run test suite
	./run_full_test_suite
