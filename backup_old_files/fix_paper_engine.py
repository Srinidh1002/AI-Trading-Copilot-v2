import re

file_path = "services/trading/paper_engine.py"

with open(file_path, "r") as f:
    content = f.read()

# Find the __init__ method
pattern = r'(def __init__\(self, config: Optional\[Dict\] = None\):.*?)(?=\n    def run\(\))'
match = re.search(pattern, content, re.DOTALL)

if match:
    old = match.group(0)
    
    # Build new __init__ with correct order
    new = '''    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        logging.basicConfig(level=logging.INFO)
        self.logger.setLevel(logging.INFO)
        
        pipeline_config = self.config.get("pipeline_config", {})
        health_config = self.config.get("health_config", {})
        target_config = self.config.get("target_config", {})
        management_config = self.config.get("management_config", {})
        
        self.decision_pipeline = DecisionPipeline(pipeline_config)
        self.health_monitor = PredictionHealthMonitor(health_config)
        self.target_tracker = TargetTracker(target_config)
        self.trade_manager = TradeManager(management_config)
        
        self.learning_engine = AdaptiveLearningEngine(max_history=500)
        
        # Set mode and markets FIRST
        self.mode = self.config.get("mode", "replay")
        self.days = self.config.get("days", 30)
        self.markets = self.config.get("markets", ["NIFTY", "SENSEX"])
        
        # Now certification can use markets
        self.certification = CertificationEngine({
            "target_trades": 100,
            "markets": self.markets,
            "persist_path": "data/certification"
        })
        
        self.active_trades: Dict[str, PaperTrade] = {}
        self.closed_trades: List[PaperTrade] = []
        self.stats: Dict[str, TradingStats] = {}
        
        self.broker_order_submission = False
        self.live_execution_eligible = False
        
        self.persist_path = Path(self.config.get("persist_path", "data/paper_trades"))
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("PaperTradingEngine initialized (PAPER ONLY - NO BROKER ORDERS)")
        self.logger.info(f"Mode: {self.mode}, Markets: {self.markets}, Days: {self.days}")'''
    
    content = content.replace(old, new)
    
    with open(file_path, "w") as f:
        f.write(content)
    
    print("✅ Fixed paper_engine.py successfully!")
else:
    print("❌ Could not find __init__ method")
