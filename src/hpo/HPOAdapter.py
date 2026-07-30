import sys

# Prevent Python from generating .pyc files (compiled bytecode files)
sys.dont_write_bytecode = True

import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from BaseAdapter        import *
from owlready2          import get_ontology
from Logger             import Logger
import pandas           as pd
import HPOAdapterUtils  as utils
import os

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
        extracted EAV rows. Returns the number of rows loaded.
        """
        ret = 0
        l = Logger()
        
        if len(self.config.input_files) > 0:

            output_file = os.path.join(
                self.config.output_folder, 
                self.config.output_file
            )

            if isFile(output_file) and self.config.skip_if_present:
                l.log("Skipping loading since output file is already present.")
            else:
                l.log("Loading the Human Phenotype Ontology " \
                     f"(HPO) from '{self.config.input_files[0]}'...")
                path = os.path.join(
                    self.config.input_folder, 
                    self.config.input_files[0]
                )
                hpo = get_ontology(path).load()

                extractors = [
                    utils.getLabels,
                    utils.getDefinitions,
                    utils.getComments,
                    utils.getChildren,
                    utils.getReferences,
                    utils.getSynonymsAndTypes,
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

                l.log(f"Loading completed. Merging data...")
                if len(frames) > 0:
                    self.data = pd.concat(frames, ignore_index = True)

                if self.data is not None:
                    ret = len(self.data.index)
                    l.log(f"Data merged. Found {ret} entities/rows in total.")

                    l.log("Removing rows without an ID...")
                    self.data = self.data[(
                        self.data[self.config.id_column].notna()) & (
                        self.data[self.config.id_column] != ''
                    )]
                    l.log("Removing rows without an ID completed.")
                    ret = len(self.data.index)
                    l.log(f"Reduced to {ret} entities/rows in total.")

                    l.log("Removing rows with a '#' in the ID...")
                    self.data = self.data[
                        ~self.data[self.config.id_column].str.contains(
                            '#', 
                            na = False
                        )
                    ]
                    l.log("Removing rows with a '#' in the ID completed.")
                    ret = len(self.data.index)
                    l.log(f"Reduced to {ret} entities/rows in total.")
                else:
                    l.log("No data found. Is it the correct file?")

                l.log("Loading the Human Phenotype Ontology " \
                     f"(HPO) from '{self.config.input_files[0]}' completed.")
        else:
            l.log("No input file found. Was it set in the configuration file?")

        return ret

if __name__ == "__main__":
    a = HPOAdapter()
    a.load()
    a.to_csv()