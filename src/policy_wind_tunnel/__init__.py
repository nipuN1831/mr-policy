import argparse


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the Policy Wind Tunnel demo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("policy_wind_tunnel.service.app:app", host=args.host, port=args.port)
