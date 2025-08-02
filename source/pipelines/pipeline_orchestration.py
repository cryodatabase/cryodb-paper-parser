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
    extract_experiments,
    extract_formulations,                                            # NEW
)
from pipelines.ingest.staging import copy_json
from pipelines.ingest.merge_agents import merge_agents
# ── timing helper  (put near the top of your file) ──────────────────
from contextlib import contextmanager
import time, logging
from distiller.schemas.papers import PaperStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
@contextmanager
def timed(label: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        logging.info(f"[TIMER] {label:<35} {dt:6.2f} s")


def run_pipeline(files: list[str], source_files: str, config: PipelineConfig):

    if config.distiller == "llama_parse" and config.llm_model_parser == "gpt-4.1-mini":
        for md5_hash, fulltext in extract_fulltext_llama_parse(files, source_files):
            with timed("0‑update_metadata"):
                paper_id = update_metadata_from_fulltext(md5_hash, fulltext)
                if paper_id is None:
                    print(f"[ERROR] Failed to update metadata for {md5_hash}")
                    update_workflow_status(md5_hash, PaperStatus.FAILED)
                    continue

        # ── Agents ───────────────────────────────────────────────
            with timed("1‑extract_agents"):
                agents = extract_agents(fulltext)
                if agents is None:
                    print(f"[ERROR] Failed to extract agents for {md5_hash}")
                    update_workflow_status(md5_hash, PaperStatus.FAILED)
                    continue
            with timed("1a‑merge_agents"):
                agent_rows = agents.get("agents", [])
                if agent_rows:
                    copy_json(agent_rows, "staging_cpa_chemicals")
                    merge_agents(agent_rows)

        # ── Agent‑level props ───────────────────────────────────
            with timed("2‑extract_agent_props"):
                props = extract_agent_properties(fulltext)
            with timed("2a‑insert_agent_props"):
                if props:
                    insert_agent_properties(paper_id, props)

        # ── Experiments ─────────────────────────────────────────
            with timed("3‑extract_experiments"):
                experiments = extract_experiments(fulltext)
            with timed("3a‑insert_experiments"):
                if experiments is not None:
                    print(f'[TRACE] experiments: {experiments}')
                    insert_experiments(md5_hash, experiments)
                    with timed("4‑extract_formulations"):
                        formulations = extract_formulations(fulltext,experiments)
                    with timed("4a‑insert_formulations"):
                        if formulations:
                            print(f'[TRACE] formulations: {formulations}')
                            insert_formulations(md5_hash, formulations, experiments)
                else:
                    print(f"[ERROR] Failed to extract experiments for {md5_hash}")
                    update_workflow_status(md5_hash, PaperStatus.FAILED)

    if config.distiller == "llama_parse" and config.llm_model_parser == "claude-sonnet-4-20250514":

        for md5_hash, fulltext in extract_fulltext_llama_parse(files, source_files):
            paper_id = update_metadata_from_fulltext(md5_hash, fulltext)
            if paper_id is None:
                print(f"[ERROR] Failed to update metadata for {md5_hash}")
                update_workflow_status(md5_hash, PaperStatus.FAILED)
                continue

        # ── Agents ───────────────────────────────────────────────
            agents = extract_agents(fulltext, llm_model=config.llm_model_parser)
            if agents is None:
                print(f"[ERROR] Failed to extract agents for {md5_hash}")
                update_workflow_status(md5_hash, PaperStatus.FAILED)
                continue
            
            print(f'[TRACE] agents: {agents}')
            agent_rows = agents.get("agents", [])
            if agent_rows:
                copy_json(agent_rows, "staging_cpa_chemicals")
                merge_agents(agent_rows)
        # ── Agent‑level props ───────────────────────────────────
            props = extract_agent_properties(fulltext, llm_model=config.llm_model_parser)
            if props:
                insert_agent_properties(paper_id, props)
        # ── Experiments ─────────────────────────────────────────
            experiments = extract_experiments(fulltext, llm_model=config.llm_model_parser)
            if experiments is not None:
                print(f'[TRACE] experiments: {experiments}')
                insert_experiments(md5_hash, experiments)
                formulations = extract_formulations(fulltext,experiments, llm_model=config.llm_model_parser)
                if formulations:
                    print(f'[TRACE] formulations: {formulations}')
                    insert_formulations(md5_hash, formulations, experiments)
                else:
                    print(f"[ERROR] Failed to extract formulations for {md5_hash}")
                    update_workflow_status(md5_hash, PaperStatus.FAILED)