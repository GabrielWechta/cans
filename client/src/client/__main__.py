"""Frontend application entry point."""

import sys  # TODO: Not needed after PoC

from . import Client

if __name__ == "__main__":
    client = Client(sys.argv[1], sys.argv[2])
    client.run()
