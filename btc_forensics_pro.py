"""
Main Bitcoin forensics processing class - refactored to use hexagonal architecture.
"""
import os
import time
import json
import logging
import requests
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
import pandas as pd
from neo4j import GraphDatabase

from infrastructure.external.openrouter_client import generate_with_openrouter, AVAILABLE_MODELS as OPENROUTER_MODELS

# Domain models
from domain.models.address import Address, EntityType
from domain.models.analysis.cluster import TransactionCluster

# Domain services
from domain.services.address_analyzer import AddressAnalyzerService
from domain.services.analysis.cluster_analyzer import ClusterAnalyzerService
from domain.services.reporting.forensic_report_generator import ForensicReportGenerator

# Infrastructure adapters
from infrastructure.adapters.blockstream_adapter import BlockstreamAdapter
from infrastructure.adapters.wallet_explorer_adapter import WalletExplorerAdapter
from infrastructure.adapters.etherscan_adapter import EtherscanAdapter
from infrastructure.adapters.blockbook_adapter import BlockbookAdapter
from infrastructure.adapters.trongrid_adapter import TronGridAdapter
from infrastructure.adapters.blockfrost_adapter import BlockfrostAdapter
from infrastructure.persistence.neo4j_adapter import Neo4jAdapter
from infrastructure.reporting.forensic_report_adapter import ForensicReportAdapter

# Configuration
from config import Config
from security import safe_path_component

# Exceptions
from exceptions import APIError, NetworkError

logger = logging.getLogger(__name__)


class BTCForensicsPro:
    """
    Main Bitcoin forensics processing class using hexagonal architecture.
    
    This class orchestrates the analysis of Bitcoin addresses and transactions
    using dependency injection for better testability and maintainability.
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        verbose: bool = True,
        max_hops: int = 3,
        min_amount: float = 0.00001,
        chain: str = "btc",
        config: Optional[Config] = None,
        case_id: Optional[str] = None,
        investigator: str = "HOPS System",
        ai_provider: str = "ollama",
        ai_model: Optional[str] = None,
        blockchain_api=None,
        wallet_api=None,
        neo4j_repository=None,
        address_analyzer_service=None,
        cluster_analyzer_service=None,
        report_generator=None
    ):
        """
        Initialize the blockchain forensics processor (multi-chain).

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            verbose: Enable verbose logging
            max_hops: Maximum number of hops to trace
            min_amount: Minimum transaction amount to consider (anti-dust filter)
            chain: Chain identifier ("btc", "eth", etc.)
            config: Configuration object (optional)
            case_id: Case identifier for reporting (optional)
            investigator: Investigator name for reporting
            ai_provider: AI provider ("ollama" or "openrouter")
            ai_model: Model name for the provider (defaults to provider default)
            blockchain_api: Blockchain API adapter (optional, for DI)
            wallet_api: Wallet API adapter (optional, for DI)
            neo4j_repository: Neo4j repository adapter (optional, for DI)
            address_analyzer_service: Address analyzer service (optional, for DI)
            cluster_analyzer_service: Cluster analyzer service (optional, for DI)
            report_generator: Report generator adapter (optional, for DI)
        """
        # Store configuration
        self.config = config or Config()
        self.verbose = verbose
        self.max_hops = max_hops
        self.min_amount = min_amount  # FILTRO ANTI-DUST
        self.chain = chain
        self.chain_name = {"btc": "Bitcoin", "eth": "Ethereum", "bch": "Bitcoin Cash", "trx": "TRON", "ada": "Cardano"}.get(chain, "Bitcoin")
        self.unit = {"btc": "BTC", "eth": "ETH", "bch": "BCH", "trx": "TRX", "ada": "ADA"}.get(chain, "BTC")
        self.rate_limit_delay = 0.6  # seconds between hop traces
        self.case_id = case_id
        self._last_trace_error = ""
        self.investigator = investigator
        self.ai_provider = ai_provider
        self.ai_model = ai_model or ("llama3" if ai_provider == "ollama" else "google/gemini-2.0-flash-001")
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if self.verbose:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        # Initialize infrastructure components with dependency injection
        self.neo4j_repo = neo4j_repository or Neo4jAdapter(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
        
        # Select blockchain API adapter based on chain
        if chain == "eth":
            eth_key = self.config.api.etherscan_api_key
            self.blockchain_api = blockchain_api or EtherscanAdapter(api_key=eth_key)
            self.wallet_api = wallet_api or WalletExplorerAdapter()
        elif chain == "bch":
            self.blockchain_api = blockchain_api or BlockbookAdapter()
            self.wallet_api = wallet_api or WalletExplorerAdapter()
        elif chain == "trx":
            self.blockchain_api = blockchain_api or TronGridAdapter()
            self.wallet_api = wallet_api or WalletExplorerAdapter()
        elif chain == "ada":
            self.blockchain_api = blockchain_api or BlockfrostAdapter(config=self.config)
            self.wallet_api = wallet_api or WalletExplorerAdapter()
        else:
            self.blockchain_api = blockchain_api or BlockstreamAdapter()
            self.wallet_api = wallet_api or WalletExplorerAdapter()
        
        # Initialize domain services
        self.address_analyzer = address_analyzer_service or AddressAnalyzerService(
            blockchain_api=self.blockchain_api,
            wallet_api=self.wallet_api,
            min_amount_threshold=self.min_amount,
            chain=self.chain,
            sanctions_checker=self.check_sanctions,
        )
        
        self.cluster_analyzer = cluster_analyzer_service or ClusterAnalyzerService()
        
        # Initialize reporting
        self.report_generator = report_generator or ForensicReportAdapter(
            case_id=self.case_id,
            investigator=self.investigator
        )
        
        # Cache for wallet IDs to reduce API calls
        self.wallet_cache = {}
        self.processed_addresses = set()  # To prevent infinite loops
        
        # Analysis results storage
        self.last_analysis_results = {}
        
        self.logger.info(f"BTCForensicsPro initialized for chain={chain}")

    def close(self):
        """Close all connections and clean up resources."""
        if hasattr(self.neo4j_repo, 'close'):
            self.neo4j_repo.close()
        self.logger.info("BTCForensicsPro resources cleaned up")

    def log(self, level: str, *args):
        """Log a message with the given level."""
        if level == "debug":
            self.logger.debug(*args)
        elif level == "info":
            self.logger.info(*args)
        elif level == "warning":
            self.logger.warning(*args)
        elif level == "error":
            self.logger.error(*args)
        elif level == "critical":
            self.logger.critical(*args)

    # ---------------------------------------------------------
    # ENHANCED FORENSIC ANALYSIS METHODS
    # ---------------------------------------------------------
    
    def analyze_address_comprehensive(self, address: str) -> Dict[str, Any]:
        """
        Perform comprehensive forensic analysis on a Bitcoin address.
        
        Args:
            address: Bitcoin address to analyze
            
        Returns:
            Dictionary containing comprehensive analysis results
        """
        self.logger.info(f"Starting comprehensive analysis for address: {address}")
        
        try:
            # Step 1: Basic address analysis
            address_model = self.address_analyzer.analyze_address(address)
            
            # Step 2: Get transaction history
            raw_transactions = self._get_raw_transaction_history(address)
            
            # Step 3: Perform cluster analysis
            clusters = []
            if raw_transactions:
                clusters = self.cluster_analyzer.analyze_transaction_patterns(raw_transactions)
            
            # Step 4: Detect mixing patterns
            mixing_analysis = {}
            if raw_transactions:
                mixing_analysis = self.cluster_analyzer.detect_mixing_patterns(raw_transactions)
            
            # Step 5: Detect peeling chain patterns
            peeling_analysis = {}
            if raw_transactions:
                peeling_analysis = self.cluster_analyzer.detect_peeling_chain(raw_transactions)
            
            # Step 6: Compile comprehensive results
            analysis_results = {
                "address_info": {
                    "address": address_model.address,
                    "wallet_id": address_model.wallet_id,
                    "entity_type": address_model.entity_type.value,
                    "entity_confidence": address_model.entity_confidence,
                    "labels": address_model.labels,
                    "transaction_count": address_model.transaction_count,
                    "total_received_btc": address_model.total_received_btc,
                    "total_sent_btc": address_model.total_sent_btc,
                    "balance_btc": address_model.balance_btc,
                    "first_seen": address_model.first_seen.isoformat() if address_model.first_seen else None,
                    "last_seen": address_model.last_seen.isoformat() if address_model.last_seen else None,
                    "is_contract": address_model.is_contract,
                    "tags": address_model.tags
                },
                "transaction_analysis": {
                    "total_transactions": len(raw_transactions),
                    "transaction_details": raw_transactions[:10]  # Limit for performance
                },
                "clustering_analysis": {
                    "clusters_found": len(clusters),
                    "clusters": [
                        {
                            "cluster_id": cluster.cluster_id,
                            "address_count": len(cluster.addresses),
                            "transaction_count": cluster.transaction_count,
                            "total_volume_btc": cluster.total_volume_btc,
                            "first_seen": cluster.first_seen.isoformat() if cluster.first_seen else None,
                            "last_seen": cluster.last_seen.isoformat() if cluster.last_seen else None,
                            "entity_types": list(cluster.entity_types),
                            "risk_score": cluster.risk_score
                        }
                        for cluster in clusters
                    ]
                },
                "pattern_analysis": {
                    "mixing_detection": mixing_analysis,
                    "peeling_chain_detection": peeling_analysis
                },
                "risk_assessment": self._calculate_overall_risk(address_model, clusters, mixing_analysis, peeling_analysis),
                "metadata": {
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                    "analyzer_version": "HOPS v2.0 (Phase 3)"
                }
            }
            
            # Store results for reporting
            self.last_analysis_results = analysis_results
            
            # Record evidence
            evidence_id = f"addr_analysis_{address}_{int(time.time())}"
            self.report_generator.record_evidence(
                evidence_id=evidence_id,
                description=f"Comprehensive forensic analysis of Bitcoin address {address}",
                source="HOPS Forensics Pro Analysis Engine",
                timestamp=datetime.utcnow()
            )
            
            self.logger.info(f"Comprehensive analysis completed for address {address}")
            return analysis_results
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive analysis for {address}: {e}")
            raise

    def _get_raw_transaction_history(self, address: str) -> List[Dict[str, Any]]:
        """Get raw transaction data from the blockchain API."""
        try:
            # Get transaction history from Neo4j (which should have been populated by trace operations)
            db_transactions = self.neo4j_repo.get_transaction_history(address, limit=1000, chain=self.chain)

            # Convert to standard format
            raw_transactions = []
            for tx in db_transactions:
                raw_tx = {
                    "txid": tx.get("txid", ""),
                    "from_address": tx.get("from_address", ""),
                    "to_address": tx.get("to_address", ""),
                    "amount": tx.get("amount", 0.0),
                    "block_time": tx.get("block_time", 0),
                    "is_change": tx.get("is_change", False),
                    "from_entity_type": tx.get("from_entity_type", "unknown"),
                    "to_entity_type": tx.get("to_entity_type", "unknown")
                }
                raw_transactions.append(raw_tx)
            
            return raw_transactions
            
        except Exception as e:
            self.logger.error(f"Error getting raw transaction history for {address}: {e}")
            return []

    def _calculate_overall_risk(self, address_model: Address, clusters: List[TransactionCluster], 
                              mixing_analysis: Dict, peeling_analysis: Dict) -> Dict[str, Any]:
        """Calculate overall risk assessment for the address."""
        # Base risk from entity type
        entity_risk = address_model.entity_confidence * {
            EntityType.SANCTIONED: 1.0,
            EntityType.DARKNET_MARKET: 0.9,
            EntityType.MIXER: 0.8,
            EntityType.GAMBLING: 0.6,
            EntityType.EXCHANGE: 0.3,
            EntityType.DEFI_PROTOCOL: 0.4,
            EntityType.BRIDGE: 0.5,
            EntityType.MINING_POOL: 0.2,
            EntityType.WALLET_SERVICE: 0.3,
            EntityType.MARKETPLACE: 0.4,
            EntityType.INDIVIDUAL: 0.1,
            EntityType.UNKNOWN: 0.5
        }.get(address_model.entity_type, 0.5)
        
        # Cluster risk
        cluster_risk = 0.0
        if clusters:
            avg_cluster_risk = sum(cluster.risk_score for cluster in clusters) / len(clusters)
            cluster_risk = min(1.0, avg_cluster_risk * len(clusters) / 10.0)  # Normalize
        
        # Pattern risks
        mixing_risk = mixing_analysis.get("confidence", 0.0) if mixing_analysis.get("is_mixing", False) else 0.0
        peeling_risk = peeling_analysis.get("confidence", 0.0) if peeling_analysis.get("is_peeling_chain", False) else 0.0
        
        # Combined risk (weighted average)
        total_risk = (
            entity_risk * 0.4 +
            cluster_risk * 0.3 +
            mixing_risk * 0.2 +
            peeling_risk * 0.1
        )
        
        # Risk level categorization
        if total_risk >= 0.8:
            risk_level = "HIGH"
        elif total_risk >= 0.5:
            risk_level = "MEDIUM"
        elif total_risk >= 0.2:
            risk_level = "LOW"
        else:
            risk_level = "VERY_LOW"
        
        return {
            "overall_risk_score": min(1.0, total_risk),
            "risk_level": risk_level,
            "entity_risk": entity_risk,
            "cluster_risk": cluster_risk,
            "mixing_risk": mixing_risk,
            "peeling_risk": peeling_risk,
            "factors": {
                "high_risk_entity": address_model.entity_type in [EntityType.SANCTIONED, EntityType.DARKNET_MARKET, EntityType.MIXER],
                "mixing_detected": mixing_analysis.get("is_mixing", False),
                "peeling_chain_detected": peeling_analysis.get("is_peeling_chain", False),
                "multiple_clusters": len(clusters) > 3 if clusters else False,
                "high_value_transactions": address_model.total_received_btc > 10.0
            }
        }

    # ---------------------------------------------------------
    # REPORTING METHODS
    # ---------------------------------------------------------
    
    def generate_forensic_report(self, format_type: str = "json") -> str:
        """
        Generate a forensic report from the last analysis.
        
        Args:
            format_type: Output format ("json", "html", "txt")
            
        Returns:
            Report content as string
        """
        if not self.last_analysis_results:
            raise ValueError("No analysis results available. Run analyze_address_comprehensive first.")
        
        self.logger.info(f"Generating forensic report in {format_type} format")
        
        try:
            report = self.report_generator.generate_report(
                self.last_analysis_results, 
                format_type=format_type
            )
            
            self.logger.info(f"Forensic report generated successfully ({len(report)} characters)")
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating forensic report: {e}")
            raise

    def save_forensic_report_to_files(self, address: str, format_type: str = "json", 
                                    out_dir: str = "reports") -> Dict[str, str]:
        """
        Save forensic report to files.
        
        Args:
            address: Bitcoin address associated with the report
            format_type: Output format ("json", "html", "txt")
            out_dir: Output directory
            
        Returns:
            Dictionary with paths to generated files
        """
        import os
        from datetime import datetime
        
        os.makedirs(out_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        
        # Generate report content
        report_content = self.generate_forensic_report(format_type)
        
        # Determine file extension
        ext_map = {"json": ".json", "html": ".html", "txt": ".txt"}
        ext = ext_map.get(format_type.lower(), ".txt")
        
        try:
            # Create filename
            safe_address = safe_path_component(address, "address")
            filename = f"forensic_report_{safe_address}_{timestamp}{ext}"
            filepath = os.path.join(out_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report_content)
            
            self.logger.info(f"Forensic report saved to: {filepath}")
            return {"report": filepath}
            
        except Exception as e:
            self.logger.error(f"Error saving forensic report: {e}")
            return {"report": ""}

    # ---------------------------------------------------------
    # ENHANCED TRACE METHODS (with analysis integration)
    # ---------------------------------------------------------
    
    def trace_and_analyze(self, address: str, hop: int = 1, direction: str = "both") -> Dict[str, Any]:
        """
        Trace transactions and perform comprehensive analysis.
        
        Args:
            address: Starting Bitcoin address
            hop: Current hop number (starts at 1)
            direction: "both", "fanin" (backwards only), or "fanout" (forwards only)
            
        Returns:
            Analysis results dictionary
        """
        self.logger.info(f"Starting trace and analyze for address {address} at hop {hop}")
        
        # Perform the trace operation (populates Neo4j with transaction data)
        self.trace(address, hop, direction)
        
        # Then perform comprehensive analysis
        analysis_results = self.analyze_address_comprehensive(address)
        
        return analysis_results

    # ---------------------------------------------------------
    # LEGACY COMPATIBILITY METHODS (maintained for backward compatibility)
    # ---------------------------------------------------------
    
    def trace(self, address: str, hop: int = 1, direction: str = "both",
               progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Trace transactions from an address.
        Dispatches to chain-specific implementation.
        Returns True if any data was saved.

        Args:
            address: Address to trace
            hop: Starting hop number
            direction: "fanin", "fanout", or "both"
            progress_callback: Optional callback(status_message) for progress updates
        """
        self._last_trace_error = ""
        self._progress_callback = progress_callback
        if hop == 1:
            # Fresh top-level trace (not a recursive hop expansion) — clear
            # state left over from a previous, unrelated analysis on this
            # instance so it doesn't get skipped as "already processed".
            self.processed_addresses = set()
        try:
            if self.chain == "eth":
                return self._trace_ethereum(address, hop)
            if self.chain == "trx":
                if direction in ("fanin", "fanout"):
                    self.log("debug", f"TRX ignoring direction param {direction}, using both")
                return self._trace_tron(address, hop)
            if self.chain == "ada":
                if direction in ("fanin", "fanout"):
                    self.log("debug", f"ADA ignoring direction param {direction}, using both")
                return self._trace_cardano(address, hop)
            return self._trace_legacy(address, hop, direction)
        except Exception as e:
            self._last_trace_error = str(e)
            self.log("error", f"Unhandled exception in trace: {e}")
            return False

    def _report_progress(self, message: str):
        """Report progress via callback if provided."""
        if self._progress_callback:
            try:
                self._progress_callback(message)
            except Exception:
                pass  # Don't let callback errors break tracing
        self.log("info", message)

    def _trace_legacy(self, address: str, hop: int = 1, direction: str = "both") -> bool:
        """Legacy trace implementation from Phase 2.
        Returns True if any data was saved to Neo4j.
        """
        self.logger.debug(f"Tracing address {address} at hop {hop}, direction {direction}")

        # FAN-IN solo permite 1 hop
        if direction == "fanin" and hop > 1:
            return False

        # FAN-OUT permite hasta max_hops
        if direction == "fanout" and hop > self.max_hops:
            return False

        # Evitar loops (use canonical address for loop detection)
        canonical_addr = address
        key = f"{canonical_addr}-{direction}-{hop}"
        if key in self.processed_addresses:
            return True
        self.processed_addresses.add(key)

        try:
            # Get address transactions from blockchain API
            txs = self.blockchain_api.get_address_transactions(address, limit=200)
        except (APIError, NetworkError) as e:
            self.log("error", f"Failed to get transactions for address {address}: {e}")
            return False
        except Exception as e:
            self.log("error", f"Unexpected error getting transactions for {address}: {e}")
            return False
        
        if not txs:
            self.log("debug", f"No transactions found for address {address}")
            return False
        self.log("info", f"Found {len(txs)} transactions for address {address}")

        # Analyze and save the address (WASS fallback handled inside analyze_address)
        try:
            address_model = self.address_analyzer.analyze_address(address)
            self.neo4j_repo.save_address(address_model)
            # Use canonical address from the model (Blockbook may normalize legacy→cashaddr)
            canonical_addr = address_model.address
        except Exception as e:
            self.log("error", f"Failed to analyze/save address {address}: {e}")
            canonical_addr = address

        self.log("debug", f"Using canonical address: {canonical_addr} (original input: {address})")

        # Process each transaction
        # NOTE: txs from get_address_txs already contain full transaction data
        # (vin, vout, status) so we do NOT need a separate get_transaction call.
        for tx in txs:
            txid = tx.get("txid")
            if not txid:
                continue

            try:
                # The tx object from /txs/chain already has full data
                inputs = tx.get("vin", [])
                outputs = tx.get("vout", [])
                block_time = tx.get("status", {}).get("block_time", 0)

                # Process FAN-OUT (address sends funds)
                is_sender = any(
                    vin.get("prevout", {}).get("scriptpubkey_address") == canonical_addr
                    for vin in inputs
                    if vin.get("prevout")
                )

                if direction in ("both", "fanout") and is_sender:
                    self._process_outputs(
                        address=canonical_addr,
                        inputs=inputs,
                        outputs=outputs,
                        block_time=block_time,
                        hop=hop,
                        txid=txid,
                        direction="fanout"
                    )

                # Process FAN-IN (address receives funds)
                if direction in ("both", "fanin"):
                    self._process_inputs(
                        address=canonical_addr,
                        inputs=inputs,
                        outputs=outputs,
                        block_time=block_time,
                        hop=hop,
                        txid=txid,
                        direction="fanin"
                    )

            except (APIError, NetworkError) as e:
                self.log("error", f"API/Network error processing transaction {txid}: {e}")
                continue
            except Exception as e:
                self.log("error", f"Unexpected error processing transaction {txid}: {e}")
                continue

        return True

    def _process_outputs(self, address: str, inputs: List, outputs: List, 
                        block_time: int, hop: int, txid: str, direction: str):
        """Process transaction outputs when address is the sender."""
        for vout in outputs:
            dest = vout.get("scriptpubkey_address")
            if not dest:
                continue

            amount = vout.get("value", 0) / 1e8  # Convert satoshis to BTC

            # FILTRO ANTI-DUST
            if amount < self.min_amount:
                continue

            # Determine if this is change output
            is_change = self._is_change_output(inputs, dest)

            # Create transaction data for persistence
            tx_payload = {
                "txid": txid,
                "from_address": address,
                "to_address": dest,
                "amount": amount,
                "block_time": block_time,
                "is_change": is_change,
                "hop": hop,
                "chain": self.chain,
            }

            # Save transaction to Neo4j
            try:
                self.neo4j_repo.save_transaction(**tx_payload)
            except Exception as e:
                self.log("error", f"Failed to save transaction to Neo4j: {e}")

            # Recursively trace destination address (only for non-change outputs in fanout)
            if not is_change and direction == "fanout":
                time.sleep(self.rate_limit_delay)
                self.trace(dest, hop + 1, direction="fanout")

    def _process_inputs(self, address: str, inputs: List, outputs: List,
                       block_time: int, hop: int, txid: str, direction: str):
        """Process transaction inputs when address is the receiver."""
        for vout in outputs:
            # Only process outputs that belong to our address
            dest = vout.get("scriptpubkey_address")
            if dest != address:
                continue

            amount = vout.get("value", 0) / 1e8  # Convert satoshis to BTC

            # FILTRO ANTI-DUST
            if amount < self.min_amount:
                continue

            # Process each input (source of funds)
            for vin in inputs:
                src = vin.get("prevout", {}).get("scriptpubkey_address")
                if not src:
                    continue

                # Create transaction data for persistence
                tx_payload = {
                    "txid": txid,
                    "from_address": src,
                    "to_address": address,
                    "amount": amount,
                    "block_time": block_time,
                    "is_change": False,  # Inputs are never change relative to the receiver
                    "hop": hop,
                    "chain": self.chain,
                }

                # Save transaction to Neo4j
                try:
                    self.neo4j_repo.save_transaction(**tx_payload)
                except Exception as e:
                    self.log("error", f"Failed to save transaction to Neo4j: {e}")

                # Recursively trace source address (only 1 hop back for fanin)
                if direction == "fanin":
                    time.sleep(self.rate_limit_delay)
                    self.trace(src, hop + 1, direction="fanin")

    def _is_change_output(self, inputs: List, output_address: str) -> bool:
        """
        Determine if an output is likely a change output.
        
        An output is considered change if it goes back to one of the input wallets.
        Only applies to BTC (WalletExplorer); other chains always return False.
        """
        if self.chain != "btc":
            return False
        try:
            input_wallets = set()
            for vin in inputs:
                if vin.get("prevout") and vin["prevout"].get("scriptpubkey_address"):
                    input_addr = vin["prevout"]["scriptpubkey_address"]
                    wallet_id = self.wallet_api.get_wallet_id(input_addr)
                    if wallet_id and wallet_id != "unknown":
                        input_wallets.add(wallet_id)

            output_wallet = self.wallet_api.get_wallet_id(output_address)
            return output_wallet in input_wallets
        except Exception as e:
            self.log("warning", f"Error determining change output: {e}")
            return False  # Default to not change on error

    # ---------------------------------------------------------
    # ETHEREUM TRACE
    # ---------------------------------------------------------

    def _trace_ethereum(self, address: str, hop: int = 1) -> bool:
        """Trace Ethereum transactions from an address via Etherscan API V2.
        Returns True if any data was saved to Neo4j.
        """
        address = address.lower()
        if hop > self.max_hops:
            self._last_trace_error = f"max_hops ({self.max_hops}) reached"
            return False

        key = f"eth-{address}-{hop}"
        if key in self.processed_addresses:
            return True
        self.processed_addresses.add(key)

        try:
            txs = self.blockchain_api.get_address_transactions(address, limit=200, chain="eth")
        except Exception as e:
            msg = f"Failed to get ETH transactions for {address}: {e}"
            self.log("error", msg)
            self._last_trace_error = msg
            return False

        if not txs:
            msg = f"No ETH transactions found for {address}"
            self.log("debug", msg)
            self._last_trace_error = msg
            return False

        self.log("info", f"Found {len(txs)} ETH transactions for {address}")

        # Analyze and save the address (WASS fallback handled inside analyze_address)
        try:
            address_model = self.address_analyzer.analyze_address(address)
            self.neo4j_repo.save_address(address_model)
        except Exception as e:
            self.log("error", f"Failed to analyze/save ETH address {address}: {e}")

        for tx in txs:
            txid = tx.get("txid") or tx.get("hash")
            if not txid:
                continue

            from_addr = tx.get("from", "").lower()
            to_addr = tx.get("to", "").lower()
            value_wei = tx.get("value", 0)
            amount_eth = float(value_wei) / 1e18
            block_time = tx.get("timeStamp", 0)
            tx_type = tx.get("tx_type", "normal")

            if tx_type == "erc20":
                continue
            if amount_eth < self.min_amount and tx_type == "normal" and amount_eth > 0:
                continue

            # FAN-OUT: address sends ETH
            if from_addr == address and to_addr:
                tx_payload = {
                    "txid": txid,
                    "from_address": address,
                    "to_address": to_addr,
                    "amount": amount_eth,
                    "block_time": int(block_time),
                    "is_change": False,
                    "hop": hop,
                    "chain": "eth",
                }
                try:
                    self.neo4j_repo.save_transaction(**tx_payload)
                except Exception as e:
                    self.log("error", f"Failed to save ETH tx {txid}: {e}")

                if tx_type == "normal":
                    time.sleep(self.rate_limit_delay)
                    self.trace(to_addr, hop + 1, direction="fanout")

            # FAN-IN: address receives ETH
            if to_addr == address and from_addr:
                tx_payload = {
                    "txid": txid,
                    "from_address": from_addr,
                    "to_address": address,
                    "amount": amount_eth,
                    "block_time": int(block_time),
                    "is_change": False,
                    "hop": hop,
                    "chain": "eth",
                }
                try:
                    self.neo4j_repo.save_transaction(**tx_payload)
                except Exception as e:
                    self.log("error", f"Failed to save ETH tx {txid}: {e}")

                if hop == 1:
                    time.sleep(self.rate_limit_delay)
                    self.trace(from_addr, hop + 1, direction="fanin")

        return True

    # ---------------------------------------------------------
    # TRON (TRX) TRACE
    # ---------------------------------------------------------

    def _trace_tron(self, address: str, hop: int = 1) -> bool:
        """Trace TRON transactions from an address via TRONGRID API.
        Returns True if any data was saved to Neo4j.
        """
        if hop > self.max_hops:
            self._last_trace_error = f"max_hops ({self.max_hops}) reached"
            return False

        key = f"trx-{address}-{hop}"
        if key in self.processed_addresses:
            return True
        self.processed_addresses.add(key)

        try:
            txs = self.blockchain_api.get_address_transactions(address, limit=200, chain="trx")
        except Exception as e:
            msg = f"Failed to get TRX transactions for {address}: {e}"
            self.log("error", msg)
            self._last_trace_error = msg
            return False

        if not txs:
            msg = f"No TRX transactions found for {address}"
            self.log("debug", msg)
            self._last_trace_error = msg
            return False

        self.log("info", f"Found {len(txs)} TRX transactions for {address}")

        # Analyze and save the address
        try:
            address_model = self.address_analyzer.analyze_address(address)
            self.neo4j_repo.save_address(address_model)
        except Exception as e:
            self.log("error", f"Failed to analyze/save TRX address {address}: {e}")

        for tx in txs:
            txid = tx.get("txid") or tx.get("transaction_id")
            if not txid:
                continue

            from_addr = tx.get("from", "")
            to_addr = tx.get("to", "")
            value_sun = tx.get("value", 0)
            amount_trx = float(value_sun) / 1e6
            block_time = tx.get("timeStamp", 0) or tx.get("block_timestamp", 0)
            tx_type = tx.get("tx_type", "transfer")

            if amount_trx < self.min_amount and tx_type == "transfer":
                continue

            # FAN-OUT: address sends TRX
            if from_addr == address and to_addr:
                tx_payload = {
                    "txid": txid,
                    "from_address": address,
                    "to_address": to_addr,
                    "amount": amount_trx,
                    "block_time": int(block_time) // 1000 if block_time > 1e12 else int(block_time),
                    "is_change": False,
                    "hop": hop,
                    "chain": "trx",
                }
                try:
                    self.neo4j_repo.save_transaction(**tx_payload)
                except Exception as e:
                    self.log("error", f"Failed to save TRX tx {txid}: {e}")

                if tx_type == "transfer":
                    time.sleep(self.rate_limit_delay)
                    self.trace(to_addr, hop + 1, direction="fanout")

            # FAN-IN: address receives TRX
            if to_addr == address and from_addr:
                tx_payload = {
                    "txid": txid,
                    "from_address": from_addr,
                    "to_address": address,
                    "amount": amount_trx,
                    "block_time": int(block_time) // 1000 if block_time > 1e12 else int(block_time),
                    "is_change": False,
                    "hop": hop,
                    "chain": "trx",
                }
                try:
                    self.neo4j_repo.save_transaction(**tx_payload)
                except Exception as e:
                    self.log("error", f"Failed to save TRX tx {txid}: {e}")

                if hop == 1:
                    time.sleep(self.rate_limit_delay)
                    self.trace(from_addr, hop + 1, direction="fanin")

        return True

    def _trace_cardano(self, address: str, hop: int = 1) -> bool:
        """Trace Cardano (ADA) transactions from an address via Blockfrost API.
        Cardano uses UTxO model similar to Bitcoin.
        Returns True if any data was saved to Neo4j.
        """
        if hop > self.max_hops:
            self._last_trace_error = f"max_hops ({self.max_hops}) reached"
            return False

        key = f"ada-{address}-{hop}"
        if key in self.processed_addresses:
            return True
        self.processed_addresses.add(key)

        try:
            self._report_progress(f"Obteniendo transacciones ADA para {address[:16]}... (hop {hop})")
            txs = self.blockchain_api.get_address_transactions(address, limit=200, chain="ada")
        except Exception as e:
            msg = f"Failed to get ADA transactions for {address}: {e}"
            self.log("error", msg)
            self._last_trace_error = msg
            return False

        if not txs:
            msg = f"No ADA transactions found for {address}"
            self.log("debug", msg)
            self._last_trace_error = msg
            return False

        self._report_progress(f"Encontradas {len(txs)} transacciones ADA para {address[:16]}...")
        self.log("info", f"Found {len(txs)} ADA transactions for {address}")

        # Analyze and save the address
        try:
            address_model = self.address_analyzer.analyze_address(address)
            self.neo4j_repo.save_address(address_model)
        except Exception as e:
            self.log("error", f"Failed to analyze/save ADA address {address}: {e}")

        total_txs = len(txs)
        for i, tx in enumerate(txs):
            if not isinstance(tx, dict):
                continue
            txid = tx.get("txid")
            if not txid:
                continue

            self._report_progress(f"Procesando transacción {i+1}/{total_txs}: {txid[:16]}...")

            # Cardano transactions have 'inputs' and 'outputs' arrays
            inputs = tx.get("inputs", [])
            outputs = tx.get("outputs", [])
            block_time = tx.get("block_time", 0)

            # Calculate sent/received amounts for this address
            sent_amount = 0
            received_amount = 0

            for inp in inputs:
                if isinstance(inp, dict) and inp.get("address") == address:
                    sent_amount += inp.get("amount", 0)

            for out in outputs:
                if isinstance(out, dict) and out.get("address") == address:
                    received_amount += out.get("amount", 0)

            # Skip dust amounts
            if hop == 1 and received_amount < self.min_amount and sent_amount < self.min_amount:
                continue

            # FAN-OUT: address sends ADA
            if sent_amount > 0:
                for out in outputs:
                    if not isinstance(out, dict):
                        continue
                    to_addr = out.get("address")
                    amount = out.get("amount", 0)
                    if not to_addr or amount <= 0:
                        continue
                    if amount < self.min_amount:
                        continue

                    tx_payload = {
                        "txid": tx.get("txid"),
                        "from_address": address,
                        "to_address": to_addr,
                        "amount": amount,
                        "block_time": block_time,
                        "is_change": False,
                        "hop": hop,
                        "chain": "ada",
                    }
                    try:
                        self.neo4j_repo.save_transaction(**tx_payload)
                    except Exception as e:
                        self.log("error", f"Failed to save ADA tx {txid}: {e}")

                    # Recurse for fanout
                    if hop < self.max_hops:
                        self._report_progress(f"Rastreando salida a {to_addr[:16]}... (hop {hop+1})")
                        time.sleep(self.rate_limit_delay)
                        self.trace(to_addr, hop + 1, direction="fanout", progress_callback=self._progress_callback)

            # FAN-IN: address receives ADA
            if received_amount > 0:
                for inp in inputs:
                    if not isinstance(inp, dict):
                        continue
                    from_addr = inp.get("address")
                    amount = inp.get("amount", 0)
                    if not from_addr or amount <= 0:
                        continue
                    if amount < self.min_amount:
                        continue

                    tx_payload = {
                        "txid": tx.get("txid"),
                        "from_address": from_addr,
                        "to_address": address,
                        "amount": amount,
                        "block_time": block_time,
                        "is_change": False,
                        "hop": hop,
                        "chain": "ada",
                    }
                    try:
                        self.neo4j_repo.save_transaction(**tx_payload)
                    except Exception as e:
                        self.log("error", f"Failed to save ADA tx {txid}: {e}")

                    # Recurse for fanin (only hop 1)
                    if hop == 1:
                        self._report_progress(f"Rastreando origen {from_addr[:16]}... (hop {hop+1})")
                        time.sleep(self.rate_limit_delay)
                        self.trace(from_addr, hop + 1, direction="fanin", progress_callback=self._progress_callback)

        return True

    def build_summary(self, address: str, limit: int = 200) -> str:
        """
        Build a textual summary of transactions for an address from Neo4j.
        
        Args:
            address: Bitcoin address to summarize
            limit: Maximum number of transactions to include

        Returns:
            Formatted summary string
        """
        self.logger.info(f"Building summary for address {address} (chain={self.chain})")
        
        try:
            # Get transaction history from Neo4j
            rows = self.neo4j_repo.get_transaction_history(address, limit=limit, chain=self.chain)
            
            if not rows:
                return f"No se encontraron transacciones para {address}."

            total_in = 0.0
            total_out = 0.0
            tx_count = len(rows)
            unique_senders = set()
            unique_receivers = set()

            resumen_lines = []
            resumen_lines.append(f"Direccion: {address}")
            resumen_lines.append(f"Total relaciones: {tx_count}")
            resumen_lines.append("")

            # Compact transaction listing (limit to avoid huge prompts)
            max_tx_lines = 40
            shown = 0
            for r in rows:
                if shown >= max_tx_lines:
                    resumen_lines.append(f"... y {tx_count - shown} transaccion(es) mas ...")
                    break
                amt = float(r.get("amount") or 0.0)
                from_addr = r.get("from_address", "")
                to_addr = r.get("to_address", "")
                txid = r.get("txid", "")
                line = f"{from_addr} -> {to_addr} | {amt:.4f} {self.unit} | {txid}"
                resumen_lines.append(line)
                shown += 1
                
                if r.get("to_address", "") == address:
                    total_in += amt
                if r.get("from_address", "") == address:
                    total_out += amt
                if r.get("from_address", ""):
                    unique_senders.add(r["from_address"])
                if r.get("to_address", ""):
                    unique_receivers.add(r["to_address"])

            resumen_lines.append("")
            resumen_lines.append(f"Total recibido (muestra): {total_in:.4f} {self.unit}")
            resumen_lines.append(f"Total enviado (muestra): {total_out:.4f} {self.unit}")
            resumen_lines.append(f"Remitentes unicos: {len(unique_senders)}")
            resumen_lines.append(f"Destinatarios unicos: {len(unique_receivers)}")
            return "\n".join(resumen_lines)
            
        except Exception as e:
            self.log("error", f"Error building summary for {address}: {e}")
            return f"Error al generar resumen para {address}: {str(e)}"

    # Legacy compatibility methods
    def get_wallet_id(self, address: str) -> Optional[str]:
        """Get wallet ID for address (legacy compatibility)."""
        if address in self.wallet_cache:
            return self.wallet_cache[address]
        
        wid = self.wallet_api.get_wallet_id(address)
        self.wallet_cache[address] = wid
        return wid

    def classify_entity(self, wallet_id: str) -> str:
        """Classify entity type from wallet ID (legacy compatibility)."""
        try:
            # Use the address analyzer's entity recognizer
            from domain.services.address_analyzer import AddressAnalyzerService
            from infrastructure.adapters.blockstream_adapter import BlockstreamAdapter
            from infrastructure.adapters.wallet_explorer_adapter import WalletExplorerAdapter
            
            temp_analyzer = AddressAnalyzerService(
                blockchain_api=BlockstreamAdapter(),
                wallet_api=WalletExplorerAdapter()
            )
            
            # This is a simplified version - in practice we'd want to pass more data
            profile = temp_analyzer.entity_recognizer.recognize_entity(wallet_id)
            return profile.entity_type.value
        except Exception as e:
            self.log("warning", f"Error classifying entity {wallet_id}: {e}")
            # Fallback to basic classification
            if not wallet_id or wallet_id == "unknown":
                return "other"

            wid = wallet_id.lower()
            mixers = ["tornado", "wasabi", "samourai"]
            exchanges = ["binance", "coinbase", "kraken", "bitfinex", "kucoin", "okx"]
            bridges = ["optimism", "arbitrum", "polygon", "bridge"]
            sanctioned = ["ofac", "sdn", "lazarus", "garantex"]

            if any(k in wid for k in sanctioned):
                return "sanctioned"
            if any(k in wid for k in mixers):
                return "mixer"
            if any(k in wid for k in exchanges):
                return "exchange"
            if any(k in wid for k in bridges):
                return "bridge"

            return "other"

    def save_to_graph(self, tx_info: dict):
        """Save transaction info to Neo4j graph (legacy compatibility)."""
        try:
            self.neo4j_repo.save_transaction(
                txid=tx_info.get("txid", ""),
                from_address=tx_info.get("from_addr", ""),
                to_address=tx_info.get("to_addr", ""),
                amount=tx_info.get("amount", 0.0),
                block_time=int(tx_info.get("time", 0)),
                is_change=tx_info.get("is_change", False),
                hop=int(tx_info.get("hop", 1))
            )
        except Exception as e:
            self.log("error", f"Failed to save to graph: {e}")

    def save_report_to_neo4j(self, address: str, report_text: str, 
                           model: str = "ollama", metadata: Optional[dict] = None) -> Optional[int]:
        """
        Save a report as a node in Neo4j.
        
        Args:
            address: Bitcoin address associated with the report
            report_text: The report content
            model: AI model used to generate the report
            metadata: Additional metadata to store

        Returns:
            Node ID if successful, None otherwise
        """
        try:
            created_at = int(time.time())
            meta_json = json.dumps(metadata or {})
            
            query = """
            MERGE (r:Report {address:$address, created_at:$created_at})
            SET r.content = $content,
                r.model = $model,
                r.metadata = $metadata
            RETURN id(r) AS report_id
            """
            
            with self.neo4j_repo.driver.session() as session:
                rec = session.run(query, 
                                address=address, 
                                created_at=created_at,
                                content=report_text, 
                                model=model, 
                                metadata=meta_json).single()
                if rec:
                    return rec["report_id"]
            return None
        except Exception as e:
            self.log("error", f"Failed to save report to Neo4j: {e}")
            return None

    def save_report_to_files(self, address: str, report_text: str, 
                            out_dir: str = "reports") -> dict:
        """
        Save report to files. Automatically detects if content is HTML and saves appropriately.
        
        Args:
            address: Bitcoin address associated with the report
            report_text: The report content
            out_dir: Output directory

        Returns:
            Dictionary with paths to saved files
        """
        import os
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        # Check if report_text looks like HTML
        is_html = False
        if report_text:
            report_text_lower = report_text.lower()
            if '<!doctype' in report_text_lower or '<html' in report_text_lower:
                is_html = True

        try:
            safe_address = safe_path_component(address, "address")
            base = f"{out_dir}/report_{safe_address}_{ts}"
            if is_html:
                # Save as HTML file only
                html_path = f"{base}.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(report_text)
                self.log("info", f"HTML report saved to: {html_path}")
                return {"html": html_path}
            else:
                # Save as text and markdown files
                txt_path = f"{base}.txt"
                md_path = f"{base}.md"

                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(report_text)

                # Para Markdown, añadimos un encabezado simple
                md_content = f"# Reporte Forense {address}\n\n" + report_text.replace("\n", "\n\n")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(md_content)

                self.log("info", f"Report saved to files: {txt_path}, {md_path}")
                return {"txt": txt_path, "md": md_path}
        except Exception as e:
            self.log("error", f"Failed to save report files: {e}")
            return {"txt": "", "md": "", "html": ""}

    def _call_ai_api(self, prompt: str, timeout: int = 120) -> Optional[str]:
        """
        Call the configured AI provider (Ollama or OpenRouter).
        
        Args:
            prompt: The prompt to send
            timeout: Request timeout in seconds

        Returns:
            Generated text or None if failed
        """
        if self.ai_provider == "openrouter":
            text = generate_with_openrouter(
                prompt=prompt,
                model=self.ai_model,
                temperature=0.1,
                max_tokens=4096,
                chain_name=self.chain_name,
            )
            if text:
                return text
            self.log("warning", "OpenRouter failed, falling back to Ollama")
        
        # Ollama fallback
        ollama_url = "http://localhost:11434/api/generate"
        payload = {
            "model": self.ai_model if self.ai_provider == "ollama" else "llama3",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "top_p": 0.9},
        }
        try:
            resp = requests.post(ollama_url, json=payload, timeout=timeout)
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            return text or None
        except requests.exceptions.ConnectionError:
            self.log("error", "Ollama not reachable at http://localhost:11434")
            return None
        except requests.exceptions.Timeout:
            self.log("error", f"Ollama timeout ({timeout}s)")
            return None
        except Exception as e:
            self.log("error", f"Ollama error: {e}")
            return None

    def generate_ai_report_with_ollama(
        self,
        resumen: str,
        model: str = "llama3",
        debug: bool = False,
        address: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Generate an AI-enhanced forensic report (supports Ollama and OpenRouter).

        Args:
            resumen: Summary text from build_summary()
            model: Override model name
            debug: Enable debug output
            address: Optional address to ground the risk evaluation in real
                     sanctions screening + typology detection instead of
                     letting the model guess from the transaction text alone
            **kwargs: Additional parameters (ignored, for compatibility)

        Returns:
            Generated report text or None if failed
        """
        risk_instruction = "1. Evaluacion de riesgo general"
        patterns_instruction = "3. Patrones de transacciones sospechosos (si los hay)"
        risk_section = ""
        if address:
            try:
                ctx = self._compute_risk_context(address)
                sanctions_result = ctx["sanctions"]
                mixing = ctx["mixing"]
                peeling = ctx["peeling"]
                san_flag = sanctions_result.get("sanctioned")
                san_text = (
                    "SANCIONADO (aparece en listas de sanciones)" if san_flag is True
                    else "Sin sanciones conocidas" if san_flag is False
                    else "No se pudo verificar"
                )
                risk_section = f"""
DATOS REALES (calculados, no los inventes ni los cambies, solo explicalos):
  Sanciones: {san_text}
  Mixing detectado: {'SI' if mixing.get('is_mixing') else 'NO'} (confianza {mixing.get('confidence', 0):.2f})
  Peeling chain detectado: {'SI' if peeling.get('is_peeling_chain') else 'NO'} (longitud maxima {peeling.get('chain_length', 0)})
"""
                risk_instruction = "1. Evaluacion de riesgo general - basala EXCLUSIVAMENTE en los datos reales indicados abajo (sanciones, mixing, peeling), no la inventes"
                patterns_instruction = "3. Patrones de transacciones sospechosos - reporta unicamente los patrones detectados indicados abajo, no inventes otros"
            except Exception as e:
                self.log("warning", f"Could not compute risk context for {address}: {e}")

        prompt = f"""Eres un experto en analisis forense de {self.chain_name} y criptomonedas.
Analiza el siguiente resumen de transacciones y direcciones de {self.chain_name} y genera un informe forense profesional en espanol que incluya:

{risk_instruction}
2. Entidades potencialmente involucradas (exchanges, mixers, servicios sancionados, etc.)
{patterns_instruction}
4. Recomendaciones para investigacion adicional
5. Conclusiones ejecutivas
{risk_section}
Resumen de transacciones:
{resumen}

Informe forense:"""

        # Override model if provided
        old_model = self.ai_model
        if model != "llama3":
            self.ai_model = model
        try:
            text = self._call_ai_api(prompt, timeout=120)
            if text and debug:
                self.log("debug", f"AI response: {text[:200]}...")
            return text
        finally:
            if model != "llama3":
                self.ai_model = old_model

    def generate_transaction_graph_html(self, address: str, limit: int = 100) -> str:
        """
        Generate an interactive transaction graph as HTML using PyVis.
        
        Args:
            address: Bitcoin address to center the graph on
            limit: Maximum number of transactions to include
            
        Returns:
            HTML string of the interactive graph
        """
        try:
            # Try to import PyVis
            from pyvis.network import Network
            import itertools
        except ImportError:
            return "<p>Error: PyVis no está instalado. Instale PyVis para generar gráficos interactivos.</p>"
        
        try:
            # Create a directed network
            net = Network(
                height="750px",
                width="100%",
                bgcolor="#222222",
                font_color="white",
                directed=True,
                notebook=False
            )
            
            # Set physics layout for better visualization
            net.barnes_hut()
            net.set_options("""
            var options = {
              "physics": {
                "barnesHut": {
                  "gravitationalConstant": -8000,
                  "centralGravity": 0.3,
                  "springLength": 250,
                  "springConstant": 0.04,
                  "damping": 0.09
                },
                "minVelocity": 0.75
              }
            }
            """)
            
            # Get transaction history from Neo4j
            rows = self.neo4j_repo.get_transaction_history(address, limit=limit, chain=self.chain)
            
            if not rows:
                return "<p>No se encontraron transacciones para generar el grafo.</p>"
            
            # Keep track of nodes we've already added to avoid duplicates
            added_nodes = set()
            
            # Add the central address node
            net.add_node(
                address,
                label=address[:10] + "...",
                title=address,
                color="#ff0000",
                size=25
            )
            added_nodes.add(address)
            
            # Process each transaction
            for r in rows:
                from_addr = r.get("from_address", "")
                to_addr = r.get("to_address", "")
                amount = float(r.get("amount") or 0.0)
                txid = r.get("txid", "")
                
                # Skip if no addresses
                if not from_addr and not to_addr:
                    continue
                
                # Add from address node if not already added
                if from_addr and from_addr not in added_nodes:
                    net.add_node(
                        from_addr,
                        label=from_addr[:10] + "...",
                        title=from_addr,
                        color="#00ff00",
                        size=15
                    )
                    added_nodes.add(from_addr)
                
                # Add to address node if not already added
                if to_addr and to_addr not in added_nodes:
                    net.add_node(
                        to_addr,
                        label=to_addr[:10] + "...",
                        title=to_addr,
                        color="#0000ff",
                        size=15
                    )
                    added_nodes.add(to_addr)
                
                # Add edge if we have both addresses
                if from_addr and to_addr:
                    net.add_edge(
                        from_addr,
                        to_addr,
                        value=max(1, amount * 1000000),  # Scale for visibility
                        title=f"Amount: {amount:.8f} {self.unit}<br>TXID: {txid}",
                        label=f"{amount:.4f}"
                    )
            
            # Generate HTML
            html = net.generate_html()
            
            # Add a title
            html = html.replace(
                "<body>",
                f"<body><h2>Grafo de Transacciones para {address}</h2>"
            )
            
            return html
            
        except Exception as e:
            self.log("error", f"Error generating transaction graph: {e}")
            return f"<p>Error al generar el grafo: {str(e)}</p>"

    # ---------------------------------------------------------
    # SANCTIONS API
    # ---------------------------------------------------------

    SANCTIONS_API_URL = "https://wass.wemsys.es/api/sanctions/crypto"

    def check_sanctions(self, address: str) -> Dict[str, Any]:
        """
        Check if an address appears in sanctions lists and get entity identifications.

        Uses the WASS API, which searches the address string directly against
        sanctions/entity lists without needing a chain/network parameter —
        works across all chains HOPS supports (BTC, ETH, BCH, TRX, ADA).
        Returns sanctions matches and entity identifications.

        Args:
            address: Blockchain address to check

        Returns:
            Dict with sanctions info, identifications, and classification
        """
        internal_key = self.config.api.sanctions_internal_key
        headers = {
            "X-Internal-Key": internal_key,
        }
        try:
            resp = requests.get(
                self.SANCTIONS_API_URL,
                params={"address": address},
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            sanctioned = data.get("match", False)
            matches = data.get("matches", [])
            identifications = data.get("identifications", [])
            total_matches = data.get("totalMatches", 0)

            classification = None
            entity_name = None
            if identifications:
                classification = identifications[0].get("classification")
                entity_name = identifications[0].get("name")

            self.log("info",
                     f"Sanctions check for {address}: sanctioned={sanctioned}, "
                     f"matches={len(matches)}, identifications={len(identifications)}")
            return {
                "sanctioned": sanctioned,
                "matches": matches,
                "identifications": identifications,
                "total_matches": total_matches,
                "address": address,
                "classification": classification,
                "entity_name": entity_name,
            }
        except requests.exceptions.ConnectionError:
            self.log("warning", f"Sanctions API not reachable for {address}")
            return {"sanctioned": None, "matches": [], "identifications": [],
                    "total_matches": 0, "address": address, "classification": None,
                    "entity_name": None, "error": "API not reachable"}
        except requests.exceptions.Timeout:
            self.log("warning", f"Sanctions API timeout for {address}")
            return {"sanctioned": None, "matches": [], "identifications": [],
                    "total_matches": 0, "address": address, "classification": None,
                    "entity_name": None, "error": "Timeout"}
        except Exception as e:
            self.log("error", f"Sanctions check error for {address}: {e}")
            return {"sanctioned": None, "matches": [], "identifications": [],
                    "total_matches": 0, "address": address, "classification": None,
                    "entity_name": None, "error": str(e)}

    # ---------------------------------------------------------
    # ENHANCED REPORT METHODS (V2)
    # ---------------------------------------------------------

    def collect_edge_data(self, address: str, depth: int = 2, limit: int = 5000,
                          start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """
        Collect edge data from Neo4j (same as dashboardpro.fetch_subgraph).
        Returns list of transaction edge dicts for report generation.

        Args:
            address: Root address
            depth: Traversal depth
            limit: Maximum edges to return
            start_date: Start date filter (ISO format YYYY-MM-DD)
            end_date: End date filter (ISO format YYYY-MM-DD)

        Returns:
            List of edge dicts with from_addr, to_addr, amount, txid, etc.
        """
        try:
            return self.neo4j_repo.get_subgraph_edges(
                address, depth=depth, limit=limit, chain=self.chain,
                start_date=start_date, end_date=end_date
            )
        except AttributeError:
            # Fallback: inline the query if the repo doesn't have the method
            pass

        # Inline fallback for get_subgraph_edges with date filtering
        depth_literal = f"*1..{depth}"

        # Build date filter clause
        date_filter = ""
        params = {"addr": address, "limit": limit, "chain": self.chain}
        if start_date:
            date_filter += " AND rel.block_time >= $start_ts"
            params["start_ts"] = int(datetime.fromisoformat(start_date).timestamp())
        if end_date:
            date_filter += " AND rel.block_time <= $end_ts"
            params["end_ts"] = int(datetime.fromisoformat(end_date + " 23:59:59").timestamp())

        query = f"""
        MATCH (root:Address {{address:$addr}})
        MATCH p=(root)-[:SENT{depth_literal}]-(b:Address)
        WHERE ALL(rel IN relationships(p) WHERE rel.chain IS NULL OR rel.chain = $chain)
        UNWIND relationships(p) AS rel
        WITH DISTINCT rel
        MATCH (a:Address)-[rel]->(b:Address)
        WHERE 1=1 {date_filter}
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
            b.labels AS to_labels
        LIMIT $limit
        """
        rows = []
        try:
            for rec in self.neo4j_repo.run_query(query, **params):
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
            self.log("error", f"Error collecting edge data: {e}")
        return rows

    def generate_ai_report_with_ollama_v2(
        self,
        resumen: str,
        structured_data: Optional[Dict[str, Any]] = None,
        model: str = "llama3",
        risk_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generate an enhanced AI forensic report (supports Ollama and OpenRouter).
        Includes structured data (timeline, heatmap, entities, sanctions) in the prompt.

        Args:
            resumen: Text summary from build_summary()
            structured_data: Dict with timeline, heatmap, entity, sanctions and transaction stats
            model: Override model name

        Returns:
            Generated report text or None
        """
        # Truncate resumen to avoid huge prompts
        resumen_lines = resumen.split("\n")
        if len(resumen_lines) > 60:
            resumen = (
                "\n".join(resumen_lines[:30])
                + "\n... [TRANSACCIONES OMITIDAS ...]\n"
                + "\n".join(resumen_lines[-20:])
            )

        # Build concise structured data section
        structured_section = ""
        if structured_data:
            parts = []

            sanctions = structured_data.get("sanctions", {})
            if sanctions:
                san_flag = sanctions.get("sanctioned")
                if san_flag is True:
                    parts.append("*** SANCIONADO *** La direccion aparece en listas de sanciones.")
                elif san_flag is False:
                    parts.append("- Sin sanciones: no aparece en listas de sanciones conocidas.")
                else:
                    parts.append("- Sanciones: no se pudo verificar (API no disponible).")
                matches = sanctions.get("matches", [])
                if matches:
                    for m in matches[:5]:
                        parts.append(f"  - Coincidencia: {m}")

            tl = structured_data.get("timeline", [])
            if tl:
                dates = [t.get("datetime", "")[:10] for t in tl if t.get("datetime")]
                if len(dates) > 1:
                    parts.append(f"- Actividad: {dates[0]} a {dates[-1]} ({len(dates)} eventos)")
            hd = structured_data.get("heatmap", {})
            if hd:
                max_hour = max(hd, key=lambda h: hd[h].get("total_amount", 0))
                parts.append(f"- Pico horario: {max_hour}:00 UTC ({float(hd[max_hour].get('total_amount', 0)):.4f} {self.unit})")
                min_hour = min(hd, key=lambda h: hd[h].get("total_amount", 0))
                if min_hour != max_hour:
                    parts.append(f"- Menor actividad: {min_hour}:00 UTC ({float(hd[min_hour].get('total_amount', 0)):.4f} {self.unit})")
            ed = structured_data.get("entity_distribution", {})
            if ed:
                top = sorted(ed.items(), key=lambda x: -x[1])[:5]
                ent_str = ", ".join(f"{e}: {c}" for e, c in top)
                parts.append(f"- Entidades: {ent_str}")
            parts.append(f"- Recibido: {float(structured_data.get('total_in_btc', 0)):.4f} {self.unit}")
            parts.append(f"- Enviado: {float(structured_data.get('total_out_btc', 0)):.4f} {self.unit}")
            parts.append(f"- Direcciones unicas: {structured_data.get('unique_addresses', 0)}")
            if parts:
                structured_section = "Datos del analisis:\n" + "\n".join(parts)

        risk_section = ""
        risk_instruction = "1. Evaluacion de riesgo (bajo/medio/alto) - Incluye el resultado de la verificacion de sanciones"
        patterns_instruction = "4. Patrones sospechosos detectados"
        if risk_context:
            risk = risk_context.get("risk", {})
            mixing = risk_context.get("mixing", {})
            peeling = risk_context.get("peeling", {})
            exposure_pct = risk_context.get("exposure_pct", {})
            exposure_lines = "\n".join(
                f"  {ent}: {pct}%" for ent, pct in sorted(exposure_pct.items(), key=lambda x: -x[1])
            ) or "  Sin datos de contraparte."
            risk_section = f"""
PUNTUACION DE RIESGO (calculada deterministicamente a partir de datos on-chain, NO la inventes ni la cambies, solo explicala):
  PUNTUACION TOTAL: {risk.get('total', 'N/A')}/100 — NIVEL: {risk.get('level', 'N/A')}
  Sub-puntuacion exposicion a contrapartes: {risk.get('exposure_score', 'N/A')}/100
  Sub-puntuacion cribado de sanciones: {risk.get('sanctions_score', 'N/A')}/100
  Sub-puntuacion tipologias detectadas: {risk.get('typology_score', 'N/A')}/100

EXPOSICION A CONTRAPARTES POR VOLUMEN:
{exposure_lines}

PATRONES DETECTADOS (analisis automatizado, no inventes otros):
  Mixing: {'SI' if mixing.get('is_mixing') else 'NO'} (confianza {mixing.get('confidence', 0):.2f}) — indicadores: {', '.join(mixing.get('indicators', [])) or 'ninguno'}
  Peeling chain: {'SI' if peeling.get('is_peeling_chain') else 'NO'} (longitud maxima {peeling.get('chain_length', 0)})
"""
            risk_instruction = "1. Evaluacion de riesgo - USA la puntuacion y el nivel indicados abajo tal cual, no inventes ni recalcules otro. Incluye el resultado de la verificacion de sanciones"
            patterns_instruction = "4. Patrones sospechosos - reporta EXACTAMENTE los patrones detectados indicados abajo (mixing/peeling). Si ambos son NO, indica que no se detectaron patrones automatizados de ocultacion, no inventes otros"

        prompt = f"""Eres un experto en analisis forense de {self.chain_name}. Genera un informe profesional en espanol basado en estos datos.

Estructura del informe:
{risk_instruction}
2. Entidades involucradas (exchanges, mixers, etc.)
3. Analisis temporal (periodos y horarios de actividad)
{patterns_instruction}
5. Recomendaciones
6. Conclusiones - Menciona explicitamente si la direccion aparece o no en listas de sanciones
{risk_section}
{structured_section}

Transacciones:
{resumen}

Informe forense:"""

        old_model = self.ai_model
        if model != "llama3":
            self.ai_model = model
        try:
            return self._call_ai_api(prompt, timeout=300)
        finally:
            if model != "llama3":
                self.ai_model = old_model

    def generate_enhanced_report(
        self,
        address: str,
        filters: Optional[Dict] = None,
        depth: int = 2,
        model: str = "llama3",
    ) -> Dict[str, Any]:
        """
        Generate a complete enhanced report with PDF, HTML, charts, and data files.

        Args:
            address: Bitcoin address to analyze
            filters: Dashboard filters (min_amount, etc.)
            depth: Neo4j traversal depth
            model: Ollama model name

        Returns:
            Dict with paths to all generated files
        """
        from forensic_report_v2 import EnhancedForensicReporter

        self.log("info", f"Generating enhanced report for {address}")

        # 1. Collect edge data from Neo4j
        filters = filters or {}
        edges = self.collect_edge_data(address, depth=depth, start_date=filters.get("start_date"), end_date=filters.get("end_date"))
        if not edges:
            self.log("warning", f"No edge data found for {address}")
            return {"error": "No hay datos de transacciones en Neo4j para esta direccion."}

        # 2. Apply filters
        if filters:
            min_amount = filters.get("min_amount", 0.00001)
            edges = [e for e in edges if float(e.get("amount", 0)) >= min_amount]
            if filters.get("hide_change"):
                edges = [e for e in edges if not e.get("is_change", False)]
            if filters.get("only_hop1"):
                edges = [e for e in edges if e.get("hop") == 1]
            if filters.get("only_fanin"):
                edges = [e for e in edges if e.get("to_addr") == address]
            if filters.get("only_fanout"):
                # An edge only qualifies as fan-out if it directly originates
                # from the analyzed address (mirrors dashboardpro.py's filter
                # and the pericial/compliance report generators below).
                edges = [e for e in edges if e.get("from_addr") == address]

        if not edges:
            self.log("warning", "No edges after filtering")
            return {"error": "No quedan datos tras aplicar los filtros."}

        # 3. Build text summary for Ollama
        resumen = self.build_summary(address)

        # 4. Build structured data for enriched prompt
        df = pd.DataFrame(edges) if edges else pd.DataFrame()

        ed = {}
        if not df.empty:
            all_entities = []
            for col in ["from_entity", "to_entity"]:
                if col in df.columns:
                    all_entities.extend(df[col].dropna().tolist())
            for ent in set(all_entities):
                ed[ent] = all_entities.count(ent)

        timeline_data = []
        if not df.empty and "ts" in df.columns:
            df_t = df[df["ts"].notna()].copy()
            df_t["datetime"] = pd.to_datetime(df_t["ts"], unit="s")
            df_t = df_t.sort_values("datetime")
            for _, r in df_t.iterrows():
                timeline_data.append({
                    "datetime": r["datetime"].isoformat(),
                    "amount": float(r.get("amount", 0)),
                })

        heatmap_data = {}
        if not df.empty and "ts" in df.columns:
            df_h = df[df["ts"].notna()].copy()
            df_h["hour"] = pd.to_datetime(df_h["ts"], unit="s").dt.hour
            hourly = df_h.groupby("hour").agg(
                total_amount=("amount", "sum"), tx_count=("txid", "count")
            ).to_dict("index")
            heatmap_data = {str(h): v for h, v in hourly.items()}

        total_in = total_out = 0.0
        if not df.empty and "amount" in df.columns:
            df_a = df[df["amount"].notna()]
            if "to_addr" in df_a.columns:
                total_in = df_a[df_a["to_addr"] == address]["amount"].sum()
            if "from_addr" in df_a.columns:
                total_out = df_a[df_a["from_addr"] == address]["amount"].sum()

        # 5. Sanctions + typology detection + exposure + deterministic risk
        #    score (shared with the other report generators).
        risk_context = self._compute_risk_context(address, edges=edges)
        sanctions_result = risk_context["sanctions"]

        structured_data = {
            "timeline": timeline_data,
            "heatmap": heatmap_data,
            "entity_distribution": ed,
            "total_in_btc": float(total_in),
            "total_out_btc": float(total_out),
            "unique_addresses": int(df["from_addr"].nunique() + df["to_addr"].nunique()) if not df.empty else 0,
            "sanctions": sanctions_result,
        }

        # 6. Generate AI report with enriched data + real risk indicators
        ollama_narrative = self.generate_ai_report_with_ollama_v2(
            resumen, structured_data=structured_data, model=model, risk_context=risk_context
        )
        if not ollama_narrative:
            ollama_narrative = "No se pudo generar el analisis IA. Verifique que Ollama este ejecutandose."

        # 6. Generate transaction graph HTML
        graph_html = self.generate_transaction_graph_html(address, limit=100)

        # 7. Generate complete report folder via EnhancedForensicReporter
        reporter = EnhancedForensicReporter(output_dir="reports", chain=self.chain)
        result = reporter.generate_report_folder(
            address=address,
            edges=edges,
            ollama_narrative=ollama_narrative,
            transaction_graph_html=graph_html,
            filters=filters,
            sanctions=sanctions_result,
        )
        result["risk_score"] = risk_context["risk"]

        self.log("info", f"Enhanced report generated: {result.get('folder')}")
        return result

    def _load_skill_file(self, filename: str) -> str:
        """Load a skill reference markdown file from references/crypto-forensics/."""
        import os as _os
        base = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "references", "crypto-forensics")
        path = _os.path.join(base, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self.log("warning", f"Could not load skill file {filename}: {e}")
            return f"[{filename} no disponible]"

    def generate_forensic_pericial_report(
        self,
        address: str,
        filters: Optional[Dict] = None,
        depth: int = 2,
        model: str = "llama3",
        case_data: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a forensic expert report for Spanish/UE courts.

        Uses the crypto-forensics skill (plantilla-informe.md, exchanges-kyc-ue.md,
        glosario-juridico.md) to produce a legally structured expert witness report
        following the 10-section template required for Spanish judicial proceedings.

        Args:
            address: Blockchain address to analyze
            filters: Dashboard filters (min_amount, etc.)
            depth: Neo4j traversal depth
            model: AI model name
            case_data: Dict with case info (victim_name, case_number, court, etc.)

        Returns:
            Dict with paths to all generated files
        """
        from forensic_report_v2 import EnhancedForensicReporter

        self.log("info", f"Generating forensic pericial report for {address}")

        # 1. Collect edge data from Neo4j
        filters = filters or {}
        edges = self.collect_edge_data(address, depth=depth, start_date=filters.get("start_date"), end_date=filters.get("end_date"))
        if not edges:
            self.log("warning", f"No edge data found for {address}")
            return {"error": "No hay datos de transacciones en Neo4j para esta direccion."}

        # 2. Apply filters
        if filters:
            min_amount = filters.get("min_amount", 0.00001)
            edges = [e for e in edges if float(e.get("amount", 0)) >= min_amount]
            if filters.get("hide_change"):
                edges = [e for e in edges if not e.get("is_change", False)]
            if filters.get("only_hop1"):
                edges = [e for e in edges if e.get("hop") == 1]
            if filters.get("only_fanin"):
                edges = [e for e in edges if e.get("to_addr") == address]
            if filters.get("only_fanout"):
                edges = [e for e in edges if e.get("from_addr") == address]

        if not edges:
            return {"error": "No quedan datos tras aplicar los filtros."}

        # 3. Build text summary
        resumen = self.build_summary(address)

        # 4. Build structured data
        df = pd.DataFrame(edges) if edges else pd.DataFrame()
        ed = {}
        if not df.empty:
            all_entities = []
            for col in ["from_entity", "to_entity"]:
                if col in df.columns:
                    all_entities.extend(df[col].dropna().tolist())
            for ent in set(all_entities):
                ed[ent] = all_entities.count(ent)

        total_in = total_out = 0.0
        if not df.empty and "amount" in df.columns:
            df_a = df[df["amount"].notna()]
            if "to_addr" in df_a.columns:
                total_in = df_a[df_a["to_addr"] == address]["amount"].sum()
            if "from_addr" in df_a.columns:
                total_out = df_a[df_a["from_addr"] == address]["amount"].sum()
        unique_addrs = int(df["from_addr"].nunique() + df["to_addr"].nunique()) if not df.empty else 0

        # Sanctions + typology detection (mixing/peeling chain), computed
        # deterministically and shared with the other report generators —
        # feeds Section 6 "Indicios de ocultacion" with real detections
        # instead of leaving the model to infer patterns from the raw hop
        # table alone.
        risk_context = self._compute_risk_context(address, edges=edges)
        sanctions_result = risk_context["sanctions"]
        mixing_analysis = risk_context["mixing"]
        peeling_analysis = risk_context["peeling"]

        # 5. Load skill references and build concise context
        plantilla = self._load_skill_file("plantilla-informe.md")
        exchanges_ref = self._load_skill_file("exchanges-kyc-ue.md")
        glosario = self._load_skill_file("glosario-juridico.md")

        # Extract just section headers from plantilla (reduce prompt size)
        secciones = []
        for line in plantilla.split("\n"):
            if line.strip().startswith("## SECCI") or line.strip().startswith("###"):
                secciones.append(line.strip().lstrip("#").strip())
        estructura = "\n".join(f"{i+1}. {s}" for i, s in enumerate(secciones))

        # Trim exchanges to just exchange names + countries
        exchanges_resumen = []
        for line in exchanges_ref.split("\n"):
            line = line.strip()
            if line.startswith("## "):
                exchanges_resumen.append(line.strip("# "))
            if "**País de registro:**" in line or "**Regulador:**" in line or "**Nombre legal:**" in line:
                exchanges_resumen.append("  " + line.strip("* "))
        exchanges_short = "\n".join(exchanges_resumen)

        # 6. Build structured data section for prompt
        parts = []
        san = sanctions_result or {}
        if san.get("sanctioned") is True:
            parts.append("SANCIONES: Aparece en listas de sanciones.")
        elif san.get("sanctioned") is False:
            parts.append("SANCIONES: Sin sanciones conocidas.")
        else:
            parts.append("SANCIONES: No se pudo verificar.")
        matches = san.get("matches", [])
        if matches:
            for m in matches[:3]:
                parts.append(f"  Coincidencia: {m}")

        if ed:
            top = sorted(ed.items(), key=lambda x: -x[1])[:5]
            ent_str = ", ".join(f"{e}: {c}" for e, c in top)
            parts.append(f"Entidades: {ent_str}")
        parts.append(f"Total recibido: {total_in:.4f} {self.unit}")
        parts.append(f"Total enviado: {total_out:.4f} {self.unit}")
        parts.append(f"Direcciones unicas: {unique_addrs}")
        parts.append(f"Red: {self.chain_name} ({self.unit})")

        # Build hops table as CSV-like data
        hops_table = []
        for i, e in enumerate(edges[:60]):
            hop = e.get("hop", i + 1)
            txid = (e.get("txid") or "")[:20]
            ts = e.get("ts", 0)
            fecha = datetime.utcfromtimestamp(int(ts)).strftime("%d/%m/%Y") if ts else "N/A"
            from_a = (e.get("from_addr") or "")[:25]
            to_a = (e.get("to_addr") or "")[:25]
            amt = float(e.get("amount") or 0)
            from_labels_list = e.get("from_labels") or []
            to_labels_list = e.get("to_labels") or []
            from_label = from_labels_list[0] if from_labels_list else ""
            to_label = to_labels_list[0] if to_labels_list else ""
            hops_table.append(f"{hop},{txid},{fecha},{from_a},{to_a},{amt:.4f},{from_label},{to_label}")

        structured_section = "\n".join(parts)
        hops_csv = "\n".join(hops_table)

        # 7. Build case data section
        case_lines = [f"Direccion analizada: {address}"]
        if case_data:
            for k, v in case_data.items():
                if v:
                    case_lines.append(f"{k}: {v}")
        case_section = "\n".join(case_lines)

        # 8. Build prompt — short and directive
        prompt = f"""Eres un perito forense de blockchain. Genera un informe pericial para tribunales espanoles/UE.

DATOS DEL CASO:
{case_section}

DATOS ON-CHAIN:
{structured_section}

TABLA DE HOPS (HOP,HASH,FECHA,ORIGEN,DESTINO,CANTIDAD,ETIQUETA):
{hops_csv}

TRANSACCIONES (resumen):
{resumen}

SANCIONES:
{json.dumps(sanctions_result, indent=2, ensure_ascii=False)}

PATRONES DE OCULTACION DETECTADOS (analisis automatizado — usa EXACTAMENTE estos resultados en la Seccion 6, no inventes otros):
  Mixing / servicio de mezcla: {'DETECTADO' if mixing_analysis.get('is_mixing') else 'NO detectado'} (confianza {mixing_analysis.get('confidence', 0):.2f}) — indicadores: {', '.join(mixing_analysis.get('indicators', [])) or 'ninguno'}
  Peeling chain (fragmentacion progresiva): {'DETECTADO' if peeling_analysis.get('is_peeling_chain') else 'NO detectado'} (longitud maxima de cadena: {peeling_analysis.get('chain_length', 0)})

ESTRUCTURA QUE DEBES SEGUIR:
{estructura}

REFERENCIAS DE EXCHANGES:
{exchanges_short}

INSTRUCCIONES:
1. Genera SOLO el informe completo, sin notas ni explicaciones.
2. Sigue EXACTAMENTE la estructura numerada de 10 secciones.
3. Rellena los datos reales del analisis. Si falta un dato, pon "No disponible" NO inventes.
4. Usa lenguaje formal y tecnico-juridico.
5. En la Seccion 6 (Indicios de ocultacion), reporta UNICAMENTE los patrones marcados como "DETECTADO" arriba. Si ninguno esta detectado, indica expresamente que no se han observado indicios automatizados de ocultacion, no inventes ninguno.
6. NO incluyas ningun texto fuera del informe (no pienses en voz alta)."""

        # 9. Call AI
        old_model = self.ai_model
        if model != "llama3":
            self.ai_model = model
        try:
            pericial_narrative = self._call_ai_api(prompt, timeout=300)
        finally:
            if model != "llama3":
                self.ai_model = old_model

        if not pericial_narrative:
            pericial_narrative = "No se pudo generar el informe pericial. Verifique que el proveedor AI este disponible."

        # 10. Generate transaction graph HTML
        graph_html = self.generate_transaction_graph_html(address, limit=100)

        # 11. Generate report folder
        reporter = EnhancedForensicReporter(output_dir="reports", chain=self.chain)
        result = reporter.generate_report_folder(
            address=address,
            edges=edges,
            ollama_narrative=pericial_narrative,
            transaction_graph_html=graph_html,
            filters=filters,
            sanctions=sanctions_result,
        )

        self.log("info", f"Forensic pericial report generated: {result.get('folder')}")
        return result

    def _compute_counterparty_exposure(self, edges: List[Dict[str, Any]], address: str) -> Dict[str, float]:
        """Volume-weighted % of funds moved through each counterparty entity
        type, across the given edges. Shared by all report generators so
        exposure figures are computed the same way everywhere instead of
        being re-derived (or guessed by the AI) per report type.

        Each edge counts its amount exactly ONCE, against whichever side is
        the counterparty relative to `address` (the other party in a direct
        hop-1 transaction); for hop 2+ edges, where neither endpoint is the
        analyzed address, the destination side is used as the representative
        entity for that flow. Summing both from_entity and to_entity per
        edge would double the volume of any edge where both endpoints have
        a known entity type, skewing the percentages.
        """
        if not edges:
            return {}
        vol_by_entity: Dict[str, float] = {}
        for e in edges:
            try:
                amt = float(e.get("amount") or 0)
            except (TypeError, ValueError):
                continue
            if amt <= 0:
                continue
            if e.get("from_addr") == address:
                ent = e.get("to_entity") or "unknown"
            elif e.get("to_addr") == address:
                ent = e.get("from_entity") or "unknown"
            else:
                ent = e.get("to_entity") or e.get("from_entity") or "unknown"
            vol_by_entity[ent] = vol_by_entity.get(ent, 0.0) + amt

        grand_total = sum(vol_by_entity.values()) or 1.0
        return {ent: round((amt / grand_total) * 100, 2) for ent, amt in vol_by_entity.items()}

    def _compute_risk_context(self, address: str, edges: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Compute real, deterministic risk indicators for `address`:
        sanctions screening, detected typologies (mixing/peeling chain),
        counterparty exposure (if edges are supplied) and an overall score.

        Every report generator (simple, enhanced, pericial, compliance)
        should feed this into its AI prompt instead of asking the model to
        invent a risk assessment from raw transaction text — the model's
        job is to explain these numbers, not to compute them.
        """
        sanctions_result = self.check_sanctions(address)
        raw_transactions = self._get_raw_transaction_history(address)
        mixing_analysis = (
            self.cluster_analyzer.detect_mixing_patterns(raw_transactions)
            if raw_transactions else {"is_mixing": False, "confidence": 0.0, "indicators": []}
        )
        peeling_analysis = (
            self.cluster_analyzer.detect_peeling_chain(raw_transactions)
            if raw_transactions else {"is_peeling_chain": False, "confidence": 0.0, "chain_length": 0}
        )
        exposure_pct = self._compute_counterparty_exposure(edges, address) if edges else {}
        risk = self._compute_risk_score(exposure_pct, sanctions_result, mixing_analysis, peeling_analysis)
        return {
            "sanctions": sanctions_result,
            "mixing": mixing_analysis,
            "peeling": peeling_analysis,
            "exposure_pct": exposure_pct,
            "risk": risk,
        }

    def _compute_risk_score(
        self,
        exposure_pct: Dict[str, float],
        sanctions_result: Dict[str, Any],
        mixing_analysis: Dict[str, Any],
        peeling_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Deterministically compute a 0-100 risk score from on-chain data,
        so the figure is reproducible and not left to the LLM to invent.
        Weighting is intentionally simple/transparent rather than a
        black-box model, so the derivation can be audited."""
        weights = self.cluster_analyzer.entity_risk_weights

        # 1. Counterparty exposure: volume-weighted average of each entity
        #    type's risk weight, scaled to 0-100.
        exposure_score = 0.0
        for entity, pct in exposure_pct.items():
            exposure_score += (pct / 100.0) * weights.get(entity, 0.5) * 100

        # 2. Sanctions screening.
        if sanctions_result.get("sanctioned") is True:
            sanctions_score = 100.0
        elif sanctions_result.get("sanctioned") is False:
            sanctions_score = 0.0
        else:
            sanctions_score = 40.0  # unverifiable is treated as elevated, not clean

        # 3. Detected typologies (mixing / peeling).
        typology_score = 0.0
        typology_score += mixing_analysis.get("confidence", 0.0) * 100 * 0.6
        typology_score += peeling_analysis.get("confidence", 0.0) * 100 * 0.4
        typology_score = min(100.0, typology_score)

        # Weighted total. Sanctions dominate: a confirmed hit alone should
        # push the address into "critico" regardless of the other factors.
        total = (exposure_score * 0.35) + (sanctions_score * 0.40) + (typology_score * 0.25)
        total = round(min(100.0, max(0.0, total)), 1)

        if total >= 75:
            level = "CRITICO"
        elif total >= 50:
            level = "ALTO"
        elif total >= 25:
            level = "MEDIO"
        else:
            level = "BAJO"

        return {
            "total": total,
            "level": level,
            "exposure_score": round(exposure_score, 1),
            "sanctions_score": round(sanctions_score, 1),
            "typology_score": round(typology_score, 1),
        }

    def generate_forensic_compliance_report(
        self,
        address: str,
        filters: Optional[Dict] = None,
        depth: int = 2,
        model: str = "llama3",
        case_data: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate an AML/compliance audit report — NOT a judicial expert
        report. Intended for a regulated entity's compliance function
        (VASP/exchange onboarding, ongoing monitoring, EDD, SAR/STR
        decision support).

        The risk score and exposure breakdown are computed deterministically
        from on-chain data (see _compute_risk_context / _compute_risk_score);
        the AI narrative explains and contextualizes those figures rather
        than inventing its own risk assessment.

        Args:
            address: Blockchain address to analyze
            filters: Dashboard filters (min_amount, etc.)
            depth: Neo4j traversal depth
            model: AI model name
            case_data: Dict with compliance case info (requesting entity,
                       reason for review, analyst, internal reference, etc.)

        Returns:
            Dict with paths to all generated files
        """
        from forensic_report_v2 import EnhancedForensicReporter

        self.log("info", f"Generating compliance report for {address}")

        # 1. Collect edge data from Neo4j
        filters = filters or {}
        edges = self.collect_edge_data(address, depth=depth, start_date=filters.get("start_date"), end_date=filters.get("end_date"))
        if not edges:
            self.log("warning", f"No edge data found for {address}")
            return {"error": "No hay datos de transacciones en Neo4j para esta direccion."}

        # 2. Apply filters
        if filters:
            min_amount = filters.get("min_amount", 0.00001)
            edges = [e for e in edges if float(e.get("amount", 0)) >= min_amount]
            if filters.get("hide_change"):
                edges = [e for e in edges if not e.get("is_change", False)]
            if filters.get("only_hop1"):
                edges = [e for e in edges if e.get("hop") == 1]
            if filters.get("only_fanin"):
                edges = [e for e in edges if e.get("to_addr") == address]
            if filters.get("only_fanout"):
                edges = [e for e in edges if e.get("from_addr") == address]

        if not edges:
            return {"error": "No quedan datos tras aplicar los filtros."}

        # 3. Build text summary
        resumen = self.build_summary(address)

        # 4. Totals
        df = pd.DataFrame(edges) if edges else pd.DataFrame()
        total_in = total_out = 0.0
        if not df.empty and "amount" in df.columns:
            df_a = df.copy()
            df_a["amount"] = pd.to_numeric(df_a["amount"], errors="coerce")
            df_a = df_a[df_a["amount"].notna()]
            if "to_addr" in df_a.columns:
                total_in = df_a[df_a["to_addr"] == address]["amount"].sum()
            if "from_addr" in df_a.columns:
                total_out = df_a[df_a["from_addr"] == address]["amount"].sum()
        unique_addrs = int(df["from_addr"].nunique() + df["to_addr"].nunique()) if not df.empty else 0

        # 5. Sanctions + typology detection + exposure + risk score, all
        #    computed deterministically and shared with the other report
        #    generators (see _compute_risk_context).
        ctx = self._compute_risk_context(address, edges=edges)
        sanctions_result = ctx["sanctions"]
        mixing_analysis = ctx["mixing"]
        peeling_analysis = ctx["peeling"]
        exposure_pct = ctx["exposure_pct"]
        risk = ctx["risk"]

        # 6. Load compliance template
        plantilla = self._load_skill_file("plantilla-compliance.md")
        secciones = []
        for line in plantilla.split("\n"):
            if line.strip().startswith("## SECCI") :
                secciones.append(line.strip().lstrip("#").strip())
        estructura = "\n".join(f"{i+1}. {s}" for i, s in enumerate(secciones))

        # 7. Build data sections for the prompt
        exposure_lines = "\n".join(
            f"  {ent}: {pct}%" for ent, pct in sorted(exposure_pct.items(), key=lambda x: -x[1])
        ) or "  Sin datos de contraparte."

        hops_table = []
        for i, e in enumerate(edges[:60]):
            hop = e.get("hop", i + 1)
            txid = (e.get("txid") or "")[:20]
            ts = e.get("ts", 0)
            fecha = datetime.utcfromtimestamp(int(ts)).strftime("%d/%m/%Y") if ts else "N/A"
            from_a = (e.get("from_addr") or "")[:25]
            to_a = (e.get("to_addr") or "")[:25]
            amt = float(e.get("amount") or 0)
            to_entity = e.get("to_entity") or ""
            hops_table.append(f"{hop},{txid},{fecha},{from_a},{to_a},{amt:.4f},{to_entity}")
        hops_csv = "\n".join(hops_table)

        case_lines = [f"Direccion analizada: {address}", f"Red: {self.chain_name} ({self.unit})"]
        if case_data:
            for k, v in case_data.items():
                if v:
                    case_lines.append(f"{k}: {v}")
        case_section = "\n".join(case_lines)

        risk_section = (
            f"PUNTUACION TOTAL: {risk['total']}/100 — NIVEL: {risk['level']}\n"
            f"  Sub-puntuacion exposicion a contrapartes: {risk['exposure_score']}/100\n"
            f"  Sub-puntuacion cribado de sanciones: {risk['sanctions_score']}/100\n"
            f"  Sub-puntuacion tipologias detectadas: {risk['typology_score']}/100\n"
            f"Mixing detectado: {mixing_analysis.get('is_mixing')} (confianza {mixing_analysis.get('confidence', 0):.2f}) — indicadores: {', '.join(mixing_analysis.get('indicators', [])) or 'ninguno'}\n"
            f"Peeling chain detectado: {peeling_analysis.get('is_peeling_chain')} (longitud maxima {peeling_analysis.get('chain_length', 0)})"
        )

        # 8. Build prompt
        prompt = f"""Eres un analista de compliance/AML especializado en activos virtuales. Genera un informe de auditoria de compliance (NO un informe pericial judicial) para el departamento de cumplimiento normativo de un sujeto obligado.

DATOS DEL CASO:
{case_section}

PUNTUACION DE RIESGO (calculada deterministicamente a partir de datos on-chain, NO la inventes ni la cambies, solo explicala):
{risk_section}

EXPOSICION A CONTRAPARTES POR VOLUMEN:
{exposure_lines}

TOTALES:
Total recibido: {total_in:.4f} {self.unit}
Total enviado: {total_out:.4f} {self.unit}
Direcciones unicas relacionadas: {unique_addrs}

TABLA DE HOPS (HOP,HASH,FECHA,ORIGEN,DESTINO,CANTIDAD,ENTIDAD_DESTINO):
{hops_csv}

TRANSACCIONES (resumen):
{resumen}

SANCIONES (detalle):
{json.dumps(sanctions_result, indent=2, ensure_ascii=False)}

ESTRUCTURA QUE DEBES SEGUIR:
{estructura}

INSTRUCCIONES:
1. Genera SOLO el informe completo, sin notas ni explicaciones fuera del informe.
2. Sigue la estructura de secciones indicada.
3. USA la puntuacion de riesgo y el nivel proporcionados arriba tal cual — no calcules ni inventes otra puntuacion.
4. Rellena los datos reales del analisis. Si falta un dato, indica "No disponible", no inventes.
5. En la seccion de recomendacion de compliance, elige UNA recomendacion coherente con el nivel de riesgo calculado y justifica brevemente.
6. Usa lenguaje formal propio de un informe de auditoria de cumplimiento normativo (AML/CFT), no lenguaje judicial/pericial.
7. NO incluyas ningun texto fuera del informe (no pienses en voz alta)."""

        # 9. Call AI
        old_model = self.ai_model
        if model != "llama3":
            self.ai_model = model
        try:
            compliance_narrative = self._call_ai_api(prompt, timeout=300)
        finally:
            if model != "llama3":
                self.ai_model = old_model

        if not compliance_narrative:
            compliance_narrative = "No se pudo generar el informe de compliance. Verifique que el proveedor AI este disponible."

        # 10. Generate transaction graph HTML
        graph_html = self.generate_transaction_graph_html(address, limit=100)

        # 11. Generate report folder
        reporter = EnhancedForensicReporter(output_dir="reports", chain=self.chain)
        result = reporter.generate_report_folder(
            address=address,
            edges=edges,
            ollama_narrative=compliance_narrative,
            transaction_graph_html=graph_html,
            filters=filters,
            sanctions=sanctions_result,
        )
        result["risk_score"] = risk
        result["compliance_report"] = True

        self.log("info", f"Compliance report generated: {result.get('folder')} (risk={risk['level']} {risk['total']})")
        return result