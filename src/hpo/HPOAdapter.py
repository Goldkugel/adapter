import sys

# Prevent Python from generating .pyc files (compiled bytecode files)
sys.dont_write_bytecode = True

from BaseAdapter        import *
from owlready2          import get_ontology
from Logger             import Logger
import pandas           as pd
import HPOAdapterUtils  as utils
import os

class HPOAdapter(BaseAdapter):
    """
    Concrete adapter for loading the Human Phenotype Ontology (HPO)
    into the shared EAV DataFrame format.

    Loads the OWL file specified in the adapter configuration via
    owlready2, then runs each HPOAdapterUtils extractor (labels,
    definitions, comments, children, references, synonyms) against
    it and concatenates the results into self.data.
    """

    def load(self) -> int:
        """
        Load the HPO OWL file and populate self.data with all
        extracted EAV rows. Returns the number of rows loaded.
        """
        ret = 0
        l = Logger()
        l.log(f"Loading the Human Phenotype Ontology (HPO) from '{self.config.input_files}'")

        if len(self.config.input_files) > 0:
            path = os.path.join(self.config.input_folder, self.config.input_files[0])
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

            if len(frames) > 0:
                self.data = pd.concat(frames, ignore_index = True)
                
            if self.data is not None:
                ret = len(self.data.index)

        return ret