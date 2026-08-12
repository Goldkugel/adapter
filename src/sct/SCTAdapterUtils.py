import sys

# Prevent Python from generating .pyc bytecode files
sys.dont_write_bytecode = True

import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from BaseAdapterUtils   import labelClass, definitionClass, referenceClass, childrenClass, synonymClass
from logger             import Logger
import pandas           as pd

referenceOntology               = "reference_ontology"

rf2SourceId                     = "id"
rf2SourceEffectiveTime          = "effectiveTime"
rf2SourceActive                 = "active"
rf2SourceModuleId               = "moduleId"
rf2SourceSourceId               = "sourceId"
rf2SourceDestinationId          = "destinationId"
rf2SourceRelationshipGroup      = "relationshipGroup"
rf2SourceTypeId                 = "typeId"
rf2SourceCharacteristicTypeId   = "characteristicTypeId"
rf2SourceModifierId             = "modifierId"
rf2SourceRefsetId               = "refsetId"
rf2SourceReferencedComponentId  = "referencedComponentId"
rf2SourceMapTarget              = "mapTarget"
rf2SourceDefinitionStatusId     = "definitionStatusId"
rf2SourceTerm                   = "term"
rf2SourceCaseSignificanceId     = "caseSignificanceId"
rf2SourceConceptId              = "conceptId"
rf2SourceLanguageCode           = "languageCode"

# Standard RF2 column layouts. Every RF2 file starts with these five
# columns; Description/TextDefinition and the SimpleMap refset each add
# their own columns after that.
conceptColumns = [ # This should be used as reference set of SCT concept included
    rf2SourceId, # ID 
    rf2SourceActive, # Filter: only include if active
    rf2SourceDefinitionStatusId # Additional
]

descriptionColumns = [
    rf2SourceActive,  # Filter: only include if active
    rf2SourceConceptId, # ID
    rf2SourceTypeId, # 900000000000003001 = "Fully Specified Name" -> "attribute" is "label", 900000000000013009 = "Synonym" -> "attribute" is "synonym", 900000000000550004 = "Definition" -> "attribute" is "definition"
    rf2SourceTerm, # Value
    rf2SourceCaseSignificanceId # Additional
]

# TextDefinition files share the exact same column layout as Description
# files - only the content differs (definitions rather than terms/synonyms).
textDefinitionColumns = descriptionColumns

relationshipColumns = [
    rf2SourceActive,  # Filter: only include if active
    rf2SourceSourceId, # ID
    rf2SourceDestinationId, # Value, "attribute" is always "child"
    #rf2SourceRelationshipGroup, 
    rf2SourceTypeId, # Filter: only 116680003 = "is_a"
    rf2SourceCharacteristicTypeId, # Additional
    #rf2SourceModifierId
]

simpleMapColumns = [
    rf2SourceActive,  # Filter: only include if active
    rf2SourceRefsetId, # Additional
    rf2SourceReferencedComponentId,  # ID
    rf2SourceMapTarget # Value, "attribute" is always "reference"
]

# Expected filename prefix for each RF2 file type. Used by
# readRF2FileByPath() to determine which reader function - and
# therefore which columns - apply to a given file, based on its name.
conceptPrefix        = "sct2_Concept_"
descriptionPrefix    = "sct2_Description_"
textDefinitionPrefix = "sct2_TextDefinition_"
relationshipPrefix   = "sct2_Relationship_"
simpleMapPrefix      = "der2_sRefset_SimpleMapFull"

# SNOMED CT description type IDs (values found in the Description /
# TextDefinition typeId column) mapped to the EAV attribute name each
# should produce.
fsnTypeId           = "900000000000003001"   # Fully Specified Name
synonymTypeId       = "900000000000013009"   # Synonym
definitionTypeId    = "900000000000550004"   # Definition

_descriptionTypeIdToAttribute = {
    fsnTypeId:          labelClass,
    synonymTypeId:      synonymClass,
    definitionTypeId:   definitionClass,
}

isActive = "1"

# Relationship typeId for the IS-A (subtype) relationship - the only
# relationship type currently converted into the EAV set.
isARelationshipTypeId = "116680003"

def _readRF2File(
    path                : str, 
    columns             : list,
    encoding            : str, 
    separator           : str
) -> pd.DataFrame:
    """
    Read a single tab-delimited RF2 file into a DataFrame. All columns are 
    read as strings to avoid misinterpreting SCTIDs or other numeric-looking 
    fields (e.g. losing precision, or reformatting into scientific notation).
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
    l.log(f"{len(ret.index)} entities of SNOMED CT extracted.")
    return ret
 
 
def readConceptFile(
    path                : str,
    encoding            : str, 
    separator           : str
) -> pd.DataFrame:
    """
    Read the Concept file: one row per SNOMED CT concept, with its
    active/inactive status and definition status.
    """
    return _readRF2File(path, conceptColumns, encoding, separator)
 
 
def readDescriptionFile(
    path: str,
    encoding            : str, 
    separator           : str
) -> pd.DataFrame:
    """
    Read the Description file: fully specified names (FSNs) and
    synonyms for each concept, one row per description.
    """
    return _readRF2File(path, descriptionColumns, encoding, separator)
 
 
def readRelationshipFile(
    path                : str,
    encoding            : str, 
    separator           : str
) -> pd.DataFrame:
    """
    Read the Relationship file: one row per relationship between two
    concepts (e.g. IS-A / subtype relationships, attribute relationships).
    """
    return _readRF2File(path, relationshipColumns, encoding, separator)
 
 
def readTextDefinitionFile(
    path                : str,
    encoding            : str, 
    separator           : str
) -> pd.DataFrame:
    """
    Read the TextDefinition file: free-text definitions for concepts,
    one row per definition (same column layout as Description).
    """
    return _readRF2File(path, textDefinitionColumns, encoding, separator)
 
 
def readSimpleMapFile(
    path                : str,
    encoding            : str, 
    separator           : str
) -> pd.DataFrame:
    """
    Read the Simple Map reference set file: one row per mapping from a
    SNOMED CT concept to a code in another scheme (e.g. ICD-10).
    """
    return _readRF2File(path, simpleMapColumns, encoding, separator)

def _activeOnly(
    data                : pd.DataFrame
) -> pd.DataFrame:
    """Filter a raw RF2 DataFrame down to active (active == '1') rows."""
    return data[data[rf2SourceActive] == isActive] 
 
def getConcepts(
    data                : pd.DataFrame,
    id_column           : str
) -> list:
    """
    Return the unique SCTIDs of all active concepts in a raw Concept
    DataFrame (from readConceptFile). Used as a reference/filter set -
    via removeNotActiveConcepts() - to restrict rows extracted from
    other RF2 files to concepts that are actually active, not to
    produce EAV rows in its own right.
    """
    active = _activeOnly(data)
    return sorted(set(active[id_column].tolist()))

def removeNotActiveConcepts(
    data                : pd.DataFrame,
    id_column           : str,
    conceptIDs          : list
) -> pd.DataFrame:
    return data[data[id_column].isin(conceptIDs)].copy().reset_index(drop = True)
 
def getDescriptions(
    data                : pd.DataFrame,
    id_column           : str,
    attribute_column    : str,
    value_column        : str,
    additional_column   : str
) -> pd.DataFrame:
    """
    Convert a raw Description or TextDefinition DataFrame (from
    readDescriptionFile / readTextDefinitionFile - both share the same
    column layout) into EAV rows. `typeId` determines the attribute
    name ("label" for FSN, "synonym" for Synonym, "definition" for
    Definition); rows with any other typeId are dropped, since they
    don't map to a known attribute. `term` becomes the value, and
    `caseSignificanceId` is carried through as additional information.
    """
    active = _activeOnly(data)
    attribute = active[rf2SourceTypeId].map(_descriptionTypeIdToAttribute)
    known = active[attribute.notna()]
    attribute = attribute[attribute.notna()]
    return pd.DataFrame({
        id_column           : known[rf2SourceConceptId],
        attribute_column    : attribute,
        value_column        : known[rf2SourceTerm],
        additional_column   : [{rf2SourceCaseSignificanceId : row[rf2SourceCaseSignificanceId]} for _, row in known.iterrows()],
    })
 
def getChildren(
    data                : pd.DataFrame,
    id_column           : str,
    attribute_column    : str,
    value_column        : str,
    additional_column   : str
) -> pd.DataFrame:
    """
    Convert a raw Relationship DataFrame (from readRelationshipFile)
    into EAV rows, keeping only active IS-A relationships. `sourceId`
    (the child) becomes the id, `destinationId` (the parent) becomes
    the value, and `attribute` is fixed to "child".
    """
    active = _activeOnly(data)
    isA = active[active[rf2SourceTypeId] == isARelationshipTypeId]
    return pd.DataFrame({
        id_column           : isA[rf2SourceSourceId],
        attribute_column    : [childrenClass] * len(isA.index),
        value_column        : isA[rf2SourceDestinationId],
        additional_column   : [{} for _ in range(len(isA.index))],
    })
 
def getReferences(
    data                : pd.DataFrame,
    id_column           : str,
    attribute_column    : str,
    value_column        : str,
    additional_column   : str
) -> pd.DataFrame:
    """
    Convert a raw Simple Map DataFrame (from readSimpleMapFile) into
    EAV rows. `referencedComponentId` becomes the id, `mapTarget`
    becomes the value, `attribute` is fixed to "reference", and
    `refsetId` is carried through as additional information (needed to
    tell which target ontology - ICD-10, ICD-O, etc. - the mapping
    belongs to; see the earlier discussion on resolving refsetId).
    """
    active = _activeOnly(data)
    return pd.DataFrame({
        id_column           : active[rf2SourceReferencedComponentId],
        attribute_column    : [referenceClass] * len(active.index),
        value_column        : active[rf2SourceMapTarget],
        additional_column   : [{referenceOntology : row[rf2SourceRefsetId]} for _, row in active.iterrows()],
    })

def getDefinitions(
    data                : pd.DataFrame,
    id_column           : str,
    attribute_column    : str,
    value_column        : str,
    additional_column   : str
) -> pd.DataFrame:
    """
    Convert a raw TextDefinition DataFrame (from readTextDefinitionFile)
    into EAV rows, keeping only active rows whose typeId marks them as
    a Definition (defensive - TextDefinition files are expected to
    contain only Definition-type rows, but this guards against a
    stray FSN/Synonym row ending up in the file). `conceptId` becomes
    the id, `term` becomes the value, `attribute` is fixed to
    "definition", and `caseSignificanceId` is carried through as
    additional information.
    """
    active = _activeOnly(data)
    definitions = active[active[rf2SourceTypeId] == definitionTypeId]
    return pd.DataFrame({
        id_column           : definitions[rf2SourceConceptId],
        attribute_column    : [definitionClass] * len(definitions.index),
        value_column        : definitions[rf2SourceTerm],
        additional_column   : [{rf2SourceCaseSignificanceId : row[rf2SourceCaseSignificanceId]} for _, row in definitions.iterrows()],
    })


# Ordered (prefix, reader) pairs, checked in order against a file's
# basename. Order matters only in that a more specific prefix must be
# listed before any shorter prefix it could also satisfy; none of the
# current RF2 prefixes overlap, but new file types should be added with
# that in mind.
_rf2ReadersByPrefix = {
    descriptionPrefix:     readDescriptionFile,
    textDefinitionPrefix:  readTextDefinitionFile,
    relationshipPrefix:    readRelationshipFile,
    simpleMapPrefix:       readSimpleMapFile,
}
_rf2TransformersByPrefix = {
    descriptionPrefix:     getDescriptions,
    textDefinitionPrefix:  getDefinitions,
    relationshipPrefix:    getChildren,
    simpleMapPrefix:       getReferences,
}

def readRF2FileByPath(
    file_path           : str,
    id_column           : str,
    attribute_column    : str,
    value_column        : str,
    additional_column   : str,
    encoding            : str, 
    separator           : str
) -> pd.DataFrame:
    """
    Read a single RF2 file, choosing the appropriate reader function -
    and therefore the appropriate column layout - based on the file's
    own name. `file_path` must point directly to the file itself, not
    to the directory containing it. Raises ValueError if the filename
    doesn't start with any of the known RF2 prefixes.
    """
    ret = None
    l = Logger()
    filename = os.path.basename(file_path)

    for key in _rf2ReadersByPrefix.keys():
        if filename.startswith(key) and ret is None:
            ret = _rf2ReadersByPrefix[key](file_path, encoding, separator)
            ret = _rf2TransformersByPrefix[key](
                ret, 
                id_column, 
                attribute_column, 
                value_column, 
                additional_column
            )
            
    if ret is None:
        l.log(f"'{filename}' doesn't match any known RF2 file prefix.")

    return ret