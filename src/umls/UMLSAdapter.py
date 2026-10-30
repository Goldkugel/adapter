"""
Concrete adapter for the Unified Medical Language System (UMLS).

Reads the configured UMLS RRF files (MRCONSO, MRDEF) via the appropriate
parsers and transformers from UMLSAdapterUtils. BaseAdapter.load()
merges and cleans the resulting EAV tables and adds the configured
prefix (by default "UMLS:", the prefix HPO uses for CUIs in its
cross-references).
"""

from __future__ import annotations

import os

from ..BaseAdapter       import BaseAdapter, standard_directory
from ..BaseAdapterConfig import BaseAdapterConfig
from .UMLSAdapterUtils   import readRRFFileByPath
import pandas            as pd

config_keyword: str = "umls"


class UMLSAdapter(BaseAdapter):
    """
    Concrete adapter for loading selected UMLS RRF files into the shared
    Entity-Attribute-Value (EAV) format.

    Each configured RRF file is read using the appropriate parser and
    transformer from UMLSAdapterUtils.
    """

    ontology_name  = "UMLS"

    # Used if the config section doesn't set `prefix`.
    default_prefix = "UMLS:"

    def __init__(
        self, config: str | os.PathLike | dict | BaseAdapterConfig = standard_directory
    ):
        """
        Load and validate the `adapter.umls` configuration.

        `config` is a YAML path, a dict (the whole configuration or just the
        `adapter.umls` settings) or a BaseAdapterConfig; see BaseAdapter.
        """
        super().__init__(config, config_keyword)

    def _loadFrames(self) -> list[pd.DataFrame]:
        """
        Read the configured UMLS RRF files and convert them to EAV rows.

        Returns
        -------
        list[pd.DataFrame]
            One entry per configured file: an EAV DataFrame, or None for
            a file that matches no known RRF prefix (skipped by load()).
        """
        frames = []

        for filename in self.config.input_files:

            path = os.path.join(
                self.config.input_folder,
                filename,
            )

            frames.append(
                readRRFFileByPath(
                    path,
                    self.config.id_column,
                    self.config.attribute_column,
                    self.config.value_column,
                    self.config.additional_column,
                    self.config.encoding,
                    self.config.separator
                )
            )

        return frames


if __name__ == "__main__":
    # Quick manual test: load UMLS and write the result to CSV.
    a = UMLSAdapter()
    a.load()
    a.to_csv()