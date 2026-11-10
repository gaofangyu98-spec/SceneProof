# Architecture

## Scope

SceneProof evaluates AI video production runs from evidence rather than from a single task-status
field. The first vertical slice is intentionally narrow:

1. Accept a local media file.
2. Invoke `ffprobe` without a shell.
3. Parse selected container and stream metadata into stable domain objects.
4. Render either a concise terminal summary or JSON.

## Boundaries

- `sceneproof.media` owns FFmpeg executable interaction and media metadata parsing.
- `sceneproof.cli` owns command-line input and output. It does not parse FFprobe payloads.
- Future platform adapters will own vendor-specific HTTP behavior.
- Future validators will consume domain objects instead of raw FFprobe dictionaries.

## Design constraints

- All subprocess calls use argument lists and never a shell.
- Media paths are resolved before probing and must reference regular files.
- External command failures become a single project-specific error type at the boundary.
- JSON output is designed for CI and downstream report generation.
- Deterministic validators are added before AI-based quality evaluation.

## Next slices

1. Persist a generation run manifest and artifacts.
2. Add a deterministic validator pipeline.
3. Add version comparison and HTML/Markdown reports.
4. Add a provider-neutral adapter with a mock provider.
5. Add multimodal evaluation with evidence citations and human review.

