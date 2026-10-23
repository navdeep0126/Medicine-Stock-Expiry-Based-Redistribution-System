class FacilityConnectionGraph:
    def __init__(self):
        self.adjacency_list = {}

    # Add a healthcare facility
    def add_facility(self, facility_id):
        if facility_id not in self.adjacency_list:
            self.adjacency_list[facility_id] = []

    # Connect two healthcare facilities
    def add_connection(self, facility1, facility2):
        self.add_facility(facility1)
        self.add_facility(facility2)

        if facility2 not in self.adjacency_list[facility1]:
            self.adjacency_list[facility1].append(facility2)

        if facility1 not in self.adjacency_list[facility2]:
            self.adjacency_list[facility2].append(facility1)

    # Display facility connections
    def display_connections(self):
        for facility in self.adjacency_list:
            print(facility, "->", self.adjacency_list[facility])

    # Find directly connected facilities
    def get_connected_facilities(self, facility_id):
        if facility_id in self.adjacency_list:
            return self.adjacency_list[facility_id]
        else:
            return []


# Create the Graph
facility_graph = FacilityConnectionGraph()

# Connect healthcare facilities
facility_graph.add_connection("F001", "F002")
facility_graph.add_connection("F001", "F003")
facility_graph.add_connection("F002", "F004")

# Display facility connections
print("All Facility Connections:")
facility_graph.display_connections()

# Find facilities connected to F001
print(
    "Facilities connected to F001:",
    facility_graph.get_connected_facilities("F001")
)