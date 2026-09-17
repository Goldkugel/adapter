"""
Shared utilities for all ontology adapters.

Provides EAV attribute-name constants (labelClass, synonymClass, etc.),
filesystem helpers (isFile, isFolder, createFolder), and CSV writing
helpers (writeCSV, writeHugeCSV) used by BaseAdapter and its concrete
subclasses.
"""

from __future__ import annotations

from logger     import Logger
import pandas   as pd
import os
import csv

labelClass      : str = "label"
definitionClass : str = "definition"
commentClass    : str = "comment"
referenceClass  : str = "reference"
childrenClass   : str = "child"
synonymClass    : str = "synonym"

def isFile(path: str = "") -> bool:
    """
    Check whether the given path refers to an existing file.

    Parameters
    ----------
    path : str, optional
        Path to check.

    Returns
    -------
    bool
        True if the path exists and is a file, False otherwise.
    """
    return os.path.isfile(path)


def isFolder(path: str = "") -> bool:
    """
    Check whether the given path refers to an existing directory.

    Parameters
    ----------
    path : str, optional
        Path to check.

    Returns
    -------
    bool
        True if the path exists and is a directory, False otherwise.
    """
    return os.path.isdir(path)


def createFolder(path: str = "") -> bool:
    """
    Create a directory if it does not already exist.

    A log message is written indicating whether the directory was created
    or already existed.

    Parameters
    ----------
    path : str, optional
        Path of the directory to create.

    Returns
    -------
    bool
        True if the directory was created, False if it already existed.
    """
    ret = False

    l = Logger()
    base_name = os.path.basename(path)

    if not isFolder(path):
        os.makedirs(path)
        l.log(f"Folder '{base_name}' created.")
        ret = True
    else:
        l.log(f"Folder '{base_name}' already exists.")

    return ret


def writeCSV(
    data: pd.DataFrame | None = None,
    file: str | None = None,
    separator: str = ";",
    encoding: str = "utf-8"
) -> int:
    """
    Write a DataFrame to disk as a CSV file with logging.

    Parameters
    ----------
    data : pd.DataFrame or None
        The DataFrame to write. If None, nothing is written and a
        message is logged instead.
    file : str or None
        Path of the CSV file to write to. If None or empty, nothing is
        written and a message is logged instead.
    separator : str, optional
        Field delimiter used in the output CSV (default ";").
    encoding : str, optional
        Character encoding used when writing the file (default "utf-8").

    Returns
    -------
    int
        Number of rows written to the CSV file.
    """
    ret: int = 0
    l: Logger = Logger()

    # Only proceed if a DataFrame was actually provided.
    if data is not None:
        # Only proceed if a target file path was actually provided.
        if file:
            # Log before starting the write, in case it's a large file
            # and takes noticeable time.
            l.printWriteFileStart(file)

            # Write the DataFrame to disk without the pandas row index,
            # using the given separator and encoding.
            data.to_csv(
                file,
                sep=separator,
                encoding=encoding,
                index=False,
                quoting=csv.QUOTE_ALL
            )

            # Log that the write completed.
            l.printWriteFileEnd(file)
            ret = len(data)
        else:
            # No file path given — log and skip writing.
            l.log("File has not been specified and is empty.")
    else:
        # No DataFrame given — log and skip writing.
        l.log("No data provided.")

    return ret


def writeHugeCSV(
    data: pd.DataFrame | None = None,
    file: str | None = None,
    separator: str = ";",
    encoding: str = "utf-8"
) -> int:
    """
    Write a DataFrame to disk atomically by first writing to a temporary
    file, then replacing the target file in a single operation.

    This avoids leaving a corrupted or partially-written file at `file`
    if the write is interrupted, since the original file is only replaced
    once the temporary file has been fully written. The temporary file is
    always cleaned up, even if the write fails.

    Parameters
    ----------
    data : pd.DataFrame or None
        The DataFrame to write.
    file : str or None
        Path of the final CSV file to write to.
    separator : str, optional
        Field delimiter used in the output CSV (default ";").
    encoding : str, optional
        Character encoding used when writing the file (default "utf-8").

    Returns
    -------
    int
        Number of rows written to the CSV file.
    """
    ret: int = 0
    l: Logger = Logger()

    # Guard early — no point in creating a temp file if inputs are invalid.
    if data is None:
        l.log("No data provided.")
        return ret
    if not file:
        l.log("File has not been specified and is empty.")
        return ret

    # Build the temporary file path by appending ".tmp" to the target path.
    tmpfile = file + ".tmp"

    l.log("Writing in temporary file first...")

    try:
        # Write to the temporary file first, reusing writeCSV's logic.
        ret = writeCSV(data, tmpfile, separator, encoding)

        # Only replace the original file if the temporary write succeeded.
        if ret > 0:
            l.log("Replacing original data with temporary data...")

            # Atomically replace the target file with the temporary file
            # (os.replace is atomic on both POSIX and Windows).
            os.replace(tmpfile, file)

            l.log("Replacing original data with temporary data completed.")
        else:
            l.log("Nothing written, therefore not replacing the data.")
    finally:
        # Always clean up the temporary file if it still exists.
        if os.path.exists(tmpfile):
            os.remove(tmpfile)

    return ret