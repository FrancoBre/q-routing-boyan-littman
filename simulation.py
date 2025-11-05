from typing import List
import sys

from classes import Node, Packet
import random

# random.seed(42)

time = 0


class Logger:
    """Redirects stdout to both console and a log file."""
    def __init__(self, filename="logs.txt"):
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding="utf-8")
        self.closed = False

    def write(self, message):
        self.terminal.write(message)
        if not self.closed:
            self.log.write(message)

    def flush(self):
        self.terminal.flush()
        if not self.closed:
            self.log.flush()

    def close(self):
        if not self.closed:
            self.log.close()
            self.closed = True


# Redirect stdout to log file
logger = Logger("logs.txt")
sys.stdout = logger

def create_irregular_6x6_grid() -> List[Node]:
    nodes = [Node(i) for i in range(36)]

    def connect(a, b):
        nodes[a].neighbors.append(nodes[b])
        nodes[b].neighbors.append(nodes[a])

    # Build regular grid
    for i in range(36):
        row, col = divmod(i, 6)
        if col < 5:
            connect(i, i + 1)
        if row < 5:
            connect(i, i + 6)

    # Remove only the vertical links in the 2x2 hole block
    holes = {14, 15, 20, 21}

    def remove(a, b):
        if nodes[b] in nodes[a].neighbors:
            nodes[a].neighbors.remove(nodes[b])
        if nodes[a] in nodes[b].neighbors:
            nodes[b].neighbors.remove(nodes[a])

    # Remove vertical edges:
    remove(10, 11)
    remove(16, 17)
    remove(22, 23)
    remove(28, 29)
    remove(4, 10)
    remove(16, 22)
    remove(28, 34)
    remove(16, 22)
    remove(14, 20)
    remove(13, 19)
    remove(12, 18)

    # Inicializar Q-tables con valores optimistas
    print("[create_grid] Initializing Q-tables...")
    for node in nodes:
        node.initialize_q_table(nodes)
    print(f"[create_grid] Q-tables initialized for {len(nodes)} nodes")

    return nodes


def generate_routing_request(nodes: List[Node]) -> Packet:
    """Generates a routing packet from a random origin to a random destination (different from origin)."""
    origin = random.randint(0, len(nodes) - 1)
    destination = random.randint(0, len(nodes) - 1)
    
    # Asegurar que origen y destino sean diferentes
    while destination == origin:
        destination = random.randint(0, len(nodes) - 1)
    
    print(f"[generate_packet] Created packet from node {origin} to node {destination}")
    return Packet(origin=origin, destination=destination)


def packets_are_delivered(packets: List[Packet]) -> bool:
    """Checks whether all packets have reached their destination."""
    return all(p.reached_destination for p in packets)


def tick(nodes: List[Node], should_sample: bool = False, label: str = None):
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

        # Choose next node based on minimum Q-value
        q_values = [node.q_table.get(packet.destination, n.id) for n in node.neighbors]
        min_q = min(q_values)
        epsilon = 1e-6  # tolerance for equality

        best_candidates = [n for n, q in zip(node.neighbors, q_values) if abs(q - min_q) < epsilon]

        if len(best_candidates) > 1:
            best_next_node = random.choice(best_candidates)
        else:
            best_next_node = best_candidates[0]

        print(f'\n[tick] Time={time} - NodeId={node.id} - Chose next node {best_next_node.id} for packet {packet}')
        print(f'[tick] Node {node.id} Q-values for dest={packet.destination}: {[(n.id, node.q_table.get(packet.destination, n.id)) for n in node.neighbors]}')

        # Schedule the packet to be sent (not yet executed)
        # La actualización de Q-values ocurrirá cuando el paquete LLEGUE al siguiente nodo
        node.plan_send(packet, best_next_node)

    # Phase 2: Execution (perform all sends at once)
    # Aquí es donde ocurren las actualizaciones de Q-values (dentro de receive())
    for node in nodes:
        node.execute_pending_requests(time)

    time += 1
    
    # Muestrear si corresponde
    if should_sample and label:
        from metrics import metrics
        avg_delivery = metrics.average_delivery_time_so_far()
        if avg_delivery is not None:
            metrics.series[label].append((time, avg_delivery))
            print(f"[sample] Time={time}, avg_delivery={avg_delivery:.2f}")


def run_gradual_load_scenario(nodes, total: int, gap: int, label: str, sample_interval: int = 10):
    """
    Inject `total` packets, one every `gap` ticks, and step the simulator
    until all injected packets are delivered.
    
    Args:
        nodes: List of network nodes
        total: Total number of packets to inject
        gap: Ticks between packet injections
        label: Label for the metrics series
        sample_interval: How often to sample metrics (in ticks)
    """
    from metrics import metrics
    metrics.start_series(label)

    pending = [generate_routing_request(nodes) for _ in range(total)]
    active: List[Packet] = []
    gap_counter = 0
    sample_counter = 0

    print(f"[main] Scenario '{label}' -> total={total}, gap={gap}, sample_interval={sample_interval}")

    while pending or any(not p.reached_destination for p in active):
        # inject if it's time and we still have packets
        if gap_counter == 0 and pending:
            pkt = pending.pop(0)
            pkt.queue_entry_time = time  # Registrar cuando entra a la cola inicial
            nodes[pkt.origin].queue.append(pkt)
            active.append(pkt)
            gap_counter = gap
            print(f"[main] Injected packet {pkt.id} at time {time}")
        else:
            gap_counter = max(0, gap_counter - 1)

        # Determinar si debemos muestrear en este tick
        should_sample = (sample_counter == 0)
        if should_sample:
            sample_counter = sample_interval
        else:
            sample_counter -= 1

        tick(nodes, should_sample=should_sample, label=label)

    # Muestrear el punto final si aún no lo hicimos en el último tick
    from metrics import metrics
    if not metrics.series[label] or metrics.series[label][-1][0] != time:
        avg_delivery = metrics.average_delivery_time_so_far()
        if avg_delivery is not None:
            metrics.series[label].append((time, avg_delivery))
            print(f"[sample] Final point - Time={time}, avg_delivery={avg_delivery:.2f}")
    
    print(f"[main] Scenario '{label}' completed at time {time}")
    final_avg = metrics.last_point(label)[1] if metrics.last_point(label) else 0
    print(f"[main] Scenario '{label}' final avg delivery time: {final_avg:.2f}")


def main():
    nodes = create_irregular_6x6_grid()

    # # ---- Low load: single packet ----
    # packet = generate_routing_request(nodes)
    # packets = [packet]
    # nodes[packet.origin].queue.append(packet)
    #
    # metrics.start_series("low_load_single")
    # print("[main] Starting simulation with 1 packet")
    # while not packets_are_delivered(packets):
    #     tick(nodes)
    #
    # print("[main] Low-load last avg:", metrics.last_point("low_load_single"))

    # metrics.plot()

    # ---- Increase load ----

    # packet_1 = generate_routing_request(nodes)
    # packet_2 = generate_routing_request(nodes)
    # packets = [packet_1, packet_2]
    # nodes[packet_1.origin].queue.append(packet_1)
    #
    # metrics.start_series("low_load_double")
    # print("[main] Starting simulation with 2 packets")
    #
    # time_until_injection = time + 5
    # while not packets_are_delivered(packets):
    #     if time == time_until_injection:
    #         nodes[packet_2.origin].queue.append(packet_2)
    #         print(f"[main] Injected second packet {packet_2} at time {time}")
    #     tick(nodes)
    #
    # print("[main] Low-load double last avg:", metrics.last_point("low_load_double"))

    # metrics.plot()

    # ---- Increase load ----
    # packet_1 = generate_routing_request(nodes)
    # packet_2 = generate_routing_request(nodes)
    # packet_3 = generate_routing_request(nodes)
    # packets = [packet_1, packet_2, packet_3]
    #
    # nodes[packet_1.origin].queue.append(packet_1)
    #
    # metrics.start_series("low_load_triple")
    # print("[main] Starting simulation with 3 packets")
    # time_until_injection_2 = time + 5
    # time_until_injection_3 = time + 10
    # while not packets_are_delivered(packets):
    #     if time == time_until_injection_2:
    #         nodes[packet_2.origin].queue.append(packet_2)
    #         print(f"[main] Injected second packet {packet_2} at time {time}")
    #     if time == time_until_injection_3:
    #         nodes[packet_3.origin].queue.append(packet_3)
    #         print(f"[main] Injected third packet {packet_3} at time {time}")
    #     tick(nodes)
    #
    # print("[main] Low-load triple last avg:", metrics.last_point("low_load_triple"))
    # metrics.plot()

    # run_gradual_load_scenario(nodes, total=10, gap=10, label="gradual_10pk_gap10")

    # run_gradual_load_scenario(nodes, total=30, gap=5, label="gradual_30pk_gap5")

    # run_gradual_load_scenario(nodes, total=60, gap=2, label="gradual_60pk_gap2")

    # for label in ["gradual_10pk_gap10", "gradual_30pk_gap5", "gradual_60pk_gap2"]:
    #     print(f"[main] {label} last avg:", metrics.last_point(label))

    # metrics.plot()

    # print("[main] All scenarios completed!")

    run_gradual_load_scenario(nodes, total=10000, gap=5, label="gradual_20pk_gap5", sample_interval=10)

    from metrics import metrics
    metrics.plot()
    print("[main] Final statistics:")
    for label in metrics.all_series().keys():
        last_point = metrics.last_point(label)
        if last_point:
            print(f"  {label}: avg_delivery_time={last_point[1]:.2f} at time={last_point[0]}")


if __name__ == "__main__":
    try:
        main()
    finally:
        # Close log file properly
        print("\n[simulation] Logs saved to logs.txt")
        logger.close()
