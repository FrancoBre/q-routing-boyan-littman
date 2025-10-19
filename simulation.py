from typing import List

from classes import Node, Packet
from metrics import Metrics

metrics = Metrics(sample_every=100)
time = 0


def create_irregular_6x6_grid() -> List[Node]:
    """Creates the irregular 6x6 grid topology from Boyan & Littman (1994)."""
    nodes = [Node(i) for i in range(36)]

    def connect(a: int, b: int):
        """Safely connect two nodes bidirectionally."""
        nodes[a].neighbors.append(nodes[b])
        nodes[b].neighbors.append(nodes[a])

    # Build a regular grid first
    for i in range(36):
        row, col = divmod(i, 6)
        if col < 5:
            connect(i, i + 1)
        if row < 5:
            connect(i, i + 6)

    # Now remove connections to form the "holes"
    holes = {8, 9, 14, 15, 20, 21, 26, 27}

    # Remove connections *to and from* these holes
    for h in holes:
        nodes[h].neighbors.clear()  # the hole itself is isolated

    # Remove any neighbor references pointing into the holes
    for node in nodes:
        node.neighbors = [n for n in node.neighbors if n.id not in holes]

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

        print(
            f'[tick] Time={time} - NodeId={node.id} - Updating Q-value [from={node.id}, destination={packet.destination}, to={best_next_node.id}] from {old_estimation:.2f} to {new_estimation:.2f}')

        node.q_table.set(node.id, packet.destination, best_next_node.id, new_estimation)

        # Increment queue time for other packets
        for p in node.queue:
            p.time_in_queue += 1
            print(
                f'[tick] Time={time} - NodeId={node.id} - Incrementing time_in_queue for packet {p} to {p.time_in_queue}')

        # Schedule the packet to be sent (not yet executed)
        node.plan_send(packet, best_next_node)

    # Phase 2: Execution (perform all sends at once)
    for node in nodes:
        node.execute_pending_requests()

    time += 1
    metrics.sample_if_needed()


def run_gradual_load_scenario(nodes, total: int, gap: int, label: str):
    """
    Inject `total` packets, one every `gap` ticks, and step the simulator
    until all injected packets are delivered.
    """
    metrics.start_series(label)

    pending = [generate_routing_request(nodes) for _ in range(total)]
    active: List[Packet] = []
    gap_counter = 0

    print(f"[main] Scenario '{label}' -> total={total}, gap={gap}")

    while pending or any(not p.reached_destination for p in active):
        # inject if it's time and we still have packets
        if gap_counter == 0 and pending:
            pkt = pending.pop(0)
            nodes[pkt.origin].queue.append(pkt)
            active.append(pkt)
            gap_counter = gap
            print(f"[main] Sent new packet {pkt}")
        else:
            gap_counter = max(0, gap_counter - 1)

        tick(nodes)

    print(f"[main] Scenario '{label}' last avg:", metrics.last_point(label))


def main():
    nodes = create_irregular_6x6_grid()

    # ---- Low load: single packet ----
    packet = generate_routing_request(nodes)
    packets = [packet]
    nodes[packet.origin].queue.append(packet)

    metrics.start_series("low_load_single")
    print("[main] Starting simulation with 1 packet")
    while not packets_are_delivered(packets):
        tick(nodes)

    print("[main] Low-load last avg:", metrics.last_point("low_load_single"))

    run_gradual_load_scenario(nodes, total=10, gap=10, label="gradual_10pk_gap10")

    run_gradual_load_scenario(nodes, total=30, gap=5, label="gradual_30pk_gap5")

    run_gradual_load_scenario(nodes, total=60, gap=2, label="gradual_60pk_gap2")

    for label in ["gradual_10pk_gap10", "gradual_30pk_gap5", "gradual_60pk_gap2"]:
        print(f"[main] {label} last avg:", metrics.last_point(label))

    metrics.plot()

    print("[main] All scenarios completed!")


if __name__ == "__main__":
    main()
