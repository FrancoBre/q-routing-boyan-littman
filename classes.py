from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Tuple, List

NodeId = int
Timestamp = float


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
        self.pending_requests: List[Tuple[Packet, 'Node']] = []  # used for delayed sends

    def receive(self, hop: Hop, packet: Packet):
        """Receives a packet; delivers if it's the destination, otherwise queues it."""
        if self.id == packet.destination:
            packet.reached_destination = True
            packet.route.append(hop)
            from simulation import metrics
            metrics.on_delivered(packet)
            print(f"[receive] Packet delivered to destination {self.id}")
        else:
            self.queue.append(packet)

    def plan_send(self, packet: Packet, next_node: 'Node'):
        """Plans to send a packet later (executed at the end of the tick)."""
        self.pending_requests.append((packet, next_node))

    def execute_pending_requests(self):
        """Executes all planned sends at the end of the tick."""
        for packet, next_node in self.pending_requests:
            from simulation import time
            hop = Hop(
                from_id=self.id,
                to_id=next_node.id,
                sent=time,
                received=time + 1
            )
            packet.time_in_queue = 0
            packet.route.append(hop)
            print(
                f'[execute_pending_requests] Time={time} - NodeId={self.id} - Sending packet {packet} to NodeId={next_node.id}')
            next_node.receive(hop, packet)
        # Clear all pending requests after they’ve been processed
        self.pending_requests.clear()

    def __repr__(self):
        return (f"Node(id={self.id}, "
                f"neighbors={[n.id for n in self.neighbors]}, "
                f"queue_size={len(self.queue)}, "
                f"pending_requests={len(self.pending_requests)})")
