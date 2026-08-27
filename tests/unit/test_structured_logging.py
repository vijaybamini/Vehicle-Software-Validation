from vehicle_validation.automation.logging import StructuredLogger


def test_structured_logger_writes_and_reads_jsonl(tmp_path) -> None:
    logger = StructuredLogger(tmp_path / "validation.jsonl")

    logger.write("diagnostic.failure", {"test_name": "startup", "fault": "none"})

    records = logger.read_recent()
    assert records[0]["event"] == "diagnostic.failure"
    assert records[0]["payload"]["test_name"] == "startup"
