"""
Utility functions and constants for the HPO adapter.

Provides SPARQL-based extractors for labels, definitions, comments,
children, references, and synonyms from an OWL-format HPO ontology,
as well as helper functions for normalising concept IDs and synonym
class/type strings.
"""

from __future__ import annotations

from logger             import Logger
from ..BaseAdapterUtils import labelClass, definitionClass, commentClass, referenceClass, childrenClass, synonymClass
from owlready2          import Ontology
from rdflib             import Namespace, RDFS, XSD
import pandas           as pd

# --- Synonym class constants ---

semanticClass           : str = "semantic_class"
exactSynonymClass       : str = "exact"
relatedSynonymClass     : str = "related"
broadSynonymClass       : str = "broad"
narrowSynonymClass      : str = "narrow"

# --- Synonym type constants ---

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

# --- OWL source property names (used for string matching) ---

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

# --- Common ontology namespaces used for RDF / OWL processing ---

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
    SPARQL filters excluding a deprecated or obsolete ?variable. HPO marks
    terms either with owl:deprecated true or with oboInOwl:is_obsolete,
    whose value is compared as a string since it is not always typed.
    """
    return (
        f"FILTER NOT EXISTS {{ ?{variable} owl:deprecated true }}\n"
        f"FILTER NOT EXISTS {{ ?{variable} oboInOwl:is_obsolete ?obsolete . "
        f"FILTER(str(?obsolete) = \"true\") }}\n"
    )


def getSynonymTypeFromString(string: str = "") -> str:
    """
    Determine the synonym *type* based on markers found in the source string.

    The string is the IRI of an oboInOwl:hasSynonymType value (e.g.
    'http://purl.obolibrary.org/obo/hp#layperson'). The markers are
    checked in the order below and the first match is returned; a string
    without a known marker, including "" for a synonym without a typed
    axiom, gives the direct type. None gives "".
    """
    ret = ""

    if string is not None:
        # Layperson-friendly synonym
        if owlSourceSynonymTypeLayperson in string:
            ret = laypersonSynonymType

        # Abbreviation synonym
        elif owlSourceSynonymTypeAbbreviation in string:
            ret = abbreviationSynonymType

        # Obsolete synonym
        elif owlSourceSynonymTypeObsolete in string:
            ret = obsoleteSynonymType

        # UK spelling variant
        elif owlSourceSynonymTypeUKSpelling in string:
            ret = ukSpellingSynonymType

        # Plural form variant
        elif owlSourceSynonymTypePlural in string:
            ret = pluralFormSynonymType

        # Allelic requirement synonym
        elif owlSourceSynonymTypeAllelic in string:
            ret = allelicRequirementSynonymType

        # Direct synonym (no or an unknown type)
        else:
            ret = directSynonymType

    return ret


def getSynonymClassFromString(string: str = "") -> str:
    """
    Determine the synonym *class* (exact, related, broad, narrow)
    based on ontology source markers in the string, i.e. the IRI of the
    oboInOwl synonym property. Returns "" if no marker matches.
    """
    ret = ""

    if string is not None:
        # Exact synonym
        if owlSourceExactSynonym in string:
            ret = exactSynonymClass

        # Related synonym
        elif owlSourceRelatedSynonym in string:
            ret = relatedSynonymClass

        # Broad synonym
        elif owlSourceBroadSynonym in string:
            ret = broadSynonymClass

        # Narrow synonym
        elif owlSourceNarrowSynonym in string:
            ret = narrowSynonymClass

    return ret


def getConceptIDFromString(string: str = "") -> str:
    """
    Extract a concept identifier from a URI or path-like string.

    Example:
        'http://purl.obolibrary.org/obo/HP_0000118'
        -> 'HP:0000118'

    Strings without a "/" (e.g. the IDs rdflib gives blank nodes) and
    None return "", so their rows are later removed by BaseAdapter.load()
    as rows without an ID. Hash IRIs keep their "#" (e.g.
    'oboInOwl#hasDbXref') and are removed by HPOAdapter._clean().
    """
    ret = ""

    if string is not None and "/" in string:
        # Extract the last path segment
        ret = string.split("/")[-1]

        # Convert underscore-based IDs to colon-based IDs
        # (e.g. HP_0000118 -> HP:0000118)
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
    Extract all synonyms for HPO concepts, including:
    - Direct synonym annotations
    - Axiom-annotated synonyms with explicit synonym types

    Returns a normalized DataFrame suitable for downstream processing.
    """
    ret = None
    l = Logger()

    if hpo is not None:
        l.log("Get synonyms and types of the Human Phenotype Ontology (HPO)...")

        # Convert Owlready2 ontology into an RDFLib graph
        g = hpo.world.as_rdflib_graph()

        # In the RDF serialisation, every synonym is stored as a direct
        # triple; synonyms with extra annotations additionally have an
        # owl:Axiom that repeats source/property/target. The synonyms
        # come from the direct triples (so each is found once, not once
        # more via its axiom), and their types from the axioms.
        #
        # Both are fetched with separate queries and joined in Python.
        # Joining them inside SPARQL (an OPTIONAL axiom pattern) makes
        # rdflib re-evaluate the axiom pattern for every synonym and
        # scan all axioms each time, which takes days on the full HPO.

        # Direct synonyms of active (not deprecated or obsolete) concepts.
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

        # Synonym types (e.g. layperson, abbreviation) from the axioms.
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

        # Collect the types of each (concept, class, synonym) triple.
        # A synonym can have more than one type.
        types = {}
        for row in g.query(typeQuery, initNs=_INIT_NS):
            key = (str(row.hpoID), str(row.synclass), str(row.synonym))
            types.setdefault(key, []).append(str(row.syntype))

        # Accumulate query results into Python lists
        ids        = []
        values     = []
        additional = []

        for row in g.query(synonymQuery, initNs=_INIT_NS):
            key = (str(row.hpoID), str(row.synclass), str(row.synonym))

            # One row per synonym type; a synonym without a typed axiom
            # gets one row with the direct type ("" maps to it).
            for syntype in types.get(key, [""]):
                # Normalize HPO ID format
                ids.append(getConceptIDFromString(str(row.hpoID)))

                # Raw synonym literal
                values.append(row.synonym)

                # Map RDF property and type to internal class and type
                additional.append({
                    semanticClass : getSynonymClassFromString(str(row.synclass)),
                    sourceType    : getSynonymTypeFromString(syntype),
                })

        # Build a standardized DataFrame representation
        ret = pd.DataFrame({
            id_column         : ids,
            attribute_column  : [synonymClass] * len(ids),
            value_column      : values,
            additional_column : additional
        })

        l.log(f"{len(ret)} entities of the Human Phenotype Ontology (HPO) extracted.")

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
    Run `query` on the RDF view of `hpo` and turn every result row into
    one EAV row with the given attribute and an empty additional dict.

    `toIdAndValue` maps a result row to its (id, value) pair. Returns None
    if `hpo` is None. `description` names what is extracted in the log
    messages (e.g. "labels").
    """
    ret = None
    l = Logger()

    if hpo is not None:
        l.log(f"Get {description} of the Human Phenotype Ontology (HPO)...")

        g = hpo.world.as_rdflib_graph()

        ids    = []
        values = []

        for row in g.query(query, initNs=_INIT_NS):
            concept_id, value = toIdAndValue(row)
            ids.append(concept_id)
            values.append(value)

        # Build a standardized DataFrame representation
        ret = pd.DataFrame({
            id_column        : ids,
            attribute_column : [attribute] * len(ids),
            value_column     : values,
            additional_column: [{} for _ in range(len(ids))]
        })

        l.log(f"{len(ret)} entities of the Human Phenotype Ontology (HPO) extracted.")

    return ret


def getComments(
    hpo              : Ontology = None,
    id_column        : str = "",
    attribute_column : str = "",
    value_column     : str = "",
    additional_column: str = ""
) -> pd.DataFrame | None:
    """
    Extract rdfs:comment annotations for HPO concepts.

    Includes:
    - Direct comment annotations
    - Axiom-based comment annotations
    """
    # SPARQL query retrieves comments from both direct and axiom-based
    # sources; DISTINCT collapses a comment found by both branches
    query = """
        SELECT DISTINCT ?hpoID ?comment WHERE {
    """ + _activeFilter("hpoID") + """
            {
                # Direct comment annotation
                ?hpoID rdfs:comment ?comment .
            }
            UNION
            {
                # Axiom-based comment annotation
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
    # Retrieve definitions from direct and axiom-based annotations;
    # DISTINCT collapses a definition found by both branches
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
    # Simple query for labels. This also matches labelled entities
    # that are not HPO concepts. Those with a hash IRI (e.g.
    # oboInOwl#hasDbXref) are removed by HPOAdapter._clean(); those
    # with an OBO IRI (e.g. obo:IAO_0000115, "definition") are kept.
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

    Each row represents:
        parent HPO ID -> child HPO ID
    i.e. the parent is the id and the child the value (attribute
    childrenClass), as in the SNOMED CT adapter.
    """
    # Retrieve all subclass relationships. Superclasses that are
    # anonymous restrictions (blank nodes) yield an empty parent ID
    # and are removed by BaseAdapter.load() as rows without an ID.
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

    Only hasDbXref annotations made directly on the concept are used.
    DbXrefs on owl:Axiom nodes annotate other annotations (e.g. the
    sources of a definition or synonym) and are not concept references.
    """
    # Retrieve cross-references annotated directly on the concept
    # (isIRI excludes the blank owl:Axiom nodes, which carry
    # hasDbXref too)
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
