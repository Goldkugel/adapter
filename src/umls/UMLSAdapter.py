"""
Concrete adapter for the Unified Medical Language System (UMLS).

Reads the configured UMLS RRF files (MRCONSO, MRDEF) via the appropriate
parsers and transformers from UMLSAdapterUtils, concatenates the resulting
EAV tables, and stores the result in self.data.
"""

from __future__ import annotations

import os

from ..BaseAdapter      import BaseAdapter, standard_directory
from ..BaseAdapterUtils import isFile
from .UMLSAdapterUtils  import readRRFFileByPath
from logger             import Logger
import pandas           as pd

config_keyword: str = "umls"


class UMLSAdapter(BaseAdapter):
    """
    Concrete adapter for loading selected UMLS RRF files into the shared
    Entity-Attribute-Value (EAV) format.

    Each configured RRF file is read using the appropriate parser and
    transformer from UMLSAdapterUtils. The resulting EAV tables are then
    concatenated into self.data.
    """

    def __init__(self, config: str = standard_directory):
        super().__init__(config, config_keyword)

    def load(self) -> int:
        """
        Load the configured UMLS RRF files and populate self.data.

        Returns
        -------
        int
            Number of EAV rows loaded into self.data.
        """
        ret = 0
        l = Logger()

        if self.config.input_files:

            output_file = os.path.join(
                self.config.output_folder,
                self.config.output_file,
            )

            if isFile(output_file) and self.config.skip_if_present:
                l.log("Skipping loading since output file is already present.")
            else:
                l.log(f"Loading UMLS from {len(self.config.input_files)} files...")

                frames = []

                for filename in self.config.input_files:

                    path = os.path.join(
                        self.config.input_folder,
                        filename,
                    )

                    frame = readRRFFileByPath(
                        path,
                        self.config.id_column,
                        self.config.attribute_column,
                        self.config.value_column,
                        self.config.additional_column,
                        self.config.encoding,
                        self.config.separator
                    )

                    if frame is not None and len(frame) > 0:
                        frames.append(frame)

                l.log("Loading completed.")

                if frames:
                    l.log("Merging data...")
                    self.data = pd.concat(
                        frames,
                        ignore_index=True,
                    )
                    ret = len(self.data)
                    l.log(f"Found {ret} entities/rows in total.")

                    # Remove rows without an identifier — these can appear
                    # when a CUI fails to resolve or a mapping row references
                    # a retired concept.
                    l.log("Removing rows without an ID...")
                    self.data = self.data[
                        (self.data[self.config.id_column].notna()) &
                        (self.data[self.config.id_column] != "")
                    ]
                    l.log("Removing rows without an ID completed.")
                    ret = len(self.data)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                    # Remove rows without a value — empty strings or map
                    # targets add no information and can cause issues
                    # downstream (e.g. empty cells in the EAV CSV).
                    l.log("Removing rows without values...")
                    self.data = self.data[
                        (self.data[self.config.value_column].notna()) &
                        (self.data[self.config.value_column] != "")
                    ]
                    l.log("Removing rows without values completed.")
                    ret = len(self.data)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                    # Remove exact duplicates across (id, attribute, value) —
                    # the same term can appear in multiple source vocabularies,
                    # so deduplication ensures clean downstream output.
                    l.log("Removing duplicate rows...")
                    self.data = self.data.drop_duplicates(subset=[
                        self.config.id_column,
                        self.config.attribute_column,
                        self.config.value_column
                    ]).reset_index(drop=True)
                    l.log("Removing duplicate rows completed.")
                    ret = len(self.data)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                else:
                    l.log("No data found. Are the configured files correct?")

                l.log(f"Loading UMLS from {len(self.config.input_files)} files completed.")

        else:
            l.log("No input files found. Were they set in the configuration file?")

        return ret


if __name__ == "__main__":
    # Quick manual test: load UMLS and write the result to CSV.
    a = UMLSAdapter()
    a.load()
    a.to_csv()