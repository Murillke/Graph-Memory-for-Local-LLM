# Graph-Memory-for-Local-LLM
A local graph memory architecture for CLI agents, enabling associative, context-aware long-term memory and intelligent relation pruning.

Local Graph Memory Architecture for CLI AgentsWhen building a local memory storage system for CLI agents using a property graph, the biggest challenge is managing the sheer volume and complexity of relationships (edges) over time.This document outlines a strategy for handling, managing, and maintaining these relations.1. Defining the Ontology (Nodes & Relations)Before you can manage relations, you must strictly define what they are. A Property Graph allows you to assign labels to Nodes and types to Edges, as well as properties (like timestamps) to both.Visualizing the Ontologygraph TD
    %% Define Nodes
    T([🎯 Task / Goal])
    A([⚡ Action / Command])
    A2([⚡ Next Action])
    R{📂 Resource}
    E[⚠️ Error]
    C((💡 Concept))

    %% Define Edges
    T -->|GENERATED| A
    A -->|MODIFIED| R
    A -->|READS| R
    A -->|RESULTED_IN| E
    A -->|RESOLVES| E
    A -->|FOLLOWS| A2
    
    %% Semantic Edges
    T -.->|RELATES_TO| C
    A -.->|RELATES_TO| C
    R -.->|RELATES_TO| C
    
    classDef default fill:#f9f9f9,stroke:#333,stroke-width:2px;
    classDef concept fill:#fff3cd,stroke:#ffc107,stroke-width:2px;
    class C concept;
Core Node TypesTask / Goal: What the user asked the agent to do.Action / Command: The actual CLI command executed.Resource: Files, directories, URLs, or API endpoints interacted with.Concept / Entity: Abstract things (e.g., "Docker", "Python", "Authentication").Error: Exceptions or stderr outputs encountered.Core Relation (Edge) TypesEdges should always have a direction (Subject -> Predicate -> Object) and properties (at minimum, a timestamp and a weight).Edge TypeSource NodeTarget NodePurposeGENERATEDTaskActionLinks a goal to the command(s) used to achieve it.MODIFIEDActionResourceTracks which commands changed which files.READSActionResourceTracks dependencies (e.g., cat config.json).RESULTED_INActionErrorLinks a failed command to the specific error output.RESOLVESActionErrorCrucial: Tracks the command that successfully fixed a previous error.RELATES_TOAnyConceptSemantic linking (e.g., script.py RELATES_TO Python).FOLLOWSActionActionTemporal linking to reconstruct chronological history.2. The Relation LifecycleHandling relations isn't just about inserting them; it's about managing their full lifecycle to prevent the graph from becoming a tangled, useless mess.Memory Processing Flowflowchart LR
    subgraph Write Phase [1. Extraction & Creation]
        DE[Deterministic Logs] --> WriteDB[(Graph DB)]
        LLM[LLM Semantic Parse] --> WriteDB
    end

    subgraph Read Phase [2. Retrieval]
        User[User Prompt] --> RAG[Contextual Spreading]
        WriteDB --> RAG
        RAG --> Context[Agent Context]
    end

    subgraph Prune Phase [3. Strengthening & Forgetting]
        Context -->|Successful Use| ST[Increase Edge Weight]
        Context -->|Time Passes| DC[Decay Weight]
        ST --> Update[(Update DB)]
        DC --> GC{Below Threshold?}
        GC -->|Yes| Del[Delete Edge]
        GC -->|No| Update
    end
    
    style Write Phase fill:#e6f3ff,stroke:#0066cc
    style Read Phase fill:#e6ffe6,stroke:#00cc00
    style Prune Phase fill:#ffe6e6,stroke:#cc0000
A. Extraction & Creation (The "Write" Phase)How do you get the relations in the first place?Deterministic Extraction: Your CLI tool automatically creates deterministic edges. If the agent runs sed -i 's/foo/bar/' config.txt, your backend automatically creates: (Action:sed) -[MODIFIED]-> (Resource:config.txt).LLM-Based Extraction (Information Extraction): After a task is completed, pass the transcript to a lightweight local LLM (or your main LLM) with a strict JSON schema prompt to extract semantic triples:{
  "subject": "Authentication Bug",
  "predicate": "RESOLVES",
  "object": "Updated JWT Secret in .env"
}
B. Retrieval & Traversal (The "Read" Phase)When the user gives a new prompt, how does the agent use the relations?Contextual Spreading Activation (Graph RAG):Identify the entities in the current user prompt (e.g., "Fix the Docker build").Find the Node for "Docker" and the current working directory "Resource".Traverse outward by 1 or 2 "hops" (edges) to find related Errors, Tasks, or Actions the agent previously performed.Pass this localized sub-graph to the agent as context: "Last time you worked on Docker here, you ran into Error X and solved it by modifying File Y."C. Strengthening & Forgetting (The "Pruning" Phase)Without pruning, local graph databases bloat and slow down retrieval.Edge Weighting: Every edge should have a weight (e.g., 1.0) and a last_accessed property.Strengthening: Every time a traversal crosses an edge to successfully help the agent, increase its weight (e.g., weight += 0.1) and update last_accessed.Decay/Garbage Collection: Run a background thread or a CLI command (e.g., agent memory prune) that decays edge weights over time. If a RELATES_TO edge weight drops below a threshold, delete the edge. Note: Keep deterministic edges (like MODIFIED) longer than semantic edges.3. Recommended Local Tech StackSince this is for a CLI agent, you cannot rely on heavy infrastructure (like running a full Neo4j Docker container). You need embedded, local-first graph engines.Kùzu (Highly Recommended): An embedded property graph database (like SQLite for graphs). It's incredibly fast, runs locally in-process, and uses Cypher query language. Perfect for Python/Node/Rust CLI tools.SQLite + NetworkX: Use SQLite to store the raw nodes and triples, and load them into a NetworkX (Python) directed graph in memory for complex traversals during execution.FalkorDB / RedisGraph: If your CLI agent already spins up local processes, FalkorDB is very fast, though less "embedded" than Kuzu.CozoDB: A transactional, relational-graph-vector database. Great if you want to mix Datalog/Graph queries with Vector similarity search later.4. Example: Handling a Relation in Code (Python/Kuzu conceptually)# Pseudo-code for relation management after a task completes

def store_memory(agent_action, target_file, error_encountered=None):
    # 1. Upsert Nodes
    db.execute("MERGE (a:Action {cmd: $cmd, time: $time})", cmd=agent_action)
    db.execute("MERGE (f:Resource {path: $path})", path=target_file)
    
    # 2. Create standard relational edge
    db.execute("""
        MATCH (a:Action {cmd: $cmd}), (f:Resource {path: $path})
        MERGE (a)-[r:MODIFIED]->(f)
        ON CREATE SET r.weight = 1.0, r.created_at = $time
        ON MATCH SET r.weight = r.weight + 0.5, r.last_accessed = $time
    """, cmd=agent_action, path=target_file, time=now())
    
    # 3. Handle Conditional Relations (e.g., Errors)
    if error_encountered:
        db.execute("MERGE (e:Error {msg: $err})", err=error_encountered)
        db.execute("""
            MATCH (a:Action {cmd: $cmd}), (e:Error {msg: $err})
            CREATE (a)-[:RESULTED_IN {time: $time}]->(e)
        """)
Summary Checklist for Relations[ ] Are your edges directed? (A -> B is different from B -> A).[ ] Do your edges have timestamps for temporal queries?[ ] Do your edges have weights to allow for "forgetting" obsolete context?[ ] Are you using MERGE (upsert) logic to prevent duplicating the same relation multiple times?
