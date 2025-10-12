from typing import List, Dict, Tuple
from dataclasses import dataclass, field
from collections import deque


NodeId = int
Timestamp = float

time = 0

@dataclass
class Hop:
    from_id: NodeId
    to_id: NodeId
    sent: Timestamp
    received: Timestamp


@dataclass
class QTable:
    q_values: Dict[Tuple[NodeId, NodeId, NodeId], float] = field(default_factory=dict)

    def get(self, from_id: NodeId, destination: NodeId, to_id: NodeId) -> float:
        return self.q_values.get((from_id, destination, to_id), 0.0)

    def set(self, from_id: NodeId, destination: NodeId, to_id: NodeId, value: float):
        self.q_values[(from_id, destination, to_id)] = value

    def __str__(self):
        if not self.q_values:
            return "QTable: (empty)"
        lines = [" QTable:", " from_id | destination | to_id | value", "-" * 36]
        for (from_id, destination, to_id), value in sorted(self.q_values.items()):
            lines.append(f" {from_id:7} | {destination:11} | {to_id:5} | {value:6.2f}")
        return "\n".join(lines)

@dataclass
class Packet:
    origin: NodeId
    destination: NodeId
    route: List[Hop] = field(default_factory=list)
    reached_destination: bool = False
    time_in_queue: int = 0
    id: int = field(init=False)

    _id_counter: int = 0  # class variable for auto-increment

    def __post_init__(self):
        type(self)._id_counter += 1
        self.id = type(self)._id_counter

    def __str__(self):
        return (f"Packet(id={self.id}, origin={self.origin}, destination={self.destination}, "
                f"reached_destination={self.reached_destination}, "
                f"time_in_queue={self.time_in_queue}, "
                f"route_length={len(self.route)})")

class Node:
    def __init__(self, node_id: NodeId):
        self.id = node_id
        self.neighbors: List['Node'] = []
        self.queue: deque[Packet] = deque()
        self.q_table = QTable()
        self.pending_requests: List[Tuple[Packet, 'Node']] = [] # used for delayed sends

    def receive(self, hop: Hop, packet: Packet):
        """Receives a packet; delivers if it's the destination, otherwise queues it."""
        if self.id == packet.destination:
            packet.reached_destination = True
            packet.route.append(hop)
            print(f"[receive] Packet delivered to destination {self.id}")
        else:
            self.queue.append(packet)

    def plan_send(self, packet: Packet, next_node: 'Node'):
        """Plans to send a packet later (executed at the end of the tick)."""
        self.pending_requests.append((packet, next_node))

    def execute_pending_requests(self):
        """Executes all planned sends at the end of the tick."""
        for packet, next_node in self.pending_requests:
            hop = Hop(
                from_id=self.id,
                to_id=next_node.id,
                sent=time,
                received=time + 1
            )
            packet.time_in_queue = 0
            packet.route.append(hop)
            print(f'[execute_pending_requests] Time={time} - NodeId={self.id} - Sending packet {packet} to NodeId={next_node.id}')
            next_node.receive(hop, packet)
        # Clear all pending requests after they’ve been processed
        self.pending_requests.clear()

    def __repr__(self):
        return (f"Node(id={self.id}, "
                f"neighbors={[n.id for n in self.neighbors]}, "
                f"queue_size={len(self.queue)}, "
                f"pending_requests={len(self.pending_requests)})")

def create_6x6_grid() -> List[Node]:
    """Creates a 6x6 grid of 36 nodes with orthogonal neighbors."""
    nodes = [Node(i) for i in range(36)]
    for i, node in enumerate(nodes):
        row, col = divmod(i, 6)
        if col < 5:
            node.neighbors.append(nodes[i + 1])
        if col > 0:
            node.neighbors.append(nodes[i - 1])
        if row < 5:
            node.neighbors.append(nodes[i + 6])
        if row > 0:
            node.neighbors.append(nodes[i - 6])
    return nodes


def generate_routing_request(nodes: List[Node]) -> Packet:
    """Generates a routing packet from node 0 to node 35 (for simplicity)."""
    origin = 0
    destination = len(nodes) - 1
    return Packet(origin=origin, destination=destination)


def packets_are_delivered(packets: List[Packet]) -> bool:
    """Checks whether all packets have reached their destination."""
    return all(p.reached_destination for p in packets)


def tick(nodes: List[Node]):
    """Simulates one tick of the system with a two-phase update (plan + execute)."""
    global time
    # Phase 1: Decision (plan all sends)
    for node in nodes:
        if not node.queue:
            continue

        packet = node.queue.popleft()
        if packet.reached_destination:
            print(f'\n[tick] Time={time} - NodeId={node.id} - Packet {packet} already delivered')
            continue

        print(f'\n[tick] Time={time} - NodeId={node.id} - Processing packet {packet}')

        # Choose next node based on minimum Q-value
        best_next_node = min(
            node.neighbors,
            key=lambda n: node.q_table.get(node.id, packet.destination, n.id)
        )

        print(f'[tick] Time={time} - NodeId={node.id} - {node.q_table}')
        print(f'[tick] Time={time} - NodeId={node.id} - Chose next node {best_next_node.id} for packet {packet}')

        # Update Q-value using temporal difference
        next_node_estimation = best_next_node.q_table.get(node.id, packet.destination, best_next_node.id)
        old_estimation = node.q_table.get(node.id, packet.destination, best_next_node.id)
        new_estimation = 0.5 * ((packet.time_in_queue + 1 + next_node_estimation) - old_estimation)

        print(f'[tick] Time={time} - NodeId={node.id} - Updating Q-value [from={node.id}, destination={packet.destination}, to={best_next_node.id}] from {old_estimation:.2f} to {new_estimation:.2f}')

        node.q_table.set(node.id, packet.destination, best_next_node.id, new_estimation)

        # Increment queue time for other packets
        for p in node.queue:
            p.time_in_queue += 1
            print(f'[tick] Time={time} - NodeId={node.id} - Incrementing time_in_queue for packet {p} to {p.time_in_queue}')

        # Schedule the packet to be sent (not yet executed)
        node.plan_send(packet, best_next_node)

    # Phase 2: Execution (perform all sends at once)
    for node in nodes:
        node.execute_pending_requests()

    time += 1


def main():
    nodes = create_6x6_grid()

    # Initial low-load scenario
    packet = generate_routing_request(nodes)
    packets = [packet]
    nodes[packet.origin].queue.append(packet)

    print("[main] Starting simulation with 1 packet")
    while not packets_are_delivered(packets):
        tick(nodes)

    # Increase network load
    print("[main] Increasing network load")
    packets = [generate_routing_request(nodes) for _ in range(10)]
    for p in packets:
        nodes[p.origin].queue.append(p)

    while not packets_are_delivered(packets):
        tick(nodes)

    print("[main] All packets delivered!")


if __name__ == "__main__":
    main()
