# DeliverIQ — Kitchen Source Validation

**Status:** Manual inspection and ad hoc reconciliation recorded; automated validation script PENDING (Task 5)
**Source of truth:** `task1/kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md` (file #13)
**SHA-256:** `7ee63f622758d0e0cdbd1396a50485b71e00d9265b5f74501dc6b3e4bfc19211` (recorded in `SOURCE_DOCUMENT_INVENTORY.md` §3, 2026-11-11)
**Rule:** No recipe value in this document or in any import is invented, corrected or inferred. Findings below are observations from reading the source; counts marked "manual" must be confirmed by the automated reconciliation script before being treated as verified.

---

## 1. Source details

| Field | Value (as stated in source) |
|---|---|
| Title | DeliverIQ Kitchen SOP Manual — Token-Friendly Markdown |
| Derived from | `DeliverIQ_Kitchen_SOP_Manual.pdf` (47 pages) — **PDF not available** |
| Self-description | "faithful text extraction and structured transcription, not a recipe rewrite" |
| Status | POC draft; chef validation required before commercial service or inventory activation |
| Scope | 104 menu items |
| Portion basis | 1 standard restaurant serving |
| Units | metric (g, ml, piece) |
| Jain variants | deferred / not configured |
| Source extraction notes | 104 unique menu IDs (MENU001–MENU104); 616 ingredient lines; generic category-level methods retained as written |

Sections present: Document metadata · Global kitchen controls · Recipe card format · Menu recipes (104) · Kitchen AI inventory command SOP (appears twice: once run-on, once formatted) · Release checklist · Source extraction notes.

## 2. Limitations caused by unavailable sources

| Unavailable source | Impact | Mitigation |
|---|---|---|
| `DeliverIQ_Menu_Ingredient_Recipe_Mapping.xlsx` (deleted) | No independent ingredient master or stable ingredient IDs; no cross-file check of quantities; no second source for dish names | Generate ingredient IDs deterministically from normalized names; mark them `DERIVED_FROM_SOP`; every mapping is single-source |
| `DeliverIQ_Kitchen_Data_Consolidated.xlsx` | No menu/BOM/SOP tabs for comparison; no prices or categories from structured data | Single-source validation only; prices/categories become owner inputs (DDR-32, DDR-36) |
| `DeliverIQ_Tandoor_Recipe_Production_Standards.xlsx` | No production standards for MENU038–MENU050 | Tandoor recipes import as DRAFT like all others |
| `DeliverIQ_Kitchen_SOP_Manual.pdf` | Cannot verify Markdown transcription against the original page/card | Trust the Markdown's self-declared fidelity; page numbers from footers are preserved as references, not verified |

Consequence: reconciliation can only check the SOP **for internal consistency**. It cannot detect transcription errors relative to the PDF. This must be stated in every import report.

`data/` files #14 and #15 both assume the menu and ingredient mapping "already exist" as separate files. That assumption no longer holds (Inventory X-14).

## 3. Dish-card validation

### 3.1 Count (manual)

Card headings `### MENUnnn — Name` were read sequentially from MENU001 to MENU104 with no gaps observed. Manual count: **104 cards**.

Ad hoc reconciliation (2026-11-11) found **104 card headings with 104 unique IDs** and **616 ingredient lines** in `name: quantity unit` form. Both agree with the SOP's own extraction notes ("104 unique menu IDs (MENU001–MENU104) were detected"; "616 ingredient lines were extracted from the recipe cards"). These are reconciliation results, not script-verified; automated validation script confirmation is pending (§8.1).

### 3.2 Candidate categories

Category labels are not fields on the cards. They appear only as trailing text after page footers (for example `... Page 8 Welcome Drinks`). They are **candidate** categories requiring owner confirmation (DDR-36).

| Card range | Count | Candidate category (from footer text) |
|---|---:|---|
| MENU001–MENU012 | 12 | **None in source** — do not infer |
| MENU013–MENU025 | 13 | Welcome Drinks |
| MENU026–MENU037 | 12 | Soup |
| MENU038–MENU050 | 13 | Tandoor Starters |
| MENU051–MENU056 | 6 | Indian Starters |
| MENU057–MENU059 | 3 | Maharashtrian Starters |
| MENU060–MENU072 | 13 | Chinese Starters |
| MENU073–MENU076 | 4 | International Starters |
| MENU077–MENU088 | 12 | Salads |
| MENU089–MENU093 | 5 | Raitas |
| MENU094–MENU104 | 11 | Indian Paneer Menu |
| **Total** | **104** | |

### 3.3 Duplicate candidates — QUARANTINED

| IDs | Name | Observation | Action (DDR-13) |
|---|---|---|---|
| MENU008, MENU057 | Mini Batata Wada | Identical preparation type, portion, all 9 ingredients and quantities (Potato 120 g, Besan 35 g, Green chilli 4 g, Ginger 3 g, Turmeric powder 1 g, Mustard seeds 1 g, Curry leaves 2 g, Cooking oil 25 ml, Salt 2 g). MENU008 is in the uncategorized block; MENU057 is in Maharashtrian Starters. | Import both with own source line refs; status `QUARANTINED_DUPLICATE_CANDIDATE`; no merge, no delete |

The reconciliation script must also check for exact and normalized duplicate names and identical ingredient sets across all 104 cards. Only this pair was observed manually.

## 4. Ingredient and unit validation

### 4.1 Units observed

Only `g`, `ml` and `piece` were observed. Fractional pieces occur (Lemon 0.1–0.5 piece). No unit conversions are stated in the source; none may be assumed (for example ml ↔ g for oil, cream or sauces).

Ad hoc reconciliation (2026-11-11), pending automated validation script confirmation:

| Unit | Ingredient lines |
|---|---:|
| `g` | 483 |
| `ml` | 113 |
| `piece` | 20 |
| **Total** | **616** |

- 0 ingredient names were observed with more than one unit.
- The unit set matches the SOP's own metadata ("Units: metric (g, ml, piece)").

### 4.2 Rules for import

1. Store quantity and unit exactly as written (decimal, not float).
2. Unit must be one of `g`, `ml`, `piece`; anything else → quarantine.
3. Quantity must be > 0; missing → quarantine.
4. An ingredient name used with more than one unit across cards → quarantine all affected lines for owner review. (None observed manually; script must confirm.)
5. Ingredient-name normalization is limited to whitespace and case. Synonyms or alternates are **not** merged (see §5.2).
6. Each ingredient line keeps: source file, SHA-256, line number, card ID, original text.

## 5. Missing-component and ingredient-ambiguity register

### 5.1 Prepared components without a batch recipe

The SOP states: "Prepared components must be produced and deducted through their own batch recipes." No batch recipe cards exist for these. Dishes using them cannot reserve raw stock accurately until resolved (DDR-33).

| Component (as written) | Used in (manual) | Missing |
|---|---|---|
| Idli batter | MENU003 | Batch recipe, yield |
| Sambhar (prepared) | MENU003, MENU006 | Batch recipe, yield |
| Coconut chutney (prepared) | MENU003, MENU006 | Batch recipe, yield |
| Onion-tomato gravy (prepared) | MENU011 | Batch recipe, yield |
| Green chutney (prepared) | MENU005, MENU078, MENU079 | Batch recipe, yield |
| Tamarind chutney (prepared) | MENU078, MENU079, MENU093 | Batch recipe, yield |
| Ginger-garlic paste (prepared) | MENU038, 039, 041, 042, 044, 046, 048, 049, 064, 094, 095, 097, 098, 100 | Batch recipe, yield |
| Tandoori marinade (prepared) | MENU104 | Batch recipe, yield |

### 5.2 Composite or unspecified ingredients (buy vs make unknown)

| Ingredient (as written) | Used in (manual) | Issue |
|---|---|---|
| Tikka spice mix | MENU038, 040, 043, 046, 048, 049, 080 | Composition not specified |
| Rasam spice mix | MENU030 | Composition not specified |
| Kadhai masala | MENU096 | Composition not specified |
| Pickle spice mix | MENU042 | Composition not specified |
| Cardamom/white pepper mix | MENU039 | Composite; ratio not specified |
| Garam masala | MENU009, 047, 052 | Purchased or prepared not stated |
| Vegetable stock | MENU026, 028, 029, 031–037 | Purchased or prepared not stated |
| Salad dressing | MENU080, 087 | Composition not specified |
| Mayonnaise, Schezwan sauce, Chilli sauce, Sweet chilli sauce | Multiple | Purchased or prepared not stated |
| Farsan, Boondi, Papdi, Fried noodles, Spring roll sheets, Pav, Bread, Cookies, Soya chaap | Multiple | Assumed purchased; not stated |

### 5.3 Ambiguous ingredient entries

| Entry | Card(s) | Ambiguity | Required owner decision |
|---|---|---|---|
| Semolina / Rava | MENU002 | Two names for one item, or alternates? | Canonical name |
| Chickpeas / Chana | MENU078 | Same | Canonical name |
| Beans/cabbage mix | MENU009, 028, 034 | Composite; ratio unknown | Split or treat as one stock item |
| Peach/apricot pulp | MENU017 | Alternate or blend? | Clarify |
| Tea leaves 2 g **and** Coffee powder 2 g | MENU012 "Tea, Coffee & Cookies" | Both in one serving, or a choice? | Clarify; possibly two dishes or a customization |
| Squash concentrate | MENU021 "Choice of Squash" | Flavour unspecified; likely customization | Define flavours and stock items |
| Sweet corn vs Corn kernels | MENU036, 054, 074 vs 084, 087 | Possibly the same ingredient | Do not merge without approval |
| Cheese | MENU005, 039, 056, 072–074, 076, 085 | Type unspecified | Clarify type(s) |
| Water | Many drinks and soups | Tracked as inventory? | Decide whether non-stock |
| Lemon (fractional piece) | Many | Stock in pieces with fractions | Confirm unit for stock tracking |

### 5.4 Method and quality-text mismatches

Methods are category-level boilerplate (acknowledged in source extraction notes). Observed mismatches:

| Card(s) | Observation |
|---|---|
| MENU056 Paneer Naramdil Kebab | Uses the paneer gravy method for a kebab |
| MENU062, 064, 065, 066 | Dry/fried paneer starters carry the paneer gravy quality text |
| MENU089–MENU093 | Raitas use the salad-washing method; MENU093 Dahi Wada needs frying (lists cooking oil and urad dal) but method does not describe it |
| All cards | No per-dish cook time, temperature, marination time ("recipe's approved time" is referenced but never given) or estimated prep time |

These must be preserved as written. Kitchen Copilot must abstain on cook times and temperatures (#6 §2.1).

### 5.5 Fields required downstream but absent from source

Price, tax classification, customer description, veg/non-veg flag, spice level, customization options, estimated prep time, allergens, images, yield verification. All 104 cards. Owner input DDR-32. Note: all listed ingredients are vegetarian, but the veg flag must still be confirmed, not inferred.

### 5.6 Extraction artefacts

- Footer text `DeliverIQ Kitchen SOP | POC draft — chef validation required Page N [Category]` is appended to many `Validation:` lines. Strip it with a logged, reversible transformation; keep page number and category text as separate source attributes.
- The Kitchen AI inventory command SOP and release checklist appear twice (once concatenated into the MENU104 validation line). Import the formatted copy as document content; ignore the concatenated copy with a logged note.

## 6. Out-of-scope source content

| Source section | Decision |
|---|---|
| Kitchen AI inventory command SOP | Excluded from MVP (DDR-18). AI is read-only |
| Lots, FEFO, expiry, receiving controls | Not implemented (Kitchen requirements #4 §7.4 exclude expiry/batch tracking). Retained as Kitchen RAG knowledge after approval |
| Batch production deductions ("raw inputs deducted when the batch is produced") | Requires a batch-production workflow not in #4. Pending DDR-33; MVP treats each prepared component as a stock item until resolved |
| Temperature targets (≤ 5 °C, ≥ 60 °C) | Kitchen RAG food-handling content only after food-safety approval; source itself says "verify current local requirements" |

## 7. Reconciliation methodology (Task 5)

1. **Register** the file: path, SHA-256, size, line count, read timestamp → `ops.source_registry`. Abort if hash changes between runs without a new source version.
2. **Parse** with a deterministic line parser (no LLM). Each card yields: menu ID, name, preparation type, portion, ingredient lines (name, quantity, unit), method, quality, inventory rule, validation text, source line range.
3. **Validate structure**: every card has all eight fields; ingredient lines match `name: quantity unit`.
4. **Strip footers** with logged transformation (§5.6).
5. **Run checks** (§8). Each failure writes to `ops.ingestion_errors` with reason, card ID and line number.
6. **Stage** into `staging` tables. Nothing is written to `app` tables unless the run passes structural checks; quarantined records are loaded with a quarantine status, not dropped.
7. **Load** recipes into `app.recipe_versions` with status `DRAFT` and `recipe_components` with source line refs. Idempotent on (source hash, menu ID, line number).
8. **Report**: `reports/import_reconciliation/<run_id>.md` with counts, quarantine list, transformations and the §2 limitation statement.
9. **Re-run** produces zero new rows and an identical report.

**Execution context (2026-11-12):**
- The import runs as pipeline **P1** on the shared pipeline-runs framework (DDR-63). Run, stage, error and quality records are persisted in `ops.*` and shown in the Data Pipelines UI.
- Fault handling is demonstrated with a separate TEST-only input file of synthetic cards written from scratch, local/test only (DDR-65). It never touches SOP records.
- No SOP recipe is activated in this POC (DDR-50). Imported SOP recipes remain `DRAFT`.

## 8. Validation checks and expected report fields

| Check | SOP explicit claim | Ad hoc reconciliation (2026-11-11) | Script status |
|---|---|---|---|
| Unique menu IDs | Yes: "104 unique menu IDs (MENU001–MENU104) were detected" | 104 card headings; 104 unique IDs | Pending |
| ID sequence MENU001–MENU104, no gaps | Yes: range stated in same note | No gaps (manual reading, §3.1) | Pending |
| Ingredient lines | Yes: "616 ingredient lines were extracted from the recipe cards" | 616 lines matching `name: quantity unit` | Pending |
| Distinct ingredient names | Not stated | 115 (exact string, no normalization) | Pending |
| Units ∈ {g, ml, piece} | Yes: "Units: metric (g, ml, piece)" | g 483, ml 113, piece 20 (sum 616); no other units | Pending |
| Quantity > 0 | Not stated | — | Pending |
| Same ingredient, multiple units | Not stated | 0 observed | Pending |
| Duplicate names / identical BOMs | Not stated | 1 pair known from manual reading (MENU008/057) | Pending |
| Cards with all 8 fields | Not stated (format described in "Recipe card format") | — | Pending |
| Prepared components without batch recipe | Not stated | 8 known from manual reading (§5.1) | Pending |
| Footer artefacts stripped | Not stated | — (count to be reported) | Pending |
| Every imported row has source file + line + hash | Not applicable | — (target 100%) | Pending |
| All recipe versions status `DRAFT` | Status "POC draft" stated in metadata | — (target 104) | Pending |

### 8.1 Reconciliation method and limits

- The ad hoc counts above came from one-off line-pattern counting of the SOP Markdown on 2026-11-11 during planning. They did not come from the Task 5 automated validation script. The command text is not kept in project files.
- "115 distinct" is an exact-string count of ingredient names after removing the list marker. Near-variants (for example Sweet corn / Corn kernels, §5.3) count separately. No synonyms are merged.
- Agreement with the SOP's stated figures checks **internal consistency only**. The SOP PDF and the Excel mappings are unavailable (§2), so no cross-source verification was possible.
- These results do **not** satisfy Task 5 acceptance criteria. Every script check in §8 remains Pending until the automated validation script runs and its report (§7 step 8) is available.

## 9. Source traceability rules

- Every `recipe_versions`, `recipe_components` and derived `ingredients` row stores: `source_id`, `source_sha256`, `source_line_start`, `source_line_end`, `source_card_id`, `source_page_ref` (from footer, unverified), `import_run_id`, `imported_at`.
- Original text of each ingredient line is stored verbatim alongside parsed fields.
- Ingredient IDs derived from SOP names are marked `origin = SOP_DERIVED`.
- No row may be edited in place after import; corrections create a new recipe version with reason and approver.
- Approval transitions (DDR-10) are audited with the release-checklist sign-off they satisfy.
- Kitchen RAG chunks for recipes reference the same `recipe_version_id` and source lines.
