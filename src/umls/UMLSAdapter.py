import sys

# Prevent Python from generating .pyc files (compiled bytecode files)
sys.dont_write_bytecode = True

import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from BaseAdapter import *
from Logger import Logger
import pandas as pd
import UMLSAdapterUtils as utils

config_keyword = "umls"


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
            Number of EAV rows loaded.
        """
        ret = 0
        l = Logger()

        if len(self.config.input_files) > 0:

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

                    frame = utils.readRFFFileByPath(
                        path,
                        self.config.id_column,
                        self.config.attribute_column,
                        self.config.value_column,
                        self.config.additional_column,
                    )

                    if frame is not None and len(frame.index) > 0:
                        frames.append(frame)

                    l.log(f"Loading completed.")

                if len(frames) > 0:

                    l.log("Merging data...")
                    self.data = pd.concat(
                        frames,
                        ignore_index=True,
                    )

                    ret = len(self.data.index)
                    l.log(f"Found {ret} entities/rows in total.")

                    #
                    # Remove rows without an identifier.
                    #
                    l.log("Removing rows without an ID...")
                    self.data = self.data[
                        (self.data[self.config.id_column].notna()) &
                        (self.data[self.config.id_column] != "")
                    ]
                    l.log("Removing rows without an ID completed.")

                    ret = len(self.data.index)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                    #
                    # Remove rows without values.
                    #
                    l.log("Removing rows without values...")
                    self.data = self.data[
                        (self.data[self.config.value_column].notna()) &
                        (self.data[self.config.value_column] != "")
                    ]
                    l.log("Removing rows without values completed.")

                    ret = len(self.data.index)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                    #
                    # Remove duplicate EAV entries.
                    #
                    l.log("Removing duplicate rows...")
                    self.data = self.data.drop_duplicates().reset_index(drop = True)
                    l.log("Removing duplicate rows completed.")

                    ret = len(self.data.index)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                else:
                    l.log("No data found. Are the configured files correct?")

                l.log(f"Loading UMLS from {len(self.config.input_files)} files completed.")
        else:
            l.log("No input files found. Were they set in the configuration file?")

        return ret


if __name__ == "__main__":
    a = UMLSAdapter()
    a.load()
    a.to_csv()