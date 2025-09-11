from deepeval.dataset import EvaluationDataset
from deepeval.test_case import LLMTestCase
from deepeval import assert_test
import pytest
from deepeval.metrics import HallucinationMetric
from distiller.schemas.extraction_passes import ExperimentPass, FormulationPass
import os
from distiller.utils.llm_extraction import extract_experiments
from distiller.utils.llm_extraction import extract_formulations_all_experiments as extract_formulations
import json
import time
from deepeval.prompt import Prompt
from metrics.recall import FORMULATIONS_RECALL, EXPERIMENTS_RECALL, FORMULATIONS_ROLE_RECALL, EXPERIMENTS_CORRESPONDENCE
# Define hallucination
HALLUCINATION = HallucinationMetric(threshold=0.5)

# Load API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# Pulling prompts from confident-ai studio dashboard
prompt = Prompt(alias="experiments_extraction")
prompt.pull()

formulations_prompt = Prompt(alias="formulations_extraction")
formulations_prompt.pull()

dataset_experiments_extraction = EvaluationDataset()
dataset_experiments_extraction.pull(alias="experiments_extraction")

dataset_formulations_extraction = EvaluationDataset()
dataset_formulations_extraction.pull(alias="formulations_extraction")

# ── timing helpers ───────────────────────────────────────────────
exp_times: list[float] = []
form_times: list[float] = []
process_start = time.perf_counter()




# ── experiments extraction ───────────────────────────────────────
for idx, golden in enumerate(dataset_experiments_extraction.goldens, 1):

    experiments_prompt = prompt.interpolate(
        SCHEMA=ExperimentPass.model_json_schema(),
        PAPER_TEXT=golden.context
    )


    # measure experiments extraction
    t0 = time.perf_counter()
    output_experiments = extract_experiments(golden.context, "claude-sonnet-4-20250514", experiments_prompt)
    exp_dur = time.perf_counter() - t0
    exp_times.append(exp_dur)



    # per-case timing log
    print(f"Case {idx}: exp {exp_dur:.2f}s, total {exp_dur:.2f}s")

    str_output_experiments = json.dumps(output_experiments)
    test_case_experiments = LLMTestCase(
        input=experiments_prompt,
        actual_output=str_output_experiments,
        context=golden.context,
        expected_output=golden.expected_output
    )
    dataset_experiments_extraction.add_test_case(test_case_experiments)


for idx, golden in enumerate(dataset_formulations_extraction.goldens, 1):
    formulations_prompt_interpolate = formulations_prompt.interpolate(
        SCHEMA=FormulationPass.model_json_schema(),
        EXPERIMENTS=golden.custom_column_key_values['experiments'],
        PAPER_TEXT=golden.context
    )
    # measure formulations extraction
    t0 = time.perf_counter()
    output_formulations = extract_formulations(golden.context, output_experiments, "claude-sonnet-4-20250514", formulations_prompt_interpolate)
    form_dur = time.perf_counter() - t0
    form_times.append(form_dur)

    str_output_formulations = json.dumps(output_formulations)
    test_case_formulations = LLMTestCase(
        input=formulations_prompt_interpolate,
        actual_output=str_output_formulations,
        context=golden.context,
        expected_output=golden.expected_output
    )
    dataset_formulations_extraction.add_test_case(test_case_formulations)

# ── print timing summary ─────────────────────────────────────────
print("\n### TIMING SUMMARY ###")
print(f"Total runtime: {time.perf_counter() - process_start:.2f} s")
if exp_times:
    print(f"  Experiments extraction – avg: {sum(exp_times)/len(exp_times):.2f}s, max: {max(exp_times):.2f}s, min: {min(exp_times):.2f}s")
if form_times:
    print(f"  Formulations extraction – avg: {sum(form_times)/len(form_times):.2f}s, max: {max(form_times):.2f}s, min: {min(form_times):.2f}s")

    
@pytest.mark.parametrize("test_case_experiments", dataset_experiments_extraction.test_cases)
def test_evaluate_experiments(test_case_experiments: LLMTestCase):
    print("RUNNING TEST")
    print(f"Input: {test_case_experiments.input[:120]}")
    print(f"Expected Output: {test_case_experiments.expected_output[:120]}")
    assert_test(test_case=test_case_experiments, metrics=[HALLUCINATION, EXPERIMENTS_RECALL, EXPERIMENTS_CORRESPONDENCE])

@pytest.mark.parametrize("test_case_formulations", dataset_formulations_extraction.test_cases)
def test_evaluate_formulations(test_case_formulations: LLMTestCase):
    print("RUNNING TEST")
    print(f"Input: {test_case_formulations.input[:120]}")
    print(f"Expected Output: {test_case_formulations.expected_output[:120]}")
    assert_test(test_case=test_case_formulations, metrics=[HALLUCINATION, FORMULATIONS_RECALL, FORMULATIONS_ROLE_RECALL])