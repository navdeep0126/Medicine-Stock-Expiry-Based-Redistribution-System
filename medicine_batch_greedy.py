
from datetime import date


# Step 1: Define a medicine batch
class MedicineBatch:
    def __init__(
        self, batch_id, medicine_id, medicine_name,
        facility_id, quantity, expiry_date, status
    ):
        self.batch_id = batch_id
        self.medicine_id = medicine_id
        self.medicine_name = medicine_name
        self.facility_id = facility_id
        self.quantity = quantity
        self.expiry_date = expiry_date
        self.status = status


# Step 2: Define a redistribution request
class RedistributionRequest:
    def __init__(
        self, request_id, destination_facility,
        medicine_id, medicine_name, requested_quantity
    ):
        self.request_id = request_id
        self.destination_facility = destination_facility
        self.medicine_id = medicine_id
        self.medicine_name = medicine_name
        self.requested_quantity = requested_quantity
        self.remaining_quantity = requested_quantity
        self.status = "Pending"


# Step 3: Implement the Greedy Algorithm
class MedicineRedistributionGreedy:
    def allocate_medicine(self, request, batches):
        print("GREEDY ALGORITHM: MEDICINE REDISTRIBUTION")
        print("------------------------------------------")
        print("Request ID:", request.request_id)
        print("Medicine:", request.medicine_name)
        print("Destination:", request.destination_facility)
        print("Requested Quantity:", request.requested_quantity)
        print("------------------------------------------")

        # Consider suitable batches with earliest expiry first
        suitable_batches = []

        for batch in batches:
            expiry = date.fromisoformat(batch.expiry_date)

            if (
                batch.medicine_id == request.medicine_id
                and expiry >= date.today()
                and batch.quantity > 0
                and batch.status == "Available"
                and batch.facility_id != request.destination_facility
            ):
                suitable_batches.append(batch)

        # Sort eligible batches by expiry date using Insertion Sort
        for i in range(1, len(suitable_batches)):
            current_batch = suitable_batches[i]
            j = i - 1

            while (
                j >= 0
                and date.fromisoformat(
                    suitable_batches[j].expiry_date
                ) > date.fromisoformat(current_batch.expiry_date)
            ):
                suitable_batches[j + 1] = suitable_batches[j]
                j -= 1

            suitable_batches[j + 1] = current_batch

        # Greedily allocate stock from the earliest-expiring batches
        for batch in suitable_batches:
            if request.remaining_quantity == 0:
                break

            allocated_quantity = min(
                batch.quantity,
                request.remaining_quantity
            )

            if allocated_quantity > 0:
                print(
                    "Source:", batch.facility_id,
                    "| Batch:", batch.batch_id,
                    "| Allocated:", allocated_quantity
                )

                batch.quantity -= allocated_quantity
                request.remaining_quantity -= allocated_quantity

        # Update request status
        if request.remaining_quantity == 0:
            request.status = "Fulfilled"
        elif request.remaining_quantity < request.requested_quantity:
            request.status = "Partially Fulfilled"
        else:
            request.status = "Pending"

        print("------------------------------------------")
        print("Requested Quantity:", request.requested_quantity)
        print(
            "Allocated Quantity:",
            request.requested_quantity - request.remaining_quantity
        )
        print("Remaining Quantity:", request.remaining_quantity)
        print("Request Status:", request.status)
        print("------------------------------------------")

        return request


# Step 4: Create sample medicine batches
batch1 = MedicineBatch(
    "B001", "M001", "Paracetamol",
    "F001", 30, "2026-12-15", "Available"
)

batch2 = MedicineBatch(
    "B002", "M001", "Paracetamol",
    "F002", 20, "2026-12-20", "Available"
)

batch3 = MedicineBatch(
    "B003", "M001", "Paracetamol",
    "F004", 50, "2025-01-10", "Available"
)

batch4 = MedicineBatch(
    "B004", "M001", "Paracetamol",
    "F005", 40, "2026-12-25", "Unavailable"
)

batches = [batch1, batch2, batch3, batch4]


# Step 5: Create a redistribution request
request = RedistributionRequest(
    "R001", "F003", "M001", "Paracetamol", 40
)


# Step 6: Run the Greedy Algorithm
greedy = MedicineRedistributionGreedy()
greedy.allocate_medicine(request, batches)


# Step 7: Display updated source stock
print("\nUpdated Source Stock:")

for batch in batches:
    print(
        "Batch:", batch.batch_id,
        "| Facility:", batch.facility_id,
        "| Remaining Stock:", batch.quantity
    )

