"""
Utility functions and constants for the SNOMED CT adapter.

Provides RF2 column layouts, file readers, and EAV transformers for
the Concept, Description, TextDefinition, Relationship, and SimpleMap
RF2 release files. All functions are used by SCTAdapter.load().
"""

from __future__ import annotations

from ..BaseAdapterUtils import labelClass, definitionClass, referenceClass, childrenClass, synonymClass
from logger             import Logger
import pandas           as pd
import os

# --- EAV additional-column key ---

referenceOntology               : str = "reference_ontology"

# --- RF2 source column names ---

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

# --- RF2 column layouts ---

# Standard RF2 column layouts. Every RF2 file starts with these five
# columns; Description/TextDefinition and the SimpleMap refset each add
# their own columns after that.
conceptColumns = [
    rf2SourceId,                # ID
    rf2SourceActive,            # Filter: only include if active
    rf2SourceDefinitionStatusId # Additional
]

descriptionColumns = [
    rf2SourceActive,            # Filter: only include if active
    rf2SourceConceptId,         # ID
    rf2SourceTypeId,            # 900000000000003001 = FSN -> label
                                # 900000000000013009 = Synonym -> synonym
                                # 900000000000550004 = Definition -> definition
    rf2SourceTerm,              # Value
    rf2SourceCaseSignificanceId # Additional
]

# TextDefinition files share the exact same column layout as Description
# files — only the content differs (definitions rather than terms/synonyms).
textDefinitionColumns = descriptionColumns

relationshipColumns = [
    rf2SourceActive,            # Filter: only include if active
    rf2SourceSourceId,          # ID
    rf2SourceDestinationId,     # Value, attribute is always "child"
    rf2SourceTypeId,            # Filter: only 116680003 = "is_a"
    rf2SourceCharacteristicTypeId, # Additional
]

simpleMapColumns = [
    rf2SourceActive,                # Filter: only include if active
    rf2SourceRefsetId,              # Additional
    rf2SourceReferencedComponentId, # ID
    rf2SourceMapTarget              # Value, attribute is always "reference"
]

# --- RF2 filename prefixes ---

# Expected filename prefix for each RF2 file type. Used by
# readRF2FileByPath() to determine which reader function — and
# therefore which columns — apply to a given file, based on its name.
conceptPrefix        : str = "sct2_Concept_"
descriptionPrefix    : str = "sct2_Description_"
textDefinitionPrefix : str = "sct2_TextDefinition_"
relationshipPrefix   : str = "sct2_Relationship_"
simpleMapPrefix      : str = "der2_sRefset_SimpleMapFull"

# --- SNOMED CT description type IDs ---

# SNOMED CT description type IDs (values found in the Description /
# TextDefinition typeId column) mapped to the EAV attribute name each
# should produce.
fsnTypeId        : str = "900000000000003001"   # Fully Specified Name
synonymTypeId    : str = "900000000000013009"   # Synonym
definitionTypeId : str = "900000000000550004"   # Definition

# Maps each RF2 description typeId to the EAV attribute name it should
# produce. Any typeId not listed here is dropped during transformation.
_descriptionTypeIdToAttribute = {
    fsnTypeId        : labelClass,       # Fully Specified Name  -> label
    synonymTypeId    : synonymClass,     # Synonym               -> synonym
    definitionTypeId : definitionClass,  # Definition            -> definition
}

# RF2 files are read with dtype=str (to preserve SCTIDs), so the active
# flag is also a string — "1" for active, "0" for inactive.
isActive : str = "1"

# Relationship typeId for the IS-A (subtype) relationship — the only
# relationship type currently converted into the EAV set.
isARelationshipTypeId : str = "116680003"


def _readRF2File(
    path     : str,
    columns  : list,
    encoding : str,
    separator: str
) -> pd.DataFrame:
    """
    Read a single tab-delimited RF2 file into a DataFrame.

    All columns are read as strings to avoid misinterpreting SCTIDs or
    other numeric-looking fields (e.g. losing precision, or reformatting
    into scientific notation).
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
    )
    l.printFileProcessingEnd(path)
    l.log(f"{len(ret)} entities of SNOMED CT extracted.")
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
    SNOMED CT concept to a code in another scheme (e.g. ICD-10).
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
    Return the unique SCTIDs of all active concepts in a raw Concept
    DataFrame (from readConceptFile).

    Used as a reference/filter set — via removeNotActiveConcepts() — to
    restrict rows extracted from other RF2 files to concepts that are
    actually active, not to produce EAV rows in its own right.
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

    Used after each RF2 file is converted to EAV to ensure only rows
    belonging to currently active concepts are retained.
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
    active    = _activeOnly(data)
    attribute = active[rf2SourceTypeId].map(_descriptionTypeIdToAttribute)
    known     = active[attribute.notna()].copy()
    attribute = attribute[attribute.notna()]

    return pd.DataFrame({
        id_column        : known[rf2SourceConceptId].values,
        attribute_column : attribute.values,
        value_column     : known[rf2SourceTerm].values,
        additional_column: known[rf2SourceCaseSignificanceId].map(
            lambda v: {rf2SourceCaseSignificanceId: v}
        ).values,
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

    Only active IS-A relationships are kept. sourceId (the child)
    becomes the id, destinationId (the parent) becomes the value, and
    attribute is fixed to childrenClass.
    """
    active = _activeOnly(data)
    isA    = active[active[rf2SourceTypeId] == isARelationshipTypeId]

    return pd.DataFrame({
        id_column        : isA[rf2SourceSourceId].values,
        attribute_column : [childrenClass] * len(isA),
        value_column     : isA[rf2SourceDestinationId].values,
        additional_column: [{}] * len(isA),
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

    referencedComponentId becomes the id, mapTarget becomes the value,
    attribute is fixed to referenceClass, and refsetId is carried through
    as additional information (needed to identify which target ontology
    the mapping belongs to, e.g. ICD-10, ICD-O).
    """
    active = _activeOnly(data)

    return pd.DataFrame({
        id_column        : active[rf2SourceReferencedComponentId].values,
        attribute_column : [referenceClass] * len(active),
        value_column     : active[rf2SourceMapTarget].values,
        additional_column: active[rf2SourceRefsetId].map(
            lambda v: {referenceOntology: v}
        ).values,
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

    Only active rows whose typeId marks them as a Definition are kept
    (defensive — TextDefinition files are expected to contain only
    Definition-type rows, but this guards against stray FSN/Synonym rows).
    conceptId becomes the id, term becomes the value, attribute is fixed
    to definitionClass, and caseSignificanceId is carried as additional.
    """
    active      = _activeOnly(data)
    definitions = active[active[rf2SourceTypeId] == definitionTypeId].copy()

    return pd.DataFrame({
        id_column        : definitions[rf2SourceConceptId].values,
        attribute_column : [definitionClass] * len(definitions),
        value_column     : definitions[rf2SourceTerm].values,
        additional_column: definitions[rf2SourceCaseSignificanceId].map(
            lambda v: {rf2SourceCaseSignificanceId: v}
        ).values,
    })


# Ordered (prefix, reader/transformer) pairs, checked against a file's
# basename. A more specific prefix must be listed before any shorter
# prefix it could also satisfy; none of the current RF2 prefixes overlap,
# but new file types should be added with that in mind.
_rf2ReadersByPrefix = {
    descriptionPrefix    : readDescriptionFile,
    textDefinitionPrefix : readTextDefinitionFile,
    relationshipPrefix   : readRelationshipFile,
    simpleMapPrefix      : readSimpleMapFile,
}
_rf2TransformersByPrefix = {
    descriptionPrefix    : getDescriptions,
    textDefinitionPrefix : getDefinitions,
    relationshipPrefix   : getChildren,
    simpleMapPrefix      : getReferences,
}


def readRF2FileByPath(
    file_path        : str,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str,
    encoding         : str,
    separator        : str
) -> pd.DataFrame:
    """
    Read a single RF2 file and convert it to EAV rows.

    Chooses the appropriate reader function — and therefore the
    appropriate column layout — based on the file's own name.
    file_path must point directly to the file itself, not to the
    directory containing it. Returns None and logs a warning if the
    filename doesn't start with any of the known RF2 prefixes.
    """
    ret      = None
    l        = Logger()
    filename = os.path.basename(file_path)

    for prefix, reader in _rf2ReadersByPrefix.items():
        if filename.startswith(prefix):
            ret = reader(file_path, encoding, separator)
            ret = _rf2TransformersByPrefix[prefix](
                ret,
                id_column,
                attribute_column,
                value_column,
                additional_column
            )
            break

    if ret is None:
        l.log(f"'{filename}' doesn't match any known RF2 file prefix.")

    return ret