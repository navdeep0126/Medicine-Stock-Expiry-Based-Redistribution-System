# MediRedistribute frontend

This folder contains the static HTML, CSS and JavaScript interface served by `web_api.py`.

- The Flask backend serves this folder and exposes the live API.
- The app uses MySQL records from `medicine_redistribution_test_db`; browser localStorage is not the source of truth.
- Sign-in is required to view the application and shared network stock.
- Hospitals can update only batches owned by their facility.
- Requests are processed by the Python DSA code through the global FIFO queue.

Start from the project root with `powershell -ExecutionPolicy Bypass -File .\run_web_api.ps1`.
See `README_START_HERE.txt` in the project root for setup instructions.
