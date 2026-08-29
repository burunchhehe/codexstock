# CodexStock architecture boundaries

`stock_suite_app.py` remains a compatibility composition root while routes move
into bounded `*_http.py` modules. New endpoints must not be added directly to
the large `do_GET` or `do_POST` chains. Each extracted group keeps its existing
path and response schema and receives dependencies from the composition root.

- `native_api_http.py`: native research and logic routes
- `local_api_security.py`: same-origin and JSON write protection
- `startup_policy.py`: clean-install safe mode
- `api_contracts.py`: data provenance and real-order eligibility

Architecture cleanup must never relax live-trading gates or migrate private
runtime ledgers automatically.
