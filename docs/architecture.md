# Architecture

## Scope

SceneProof evaluates AI video production runs from evidence rather than from a single task-status
field. The current vertical slice is intentionally narrow:

1. Load and validate a generation manifest.
2. Create an immutable run directory.
3. Execute a provider-neutral generation adapter.
4. Save the manifest snapshot and artifact hashes.
5. Inspect media files through `ffprobe`.
6. Render a concise terminal summary or JSON.

## Boundaries

- `sceneproof.media` owns FFmpeg executable interaction and media metadata parsing.
- `sceneproof.models` owns manifest and run-record contracts.
- `sceneproof.ledger` owns run directory creation and artifact hashing.
- `sceneproof.providers` owns platform-specific generation behavior.
- `sceneproof.cli` owns command-line input and output. It does not parse FFprobe payloads.
- Future platform adapters will own vendor-specific HTTP behavior.
- Future validators will consume domain objects instead of raw FFprobe dictionaries.

## Design constraints

- All subprocess calls use argument lists and never a shell.
- Media paths are resolved before probing and must reference regular files.
- External command failures become a single project-specific error type at the boundary.
- Run identifiers and case identifiers are restricted before they are used as path components.
- Provider failures still produce a failed run record with partial artifacts and evidence.
- Artifact paths, file sizes, MIME types, and SHA-256 hashes are persisted.
- JSON output is designed for CI and downstream report generation.
- Deterministic validators are added before AI-based quality evaluation.

## Next slices

1. Add a deterministic validator pipeline over the run artifacts.
2. Add version comparison and HTML/Markdown reports.
3. Add an HTTP adapter for authorized platform APIs.
4. Add multimodal evaluation with evidence citations and human review.

