"""
Tests for HPOAdapter and its configuration loading.

Contains four test classes:
- TestHPOAdapterInit: unit tests for configuration loading via __init__.
- TestHPOAdapterLoad: integration tests against the real hp.owl file,
  verifying the shape and contents of the loaded EAV DataFrame.
- TestHPOAdapterUtilsQueries: unit tests for the SPARQL extractors
  against a small in-memory graph.
- TestHPOAdapterLoadWithSampleGraph: load() end to end on that graph.
"""

from __future__ import annotations

import os
import time
import pytest

from unittest.mock      import MagicMock, patch
from rdflib             import Graph
from .HPOAdapter        import HPOAdapter
from .HPOAdapterUtils   import (
    getSynonymsAndTypes, getReferences,
    semanticClass, sourceType, exactSynonymClass, relatedSynonymClass,
    laypersonSynonymType, directSynonymType,
    abbreviationSynonymType, pluralFormSynonymType,
)
from ..BaseAdapterUtils import (
    labelClass, definitionClass, commentClass,
    referenceClass, childrenClass, synonymClass,
)


@pytest.fixture
def adapter():
    """
    Build an HPOAdapter passing the path relative to the repo root.
    """
    return HPOAdapter(config="./config/config.yaml")


@pytest.fixture(scope="module")
def loaded_adapter():
    """
    Build an HPOAdapter and run the real load() once for the whole
    module - this parses the actual configured hp.owl file via
    owlready2 and runs the real HPOAdapterUtils extractors against it,
    with no mocking involved. Scoped to the module (rather than
    per-function) since re-parsing the full ontology for every test
    would be expensive and these tests only read the result, never
    mutate it.

    Requires owlready2 to be installed and the real ontology file to
    exist at the path configured in ./config/config.yaml. Without the
    file (e.g. in CI, where data/input/ is not checked in), the tests
    using this fixture are skipped.
    """
    a = HPOAdapter(config="./config/config.yaml")
    path = os.path.join(a.config.input_folder, a.config.input_files[0])
    if not os.path.isfile(path):
        pytest.skip(f"HPO ontology file '{path}' not found.")
    row_count = a.load()
    return a, row_count


class TestHPOAdapterInit:
    """
    Unit tests for HPOAdapter.__init__.

    Verifies that configuration values are correctly loaded from the
    YAML file and that defaults are applied for fields not explicitly set.
    """

    def test_init_loads_input_settings_from_real_config(self, adapter):
        assert adapter.config.input_folder == "./data/input/hpo/"
        assert adapter.config.input_files == ["hp.owl"]

    def test_init_loads_output_settings_from_real_config(self, adapter):
        assert adapter.config.output_folder == "./data/output/transformed/hpo/"
        assert adapter.config.output_file == "hpo.csv"

    def test_init_applies_defaults_for_fields_not_set_in_config(self, adapter):
        # delimiter, encoding, and the EAV column names aren't overridden
        # in config.yaml, so BaseAdapterConfig's own defaults apply.
        assert adapter.config.delimiter == ";"
        assert adapter.config.encoding == "utf-8"
        assert adapter.config.id_column == "id"
        assert adapter.config.attribute_column == "attribute"
        assert adapter.config.value_column == "value"
        assert adapter.config.additional_column == "additional"

    def test_init_loads_empty_prefix_from_real_config(self, adapter):
        assert adapter.config.prefix == ""

    def test_data_is_unset_before_load(self, adapter):
        assert adapter.data is None


class TestHPOAdapterLoad:
    """
    Integration tests against the real hp.owl file - no mocking of
    get_ontology or HPOAdapterUtils. Assertions check the shape and
    general contents of the real output rather than exact row counts,
    since those depend on whatever the actual ontology file contains.
    """

    def test_load_returns_a_positive_row_count(self, loaded_adapter):
        _, row_count = loaded_adapter
        assert row_count > 0

    def test_load_populates_self_data(self, loaded_adapter):
        adapter, row_count = loaded_adapter
        assert adapter.data is not None
        assert len(adapter.data) == row_count

    def test_load_data_has_the_configured_eav_columns(self, loaded_adapter):
        adapter, _ = loaded_adapter
        expected_columns = {
            adapter.config.id_column,
            adapter.config.attribute_column,
            adapter.config.value_column,
            adapter.config.additional_column,
        }
        assert expected_columns.issubset(set(adapter.data.columns))

    def test_load_produces_every_known_attribute_type(self, loaded_adapter):
        adapter, _ = loaded_adapter
        found_attributes = set(adapter.data[adapter.config.attribute_column])
        expected_attributes = {
            labelClass, definitionClass, commentClass,
            referenceClass, childrenClass, synonymClass,
        }
        assert expected_attributes.issubset(found_attributes)

    def test_load_removes_rows_without_an_id(self, loaded_adapter):
        adapter, _ = loaded_adapter
        id_column = adapter.data[adapter.config.id_column]
        assert id_column.notna().all()
        assert (id_column != "").all()

    def test_load_removes_rows_with_a_hash_in_the_id(self, loaded_adapter):
        adapter, _ = loaded_adapter
        id_column = adapter.data[adapter.config.id_column]
        assert not id_column.str.contains("#", na=False).any()


# Minimal OWL content in the RDF shape OWLAPI writes for hp.owl: annotated
# synonyms and definitions have both the direct triple and an owl:Axiom.
SAMPLE_TTL = """
@prefix rdf:      <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:     <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:      <http://www.w3.org/2002/07/owl#> .
@prefix xsd:      <http://www.w3.org/2001/XMLSchema#> .
@prefix obo:      <http://purl.obolibrary.org/obo/> .
@prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#> .

obo:HP_1 a owl:Class ;
    rdfs:label "Concept one" ;
    obo:IAO_0000115 "A definition." ;
    oboInOwl:hasDbXref "UMLS:C1" ;
    oboInOwl:hasExactSynonym "plain", "lay", "ABC" ;
    oboInOwl:hasRelatedSynonym "sourced" .

[] a owl:Axiom ;
    owl:annotatedSource obo:HP_1 ;
    owl:annotatedProperty oboInOwl:hasExactSynonym ;
    owl:annotatedTarget "lay" ;
    oboInOwl:hasSynonymType <http://purl.obolibrary.org/obo/hp#layperson> ;
    oboInOwl:hasDbXref "ORCID:1" .

[] a owl:Axiom ;
    owl:annotatedSource obo:HP_1 ;
    owl:annotatedProperty oboInOwl:hasExactSynonym ;
    owl:annotatedTarget "ABC" ;
    oboInOwl:hasSynonymType <http://purl.obolibrary.org/obo/hp#abbreviation>,
                            <http://purl.obolibrary.org/obo/hp#plural_form> .

[] a owl:Axiom ;
    owl:annotatedSource obo:HP_1 ;
    owl:annotatedProperty oboInOwl:hasRelatedSynonym ;
    owl:annotatedTarget "sourced" ;
    oboInOwl:hasDbXref "PMID:2" .

[] a owl:Axiom ;
    owl:annotatedSource obo:HP_1 ;
    owl:annotatedProperty obo:IAO_0000115 ;
    owl:annotatedTarget "A definition." ;
    oboInOwl:hasDbXref "PMID:3" .

obo:HP_2 a owl:Class ;
    owl:deprecated true ;
    oboInOwl:hasExactSynonym "deprecated synonym" .

[] a owl:Axiom ;
    owl:annotatedSource obo:HP_2 ;
    owl:annotatedProperty oboInOwl:hasExactSynonym ;
    owl:annotatedTarget "deprecated synonym" ;
    oboInOwl:hasSynonymType <http://purl.obolibrary.org/obo/hp#layperson> .

obo:HP_3 a owl:Class ;
    oboInOwl:is_obsolete "true"^^xsd:boolean ;
    oboInOwl:hasExactSynonym "obsolete synonym" .
"""


@pytest.fixture
def sample_hpo():
    """
    A stand-in for an owlready2 ontology whose RDF graph is SAMPLE_TTL,
    so the real SPARQL queries in HPOAdapterUtils can run without hp.owl.
    """
    hpo = MagicMock()
    hpo.world.as_rdflib_graph.return_value = Graph().parse(data=SAMPLE_TTL, format="turtle")
    return hpo


class TestHPOAdapterUtilsQueries:
    """
    Unit tests running the HPOAdapterUtils SPARQL extractors against a
    small in-memory graph.
    """

    def test_each_synonym_is_extracted_once_with_its_type(self, sample_hpo):
        frame = getSynonymsAndTypes(sample_hpo, "id", "attribute", "value", "additional")
        rows = sorted(
            (r.id, str(r.value), r.additional[semanticClass], r.additional[sourceType])
            for r in frame.itertuples()
        )
        assert rows == [
            ("HP:1", "ABC",     exactSynonymClass,   abbreviationSynonymType),
            ("HP:1", "ABC",     exactSynonymClass,   pluralFormSynonymType),
            ("HP:1", "lay",     exactSynonymClass,   laypersonSynonymType),
            ("HP:1", "plain",   exactSynonymClass,   directSynonymType),
            ("HP:1", "sourced", relatedSynonymClass, directSynonymType),
        ]

    def test_synonym_extraction_scales_linearly(self):
        # Regression test: joining synonyms with their axioms inside one
        # SPARQL query took time proportional to synonyms x axioms (about
        # two minutes for this graph, days for the full HPO).
        n = 300
        ttl = [SAMPLE_TTL.split("obo:HP_1", 1)[0]]
        for i in range(n):
            ttl.append(f"""
obo:HP_{i + 10} a owl:Class ;
    oboInOwl:hasExactSynonym "lay {i}" ;
    oboInOwl:hasRelatedSynonym "plain {i}" .
[] a owl:Axiom ;
    owl:annotatedSource obo:HP_{i + 10} ;
    owl:annotatedProperty oboInOwl:hasExactSynonym ;
    owl:annotatedTarget "lay {i}" ;
    oboInOwl:hasSynonymType <http://purl.obolibrary.org/obo/hp#layperson> .
[] a owl:Axiom ;
    owl:annotatedSource obo:HP_{i + 10} ;
    owl:annotatedProperty oboInOwl:hasRelatedSynonym ;
    owl:annotatedTarget "plain {i}" ;
    oboInOwl:hasDbXref "PMID:{i}" .
""")
        hpo = MagicMock()
        hpo.world.as_rdflib_graph.return_value = Graph().parse(data="".join(ttl), format="turtle")

        start = time.perf_counter()
        frame = getSynonymsAndTypes(hpo, "id", "attribute", "value", "additional")
        elapsed = time.perf_counter() - start

        assert len(frame) == 2 * n
        assert sum(a[sourceType] == laypersonSynonymType for a in frame["additional"]) == n
        assert elapsed < 10

    def test_references_exclude_xrefs_on_axioms(self, sample_hpo):
        frame = getReferences(sample_hpo, "id", "attribute", "value", "additional")
        assert [(r.id, str(r.value)) for r in frame.itertuples()] == [("HP:1", "UMLS:C1")]


class TestHPOAdapterLoadWithSampleGraph:
    """
    Runs HPOAdapter.load() end to end on the small in-memory graph, so
    the shared BaseAdapter steps are covered without hp.owl.
    """

    def test_load_extracts_cleans_and_keeps_hp_ids(self, adapter, sample_hpo):
        with patch("os.path.isfile", return_value=False), \
             patch("src.hpo.HPOAdapter.get_ontology") as mock_get_ontology:
            mock_get_ontology.return_value.load.return_value = sample_hpo
            ret = adapter.load()

        data = adapter.data
        assert ret == len(data) > 0
        # Only the active concept HP:1 is left, without a prefix added.
        assert set(data[adapter.config.id_column]) == {"HP:1"}
        assert set(data[adapter.config.attribute_column]) == {
            labelClass, definitionClass, referenceClass, synonymClass,
        }


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))