"""
File Manager

Centralized file management utility for the
AI Trading Copilot.

Responsibilities
----------------
✓ Create Files & Directories
✓ Read / Write Files
✓ Append Files
✓ Copy / Move Files
✓ Delete Files
✓ List Directory Contents
✓ File Information
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


class FileManager:

    # --------------------------------------------------

    @staticmethod
    def create_directory(
        directory: str | Path,
    ) -> Path:

        path = Path(directory)

        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        return path

    # --------------------------------------------------

    @staticmethod
    def exists(
        path: str | Path,
    ) -> bool:

        return Path(path).exists()

    # --------------------------------------------------

    @staticmethod
    def create_file(
        path: str | Path,
    ) -> Path:

        file = Path(path)

        file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file.touch(
            exist_ok=True,
        )

        return file

    # --------------------------------------------------

    @staticmethod
    def read_text(
        path: str | Path,
        encoding: str = "utf-8",
    ) -> str:

        return Path(path).read_text(
            encoding=encoding,
        )

    # --------------------------------------------------

    @staticmethod
    def write_text(
        path: str | Path,
        data: str,
        encoding: str = "utf-8",
    ):

        file = Path(path)

        file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file.write_text(
            data,
            encoding=encoding,
        )

    # --------------------------------------------------

    @staticmethod
    def append_text(
        path: str | Path,
        data: str,
        encoding: str = "utf-8",
    ):

        file = Path(path)

        file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with file.open(
            "a",
            encoding=encoding,
        ) as f:

            f.write(data)

    # --------------------------------------------------

    @staticmethod
    def read_json(
        path: str | Path,
    ) -> dict[str, Any]:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    # --------------------------------------------------

    @staticmethod
    def write_json(
        path: str | Path,
        data: dict[str, Any],
    ):

        file = Path(path)

        file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with file.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                default=str,
            )

    # --------------------------------------------------

    @staticmethod
    def copy(
        source: str | Path,
        destination: str | Path,
    ):

        destination = Path(destination)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

    # --------------------------------------------------

    @staticmethod
    def move(
        source: str | Path,
        destination: str | Path,
    ):

        destination = Path(destination)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.move(
            str(source),
            str(destination),
        )

    # --------------------------------------------------

    @staticmethod
    def delete(
        path: str | Path,
    ) -> bool:

        file = Path(path)

        if not file.exists():

            return False

        if file.is_dir():

            shutil.rmtree(file)

        else:

            file.unlink()

        return True

    # --------------------------------------------------

    @staticmethod
    def list_files(
        directory: str | Path,
        pattern: str = "*",
    ) -> list[Path]:

        directory = Path(directory)

        if not directory.exists():

            return []

        return sorted(

            directory.glob(pattern)

        )

    # --------------------------------------------------

    @staticmethod
    def file_size(
        path: str | Path,
    ) -> int:

        return Path(path).stat().st_size

    # --------------------------------------------------

    @staticmethod
    def file_info(
        path: str | Path,
    ) -> dict[str, Any]:

        file = Path(path)

        stat = file.stat()

        return {

            "name": file.name,

            "path": str(file),

            "exists": file.exists(),

            "is_file": file.is_file(),

            "is_directory": file.is_dir(),

            "size": stat.st_size,

            "modified": stat.st_mtime,

            "created": stat.st_ctime,

        }

    # --------------------------------------------------

    @staticmethod
    def summary(
        directory: str | Path,
    ) -> dict[str, Any]:

        files = FileManager.list_files(directory)

        return {

            "directory": str(directory),

            "files": len(files),

            "names": [

                file.name

                for file in files

            ],

        }