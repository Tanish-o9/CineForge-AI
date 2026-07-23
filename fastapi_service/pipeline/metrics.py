from prometheus_client import Counter, Histogram, Gauge

# 1. Histogram for per-stage duration
STAGE_DURATION = Histogram(
    'cineforge_pipeline_stage_duration_seconds',
    'Duration of generation pipeline stages in seconds',
    ['stage_name']
)

# 2. Counter for per-stage execution status
STAGE_STATUS = Counter(
    'cineforge_pipeline_stage_total',
    'Total count of pipeline stages executed by status',
    ['stage_name', 'status'] # status: success, failure, retry
)

# 3. Gauges for Queue depth and GPU resource gauges
QUEUE_DEPTH = Gauge(
    'cineforge_queue_depth',
    'Number of pending tasks in Celery message broker queues'
)

ACTIVE_GPU_WORKERS = Gauge(
    'cineforge_active_gpu_workers',
    'Number of active GPU workers processing render pipelines'
)

# 4. Counter for external API calls cost tracking
EXTERNAL_API_CALLS = Counter(
    'cineforge_external_api_calls_total',
    'Total count of external API requests executed',
    ['service_name'] # service_name: OpenAI, ElevenLabs, Replicate
)
