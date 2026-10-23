class RedistributionRequest:
    def __init__(self, request_id, destination_facility, medicine_id, medicine_name, requested_quantity):
        self.request_id = request_id
        self.destination_facility = destination_facility
        self.medicine_id = medicine_id
        self.medicine_name = medicine_name
        self.requested_quantity = requested_quantity
        self.remaining_quantity = requested_quantity
        self.status = "Pending"
        self.next = None


class RedistributionRequestQueue:
    def __init__(self):
        self.front = None
        self.rear = None

    def enqueue(self, request):
        if self.rear is None:
            self.front = request
            self.rear = request
        else:
            self.rear.next = request
            self.rear = request

    def dequeue(self):
        if self.front is None:
            return None

        removed_request = self.front
        self.front = self.front.next

        if self.front is None:
            self.rear = None

        removed_request.next = None

        return removed_request


# Creating the Queue
request_queue = RedistributionRequestQueue()


# Creating redistribution requests
request1 = RedistributionRequest(
    "R001",
    "F003",
    "M001",
    "Paracetamol",
    40
)

request2 = RedistributionRequest(
    "R002",
    "F004",
    "M001",
    "Paracetamol",
    30
)


# Adding requests to the Queue
request_queue.enqueue(request1)
request_queue.enqueue(request2)


# Displaying the front and rear before dequeue
print("Before Dequeue")
print("Front Request:", request_queue.front.request_id)
print("Rear Request:", request_queue.rear.request_id)


# Removing the first request
processed_request = request_queue.dequeue()


# Displaying the request that was removed
print("\nProcessed Request:", processed_request.request_id)


# Displaying the new front
if request_queue.front is not None:
    print("New Front Request:", request_queue.front.request_id)
else:
    print("Queue is empty")