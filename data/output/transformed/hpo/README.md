# HPO output

`HPOAdapter.to_csv()` writes the EAV table of the Human Phenotype Ontology
here, as `hpo.csv` by default (see `adapter.hpo.output_file` in
`config/config.yaml`). The CSV files are not tracked by version control.

## Content

IDs are HPO CURIEs such as `HP:0000118`. Obsolete and deprecated terms are
excluded.

| attribute | value | additional |
|---|---|---|
| `label` | Term name | `{}` |
| `definition` | Textual definition | `{}` |
| `comment` | Comment | `{}` |
| `synonym` | Synonym | `semantic_class` and `source_type` (see below) |
| `reference` | Cross-reference, e.g. `UMLS:C0000001`, `SNOMEDCT_US:…` | `{}` |
| `child` | ID of a direct subclass of `id` | `{}` |

For synonyms, `semantic_class` is one of `exact`, `related`, `broad` or
`narrow`, and `source_type` is one of `layperson`, `abbreviation`,
`obsolete`, `plural`, `uk`, `allelic`, or `direct` if the synonym has no
type.

All fields are quoted and separated by `;` (configurable). The
`additional` column is a Python dict literal; read it with
`ast.literal_eval`.
