"""Render entry point: bind the assigned port without prompting for a key."""
import os
from bag_local import App, ThreadingHTTPServer, VERSION


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), App)
    print(f"BaoDongNi {VERSION} listening on port {port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
