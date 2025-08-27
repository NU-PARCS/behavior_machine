from ..core import StateStatus, State


class PrintState(State):

    _text: str

    def __init__(self, text: str, name: str = ""):
        """Constructor for PrintState

        Parameters
        ----------
        name : str
            Name of the State, useful in Debugging.
        text : str
            Text to print on Screen
        """
        super().__init__(name=name)
        self._text = text

    def execute(self, board):
        print(self._text)
        return StateStatus.SUCCESS
