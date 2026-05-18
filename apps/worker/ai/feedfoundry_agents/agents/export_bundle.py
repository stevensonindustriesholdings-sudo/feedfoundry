from __future__ import annotations

from ai.feedfoundry_agents.schemas import ExportBundleHintsOutput, FeedFoundryJobInput


def run_export_bundle_assembler(job: FeedFoundryJobInput) -> ExportBundleHintsOutput:
    names = [
        "transcript.json",
        "chapters.json",
        "factsheet.json",
        "faq.json",
        "metadata.json",
        "ctas.json",
        "hosted_manifest.json",
        "bundle_index.json",
    ]
    return ExportBundleHintsOutput(
        artefact_filenames=names,
        index_notes=["Deterministic index — aligns with worker stub output contract."],
    )
