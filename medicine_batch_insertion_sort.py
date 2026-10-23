
from datetime import date


# Step 1: Create a Medicine Batch
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


# Step 2: Implement Insertion Sort
class MedicineBatchInsertionSort:
    def sort_by_expiry(self, batches):
        for i in range(1, len(batches)):
            current_batch = batches[i]
            j = i - 1

            while (
                j >= 0
                and date.fromisoformat(batches[j].expiry_date)
                > date.fromisoformat(current_batch.expiry_date)
            ):
                batches[j + 1] = batches[j]
                j -= 1

            batches[j + 1] = current_batch

        return batches


# Step 3: Create Sample Medicine Batches
batch1 = MedicineBatch(
    "B001", "M001", "Paracetamol",
    "F001", 100, "2026-12-15", "Available"
)

batch2 = MedicineBatch(
    "B002", "M001", "Paracetamol",
    "F002", 80, "2026-12-20", "Available"
)

batch3 = MedicineBatch(
    "B003", "M001", "Paracetamol",
    "F003", 50, "2026-11-30", "Available"
)

batch4 = MedicineBatch(
    "B004", "M001", "Paracetamol",
    "F004", 40, "2026-12-25", "Unavailable"
)


# Step 4: Store All Batches
batches = [batch1, batch2, batch3, batch4]


# Step 5: Filter Suitable Batches
print("CODE IS RUNNING: INSERTION SORT")

suitable_batches = []

for batch in batches:
    expiry = date.fromisoformat(batch.expiry_date)

    if (
        expiry >= date.today()
        and batch.quantity > 0
        and batch.status == "Available"
    ):
        suitable_batches.append(batch)


# Step 6: Sort by Earliest Expiry Date
sorter = MedicineBatchInsertionSort()
sorted_batches = sorter.sort_by_expiry(suitable_batches)


# Step 7: Display Sorted Results
print("\nSuitable Batches After Insertion Sort:")
print("Priority: Earliest Expiry First")
print("======================================")

if sorted_batches:
    for batch in sorted_batches:
        print("Batch ID:", batch.batch_id)
        print("Medicine:", batch.medicine_name)
        print("Facility:", batch.facility_id)
        print("Quantity:", batch.quantity)
        print("Expiry Date:", batch.expiry_date)
        print("Status:", batch.status)
        print("--------------------------------------")
else:
    print("No suitable medicine batches found.")

print("INSERTION SORT COMPLETED")
