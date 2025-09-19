from deepeval.metrics import GEval  # or CustomMetric, according to your setup
from deepeval.test_case import LLMTestCaseParams

EXPERIMENTS_RECALL = GEval(
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    name="experiments_recall",
    threshold=0.89,
    criteria="""
Goal: Compute experiment-level recall by comparing actual output vs expected output.

Parameters used: actual output, expected output.
Parameters NOT used: input, retrieval context, context, tools called, expected tools.

What counts as a match (one-to-one):
Treat two experiment objects as the same underlying experiment when, taken together, they describe the same biological target and experimental procedure, regardless of IDs or section headers.

Biological target equivalence: same organ and (if present) same species. If a field is missing on one side, don’t penalize; if both present and disagree, treat as non-match.

Procedure equivalence: the type of operation (e.g., cooling vs warming) and the technique (e.g., perfusion cooling, liquid-nitrogen plunge, dry-ice/methanol slush, electrolyte bath warming, gas-circulation rewarm, diathermy, super-cooling) are semantically the same even if phrased differently. Prefer semantic meaning over surface words.

Ignore: object id, section names, numbering, and minor wording differences.

Include evidence from method, quote, and any structured fields (e.g., dependent_properties) to judge equivalence.

Filter: exclude any item with performed_in_this_paper=false on either side from consideration. If the field is missing, assume it’s performed.

One-to-one constraint: a single actual item may satisfy at most one expected item. If an actual looks like a merged description of multiple expected experiments, count only one true positive; the rest stay false negatives.

What to compute:
Let E be the set of expected experiments and A the set of actual experiments (after the filter). Build a one-to-one alignment between E and A that maximizes the number of semantically equivalent pairs. Then:

TP = number of matched pairs.

FN = |E| − TP.

FP = |A| − TP.

Recall = TP / (TP + FN).
    """
)

FORMULATIONS_RECALL = GEval(
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    name="formulations_recall",
    threshold=0.84,
    criteria="""
Goal: Compute formulation-level recall by comparing actual output vs expected output (per SCHEMA FORMULATIONS).

Parameters used: actual output, expected output.
Parameters NOT used: input, retrieval context, context, tools called, expected tools.

Objects to compare:
- Each side is a FormulationPass with a 'formulations' array. If the wrapper is missing, treat the top-level as the array.
- Ignore non-semantic IDs and ordering: formulation_id, component_id, and array order do not matter.

What counts as a match (one-to-one):
Treat two formulations as the same underlying formulation when, taken together, they describe the same chemical composition (identity + role + amount) used in the same context, regardless of IDs or section headers.

Composition equivalence (all must hold):
1) Component identity: For every expected component with role ∈ {CPA, ADJUVANT}, there exists a corresponding actual component with the same chemical.
   - Prefer agent_id (InChIKey) when present; if both sides have agent_id and they disagree, treat as non-match.
   - If agent_id is missing on either side, match by label using common synonyms/abbreviations (e.g., "DMSO" ≡ "dimethyl sulfoxide"; "EG" ≡ "ethylene glycol"; "PEG-400" ≡ "polyethylene glycol 400"). Case/punctuation do not matter.

2) Role agreement: Roles must match (CPA vs ADJUVANT vs CARRIER). If the chemical appears under a different role, treat as non-match.

3) Amount agreement: Amounts must be numerically consistent after unit normalization.
   - point vs point: values match within tolerance (±5% relative OR, if unit is "%", ±0.5 percentage points; use the larger tolerance).
   - point vs range: the point lies within the range (allow the same tolerance on the endpoints).
   - range vs range: ranges overlap (any non-empty intersection).
   - Accept common unit synonyms/conversions:
       • "%" ≡ "percent". Distinguish v/v vs w/v unless the quote/context explicitly equates them.
       • M, mM, µM where 1000 µM = 1 mM and 1000 mM = 1 M.
       • mg/mL ↔ % w/v using 1% w/v = 10 mg/mL; g/L ↔ % w/v using 1% w/v = 10 g/L.
       • µL/mL ↔ % v/v using 1% v/v = 10 µL/mL.
     If unit is missing on one side, use the quote as evidence; if still unclear but the numeric clearly corresponds under a standard conversion, consider it a match.

4) Carrier handling: Differences in CARRIER components (e.g., water, PBS, base buffer/solvent) do not prevent a match as long as all CPA and ADJUVANT components and their amounts match. Treat "q.s. to 100%" / "balance to 100%" / "to volume" as implicit. If the expected explicitly specifies a numeric carrier ratio (e.g., "EG:water 60:40"), require approximate agreement under the same tolerances.

Additional equivalence signals (supporting, not required):
- Formulation label (e.g., "VS55", "M22", "DP6"). Exact/synonymous labels strengthen a match but are not mandatory.
- Dependent properties (e.g., LOADING_TEMPERATURE, TOXICITY) and the formulation-level quote can be used to disambiguate near-duplicates; they need not match exactly.
- experiment_id may be used to break ties when two expected formulations have identical composition. If both sides provide experiment_id and they conflict, prefer pairings where experiment_id agrees.

Ignore for matching:
- formulation_id, component_id, free-text notes, minor wording, and array ordering.
- Exact quote wording/length; use quotes only as evidence for identity, units, and amounts.

One-to-one constraint:
- Build a one-to-one alignment between expected and actual formulations that maximizes the number of matches. A single actual formulation may satisfy at most one expected formulation. If an actual object merges multiple expected formulations, count only one true positive; the remaining expected items remain false negatives.

What to compute:
Let E be the set of expected formulations and A the set of actual formulations (exclude any item with an empty components list).
TP = number of matched pairs under the rules above.
FN = |E| − TP.
FP = |A| − TP.
Recall = TP / (TP + FN).
"""
)

FORMULATIONS_ROLE_RECALL = GEval(
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    name="formulations_role_recall",
    threshold=0.88,
    criteria="""
Goal: Compute component-level recall for component ROLES (CPA, ADJUVANT, CARRIER) while being SUPerset‑tolerant. Extra components present in the actual output MUST NOT reduce recall. Only the roles of components that appear in the expected output are scored.
 
Parameters used: actual output, expected output.
Parameters NOT used: input, retrieval context, context, tools called, expected tools.

Population to score:
- E_components = all components across all formulations in the expected output.
- Only components in E_components are eligible for scoring; any additional components present in the actual output are ignored for both alignment and scoring (no penalties).

Two-stage evaluation:

Step 1 — Align formulations (superset‑tolerant, role‑recall friendly)
- Find a one‑to‑one alignment between expected and actual formulations that maximizes the number of expected components that can be role‑scored as True Positives (TP).
- Candidate matching rules (apply in order):
  1) Prefer pairs with the same experiment_id when both sides specify it.
  2) Superset condition: an actual formulation is a valid candidate for an expected formulation if EVERY expected CPA/ADJUVANT component (by chemical identity) is present in the actual formulation (amount‑compatible per normalization below). Actual MAY contain extra components (including carriers, buffer constituents, other adjuvants) — these MUST NOT invalidate the match.
  3) Carriers are OPTIONAL for alignment unless the expected formulation explicitly includes a carrier; if expected includes a carrier, the actual must include the same carrier (identity‑compatible) to satisfy the candidate match. If the expected does NOT include a carrier, the presence/absence of carriers in the actual is ignored for alignment.
  4) Tie‑breakers across multiple candidates (in order): 
     a) more matched expected components; 
     b) higher Jaccard overlap using only the expected component set; 
     c) same or closer experiment_id label match.
- Amount normalization used ONLY for Step 1 candidacy (NOT for Step 2 scoring):
  • Treat “x” and “×” as equivalent. 
  • Treat “%” and “vol%” as equivalent when context indicates v/v. 
  • “X% A in B” in actual is compatible with expected that lists carrier B at (100−X)% (remainder rule), and vice‑versa. 
  • For carriers, consider “1×”, “proportion 1.0”, or umbrella strengths (e.g., “0.1 M cacodylate buffer”) mutually compatible for alignment if the carrier identity matches.
  • Minor formatting differences (spacing, case, unicode symbols like μ) are ignored.

Step 2 — Align and score components within matched pairs (roles only; extras ignored)
- For each aligned expected–actual formulation pair, align components ONE‑TO‑ONE by chemical identity (role is NOT used for alignment at this step):
  Identity matching rules (apply in order):
  • If both sides provide agent_id (InChIKey), require exact equality (case‑insensitive). 
  • Otherwise match by label using common synonyms/abbreviations (case/punctuation/spacing ignored). Examples: “FBS” ≡ “fetal bovine serum”; “P/S” ≡ “penicillin‑streptomycin”; “HB‑HBSS” ≡ “HEPES‑buffered HBSS”.
  • For combined antibiotics: a single actual component labeled “penicillin‑streptomycin”, “P/S”, or equivalent abbreviations may satisfy identity for both expected “penicillin” and “streptomycin” components (count as two identity matches if roles qualify).
- Scoring (roles only):
  • True Positive (TP): an expected component whose identity is matched in the actual AND whose role exactly equals the expected role (“CPA”, “ADJUVANT”, or “CARRIER”).
  • False Negative (FN): every expected component that is not a TP (parent formulation unmatched; or identity not found; or role differs).
- Explicitly ignore for scoring:
  • Any actual components that are not in the expected set (no penalties).
  • Amount values and units (already handled for alignment only).
  • Quotes, notes, component_id, formulation_id, array order.

What to compute:
- TP = total number of True Positives over E_components.
- FN = |E_components| − TP.
- Recall = TP / (TP + FN) = TP / |E_components|.

Edge cases & clarifications:
- Extra components in actual (e.g., internal buffer constituents like HEPES, CaCl₂) NEVER reduce recall.
- If expected lacks a carrier but actual includes one, this does NOT affect recall.
- If expected includes a carrier and actual omits it (or assigns a different role), that expected carrier is an FN.
- When multiple expected formulations are identical in composition but differ by experiment_id, alignment remains one‑to‑one; experiment_id equality is a strong preference but not mandatory if compositionally identical and unambiguous.

"""
)

EXPERIMENTS_CORRESPONDENCE = GEval(
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    name="experiments_correspondence",
    threshold=0.95,  # A higher threshold is typical for correspondence/F1-style metrics
    criteria="""
Goal: Compute a strict experiment-level correspondence score. The score must be 1.0 only if there is a perfect one-to-one relationship between the actual and expected experiments, penalizing both missing (recall) and extra (precision) items.

Parameters used: actual output, expected output.
Parameters NOT used: input, retrieval context, context, tools called, expected tools.

What counts as a match (one-to-one):
Treat two experiment objects as the same underlying experiment when, taken together, they describe the same biological target and experimental procedure, regardless of IDs or section headers. This matching logic is identical to experiment-level recall.

- **Biological target equivalence**: same organ and (if present) same species. If a field is missing on one side, don’t penalize; if both present and disagree, treat as non-match.
- **Procedure equivalence**: the type of operation (e.g., cooling vs warming) and the technique (e.g., perfusion cooling, liquid-nitrogen plunge) are semantically the same.
- **Ignore**: object id, section names, numbering, and minor wording differences.
- **Evidence**: Include evidence from method, quote, and any structured fields.
- **Filter**: Exclude any item with performed_in_this_paper=false on either side. If the field is missing, assume it’s performed.
- **One-to-one constraint**: A single actual item may satisfy at most one expected item.

What to compute:
Let E be the set of expected experiments and A be the set of actual experiments (after the filter). Build a one-to-one alignment between E and A that maximizes the number of semantically equivalent pairs. Then, define the following counts:

- **TP (True Positives)** = number of matched pairs.
- **FN (False Negatives)** = |E| − TP. This represents the number of expected experiments that were missed.
- **FP (False Positives)** = |A| − TP. This represents the number of actual experiments that were incorrectly extracted or are duplicates.

The final score is the Jaccard Index (Intersection over Union), which measures the similarity between the two sets:

**Score = TP / (TP + FN + FP)**

A score of 1.0 is achieved only when FN = 0 and FP = 0, meaning the set of actual experiments is identical to the set of expected experiments.
"""
)
CARRIER_RECALL = GEval(
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    name="carrier_recall",
    threshold=0.85,
    criteria="""
Goal
Compute a component-level recall metric restricted to the role CARRIER, with superset tolerance and one-to-one formulation alignment. The score is perfect (1.0) only when, for every aligned formulation pair, all expected CARRIER components are present in the actual and labeled with role 'CARRIER'.

Parameters used: actual output, expected output.
Parameters NOT used: input, retrieval context, context, tools called, expected tools.

Population to score
- E_carriers = the set of all components across all expected formulations whose role == 'CARRIER'.
- Only components in E_carriers are eligible for scoring. Non-carrier components are used only to help align formulations; they are never scored.
- Extra components in the actual output (including extra carriers) are ignored for scoring (no penalties).

Two-stage evaluation

Step 1 — Align formulations (superset‑tolerant, carrier‑recall friendly)
Build a one‑to‑one alignment between expected and actual formulations that maximizes the number of expected carriers that can become True Positives (TP).

Candidate matching rules (apply in order):
  1) Prefer pairs with the same experiment_id when both sides specify it.
  2) Superset anchor using NON‑CARRIER components: an actual formulation is a valid candidate for an expected formulation if EVERY expected CPA/ADJUVANT component (by identity; see normalization below) is present in the actual. The actual may contain extra components (including carriers, buffers, salts) — these NEVER invalidate candidacy.
  3) If an expected formulation has no CPA/ADJUVANT components (i.e., only carriers are listed), then candidacy is based on carrier identity: an actual formulation is a candidate if it contains at least one of the expected carriers (identity‑compatible). If no such actual exists, leave the expected formulation unmatched.
  4) Tie‑breakers across multiple candidates (in order): 
     a) more matched expected non‑carrier components; 
     b) higher Jaccard overlap using only the expected component set; 
     c) same or closer experiment_id label match.

Amount/format normalization for Step 1 candidacy ONLY (NOT used for Step 2 scoring):
  • Treat “x” and “×” as equivalent.
  • Treat “%” and “vol%” as equivalent when context indicates v/v.
  • Remainder rule: “X% A in B” is compatible with an expected that lists carrier B at (100−X)% (and vice‑versa).
  • For carriers/buffers, treat “1×”, “1x”, “proportion 1.0”, and umbrella strengths (e.g., “0.1 M cacodylate buffer”) as mutually compatible for alignment if the carrier identity matches.
  • Minor formatting differences (spacing, case, unicode symbols like μ/H₂O) are ignored.

Step 2 — Align and score components within matched pairs (CARRIERS only; extras ignored)
For each aligned expected–actual formulation pair, align components ONE‑TO‑ONE by chemical identity (role is NOT used for alignment at this step). Only expected carriers are considered for alignment and scoring.

Identity matching rules (apply in order):
  • If both sides provide agent_id (e.g., InChIKey), require exact equality (case‑insensitive).
  • Otherwise match by label using common synonyms/abbreviations (case/punctuation/spacing ignored). Examples:
      “PBS” ≡ “phosphate‑buffered saline”; 
      “HBSS” ≡ “Hanks’ balanced salt solution”; 
      “H2O” ≡ “water” ≡ “ddH2O” ≡ “Milli‑Q water”; 
      “HEPES‑buffered HBSS” ≡ “HB‑HBSS”.
  • Carrier umbrella strengths and presentation variants are identity‑compatible (e.g., “PBS pH 7.4” ≡ “PBS”, “0.1 M cacodylate buffer” ≡ “cacodylate buffer 0.1M”).

Scoring (carriers only):
  • True Positive (TP): an expected carrier whose identity is matched in the actual AND whose role in the actual is exactly “CARRIER”.
  • False Negative (FN): every expected carrier that is not a TP (parent formulation unmatched; or identity not found; or role differs).
  
Explicitly ignore for scoring:
  • All expected non‑carrier components, and any actual components not in E_carriers (no penalties).
  • Amount values and units (handled only for alignment).
  • Quotes, notes, component_id, formulation_id, array order.

What to compute:
  • TP = total number of True Positives over E_carriers.
  • FN = |E_carriers| − TP.
  • Recall = TP / (TP + FN) = TP / |E_carriers|.

Edge cases & clarifications:
  • Extra components in actual (including extra carriers, salts, buffer constituents like HEPES, CaCl₂) NEVER reduce recall.
  • If expected lacks carriers entirely (|E_carriers| = 0), define Recall = 1.0 by convention.
  • If expected includes a carrier and actual omits it or assigns a different role, that expected carrier is an FN.
  • When multiple expected formulations are identical in composition but differ by experiment_id, alignment remains one‑to‑one; experiment_id equality is a strong preference but not mandatory if compositionally identical and unambiguous.
"""
)
