from __future__ import annotations

from ai.feedfoundry_agents.schemas import FeedFoundryJobInput, RepositoryManifestOutput


def run_repository_manifest_librarian(job: FeedFoundryJobInput) -> RepositoryManifestOutput:
    slug = job.asset_slug
    creator = job.creator_slug
    llms = f"# {creator}\n> Creator archive (FeedFoundry)\n\n## Episodes\n- ./{slug}/hosted_manifest.json\n"
    llms_full = (
        f"# {creator} — expanded machine context\n"
        f"## Policy\n- No URL ingestion in V1; uploads only.\n"
        f"## Episode {slug}\n"
        f"- Manifest fields: canonical_title, summary, chapters, outputs_available, derived_from.\n"
    )
    return RepositoryManifestOutput(llms_txt_candidate=llms, llms_full_txt_candidate=llms_full)
