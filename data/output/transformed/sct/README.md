# SNOMED CT output

`SCTAdapter.to_csv()` writes the EAV table of SNOMED CT here, as `sct.csv` by
default (see `adapter.sct.output_file` in `config/config.yaml`). The CSV
files are not tracked by version control.

## Content

IDs are SCTIDs with the prefix `SNOMEDCT_US:`, e.g.
`SNOMEDCT_US:404684003`. Only currently active concepts are included, and
only the latest, active version of each description, relationship and map.

| attribute | value | additional | Source file |
|---|---|---|---|
| `label` | Fully Specified Name | `caseSignificanceId` | `sct2_Description_` |
| `synonym` | Synonym | `caseSignificanceId` | `sct2_Description_` |
| `definition` | Textual definition | `caseSignificanceId` | `sct2_TextDefinition_` |
| `child` | `SNOMEDCT_US:` ID of a direct IS-A child of `id` (inferred) | `{}` | `sct2_Relationship_` |
| `reference` | Map target code | `reference_ontology` (the refset ID) | `der2_sRefset_SimpleMap` |

All fields are quoted and separated by `;` (configurable). The
`additional` column is a Python dict literal; read it with
`ast.literal_eval`.
