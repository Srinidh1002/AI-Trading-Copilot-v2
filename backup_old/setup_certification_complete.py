"""
Create Complete Runtime Config for Task 9 Certification
"""
import json
from datetime import datetime
from pathlib import Path
import hashlib

def create_complete_runtime_config():
    """Create runtime config with ALL required fields."""
    
    config = {
        # Core identity
        'runtime_config_id': 'task9-runtime-2026-08-31-r1',
        'runtime_config_version': 1,
        'created_at': datetime.now().isoformat(),
        
        # Execution mode - CRITICAL
        'execution_mode': 'PAPER',
        'broker_order_submission': False,
        'live_execution_eligible': False,
        
        # Campaign identity
        'campaign_id': 'task9-live-certification-2026-08-18-r2',
        'market_date': '2026-08-31',
        'official_run_id': 'task9-live-20260831-r1',
        
        # Persistence
        'authoritative_persistence_root': 'data/task9',
        
        # Capital and risk
        'available_capital': 10000.0,
        'trade_risk_fraction': 0.02,
        'maximum_quantity': 100,
        'maximum_daily_loss_fraction': 0.05,
        
        # Policy references
        'policy_references': {
            'canonical_directional': 'directional.v1',
            'session': 'session.v1',
            'risk': 'risk.v1',
            'contract_selection': 'contract-selection.v1',
            'lifecycle': 'lifecycle.v1',
            'counting': 'counting.v1',
            'failure_disposition': 'failure-disposition.v1',
            'contract_spread': 'spread.v1',
            'liquidity': 'liquidity.v1',
            'minimum_risk_reward': 'rr.v1',
            'stop_target': 'stop-target.v1',
            'portfolio_concurrency': 'portfolio.v1'
        },
        
        # Full config for snapshot
        'config': {
            'execution_mode': 'PAPER',
            'broker_order_submission': False,
            'live_execution_eligible': False,
            'campaign_id': 'task9-live-certification-2026-08-18-r2',
            'market_date': '2026-08-31',
            'official_run_id': 'task9-live-20260831-r1',
            'authoritative_persistence_root': 'data/task9',
            'available_capital': 10000.0,
            'trade_risk_fraction': 0.02,
            'maximum_quantity': 100,
            'maximum_daily_loss_fraction': 0.05,
            'cycle_interval_seconds': 60,
            'policy_references': {
                'canonical_directional': 'directional.v1',
                'session': 'session.v1',
                'risk': 'risk.v1',
                'contract_selection': 'contract-selection.v1',
                'lifecycle': 'lifecycle.v1',
                'counting': 'counting.v1',
                'failure_disposition': 'failure-disposition.v1',
                'contract_spread': 'spread.v1',
                'liquidity': 'liquidity.v1',
                'minimum_risk_reward': 'rr.v1',
                'stop_target': 'stop-target.v1',
                'portfolio_concurrency': 'portfolio.v1'
            }
        }
    }
    
    # Ensure directory exists
    Path('data/task9/runtime-config-snapshots').mkdir(parents=True, exist_ok=True)
    
    # Generate filename with hash
    config_string = json.dumps(config, sort_keys=True)
    hash_value = hashlib.sha256(config_string.encode()).hexdigest()
    filename = f'task9-runtime-config-{hash_value}.json'
    filepath = Path('data/task9/runtime-config-snapshots') / filename
    
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f'✅ Complete runtime config created: {filename}')
    print(f'   Config ID: {config["runtime_config_id"]}')
    print(f'   Version: {config["runtime_config_version"]}')
    print(f'   Execution Mode: {config["execution_mode"]}')
    print(f'   Broker Submission: {config["broker_order_submission"]}')
    print(f'   Path: {filepath}')
    
    return config

def create_campaign_registry():
    """Create campaign registry matching the config."""
    
    campaign = {
        'campaign_id': 'task9-live-certification-2026-08-18-r2',
        'market_date': '2026-08-31',
        'official_run_id': 'task9-live-20260831-r1',
        'runtime_config_id': 'task9-runtime-2026-08-31-r1',
        'runtime_config_version': 1,
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
    create_complete_runtime_config()
    create_campaign_registry()
    print('\n✅ Setup complete!')
