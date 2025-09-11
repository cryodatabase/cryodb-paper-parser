from pipelines.extract.llama_parse import extract_fulltext as extract_fulltext_llama_parse
from pipelines.utils.paper_utils import update_metadata_from_fulltext
from pipelines.utils.pipeline_utils import update_workflow_status
from pipelines.post_processing.agent_property_ingest import insert_agent_properties
from pipelines.post_processing.experiment_ingest import insert_experiments
from pipelines.post_processing.formulation_ingest import insert_formulations   # NEW
from distiller.schemas.pipeline_config import PipelineConfig
from distiller.utils.llm_extraction import (
    extract_agents,
    extract_agent_properties,
    extract_experiments,                                           # NEW
)
from distiller.utils.llm_extraction import extract_formulations_all_experiments as extract_formulations
from pipelines.ingest.staging import copy_json
from pipelines.ingest.merge_agents import merge_agents
from pipelines.post_processing.evaluation.playground import run_evaluation
from contextlib import contextmanager
import time, logging
from distiller.schemas.papers import PaperStatus
import uuid
from pipelines.utils.file_utils import save_json
from pipelines.utils.evaluation_utils import evaluate_hallucination
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
from deepeval.test_case import LLMTestCase
from deepeval.metrics import HallucinationMetric
from deepeval.dataset import EvaluationDataset
from deepeval import evaluate

HALLUCINATION = HallucinationMetric(threshold=0.5)
@contextmanager
def timed(label: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        logging.info(f"[TIMER] {label:<35} {dt:6.2f} s")

# Pulling prompts from confident-ai studio dashboard



def run_pipeline(files: list[str], source_files: str, config: PipelineConfig):

    if config.distiller == "llama_parse" and "gpt-5-2025-08-07" in config.llm_model_parser:
        for md5_hash, fulltext in extract_fulltext_llama_parse(files, source_files, config=config):
            if config.playground_enabled:
                json_uuid = md5_hash
                paper_id = update_metadata_from_fulltext(md5_hash, fulltext)
                agents, llm_res_agents = extract_agents(fulltext, llm_model="gpt-4.1-mini")
                props = extract_agent_properties(fulltext, llm_model="gpt-4.1-mini")
                experiments = extract_experiments(fulltext, llm_model="gpt-4.1-mini")
                formulations = extract_formulations(fulltext, experiments, llm_model="gpt-4.1-mini")
                save_json({"paper_id": [str(paper_id)]}, json_uuid, "gpt-4.1-mini")
                save_json({"agents": agents}, json_uuid, "gpt-4.1-mini")
                save_json({"agents_properties": props}, json_uuid, "gpt-4.1-mini")
                save_json({"experiments": experiments}, json_uuid, "gpt-4.1-mini")
                save_json({"formulations": formulations}, json_uuid, "gpt-4.1-mini")

            else:
                with timed("0‑update_metadata"):
                    paper_id = update_metadata_from_fulltext(md5_hash, fulltext)
                    if paper_id is None:
                        print(f"[ERROR] Failed to update metadata for {md5_hash}")
                        update_workflow_status(md5_hash, PaperStatus.FAILED)
                        continue

            # ── Agents ───────────────────────────────────────────────
                with timed("1‑extract_agents"):
                    agents = extract_agents(fulltext, llm_model="gpt-4.1-mini")
                    if agents is None:
                        print(f"[ERROR] Failed to extract agents for {md5_hash}")
                        update_workflow_status(md5_hash, PaperStatus.FAILED)
                        continue
                with timed("1a‑merge_agents"):
                    agent_rows = agents.get("agents", [])
                    if agent_rows:
                        copy_json(agent_rows, "staging_cpa_chemicals")
                        agents_inserted = merge_agents(agent_rows)
            # ── Agent‑level props ───────────────────────────────────
                with timed("2‑extract_agent_props"):
                    props = extract_agent_properties(fulltext, llm_model="gpt-4.1-mini")
                with timed("2a‑insert_agent_props"):
                    if props:
                        insert_agent_properties(paper_id, props)
                        save_json({"agents_properties": props}, json_uuid, "gpt-4.1-mini")

            # ── Experiments ─────────────────────────────────────────
                with timed("3‑extract_experiments"):
                    experiments = extract_experiments(fulltext, llm_model="gpt-4.1-mini")
                with timed("3a‑insert_experiments"):
                    if experiments is not None:
                        print(f'[TRACE] experiments: {experiments}')
                        insert_experiments(md5_hash, experiments)
                        save_json({"experiments": experiments}, json_uuid, "gpt-4.1-mini")
                        with timed("4‑extract_formulations"):
                            formulations = extract_formulations(fulltext, experiments, llm_model="gpt-4.1-mini")
                        with timed("4a‑insert_formulations"):
                            if formulations:
                                print(f'[TRACE] formulations: {formulations}')
                                insert_formulations(md5_hash, formulations, experiments)
                                save_json({"formulations": formulations}, json_uuid, "gpt-4.1-mini")
                    else:
                        print(f"[ERROR] Failed to extract experiments for {md5_hash}")
                        update_workflow_status(md5_hash, PaperStatus.FAILED)

    #how to review in the entire config.llm_model_parser list[str]

    if config.distiller == "llama_parse" and "claude-sonnet-4-20250514" in config.llm_model_parser:
        all_test_cases = []
        dataset = EvaluationDataset()
        for paper_id, md5_hash, fulltext in extract_fulltext_llama_parse(files, source_files, config=config):

            if config.playground_enabled:
                json_uuid = md5_hash
                save_json({"paper_id": [str(paper_id)]}, json_uuid, "claude-sonnet-4-20250514")
                agents = extract_agents(fulltext, llm_model="claude-sonnet-4-20250514")
                all_test_cases.append(tc_agents)
                props = extract_agent_properties(fulltext, llm_model="claude-sonnet-4-20250514")
                all_test_cases.append(tc_props)
                experiments = extract_experiments(fulltext, llm_model="claude-sonnet-4-20250514")
                all_test_cases.append(tc_experiments)
                formulations = extract_formulations(fulltext, experiments, llm_model="claude-sonnet-4-20250514")
                all_test_cases.append(tc_formulations)
                #save_json({"agents": agents}, json_uuid, "claude-sonnet-4-20250514")
                #save_json({"agents_properties": props}, json_uuid, "claude-sonnet-4-20250514")
                #save_json({"experiments": experiments}, json_uuid, "claude-sonnet-4-20250514")
                #save_json({"formulations": formulations}, json_uuid, "claude-sonnet-4-20250514")
            else:
                paper_id = update_metadata_from_fulltext(md5_hash, fulltext)
                if paper_id is None:
                    print(f"[ERROR] Failed to update metadata for {md5_hash}")
                    update_workflow_status(md5_hash, PaperStatus.FAILED)
                    continue

            # ── Agents ───────────────────────────────────────────────
                agents = extract_agents(fulltext, llm_model="claude-sonnet-4-20250514")
                if agents is None:
                    print(f"[ERROR] Failed to extract agents for {md5_hash}")
                    update_workflow_status(md5_hash, PaperStatus.FAILED)
                    continue
                
                print(f'[TRACE] agents: {agents}')
                agent_rows = agents.get("agents", [])
                if agent_rows:
                    copy_json(agent_rows, "staging_cpa_chemicals")
                    agents_inserted = merge_agents(agent_rows)
            # ── Agent‑level props ───────────────────────────────────
                props = extract_agent_properties(fulltext, llm_model="claude-sonnet-4-20250514")
                print(f"[TRACE] PROPERTIES: {props}")
                if props:
                    insert_agent_properties(paper_id, props)
            # ── Experiments ─────────────────────────────────────────
                experiments = extract_experiments(fulltext, llm_model="claude-sonnet-4-20250514")
                if experiments is not None:
                    insert_experiments(md5_hash, experiments)
                    formulations = extract_formulations(fulltext,experiments, llm_model="claude-sonnet-4-20250514")
                    if formulations:
                        print(f'[TRACE] formulations: {formulations}')
                        insert_formulations(md5_hash, formulations, experiments)
                        if config.playground_enabled:
                            run_evaluation(
                            extractor_model=config.llm_model_parser,
                            agents=agents,
                            props=props,
                            experiments=experiments,
                            formulations=formulations,
                            judge_model="test",
                        )
                            update_workflow_status(md5_hash, PaperStatus.COMPLETED)
                        else:
                            print(f"[TRACE] Playground evaluation is disabled.")
                            update_workflow_status(md5_hash, PaperStatus.COMPLETED)
                    else:
                        print(f"[ERROR] Failed to extract formulations for {md5_hash}")
                        update_workflow_status(md5_hash, PaperStatus.FAILED)