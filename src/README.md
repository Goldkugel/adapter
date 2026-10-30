# Source code

This folder is the `adapter` Python package (`pyproject.toml` maps the package
name `adapter` to `src/`). Everything that is part of the public API is
exported from `__init__.py`.

---

## Layout

```
src/
├── __init__.py            Public API (adapters, BaseAdapterConfig, CSV writers and attribute-name constants)
├── BaseAdapter.py         Abstract base class: config loading, shared load() steps and CSV export
├── BaseAdapterConfig.py   Pydantic model of one adapter config section
├── BaseAdapterUtils.py    EAV attribute names, filesystem and CSV helpers
├── BaseAdapterTest.py     pytest tests for BaseAdapter
├── hpo/                   Human Phenotype Ontology (OWL)
├── sct/                   SNOMED CT (RF2)
└── umls/                  UMLS Metathesaurus (RRF)
```

Each ontology subpackage follows the same pattern:

| File | Content |
|---|---|
| `<Name>Adapter.py` | Concrete `BaseAdapter` subclass; its `_loadFrames()` reads the input files, and it sets the ontology name and default prefix |
| `<Name>AdapterUtils.py` | Source-specific constants, file readers and EAV extractors/transformers |
| `<Name>AdapterTest.py` | pytest tests for the adapter and its utilities |

---

## How an adapter works

1. **Configuration** – `BaseAdapter.__init__()` reads a YAML file
   (`config/config.yaml` by default) or a full configuration dict and
   validates the section `adapter.<name>` (e.g. `adapter.sct`) into a
   `BaseAdapterConfig`. It also accepts just the adapter's settings as a
   dict, or a ready `BaseAdapterConfig` (of which it stores a copy).
   Unknown keys are rejected. If `prefix` isn't set, the adapter's
   `default_prefix` applies. A missing, empty or invalid section raises a
   `ValueError` naming the section. If the logger is not configured yet,
   it is configured from the `logger` section of the same file or dict.
2. **Loading** – `load()` calls the adapter's `_loadFrames()`, which reads
   the configured input files and converts each into a DataFrame with the
   four EAV columns (`id`, `attribute`, `value`, `additional`). The column
   names come from the configuration.
   - **HPO** loads `hp.owl` with owlready2 and runs one SPARQL query per
     attribute (labels, definitions, comments, children, references,
     synonyms) on its rdflib view.
   - **SNOMED CT** picks a reader/transformer per RF2 file by filename
     prefix, keeps only the latest version of each component in Full
     release files, keeps active rows, and restricts everything to active
     concepts from the Concept file.
   - **UMLS** picks a reader/transformer per RRF file by filename prefix
     and keeps only English, non-suppressed rows. Concepts without a
     `PT`/`PN` string get a label from their preferred atom.
3. **Cleaning** – `load()` concatenates the frames, removes rows without
   an ID or value, calls the adapter's `_clean()` hook (HPO removes hash
   IRIs there) and drops duplicate `(id, attribute, value)` rows.
4. **Prefixing** – `load()` adds the configured `prefix` to every ID and to
   the value of every `child` row.
5. **Export** – `to_csv()` writes `self.data` to
   `<output_folder>/<output_file>`. It writes to a temporary file first and
   then replaces the target, so an interrupted run never leaves a
   half-written CSV.

`load()` does nothing if no input files are configured, or if
`skip_if_present` is set and the output file already exists. Files whose
names match no known prefix are logged and skipped.

---

## EAV attributes

The attribute names are constants in `BaseAdapterUtils.py` and are shared by
all adapters:

| Constant | Value | Meaning |
|---|---|---|
| `labelClass` | `label` | Preferred name (HPO label, SNOMED CT FSN, UMLS PT/PN or preferred atom) |
| `synonymClass` | `synonym` | Alternative name |
| `definitionClass` | `definition` | Textual definition |
| `commentClass` | `comment` | Comment (HPO only) |
| `referenceClass` | `reference` | Code in another terminology |
| `childrenClass` | `child` | `value` is a direct child (subclass) of `id` |

Source-specific keys of the `additional` dict are defined in the respective
`*AdapterUtils.py` (e.g. `semanticClass` and `sourceType` for HPO synonyms,
`referenceOntology` for SNOMED CT maps, `sourceAbbreviation` for UMLS).

---

## Tests

Run from the repository root, so that the relative paths in the
configuration and the `src.` patch targets in the tests resolve:

```bash
pytest
```

(`pyproject.toml` points pytest at `src/` and collects the `*Test.py`
files.) Most tests use mocks, small temporary RF2/RRF files or an
in-memory RDF graph; `BaseAdapterTest.py` uses a minimal dummy adapter.
`TestHPOAdapterLoad` needs the real `data/input/hpo/hp.owl` and is skipped
without it.
