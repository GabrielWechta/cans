"""Backend application entry point."""

from . import Server

if __name__ == "__main__":
    server = Server()
    server.run()
