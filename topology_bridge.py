import asyncio
import networkx as nx
import random
import time

class SDNControllerMock:
    """
    Simulates a production SDN controller (like ONOS or Ryu).
    In a physical deployment, the controller uses LLDP (Link Layer Discovery Protocol)
    to discover switches and links, and exposes them via a REST API.
    This mock generates a realistic topology structure.
    """
    def __init__(self):
        self.nodes = ["Router_A", "Router_B", "Router_C", "Router_D", "Server_Farm"]
        self.base_links = [
            {"source": "Router_A", "target": "Router_B", "capacity": "10G"},
            {"source": "Router_A", "target": "Router_C", "capacity": "1G"},
            {"source": "Router_B", "target": "Router_D", "capacity": "10G"},
            {"source": "Router_C", "target": "Router_D", "capacity": "1G"},
            {"source": "Router_D", "target": "Server_Farm", "capacity": "10G"},
        ]

    async def fetch_topology(self):
        """
        Simulates an HTTP GET request to the SDN Controller's /v1/topology endpoint.
        Periodically introduces or removes a link to simulate link flapping or new provisions.
        """
        # Simulating network latency to controller
        await asyncio.sleep(0.1)

        current_links = list(self.base_links)
        # Randomly flap a backup link for dynamic testing
        if random.random() > 0.8:
            current_links.append({"source": "Router_B", "target": "Router_C", "capacity": "1G"})

        return {
            "nodes": [{"id": n} for n in self.nodes],
            "links": current_links,
            "timestamp": time.time()
        }

class TopologyBridge:
    """
    Middleware that bridges the gap between the SDN Controller and the RL/GNN Engine.
    It takes the raw JSON topology and parses it into the Adjacency Matrix format
    that Graph Neural Networks natively compute on.
    """
    def __init__(self):
        self.controller = SDNControllerMock()
        self.current_adj_matrix = None
        self.node_ordering = []

    def parse_to_gnn_format(self, raw_topology):
        """
        Converts the JSON representation into a NetworkX graph, and then
        extracts the Numpy Adjacency Matrix required by the AI.
        """
        G = nx.DiGraph() # Using directed graph for traffic flow

        # Add nodes
        for node in raw_topology["nodes"]:
            G.add_node(node["id"])

        # Add edges
        for link in raw_topology["links"]:
            # Depending on the network, links might be bidirectional
            G.add_edge(link["source"], link["target"], capacity=link["capacity"])
            G.add_edge(link["target"], link["source"], capacity=link["capacity"])

        # Maintain consistent ordering of nodes for the matrix
        self.node_ordering = list(G.nodes())

        # Convert to numpy Adjacency Matrix
        # A value of 1 means connected, 0 means no direct link
        adj_matrix = nx.to_numpy_array(G, nodelist=self.node_ordering)
        return adj_matrix

    async def run_discovery_loop(self):
        """
        The main worker loop that constantly keeps the digital twin's understanding
        of the physical network topology up to date.
        """
        print("🌐 Starting SDN Topology Discovery Loop...")
        while True:
            try:
                # 1. Fetch live topology from controller
                raw_topo = await self.controller.fetch_topology()

                # 2. Parse into Mathematical Matrix for GNN
                self.current_adj_matrix = self.parse_to_gnn_format(raw_topo)

                print(f"🔄 Topology Updated [{time.strftime('%H:%M:%S')}]")
                print(f"   Nodes ({len(self.node_ordering)}): {self.node_ordering}")
                print(f"   Adjacency Matrix:\n{self.current_adj_matrix}\n")

                # In production, this would publish to Redis or a fast message queue
                # so app_brains.py can instantly read the latest matrix on each step.

                # Poll every 5 seconds (LLDP intervals are typically slow, e.g., 5-30s)
                await asyncio.sleep(5)

            except Exception as e:
                print(f"⚠️ Error polling controller: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    bridge = TopologyBridge()
    try:
        asyncio.run(bridge.run_discovery_loop())
    except KeyboardInterrupt:
        print("\n🛑 Topology Bridge Shutting Down.")
