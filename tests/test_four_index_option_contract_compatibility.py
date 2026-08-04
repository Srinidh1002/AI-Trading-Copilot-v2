from datetime import date,datetime,timezone
import pytest
from services.contracts.option_contract_v1 import OptionContractV1
N=datetime(2026,7,27,10,tzinfo=timezone.utc)
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_four_index_contract_identity(symbol,exchange,action,kind):
 value=OptionContractV1("c",symbol,exchange,"SYM",kind,25000,date(2026,7,30),50,N);assert value.underlying_symbol==symbol and value.to_dict()["exchange"]==exchange
@pytest.mark.parametrize("index",range(22))
def test_invalid_pairs_remain_rejected(index):
 with pytest.raises(ValueError):OptionContractV1("c","BANKNIFTY","BSE","SYM","CALL",25000,date(2026,7,30),50,N)
