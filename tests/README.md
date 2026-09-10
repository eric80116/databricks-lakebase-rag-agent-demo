# Test suite (#14)

End-to-end verification of the deployed Sentiva RAG demo. Each test maps to a
requirement so a failure pinpoints the broken component.

## Prereqs
- The demo deployed (bootstrap + deploy.sh) and the ingest job run at least once.
- Databricks CLI configured with the profile in `config.env` (`PROFILE`).
- Python: `pip install pytest` (tests use only stdlib + the databricks CLI).

## Run
```bash
pytest tests/ -v
```

## Coverage
| Test | Requirement |
|---|---|
| test_embedding_endpoint_1024 | #8 embedding (Qwen3, 1024-dim) |
| test_gateway_llm_responds | #9 LLM via Unity AI Gateway |
| test_inference_table_logs | #10 gateway usage tracking + inference table |
| test_pipeline_tables_populated | #6/#7 JSON+PDF → Delta pipeline |
| test_lakebase_kb_loaded | #5 KB chunks |
| test_app_a_health / test_app_b_serves | #2/#11 apps |
| test_agent_chat_grounded | #2 end-to-end RAG (retrieval+LLM+grounding) |
| test_agent_memory_multiturn | #4 Lakebase memory |
| test_otel_spans_in_uc / test_otel_per_step_timing | #3 MLflow OTel traces in UC |
