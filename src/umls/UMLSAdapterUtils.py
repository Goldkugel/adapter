import sys

# Prevent Python from generating .pyc bytecode files
sys.dont_write_bytecode = True

from BaseAdapterUtils   import labelClass, definitionClass, referenceClass, synonymClass
from logger             import Logger
from pathlib            import Path
import pandas           as pd
import os

yes = "Y"
no = "N"

preferredTerm = "PT"
synonymTerm = "SY"
abbreviationTerm = "AB"
preferredNameTerm = "PN"

englishLanguage = "ENG"

sourceAbbreviation = "source_abbreviation"

rrfConceptUniqueIdentifier: str = "CUI"
rrfLanguage: str = "LAT"
rrfTermStatus: str = "TS"
rrfLexicalUniqueIdentifier: str = "LUI"
rrfStringType: str = "STT"
rrfStringUniqueIdentifier: str = "SUI"
rrfIsPreferred: str = "ISPREF"
rrfAtomUniqueIdentifier: str = "AUI"
rrfSourceAtomUniqueIdentifier: str = "SAUI"
rrfSourceConceptUniqueIdentifier: str = "SCUI"
rrfSourceDescriptorUniqueIdentifier: str = "SDUI"
rrfSourceAbbreviation: str = "SAB"
rrfTermType: str = "TTY"
rrfSourceCode: str = "CODE"
rrfString: str = "STR"
rrfSourceRestrictionLevel: str = "SRL"
rrfSuppressibleFlag: str = "SUPPRESS"
rrfContentViewFlag: str = "CVF"

rrfAttributeUniqueIdentifier: str = "ATUI"
rrfSourceAssertedAttributeIdentifier: str = "SATUI"
rrfDefinition: str = "DEF"

rrfSemanticTypeUniqueIdentifier: str = "TUI"
rrfSemanticTypeTreeNumber: str = "STN"
rrfSemanticType: str = "STY"

rrfConceptUniqueIdentifier1: str = "CUI1"
rrfAtomUniqueIdentifier1: str = "AUI1"
rrfSourceOrAtomIdentifierType1: str = "STYPE1"

rrfRelationship: str = "REL"

rrfConceptUniqueIdentifier2: str = "CUI2"
rrfAtomUniqueIdentifier2: str = "AUI2"
rrfSourceOrAtomIdentifierType2: str = "STYPE2"

rrfRelationshipAttribute: str = "RELA"

rrfRelationshipUniqueIdentifier: str = "RUI"
rrfSourceAssertedRelationshipIdentifier: str = "SRUI"

rrfSourceLevel: str = "SL"
rrfRelationshipGroup: str = "RG"
rrfDirectionalityFlag: str = "DIR"

mrconsoColumns = [
    rrfConceptUniqueIdentifier,
    rrfLanguage,
    rrfTermStatus,
    rrfLexicalUniqueIdentifier,
    rrfStringType,
    rrfStringUniqueIdentifier,
    rrfIsPreferred,
    rrfAtomUniqueIdentifier,
    rrfSourceAtomUniqueIdentifier,
    rrfSourceConceptUniqueIdentifier,
    rrfSourceDescriptorUniqueIdentifier,
    rrfSourceAbbreviation,
    rrfTermType,
    rrfSourceCode,
    rrfString,
    rrfSourceRestrictionLevel,
    rrfSuppressibleFlag,
    rrfContentViewFlag,
]

mrdefColumns = [
    rrfConceptUniqueIdentifier,
    rrfAtomUniqueIdentifier,
    rrfAttributeUniqueIdentifier,
    rrfSourceAssertedAttributeIdentifier,
    rrfSourceAbbreviation,
    rrfDefinition,
    rrfSuppressibleFlag,
    rrfContentViewFlag,
]

mrstyColumns = [
    rrfConceptUniqueIdentifier,
    rrfSemanticTypeUniqueIdentifier,
    rrfSemanticTypeTreeNumber,
    rrfSemanticType,
    rrfAttributeUniqueIdentifier,
    rrfContentViewFlag,
]

mrrelColumns = [
    rrfConceptUniqueIdentifier1,
    rrfAtomUniqueIdentifier1,
    rrfSourceOrAtomIdentifierType1,
    rrfRelationship,
    rrfConceptUniqueIdentifier2,
    rrfAtomUniqueIdentifier2,
    rrfSourceOrAtomIdentifierType2,
    rrfRelationshipAttribute,
    rrfRelationshipUniqueIdentifier,
    rrfSourceAssertedRelationshipIdentifier,
    rrfSourceAbbreviation,
    rrfSourceLevel,
    rrfRelationshipGroup,
    rrfDirectionalityFlag,
    rrfSuppressibleFlag,
    rrfContentViewFlag,
]

def _readRRFFile(
    path: str, 
    columns: list[str], 
    encoding: str, 
    separator: str
) -> pd.DataFrame:
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
        sep         = separator,
        header      = None,
        names       = columns + ["_"],
        dtype       = str,
        encoding    = encoding,
        low_memory  = False,
    )
    l.printFileProcessingEnd(path)
    l.log(f"{len(ret.index)} entities of UMLS extracted.")

    return ret.drop(columns = "_", errors = "ignore")

def readMRCONSOFile(
    path: str, 
    encoding: str, 
    separator: str
) -> pd.DataFrame:
    """Read MRCONSO.RRF."""
    return _readRRFFile(path, mrconsoColumns, encoding, separator)

def readMRDEFFile(
    path: str, 
    encoding: str, 
    separator: str
) -> pd.DataFrame:
    """Read MRDEF.RRF."""
    return _readRRFFile(path, mrdefColumns, encoding, separator)

def readMRSTYFile(
    path: str, 
    encoding: str, 
    separator: str
) -> pd.DataFrame:
    """Read MRSTY.RRF."""
    return _readRRFFile(path, mrstyColumns, encoding, separator)

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
    data = data[(
        data[rrfLanguage] == englishLanguage) & (
        data[rrfSuppressibleFlag] == no
    )].reset_index(drop = True)
    rows = []
    l = Logger()
    l.log(f"Transforming {len(data.index)} rows in EAV schema...")
    for _, row in data.iterrows():

        #
        # Preferred label / synonym
        #
        attribute = ""
        if row[rrfTermType] == preferredTerm or row[rrfTermType] == preferredNameTerm:
            attribute = labelClass
        else:
            if row[rrfTermType] == synonymTerm or row[rrfTermType] == abbreviationTerm:
                attribute = synonymClass

        if len(attribute) > 0 and pd.notna(row[rrfString]) and len(str(row[rrfString])) > 0: 
            rows.append({
                id_column               : row[rrfConceptUniqueIdentifier],
                attribute_column        : attribute,
                value_column            : str(row[rrfString]),
                additional_column       : {sourceAbbreviation : str(row[rrfSourceAbbreviation])},
            })

        #
        # Source Concept Unique Identifier
        #
        if pd.notna(row[rrfSourceCode]) and len(str(row[rrfSourceCode])) > 0:
            rows.append({
                id_column               : row[rrfConceptUniqueIdentifier],
                attribute_column        : referenceClass,
                value_column            : row[rrfSourceCode],
                additional_column       : {sourceAbbreviation : str(row[rrfSourceAbbreviation])},
            })

    l.log(f"Transforming {len(data.index)} rows in EAV schema completed.")
    l.log(f"Removing duplicated rows...")
    data = (pd.DataFrame(rows)
        .drop_duplicates(subset=[id_column, attribute_column, value_column])
        .reset_index(drop = True))
    l.log(f"Removing duplicated rows completed. {len(data.index)} rows left.")
    return data

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

    data = data[data[rrfSuppressibleFlag] == no].reset_index(drop = True)
    rows = []
    l = Logger()
    l.log(f"Transforming {len(data.index)} rows in EAV schema...")
    rows = []

    for _, row in data.iterrows():

        definition = row[rrfDefinition]

        #
        # Ignore empty definitions
        #
        if pd.isna(definition) or len(str(definition).strip()) == 0:
            continue

        rows.append({
            id_column               : row[rrfConceptUniqueIdentifier],
            attribute_column        : definitionClass,
            value_column            : str(definition),
            additional_column: {
                sourceAbbreviation: str(row[rrfSourceAbbreviation])
            },
        })

    l.log(f"Transforming {len(data.index)} rows in EAV schema completed.")
    l.log(f"Removing duplicated rows...")
    data = (pd.DataFrame(rows)
        .drop_duplicates(subset=[id_column, attribute_column, value_column])
        .reset_index(drop = True))
    l.log(f"Removing duplicated rows completed. {len(data.index)} rows left.")
    return data

conceptPrefix        = "MRCONSO"
definitionPrefix     = "MRDEF"

_rrfReadersByPrefix = {
    conceptPrefix: readMRCONSOFile,
    definitionPrefix : readMRDEFFile
}
_rrfTransformersByPrefix = {
    conceptPrefix: getConcepts,
    definitionPrefix: getDefinitions, 
}

def readRFFFileByPath(
    file_path           : str,
    id_column           : str,
    attribute_column    : str,
    value_column        : str,
    additional_column   : str,
    encoding            : str, 
    separator           : str
) -> pd.DataFrame:
    """
    Read a single RFF file, choosing the appropriate reader function -
    and therefore the appropriate column layout - based on the file's
    own name. `file_path` must point directly to the file itself, not
    to the directory containing it. Raises ValueError if the filename
    doesn't start with any of the known RRF prefixes.
    """
    ret = None
    l = Logger()
    filename = os.path.basename(file_path)

    for key in _rrfReadersByPrefix.keys():
        if filename.startswith(key) and ret is None:
            ret = _rrfReadersByPrefix[key](file_path, encoding, separator)
            ret = _rrfTransformersByPrefix[key](
                ret, 
                id_column, 
                attribute_column, 
                value_column, 
                additional_column
            )
            
    if ret is None:
        l.log(f"'{filename}' doesn't match any known RRF file prefix.")

    return ret