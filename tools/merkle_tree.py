"""
Merkle Tree implementation for ownership proofs.

Allows proving data ownership without revealing actual content.
"""

import hashlib
from typing import List, Optional, Tuple


class MerkleTree:
    """
    Merkle tree for creating compact, verifiable proofs.
    
    Build from interaction hashes to prove ownership without revealing conversations.
    """
    
    def __init__(self, leaves: List[str]):
        """
        Build Merkle tree from leaf hashes.
        
        Args:
            leaves: List of SHA-256 hashes (interaction content_hash values)
        """
        if not leaves:
            raise ValueError("Cannot build Merkle tree from empty list")
        
        self.leaves = leaves
        self.tree = self._build_tree(leaves)
        self.root = self.tree[-1][0] if self.tree else None
    
    def _build_tree(self, leaves: List[str]) -> List[List[str]]:
        """
        Build Merkle tree bottom-up.
        
        Args:
            leaves: Leaf hashes
        
        Returns:
            List of levels, where tree[0] is leaves and tree[-1] is root
        """
        tree = [leaves]
        current_level = leaves
        
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                # If odd number of nodes, duplicate last one
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                # Hash concatenation of left and right
                parent = hashlib.sha256(f"{left}{right}".encode()).hexdigest()
                next_level.append(parent)
            tree.append(next_level)
            current_level = next_level
        
        return tree
    
    def get_proof(self, index: int) -> List[Tuple[str, str]]:
        """
        Get Merkle proof for leaf at index.
        
        Args:
            index: Index of leaf in original list
        
        Returns:
            List of (hash, position) tuples where position is 'left' or 'right'
        
        Example:
            For tree with 4 leaves, proof for index 0:
            [(sibling_hash, 'right'), (uncle_hash, 'right')]
        """
        if index < 0 or index >= len(self.leaves):
            raise ValueError(f"Index {index} out of range [0, {len(self.leaves)})")
        
        proof = []
        current_index = index
        
        for level in self.tree[:-1]:  # Exclude root level
            # Get sibling index (XOR with 1 flips last bit)
            sibling_index = current_index ^ 1
            
            if sibling_index < len(level):
                sibling_hash = level[sibling_index]
                # Determine if sibling is on left or right
                position = 'left' if sibling_index < current_index else 'right'
                proof.append((sibling_hash, position))
            
            # Move to parent level
            current_index //= 2
        
        return proof
    
    def verify_proof(self, leaf_hash: str, proof: List[Tuple[str, str]], root: str) -> bool:
        """
        Verify Merkle proof.
        
        Args:
            leaf_hash: Hash of the leaf to verify
            proof: List of (hash, position) tuples from get_proof()
            root: Expected root hash
        
        Returns:
            True if proof is valid, False otherwise
        
        Example:
            >>> tree = MerkleTree(['hash1', 'hash2', 'hash3', 'hash4'])
            >>> proof = tree.get_proof(0)
            >>> tree.verify_proof('hash1', proof, tree.root)
            True
        """
        current = leaf_hash
        
        for sibling_hash, position in proof:
            if position == 'left':
                # Sibling is on left, current is on right
                current = hashlib.sha256(f"{sibling_hash}{current}".encode()).hexdigest()
            else:
                # Sibling is on right, current is on left
                current = hashlib.sha256(f"{current}{sibling_hash}".encode()).hexdigest()
        
        return current == root
    
    def get_root(self) -> str:
        """Get Merkle root hash."""
        return self.root
    
    def get_leaf_count(self) -> int:
        """Get number of leaves in tree."""
        return len(self.leaves)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"MerkleTree(leaves={len(self.leaves)}, root={self.root[:16]}...)"


def build_merkle_tree_from_interactions(interactions: List[dict]) -> MerkleTree:
    """
    Build Merkle tree from list of interactions.
    
    Args:
        interactions: List of interaction dicts with 'content_hash' field
    
    Returns:
        MerkleTree built from interaction hashes
    
    Example:
        >>> interactions = get_all_interactions('my-project')
        >>> tree = build_merkle_tree_from_interactions(interactions)
        >>> print(tree.root)
    """
    hashes = [interaction['content_hash'] for interaction in interactions]
    return MerkleTree(hashes)

