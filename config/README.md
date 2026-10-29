# Configuration

The `logger`, `normalizer` and `llm` sections of `config.yaml` belong to
other packages of the pipeline that share this file; only the `adapter`
section is read by this package.

All adapter settings are stored in `config.yaml` under the top-level
`adapter` section. Each subsection is keyed by the adapter's short name
(`hpo`, `sct`, `umls`) and maps directly to a `BaseAdapterConfig` Pydantic
model. Fields not explicitly set fall back to the defaults defined in
`BaseAdapterConfig`, except `prefix`, which falls back to the adapter's own
default.

If the `adapter` section or the adapter's subsection is missing or empty, or
if it contains unknown keys or invalid values, creating the adapter raises a
`ValueError` that names the section and the configuration file.

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
| `prefix` | string | adapter-specific: `""` (HPO), `"SNOMEDCT_US:"` (SNOMED CT), `"UMLS:"` (UMLS) | Prefix added to every ID and to the value of every `child` row. |
| `skip_if_present` | boolean | `false` | If `true`, `load()` returns immediately when the output file already exists, without re-parsing the source files. |
| `id_column` | string | `"id"` | Name of the EAV identifier column in the output CSV. |
| `attribute_column` | string | `"attribute"` | Name of the EAV attribute column in the output CSV. |
| `value_column` | string | `"value"` | Name of the EAV value column in the output CSV. |
| `additional_column` | string | `"additional"` | Name of the EAV additional-information column (a dict, written as a Python dict literal) in the output CSV. |

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
    prefix: ""
```

**Notes:**
- Only the first entry in `input_files` is used; the HPO is distributed as a single `.owl` file.
- `separator` and `encoding` are not needed and can be omitted; the OWL file is parsed by owlready2, not read as a tabular file.
- `prefix` is empty, since HPO IDs already carry their prefix (`HP:0000118`).

---

## `sct` — SNOMED CT

The SCT adapter reads multiple RF2 release files. Exactly one Concept file is
required — it is used to build the active-concept filter set that restricts
all other files to currently active concepts. `load()` raises a
`FileNotFoundError` if it is missing and a `ValueError` if more than one is
configured.

```yaml
adapter:
  sct:
    input_folder: "./data/input/sct/"
    input_files:
      - "der2_sRefset_SimpleMapFull_INT_20260701.txt"
      - "sct2_Concept_Full_INT_20260701.txt"
      - "sct2_Description_Full-en_INT_20260701.txt"
      - "sct2_sRefset_OWLExpressionFull_INT_20260701.txt"
      - "sct2_Relationship_Full_INT_20260701.txt"
      - "sct2_RelationshipConcreteValues_Full_INT_20260701.txt"
      - "sct2_Identifier_Full_INT_20260701.txt"
      - "sct2_StatedRelationship_Full_INT_20260701.txt"
      - "sct2_TextDefinition_Full-en_INT_20260701.txt"
    output_folder: "./data/output/transformed/sct/"
    output_file: "sct.csv"
    skip_if_present: false
    prefix: "SNOMEDCT_US:"
    encoding: "utf-8"
    separator: "\t"
```

**Supported RF2 file prefixes:**

| Prefix | Content | EAV attributes produced |
|---|---|---|
| `sct2_Concept_` | Active concept list (filter only, no EAV output) | — |
| `sct2_Description_` | Fully Specified Names and Synonyms | `label`, `synonym` |
| `sct2_TextDefinition_` | Free-text definitions | `definition` |
| `sct2_Relationship_` | Inferred IS-A relationships | `child` |
| `der2_sRefset_SimpleMap` | Cross-map reference sets (e.g. ICD-O), Full/Snapshot/Delta | `reference` |

Files whose names do not match any of the prefixes above are skipped with a
log message. In the configuration above, this applies to
`sct2_sRefset_OWLExpression…`, `sct2_RelationshipConcreteValues_…`,
`sct2_Identifier_…` and `sct2_StatedRelationship_…`; they are listed but not
processed.

**Notes:**
- `separator` must be `"\t"` (tab) — the standard RF2 delimiter.
- Full and Snapshot files can both be used. For Full files, only the latest
  version (highest `effectiveTime`) of each component is kept before the
  active filter is applied, so historical rows never reach the output.
- The release date in the filename (e.g. `20260701`) does not affect processing.
- IDs (and the values of `child` rows) are prefixed with `prefix`
  (`SNOMEDCT_US:`, matching the UMLS source abbreviation, which downstream
  mapping code relies on).

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
      - "MRRANK.RRF"
      - "MRREL.RRF"
      - "MRSAT.RRF"
      - "MRSTY.RRF"
    output_folder: "./data/output/transformed/umls/"
    output_file: "umls.csv"
    skip_if_present: false
    prefix: "UMLS:"
    encoding: "utf-8"
    separator: "|"
```

**Supported RRF file prefixes:**

| Prefix | Content | EAV attributes produced |
|---|---|---|
| `MRCONSO` | Concept strings across all source vocabularies | `label`, `synonym`, `reference` |
| `MRDEF` | Concept definitions | `definition` |

Files whose names do not match any of the prefixes above are skipped with a
log message. In the configuration above, this applies to `MRRANK`, `MRREL`,
`MRSAT` and `MRSTY`; they are listed but not processed.

**Notes:**
- `separator` must be `"|"` (pipe) — the standard RRF delimiter.
- RRF has no quoting: strings are read verbatim (quote characters included),
  and values such as `NA` are kept as strings rather than treated as missing.
- CUIs are prefixed with `prefix` (`UMLS:`, the form HPO uses in its
  cross-references), e.g. `UMLS:C0000005`.
- UMLS requires a license from the U.S. National Library of Medicine (NLM).
  The RRF files are not redistributable and must be downloaded separately.