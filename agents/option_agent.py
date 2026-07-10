from models.recommendation import Recommendation


class OptionAgent:

    def analyse(self):

        return Recommendation(

            action="WAIT",

            confidence=0,

            strategy="None",

            entry=0,

            stop_loss=0,

            target1=0,

            target2=0,

            reason=[
                "AI Engine not connected."
            ]
        )