"""
Download Angel One Instrument Master
"""

from pathlib import Path
import json
import requests


INSTRUMENT_MASTER_URL = (
    "https://margincalculator.angelbroking.com/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)

SAVE_PATH = Path("data/instruments.json")


class InstrumentDownloader:

    def __init__(self):

        SAVE_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # -----------------------------------------------------

    def download(self):

        print("\n" + "=" * 70)
        print("DOWNLOADING INSTRUMENT MASTER")
        print("=" * 70)

        response = requests.get(
            INSTRUMENT_MASTER_URL,
            timeout=60,
        )

        response.raise_for_status()

        data = response.json()

        with open(
            SAVE_PATH,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
            )

        print(f"✓ Saved : {SAVE_PATH}")
        print(f"✓ Contracts : {len(data)}")

        return SAVE_PATH

    # -----------------------------------------------------

    def exists(self):

        return SAVE_PATH.exists()

    # -----------------------------------------------------

    def count(self):

        if not self.exists():
            return 0

        with open(
            SAVE_PATH,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        return len(data)