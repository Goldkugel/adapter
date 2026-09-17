"""
Concrete adapter for SNOMED CT (RF2 release format).

Reads the Concept, Description, TextDefinition, Relationship, and
SimpleMap files named in the configuration, restricts every file to
concepts that are currently active (per the Concept file), then
converts each remaining file into EAV rows and concatenates them into
self.data.
"""

from __future__ import annotations

import os

from ..BaseAdapter      import BaseAdapter, standard_directory
from ..BaseAdapterUtils import isFile
from .SCTAdapterUtils   import (
    conceptPrefix, readConceptFile, getConcepts, rf2SourceId,
    readRF2FileByPath, removeNotActiveConcepts,
)
from logger             import Logger
import pandas           as pd

config_keyword: str = "sct"


class SCTAdapter(BaseAdapter):
    """
    Concrete adapter for loading SNOMED CT (RF2 release format) into
    the shared EAV DataFrame format.

    Reads the Concept, Description, TextDefinition, Relationship, and
    Simple Map files named in the configuration, restricts every file
    to concepts that are currently active (per the Concept file), then
    converts each remaining file into EAV rows and concatenates them
    into self.data.
    """

    def __init__(self, config: str = standard_directory):
        super().__init__(config, config_keyword)

    def _findInputFile(self, prefix: str) -> str:
        """
        Return the single configured input file whose name starts with
        `prefix`. Raises if none or more than one match is found.
        """
        matches = [
            f for f in self.config.input_files
            if os.path.basename(f).startswith(prefix)
        ]
        if len(matches) == 0:
            raise FileNotFoundError(
                f"No configured input file starts with '{prefix}'."
            )
        if len(matches) > 1:
            raise ValueError(
                f"Multiple configured input files start with '{prefix}': "
                f"{matches}. Expected exactly one."
            )
        return matches[0]

    def load(self) -> int:
        """
        Load the configured SNOMED CT RF2 files and populate self.data
        with all extracted EAV rows.

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
                self.config.output_file
            )

            if isFile(output_file) and self.config.skip_if_present:
                l.log("Skipping loading since output file is already present.")
            else:
                l.log(f"Loading SNOMED CT from "
                      f"{len(self.config.input_files)} files...")

                concepts = None

                # Separate the Concept file from the rest — it is read
                # first to build the active-concept filter set, then
                # excluded from the main EAV extraction loop.
                files = self.config.input_files.copy()
                for input_file in self.config.input_files:
                    if str(input_file).startswith(conceptPrefix) and concepts is None:
                        files.remove(input_file)
                        full_path = os.path.join(
                            self.config.input_folder,
                            input_file
                        )
                        concepts = getConcepts(
                            readConceptFile(
                                full_path,
                                self.config.encoding,
                                self.config.separator
                            ),
                            rf2SourceId
                        )

                frames = []

                for input_file in files:
                    full_path = os.path.join(
                        self.config.input_folder,
                        input_file
                    )

                    frame = readRF2FileByPath(
                        full_path,
                        self.config.id_column,
                        self.config.attribute_column,
                        self.config.value_column,
                        self.config.additional_column,
                        self.config.encoding,
                        self.config.separator
                    )
                    if frame is not None:
                        frame = removeNotActiveConcepts(
                            frame,
                            self.config.id_column,
                            concepts
                        )
                        if len(frame) > 0:
                            frames.append(frame)

                l.log("Loading completed.")

                if frames:
                    l.log("Merging data...")
                    self.data = pd.concat(frames, ignore_index=True)
                    ret = len(self.data)
                    l.log(f"Found {ret} entities/rows in total.")

                    # Remove rows without an identifier — these can appear
                    # when a concept URI fails to resolve to a valid SCTID,
                    # or when a mapping row references a retired concept.
                    l.log("Removing rows without an ID...")
                    self.data = self.data[
                        (self.data[self.config.id_column].notna()) &
                        (self.data[self.config.id_column] != "")
                    ]
                    l.log("Removing rows without an ID completed.")
                    ret = len(self.data)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                    # Remove rows without a value — empty terms or map
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
                    # the same term or relationship can appear in both a Full
                    # and a Snapshot RF2 file if both are configured, so
                    # deduplication ensures clean downstream output.
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
                    l.log("No data found. Is it the correct file?")

                l.log(f"Loading SNOMED CT from "
                      f"{len(self.config.input_files)} files completed.")

        else:
            l.log("No input files found. Were they set in the "
                  "configuration file?")

        return ret


if __name__ == "__main__":
    # Quick manual test: load SNOMED CT and write the result to CSV.
    a = SCTAdapter()
    a.load()
    a.to_csv()