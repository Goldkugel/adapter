"""
Concrete adapter for the Human Phenotype Ontology (HPO).

Loads an OWL-format HPO file via owlready2, runs each extractor from
HPOAdapterUtils against it, and concatenates the results into a single
EAV DataFrame stored in self.data.
"""

from __future__ import annotations

import os

from ..BaseAdapter      import BaseAdapter, standard_directory
from ..BaseAdapterUtils import isFile
from owlready2          import get_ontology
from logger             import Logger
from .HPOAdapterUtils   import (
    getLabels, getDefinitions, getComments,
    getChildren, getReferences, getSynonymsAndTypes,
)
import pandas as pd

config_keyword = "hpo"


class HPOAdapter(BaseAdapter):
    """
    Concrete adapter for loading the Human Phenotype Ontology (HPO)
    into the shared EAV DataFrame format.

    Loads the OWL file specified in the adapter configuration via
    owlready2, then runs each HPOAdapterUtils extractor (labels,
    definitions, comments, children, references, synonyms) against
    it and concatenates the results into self.data.
    """

    def __init__(self, config: str = standard_directory):
        super().__init__(config, config_keyword)

    def load(self) -> int:
        """
        Load the HPO OWL file and populate self.data with all
        extracted EAV rows.

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
                    frame = extract(
                        hpo,
                        self.config.id_column,
                        self.config.attribute_column,
                        self.config.value_column,
                        self.config.additional_column,
                    )
                    if frame is not None:
                        frames.append(frame)

                if frames:
                    l.log("Merging data...")
                    self.data = pd.concat(frames, ignore_index=True)
                    l.log("Merging data completed.")

                if self.data is not None:
                    ret = len(self.data)
                    l.log(f"Found {ret} entities/rows in total.")

                    l.log("Removing rows without an ID...")
                    self.data = self.data[
                        self.data[self.config.id_column].notna() &
                        (self.data[self.config.id_column] != '')
                    ]
                    l.log("Removing rows without an ID completed.")
                    ret = len(self.data)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                    l.log("Removing rows with a '#' in the ID...")
                    self.data[self.config.id_column] = self.data[self.config.id_column].astype(str)
                    self.data = self.data[
                        ~self.data[self.config.id_column].str.contains('#', na=False)
                    ]
                    l.log("Removing rows with a '#' in the ID completed.")
                    ret = len(self.data)
                    l.log(f"Reduced to {ret} entities/rows in total.")
                else:
                    l.log("No data found. Is it the correct file?")

                l.log(f"Loading the Human Phenotype Ontology (HPO) from '{input_file}' completed.")
        else:
            l.log("No input file found. Was it set in the configuration file?")

        return ret


if __name__ == "__main__":
    # Quick manual test: load the HPO and write the result to CSV.
    a = HPOAdapter()
    a.load()
    a.to_csv()