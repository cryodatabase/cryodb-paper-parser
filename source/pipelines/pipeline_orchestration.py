from pipelines.extract.llama_parse import extract_fulltext as extract_fulltext_llama_parse
from pipelines.utils.paper_utils import update_metadata_from_fulltext, get_cpa_facts_from_fulltext
from pipelines.post_processing.cpa_ingest import store_cpa_data
from distiller.schemas.pipeline_config import PipelineConfig


def run_pipeline(files: list[str], source_files: str, config: PipelineConfig):
    if config.distiller == "llama_parse" and config.llm_model_parser == "gpt-4.1-mini":
        for md5_hash, fulltext in extract_fulltext_llama_parse(files, source_files):
            update_metadata_from_fulltext(md5_hash, fulltext)
            status = get_cpa_facts_from_fulltext(md5_hash)

            # Post-processing
            if status == "FAILED":
                continue
            store_cpa_data(md5_hash)

    else:
        raise ValueError(f"Unknown distiller: {config.distiller}")