"""
Create Proper Task 9 Runtime Config
"""
import json
from pathlib import Path
import hashlib
from datetime import datetime

def create_proper_runtime_config():
    """Create runtime config matching the working format."""
    
    config = {
        "schema_version": "task9_runtime_config.v1",
        "runtime_config_id": "task9-runtime-2026-08-31-r1",
        "runtime_config_version": "1",
        "canonical_config": {
            "runtime_config_id": "task9-runtime-2026-08-31-r1",
            "runtime_config_version": "1",
            "schema_version": "task9_runtime_config.v1",
            "execution_mode": "PAPER",
            "broker_order_submission": False,
            "live_execution_eligible": False,
            "campaign_id": "task9-live-certification-2026-08-18-r2",
            "market_date": "2026-08-31",
            "official_run_id": "task9-live-20260831-r1",
            "authoritative_persistence_root": "data/task9",
            "campaign_registry_location": "data/task9/campaign_registry",
            "certification_registry_root": "data/task9/certification_registry",
            "dashboard_publication_location": "data/task9/dashboard",
            "official_root": "data/task9/official",
            "available_capital": 10000.0,
            "trade_risk_fraction": 0.02,
            "maximum_quantity": 10,
            "maximum_lots": 3,
            "maximum_daily_loss_fraction": 0.05,
            "maximum_spread_fraction": 0.1,
            "parent_cycle_cadence_seconds": 60.0,
            "collector_heartbeat_seconds": 5.0,
            "market_quote_max_age_seconds": 300.0,
            "option_quote_max_age_seconds": 300.0,
            "instrument_master_max_age_seconds": 86400.0,
            "timezone": "Asia/Kolkata",
            "run_classification": "OFFICIAL_CERTIFICATION",
            "emergency_halt_enabled": False,
            "emergency_halt_reason": None,
            "policy_references": {
                "canonical_directional": "directional.v1",
                "session": "session.v1",
                "risk": "risk.v1",
                "contract_selection": "contract-selection.v1",
                "lifecycle": "lifecycle.v1",
                "counting": "counting.v1",
                "failure_disposition": "failure-disposition.v1",
                "contract_spread": "spread.v1",
                "liquidity": "liquidity.v1",
                "minimum_risk_reward": "rr.v1",
                "stop_target": "stop-target.v1",
                "portfolio_concurrency": "portfolio.v1"
            },
            "markets": [
                {
                    "market": "NIFTY",
                    "exchange": "NSE",
                    "option_exchange": "NFO",
                    "provider_market_name": "Nifty 50",
                    "spot_token": "99926000"
                },
                {
                    "market": "SENSEX",
                    "exchange": "BSE",
                    "option_exchange": "BFO",
                    "provider_market_name": "SENSEX",
                    "spot_token": "99919000"
                }
            ],
            "provider_features": {
                "angel_spot": "ENABLED_REQUIRED",
                "angel_option_full": "ENABLED_REQUIRED",
                "angel_greeks": "CAPABILITY_AWARE",
                "india_vix": "ENABLED_OPTIONAL",
                "events": "PROVIDER_NOT_SELECTED",
                "fii_dii": "PROVIDER_NOT_SELECTED",
                "global": "PROVIDER_NOT_SELECTED",
                "market_breadth": "PROVIDER_NOT_SELECTED",
                "news": "PROVIDER_NOT_SELECTED",
                "llm": "OPTIONAL_FUTURE"
            }
        }
    }
    
    # Ensure directory exists
    Path('data/task9/runtime-config-snapshots').mkdir(parents=True, exist_ok=True)
    
    # Generate filename with hash matching existing pattern
    config_string = json.dumps(config, sort_keys=True)
    hash_value = hashlib.sha256(config_string.encode()).hexdigest()
    filename = f'task9-runtime-config-{hash_value}.json'
    filepath = Path('data/task9/runtime-config-snapshots') / filename
    
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Also update the content_sha256 field
    config['content_sha256'] = hash_value
    config['snapshot_id'] = f'task9-runtime-config-{hash_value}'
    
    # Save again with updated fields
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f'✅ Proper runtime config created: {filename}')
    print(f'   Config ID: {config["runtime_config_id"]}')
    print(f'   Version: {config["runtime_config_version"]}')
    print(f'   Execution Mode: {config["canonical_config"]["execution_mode"]}')
    print(f'   Broker Submission: {config["canonical_config"]["broker_order_submission"]}')
    print(f'   Path: {filepath}')
    
    return config

def create_campaign_registry():
    """Create campaign registry matching the config."""
    
    campaign = {
        'campaign_id': 'task9-live-certification-2026-08-18-r2',
        'market_date': '2026-08-31',
        'official_run_id': 'task9-live-20260831-r1',
        'runtime_config_id': 'task9-runtime-2026-08-31-r1',
        'runtime_config_version': '1',
        'created_at': '2026-08-31T00:00:00',
        'status': 'active',
        'markets': ['NIFTY', 'SENSEX'],
        'target_trades': 100,
        'execution_mode': 'PAPER',
        'broker_order_submission': False,
        'live_execution_eligible': False
    }
    
    Path('data/task9').mkdir(parents=True, exist_ok=True)
    
    with open('data/task9/campaign-registry.json', 'w') as f:
        json.dump(campaign, f, indent=2)
    
    print('✅ Campaign registry created')
    print(f'   Campaign ID: {campaign["campaign_id"]}')
    print(f'   Runtime Config: {campaign["runtime_config_id"]}')
    
    return campaign

if __name__ == '__main__':
    create_proper_runtime_config()
    create_campaign_registry()
    print('\n✅ Setup complete!')
