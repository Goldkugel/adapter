import sys

# Prevent Python from generating .pyc bytecode files
sys.dont_write_bytecode = True

import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from BaseAdapter        import *
from BaseAdapterUtils   import *
from Logger             import Logger
from SCTAdapterUtils    import *
import pandas           as pd

config_keyword = "sct"

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
        with all extracted EAV rows. Returns the number of rows loaded.
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
                l.log(f"Loading SNOMED CT from {len(self.config.input_files)} files...")

                concepts = None

                files = self.config.input_files.copy()
                for input_file in self.config.input_files:
                    if str(input_file).startswith(conceptPrefix) and concepts is None:
                        files.remove(input_file)
                        input_file = os.path.join(self.config.input_folder, input_file)
                        concepts = getConcepts(readConceptFile(input_file), rf2SourceId)

                frames = []

                for input_file in files:
                    input_file = os.path.join(
                        self.config.input_folder, 
                        input_file
                    )

                    frame = readRF2FileByPath(
                        input_file, 
                        self.config.id_column, 
                        self.config.attribute_column, 
                        self.config.value_column, 
                        self.config.additional_column,
                        self.config.encoding,
                        self.config.separator
                    )
                    if frame is not None:
                        frame = removeNotActiveConcepts(frame, self.config.id_column, concepts)
                        if len(frame.index) > 0:
                            frames.append(frame)

                l.log(f"Loading completed.")

                if len(frames) > 0:
                    l.log("Merging data...")
                    self.data = pd.concat(frames, ignore_index = True)
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
                    self.data = self.data.drop_duplicates(subset=[
                        self.config.id_column, 
                        self.config.attribute_column, 
                        self.config.value_column
                    ]).reset_index(drop = True)
                    l.log("Removing duplicate rows completed.")

                    ret = len(self.data.index)
                    l.log(f"Reduced to {ret} entities/rows in total.")
                else:
                    l.log("No data found. Is it the correct file?")

                l.log(f"Loading SNOMED CT from {len(self.config.input_files)} files completed.")

        else:
            l.log("No input files found. Were they set in the configuration file?")

        return ret

if __name__ == "__main__":
    a = SCTAdapter()
    a.load()
    a.to_csv()