
from datetime import date, timedelta

from main import (
    MedicineBatch,
    MedicineInventory,
    RedistributionRequest,
    RedistributionRequestQueue,
    FacilityConnectionGraph,
    MedicineBatchLinearSearch,
    MedicineBatchInsertionSort,
    MedicineRedistributionGreedy,
    get_expiry_label,
    NEAR_EXPIRY_DAYS,
    TRANSACTION_RECORDS,
)


def expect_value_error(description, operation):
    try:
        operation()
    except ValueError:
        print(f"PASS: {description} was rejected.")
        return

    raise AssertionError(f"FAIL: {description} was not rejected.")


def create_test_graph():
    graph = FacilityConnectionGraph()
    graph.add_connection("F004", "F001")
    graph.add_connection("F004", "F002")
    return graph


def allocate_test_request(inventory, request):
    """Search current inventory and allocate stock for one request."""
    suitable = MedicineBatchLinearSearch.search(
        inventory, request, create_test_graph()
    )
    sorted_batches = MedicineBatchInsertionSort.sort_by_expiry(suitable)

    return MedicineRedistributionGreedy.allocate_medicine(
        request, sorted_batches, inventory
    )


def test_partial_fulfillment():
    print("\nTEST 1: Partial fulfillment")

    inventory = MedicineInventory()
    inventory.add_batch(
        MedicineBatch(
            "TEST_B001", "TEST_M001", "Test Medicine", "F001",
            5, (date.today() + timedelta(days=120)).isoformat(),
            "Available",
        )
    )

    request = RedistributionRequest(
        "TEST_R001", "F004", "TEST_M001", "Test Medicine", 10
    )

    suitable = MedicineBatchLinearSearch.search(
        inventory, request, create_test_graph()
    )
    sorted_batches = MedicineBatchInsertionSort.sort_by_expiry(suitable)

    transaction_count = len(TRANSACTION_RECORDS)
    try:
        status = MedicineRedistributionGreedy.allocate_medicine(
            request, sorted_batches, inventory
        )
    finally:
        del TRANSACTION_RECORDS[transaction_count:]

    assert status == "Partially Fulfilled"
    assert request.total_allocated == 5
    assert request.remaining_quantity == 5
    assert inventory.find_batch("TEST_B001").quantity == 0

    print("PASS: Partial fulfillment works correctly.")


def test_no_eligible_batches():
    print("\nTEST 2: No eligible batches")

    inventory = MedicineInventory()

    inventory.add_batch(
        MedicineBatch(
            "TEST_B002", "TEST_M002", "Expired Medicine", "F001",
            10, (date.today() - timedelta(days=1)).isoformat(),
            "Available",
        )
    )

    inventory.add_batch(
        MedicineBatch(
            "TEST_B003", "TEST_M002", "Unavailable Medicine", "F002",
            10, (date.today() + timedelta(days=120)).isoformat(),
            "Unavailable",
        )
    )

    request = RedistributionRequest(
        "TEST_R002", "F004", "TEST_M002", "Test Medicine", 5
    )

    suitable = MedicineBatchLinearSearch.search(
        inventory, request, create_test_graph()
    )
    assert suitable == []

    transaction_count = len(TRANSACTION_RECORDS)
    try:
        status = MedicineRedistributionGreedy.allocate_medicine(
            request, suitable, inventory
        )
    finally:
        del TRANSACTION_RECORDS[transaction_count:]

    assert status == "Pending"
    assert request.total_allocated == 0
    assert request.remaining_quantity == 5
    assert inventory.find_batch("TEST_B002").status == "Expired"
    assert inventory.find_batch("TEST_B003").status == "Unavailable"

    print("PASS: Expired and unavailable batches were excluded.")


def test_invalid_medicine_inputs():
    print("\nTEST 3: Invalid medicine inputs")

    future_date = (date.today() + timedelta(days=120)).isoformat()

    expect_value_error(
        "Negative medicine quantity",
        lambda: MedicineBatch(
            "TEST_V001", "TEST_M003", "Test Medicine",
            "F001", -5, future_date, "Available"
        ),
    )

    expect_value_error(
        "Decimal medicine quantity",
        lambda: MedicineBatch(
            "TEST_V002", "TEST_M003", "Test Medicine",
            "F001", 2.5, future_date, "Available"
        ),
    )

    expect_value_error(
        "Invalid expiry-date format",
        lambda: MedicineBatch(
            "TEST_V003", "TEST_M003", "Test Medicine",
            "F001", 5, "31-12-2027", "Available"
        ),
    )

    print("PASS: Invalid medicine inputs were rejected.")


def test_duplicate_batch_id():
    print("\nTEST 4: Duplicate batch ID")

    inventory = MedicineInventory()
    future_date = (date.today() + timedelta(days=120)).isoformat()

    inventory.add_batch(
        MedicineBatch(
            "TEST_DUP001", "TEST_M004", "Test Medicine",
            "F001", 10, future_date, "Available"
        )
    )

    expect_value_error(
        "Duplicate batch ID",
        lambda: inventory.add_batch(
            MedicineBatch(
                "TEST_DUP001", "TEST_M005", "Another Medicine",
                "F002", 5, future_date, "Available"
            )
        ),
    )

    assert len(inventory.get_all_batches()) == 1
    print("PASS: Duplicate batch was not added.")


def test_invalid_request_quantities():
    print("\nTEST 5: Invalid request quantities")

    expect_value_error(
        "Zero request quantity",
        lambda: RedistributionRequest(
            "TEST_R003", "F004", "TEST_M006", "Test Medicine", 0
        ),
    )

    expect_value_error(
        "Negative request quantity",
        lambda: RedistributionRequest(
            "TEST_R004", "F004", "TEST_M006", "Test Medicine", -3
        ),
    )

    expect_value_error(
        "Decimal request quantity",
        lambda: RedistributionRequest(
            "TEST_R005", "F004", "TEST_M006", "Test Medicine", 2.5
        ),
    )

    print("PASS: Invalid request quantities were rejected.")


def test_valid_input():
    print("\nTEST 6: Valid input")

    inventory = MedicineInventory()
    future_date = (date.today() + timedelta(days=120)).isoformat()

    batch = MedicineBatch(
        "TEST_VALID001", "TEST_M007", "Valid Medicine",
        "F001", 10, future_date, "Available"
    )
    inventory.add_batch(batch)

    request = RedistributionRequest(
        "TEST_R006", "F004", "TEST_M007", "Valid Medicine", 5
    )

    assert inventory.find_batch("TEST_VALID001") is batch
    assert request.requested_quantity == 5

    print("PASS: Valid medicine and request were accepted.")


def test_expiry_sorting():
    print("\nTEST 7: Insertion Sort by expiry date")

    inventory = MedicineInventory()

    for batch_id, expiry in [
        ("B003", "2027-01-15"),
        ("B002", "2026-12-10"),
        ("B001", "2026-11-05"),
    ]:
        inventory.add_batch(
            MedicineBatch(
                batch_id, "TEST_SORT", "Test Medicine", "F001",
                10, expiry, "Available"
            )
        )

    original_order = [
        batch.batch_id for batch in inventory.get_all_batches()
    ]

    sorted_batches = MedicineBatchInsertionSort.sort_by_expiry(
        inventory.get_all_batches()
    )

    assert [batch.batch_id for batch in sorted_batches] == [
        "B001", "B002", "B003"
    ]
    assert [
        batch.batch_id for batch in inventory.get_all_batches()
    ] == original_order

    print("PASS: Earliest expiry is prioritized.")
    print("PASS: Original inventory order is unchanged.")

    equal_date_batches = [
        MedicineBatch(
            batch_id, "TEST_SORT", "Test Medicine", "F001",
            10, "2026-12-10", "Available"
        )
        for batch_id in ["B003", "B001", "B002"]
    ]

    tied_order = [
        batch.batch_id
        for batch in MedicineBatchInsertionSort.sort_by_expiry(
            equal_date_batches
        )
    ]

    assert tied_order == ["B001", "B002", "B003"]
    print("PASS: Equal expiry dates use alphabetical batch IDs.")


def test_linear_search_and_facility_connections():
    print("\nTEST 8: Linear Search and facility connections")

    inventory = MedicineInventory()
    future_date = (date.today() + timedelta(days=120)).isoformat()
    expired_date = (date.today() - timedelta(days=1)).isoformat()

    test_batches = [
        ("TEST_L001", "TEST_M008", "F001", 10, future_date, "Available"),
        ("TEST_L002", "TEST_OTHER", "F001", 10, future_date, "Available"),
        ("TEST_L003", "TEST_M008", "F003", 10, future_date, "Available"),
        ("TEST_L004", "TEST_M008", "F004", 10, future_date, "Available"),
        ("TEST_L005", "TEST_M008", "F002", 10, expired_date, "Available"),
        ("TEST_L006", "TEST_M008", "F002", 10, future_date, "Unavailable"),
        ("TEST_L007", "TEST_M008", "F002", 0, future_date, "Available"),
    ]

    for batch_id, medicine_id, facility_id, quantity, expiry, status in test_batches:
        inventory.add_batch(
            MedicineBatch(
                batch_id, medicine_id, "Search Medicine", facility_id,
                quantity, expiry, status
            )
        )

    request = RedistributionRequest(
        "TEST_R008", "F004", "TEST_M008", "Search Medicine", 5
    )

    suitable = MedicineBatchLinearSearch.search(
        inventory, request, create_test_graph()
    )

    assert [batch.batch_id for batch in suitable] == ["TEST_L001"]
    assert inventory.find_batch("TEST_L005").status == "Expired"
    assert inventory.find_batch("TEST_L006").status == "Unavailable"
    assert inventory.find_batch("TEST_L007").status == "Out of Stock"

    print("PASS: Correct medicine was found.")
    print("PASS: Unconnected facility was excluded.")
    print("PASS: Destination's own stock was excluded.")
    print("PASS: Expired, unavailable, and zero-stock batches were excluded.")


def test_fifo_queue():
    print("\nTEST 9: FIFO Queue behaviour")

    queue = RedistributionRequestQueue()

    assert queue.is_empty()
    assert queue.peek_request() is None
    assert queue.remove_request() is None

    print("PASS: Empty queue is handled safely.")

    request1 = RedistributionRequest(
        "TEST_QUEUE_R001", "F004", "TEST_M010", "Medicine A", 10
    )
    request2 = RedistributionRequest(
        "TEST_QUEUE_R002", "F004", "TEST_M011", "Medicine B", 20
    )
    request3 = RedistributionRequest(
        "TEST_QUEUE_R003", "F004", "TEST_M012", "Medicine C", 15
    )

    queue.add_request(request1)
    queue.add_request(request2)
    queue.add_request(request3)

    assert not queue.is_empty()
    assert queue.peek_request() is request1

    print("PASS: The first request added is at the front.")

    assert queue.remove_request() is request1
    assert queue.peek_request() is request2

    print("PASS: First request was removed; second is now first.")

    assert queue.remove_request() is request2
    assert queue.remove_request() is request3

    print("PASS: All requests were removed in FIFO order.")

    assert queue.is_empty()
    assert queue.peek_request() is None
    assert queue.remove_request() is None

    print("PASS: Queue behaves correctly after becoming empty.")


def test_greedy_allocation():
    print("\nTEST 10: Greedy Allocation")

    inventory = MedicineInventory()

    inventory.add_batch(
        MedicineBatch(
            "TEST_GREEDY_A", "TEST_M020", "Greedy Test Medicine",
            "F001", 7,
            (date.today() + timedelta(days=30)).isoformat(),
            "Available",
        )
    )

    inventory.add_batch(
        MedicineBatch(
            "TEST_GREEDY_B", "TEST_M020", "Greedy Test Medicine",
            "F002", 8,
            (date.today() + timedelta(days=90)).isoformat(),
            "Available",
        )
    )

    request = RedistributionRequest(
        "TEST_GREEDY_R001", "F004", "TEST_M020",
        "Greedy Test Medicine", 12
    )

    suitable = MedicineBatchLinearSearch.search(
        inventory, request, create_test_graph()
    )
    sorted_batches = MedicineBatchInsertionSort.sort_by_expiry(suitable)

    assert [
        batch.batch_id for batch in sorted_batches
    ] == ["TEST_GREEDY_A", "TEST_GREEDY_B"]

    transaction_count = len(TRANSACTION_RECORDS)

    try:
        status = MedicineRedistributionGreedy.allocate_medicine(
            request, sorted_batches, inventory
        )

        assert status == "Fulfilled"
        assert request.total_allocated == 12
        assert request.remaining_quantity == 0
        assert inventory.find_batch("TEST_GREEDY_A").quantity == 0
        assert inventory.find_batch("TEST_GREEDY_B").quantity == 3

        new_transactions = TRANSACTION_RECORDS[transaction_count:]
        assert len(new_transactions) == 2

        print("PASS: Earliest-expiring batch was prioritized.")
        print("PASS: 7 tablets were taken from Batch A.")
        print("PASS: 5 tablets were taken from Batch B.")
        print("PASS: Request for 12 tablets was fulfilled.")
        print("PASS: Remaining source stock is correct.")
        print("PASS: Two allocation transaction records were created.")

    finally:
        del TRANSACTION_RECORDS[transaction_count:]


def test_near_expiry_threshold():
    print("\nTEST 11: Near-expiry threshold (60 days)")

    today = date.today()

    cases = [
        ("Already expired", -1, "EXPIRED"),
        ("Expires today", 0, "NEAR-EXPIRY"),
        ("Expires in 20 days", 20, "NEAR-EXPIRY"),
        ("Exactly 60 days left", 60, "NEAR-EXPIRY"),
        ("61 days left", 61, "Normal"),
        ("90 days left", 90, "Normal"),
    ]

    assert NEAR_EXPIRY_DAYS == 60
    print("PASS: Configured near-expiry threshold is 60 days.")

    for description, days_remaining, expected_label in cases:
        expiry = (today + timedelta(days=days_remaining)).isoformat()
        actual_label = get_expiry_label(expiry)

        assert actual_label.startswith(expected_label), (
            f"{description}: expected {expected_label!r}, "
            f"received {actual_label!r}"
        )

        print(f"PASS: {description} -> {actual_label}")

    inventory = MedicineInventory()

    near_expiry_batch = MedicineBatch(
        "TEST_NEAR001", "TEST_M030", "Near Expiry Test Medicine",
        "F001", 10, (today + timedelta(days=20)).isoformat(),
        "Available",
    )
    inventory.add_batch(near_expiry_batch)

    assert get_expiry_label(near_expiry_batch.expiry_date).startswith(
        "NEAR-EXPIRY"
    )
    assert near_expiry_batch.status == "Available"

    print("PASS: Near-expiry warning does not change Available status.")

    boundary_batch = MedicineBatch(
        "TEST_NEAR002", "TEST_M030", "Boundary Test Medicine",
        "F001", 5, (today + timedelta(days=60)).isoformat(),
        "Available",
    )
    inventory.add_batch(boundary_batch)

    assert get_expiry_label(boundary_batch.expiry_date).startswith(
        "NEAR-EXPIRY"
    )
    assert boundary_batch.status == "Available"

    print("PASS: Batch at exactly 60 days is flagged, not expired.")
    print("PASS: Near-expiry checks leave inventory quantities unchanged.")


def test_insufficient_stock():
    print("\nTEST 12: Insufficient stock and partial fulfillment")

    inventory = MedicineInventory()

    inventory.add_batch(
        MedicineBatch(
            "TEST_SHORT_A", "TEST_M040", "Insufficient Stock Medicine",
            "F001", 7,
            (date.today() + timedelta(days=120)).isoformat(),
            "Available",
        )
    )

    inventory.add_batch(
        MedicineBatch(
            "TEST_SHORT_B", "TEST_M040", "Insufficient Stock Medicine",
            "F002", 5,
            (date.today() + timedelta(days=150)).isoformat(),
            "Available",
        )
    )

    request = RedistributionRequest(
        "TEST_SHORT_R001", "F004", "TEST_M040",
        "Insufficient Stock Medicine", 20
    )

    suitable = MedicineBatchLinearSearch.search(
        inventory, request, create_test_graph()
    )
    sorted_batches = MedicineBatchInsertionSort.sort_by_expiry(suitable)

    assert [
        batch.batch_id for batch in sorted_batches
    ] == ["TEST_SHORT_A", "TEST_SHORT_B"]

    transaction_count = len(TRANSACTION_RECORDS)

    try:
        status = MedicineRedistributionGreedy.allocate_medicine(
            request, sorted_batches, inventory
        )

        assert status == "Partially Fulfilled"
        assert request.total_allocated == 12
        assert request.remaining_quantity == 8
        assert inventory.find_batch("TEST_SHORT_A").quantity == 0
        assert inventory.find_batch("TEST_SHORT_B").quantity == 0

        new_transactions = TRANSACTION_RECORDS[transaction_count:]
        assert len(new_transactions) == 2

        transferred_total = sum(
            transaction["quantity_transferred"]
            for transaction in new_transactions
        )
        assert transferred_total == 12

        print("PASS: Only available stock was allocated.")
        print("PASS: 7 tablets were allocated from Batch A.")
        print("PASS: 5 tablets were allocated from Batch B.")
        print("PASS: Total allocated quantity is 12, not 20.")
        print("PASS: Request remains partially fulfilled.")
        print("PASS: Remaining requested quantity is 8.")
        print("PASS: Both source batches have zero stock.")
        print("PASS: Transaction quantities total 12.")

    finally:
        del TRANSACTION_RECORDS[transaction_count:]


def test_repeated_requests_stock_consistency():
    print("\nTEST 13: Repeated requests and stock consistency")

    inventory = MedicineInventory()

    inventory.add_batch(
        MedicineBatch(
            "TEST_REPEAT_A", "TEST_M050", "Repeated Request Medicine",
            "F001", 10,
            (date.today() + timedelta(days=120)).isoformat(),
            "Available",
        )
    )

    request1 = RedistributionRequest(
        "TEST_REPEAT_R001", "F004", "TEST_M050",
        "Repeated Request Medicine", 7
    )

    request2 = RedistributionRequest(
        "TEST_REPEAT_R002", "F004", "TEST_M050",
        "Repeated Request Medicine", 5
    )

    transaction_count = len(TRANSACTION_RECORDS)

    try:
        # First request consumes 7 of the 10 tablets.
        status1 = allocate_test_request(inventory, request1)

        assert status1 == "Fulfilled"
        assert request1.total_allocated == 7
        assert request1.remaining_quantity == 0
        assert inventory.find_batch("TEST_REPEAT_A").quantity == 3

        print("PASS: First request received 7 tablets.")
        print("PASS: Source stock fell from 10 tablets to 3.")

        # Search the updated inventory for the second request.
        status2 = allocate_test_request(inventory, request2)

        assert status2 == "Partially Fulfilled"
        assert request2.total_allocated == 3
        assert request2.remaining_quantity == 2
        assert inventory.find_batch("TEST_REPEAT_A").quantity == 0

        print("PASS: Second request received only 3 remaining tablets.")
        print("PASS: Second request has 2 tablets still unfulfilled.")
        print("PASS: Source stock never became negative.")

        # Check that transactions account for only the original 10 tablets.
        new_transactions = TRANSACTION_RECORDS[transaction_count:]

        transferred_total = sum(
            transaction["quantity_transferred"]
            for transaction in new_transactions
        )

        assert transferred_total == 10

        print("PASS: Total allocated across both requests is 10.")
        print("PASS: The same source stock was not allocated twice.")

    finally:
        del TRANSACTION_RECORDS[transaction_count:]


def run_tests():
    print("SAFE EDGE-CASE AND VALIDATION TESTS")
    print("Using temporary in-memory data; no MySQL save functions are called.")

    test_partial_fulfillment()
    test_no_eligible_batches()
    test_invalid_medicine_inputs()
    test_duplicate_batch_id()
    test_invalid_request_quantities()
    test_valid_input()
    test_expiry_sorting()
    test_linear_search_and_facility_connections()
    test_fifo_queue()
    test_greedy_allocation()
    test_near_expiry_threshold()
    test_insufficient_stock()
    test_repeated_requests_stock_consistency()

    print("\nALL THIRTEEN TEST GROUPS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_tests()
