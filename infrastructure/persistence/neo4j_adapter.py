"""
Adapter for Neo4j persistence implementing the Neo4jRepository port.
"""
from typing import Optional, List, Dict, Any
import logging
from neo4j import GraphDatabase

from domain.models.address import Address, EntityType
from domain.ports.neo4j_repository import Neo4jRepository

logger = logging.getLogger(__name__)


class Neo4jAdapter(Neo4jRepository):
    """Adapter that makes Neo4j driver conform to Neo4jRepository port."""

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j adapter.

        Args:
            uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
            user: Neo4j username
            password: Neo4j password
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.logger = logger

    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()

    def save_address(self, address: Address) -> bool:
        """
        Save or update an address in the Neo4j graph database.

        Args:
            address: Address domain model to save

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.driver.session() as session:
                # Convert EntityType enum to string for storage
                entity_type_str = address.entity_type.value if address.entity_type else "unknown"
                
                query = """
                MERGE (a:Address {address: $address})
                SET a.chain = $chain,
                    a.decimals = $decimals,
                    a.wallet_id = $wallet_id,
                    a.entity_type = $entity_type,
                    a.entity_confidence = $entity_confidence,
                    a.labels = $labels,
                    a.first_seen = $first_seen,
                    a.last_seen = $last_seen,
                    a.transaction_count = $transaction_count,
                    a.total_received_satoshis = $total_received_satoshis,
                    a.total_sent_satoshis = $total_sent_satoshis,
                    a.balance_satoshis = $balance_satoshis,
                    a.is_contract = $is_contract,
                    a.tags = $tags,
                    a.updated_at = datetime()
                RETURN a.address as addr
                """
                
                result = session.run(query, 
                                   address=address.address,
                                   chain=address.chain,
                                   decimals=address.decimals,
                                   wallet_id=address.wallet_id,
                                   entity_type=entity_type_str,
                                   entity_confidence=address.entity_confidence,
                                   labels=address.labels,
                                   first_seen=address.first_seen,
                                   last_seen=address.last_seen,
                                   transaction_count=address.transaction_count,
                                   total_received_satoshis=address.total_received_satoshis,
                                   total_sent_satoshis=address.total_sent_satoshis,
                                   balance_satoshis=address.balance_satoshis,
                                   is_contract=address.is_contract,
                                   tags=address.tags)
                
                record = result.single()
                if record:
                    self.logger.debug(f"Saved/updated address: {record['addr']}")
                    return True
                else:
                    self.logger.warning(f"No record returned when saving address: {address.address}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error saving address {address.address} to Neo4j: {e}")
            return False

    def save_transaction(self, txid: str, from_address: str, to_address: str,
                        amount: float, block_time: int, is_change: bool = False,
                        hop: int = 1, chain: str = "btc") -> bool:
        """
        Save a transaction relationship between addresses in Neo4j.

        Args:
            txid: Transaction ID
            from_address: Source address
            to_address: Destination address
            amount: Transaction amount in native unit (BTC/ETH)
            block_time: Unix timestamp of block confirmation
            is_change: Whether this is a change output
            hop: Hop distance from the root address
            chain: Chain identifier ("btc", "eth", etc.)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.driver.session() as session:
                query = """
                // Ensure source address exists
                MERGE (from:Address {address: $from_address})
                SET from.chain = coalesce(from.chain, $chain),
                    from.updated_at = datetime()
                ON CREATE SET 
                    from.first_seen = datetime()
                
                // Ensure destination address exists  
                MERGE (to:Address {address: $to_address})
                SET to.chain = coalesce(to.chain, $chain),
                    to.updated_at = datetime()
                ON CREATE SET
                    to.first_seen = datetime()
                
                // Create or update transaction relationship
                MERGE (from)-[r:SENT {txid: $txid}]->(to)
                SET r.amount = $amount,
                    r.block_time = $block_time,
                    r.is_change = $is_change,
                    r.hop = $hop,
                    r.chain = $chain,
                    r.updated_at = datetime()
                RETURN r.txid as txid
                """
                
                result = session.run(query,
                                   from_address=from_address,
                                   to_address=to_address,
                                   txid=txid,
                                   amount=amount,
                                   block_time=block_time,
                                   is_change=is_change,
                                   hop=hop,
                                   chain=chain)
                
                record = result.single()
                if record:
                    self.logger.debug(f"Saved transaction: {record['txid']} from {from_address} to {to_address}")
                    return True
                else:
                    self.logger.warning(f"No record returned when saving transaction: {txid}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error saving transaction {txid} from {from_address} to {to_address}: {e}")
            return False

    def get_address(self, address: str, chain: str = "btc") -> Optional[Address]:
        """
        Retrieve an address from the Neo4j graph database.

        Args:
            address: Blockchain address to retrieve
            chain: Chain identifier

        Returns:
            Address domain model or None if not found
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (a:Address {address: $address})
                WHERE a.chain IS NULL OR a.chain = $chain
                RETURN a.address as address,
                       a.chain as chain,
                       a.decimals as decimals,
                       a.wallet_id as wallet_id,
                       a.entity_type as entity_type,
                       a.entity_confidence as entity_confidence,
                       a.labels as labels,
                       a.first_seen as first_seen,
                       a.last_seen as last_seen,
                       a.transaction_count as transaction_count,
                       a.total_received_satoshis as total_received_satoshis,
                       a.total_sent_satoshis as total_sent_satoshis,
                       a.balance_satoshis as balance_satoshis,
                       a.is_contract as is_contract,
                       a.tags as tags
                """
                
                result = session.run(query, address=address, chain=chain)
                record = result.single()
                
                if record:
                    # Convert entity_type string back to Enum
                    entity_type_str = record["entity_type"] or "unknown"
                    try:
                        entity_type = EntityType(entity_type_str)
                    except ValueError:
                        entity_type = EntityType.UNKNOWN
                    
                    # Convert datetime objects
                    first_seen = record["first_seen"]
                    last_seen = record["last_seen"]
                    
                    # Neo4j datetime objects need special handling
                    if hasattr(first_seen, 'to_native'):
                        first_seen = first_seen.to_native()
                    if hasattr(last_seen, 'to_native'):
                        last_seen = last_seen.to_native()
                    
                    chain_val = record.get("chain") or "btc"
                    decimals_val = record.get("decimals") or (18 if chain_val == "eth" else 8)
                    addr = Address(
                        address=record["address"],
                        chain=chain_val,
                        decimals=decimals_val,
                        wallet_id=record["wallet_id"],
                        entity_type=entity_type,
                        entity_confidence=record["entity_confidence"] or 0.0,
                        labels=record["labels"] or [],
                        first_seen=first_seen,
                        last_seen=last_seen,
                        transaction_count=record["transaction_count"] or 0,
                        total_received_satoshis=record["total_received_satoshis"] or 0,
                        total_sent_satoshis=record["total_sent_satoshis"] or 0,
                        balance_satoshis=record["balance_satoshis"] or 0,
                        is_contract=record["is_contract"] or False,
                        tags=record["tags"] or []
                    )
                    
                    self.logger.debug(f"Retrieved address: {address}")
                    return addr
                else:
                    self.logger.debug(f"Address not found: {address}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error retrieving address {address} from Neo4j: {e}")
            return None

    def find_path(self, start_address: str, end_address: str, max_hops: int = 5,
                  chain: str = "btc") -> List[List[str]]:
        """
        Find all paths between two addresses within max_hops.

        Args:
            start_address: Starting address
            end_address: Target address
            max_hops: Maximum number of hops to traverse
            chain: Chain identifier

        Returns:
            List of paths, where each path is a list of addresses
        """
        try:
            with self.driver.session() as session:
                # Using variable-length path pattern to find paths
                query = f"""
                MATCH path = (from:Address {{address: $start_address}})-[r:SENT*1..{max_hops}]-(to:Address {{address: $end_address}})
                WHERE NONE(x IN relationships(path) WHERE x.is_change = true)
                  AND ALL(x IN relationships(path) WHERE x.chain IS NULL OR x.chain = $chain)
                RETURN [n IN nodes(path) | n.address] as path
                LIMIT 100
                """
                
                result = session.run(query, start_address=start_address, end_address=end_address, chain=chain)
                paths = []
                
                for record in result:
                    path = record["path"]
                    if path:  # Make sure path is not empty
                        paths.append(path)
                
                self.logger.debug(f"Found {len(paths)} paths from {start_address} to {end_address} (max hops: {max_hops})")
                return paths
                
        except Exception as e:
            self.logger.error(f"Error finding paths from {start_address} to {end_address}: {e}")
            return []

    def get_transaction_history(self, address: str, limit: int = 100,
                                chain: str = "btc") -> List[Dict[str, Any]]:
        """
        Get transaction history for an address from the graph.

        Args:
            address: Blockchain address
            limit: Maximum number of transactions to return
            chain: Chain identifier

        Returns:
            List of transaction dictionaries
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (target:Address {address: $address})-[r:SENT]-(connected:Address)
                WHERE r.chain IS NULL OR r.chain = $chain
                RETURN r.txid as txid,
                       r.amount as amount,
                       r.block_time as block_time,
                       r.is_change as is_change,
                       r.chain as chain,
                       endNode(r).address AS to_address,
                       startNode(r).address AS from_address
                ORDER BY r.block_time DESC
                LIMIT $limit
                """
                
                result = session.run(query, address=address, limit=limit, chain=chain)
                transactions = []
                
                for record in result:
                    # Convert block_time from Neo4j datetime if needed
                    block_time = record["block_time"]
                    if hasattr(block_time, 'to_native'):
                        block_time = block_time.to_native()
                    
                    tx = {
                        "txid": record["txid"],
                        "amount": record["amount"],
                        "block_time": int(block_time) if block_time else 0,
                        "is_change": record["is_change"],
                        "chain": record.get("chain") or "btc",
                        "to_address": record["to_address"],
                        "from_address": record["from_address"]
                    }
                    transactions.append(tx)
                
                self.logger.debug(f"Retrieved {len(transactions)} transactions for address {address}")
                return transactions
                
        except Exception as e:
            self.logger.error(f"Error getting transaction history for {address}: {e}")
            return []

    def run_query(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Run an arbitrary Cypher query and return results as list of dicts.

        Args:
            query: Cypher query string
            **kwargs: Query parameters

        Returns:
            List of result records as dicts
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, **kwargs)
                return [dict(rec) for rec in result]
        except Exception as e:
            self.logger.error(f"Error running query: {e}")
            return []

    def get_subgraph_edges(self, address: str, depth: int = 2, limit: int = 5000,
                           chain: str = "btc") -> List[Dict[str, Any]]:
        """
        Get all edges (transactions) in the subgraph around an address.

        Args:
            address: Root address
            depth: Traversal depth
            limit: Maximum edges to return
            chain: Chain identifier

        Returns:
            List of edge dicts with from_addr, to_addr, amount, txid, etc.
        """
        depth_literal = f"*1..{depth}"
        query = f"""
        MATCH (root:Address {{address:$addr}})
        MATCH p=(root)-[:SENT{depth_literal}]-(b:Address)
        WHERE ALL(rel IN relationships(p) WHERE rel.chain IS NULL OR rel.chain = $chain)
        UNWIND relationships(p) AS rel
        WITH DISTINCT rel
        MATCH (a:Address)-[rel]->(b:Address)
        RETURN 
            a.address AS from_addr,
            b.address AS to_addr,
            rel.amount AS amount,
            rel.txid AS txid,
            coalesce(rel.hop, 1) AS hop,
            coalesce(rel.block_time, rel.timestamp) AS ts,
            coalesce(rel.is_change, false) AS is_change,
            a.entity_type AS from_entity,
            b.entity_type AS to_entity,
            a.labels AS from_labels,
            b.labels AS to_labels,
            coalesce(rel.chain, 'btc') AS chain
        LIMIT $limit
        """
        rows = []
        try:
            recs = self.run_query(query, addr=address, limit=limit, chain=chain)
            for rec in recs:
                row = dict(rec)
                if not isinstance(row.get('from_labels'), list):
                    row['from_labels'] = []
                if not isinstance(row.get('to_labels'), list):
                    row['to_labels'] = []
                ts = row.get('ts')
                if ts:
                    if hasattr(ts, 'to_native'):
                        ts = ts.to_native()
                    if hasattr(ts, 'timestamp'):
                        ts = ts.timestamp()
                    try:
                        row['ts'] = int(float(ts))
                    except (ValueError, TypeError):
                        row['ts'] = 0
                else:
                    row['ts'] = 0
                rows.append(row)
        except Exception as e:
            self.logger.error(f"Error getting subgraph edges for {address}: {e}")
        return rows

    def clear_database(self) -> bool:
        """
        Clear all data from the Neo4j graph database.
        Use with caution - mainly for testing.

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.driver.session() as session:
                # Delete all relationships first, then nodes
                session.run("MATCH ()-[r]->() DELETE r")
                session.run("MATCH (n) DELETE n")
                self.logger.warning("Cleared all data from Neo4j database")
                return True
        except Exception as e:
            self.logger.error(f"Error clearing Neo4j database: {e}")
            return False