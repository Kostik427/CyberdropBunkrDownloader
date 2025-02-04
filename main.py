import sys
import argparse
import os
from modules import network, downloader


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Manager")
    parser.add_argument(
        "-u", help="URL to fetch", type=str, required=False, default=None
    )
    parser.add_argument(
        "-f", help="File with list of URLs to download", type=str, default=None
    )
    parser.add_argument(
        "-r", help="Number of retries if connection fails", type=int, default=10
    )
    parser.add_argument(
        "-e", help="Comma-separated file extensions to download", type=str, default=""
    )
    parser.add_argument(
        "-p", help="Custom download folder path", type=str, default=None
    )
    parser.add_argument(
        "-w", help="Export URL list only (for wget, etc.)", action="store_true"
    )
    return parser.parse_args()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    args = parse_arguments()

    if args.u is None and args.f is None:
        print("[-] No URL or file provided")
        sys.exit(1)

    if args.u is not None and args.f is not None:
        print("[-] Please provide only one URL or file")
        sys.exit(1)

    session = network.create_session()
    cdn_list = network.get_cdn_list(session)

    if args.f:
        if not os.path.isfile(args.f):
            print(f"[-] File {args.f} does not exist.")
            sys.exit(1)
        with open(args.f, "r", encoding="utf-8") as file:
            urls = file.read().splitlines()
        for url in urls:
            print(f"[~] Processing URL: {url}")
            downloader.process_url(
                session=session,
                cdn_list=cdn_list,
                url=url,
                retries=args.r,
                extensions=args.e,
                only_export=args.w,
                custom_path=args.p,
            )
    else:
        downloader.process_url(
            session=session,
            cdn_list=cdn_list,
            url=args.u,
            retries=args.r,
            extensions=args.e,
            only_export=args.w,
            custom_path=args.p,
        )


if __name__ == "__main__":
    main()