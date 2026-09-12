"""WellPaiD Trader - Memory Module

Simple local memory system using JSON storage.
Supports saving, retrieving, and searching memories with timestamps and categories.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

try:
    from agent.core.storage import sqlite_db
except ImportError:
    from ..core.storage import sqlite_db


@dataclass
class Memory:
    """Represents a single memory entry."""
    id: str
    content: str
    category: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any]


class MemoryStore:
    """Local memory store using JSON file storage.
    
    Supports saving, retrieving, searching, and deleting memories.
    All memories are stored locally and never sent externally.
    """
    
    def __init__(self, storage_path: str = "agent/data/memory.db") -> None:
        """Initialize memory store.
        
        State is persisted in SQLite (write-through on every mutation).

        Args:
            storage_path: Path to SQLite database file
        """
        self.storage_path = Path(storage_path)
        self.memories: dict[str, Memory] = {}
        self._init_db()

    def _connect(self):
        """Open a short-lived, auto-closing connection to the store."""
        return sqlite_db(self.storage_path)

    def _init_db(self) -> None:
        """Create schema and load persisted memories into memory."""
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS memories"
                "(id TEXT PRIMARY KEY, content TEXT, category TEXT, "
                "created_at TEXT, updated_at TEXT, metadata TEXT)"
            )
            for r in conn.execute("SELECT * FROM memories"):
                import json as _json

                self.memories[r["id"]] = Memory(
                    id=r["id"],
                    content=r["content"],
                    category=r["category"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    metadata=_json.loads(r["metadata"] or "{}"),
                )

    def _persist_memory(self, memory: Memory) -> None:
        import json as _json

        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memories VALUES(?,?,?,?,?,?)",
                (
                    memory.id,
                    memory.content,
                    memory.category,
                    memory.created_at,
                    memory.updated_at,
                    _json.dumps(memory.metadata),
                ),
            )

    def _load(self) -> None:
        """Legacy entry point: state is loaded by _init_db at construction."""
        return None

    def _save(self) -> None:
        """Legacy entry point: persistence is write-through per mutation."""
        return None
    
    def save(
        self,
        content: str,
        category: str = "general",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Memory:
        """Save a new memory.
        
        Args:
            content: Memory content
            category: Memory category (e.g., 'research', 'task', 'note')
            metadata: Optional metadata dictionary
            
        Returns:
            Created Memory object
        """
        now = datetime.now().isoformat()
        memory = Memory(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self.memories[memory.id] = memory
        self._persist_memory(memory)
        return memory
    
    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID.
        
        Args:
            memory_id: Memory ID
            
        Returns:
            Memory object or None if not found
        """
        return self.memories.get(memory_id)
    
    def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Search memories, ranked by relevance.
        
        Ranking: term-frequency in content first, then newest. A query
        that appears twice in one memory outranks a single mention;
        category-only searches stay newest-first.
        
        Args:
            query: Search query (searches content)
            category: Filter by category
            limit: Maximum results to return
            
        Returns:
            List of matching Memory objects
        """
        results = list(self.memories.values())
        
        # Filter by category
        if category:
            results = [m for m in results if m.category == category]
        
        # Filter and rank by query
        if query:
            query_lower = query.lower()
            scored = []
            for m in results:
                hits = m.content.lower().count(query_lower)
                if hits > 0:
                    scored.append((hits, m.created_at, m))
            # Most mentions first, newest breaks ties.
            scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
            results = [m for _, _, m in scored]
        else:
            # Sort by creation time (newest first)
            results.sort(key=lambda m: m.created_at, reverse=True)
        
        # Apply limit
        return results[:limit]
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.
        
        Args:
            memory_id: Memory ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        if memory_id in self.memories:
            del self.memories[memory_id]
            with self._connect() as conn:
                conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            return True
        return False
    
    def list_categories(self) -> list[str]:
        """Get list of all categories.
        
        Returns:
            Sorted list of unique categories
        """
        categories = set(m.category for m in self.memories.values())
        return sorted(categories)
    
    def count(self, category: Optional[str] = None) -> int:
        """Count memories.
        
        Args:
            category: Optional category to count
            
        Returns:
            Number of memories
        """
        if category:
            return len([m for m in self.memories.values() if m.category == category])
        return len(self.memories)
    
    def clear(self) -> int:
        """Clear all memories.
        
        Returns:
            Number of memories cleared
        """
        count = len(self.memories)
        self.memories = {}
        with self._connect() as conn:
            conn.execute("DELETE FROM memories")
        return count
