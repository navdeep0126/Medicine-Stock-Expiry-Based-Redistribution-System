class MedicineBatchNode:
    def __init__(self, batch_id, medicine_id, medicine_name, facility_id, quantity, expiry_date, status):
        self.batch_id = batch_id
        self.medicine_id = medicine_id
        self.medicine_name = medicine_name
        self.facility_id = facility_id
        self.quantity = quantity
        self.expiry_date = expiry_date
        self.status = status
        self.next = None


# Creating the first medicine batch node
batch1 = MedicineBatchNode(
    "B001",
    "M001",
    "Paracetamol",
    "F001",
    100,
    "2026-12-15",
    "Available"
)


# Creating the second medicine batch node
batch2 = MedicineBatchNode(
    "B002",
    "M001",
    "Paracetamol",
    "F002",
    80,
    "2026-12-20",
    "Available"
)


# Medicine Batch Linked List
class MedicineBatchLinkedList:
    def __init__(self):
        self.head = None

    def add_batch(self, new_batch):
        if self.head is None:
            self.head = new_batch
        else:
            current = self.head

            while current.next is not None:
                current = current.next

            current.next = new_batch

    def display_batches(self):
        current = self.head

        while current is not None:
            print("Batch ID:", current.batch_id)
            print("Medicine:", current.medicine_name)
            print("Facility:", current.facility_id)
            print("Quantity:", current.quantity)
            print("Expiry Date:", current.expiry_date)
            print("Status:", current.status)
            print("--------------------")

            current = current.next


# Creating the Linked List
batch_list = MedicineBatchLinkedList()


# Adding batches to the Linked List
batch_list.add_batch(batch1)
batch_list.add_batch(batch2)


# Displaying the batch IDs
print(batch_list.head.batch_id)
print(batch_list.head.next.batch_id)

# Displaying all batch details
batch_list.display_batches()