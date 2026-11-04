"""
Shared utilities for all ontology adapters.

EAV attribute-name constants, filesystem and CSV writing helpers, helpers
for the source-specific readers (additionalFrom, readFileByPrefix) and
mergeAdditional for the additional information of duplicate rows.
"""

from __future__ import annotations

from logger     import Logger
import pandas   as pd
import os
import csv

# --- EAV attribute names (values of the attribute column) ---

# childrenClass rows read "id has child value": the id is the parent
# concept and the value is one of its direct children.
labelClass      : str = "label"
definitionClass : str = "definition"
commentClass    : str = "comment"
referenceClass  : str = "reference"
childrenClass   : str = "child"
synonymClass    : str = "synonym"

# Joins the different values of one key when the additional information of
# duplicate rows is merged (see mergeAdditional()), e.g. "exact, related".
additionalSeparator : str = ", "

def mergeAdditional(entries) -> dict:
    """
    Merge the additional dicts of duplicate (id, attribute, value) rows.

    A key with one distinct value keeps it; different values are joined in
    row order with additionalSeparator, e.g. {"class": "exact"} and
    {"class": "related"} give {"class": "exact, related"}. Non-dict entries
    (e.g. NaN) are ignored.
    """
    values: dict = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key, value in entry.items():
            known = values.setdefault(key, [])
            if value not in known:
                known.append(value)

    return {
        key: known[0] if len(known) == 1 else additionalSeparator.join(str(v) for v in known)
        for key, known in values.items()
    }


def additionalFrom(values: pd.Series, key: str):
    """
    Build the additional column from one source column: a separate dict
    {key: value} per row, so rows never share one.
    """
    return values.map(lambda v: {key: v}).values


def readFileByPrefix(
    file_path        : str,
    handlers         : dict,
    kind             : str,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str,
    encoding         : str,
    separator        : str
) -> pd.DataFrame | None:
    """
    Read a single source file and convert it to EAV rows.

    `handlers` maps a filename prefix to a (reader, transformer) pair; the
    pair of the first prefix the file's own name starts with is used, so
    file_path must point to the file itself, not to its directory. The
    reader gets (file_path, encoding, separator), the transformer the
    raw frame and the four EAV column names. Returns None and logs a
    message naming `kind` (e.g. "RF2") if no prefix matches.
    """
    ret      = None
    l        = Logger()
    filename = os.path.basename(file_path)

    for prefix, (reader, transform) in handlers.items():
        if filename.startswith(prefix):
            ret = transform(
                reader(file_path, encoding, separator),
                id_column,
                attribute_column,
                value_column,
                additional_column
            )
            break

    if ret is None:
        l.log(f"'{filename}' doesn't match any known {kind} file prefix.")

    return ret


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

    Every field is quoted (csv.QUOTE_ALL), so separators, quotes and line
    breaks in values survive a round trip.

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

    if data is not None:
        if file:
            l.printWriteFileStart(file)
            data.to_csv(
                file,
                sep=separator,
                encoding=encoding,
                index=False,
                quoting=csv.QUOTE_ALL
            )

            l.printWriteFileEnd(file)
            ret = len(data)
        else:
            l.log("File has not been specified and is empty.")
    else:
        l.log("No data provided.")

    return ret


def writeHugeCSV(
    data: pd.DataFrame | None = None,
    file: str | None = None,
    separator: str = ";",
    encoding: str = "utf-8"
) -> int:
    """
    Write a DataFrame to disk atomically via a temporary file.

    An interrupted write never leaves a partial file at `file`; the
    temporary file is removed even if the write fails. An existing file
    is not replaced if no rows were written.

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

    if data is None:
        l.log("No data provided.")
        return ret
    if not file:
        l.log("File has not been specified and is empty.")
        return ret

    tmpfile = file + ".tmp"

    l.log("Writing to a temporary file first...")

    try:
        ret = writeCSV(data, tmpfile, separator, encoding)
        l.log("Writing to a temporary file first completed.")

        if ret > 0:
            l.log("Replacing original data with temporary data...")
            # os.replace is atomic on both POSIX and Windows.
            os.replace(tmpfile, file)

            l.log("Replacing original data with temporary data completed.")
        else:
            l.log("Nothing written, therefore not replacing the data.")
    finally:
        if os.path.exists(tmpfile):
            os.remove(tmpfile)

    return ret