from deepeval.dataset import EvaluationDataset
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric
from deepeval import assert_test
import pytest

dataset = EvaluationDataset()
dataset.pull(alias="firstdataset")
for golden in dataset.goldens:
    test_case = LLMTestCase(
        input=golden.input,
        actual_output="test"
        context=golden.context,
        expected_output=golden.expected_output,
    )
    dataset.add_test_case(test_case)

@pytest.mark.parametrize("test_case", dataset.test_cases)
def test_llm_app(test_case: LLMTestCase):
    assert_test(test_case=test_case, metrics=[AnswerRelevancyMetric()])