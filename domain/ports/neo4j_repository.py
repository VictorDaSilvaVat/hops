"""
Port (interface) for Neo4j persistence operations.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from ..models.address import Address


class Neo4jRepository(ABC):
    """Abstract interface for Neo4j persistence operations."""

    @abstractmethod
    def save_address(self, address: Address) -> bool:
        """
        Save or update an address in the graph database.

        Args:
            address: Address domain model to save

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def save_transaction(self, txid: str, from_address: str, to_address: str,
                        amount: float, block_time: int, is_change: bool = False,
                        hop: int = 1) -> bool:
        """
        Save a transaction relationship between addresses.

        Args:
            txid: Transaction ID
            from_address: Source address
            to_address: Destination address
            amount: Transaction amount in BTC
            block_time: Unix timestamp of block confirmation
            is_change: Whether this is a change output
            hop: Hop distance from the root address

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_address(self, address: str) -> Optional[Address]:
        """
        Retrieve an address from the graph database.

        Args:
            address: Bitcoin address to retrieve

        Returns:
            Address domain model or None if not found
        """
        pass

    @abstractmethod
    def find_path(self, start_address: str, end_address: str, max_hops: int = 5) -> List[List[str]]:
        """
        Find all paths between two addresses within max_hops.

        Args:
            start_address: Starting Bitcoin address
            end_address: Target Bitcoin address
            max_hops: Maximum number of hops to traverse

        Returns:
            List of paths, where each path is a list of addresses
        """
        pass

    @abstractmethod
    def get_transaction_history(self, address: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get transaction history for an address from the graph.

        Args:
            address: Bitcoin address
            limit: Maximum number of transactions to return

        Returns:
            List of transaction dictionaries
        """
        pass

    @abstractmethod
    def run_query(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Run an arbitrary Cypher query.

        Args:
            query: Cypher query string
            **kwargs: Query parameters

        Returns:
            List of result records as dicts
        """
        pass

    @abstractmethod
    def get_subgraph_edges(self, address: str, depth: int = 2, limit: int = 5000) -> List[Dict[str, Any]]:
        """
        Get all edges in the subgraph around an address.

        Args:
            address: Root address
            depth: Traversal depth
            limit: Maximum edges

        Returns:
            List of edge dicts
        """
        pass

    @abstractmethod
    def clear_database(self) -> bool:
        """
        Clear all data from the graph database.
        Use with caution - mainly for testing.

        Returns:
            True if successful, False otherwise
        """
        pass