[DVA] [02:56:01] [Phase] Processing Started
[DVA] [02:56:01] [MEM] BEFORE AGGREGATION (EXISTING) — RSS: 178.3 MB
Requirement validation failed: File type not detected — run Detection phase first; No schema detected — run Canonical phase first
[DVA] [02:56:01] [Phase] Canonical Dataset — building (store, template=minimal)
[DVA] [02:56:01] [Phase] Canonical Dataset — building (store, template=minimal)
[DVA] [02:56:01] [Phase] Canonical Dataset — building (item, template=minimal)
[DVA] [02:56:01] [Phase] Canonical Dataset — building (item, template=minimal)
BAU stream_store_aggregate failed: 
Traceback (most recent call last):
  File "C:\Users\armu6001\Documents\DVA_Data_Parser\DVA_Data_Parser\dav_tool\operations\workflow_ops.py", line 111, in execute
    result, elapsed = future.result(timeout=600)
                      ~~~~~^^^^^^^^^^^^^
  File "C:\Users\armu6001\AppData\Local\Python\pythoncore-3.14-64\Lib\concurrent\futures\_base.py", line 452, in result
    raise TimeoutError()
TimeoutError
store aggregation failed
Traceback (most recent call last):
  File "C:\Users\armu6001\Documents\DVA_Data_Parser\DVA_Data_Parser\dav_tool\workflow\processing.py", line 51, in _aggregate_via_dataset
    result = aggregate_dataset(dataset, source=dataset_source)
  File "C:\Users\armu6001\Documents\DVA_Data_Parser\DVA_Data_Parser\dav_tool\_aggregators.py", line 163, in aggregate_dataset
    return _aggregate_store_stream(stream)
  File "C:\Users\armu6001\Documents\DVA_Data_Parser\DVA_Data_Parser\dav_tool\_aggregators.py", line 232, in _aggregate_store_stream
    for chunk in stream:
                 ^^^^^^
  File "C:\Users\armu6001\Documents\DVA_Data_Parser\DVA_Data_Parser\dav_tool\workflow\canonical.py", line 154, in iter_chunks
    yield from self._stream_factory()
  File "C:\Users\armu6001\Documents\DVA_Data_Parser\DVA_Data_Parser\dav_tool\_parsers.py", line 590, in canonical_chunk_stream
    yield lazy.collect(engine="streaming")
          ~~~~^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\armu6001\Documents\DVA_Data_Parser\DVA_Data_Parser\.venv\Lib\site-packages\polars\_utils\deprecation.py", line 97, in wrapper
    return function(*args, **kwargs)
  File "C:\Users\armu6001\Documents\DVA_Data_Parser\DVA_Data_Parser\.venv\Lib\site-packages\polars\lazyframe\opt_flags.py", line 361, in wrapper
    return function(*args, **kwargs)
  File "C:\Users\armu6001\Documents\DVA_Data_Parser\DVA_Data_Parser\.venv\Lib\site-packages\polars\lazyframe\frame.py", line 2624, in collect
    return wrap_df(ldf.collect(engine, callback))
                   ~~~~~^^^^^^^^^^^^^^^^^^
OSError: The paging file is too small for this operation to complete. (os error 1455)
memory allocation of 953106064 bytes failed
note: run with RUST_BACKTRACE=1 environment variable to display a backtrace
