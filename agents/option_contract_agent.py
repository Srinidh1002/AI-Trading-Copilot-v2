from models.option_contract_state import (
    OptionContractState,
)

from services.option_contract_selector import (
    select_option_contract,
)


class OptionContractAgent:

    def analyse(
        self,
        contracts,
        direction,
        spot_price,
        **kwargs,
    ):
        result = select_option_contract(
            contracts=contracts,
            direction=direction,
            spot_price=spot_price,
            **kwargs,
        )

        return OptionContractState(
            selected=result["selected"],
            decision=result["decision"],
            symbol=result["symbol"],
            strike=result["strike"],
            option_type=result[
                "option_type"
            ],
            expiry=result["expiry"],
            premium=result["premium"],
            score=result["score"],
            reasons=result["reasons"],
        )