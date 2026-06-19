"""
blockchain.py — Core Blockchain Engine for E-Voting System
Uses real SHA-256 hashing via Python's hashlib.
"""

import hashlib
import json
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────
#  BLOCK
# ─────────────────────────────────────────────────────────────

class Block:
    """
    Represents a single block in the blockchain.
    Each vote is stored as one block.
    """

    DIFFICULTY = 2  # Number of leading zeros required (Proof of Work)

    def __init__(self, index: int, data: dict, previous_hash: str):
        self.index = index
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.data = data
        self.previous_hash = previous_hash
        self.nonce = 0
        self.hash = self._mine()

    # ── Hashing ──────────────────────────────────────────────

    def calculate_hash(self) -> str:
        """Compute SHA-256 hash of the block contents."""
        block_contents = {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        raw = json.dumps(block_contents, sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()

    def _mine(self) -> str:
        """Proof of Work: find a nonce so that hash starts with DIFFICULTY zeros."""
        target = "0" * self.DIFFICULTY
        while True:
            h = self.calculate_hash()
            if h.startswith(target):
                return h
            self.nonce += 1

    # ── Serialisation ────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    def __repr__(self):
        return f"<Block #{self.index} hash={self.hash[:12]}...>"


# ─────────────────────────────────────────────────────────────
#  BLOCKCHAIN
# ─────────────────────────────────────────────────────────────

class VotingBlockchain:
    """
    A blockchain tailored for secure electronic voting.

    Phases:
        registration → voting → ended
    """

    def __init__(self):
        self.chain: list[Block] = [self._genesis()]
        self.voters: dict[str, str] = {}     # voter_id  →  voter_name
        self.voted: set[str] = set()          # voter_ids that have cast a vote
        self.phase: str = "registration"

    # ── Genesis ──────────────────────────────────────────────

    def _genesis(self) -> Block:
        return Block(
            index=0,
            data={"type": "genesis", "message": "Blockchain E-Voting System Initialized"},
            previous_hash="0" * 64,
        )

    # ── Chain helpers ────────────────────────────────────────

    @property
    def latest_block(self) -> Block:
        return self.chain[-1]

    @property
    def total_votes(self) -> int:
        return sum(1 for b in self.chain if b.data.get("type") == "vote")

    # ── Voter Registration ───────────────────────────────────

    def register_voter(self, voter_id: str, name: str) -> tuple[bool, str]:
        if self.phase != "registration":
            return False, "Registration is closed."
        if not voter_id.strip() or not name.strip():
            return False, "Voter ID and name cannot be empty."
        if voter_id in self.voters:
            return False, f"Voter ID '{voter_id}' is already registered."
        self.voters[voter_id] = name
        return True, f"'{name}' registered successfully."

    # ── Voting ───────────────────────────────────────────────

    def cast_vote(self, voter_id: str, candidate_id: str) -> tuple[bool, str | Block]:
        if self.phase != "voting":
            return False, "Voting is not currently active."
        if voter_id not in self.voters:
            return False, "Voter ID not found. Please register first."
        if voter_id in self.voted:
            return False, "You have already cast your vote."

        # Anonymise the voter ID before storing on-chain
        anon_id = hashlib.sha256(
            (voter_id + "🔒_secure_salt_2026").encode()
        ).hexdigest()[:16]

        data = {
            "type": "vote",
            "anon_voter_id": anon_id,
            "candidate_id": candidate_id,
        }
        block = Block(len(self.chain), data, self.latest_block.hash)
        self.chain.append(block)
        self.voted.add(voter_id)
        return True, block

    # ── Phase Control ────────────────────────────────────────

    def start_voting(self) -> tuple[bool, str]:
        if self.phase != "registration":
            return False, "Cannot start voting from current phase."
        self.phase = "voting"
        return True, "Voting phase has started."

    def end_election(self) -> tuple[bool, str]:
        if self.phase != "voting":
            return False, "Cannot end election from current phase."
        self.phase = "ended"
        return True, "Election has ended. Results are final."

    # ── Results ──────────────────────────────────────────────

    def get_tally(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for block in self.chain:
            if block.data.get("type") == "vote":
                cid = block.data["candidate_id"]
                tally[cid] = tally.get(cid, 0) + 1
        return tally

    # ── Integrity Check ──────────────────────────────────────

    def is_valid(self) -> tuple[bool, str]:
        """Verify every block in the chain."""
        for i in range(1, len(self.chain)):
            curr = self.chain[i]
            prev = self.chain[i - 1]

            # Check hash linkage
            if curr.previous_hash != prev.hash:
                return False, f"Block #{i}: previous_hash mismatch (chain broken)."

            # Recompute hash to detect tampering
            if curr.hash != curr.calculate_hash():
                return False, f"Block #{i}: hash invalid (data tampered)."

        return True, "Blockchain is intact. All blocks verified."

    # ── Serialisation ────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "block_count": len(self.chain),
            "total_votes": self.total_votes,
            "registered_voters": len(self.voters),
            "chain": [b.to_dict() for b in self.chain],
        }
