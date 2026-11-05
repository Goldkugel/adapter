"""
Concrete adapter for SNOMED CT (RF2 release format).

Reads the configured Concept, Description, TextDefinition, Relationship
and SimpleMap files, keeps only concepts active per the Concept file and
converts the rest into EAV rows. The default prefix "SNOMEDCT_US:" matches
the UMLS source abbreviation, which downstream mapping code relies on.
"""

from __future__ import annotations

import os

from ..BaseAdapter       import BaseAdapter
from .SCTAdapterUtils    import (
    conceptPrefix, readConceptFile, getConcepts, rf2SourceId,
    readRF2FileByPath, removeNotActiveConcepts,
)
import pandas            as pd


class SCTAdapter(BaseAdapter):
    """
    Adapter loading SNOMED CT (RF2 release format) into the shared EAV
    format, restricted to active concepts.
    """

    ontology_name  = "SNOMED CT"

    # Settings are read from the `adapter.sct` section.
    config_section = "sct"

    # Used if the config section doesn't set `prefix`.
    default_prefix = "SNOMEDCT_US:"

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
            One EAV DataFrame per recognised RF2 file other than the
            Concept file.
        """
        # The Concept file only provides the active-concept filter; it is
        # required, since without it inactive concepts can't be removed.
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
            # None: no known RF2 prefix (logged by readRF2FileByPath).
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