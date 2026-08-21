from logger     import Logger
import pandas   as pd
import os
import csv

labelClass                      = "label"
definitionClass                 = "definition"
commentClass                    = "comment"
referenceClass                  = "reference"
childrenClass                   = "child"
synonymClass                    = "synonym"

def writeCSV(
    data: pd.DataFrame = None,
    file: str = "",
    separator: str = ";",
    encoding: str = "utf-8"
) -> int:
    """
    Write a DataFrame to disk as a CSV file with logging.

    Parameters
    ----------
    data : pd.DataFrame, optional
        The DataFrame to write. If None, nothing is written and a
        message is logged instead.
    file : str, optional
        Path of the CSV file to write to. If empty, nothing is written
        and a message is logged instead.
    separator : str, optional
        Field delimiter used in the output CSV (default ";").
    encoding : str, optional
        Character encoding used when writing the file (default "utf-8").

    Returns
    -------
    int
        amount of lines written in CSV file.
    """
    ret: int = 0
    l: Logger = Logger()

    # Only proceed if a DataFrame was actually provided.
    if data is not None:
        # Only proceed if a target file path was actually provided.
        if len(file) > 0:
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
            ret = len(data.index)
        else:
            # No file path given — log and skip writing.
            l.log("File has not been specified and is empty.")
    else:
        # No DataFrame given — log and skip writing.
        l.log("No data provided.")

    return ret


def writeHugeCSV(
    data: pd.DataFrame = None,
    file: str = "",
    separator: str = ";",
    encoding: str = "utf-8"
) -> int:
    """
    Write a large DataFrame to disk safely by first writing to a
    temporary file, then atomically replacing the target file.

    This avoids leaving a corrupted or partially-written file at
    `file` if the write is interrupted, since the original file is
    only replaced once the temporary file has been fully written.

    Parameters
    ----------
    data : pd.DataFrame, optional
        The DataFrame to write.
    file : str, optional
        Path of the final CSV file to write to.
    separator : str, optional
        Field delimiter used in the output CSV (default ";").
    encoding : str, optional
        Character encoding used when writing the file (default "utf-8").

    Returns
    -------
    int
        amount of lines written in CSV file.
    """
    ret: int = 0
    l: Logger = Logger()

    l.log("Writing in temporary file first...")

    # Build the temporary file path by appending ".tmp" to the target path.
    tmpfile = file + ".tmp"

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

    return ret