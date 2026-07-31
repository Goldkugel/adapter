import sys

# Prevent Python from generating .pyc bytecode files
sys.dont_write_bytecode = True

from Logger import Logger
from pathlib import Path
import pandas as pd
import os

labelClass                      = "label"
definitionClass                 = "definition"
commentClass                    = "comment"
referenceClass                  = "reference"
childrenClass                   = "child"
synonymClass                    = "synonym"

yes = "Y"
no = "N"

preferredTerm = "PT"
synonymTerm = "SY"
abbreviationTerm = "AB"
preferredNameTerm = "PN"

sourceAbbreviation = "source_abbreviation"

rffConceptUniqueIdentifier: str = "CUI"
rffLanguage: str = "LAT"
rffTermStatus: str = "TS"
rffLexicalUniqueIdentifier: str = "LUI"
rffStringType: str = "STT"
rffStringUniqueIdentifier: str = "SUI"
rffIsPreferred: str = "ISPREF"
rffAtomUniqueIdentifier: str = "AUI"
rffSourceAtomUniqueIdentifier: str = "SAUI"
rffSourceConceptUniqueIdentifier: str = "SCUI"
rffSourceDescriptorUniqueIdentifier: str = "SDUI"
rffSourceAbbreviation: str = "SAB"
rffTermType: str = "TTY"
rffSourceCode: str = "CODE"
rffString: str = "STR"
rffSourceRestrictionLevel: str = "SRL"
rffSuppressibleFlag: str = "SUPPRESS"
rffContentViewFlag: str = "CVF"

rffAttributeUniqueIdentifier: str = "ATUI"
rffSourceAssertedAttributeIdentifier: str = "SATUI"
rffDefinition: str = "DEF"

rffSemanticTypeUniqueIdentifier: str = "TUI"
rffSemanticTypeTreeNumber: str = "STN"
rffSemanticType: str = "STY"

rffConceptUniqueIdentifier1: str = "CUI1"
rffAtomUniqueIdentifier1: str = "AUI1"
rffSourceOrAtomIdentifierType1: str = "STYPE1"

rffRelationship: str = "REL"

rffConceptUniqueIdentifier2: str = "CUI2"
rffAtomUniqueIdentifier2: str = "AUI2"
rffSourceOrAtomIdentifierType2: str = "STYPE2"

rffRelationshipAttribute: str = "RELA"

rffRelationshipUniqueIdentifier: str = "RUI"
rffSourceAssertedRelationshipIdentifier: str = "SRUI"

rffSourceLevel: str = "SL"
rffRelationshipGroup: str = "RG"
rffDirectionalityFlag: str = "DIR"

mrconsoColumns = [
    rffConceptUniqueIdentifier,
    rffLanguage,
    rffTermStatus,
    rffLexicalUniqueIdentifier,
    rffStringType,
    rffStringUniqueIdentifier,
    rffIsPreferred,
    rffAtomUniqueIdentifier,
    rffSourceAtomUniqueIdentifier,
    rffSourceConceptUniqueIdentifier,
    rffSourceDescriptorUniqueIdentifier,
    rffSourceAbbreviation,
    rffTermType,
    rffSourceCode,
    rffString,
    rffSourceRestrictionLevel,
    rffSuppressibleFlag,
    rffContentViewFlag,
]

mrdefColumns = [
    rffConceptUniqueIdentifier,
    rffAtomUniqueIdentifier,
    rffAttributeUniqueIdentifier,
    rffSourceAssertedAttributeIdentifier,
    rffSourceAbbreviation,
    rffDefinition,
    rffSuppressibleFlag,
    rffContentViewFlag,
]

mrstyColumns = [
    rffConceptUniqueIdentifier,
    rffSemanticTypeUniqueIdentifier,
    rffSemanticTypeTreeNumber,
    rffSemanticType,
    rffAttributeUniqueIdentifier,
    rffContentViewFlag,
]

mrrelColumns = [
    rffConceptUniqueIdentifier1,
    rffAtomUniqueIdentifier1,
    rffSourceOrAtomIdentifierType1,
    rffRelationship,
    rffConceptUniqueIdentifier2,
    rffAtomUniqueIdentifier2,
    rffSourceOrAtomIdentifierType2,
    rffRelationshipAttribute,
    rffRelationshipUniqueIdentifier,
    rffSourceAssertedRelationshipIdentifier,
    rffSourceAbbreviation,
    rffSourceLevel,
    rffRelationshipGroup,
    rffDirectionalityFlag,
    rffSuppressibleFlag,
    rffContentViewFlag,
]

def _readRRFFile(path: str | Path, columns: list[str]) -> pd.DataFrame:
    """
    Read a UMLS RRF file.

    Parameters
    ----------
    path
        Path to the RRF file.
    columns
        Column names according to the UMLS documentation.

    Returns
    -------
    pandas.DataFrame
    """
    ret = None
    l = Logger()
    l.printFileProcessingStart(path)
    ret = pd.read_csv(
        path,
        sep         = "|",
        header      = None,
        names       = columns + ["_"],
        dtype       = str,
        encoding    = "utf-8",
        low_memory  = False,
    )
    l.printFileProcessingEnd(path)
    l.log(f"{len(ret.index)} entities of UMLS extracted.")

    return ret.drop(columns = "_", errors = "ignore")

def readMRCONSOFile(path: str) -> pd.DataFrame:
    """Read MRCONSO.RRF."""
    return _readRRFFile(path, mrconsoColumns)

def readMRDEFFile(path: str) -> pd.DataFrame:
    """Read MRDEF.RRF."""
    return _readRRFFile(path, mrdefColumns)

def readMRSTYFile(path: str) -> pd.DataFrame:
    """Read MRSTY.RRF."""
    return _readRRFFile(path, mrstyColumns)

def getConcepts(
    data: pd.DataFrame,
    id_column: str,
    attribute_column: str,
    value_column: str,
    additional_column: str,
) -> pd.DataFrame:
    """
    Convert MRCONSO into an Entity-Attribute-Value (EAV) table.

    Generated attributes:
        - label
        - synonym
        - reference
    """

    rows = []

    for _, row in data.iterrows():

        #
        # Preferred label / synonym
        #
        attribute = ""
        if row[rffTermType] == preferredTerm or row[rffTermType] == preferredNameTerm:
            attribute = labelClass
        else:
            if row[rffTermType] == synonymTerm or row[rffTermType] == abbreviationTerm:
                attribute = synonymClass

        if len(attribute) > 0 and pd.notna(row[rffString]) and len(str(row[rffString])) > 0: 
            rows.append({
                id_column               : row[rffConceptUniqueIdentifier],
                attribute_column        : attribute,
                value_column            : str(row[rffString]),
                additional_column       : {sourceAbbreviation : str(row[rffSourceAbbreviation])},
            })

        #
        # Source Concept Unique Identifier
        #
        if pd.notna(row[rffSourceCode]) and len(str(row[rffSourceCode])) > 0:
            rows.append({
                id_column               : row[rffConceptUniqueIdentifier],
                attribute_column        : referenceClass,
                value_column            : row[rffSourceCode],
                additional_column       : {sourceAbbreviation : str(row[rffSourceAbbreviation])},
            })

    return (
        pd.DataFrame(rows)
        .drop_duplicates()
        .reset_index(drop = True)
    )

def getDefinitions(
    data: pd.DataFrame,
    id_column: str,
    attribute_column: str,
    value_column: str,
    additional_column: str,
) -> pd.DataFrame:
    """
    Convert MRDEF into an Entity-Attribute-Value (EAV) table.

    Generated attributes:
        - definition
    """

    rows = []

    for _, row in data.iterrows():

        definition = row[rffDefinition]

        #
        # Ignore empty definitions
        #
        if pd.isna(definition) or len(str(definition).strip()) == 0:
            continue

        rows.append({
            id_column               : row[rffConceptUniqueIdentifier],
            attribute_column        : definitionClass,
            value_column            : str(definition),
            additional_column: {
                sourceAbbreviation: str(row[rffSourceAbbreviation])
            },
        })

    return (
        pd.DataFrame(rows)
        .drop_duplicates()
        .reset_index(drop=True)
    )

conceptPrefix        = "MRCONSO"
definitionPrefix     = "MRDEF"

_rffReadersByPrefix = {
    conceptPrefix: readMRCONSOFile,
    definitionPrefix : readMRDEFFile
}
_rffTransformersByPrefix = {
    conceptPrefix: getConcepts,
    definitionPrefix: getDefinitions, 
}

def readRFFFileByPath(
    file_path           : str,
    id_column           : str,
    attribute_column    : str,
    value_column        : str,
    additional_column   : str
) -> pd.DataFrame:
    """
    Read a single RFF file, choosing the appropriate reader function -
    and therefore the appropriate column layout - based on the file's
    own name. `file_path` must point directly to the file itself, not
    to the directory containing it. Raises ValueError if the filename
    doesn't start with any of the known RFF prefixes.
    """
    ret = None
    l = Logger()
    filename = os.path.basename(file_path)

    for key in _rffReadersByPrefix.keys():
        if filename.startswith(key) and ret is None:
            ret = _rffReadersByPrefix[key](file_path)
            ret = _rffTransformersByPrefix[key](
                ret, 
                id_column, 
                attribute_column, 
                value_column, 
                additional_column
            )
            
    if ret is None:
        l.log(f"'{filename}' doesn't match any known RFF file prefix.")

    return ret