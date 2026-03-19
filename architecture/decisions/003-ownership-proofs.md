# ADR 003: Ownership Proofs Without Revealing Conversations

**Date:** 2026-03-04

**Status:** Accepted

---

## Context

**Problem:** How do you prove you own certain data without revealing the actual conversations?

**Use Cases:**
1. Prove you had a conversation about topic X on date Y
2. Prove you extracted entity Z from your conversations
3. Prove your knowledge came from real conversations (not fabricated)
4. Share proof of work without exposing private conversations (cursing, personal info)

**Requirements:**
1. Cryptographically verifiable
2. Doesn't reveal conversation content
3. Simple to implement (no ZK-SNARK complexity)
4. Works with existing hash chain
5. Can prove specific facts without revealing all data

---

## Decision

We will implement **Merkle Tree-based ownership proofs** using existing interaction hashes.

**Key Insight:** We already have SHA-256 hashes of every interaction. We can build a Merkle tree from these hashes to create compact, verifiable proofs.

---

## How It Works

### 1. Merkle Tree Construction

**Build tree from interaction hashes:**

```
                    Root Hash (Merkle Root)
                    /                    \
            Hash(H1+H2)                Hash(H3+H4)
            /        \                  /        \
          H1         H2               H3         H4
          |          |                |          |
    Interaction  Interaction    Interaction  Interaction
        1            2               3            4
```

**Properties:**
- Root hash represents ALL interactions
- Can prove specific interaction exists without revealing others
- Compact proof (log N hashes)

### 2. Ownership Proof

**What you publish:**
```json
{
  "project_name": "my-project",
  "merkle_root": "abc123...",
  "timestamp": "2026-03-04T10:00:00Z",
  "interaction_count": 42,
  "signature": "signed_with_private_key"
}
```

**What you keep private:**
- Actual conversation content
- Individual interaction hashes
- Merkle tree structure

### 3. Selective Disclosure

**Prove specific interaction exists:**

```json
{
  "claim": "I had a conversation about JWT tokens on 2026-03-04",
  "proof": {
    "interaction_hash": "def456...",
    "merkle_path": ["hash1", "hash2", "hash3"],
    "merkle_root": "abc123..."
  }
}
```

**Verifier can:**
- ✅ Verify interaction_hash is in the tree
- ✅ Verify merkle_root matches published root
- ❌ Cannot see conversation content
- ❌ Cannot see other interactions

---

## Implementation

### Step 1: Build Merkle Tree

```python
# tools/merkle_tree.py

import hashlib
from typing import List, Tuple

class MerkleTree:
    def __init__(self, hashes: List[str]):
        """Build Merkle tree from interaction hashes."""
        self.leaves = hashes
        self.tree = self._build_tree(hashes)
        self.root = self.tree[-1][0] if self.tree else None
    
    def _build_tree(self, hashes: List[str]) -> List[List[str]]:
        """Build Merkle tree bottom-up."""
        if not hashes:
            return []
        
        tree = [hashes]
        current_level = hashes
        
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                parent = hashlib.sha256(f"{left}{right}".encode()).hexdigest()
                next_level.append(parent)
            tree.append(next_level)
            current_level = next_level
        
        return tree
    
    def get_proof(self, index: int) -> List[str]:
        """Get Merkle proof for interaction at index."""
        proof = []
        current_index = index
        
        for level in self.tree[:-1]:
            sibling_index = current_index ^ 1  # XOR to get sibling
            if sibling_index < len(level):
                proof.append(level[sibling_index])
            current_index //= 2
        
        return proof
    
    def verify_proof(self, leaf_hash: str, proof: List[str], root: str) -> bool:
        """Verify Merkle proof."""
        current = leaf_hash
        for sibling in proof:
            current = hashlib.sha256(f"{current}{sibling}".encode()).hexdigest()
        return current == root
```

### Step 2: Generate Ownership Proof

```python
# scripts/generate_ownership_proof.py

from tools.sql_db import get_all_interactions
from tools.merkle_tree import MerkleTree
import json

def generate_ownership_proof(project_name: str):
    """Generate ownership proof for project."""
    # Get all interaction hashes
    interactions = get_all_interactions(project_name)
    hashes = [i['content_hash'] for i in interactions]
    
    # Build Merkle tree
    tree = MerkleTree(hashes)
    
    # Create proof
    proof = {
        "project_name": project_name,
        "merkle_root": tree.root,
        "timestamp": datetime.now().isoformat(),
        "interaction_count": len(hashes),
        "earliest_interaction": interactions[0]['timestamp'],
        "latest_interaction": interactions[-1]['timestamp']
    }
    
    return proof
```

### Step 3: Prove Specific Fact

```python
# scripts/prove_fact.py

def prove_fact(project_name: str, entity_name: str):
    """Prove you extracted an entity without revealing conversation."""
    # Get entity and its extraction proof
    entity = get_entity(project_name, entity_name)
    source_interactions = entity['extraction_proof']['source_interactions']
    
    # Get interaction hashes
    interactions = get_all_interactions(project_name)
    hashes = [i['content_hash'] for i in interactions]
    
    # Build Merkle tree
    tree = MerkleTree(hashes)
    
    # Get proof for each source interaction
    proofs = []
    for uuid in source_interactions:
        index = find_interaction_index(uuid, interactions)
        merkle_proof = tree.get_proof(index)
        proofs.append({
            "interaction_uuid": uuid,
            "interaction_hash": interactions[index]['content_hash'],
            "merkle_proof": merkle_proof
        })
    
    return {
        "entity": entity_name,
        "merkle_root": tree.root,
        "source_proofs": proofs
    }
```

---

## Use Cases

### Use Case 1: Prove Project Ownership

**Publish:**
```json
{
  "project_name": "my-project",
  "merkle_root": "abc123...",
  "interaction_count": 42,
  "timestamp": "2026-03-04"
}
```

**Proves:** You have 42 interactions in this project as of this date

**Doesn't reveal:** What those conversations were about

### Use Case 2: Prove Entity Extraction

**Publish:**
```json
{
  "entity": "JWT Token",
  "merkle_root": "abc123...",
  "source_proof": {
    "interaction_hash": "def456...",
    "merkle_path": ["hash1", "hash2"]
  }
}
```

**Proves:** You extracted "JWT Token" from a real conversation

**Doesn't reveal:** The actual conversation content

### Use Case 3: Prove Conversation on Date

**Publish:**
```json
{
  "claim": "Had conversation about authentication on 2026-03-04",
  "merkle_root": "abc123...",
  "interaction_hash": "def456...",
  "timestamp": "2026-03-04T10:30:00Z",
  "merkle_proof": ["hash1", "hash2", "hash3"]
}
```

**Proves:** You had a conversation at that time

**Doesn't reveal:** What was said

---

## Advantages

**Simple:**
- ✅ Uses existing SHA-256 hashes
- ✅ No complex cryptography (no ZK-SNARK)
- ✅ Easy to implement and verify

**Compact:**
- ✅ Proof size is O(log N) hashes
- ✅ 1000 interactions = ~10 hashes in proof
- ✅ Small enough to share easily

**Verifiable:**
- ✅ Anyone can verify proof
- ✅ Cryptographically secure
- ✅ Can't fake without knowing hashes

**Private:**
- ✅ Doesn't reveal conversation content
- ✅ Doesn't reveal other interactions
- ✅ Selective disclosure (prove what you want)

---

## Limitations

**What it CAN'T do:**
- ❌ Can't prove conversation content without revealing hash
- ❌ Can't prove you DON'T have certain data
- ❌ Can't prove temporal ordering without revealing more

**What it CAN do:**
- ✅ Prove you have N interactions
- ✅ Prove specific interaction exists
- ✅ Prove entity came from real conversation
- ✅ Prove ownership without revealing content

---

## Related Decisions

- ADR 001: Command-Based Interface
- ADR 002: Configuration System
- Hash chain in SQL database (existing)

---

## References

- Merkle Trees: https://en.wikipedia.org/wiki/Merkle_tree
- User question: "can we proof that we own the data without releasing the conversations?"

