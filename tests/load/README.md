# Load Tests

This directory contains load and stress tests for the DICOM Gateway to measure throughput, latency, and system behavior under load.

## Test Files

### `test_throughput.py`
Tests for measuring throughput (files per second):
- `test_receive_throughput` - C-STORE receive throughput
- `test_forward_throughput` - C-STORE forward throughput
- `test_concurrent_receive_throughput` - Concurrent receive operations

### `test_latency.py`
Tests for measuring latency (response times):
- `test_receive_latency` - C-STORE receive latency (mean, median, P95, P99)
- `test_forward_latency` - C-STORE forward latency
- `test_file_io_latency` - File I/O read/write latency

### `test_database_pool.py`
Tests for database connection pool behavior:
- `test_pool_connection_acquisition` - Connection acquisition under load
- `test_pool_saturation` - Behavior when pool is exhausted
- `test_pool_concurrent_queries` - Concurrent query execution
- `test_pool_connection_reuse` - Connection reuse verification
- `test_pool_metrics_under_load` - Metrics collection under load

### `test_stress.py`
Stress tests for extreme load conditions:
- `test_sustained_load` - Sustained load over extended period
- `test_burst_load` - Burst load (many files at once)
- `test_memory_usage` - Memory usage under load

## Running Load Tests

### Prerequisites

1. **Dependencies installed**:
   ```bash
   pip install -r requirements.txt
   pip install psutil  # For memory tests
   ```

2. **Test database**: Tests use in-memory SQLite for most operations

3. **System resources**: Load tests require significant CPU and memory

### Run All Load Tests

```bash
# Run all load tests
pytest tests/load/ -v -m load

# Run with markers
pytest tests/load/ -v -m "load and slow"
```

### Run Specific Test File

```bash
# Test throughput
pytest tests/load/test_throughput.py -v

# Test latency
pytest tests/load/test_latency.py -v

# Test database pool
pytest tests/load/test_database_pool.py -v

# Test stress
pytest tests/load/test_stress.py -v
```

### Run Specific Test

```bash
pytest tests/load/test_throughput.py::TestThroughput::test_receive_throughput -v
```

### Run with Performance Profiling

```bash
# With coverage
pytest tests/load/ -v --cov=dicom_gw --cov-report=html

# With timing
pytest tests/load/ -v --durations=10
```

## Performance Benchmarks

The load tests include assertions for minimum performance thresholds. Adjust these based on your requirements:

### Throughput Targets
- **Receive**: > 10 files/second
- **Forward**: > 5 files/second
- **Concurrent Receive**: > 15 files/second

### Latency Targets
- **Receive Mean**: < 1000ms
- **Receive P95**: < 2000ms
- **Forward Mean**: < 2000ms
- **Forward P95**: < 5000ms
- **File I/O Read**: < 10ms
- **File I/O Write**: < 50ms

### Database Pool Targets
- **Connection Acquisition**: All connections acquired successfully
- **Saturation**: Proper handling when pool is exhausted
- **Concurrent Queries**: All queries execute successfully
- **Connection Reuse**: Connections properly reused

## Test Results

Load tests print detailed results including:
- Throughput (files/second)
- Latency statistics (mean, median, P95, P99)
- Success/failure rates
- Memory usage
- Connection pool metrics

## Troubleshooting

### Tests Fail with Timeout

If tests timeout:
- Increase timeout values in test code
- Check system resources (CPU, memory)
- Reduce test load (fewer files, shorter duration)

### Low Throughput

If throughput is lower than expected:
- Check system resources
- Verify network configuration
- Review database connection pool settings
- Check for resource contention

### High Latency

If latency is higher than expected:
- Check disk I/O performance
- Verify database query performance
- Review network latency
- Check for resource bottlenecks

### Memory Issues

If memory usage is high:
- Check for memory leaks
- Review file handling (proper cleanup)
- Verify connection pool cleanup
- Check for large object retention

## Continuous Integration

Load tests are marked with `@pytest.mark.load` and `@pytest.mark.slow` markers. In CI:

```bash
# Skip load tests in CI (faster)
pytest -v -m "not load"

# Run load tests separately
pytest tests/load/ -v -m load
```

## Notes

- Load tests may take several minutes to complete
- Tests use temporary files and directories
- Mock SCP servers are created for forward testing
- Database pool tests require a real database connection
- Memory tests require `psutil` package

