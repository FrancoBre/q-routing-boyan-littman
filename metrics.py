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

    def plot(self, filename: str = "average_delivery_times.png"):
        """
        matplotlib plot of all series. Saves to file without displaying.
        """
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        
        if not self.series:
            print("[metrics] No data to plot")
            return
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for label, points in self.series.items():
            if not points:
                continue
            xs, ys = zip(*points)
            
            # Use markers for better visibility when there are few points
            if len(points) == 1:
                # Single point: show as a large marker with annotation
                ax.plot(xs, ys, marker='o', markersize=12, label=label, linewidth=0)
                ax.annotate(f'{ys[0]:.2f}', xy=(xs[0], ys[0]), 
                           xytext=(10, 10), textcoords='offset points',
                           fontsize=10, bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7))
            else:
                # Multiple points: show line without markers
                ax.plot(xs, ys, label=label, linewidth=2)
        
        ax.set_xlabel("Simulator Time (ticks)", fontsize=12)
        ax.set_ylabel("Average Delivery Time (ticks)", fontsize=12)
        ax.legend(fontsize=10)
        ax.set_title("Average Delivery Time vs Simulator Time", fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"[metrics] Plot saved to {filename}")
        plt.close()

metrics = Metrics(sample_every=10)