# Novel TTS Service Design (Qwen3-TTS)

Date: 2026-06-01
Scope: First phase design for a local LAN TTS service for novel listening.

## 1. Goals and Non-Goals

### Goals
- Run through a stable end-to-end pipeline with Qwen3-TTS-12Hz-0.6B-CustomVoice first.
- Provide asynchronous API for chapter-level generation (about 2000-3000 Chinese characters per chapter).
- Integrate with novel-workspace as API caller.
- Deploy on Windows machine with NVIDIA RTX 4090 and expose service in LAN.
- Reserve configuration and API compatibility for switching to 1.7B-CustomVoice later.

### Non-Goals (Phase 1)
- Real-time streaming playback synthesis.
- Multi-GPU scheduling.
- Cloud deployment.
- Complex auth systems (OAuth, SSO, etc.).

## 2. Constraints and Environment

- Runtime host: Windows + RTX 4090.
- Existing local services on same machine: Ollama, ComfyUI (potential GPU contention).
- Calling mode: novel-workspace sends API requests over LAN.
- Priority: ship quickly and reliably before adding advanced features.

## 3. Candidate Approaches and Trade-offs

### Approach A: Monolith API + In-process Queue + Single Worker (Recommended)
- FastAPI process serves API and owns an internal job queue.
- A single worker consumes queued jobs and runs TTS inference.

Pros:
- Fastest to deliver.
- Minimal dependencies.
- Easiest debugging path.

Cons:
- Horizontal scaling needs future refactor.

### Approach B: API + Redis + Worker (Celery/RQ)
- API process writes jobs into Redis queue.
- Separate worker process performs inference.

Pros:
- Better scaling and reliability patterns.

Cons:
- More setup and operational complexity in phase 1.

### Approach C: File-driven Batch Pipeline
- API writes task files and worker watches directories.

Pros:
- Strong replayability and batch-friendly flow.

Cons:
- Weaker API experience and status observability.

Recommendation:
- Use Approach A in phase 1, but design abstractions so migration to Approach B is low-risk.

## 4. High-level Architecture

Components:
1. API Layer
- Receives job requests from novel-workspace.
- Validates payload, enforces idempotency and rate limits.
- Exposes job status and audio download endpoints.

2. Job Manager
- Stores job metadata and lifecycle state.
- Maintains an internal queue.

3. TTS Worker (single concurrency)
- Pulls queued jobs.
- Splits chapter text into segments.
- Runs segment synthesis with Qwen3-TTS.
- Merges segment audio into one chapter file.

4. Storage
- Metadata: SQLite (phase 1).
- Audio files: local filesystem with deterministic naming.

5. Model Registry
- Maps model_id to model source, runtime options, and defaults.
- Default active model in phase 1: 0.6B-CustomVoice.
- Reserved model metadata for 1.7B.

## 5. End-to-end Data Flow

1. novel-workspace sends POST /v1/tts/jobs with chapter text and synthesis options.
2. API validates request and computes idempotency key.
3. If duplicate request, return existing job_id.
4. Otherwise create job in status queued and return job_id.
5. Worker pulls next job, marks processing.
6. Worker normalizes and splits text (target 120-220 chars/segment).
7. Worker synthesizes each segment to temp wav.
8. Worker merges segments, inserts short pauses, writes final chapter wav.
9. Worker marks job succeeded and stores audio path.
10. Caller polls GET /v1/tts/jobs/{job_id} and fetches audio when ready.

## 6. API Contract (v1)

### 6.1 Create Job
POST /v1/tts/jobs

Request body (core fields):
- request_id: string (idempotency key from caller)
- book_id: string
- chapter_id: string
- text: string (2000-3000 chars typical)
- voice_profile: string (e.g., narrator_default)
- model_id: string (default qwen3_tts_0_6b_customvoice)
- audio_format: string (wav recommended in phase 1)
- sample_rate: int (e.g., 24000)
- speed: float (optional)
- pitch: float (optional)
- volume: float (optional)
- pause_ms: int (optional)

Response:
- job_id
- status: queued
- estimated_wait_seconds (optional)

### 6.2 Query Job
GET /v1/tts/jobs/{job_id}

Response (core fields):
- job_id
- status: queued | processing | succeeded | failed
- progress: 0-100
- segments_total
- segments_done
- error_code (if failed)
- error_message (if failed)
- audio_url (if succeeded)

### 6.3 Download Audio
GET /v1/tts/jobs/{job_id}/audio

Behavior:
- succeeded: returns chapter audio stream.
- otherwise: returns 409 (not ready) or 404 (not found).

### 6.4 Optional Retry
POST /v1/tts/jobs/{job_id}/retry (phase 1 optional)

### 6.5 Service/Model Introspection
- GET /healthz
- GET /v1/models

## 7. Job State Machine

Primary states:
- queued
- processing
- succeeded
- failed

Optional extension:
- retrying

Transitions:
- queued -> processing -> succeeded
- queued -> processing -> failed
- failed -> retrying -> processing

## 8. Text Segmentation and Audio Merge Strategy

Segmentation rules:
- Prefer sentence boundaries: 。！？；
- Secondary split on ， when needed.
- Hard split if segment exceeds max threshold.

Target size:
- 120-220 Chinese chars per segment.

Audio merge:
- Generate temp wav per segment.
- Normalize sample rate/channels/bit depth.
- Add short silence (120-220 ms) between segments.
- Output single chapter wav.

## 9. Reliability, Retry, and Dedup

Dedup keys:
- request_id + chapter_id for API idempotency.
- content hash = hash(text + voice_profile + model_id + synthesis params) for output caching.

Retry policy:
- Segment-level retry up to 2 times.
- Exponential backoff (e.g., 1s, 3s).
- Fail job if critical segments keep failing.

Timeouts:
- Per-job hard timeout to avoid GPU lock-up.

## 10. Model and Config Strategy (0.6B now, 1.7B later)

Config levels:
1. Global service config
- default_model_id
- available_models
- device
- dtype
- max_concurrent_jobs

2. Model registry
- model_id -> source path/repo + defaults

3. Request-level override
- caller may pass model_id; fallback to default_model_id.

Phase 1 runtime policy:
- Preload only 0.6B model.
- Keep 1.7B in config but not loaded.
- Switch later by config change + restart, or per-request controlled rollout.

## 11. Deployment Plan (Windows + LAN)

Phase 1 deployment shape:
- Direct Python process on Windows host (avoid early CUDA container complexity).
- Bind 0.0.0.0 on a LAN port (e.g., 8008).
- Run as managed background service (Task Scheduler or NSSM style tooling).

GPU coexistence policy:
- Keep TTS worker concurrency = 1.
- Prefer off-peak chapter generation windows when other GPU-heavy services are busy.

## 12. Security and Access Control (LAN)

Minimum controls:
- API key in request header.
- Request size limit.
- Basic rate limiting.
- Optional LAN subnet allow-list.
- Do not expose local model paths in API responses.

## 13. Observability and Ops

Structured logs per request/job:
- request_id, trace_id, job_id, book_id, chapter_id, model_id, status, duration_ms.

Core metrics:
- job success rate
- avg chapter generation time
- queue wait time
- retries count
- sampled GPU memory peak (log-based in phase 1)

Health checks:
- process alive
- model loaded
- queue consumable

## 14. Data Model (Phase 1 Suggestion)

jobs table:
- job_id (PK)
- request_id
- book_id
- chapter_id
- status
- model_id
- voice_profile
- params_json
- text_hash
- segments_total
- segments_done
- audio_path
- error_code
- error_message
- created_at
- updated_at

Optional segments table (future):
- job_id
- segment_index
- segment_text
- status
- retry_count
- duration_ms

## 15. Testing Strategy (Phase 1)

Must-pass checks:
1. API contract tests
- Create job, query status, download audio happy path.

2. Idempotency test
- Same request_id + chapter_id returns same job_id.

3. Retry test
- Inject synthetic segment failure and confirm retry behavior.

4. Throughput sanity test
- Sequential 5-10 chapters in queue; all complete without crash.

5. Compatibility test
- Validate model_id fallback and unknown model rejection.

## 16. Incremental Roadmap

Phase 1 (now):
- Async chapter-level generation with 0.6B stable path.

Phase 2:
- Upgrade queue abstraction (optional Redis worker split).
- Add 1.7B rollout controls.

Phase 3:
- Add streaming inference/playback endpoint.
- Add richer voice controls and quality presets.

## 17. Risks and Mitigations

Risk: GPU contention with Ollama/ComfyUI.
Mitigation: single worker, scheduling policy, queue backpressure.

Risk: Long chapter latency.
Mitigation: segmentation, progress reporting, async polling model.

Risk: Duplicate requests from caller retries.
Mitigation: strict idempotency and output cache hash.

## 18. Acceptance Criteria

- API caller can submit chapter text and receive job_id.
- Job transitions to succeeded for normal 2000-3000 char chapters.
- Output audio can be downloaded over LAN.
- Failures surface with actionable error fields.
- Configuration includes 1.7B model reservation without changing API contract.

## 19. Open Decisions Deferred to Implementation Plan

- Exact TTS library invocation wrapper and model loading lifecycle.
- Precise folder naming conventions for audio artifacts.
- Final auth header naming and key rotation policy.
- Choice of audio post-processing library.
