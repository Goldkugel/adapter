# Configuration

All adapter settings are stored in `config.yaml` under the top-level
`adapter` section. Each subsection is keyed by the adapter's short name
(`hpo`, `sct`, `umls`) and maps directly to a `BaseAdapterConfig` Pydantic
model. Fields not explicitly set fall back to the defaults defined in
`BaseAdapterConfig`.

---

## Shared fields (all adapters)

| Field | Type | Default | Description |
|---|---|---|---|
| `input_folder` | string | `"./data/input/"` | Directory containing the raw ontology input file(s). |
| `input_files` | list of strings | `[]` | File names to load from `input_folder`. |
| `output_folder` | string | `"./data/output/transformed/"` | Directory where the output CSV is written. Created automatically if it does not exist. |
| `output_file` | string | `"ontology.csv"` | Name of the output CSV file within `output_folder`. |
| `delimiter` | string | `";"` | Field delimiter used in the output CSV. |
| `encoding` | string | `"utf-8"` | Character encoding used for both reading input files and writing the output CSV. |
| `separator` | string | `"\t"` | Field separator used when reading tabular input files (e.g. RF2 or RRF files). |
| `skip_if_present` | boolean | `false` | If `true`, `load()` returns immediately when the output file already exists, without re-parsing the source files. |
| `id_column` | string | `"id"` | Name of the EAV identifier column in the output CSV. |
| `attribute_column` | string | `"attribute"` | Name of the EAV attribute column in the output CSV. |
| `value_column` | string | `"value"` | Name of the EAV value column in the output CSV. |
| `additional_column` | string | `"additional"` | Name of the EAV additional-information column (JSON object) in the output CSV. |

---

## `hpo` — Human Phenotype Ontology

The HPO adapter reads a single OWL file via owlready2 and rdflib.

```yaml
adapter:
  hpo:
    input_folder: "./data/input/hpo/"
    input_files:
      - "hp.owl"
    output_folder: "./data/output/transformed/hpo/"
    output_file: "hpo.csv"
    skip_if_present: false
```

**Notes:**
- Only the first entry in `input_files` is used; the HPO is distributed as a single `.owl` file.
- `separator` and `encoding` are not needed and can be omitted; the OWL file is parsed by owlready2, not read as a tabular file.

---

## `sct` — SNOMED CT

The SCT adapter reads multiple RF2 release files. The Concept file is required
and must be included — it is used to build the active-concept filter set that
restricts all other files to currently active concepts.

```yaml
adapter:
  sct:
    input_folder: "./data/input/sct/"
    input_files:
      - "sct2_Concept_Full_INT_20260701.txt"
      - "sct2_Description_Full-en_INT_20260701.txt"
      - "sct2_TextDefinition_Full-en_INT_20260701.txt"
      - "sct2_Relationship_Full_INT_20260701.txt"
      - "der2_sRefset_SimpleMapFull_INT_20260701.txt"
    output_folder: "./data/output/transformed/sct/"
    output_file: "sct.csv"
    skip_if_present: false
    encoding: "utf-8"
    separator: "\t"
```

**Supported RF2 file prefixes:**

| Prefix | Content | EAV attributes produced |
|---|---|---|
| `sct2_Concept_` | Active concept list (filter only, no EAV output) | — |
| `sct2_Description_` | Fully Specified Names and Synonyms | `label`, `synonym` |
| `sct2_TextDefinition_` | Free-text definitions | `definition` |
| `sct2_Relationship_` | IS-A relationships | `child` |
| `der2_sRefset_SimpleMapFull` | Cross-map reference sets (e.g. ICD-10) | `reference` |

Files whose names do not match any of the prefixes above are skipped with a
log warning. Other RF2 files (e.g. `sct2_StatedRelationship_`,
`sct2_Identifier_`) are currently not processed.

**Notes:**
- `separator` must be `"\t"` (tab) — the standard RF2 delimiter.
- The release date in the filename (e.g. `20260701`) does not affect processing.

---

## `umls` — Unified Medical Language System

The UMLS adapter reads RRF files from a UMLS Metathesaurus release. Only
English, non-suppressed rows are extracted.

```yaml
adapter:
  umls:
    input_folder: "./data/input/umls/"
    input_files:
      - "MRCONSO.RRF"
      - "MRDEF.RRF"
    output_folder: "./data/output/transformed/umls/"
    output_file: "umls.csv"
    skip_if_present: false
    encoding: "utf-8"
    separator: "|"
```

**Supported RRF file prefixes:**

| Prefix | Content | EAV attributes produced |
|---|---|---|
| `MRCONSO` | Concept strings across all source vocabularies | `label`, `synonym`, `reference` |
| `MRDEF` | Concept definitions | `definition` |

Files whose names do not match any of the prefixes above are skipped with a
log warning. Other RRF files (e.g. `MRREL`, `MRSTY`) are currently not
processed.

**Notes:**
- `separator` must be `"|"` (pipe) — the standard RRF delimiter.
- UMLS requires a license from the U.S. National Library of Medicine (NLM).
  The RRF files are not redistributable and must be downloaded separately.