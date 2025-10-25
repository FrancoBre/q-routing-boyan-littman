from typing import List

from classes import Node, Packet
import random

random.seed(42)
time = 0

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
    remove(14, 20)
    remove(15, 21)

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

        # print(f'\n[tick] Time={time} - NodeId={node.id} - Processing packet {packet}')

        # Choose next node based on minimum Q-value
        # el paper no explica que pasa en caso de "empate", asi que elegimos aleatoriamente entre los mejores
        q_values = [node.q_table.get(node.id, packet.destination, n.id) for n in node.neighbors]
        min_q = min(q_values)
        epsilon = 1e-6  # tolerance for equality

        best_candidates = [n for n, q in zip(node.neighbors, q_values) if abs(q - min_q) < epsilon]

        if len(best_candidates) > 1:
            best_next_node = random.choice(best_candidates)
        else:
            best_next_node = best_candidates[0]

        print(f'---\n[tick] Time={time} - NodeId={node.id} - {node.q_table}')
        print(f'[tick] Time={time} - NodeId={node.id} - Chose next node {best_next_node.id} for packet {packet}')

        # Update Q-value for the (node, destination, next_node) triplet using Temporal Difference Learning
        old_estimation = node.q_table.get(node.id, packet.destination, best_next_node.id)

        # compute t = next node's best estimate
        min_next_neighbor = min(
            best_next_node.neighbors,
            key=lambda z: best_next_node.q_table.get(best_next_node.id, packet.destination, z.id)
        )
        t = best_next_node.q_table.get(best_next_node.id, packet.destination, min_next_neighbor.id)

        q = packet.time_in_queue
        s = 1
        eta = 0.5

        delta = eta * ((q + s + t) - old_estimation)

        new_value = old_estimation + delta

        print(
            f'[tick] Time={time} - NodeId={node.id} - Updating Q-value [from={node.id}, destination={packet.destination}, to={best_next_node.id}] from {old_estimation:.2f} to {new_value:.2f}')

        node.q_table.set(node.id, packet.destination, best_next_node.id, new_value)

        # Increment queue time for other packets
        for p in node.queue:
            p.time_in_queue += 1
            print(
                f'[tick] Time={time} - NodeId={node.id} - Incrementing time_in_queue for packet {p} to {p.time_in_queue}')

        # Schedule the packet to be sent (not yet executed)
        node.plan_send(packet, best_next_node)

    # Phase 2: Execution (perform all sends at once)
    for node in nodes:
        node.execute_pending_requests(time)

    time += 1
    from metrics import metrics
    metrics.sample_if_needed(time)


def run_gradual_load_scenario(nodes, total: int, gap: int, label: str):
    """
    Inject `total` packets, one every `gap` ticks, and step the simulator
    until all injected packets are delivered.
    """
    from metrics import metrics
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

    run_gradual_load_scenario(nodes, total=1000, gap=10, label="gradual_1000pk_gap10")

    from metrics import metrics
    metrics.plot()
    print("[main] gradual_60pk_gap2 last avg:", metrics.last_point("gradual_1000pk_gap10"))


if __name__ == "__main__":
    main()
