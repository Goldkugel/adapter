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
- Configurable through YAML
- Standardized EAV output
- Built-in logging
- Validation using Pydantic models
- Extensible architecture for additional ontologies
- CSV export

---

## Project Structure

```
adapter/
├── config/
│   └── config.yaml
├── data/
│   ├── input/
│   │   ├── hpo/
│   │   ├── sct/
│   │   └── umls/
│   ├── output/
│   └── logs/
├── src/
│   ├── BaseAdapter.py
│   ├── BaseAdapterConfig.py
│   ├── BaseAdapterUtils.py
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

- Python 3.11 or newer (recommended)
- pandas
- pydantic
- PyYAML
- owlready2 (for HPO support)
- rdflib (for HPO support)
- logger package

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

Configuration is stored in

```
config/config.yaml
```

The base configuration defines:

- input folder
- input files
- output folder
- output filename
- delimiter
- encoding
- logging options
- adapter-specific settings

Each ontology adapter reads its own configuration section while sharing the common base configuration.

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

The SNOMED CT adapter processes RF2 release files and extracts terminology into the same EAV format used by the HPO adapter. Supported RF2 file types include Concept, Description, TextDefinition, Relationship, and SimpleMap reference set files.

---

### UMLS

The UMLS adapter processes RRF release files (MRCONSO, MRDEF) and extracts concepts, synonyms, definitions, and source references into the same EAV format used by the other adapters.

---

## Output Format

All adapters produce a normalized Entity–Attribute–Value table with the following columns:

| id | attribute | value |
|----|-----------|-------|
| HP:0000118 | label | Phenotypic abnormality |
| HP:0000118 | definition | A phenotypic abnormality. |
| HP:0000118 | synonym | Clinical abnormality |

This common representation enables downstream processing independent of the original ontology format. The EAV attribute names are defined as constants in `BaseAdapterUtils.py` (e.g. `labelClass`, `synonymClass`) and should be reused by any new adapter.

---

## Using an Adapter

Example:

```python
from src import HPOAdapter

adapter = HPOAdapter()

adapter.load()
adapter.to_csv()
```

The resulting CSV is written to the configured output directory.

---

## Extending the Framework

To support another ontology:

1. Subclass `BaseAdapter` and implement the `load()` method to populate `self.data` with EAV rows.
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

---

## Development

Install in editable mode:

```bash
pip install -e .
```

Run the test suite with pytest:

```bash
pytest src/
```

Place ontology input files inside the appropriate directory under `data/input/` before running an adapter.

---

## License

This project is licensed under the MIT License.

See the `LICENSE` file for details.