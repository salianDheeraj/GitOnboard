const fs = require('fs');
const http = require('http');

http.get('http://127.0.0.1:8000/api/repos/flask/dependencies', (res) => {
  let rawData = '';
  res.on('data', (chunk) => { rawData += chunk; });
  res.on('end', () => {
    try {
      const data = JSON.parse(rawData);
      analyze(data.nodes, data.edges);
    } catch (e) {
      console.error(e.message);
    }
  });
}).on('error', (e) => {
  console.error(`Error: ${e.message}`);
});

function analyze(nodes, edges) {
  console.log(`Nodes: ${nodes.length}`);
  console.log(`Edges: ${edges.length}`);
  
  const validNodes = new Set(nodes.map(n => n.id));
  const validEdges = edges.filter(e => validNodes.has(e.source) && validNodes.has(e.target));
  
  console.log(`Valid Edges: ${validEdges.length}`);
  
  const inDegrees = {};
  const outDegrees = {};
  nodes.forEach(n => {
    inDegrees[n.id] = 0;
    outDegrees[n.id] = 0;
  });
  
  validEdges.forEach(e => {
    outDegrees[e.source]++;
    inDegrees[e.target]++;
  });
  
  const totalDegrees = {};
  nodes.forEach(n => {
    totalDegrees[n.id] = inDegrees[n.id] + outDegrees[n.id];
  });
  
  const maxIn = Math.max(...Object.values(inDegrees));
  const maxOut = Math.max(...Object.values(outDegrees));
  const maxTotal = Math.max(...Object.values(totalDegrees));
  
  const maxInNodes = nodes.filter(n => inDegrees[n.id] === maxIn).map(n => n.id);
  const maxOutNodes = nodes.filter(n => outDegrees[n.id] === maxOut).map(n => n.id);
  const maxTotalNodes = nodes.filter(n => totalDegrees[n.id] === maxTotal).map(n => n.id);
  
  const avgDegree = (validEdges.length * 2) / nodes.length;
  
  // Quick Tarjan's for SCC
  let index = 0;
  const stack = [];
  const indices = {};
  const lowlinks = {};
  const onStack = {};
  const sccs = [];
  
  function strongconnect(v) {
    indices[v] = index;
    lowlinks[v] = index;
    index++;
    stack.push(v);
    onStack[v] = true;
    
    const targets = validEdges.filter(e => e.source === v).map(e => e.target);
    for (const w of targets) {
      if (indices[w] === undefined) {
        strongconnect(w);
        lowlinks[v] = Math.min(lowlinks[v], lowlinks[w]);
      } else if (onStack[w]) {
        lowlinks[v] = Math.min(lowlinks[v], indices[w]);
      }
    }
    
    if (lowlinks[v] === indices[v]) {
      const scc = [];
      let w;
      do {
        w = stack.pop();
        onStack[w] = false;
        scc.push(w);
      } while (w !== v);
      sccs.push(scc);
    }
  }
  
  nodes.forEach(n => {
    if (indices[n.id] === undefined) {
      strongconnect(n.id);
    }
  });
  
  // Weakly connected components (undirected)
  const wccAdj = {};
  nodes.forEach(n => wccAdj[n.id] = []);
  validEdges.forEach(e => {
    wccAdj[e.source].push(e.target);
    wccAdj[e.target].push(e.source);
  });
  
  const visited = new Set();
  let numWcc = 0;
  nodes.forEach(n => {
    if (!visited.has(n.id)) {
      numWcc++;
      const q = [n.id];
      visited.add(n.id);
      while (q.length > 0) {
        const u = q.shift();
        for (const v of wccAdj[u]) {
          if (!visited.has(v)) {
            visited.add(v);
            q.push(v);
          }
        }
      }
    }
  });
  
  console.log("\n--- Graph Statistics ---");
  console.log(`Total Nodes: ${nodes.length}`);
  console.log(`Total Valid Edges: ${validEdges.length}`);
  console.log(`Graph Density: ${validEdges.length / (nodes.length * (nodes.length - 1))}`);
  console.log(`Weakly Connected Components: ${numWcc}`);
  console.log(`Strongly Connected Components: ${sccs.length}`);
  console.log(`Is DAG (No cycles): ${sccs.length === nodes.length}`);
  
  console.log(`\nAverage Degree: ${avgDegree.toFixed(2)}`);
  console.log(`Maximum Total Degree: ${maxTotal} (Nodes: ${maxTotalNodes.slice(0,3).join(', ')})`);
  console.log(`Maximum In-Degree: ${maxIn} (Nodes: ${maxInNodes.slice(0,3).join(', ')})`);
  console.log(`Maximum Out-Degree: ${maxOut} (Nodes: ${maxOutNodes.slice(0,3).join(', ')})`);
}
