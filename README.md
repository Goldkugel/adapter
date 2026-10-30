# Adapter

A Python library for transforming biomedical ontologies into a unified **Entity–Attribute–Value (EAV)** representation.

The project provides a common adapter framework together with ontology-specific implementations, currently supporting:

- Human Phenotype Ontology (HPO)
- SNOMED CT (SCT)
- Unified Medical Language System (UMLS)

The generated EAV tables can be used for downstream analytics, knowledge graph construction, database import, or data integration workflows.

---

## Features

- Common adapter framework for ontology transformation
- Configurable through YAML, a dict or a Pydantic model
- Standardized EAV output
- Built-in logging
- Validation using Pydantic models
- Extensible architecture for additional ontologies
- CSV export

---

## Project Structure

```
adapter/
├── .github/workflows/
│   └── tests.yml
├── config/
│   └── config.yaml
├── data/
│   ├── input/
│   │   ├── hpo/
│   │   ├── sct/
│   │   └── umls/
│   ├── output/
│   │   └── transformed/
│   └── logs/
├── src/
│   ├── __init__.py
│   ├── BaseAdapter.py
│   ├── BaseAdapterConfig.py
│   ├── BaseAdapterUtils.py
│   ├── BaseAdapterTest.py
│   ├── BaseAdapterUtilsTest.py
│   ├── hpo/
│   │   ├── HPOAdapter.py
│   │   ├── HPOAdapterUtils.py
│   │   └── HPOAdapterTest.py
│   ├── sct/
│   │   ├── SCTAdapter.py
│   │   ├── SCTAdapterUtils.py
│   │   └── SCTAdapterTest.py
│   └── umls/
│       ├── UMLSAdapter.py
│       ├── UMLSAdapterUtils.py
│       └── UMLSAdapterTest.py
└── pyproject.toml
```

---

## Requirements

- Python 3.9 or newer
- pandas
- pydantic (version 2)
- PyYAML
- owlready2 (for HPO support)
- rdflib (for HPO support)
- [logger](https://github.com/Goldkugel/logger) package

All dependencies are declared in `pyproject.toml` and installed by `pip install .`.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/Goldkugel/adapter.git
cd adapter
```

Install the package:

```bash
pip install .
```

or in editable mode for development:

```bash
pip install -e .
```

---

## Configuration

Configuration is stored by default in

```
config/config.yaml
```

The `adapter` section has one subsection per adapter (`hpo`, `sct`, `umls`), each defining:

- input folder and input files
- output folder and output filename
- output delimiter, input separator and encoding
- ID prefix
- EAV column names

All subsections share the same schema (`BaseAdapterConfig`); fields that are not set fall back to its defaults. The `logger` section of the same file configures the logger package (see [Logging](#logging)). Instead of a YAML file, an adapter can also be given a dict or a `BaseAdapterConfig` (see [Using an Adapter](#using-an-adapter)). All fields are described in [config/README.md](config/README.md).

---

## Supported Adapters

### Human Phenotype Ontology (HPO)

The HPO adapter loads ontology data using **owlready2** and **rdflib** and extracts information including:

- identifiers
- labels
- definitions
- comments
- synonyms
- references
- parent-child relationships

The extracted information is converted into the common EAV representation.

---

### SNOMED CT

The SNOMED CT adapter processes RF2 release files and extracts terminology into the same EAV format used by the HPO adapter. Supported RF2 file types are Concept, Description, TextDefinition, Relationship (inferred IS-A relationships) and SimpleMap reference set files; other configured RF2 files are skipped.

Full release files contain every historical version of each component. The adapter keeps only the latest version, so concepts, descriptions, relationships and maps that were later inactivated are not included. The Concept file is required: it restricts all other files to currently active concepts. SNOMED CT IDs are written with the configured prefix (`SNOMEDCT_US:` by default), matching the UMLS source abbreviation.

---

### UMLS

The UMLS adapter processes RRF release files (MRCONSO, MRDEF) and extracts concepts, synonyms, definitions, and source references into the same EAV format used by the other adapters. Only English, non-suppressed rows are used; other configured RRF files are skipped. Every concept gets a label: from its `PT`/`PN` strings, or otherwise from its preferred atom. CUIs are written with the configured prefix (`UMLS:` by default), the form HPO uses in its cross-references.

---

## Output Format

All adapters produce a normalized Entity–Attribute–Value table with the following columns (illustrative rows):

| id | attribute | value | additional |
|----|-----------|-------|------------|
| HP:0000118 | label | Phenotypic abnormality | {} |
| HP:0000118 | definition | A phenotypic abnormality. | {} |
| HP:0000118 | synonym | Clinical abnormality | {'semantic_class': 'exact', 'source_type': 'direct'} |
| HP:0000118 | child | HP:0000119 | {} |

The `additional` column holds a dictionary with source-specific metadata, e.g. the synonym class and type for HPO, the case significance or map refset for SNOMED CT, or the source vocabulary for UMLS. It is written as a Python dict literal (single quotes, not JSON), so read it back with `ast.literal_eval`. A `child` row means that `value` is a direct child (subclass) of `id`.

All fields are quoted, and the field delimiter is configurable (`;` by default).

This common representation enables downstream processing independent of the original ontology format. The EAV attribute names are defined as constants in `BaseAdapterUtils.py` (e.g. `labelClass`, `synonymClass`) and should be reused by any new adapter.

---

## Using an Adapter

Example:

```python
from adapter import HPOAdapter

adapter = HPOAdapter()              # reads ./config/config.yaml by default

adapter.load()
adapter.to_csv()
```

Instead of a YAML path, every adapter also accepts a dict or a `BaseAdapterConfig`:

```python
from adapter import BaseAdapterConfig, SCTAdapter

# From a YAML file (a pathlib.Path works as well).
adapter = SCTAdapter("./config/config.yaml")

# From a dict: either the whole configuration (with an "adapter" key and
# optionally a "logger" key) or just the settings of this adapter.
adapter = SCTAdapter({"adapter": {"sct": {"input_files": [...]}}, "logger": {...}})
adapter = SCTAdapter({"input_files": [...], "output_file": "sct.csv"})

# From a BaseAdapterConfig (a copy is stored).
adapter = SCTAdapter(BaseAdapterConfig(input_files=[...]))
```

If `prefix` is not set, the adapter's default prefix applies in all three cases (e.g. `SNOMEDCT_US:` for SNOMED CT).

When working directly in a clone of this repository without installing it, import from `src` instead (`from src import HPOAdapter`). Paths in the configuration are relative to the working directory, so run from the repository root.

The resulting CSV is written to the configured output directory.

---

## Extending the Framework

To support another ontology:

1. Subclass `BaseAdapter`, set `ontology_name` (used in log messages) and `default_prefix`, and implement `_loadFrames()` to return the EAV rows read from the input files. The shared `load()` merges and cleans them and adds the prefix; override `_clean()` for source-specific cleaning.
2. Use the shared EAV attribute-name constants from `BaseAdapterUtils` (e.g. `labelClass`, `synonymClass`) to keep attribute names consistent across adapters.
3. Add a configuration section for the new adapter to `config/config.yaml`, following the same structure as the existing adapter sections.
4. Export the new adapter class from `src/__init__.py`.

This design keeps ontology-specific parsing separate from the shared export and configuration logic.

---

## Logging

The project uses the external `logger` package for consistent logging during:

- loading
- parsing
- validation
- CSV export
- directory creation

The logger is a process-wide singleton. If it has not been configured yet when an adapter is created, it is configured from the same source: the `logger` section of the YAML file, or the `logger` key of a full configuration dict. Otherwise (adapter settings only, or a `BaseAdapterConfig`) configure it first with `Logger("path/to/config.yaml")`, or it falls back to `./config/config.yaml`.

---

## Development

Install in editable mode, with the test dependencies:

```bash
pip install -e ".[test]"
```

Run the test suite with pytest from the repository root (the test files are named `*Test.py`; `pyproject.toml` configures pytest to collect them from `src/`):

```bash
pytest
```

Most tests use mocks or small temporary files. The `TestHPOAdapterLoad` tests are integration tests and need the real `hp.owl` in `data/input/hpo/`; without it they are skipped.

A GitHub Actions workflow (`.github/workflows/tests.yml`) runs the tests on Python 3.9, 3.11 and 3.14 on every push and pull request. The input files are not checked in, so the `hp.owl` integration tests are skipped there.

Place ontology input files inside the appropriate directory under `data/input/` before running an adapter.

---

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).

See the `LICENSE` file for details.