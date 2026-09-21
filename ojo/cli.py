"""`ojo build` and `ojo serve`."""

from __future__ import annotations

import argparse
import functools
import http.server
import logging
import socketserver
import webbrowser

from .config import SITE_DIR
from .export import build_all, write

log = logging.getLogger(__name__)


def cmd_build(args: argparse.Namespace) -> int:
    payload = build_all()
    write(payload)
    counts = payload["counts"]
    print()
    print(f"  Santa Fe        {counts['santa_fe']:3d} corridors  (curated from reporting; no city feed)")
    print(f"  Albuquerque     {counts['albuquerque']:3d} corridors  (city-published list)")
    print(f"  community       {counts['community']:3d} corridors  ({counts['duplicates_dropped']} duplicates dropped)")
    print(f"  schools         {counts['schools']:3d} points")
    print(f"  near a school   {counts['corridors_near_a_school']:3d} corridors have the halved threshold in play")
    if payload["unresolved"]:
        print()
        print(f"  {len(payload['unresolved'])} announcement(s) could NOT be placed:")
        for line in payload["unresolved"]:
            print(f"    - {line}")
        print("  These are real cameras. They are missing from the map, not absent from the road.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE_DIR))
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as server:
        url = f"http://127.0.0.1:{args.port}/"
        print(f"serving {SITE_DIR} at {url}  (ctrl-c to stop)")
        if not args.no_open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ojo", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="refresh every source and write site/data")
    build.set_defaults(func=cmd_build)

    serve = subparsers.add_parser("serve", help="serve site/ locally")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--no-open", action="store_true")
    serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)
