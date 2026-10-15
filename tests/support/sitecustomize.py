"""Network tripwire for CLI test subprocesses, activated explicitly by the tests."""
import os
if os.environ.get("MAKESOUND_TEST_NO_NETWORK") == "1":
    import socket

    def denied(*args, **kwargs):
        raise RuntimeError("NETWORK_FORBIDDEN_IN_M1_TEST")

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
