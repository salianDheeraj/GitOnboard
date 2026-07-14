import requests
import networkx as nx
import json
from collections import Counter

def analyze_graph():
    print("Fetching graph data for 'flask'...")
    try:
        response = requests.get("http://127.0.0.1:8000/api/repos/flask/dependencies")
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Failed to fetch data: {e}")
        return

    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    
    print(f"Nodes: {len(nodes)}")
    print(f"Edges: {len(edges)}")
    
    # Build NetworkX graph
    G = nx.DiGraph()
    for n in nodes:
        G.add_node(n['id'])
    
    # Filter edges to only include those where both source and target exist
    valid_nodes = set(n['id'] for n in nodes)
    valid_edges = []
    for e in edges:
        if e['source'] in valid_nodes and e['target'] in valid_nodes:
            valid_edges.append(e)
            G.add_edge(e['source'], e['target'])
            
    print(f"Valid Edges (both nodes exist): {len(valid_edges)}")
    
    # Metrics
    # Number of strongly connected components (SCC)
    scc = list(nx.strongly_connected_components(G))
    num_scc = len(scc)
    
    # Is it a DAG? (Checking for cycles)
    is_dag = nx.is_directed_acyclic_graph(G)
    num_cycles = 0
    if not is_dag:
        # Just find simple cycles, but limit the search if there are too many
        try:
            cycles_iter = nx.simple_cycles(G)
            for i, _ in enumerate(cycles_iter):
                num_cycles += 1
                if num_cycles > 1000:
                    print("More than 1000 cycles found, stopping cycle count.")
                    break
        except Exception:
            pass
            
    # Number of weakly connected components (disconnected components)
    wcc = list(nx.weakly_connected_components(G))
    num_wcc = len(wcc)
    
    # In-degree/out-degree distribution
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    total_degrees = {n: in_degrees[n] + out_degrees[n] for n in G.nodes()}
    
    in_dist = Counter(in_degrees.values())
    out_dist = Counter(out_degrees.values())
    total_dist = Counter(total_degrees.values())
    
    # Maximum node degree
    max_in = max(in_degrees.values()) if in_degrees else 0
    max_out = max(out_degrees.values()) if out_degrees else 0
    max_total = max(total_degrees.values()) if total_degrees else 0
    
    max_in_nodes = [n for n, d in in_degrees.items() if d == max_in]
    max_out_nodes = [n for n, d in out_degrees.items() if d == max_out]
    max_total_nodes = [n for n, d in total_degrees.items() if d == max_total]
    
    # Average degree
    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()
    avg_degree = (num_edges * 2) / num_nodes if num_nodes > 0 else 0
    
    # Graph density
    density = nx.density(G)
    
    print("\n--- Graph Statistics ---")
    print(f"Total Nodes: {num_nodes}")
    print(f"Total Valid Edges: {num_edges}")
    print(f"Graph Density: {density:.6f}")
    print(f"Weakly Connected Components (Disconnected Components): {num_wcc}")
    print(f"Strongly Connected Components: {num_scc}")
    print(f"Is DAG (No cycles): {is_dag}")
    if not is_dag:
        print(f"Number of simple cycles (capped at 1000): {num_cycles}")
        
    print(f"\nAverage Degree: {avg_degree:.2f}")
    print(f"Maximum Total Degree: {max_total} (Nodes: {', '.join(max_total_nodes[:3])})")
    print(f"Maximum In-Degree: {max_in} (Nodes: {', '.join(max_in_nodes[:3])})")
    print(f"Maximum Out-Degree: {max_out} (Nodes: {', '.join(max_out_nodes[:3])})")
    
    print("\nIn-Degree Distribution (Degree: Count):")
    for d, c in sorted(in_dist.items(), reverse=True)[:10]:
        print(f"  {d}: {c} nodes")
        
    print("\nOut-Degree Distribution (Degree: Count):")
    for d, c in sorted(out_dist.items(), reverse=True)[:10]:
        print(f"  {d}: {c} nodes")

if __name__ == "__main__":
    analyze_graph()
