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
    """Q-table simplificada: (destination, neighbor) -> estimated_time
    El from_id está implícito (es el nodo que contiene esta Q-table)"""
    q_values: Dict[Tuple[NodeId, NodeId], float] = field(default_factory=dict)

    def get(self, destination: NodeId, neighbor: NodeId) -> float:
        """Obtiene Q-value para ir al destino vía el vecino"""
        return self.q_values.get((destination, neighbor), 0.0)

    def set(self, destination: NodeId, neighbor: NodeId, value: float):
        """Establece Q-value para ir al destino vía el vecino"""
        self.q_values[(destination, neighbor)] = value

    def get_min_for_destination(self, destination: NodeId) -> float:
        """Obtiene el mínimo Q-value para un destino dado (t en la fórmula)"""
        relevant = [v for (d, n), v in self.q_values.items() if d == destination]
        return min(relevant) if relevant else 0.0

    def __str__(self):
        if not self.q_values:
            return "QTable: (empty)"
        lines = [" QTable:", " destination | neighbor | value", "-" * 36]
        for (destination, neighbor), value in sorted(self.q_values.items()):
            lines.append(f" {destination:11} | {neighbor:8} | {value:6.2f}")
        return "\n".join(lines)


@dataclass
class Packet:
    origin: NodeId
    destination: NodeId
    route: List[Hop] = field(default_factory=list)
    reached_destination: bool = False
    time_in_queue: int = 0  # deprecated, usar queue_entry_time y departure_time
    queue_entry_time: int = 0  # tick cuando entró a la cola del nodo actual
    departure_time: int = 0  # tick cuando salió del nodo anterior
    arrival_time: int = 0  # tick cuando llegó al nodo actual
    id: int = field(init=False)

    _id_counter: int = 0  # class variable for auto-increment

    def __post_init__(self):
        type(self)._id_counter += 1
        self.id = type(self)._id_counter

    def __str__(self):
        return (f"Packet(id={self.id}, origin={self.origin}, destination={self.destination}, "
                f"reached_destination={self.reached_destination}, "
                f"route_length={len(self.route)})")


class Node:
    def __init__(self, node_id: NodeId):
        self.id = node_id
        self.neighbors: List['Node'] = []
        self.queue: deque[Packet] = deque()
        self.q_table = QTable()
        self.pending_requests: List[Tuple[Packet, 'Node']] = []  # used for delayed sends
        self.learning_rate: float = 0.5  # η en la fórmula del paper

    def initialize_q_table(self, all_nodes: List['Node']):
        """Inicializa Q-table con valores optimistas para todos los destinos y vecinos"""
        for dest_node in all_nodes:
            if dest_node.id != self.id:  # No inicializar para sí mismo
                for neighbor in self.neighbors:
                    # Inicialización optimista con valor bajo
                    self.q_table.set(dest_node.id, neighbor.id, 1.0)

    def receive(self, hop: Hop, packet: Packet, current_time: int, previous_node: 'Node' = None):
        """Receives a packet; delivers if it's the destination, otherwise queues it.
        
        IMPORTANTE: Aquí es donde se actualiza la Q-table según el paper.
        """
        packet.arrival_time = current_time
        
        # Si hay un nodo anterior, actualizar su Q-table con la experiencia real
        if previous_node is not None and packet.route:
            # Calcular q: tiempo que estuvo en cola en el nodo anterior
            q = packet.departure_time - packet.queue_entry_time
            
            # Calcular s: tiempo de transmisión entre nodos
            s = packet.arrival_time - packet.departure_time
            
            # Calcular t: mejor estimación de este nodo para llegar al destino
            t = self.q_table.get_min_for_destination(packet.destination)
            
            # Actualizar Q-table del nodo anterior usando la fórmula del paper
            # ΔQx(d,y) = η[(q + s + t) - Qx(d,y)]
            old_estimate = previous_node.q_table.get(packet.destination, self.id)
            new_experience = q + s + t
            delta = previous_node.learning_rate * (new_experience - old_estimate)
            new_value = old_estimate + delta
            
            previous_node.q_table.set(packet.destination, self.id, new_value)
            
            print(f"[Q-update] Time={current_time} Node {previous_node.id}->{self.id} for dest={packet.destination}: "
                  f"q={q}, s={s}, t={t:.2f}, old={old_estimate:.2f}, new={new_value:.2f}")
        
        # Procesar el paquete
        if self.id == packet.destination:
            packet.reached_destination = True
            packet.route.append(hop)
            from metrics import metrics
            metrics.on_delivered(packet)
            print(f"[receive] Packet {packet.id} delivered to destination {self.id}")
        else:
            # Registrar que entró a la cola de este nodo
            packet.queue_entry_time = current_time
            self.queue.append(packet)

    def plan_send(self, packet: Packet, next_node: 'Node'):
        """Plans to send a packet later (executed at the end of the tick)."""
        self.pending_requests.append((packet, next_node))

    def execute_pending_requests(self, current_time: int):
        """Executes all planned sends at the end of the tick."""
        for packet, next_node in self.pending_requests:
            hop = Hop(
                from_id=self.id,
                to_id=next_node.id,
                sent=current_time,
                received=current_time + 1
            )
            # Registrar el momento de salida para cálculos futuros
            packet.departure_time = current_time
            packet.route.append(hop)
            
            # Enviar al siguiente nodo, pasando referencia al nodo actual
            next_node.receive(hop, packet, current_time + 1, previous_node=self)
        
        # Clear all pending requests after they've been processed
        self.pending_requests.clear()

    def __repr__(self):
        return (f"Node(id={self.id}, "
                f"neighbors={[n.id for n in self.neighbors]}, "
                f"queue_size={len(self.queue)}, "
                f"pending_requests={len(self.pending_requests)})")
