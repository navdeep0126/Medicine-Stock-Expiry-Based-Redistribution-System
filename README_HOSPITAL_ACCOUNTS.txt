MEDICINE STOCK & EXPIRY-BASED REDISTRIBUTION SYSTEM — UPDATED PROJECT

WHAT CHANGED IN THIS UPDATE
- Removed the LIVE · TEST DB header badge and the informational DSA banners from Inventory,
  Redistribution Requests and Eligible Medicine Sources pages. The mobile Menu button remains
  available on narrow screens so the navigation remains usable.
- Inventory can create a new medicine while adding its first batch. Enter a new Medicine ID and
  Medicine Name; after the batch saves successfully, the medicine appears in the catalogue.
- Availability is calculated automatically instead of being manually selected:
    * Positive quantity and future expiry date: Available
    * Quantity zero: Out of Stock
    * Expiry date before today: Expired
  New batches must start with at least one unit. Editing an existing batch can reduce its quantity
  to zero. Expired batches are retained for tracking but excluded from redistribution.
- The facilities directory lets a system administrator add a facility and create its active
  hospital login together. The account is active immediately; no approval/review step is required.
  Hospitals can also self-register through register.html.
- Facility-specific inventory ownership rules remain in the backend. A hospital account can change
  only its own batches; eligible stock remains visible across the signed-in hospital network.
- Dashboard loading now displays an API error rather than spinning indefinitely if a request fails.

DSA PRESERVATION RULE
The existing DSA implementation files have not been modified in this update:
- main.py
- facility_connection_graph.py
- medicine_batch_greedy.py
- medicine_batch_insertion_sort.py
- medicine_batch_linear_search.py
- medicine_batch_linked_list.py
- redistribution_request_queue.py

TECHNOLOGY
Python, Flask, MySQL and a static HTML/CSS/JavaScript frontend.
The web API calls the existing DSA classes; it does not replace their algorithms.

SAFETY
This web application is configured to run only against medicine_redistribution_test_db.
Do not expose the local development server to the public internet. A real medicine transfer requires
appropriate authorization, handling, quality, storage and regulatory checks.

SETUP (VS CODE POWERSHELL)
1. Extract this ZIP into a new folder or back up your existing project first.
2. Open a terminal in the project root: the folder containing main.py and web_api.py.
3. Install dependencies:
   python -m pip install -r .\requirements-web.txt
4. Initialize the hospital account table and persistent request ordering:
   python .\setup_hospital_accounts.py
   Enter your MySQL password at the hidden prompt if MEDICINE_DB_PASSWORD is not already set.
   The script targets only medicine_redistribution_test_db. It adds queue_order if it is missing,
   fills queue order for old requests and does not delete inventory, request or transaction records.
5. Start the backend:
   powershell -ExecutionPolicy Bypass -File .\run_web_api.ps1
6. Keep the terminal open and browse to:
   http://127.0.0.1:5000/login.html
7. Register a hospital or sign in to an existing account.

USAGE
- Inventory: view shared network stock; add batches, choose an existing medicine or enter a new
  Medicine ID and name; status is derived from quantity and expiry. Hospitals can change only their
  own stock. To add a facility, use Healthcare Facilities if signed in as the system administrator,
  or use hospital self-registration.
- Requests: submit redistribution requests. The persistent queue processes outstanding requests in
  queue order; an unfulfilled pending request may move to the back so other pending requests can be
  attempted. Completed and partial outcomes are kept in history.
- Eligible Medicine Sources: view suitable stock candidates and suggested quantities.
- Transaction History: review saved transfer transactions.
- Healthcare Facilities: search facilities; administrators can create a facility and its active account.
- To stop Flask, press Ctrl+C in the terminal running the server.

TROUBLESHOOTING
- If setup says a file cannot be found, verify the terminal is in the folder containing main.py,
  web_api.py, setup_hospital_accounts.py and run_web_api.ps1.
- If the dashboard says Unknown column 'queue_order', stop Flask and run setup_hospital_accounts.py
  against the test database before starting the server again.
- If /api/health does not report ok=true and database=medicine_redistribution_test_db, check MySQL
  credentials and confirm the test database and the original inventory/request/transaction tables exist.
- Do not reset the database to solve a missing-column or API problem.
