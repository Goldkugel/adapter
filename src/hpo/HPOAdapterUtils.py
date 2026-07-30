import sys

# Prevent Python from generating .pyc bytecode files
sys.dont_write_bytecode = True

import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from Logger         import Logger
from owlready2      import *
from rdflib         import Namespace, RDF
import pandas       as pd
import os

labelClass                      = "label"
definitionClass                 = "definition"
commentClass                    = "comment"
referenceClass                  = "reference"
childrenClass                   = "child"
synonymClass                    = "synonym"

semanticClass                   = "semantic_class"
exactSynonymClass               = "exact"
relatedSynonymClass             = "related"
broadSynonymClass               = "broad"
narrowSynonymClass              = "narrow"

sourceType                      = "source_type"
expertSynonymType               = "expert"
laypersonSynonymType            = "layperson"
abbreviationSynonymType         = "abbreviation"
obsoleteSynonymType             = "obsolete"
pluralFormSynonymType           = "plural"
ukSpellingSynonymType           = "uk"
allelicRequirementSynonymType   = "allelic"

# In OWL Class Section, rather than in Axiom Section.
directSynonymType               = "direct"

owlSourceExactSynonym                   = "hasExactSynonym"
owlSourceRelatedSynonym                 = "hasRelatedSynonym"
owlSourceBoradSynonym                   = "hasBroadSynonym"
owlSourceNarrowSynonym                  = "hasNarrowSynonym"

owlSourceSynonymTypeLayperson           = "layperson"
owlSourceSynonymTypeAbbreviation        = "abbreviation"
owlSourceSynonymTypeObsolete            = "obsolete_synonym"
owlSourceSynonymTypePlural              = "plural_form"
owlSourceSynonymTypeUKSpelling          = "uk_spelling"
owlSourceSynonymTypeAllelic             = "allelic_requirement"

# Common ontology namespaces used for RDF / OWL processing
OBO      = Namespace("http://purl.obolibrary.org/obo/")
OBOINOWL = Namespace("http://www.geneontology.org/formats/oboInOwl#")
OWL      = Namespace("http://www.w3.org/2002/07/owl#")
RDF      = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

def getSynonymTypeFromString(string: str = "") -> str:
    """
    Determine the synonym *type* based on markers found in the source string.

    The first matching type found will be returned.
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

        # Direct synonym (no qualifier)
        else:
            ret = directSynonymType

    return ret

def getSynonymClassFromString(string: str = "") -> str:
    """
    Determine the synonym *class* (exact, related, broad, narrow)
    based on ontology source markers in the string.
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
        elif owlSourceBoradSynonym in string:
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
    """
    ret = ""

    if string is not None and "/" in string:
        # Extract the last path segment
        parts = string.split("/")
        ret = parts[len(parts) - 1]

        # Convert underscore-based IDs to colon-based IDs
        # (e.g. HP_0000118 -> HP:0000118)
        if "_" in ret:
            ret = ret.replace("_", ":")

    return ret

def getSynonymsAndTypes(
    hpo                 : Ontology = None, 
    id_column           : str = "", 
    attribute_column    : str = "", 
    value_column        : str = "", 
    additional_column   : str = ""
) -> pd.DataFrame:
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

        # SPARQL query retrieves:
        # - Concept ID
        # - Synonym text
        # - Synonym class (exact, broad, narrow, related)
        # - Optional synonym type (e.g. layperson, abbreviation)
        query = """
        SELECT ?hpoID ?synonym ?synclass ?syntype WHERE 
        {
            {
                # Direct class annotations without axiom metadata
                ?hpoID ?synclass ?synonym .
                FILTER(?synclass IN (
                    oboInOwl:hasExactSynonym,
                    oboInOwl:hasBroadSynonym,
                    oboInOwl:hasNarrowSynonym,
                    oboInOwl:hasRelatedSynonym
                ))
                # Direct annotations have no synonym type metadata
                BIND(\"""" + directSynonymType + """\" AS ?syntype)
            }
            UNION
            {
                # Synonyms defined via OWL axioms (allow extra annotations)
                ?axiom rdf:type owl:Axiom .
                ?axiom owl:annotatedSource ?hpoID .
                ?axiom owl:annotatedProperty ?synclass .
                ?axiom owl:annotatedTarget ?synonym .
                FILTER(?synclass IN (
                    oboInOwl:hasExactSynonym,
                    oboInOwl:hasBroadSynonym,
                    oboInOwl:hasNarrowSynonym,
                    oboInOwl:hasRelatedSynonym
                ))
                # Optional synonym type (e.g. layperson, obsolete)
                OPTIONAL { ?axiom oboInOwl:hasSynonymType ?syntype }
            }
        }
        """

        # Execute query with required namespace bindings
        result = g.query(
            query,
            initNs={
                "rdf": RDF,
                "owl": OWL,
                "obo": OBO,
                "oboInOwl": OBOINOWL,
            }
        )
        
        # Accumulate query results into Python lists
        ids        = []
        attributes = []
        additional = []

        for row in result:
            # Normalize HPO ID format
            ids.append(getConceptIDFromString(str(row.hpoID)))

            # Raw synonym literal
            attributes.append(row.synonym)

            # Map RDF property to internal synonym class
            a = {}
            a[semanticClass] = getSynonymClassFromString(str(row.synclass))
            a[sourceType]    = getSynonymTypeFromString(str(row.syntype))
            additional.append(a)

        # Build a standardized DataFrame representation
        ret = pd.DataFrame({
            id_column         : ids,
            attribute_column  : [synonymClass] * len(ids),
            value_column      : attributes,
            additional_column : additional
        })

        l.log(f"{len(ret.index)} entities of the Human Phenotype Ontology (HPO) extracted.")

    return ret

def getComments(
    hpo                 : Ontology = None, 
    id_column           : str = "", 
    attribute_column    : str = "", 
    value_column        : str = "", 
    additional_column   : str = ""
) -> pd.DataFrame:
    """
    Extract rdfs:comment annotations for HPO concepts.

    Includes:
    - Direct comment annotations
    - Axiom-based comment annotations
    """
    ret = None
    l = Logger()

    if hpo is not None:
        l.log("Get comments of the Human Phenotype Ontology (HPO)...")

        g = hpo.world.as_rdflib_graph()

        # SPARQL query retrieves comments from both direct and axiom-based sources
        query = """
            SELECT DISTINCT ?hpoID ?comment WHERE {
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
                    ?axiom owl:annotatedAnnotatedTarget ?comment .
                }
            }
        """

        result = g.query(
            query,
            initNs={
                "rdf": RDF,
                "owl": OWL,
                "obo": OBO,
                "oboInOwl": OBOINOWL,
            }
        )

        ids    = []
        values = []

        for row in result:
            ids.append(getConceptIDFromString(str(row.hpoID)))
            values.append(row.comment)

        # Normalize comments into standard DataFrame format
        ret = pd.DataFrame({
            id_column           : ids, 
            attribute_column    : [commentClass] * len(ids), 
            value_column        : values, 
            additional_column   : [{} for _ in range(len(ids))]
        })

        l.log(f"{len(ret.index)} entities of the Human Phenotype Ontology (HPO) extracted.")

    return ret

def getDefinitions(
    hpo                 : Ontology = None, 
    id_column           : str = "", 
    attribute_column    : str = "", 
    value_column        : str = "", 
    additional_column   : str = ""
) -> pd.DataFrame:
    """
    Extract textual definitions for HPO concepts
    (obo:IAO_0000115 annotations).
    """
    ret = None
    l = Logger()

    if hpo is not None:
        l.log("Get definitions of the Human Phenotype Ontology (HPO)...")

        g = hpo.world.as_rdflib_graph()

        # Retrieve definitions from direct and axiom-based annotations
        query = """
            SELECT DISTINCT ?hpoID ?definition WHERE {
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

        result = g.query(
            query,
            initNs={
                "rdf": RDF,
                "owl": OWL,
                "obo": OBO,
                "oboInOwl": OBOINOWL,
            }
        )

        ids    = []
        values = []

        for row in result:
            ids.append(getConceptIDFromString(str(row.hpoID)))
            values.append(row.definition)

        # Normalize comments into standard DataFrame format
        ret = pd.DataFrame({
            id_column           : ids, 
            attribute_column    : [definitionClass] * len(ids), 
            value_column        : values, 
            additional_column   : [{} for _ in range(len(ids))]
        })

        l.log(f"{len(ret.index)} entities of the Human Phenotype Ontology (HPO) extracted.")

    return ret

def getLabels(
    hpo                 : Ontology = None, 
    id_column           : str = "", 
    attribute_column    : str = "", 
    value_column        : str = "", 
    additional_column   : str = ""
) -> pd.DataFrame:
    """
    Extract rdfs:label annotations for HPO concepts.
    """
    ret = None
    l = Logger()

    if hpo is not None:
        l.log("Get labels of the Human Phenotype Ontology (HPO)...")

        g = hpo.world.as_rdflib_graph()

        # Simple query for concept labels
        query = """
            SELECT ?hpoID ?label WHERE {
                ?hpoID rdfs:label ?label .
            }
        """

        result = g.query(
            query,
            initNs={
                "rdf": RDF,
                "owl": OWL,
                "obo": OBO,
                "oboInOwl": OBOINOWL,
            }
        )

        ids    = []
        values = []

        for row in result:
            ids.append(getConceptIDFromString(str(row.hpoID)))
            values.append(row.label)

        # Normalize comments into standard DataFrame format
        ret = pd.DataFrame({
            id_column           : ids, 
            attribute_column    : [labelClass] * len(ids), 
            value_column        : values, 
            additional_column   : [{} for _ in range(len(ids))]
        })

        l.log(f"{len(ret.index)} entities of the Human Phenotype Ontology (HPO) extracted.")

    return ret

def getChildren(
    hpo                 : Ontology = None, 
    id_column           : str = "", 
    attribute_column    : str = "", 
    value_column        : str = "", 
    additional_column   : str = ""
) -> pd.DataFrame:
    """
    Extract parent–child (subClassOf) relationships from the ontology.

    Each row represents:
        parent HPO ID -> child HPO ID
    """
    ret = None
    l = Logger()

    if hpo is not None:
        l.log("Get children of concepts of the Human Phenotype Ontology (HPO)...")

        # Convert Owlready2 ontology into an RDFLib graph
        g = hpo.world.as_rdflib_graph()

        # Retrieve all subclass relationships
        query = """
            SELECT ?child ?parent WHERE {
                ?child rdfs:subClassOf ?parent .
            }
        """

        result = g.query(
            query,
            initNs={
                "rdf": RDF,
                "owl": OWL,
                "obo": OBO,
                "oboInOwl": OBOINOWL,
            }
        )

        ids    = []
        values = []

        for row in result:
            ids.append(getConceptIDFromString(str(row.parent)))
            values.append(getConceptIDFromString(str(row.child)))

        # Normalize comments into standard DataFrame format
        ret = pd.DataFrame({
            id_column           : ids, 
            attribute_column    : [childrenClass] * len(ids), 
            value_column        : values, 
            additional_column   : [{} for _ in range(len(ids))]
        })

        l.log(f"{len(ret.index)} entities of the Human Phenotype Ontology (HPO) extracted.")

    return ret

def getReferences(
    hpo                 : Ontology = None, 
    id_column           : str = "", 
    attribute_column    : str = "", 
    value_column        : str = "", 
    additional_column   : str = ""
) -> pd.DataFrame:
    """
    Extract database cross-references (DbXrefs) for HPO concepts.

    Includes:
    - Direct hasDbXref annotations
    - Axiom-annotated DbXrefs
    """
    ret = None
    l = Logger()

    if hpo is not None:
        l.log("Get references of the Human Phenotype Ontology (HPO)...")

        g = hpo.world.as_rdflib_graph()

        # Retrieve cross-references from both direct and axiom-based annotations
        query = """
            SELECT DISTINCT ?hpoID ?xref WHERE {
                {
                    ?hpoID oboInOwl:hasDbXref ?xref .
                }
                UNION
                {
                    ?axiom rdf:type owl:Axiom .
                    ?axiom owl:annotatedSource ?hpoID .
                    ?axiom oboInOwl:hasDbXref ?xref .
                }
            }
        """

        result = g.query(
            query,
            initNs={
                "rdf": RDF,
                "owl": OWL,
                "obo": OBO,
                "oboInOwl": OBOINOWL,
            }
        )

        ids     = []
        values  = []

        for row in result:
            ids.append(getConceptIDFromString(str(row.hpoID)))
            values.append(row.xref)

        # Normalize references into standard DataFrame format
        ret = pd.DataFrame({
            id_column         : ids,
            attribute_column  : [referenceClass] * len(ids),
            value_column      : values,
            additional_column : [{} for _ in range(len(ids))]
        })

        l.log(f"{len(ret.index)} entities of the Human Phenotype Ontology (HPO) extracted.")

    return ret