import sys
sys.path.append('src')
from target_focused_bot import UnifiedTradingBot
import time
from datetime import datetime

bot = UnifiedTradingBot('NIFTY')
bot.load_state()
bot.connect_with_retry()
bot.load_instruments()

bot.MARKET_OPEN = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
bot.FINAL_EXIT = datetime.now().replace(hour=15, minute=28, second=0, microsecond=0)

print('Market open:', bot.is_market_open())
print('NIFTY entered=', bot.current_session, ' cert=', bot.certification_counter, '/100')  # R6_cert_counter

attempts = 0
max_attempts = 1000  # safety valve only; is_market_open() is the real stop  # Max attempts per day

while bot.is_market_open() and bot.certification_counter < 100 and attempts < max_attempts:  # R6_cert_counter
    attempts += 1
    print()
    print('=' * 40)
    print('Attempt', attempts, '| Cert:', bot.certification_counter, '/100 | Entered:', bot.current_session)  # R6_cert_counter
    print('=' * 40)
    
    result = bot.run_single_session()
    
    if result:
        bot.current_session += 1  # Only count actual trades
        bot.session_history.append(result)
        bot.sessions_completed_today += 1
        print(f'>>> TRADE TAKEN - Entered={bot.current_session} Cert={bot.certification_counter}/100')  # R6_cert_counter
    else:
        print('>>> SKIPPED - not counted toward 100')
    
    bot.save_state()
    
    if bot.is_market_open() and bot.certification_counter < 100 and attempts < max_attempts:  # R6_cert_counter
        time.sleep(30)
    else:
        break

print()
print('Daily Summary:')
print('  Entered:', bot.current_session, '| Cert:', bot.certification_counter, '/100')  # R6_cert_counter
print('  Attempts:', attempts)
bot.show_daily_summary()
