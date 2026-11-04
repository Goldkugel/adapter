"""
Utility functions and constants for the HPO adapter.

SPARQL-based extractors for labels, definitions, comments, children,
references and synonyms of an OWL-format HPO, and helpers normalising
concept IDs and synonym class/type strings.
"""

from __future__ import annotations

from logger             import Logger
from ..BaseAdapterUtils import labelClass, definitionClass, commentClass, referenceClass, childrenClass, synonymClass
from owlready2          import Ontology
from rdflib             import Namespace, RDFS, XSD
import pandas           as pd

# Synonym classes (key semanticClass of the additional dict).
semanticClass           : str = "semantic_class"
exactSynonymClass       : str = "exact"
relatedSynonymClass     : str = "related"
broadSynonymClass       : str = "broad"
narrowSynonymClass      : str = "narrow"

# Synonym types (key sourceType of the additional dict).
sourceType                    : str = "source_type"
expertSynonymType             : str = "expert"
laypersonSynonymType          : str = "layperson"
abbreviationSynonymType       : str = "abbreviation"
obsoleteSynonymType           : str = "obsolete"
pluralFormSynonymType         : str = "plural"
ukSpellingSynonymType         : str = "uk"
allelicRequirementSynonymType : str = "allelic"

# Synonym defined directly in the OWL Class section, rather than via an Axiom.
directSynonymType             : str = "direct"

# Markers matched against the OWL property and synonym type IRIs.
owlSourceExactSynonym    = "hasExactSynonym"
owlSourceRelatedSynonym  = "hasRelatedSynonym"
owlSourceBroadSynonym    = "hasBroadSynonym"
owlSourceNarrowSynonym   = "hasNarrowSynonym"

owlSourceSynonymTypeLayperson    = "layperson"
owlSourceSynonymTypeAbbreviation = "abbreviation"
owlSourceSynonymTypeObsolete     = "obsolete_synonym"
owlSourceSynonymTypePlural       = "plural_form"
owlSourceSynonymTypeUKSpelling   = "uk_spelling"
owlSourceSynonymTypeAllelic      = "allelic_requirement"

OBO      = Namespace("http://purl.obolibrary.org/obo/")
OBOINOWL = Namespace("http://www.geneontology.org/formats/oboInOwl#")
OWL      = Namespace("http://www.w3.org/2002/07/owl#")
RDF      = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

# Shared namespace bindings passed to every SPARQL query.
_INIT_NS = {
    "rdf"      : RDF,
    "rdfs"     : RDFS,
    "owl"      : OWL,
    "obo"      : OBO,
    "oboInOwl" : OBOINOWL,
    "xsd"      : XSD,
}


def _activeFilter(variable: str) -> str:
    """
    SPARQL filters excluding a deprecated or obsolete ?variable. HPO uses
    owl:deprecated or oboInOwl:is_obsolete; the latter is compared as a
    string since it is not always typed.
    """
    return (
        f"FILTER NOT EXISTS {{ ?{variable} owl:deprecated true }}\n"
        f"FILTER NOT EXISTS {{ ?{variable} oboInOwl:is_obsolete ?obsolete . "
        f"FILTER(str(?obsolete) = \"true\") }}\n"
    )


# Synonym type marker -> synonym type, checked in this order; the first
# marker found in the hasSynonymType IRI wins.
_synonymTypesByMarker = (
    (owlSourceSynonymTypeLayperson,    laypersonSynonymType),
    (owlSourceSynonymTypeAbbreviation, abbreviationSynonymType),
    (owlSourceSynonymTypeObsolete,     obsoleteSynonymType),
    (owlSourceSynonymTypeUKSpelling,   ukSpellingSynonymType),
    (owlSourceSynonymTypePlural,       pluralFormSynonymType),
    (owlSourceSynonymTypeAllelic,      allelicRequirementSynonymType),
)

# Synonym property marker -> synonym class, checked in this order.
_synonymClassesByMarker = (
    (owlSourceExactSynonym,   exactSynonymClass),
    (owlSourceRelatedSynonym, relatedSynonymClass),
    (owlSourceBroadSynonym,   broadSynonymClass),
    (owlSourceNarrowSynonym,  narrowSynonymClass),
)


def getSynonymTypeFromString(string: str = "") -> str:
    """
    Map an oboInOwl:hasSynonymType IRI (e.g. '.../obo/hp#layperson') to a
    synonym type. The first marker of _synonymTypesByMarker found wins;
    no known marker (including "" for an untyped synonym) gives the direct
    type, None gives "".
    """
    if string is None:
        return ""

    for marker, result in _synonymTypesByMarker:
        if marker in string:
            return result

    return directSynonymType


def getSynonymClassFromString(string: str = "") -> str:
    """
    Map the IRI of an oboInOwl synonym property to the synonym class
    (exact, related, broad, narrow). Returns "" if no marker matches or
    the string is None.
    """
    if string is None:
        return ""

    for marker, result in _synonymClassesByMarker:
        if marker in string:
            return result

    return ""


def getConceptIDFromString(string: str = "") -> str:
    """
    Extract a concept identifier from a URI or path-like string.

    Example:
        'http://purl.obolibrary.org/obo/HP_0000118'
        -> 'HP:0000118'

    Strings without a "/" (e.g. rdflib blank node IDs) and None give "",
    so load() drops their rows. Hash IRIs keep their "#" (e.g.
    'oboInOwl#hasDbXref') and are removed by HPOAdapter._clean().
    """
    ret = ""

    if string is not None and "/" in string:
        ret = string.split("/")[-1]
        if "_" in ret:
            ret = ret.replace("_", ":")

    return ret


def getSynonymsAndTypes(
    hpo              : Ontology = None,
    id_column        : str = "",
    attribute_column : str = "",
    value_column     : str = "",
    additional_column: str = ""
) -> pd.DataFrame | None:
    """
    Extract the synonyms of active HPO concepts as EAV rows, with their
    synonym class and type in the additional column.
    """
    ret = None
    l = Logger()

    if hpo is not None:
        l.log("Getting the synonyms and types of the Human Phenotype Ontology (HPO)...")

        g = hpo.world.as_rdflib_graph()

        # Every synonym is a direct triple; annotated ones also have an
        # owl:Axiom repeating it. Synonyms come from the triples (found once
        # each), types from the axioms. They are joined in Python: an
        # OPTIONAL join in SPARQL makes rdflib take days on the full HPO.
        synonymQuery = """
        SELECT DISTINCT ?hpoID ?synonym ?synclass WHERE
        {
            VALUES ?synclass {
                oboInOwl:hasExactSynonym
                oboInOwl:hasBroadSynonym
                oboInOwl:hasNarrowSynonym
                oboInOwl:hasRelatedSynonym
            }
            ?hpoID ?synclass ?synonym .
        """ + _activeFilter("hpoID") + """
        }
        """

        # Starting from hasSynonymType keeps this to the typed axioms.
        typeQuery = """
        SELECT DISTINCT ?hpoID ?synonym ?synclass ?syntype WHERE
        {
            ?axiom oboInOwl:hasSynonymType ?syntype .
            ?axiom owl:annotatedSource ?hpoID .
            ?axiom owl:annotatedProperty ?synclass .
            ?axiom owl:annotatedTarget ?synonym .
        }
        """

        # A synonym can have more than one type.
        types = {}
        for row in g.query(typeQuery, initNs=_INIT_NS):
            key = (str(row.hpoID), str(row.synclass), str(row.synonym))
            types.setdefault(key, []).append(str(row.syntype))

        ids        = []
        values     = []
        additional = []

        for row in g.query(synonymQuery, initNs=_INIT_NS):
            key = (str(row.hpoID), str(row.synclass), str(row.synonym))

            # One row per type (load() merges them); "" gives the direct type.
            for syntype in types.get(key, [""]):
                ids.append(getConceptIDFromString(str(row.hpoID)))
                values.append(row.synonym)
                additional.append({
                    semanticClass : getSynonymClassFromString(str(row.synclass)),
                    sourceType    : getSynonymTypeFromString(syntype),
                })

        ret = pd.DataFrame({
            id_column         : ids,
            attribute_column  : [synonymClass] * len(ids),
            value_column      : values,
            additional_column : additional
        })

        l.log(f"{len(ret)} entities of the Human Phenotype Ontology (HPO) extracted.")
        l.log("Getting the synonyms and types of the Human Phenotype Ontology (HPO) completed.")

    return ret


def _extract(
    hpo              : Ontology,
    description      : str,
    query            : str,
    attribute        : str,
    toIdAndValue,
    id_column        : str,
    attribute_column : str,
    value_column     : str,
    additional_column: str
) -> pd.DataFrame | None:
    """
    Run `query` on `hpo` and turn every result row into an EAV row with
    `attribute` and an empty additional dict. `toIdAndValue` maps a result
    row to (id, value); `description` names it in the logs. None if `hpo`
    is None.
    """
    ret = None
    l = Logger()

    if hpo is not None:
        l.log(f"Getting the {description} of the Human Phenotype Ontology (HPO)...")

        g = hpo.world.as_rdflib_graph()

        ids    = []
        values = []

        for row in g.query(query, initNs=_INIT_NS):
            concept_id, value = toIdAndValue(row)
            ids.append(concept_id)
            values.append(value)

        ret = pd.DataFrame({
            id_column        : ids,
            attribute_column : [attribute] * len(ids),
            value_column     : values,
            additional_column: [{} for _ in range(len(ids))]
        })

        l.log(f"{len(ret)} entities of the Human Phenotype Ontology (HPO) extracted.")
        l.log(f"Getting the {description} of the Human Phenotype Ontology (HPO) completed.")

    return ret


def getComments(
    hpo              : Ontology = None,
    id_column        : str = "",
    attribute_column : str = "",
    value_column     : str = "",
    additional_column: str = ""
) -> pd.DataFrame | None:
    """
    Extract the rdfs:comment annotations (direct and axiom-based) of HPO
    concepts.
    """
    # DISTINCT collapses a comment found by both branches.
    query = """
        SELECT DISTINCT ?hpoID ?comment WHERE {
    """ + _activeFilter("hpoID") + """
            {
                ?hpoID rdfs:comment ?comment .
            }
            UNION
            {
                ?axiom rdf:type owl:Axiom .
                ?axiom owl:annotatedSource ?hpoID .
                ?axiom owl:annotatedProperty rdfs:comment .
                ?axiom owl:annotatedTarget ?comment .
            }
        }
    """
    return _extract(
        hpo, "comments", query, commentClass,
        lambda row: (getConceptIDFromString(str(row.hpoID)), row.comment),
        id_column, attribute_column, value_column, additional_column,
    )


def getDefinitions(
    hpo              : Ontology = None,
    id_column        : str = "",
    attribute_column : str = "",
    value_column     : str = "",
    additional_column: str = ""
) -> pd.DataFrame | None:
    """
    Extract textual definitions for HPO concepts
    (obo:IAO_0000115 annotations).
    """
    # Direct and axiom-based; DISTINCT collapses one found by both.
    query = """
        SELECT DISTINCT ?hpoID ?definition WHERE {
    """ + _activeFilter("hpoID") + """
            {
                ?hpoID obo:IAO_0000115 ?definition .
            }
            UNION
            {
                ?axiom rdf:type owl:Axiom .
                ?axiom owl:annotatedProperty obo:IAO_0000115 .
                ?axiom owl:annotatedTarget ?definition .
                ?axiom owl:annotatedSource ?hpoID .
            }
        }
    """
    return _extract(
        hpo, "definitions", query, definitionClass,
        lambda row: (getConceptIDFromString(str(row.hpoID)), row.definition),
        id_column, attribute_column, value_column, additional_column,
    )


def getLabels(
    hpo              : Ontology = None,
    id_column        : str = "",
    attribute_column : str = "",
    value_column     : str = "",
    additional_column: str = ""
) -> pd.DataFrame | None:
    """
    Extract rdfs:label annotations for HPO concepts.
    """
    # Also matches labelled non-concepts: hash IRIs (e.g.
    # oboInOwl#hasDbXref) are removed by HPOAdapter._clean(), OBO IRIs
    # (e.g. obo:IAO_0000115, "definition") are kept.
    query = """
        SELECT ?hpoID ?label WHERE {
    """ + _activeFilter("hpoID") + """
            ?hpoID rdfs:label ?label .
        }
    """
    return _extract(
        hpo, "labels", query, labelClass,
        lambda row: (getConceptIDFromString(str(row.hpoID)), row.label),
        id_column, attribute_column, value_column, additional_column,
    )


def getChildren(
    hpo              : Ontology = None,
    id_column        : str = "",
    attribute_column : str = "",
    value_column     : str = "",
    additional_column: str = ""
) -> pd.DataFrame | None:
    """
    Extract parent–child (subClassOf) relationships from the ontology.

    The parent is the id and the child the value, as in the SNOMED CT
    adapter.
    """
    # Anonymous superclasses (blank nodes) give an empty parent ID and are
    # dropped by load().
    query = """
        SELECT ?child ?parent WHERE {
    """ + _activeFilter("child") + _activeFilter("parent") + """
            ?child rdfs:subClassOf ?parent .
        }
    """
    return _extract(
        hpo, "children of concepts", query, childrenClass,
        lambda row: (
            getConceptIDFromString(str(row.parent)),
            getConceptIDFromString(str(row.child)),
        ),
        id_column, attribute_column, value_column, additional_column,
    )


def getReferences(
    hpo              : Ontology = None,
    id_column        : str = "",
    attribute_column : str = "",
    value_column     : str = "",
    additional_column: str = ""
) -> pd.DataFrame | None:
    """
    Extract database cross-references (DbXrefs) for HPO concepts.

    Only hasDbXref annotations made directly on the concept are used;
    those on owl:Axiom nodes give the sources of other annotations.
    """
    # isIRI excludes the blank owl:Axiom nodes.
    query = """
        SELECT DISTINCT ?hpoID ?xref WHERE {
            FILTER(isIRI(?hpoID))
    """ + _activeFilter("hpoID") + """
            ?hpoID oboInOwl:hasDbXref ?xref .
        }
    """
    return _extract(
        hpo, "references", query, referenceClass,
        lambda row: (getConceptIDFromString(str(row.hpoID)), row.xref),
        id_column, attribute_column, value_column, additional_column,
    )
