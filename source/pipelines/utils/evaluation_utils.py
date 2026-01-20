from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import HallucinationMetric
from pydantic import BaseModel

class LLMResult(BaseModel):
    prompt: str
    output: str
    model_name: str
HALLUCINATION = HallucinationMetric(threshold=0.5)

def evaluate_hallucination(fulltext: str, llm_res: LLMResult, component_extracted: str) -> float:

    test_case_name = f"hallucination_{llm_res.model_name}_{component_extracted}"
    tc = LLMTestCase(
        input          = llm_res.prompt,
        actual_output  = llm_res.output,
        context        = [fulltext],
        name=test_case_name
    )
    result = evaluate(metrics=[HALLUCINATION], test_cases=[tc])
    ## help me to know the result of the evaluation (i do not know what type of data is)
    print(f'[DEEPEVAL] RESULTS: NAME: {result.name}, SUCESS: {result.success}, metrics_data: {result.metrics_data}')
    return result
