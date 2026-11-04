"""
Utility functions and constants for the SNOMED CT adapter.

RF2 column layouts, file readers and EAV transformers for the Concept,
Description, TextDefinition, Relationship and SimpleMap release files.
"""

from __future__ import annotations

from ..BaseAdapterUtils import (
    labelClass, definitionClass, referenceClass, childrenClass, synonymClass,
    additionalFrom, readFileByPrefix,
)
from logger             import Logger
import pandas           as pd
import csv

# Key of the refsetId in the additional dict of reference rows.
referenceOntology               : str = "reference_ontology"

rf2SourceId                     : str = "id"
rf2SourceEffectiveTime          : str = "effectiveTime"
rf2SourceActive                 : str = "active"
rf2SourceModuleId               : str = "moduleId"
rf2SourceSourceId               : str = "sourceId"
rf2SourceDestinationId          : str = "destinationId"
rf2SourceRelationshipGroup      : str = "relationshipGroup"
rf2SourceTypeId                 : str = "typeId"
rf2SourceCharacteristicTypeId   : str = "characteristicTypeId"
rf2SourceModifierId             : str = "modifierId"
rf2SourceRefsetId               : str = "refsetId"
rf2SourceReferencedComponentId  : str = "referencedComponentId"
rf2SourceMapTarget              : str = "mapTarget"
rf2SourceDefinitionStatusId     : str = "definitionStatusId"
rf2SourceTerm                   : str = "term"
rf2SourceCaseSignificanceId     : str = "caseSignificanceId"
rf2SourceConceptId              : str = "conceptId"
rf2SourceLanguageCode           : str = "languageCode"

# Columns read (usecols) per RF2 file type. Each includes id and
# effectiveTime, so _readRF2File() can reduce Full releases to the latest
# version per component. "ID" / "Value" / "Additional" name the EAV column
# a source column ends up in.
conceptColumns = [
    rf2SourceId,                # ID (SCTID of the concept)
    rf2SourceEffectiveTime,     # Keep only the latest version per id
    rf2SourceActive,            # Filter: only include if active
    rf2SourceDefinitionStatusId # Read, but not used (no EAV rows)
]

descriptionColumns = [
    rf2SourceId,                # Description ID (not the concept ID)
    rf2SourceEffectiveTime,     # Keep only the latest version per id
    rf2SourceActive,            # Filter: only include if active
    rf2SourceConceptId,         # ID (concept the description belongs to)
    rf2SourceTypeId,            # 900000000000003001 = FSN -> label
                                # 900000000000013009 = Synonym -> synonym
                                # 900000000000550004 = Definition -> definition
    rf2SourceTerm,              # Value
    rf2SourceCaseSignificanceId # Additional
]

textDefinitionColumns = descriptionColumns

relationshipColumns = [
    rf2SourceId,                # Relationship ID
    rf2SourceEffectiveTime,     # Keep only the latest version per id
    rf2SourceActive,            # Filter: only include if active
    rf2SourceSourceId,          # ID
    rf2SourceDestinationId,     # Value, attribute is always "child"
    rf2SourceTypeId,            # Filter: only 116680003 = "is_a"
    rf2SourceCharacteristicTypeId, # Read, but not used
]

simpleMapColumns = [
    rf2SourceId,                    # Refset member ID (UUID)
    rf2SourceEffectiveTime,         # Keep only the latest version per id
    rf2SourceActive,                # Filter: only include if active
    rf2SourceRefsetId,              # Additional
    rf2SourceReferencedComponentId, # ID
    rf2SourceMapTarget              # Value, attribute is always "reference"
]

# Filename prefixes selecting the reader of a file. The trailing "_" in
# relationshipPrefix excludes sct2_StatedRelationship_ and
# sct2_RelationshipConcreteValues_, which are not processed.
conceptPrefix        : str = "sct2_Concept_"
descriptionPrefix    : str = "sct2_Description_"
textDefinitionPrefix : str = "sct2_TextDefinition_"
relationshipPrefix   : str = "sct2_Relationship_"
simpleMapPrefix      : str = "der2_sRefset_SimpleMap"

# Description typeIds (Description / TextDefinition files).
fsnTypeId        : str = "900000000000003001"   # Fully Specified Name
synonymTypeId    : str = "900000000000013009"   # Synonym
definitionTypeId : str = "900000000000550004"   # Definition

# typeIds not listed here are dropped.
_descriptionTypeIdToAttribute = {
    fsnTypeId        : labelClass,
    synonymTypeId    : synonymClass,
    definitionTypeId : definitionClass,
}

# RF2 files are read with dtype=str, so the active flag is a string.
isActive : str = "1"

# IS-A, the only relationship type converted to EAV rows.
isARelationshipTypeId : str = "116680003"


def _readRF2File(
    path     : str,
    columns  : list,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read a single RF2 file into a DataFrame, keeping only the latest
    version of each component. All columns are strings, so SCTIDs keep
    their precision, and empty fields become "".
    """
    l = Logger()
    l.printFileProcessingStart(path)

    ret = pd.read_csv(
        path,
        sep             = separator,
        dtype           = str,
        keep_default_na = False,
        encoding        = encoding,
        usecols         = columns,
        quoting         = csv.QUOTE_NONE,  # RF2 has no quoting
    )

    # Full releases have one row per effectiveTime per component; keeping
    # the latest makes a later inactivated component count as inactive.
    # effectiveTime is YYYYMMDD, so string order is chronological.
    if rf2SourceEffectiveTime in ret.columns and rf2SourceId in ret.columns:
        ret = ret.sort_values(rf2SourceEffectiveTime, ascending=False) \
            .drop_duplicates(subset=[rf2SourceId], keep="first")

    l.log(f"{len(ret)} entities of SNOMED CT extracted.")
    l.printFileProcessingEnd(path)
    return ret


def readConceptFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read the Concept file: one row per SNOMED CT concept, with its
    active/inactive status and definition status.
    """
    return _readRF2File(path, conceptColumns, encoding, separator)


def readDescriptionFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read the Description file: fully specified names (FSNs) and
    synonyms for each concept, one row per description.
    """
    return _readRF2File(path, descriptionColumns, encoding, separator)


def readRelationshipFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read the Relationship file: one row per relationship between two
    concepts (e.g. IS-A / subtype relationships, attribute relationships).
    """
    return _readRF2File(path, relationshipColumns, encoding, separator)


def readTextDefinitionFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read the TextDefinition file: free-text definitions for concepts,
    one row per definition (same column layout as Description).
    """
    return _readRF2File(path, textDefinitionColumns, encoding, separator)


def readSimpleMapFile(
    path     : str,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read the Simple Map reference set file: one row per mapping from a
    SNOMED CT concept to a code in another scheme (e.g. ICD-O).
    """
    return _readRF2File(path, simpleMapColumns, encoding, separator)


def _activeOnly(data: pd.DataFrame) -> pd.DataFrame:
    """Filter a raw RF2 DataFrame down to active (active == '1') rows."""
    return data[data[rf2SourceActive] == isActive]


def getConcepts(
    data     : pd.DataFrame,
    id_column: str
) -> list:
    """
    Return the sorted unique SCTIDs of the active concepts in a raw Concept
    DataFrame, the filter set for removeNotActiveConcepts().
    """
    active = _activeOnly(data)
    return sorted(set(active[id_column].tolist()))


def removeNotActiveConcepts(
    data      : pd.DataFrame,
    id_column : str,
    conceptIDs: list
) -> pd.DataFrame:
    """
    Filter an EAV DataFrame to rows whose ID appears in conceptIDs.

    Only the ID column is checked: for child rows that is the parent; the
    child in the value column is not checked.
    """
    return data[data[id_column].isin(conceptIDs)].copy().reset_index(drop=True)


def getDescriptions(
    data             : pd.DataFrame,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str
) -> pd.DataFrame:
    """
    Convert a raw Description or TextDefinition DataFrame into EAV rows.

    typeId determines the attribute name (label for FSN, synonym for
    Synonym, definition for Definition); rows with any other typeId are
    dropped. term becomes the value, and caseSignificanceId is carried
    through as additional information.
    """
    # Unknown typeIds map to NaN and are dropped from both, keeping them
    # aligned.
    active    = _activeOnly(data)
    attribute = active[rf2SourceTypeId].map(_descriptionTypeIdToAttribute)
    known     = active[attribute.notna()].copy()
    attribute = attribute[attribute.notna()]

    return pd.DataFrame({
        id_column        : known[rf2SourceConceptId].values,
        attribute_column : attribute.values,
        value_column     : known[rf2SourceTerm].values,
        additional_column: additionalFrom(known[rf2SourceCaseSignificanceId], rf2SourceCaseSignificanceId),
    })


def getChildren(
    data             : pd.DataFrame,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str
) -> pd.DataFrame:
    """
    Convert a raw Relationship DataFrame into EAV rows.

    Only active IS-A relationships are kept. destinationId (the parent)
    becomes the id and sourceId (the child) the value, as in the HPO
    adapter.
    """
    active = _activeOnly(data)
    isA    = active[active[rf2SourceTypeId] == isARelationshipTypeId]

    return pd.DataFrame({
        id_column        : isA[rf2SourceDestinationId].values,
        attribute_column : [childrenClass] * len(isA),
        value_column     : isA[rf2SourceSourceId].values,
        additional_column: [{} for _ in range(len(isA))],
    })


def getReferences(
    data             : pd.DataFrame,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str
) -> pd.DataFrame:
    """
    Convert a raw Simple Map DataFrame into EAV rows.

    referencedComponentId becomes the id and mapTarget the value; refsetId
    goes to the additional dict, as it identifies the target scheme (e.g.
    ICD-O).
    """
    active = _activeOnly(data)

    return pd.DataFrame({
        id_column        : active[rf2SourceReferencedComponentId].values,
        attribute_column : [referenceClass] * len(active),
        value_column     : active[rf2SourceMapTarget].values,
        additional_column: additionalFrom(active[rf2SourceRefsetId], referenceOntology),
    })


def getDefinitions(
    data             : pd.DataFrame,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str
) -> pd.DataFrame:
    """
    Convert a raw TextDefinition DataFrame into EAV rows.

    Keeps only active Definition-type rows (guarding against stray
    FSN/Synonym rows) and converts them like getDescriptions(), whose
    layout TextDefinition files share.
    """
    definitions = data[data[rf2SourceTypeId] == definitionTypeId]
    return getDescriptions(
        definitions, id_column, attribute_column, value_column, additional_column
    )


# Checked in order against a file's basename; the first match wins, so a
# new prefix must precede any shorter prefix it also matches.
_rf2HandlersByPrefix = {
    descriptionPrefix    : (readDescriptionFile,    getDescriptions),
    textDefinitionPrefix : (readTextDefinitionFile, getDefinitions),
    relationshipPrefix   : (readRelationshipFile,   getChildren),
    simpleMapPrefix      : (readSimpleMapFile,      getReferences),
}


def readRF2FileByPath(
    file_path        : str,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str,
    encoding         : str,
    separator        : str
) -> pd.DataFrame | None:
    """
    Read a single RF2 file and convert it to EAV rows.

    The reader is chosen by the file's own name, so file_path must point
    to the file, not its directory. Returns None (and logs) if no known
    RF2 prefix matches.
    """
    return readFileByPrefix(
        file_path, _rf2HandlersByPrefix, "RF2",
        id_column, attribute_column, value_column, additional_column,
        encoding, separator,
    )
