"""
Concrete adapter for SNOMED CT (RF2 release format).

Reads the Concept, Description, TextDefinition, Relationship, and
SimpleMap files named in the configuration, restricts every file to
concepts that are currently active (per the Concept file), and
converts each remaining file into EAV rows. BaseAdapter.load() merges
and cleans them and adds the configured prefix (by default
"SNOMEDCT_US:", which matches the source abbreviation used by UMLS and
which downstream mapping code relies on).
"""

from __future__ import annotations

import os

from ..BaseAdapter      import BaseAdapter, standard_directory
from .SCTAdapterUtils   import (
    conceptPrefix, readConceptFile, getConcepts, rf2SourceId,
    readRF2FileByPath, removeNotActiveConcepts,
)
import pandas           as pd

config_keyword: str = "sct"


class SCTAdapter(BaseAdapter):
    """
    Concrete adapter for loading SNOMED CT (RF2 release format) into
    the shared EAV DataFrame format.

    Reads the Concept, Description, TextDefinition, Relationship, and
    Simple Map files named in the configuration, restricts every file
    to concepts that are currently active (per the Concept file), and
    converts each remaining file into EAV rows.
    """

    ontology_name  = "SNOMED CT"

    # Used if the config section doesn't set `prefix`.
    default_prefix = "SNOMEDCT_US:"

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

    def _loadFrames(self) -> list[pd.DataFrame]:
        """
        Read the configured SNOMED CT RF2 files and convert them to EAV
        rows, restricted to active concepts.

        Returns
        -------
        list[pd.DataFrame]
            One EAV DataFrame per recognised RF2 file (excluding the
            Concept file, which only provides the active-concept filter).
        """
        # Separate the Concept file from the rest — it is read first to
        # build the active-concept filter set, then excluded from the
        # main EAV extraction loop. Raises if no (or more than one)
        # Concept file is configured, since without it inactive concepts
        # cannot be filtered out.
        concept_file = self._findInputFile(conceptPrefix)
        files = [f for f in self.config.input_files if f != concept_file]

        concepts = getConcepts(
            readConceptFile(
                os.path.join(self.config.input_folder, concept_file),
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
                frames.append(
                    removeNotActiveConcepts(
                        frame,
                        self.config.id_column,
                        concepts
                    )
                )

        return frames


if __name__ == "__main__":
    # Quick manual test: load SNOMED CT and write the result to CSV.
    a = SCTAdapter()
    a.load()
    a.to_csv()