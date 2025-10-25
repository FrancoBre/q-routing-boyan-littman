from typing import List, Tuple, Dict

from classes import Packet


class Metrics:
    """
    Encapsulates:
      - delivered packets registry
      - (tick, avg_delivery_time) time series per scenario label
      - sampling policy (every N ticks)
    """

    def __init__(self, sample_every: int = 100):
        self.sample_every = sample_every
        from simulation import Packet
        self.delivered_packets: List[Packet] = []
        self.series: Dict[str, List[Tuple[int, float]]] = {}
        self._current_label: str | None = None

    # ---- wiring helpers ----
    def start_series(self, label: str):
        """Start/clear a labeled time series; keep delivered packets (global learning)."""
        self._current_label = label
        self.series[label] = []

    def on_delivered(self, packet: Packet):
        """Register that a packet has been delivered."""
        self.delivered_packets.append(packet)

    def sample_if_needed(self, time: int):
        """Sample avg delivery time based on sampling policy."""
        if self._current_label is None:
            return
        if time % self.sample_every == 0:
            avg = self.average_delivery_time_so_far()
            self.series[self._current_label].append((time, avg))

    # ---- computations ----
    @staticmethod
    def delivery_time(p: Packet) -> int:
        """Total travel time in ticks: first sent to last received."""
        if not p.route:
            return 0
        return int(p.route[-1].received - p.route[0].sent)

    def average_delivery_time_so_far(self) -> float:
        """Average over all delivered packets so far (global view)."""
        delivered_with_route = [p for p in self.delivered_packets if p.route] # <- FIXME: o delivered_packets está vacío, o p.route está vacío
        if not delivered_with_route:
            return 0.0
        total = sum(self.delivery_time(p) for p in delivered_with_route)
        return total / len(delivered_with_route)

    # ---- convenience getters ----
    def last_point(self, label: str) -> Tuple[int, float] | None:
        s = self.series.get(label, [])
        return s[-1] if s else None

    def all_series(self) -> Dict[str, List[Tuple[int, float]]]:
        return self.series

    def plot(self):
        """
        matplotlib plot of all series.
        """
        import matplotlib.pyplot as plt
        for label, points in self.series.items():
            if not points:
                continue
            xs, ys = zip(*points)
            plt.plot(xs, ys, label=label)
        plt.xlabel("Simulator Time")
        plt.ylabel("Average Delivery Time")
        plt.legend()
        plt.title("Average Delivery Time vs Simulator Time")
        plt.show()
        # plt.savefig("average_delivery_times.png", dpi=300)

metrics = Metrics(sample_every=10)