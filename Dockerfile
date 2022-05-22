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

FROM python:3.8 AS client_echo

WORKDIR /usr/src/app

# installing olm
RUN apt-get update && apt-get install -y \
        cmake \
        libolm-dev

COPY resources/olm /usr/src/app/olm

# buidling olm
WORKDIR /usr/src/app/olm
RUN cmake . -Bbuild
RUN cmake --build build
RUN make install
# buidling python binding for olm
WORKDIR /usr/src/app/olm/python
RUN make olm-python3

WORKDIR /usr/src/app

# installing SQLCipher
RUN apt-get update && apt-get install -y \
        sqlcipher \
        libsqlcipher-dev \
        libsqlcipher0 \
        libssl-dev \
        gcc

RUN export LD_LIBRARY_PATH=/usr/local/lib
COPY resources/sqlcipher3 /usr/src/app/sqlcipher3
WORKDIR /usr/src/app/sqlcipher3
RUN python setup.py build
RUN python setup.py install

WORKDIR /usr/src/app

# Copy required modules
COPY client client
COPY common common

# Install the modules
RUN pip install -e client
RUN pip install -e common

# Copy resources
COPY resources/certs/CansCert.pem resources/certs/CansCert.pem
