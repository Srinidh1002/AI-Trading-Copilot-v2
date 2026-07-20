from services.market.download_master import InstrumentDownloader


def main():

    downloader = InstrumentDownloader()

    path = downloader.download()

    print("\n")
    print("=" * 70)
    print("DOWNLOAD COMPLETE")
    print("=" * 70)

    print("Path :", path)

    print("Exists :", downloader.exists())

    print("Contracts :", downloader.count())


if __name__ == "__main__":
    main()