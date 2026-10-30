"""
Concrete adapter for the Human Phenotype Ontology (HPO).

Loads an OWL-format HPO file via owlready2 and runs each extractor from
HPOAdapterUtils against it. BaseAdapter.load() merges and cleans the
results; HPO IDs already carry their prefix ("HP:"), so the configured
prefix is empty by default.
"""

from __future__ import annotations

import os

from ..BaseAdapter       import BaseAdapter
from owlready2           import get_ontology
from logger              import Logger
from .HPOAdapterUtils    import (
    getLabels, getDefinitions, getComments,
    getChildren, getReferences, getSynonymsAndTypes,
)
import pandas            as pd


class HPOAdapter(BaseAdapter):
    """
    Concrete adapter for loading the Human Phenotype Ontology (HPO)
    into the shared EAV DataFrame format.

    Loads the OWL file specified in the adapter configuration (the first
    entry of `input_files`) via owlready2, then runs each HPOAdapterUtils
    extractor (labels, definitions, comments, children, references,
    synonyms) against it.
    """

    ontology_name  = "the Human Phenotype Ontology (HPO)"

    # Settings are read from the `adapter.hpo` section.
    config_section = "hpo"

    # Used if the config section doesn't set `prefix`.
    default_prefix = ""

    def _loadFrames(self) -> list[pd.DataFrame]:
        """
        Load the HPO OWL file and run every extractor against it.

        Returns
        -------
        list[pd.DataFrame]
            One EAV DataFrame per extractor (labels, definitions,
            comments, children, references, synonyms).
        """
        l = Logger()

        # The HPO is distributed as a single OWL file, so only the first
        # configured input file is used; any further entries are ignored.
        input_file = self.config.input_files[0]
        l.log(f"Loading the Human Phenotype Ontology (HPO) from '{input_file}'...")

        path = os.path.join(self.config.input_folder, input_file)
        hpo = get_ontology(path).load()

        extractors = [
            getLabels,
            getDefinitions,
            getComments,
            getChildren,
            getReferences,
            getSynonymsAndTypes,
        ]

        frames = []
        for extract in extractors:
            frames.append(
                extract(
                    hpo,
                    self.config.id_column,
                    self.config.attribute_column,
                    self.config.value_column,
                    self.config.additional_column,
                )
            )

        return frames

    def _clean(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Remove rows with a '#' in the ID — these are not concepts but
        hash IRIs such as annotation properties (oboInOwl#hasDbXref) or
        synonym types (hp#layperson).
        """
        l = Logger()

        l.log("Removing rows with a '#' in the ID...")
        id_column = self.config.id_column
        # Work on a copy: `data` is a filtered view of the merged frame,
        # and assigning a column to it would raise SettingWithCopyWarning.
        data = data.copy()
        data[id_column] = data[id_column].astype(str)
        data = data[~data[id_column].str.contains('#', na=False)]
        l.log("Removing rows with a '#' in the ID completed.")
        l.log(f"Reduced to {len(data)} entities/rows in total.")

        return data


if __name__ == "__main__":
    # Quick manual test: load the HPO and write the result to CSV.
    a = HPOAdapter()
    a.load()
    a.to_csv()