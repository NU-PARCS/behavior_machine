from behavior_machine.library import WaitState
import pytest
import time

from behavior_machine.core import State, StateStatus, Machine, Board


class PrintState(State):

    _text: str

    def __init__(self, text, name = ""):
        super().__init__(name)
        self._text = text

    def execute(self, board):
        print(self._text)
        return StateStatus.SUCCESS


class DummyState(State):
    def execute(self, board):
        return StateStatus.SUCCESS


def test_simple_machine(capsys):
    ps1 = PrintState("print1")
    ps2 = PrintState("print2", name="ps2")
    ps1.add_transition_on_success(ps2)
    exe = Machine(ps1, end_state_ids=["ps2"], rate=10)
    b = Board()
    exe.run(b)
    assert exe.is_end()
    assert capsys.readouterr().out == "print1\nprint2\n"


def test_transition_on_failed(capsys):

    class failedState(State):
        def execute(self, board):
            return StateStatus.FAILED

    fs = failedState()
    ps1 = PrintState("success", name="ps1")
    ps2 = PrintState("failed", name="ps2")
    fs.add_transition_on_success(ps1)
    fs.add_transition_on_failed(ps2)
    exe = Machine(fs, end_state_ids=["ps1", "ps2"], rate=10)
    exe.run(None)
    assert exe.is_end()
    assert exe._curr_state.check_name("ps2")
    assert capsys.readouterr().out == "failed\n"


def test_transition_on_complete(capsys):

    class NothingState(State):
        def execute(self, board):
            print("hello")

    ds1 = DummyState("d1")
    ns = NothingState("ns")
    ds2 = DummyState("ds2")

    ds1.add_transition_on_success(ns)
    ns.add_transition_on_complete(ds2)

    exe = Machine(ds1, end_state_ids=["ds2"], rate=10)
    exe.run(None)
    assert exe.is_end()
    assert exe._curr_state.check_name("ds2")
    assert capsys.readouterr().out == "hello\n"


def test_simple_machine2(capsys):
    ps1 = PrintState("print1", name="ps1")
    ps2 = PrintState("print2", name="ps2")
    ps3 = PrintState("print3", name="ps3")
    ps1.add_transition_on_success(ps2)
    ps2.add_transition_on_success(ps3)
    exe = Machine(ps1, rate=10)
    b = Board()
    exe.start(b, manual_exec=True)
    assert capsys.readouterr().out == "print1\n"
    exe.update(b, wait=True)
    assert capsys.readouterr().out == "print2\n"
    exe.update(b, wait=True)
    assert capsys.readouterr().out == "print3\n"


def test_chain_case():
    s1 = DummyState("s1")
    s2 = DummyState("s2")
    s1.add_transition_on_success(s2)
    s3 = DummyState("s3")
    s2.add_transition_on_success(s3)
    exe = Machine(s1, end_state_ids=["s3"], rate=10)
    b = Board()
    exe.start(b, manual_exec=True)
    exe.update(b, True)
    assert not exe.is_end()
    exe.update(b, True)
    assert exe.is_end()


def test_end_case():
    ps1 = PrintState("ps1", "Hello World")
    es = DummyState("endState")
    ps1.add_transition_on_success(es)
    exe = Machine(ps1, end_state_ids=["endState"], rate=10)
    exe.run()
    assert exe.is_end()


# This test checks if machine is completed (is_end())
# only after the endState finish execution.
def test_end_case_delay(capsys):
    ps1 = PrintState("Hello World")

    class EndState(State):
        def execute(self, board):
            time.sleep(0.5)
            print('completed')
            return StateStatus.SUCCESS
    es = EndState('endState')
    ps1.add_transition_on_success(es)
    exe = Machine(ps1, end_state_ids=["endState"], rate=10)
    exe.run()
    assert exe.is_end()
    assert capsys.readouterr().out == "Hello World\ncompleted\n"


def test_machine_rate_slow():
    w1 = WaitState(0.1) # execute at second 0
    w2 = WaitState(0.1) # execute at second 2
    es = DummyState("endState")  # execute at second 4
    w1.add_transition_on_success(w2)
    w2.add_transition_on_success(es)
    exe = Machine(w1, end_state_ids=["endState"], rate=0.5)
    start_time = time.time()
    exe.run()
    duration = time.time() - start_time
    assert pytest.approx(duration, rel=1e-2) == 4
    assert w1._status == StateStatus.SUCCESS
    assert w2._status == StateStatus.SUCCESS


def test_machine_rate_fast():
    w1 = WaitState(0.05) # execute at second 0
    w2 = WaitState(0.05) # execute at second 0.1s
    es = DummyState("endState")  # execute at second 0.2
    w1.add_transition_on_success(w2)
    w2.add_transition_on_success(es)
    exe = Machine(w1, end_state_ids=["endState"], rate=10)
    start_time = time.time()
    exe.run()
    duration = time.time() - start_time
    assert pytest.approx(duration, abs=1e-2) == 0.2
    assert w1._status == StateStatus.SUCCESS
    assert w2._status == StateStatus.SUCCESS

def test_nested_machine(capsys):

    ps1 = PrintState("in mach1")
    ps15 = PrintState("in mach1 too")
    es = DummyState("endState")
    ps1.add_transition_on_success(ps15)
    ps15.add_transition_on_success(es)
    mach1 = Machine(ps1, end_state_ids=["endState"], rate=10)

    ps2 = PrintState("enter mach1")
    ps2.add_transition_on_success(mach1)
    ps3 = PrintState("leaving mach1")
    mach1.add_transition_on_success(ps3)
    es2 = DummyState("endState")
    ps3.add_transition_on_success(es2)

    mac2 = Machine(ps2, end_state_ids=["endState"], rate=10)
    mac2.run()

    assert capsys.readouterr().out == "enter mach1\nin mach1\nin mach1 too\nleaving mach1\n"


class RaiseExceptionState(State):

    def execute(self, board):
        raise InterruptedError("raiseException")


def test_machine_with_exception(capsys):

    ps1 = PrintState("p1")
    re1 = RaiseExceptionState('re1')
    ps2 = PrintState("p2")

    ps1.add_transition_on_success(re1)
    re1.add_transition_on_success(ps2)

    mac = Machine(ps1, name="mac", end_state_ids=["ps2"])
    mac.run()

    assert capsys.readouterr().out == 'p1\n'
    assert mac.check_status(StateStatus.EXCEPTION)
    assert str(mac._internal_exception) == "raiseException"
    assert mac._exception_raised_state_name == "mac.re1"


def test_machine_with_exception_in_transition(capsys):

    is1 = DummyState('d1')
    is2 = DummyState('d2')

    is1.add_transition(lambda s, b: s.unknown(), is2)

    mac = Machine(is1, ["is2"])
    mac.run()

    assert mac._status == StateStatus.EXCEPTION
    assert not mac._run_thread.is_alive()
    assert not is1._run_thread.is_alive()
    assert is2._run_thread is None  # Never reach is2


def test_machine_with_exception_in_transition_with_zombie_states(capsys):

    ws1 = WaitState(10)
    is2 = DummyState('d2')

    ws1.add_transition(lambda s, b: s.unknown(), is2)

    mac = Machine(ws1, ["is2"])
    mac.run()
    assert mac._status == StateStatus.EXCEPTION
    # this is an interrupted, because exception happen at higher level
    assert ws1._status == StateStatus.INTERRUPTED
    assert not mac._run_thread.is_alive()
    assert not ws1._run_thread.is_alive()
    assert is2._run_thread is None  # Never reach it


def test_debugging_machine(caplog):
    import logging
    logging.basicConfig(level=logging.DEBUG)
    caplog.set_level(logging.DEBUG)

    logger = logging.getLogger(__name__)

    s1 = WaitState(1.1, name='s1')
    s2 = DummyState('s2')
    s1.add_transition_on_success(s2)
    mac = Machine(s1, name="mac", end_state_ids=["s2"], debug=True, rate=1, logger=logger)
    mac.run()
    assert mac.is_end()
    assert len(caplog.records) == 3
    assert caplog.records[0].message == "[Base] mac(Machine) -- RUNNING\n  -> s1(WaitState) -- RUNNING" # This is at t=0
    assert caplog.records[1].message == "[Base] mac(Machine) -- RUNNING\n  -> s1(WaitState) -- RUNNING" # This is at t=1 
    assert caplog.records[2].message == "[Base] mac(Machine) -- RUNNING\n  -> s2(DummyState) -- SUCCESS" # At the end


def test_interrupt_machine(capsys):
    s1 = WaitState(1.1)
    s2 = DummyState('s2')
    s1.add_transition_on_success(s2)
    mac = Machine(s1, ["s2"], debug=True, rate=1)
    mac.start(None)
    assert mac.interrupt()

def test_flow_into_machine(capsys):

    test_phrase = "test_flow_into_machine"

    class OnlyState(State):
        def execute(self, board):
            assert self.flow_in == test_phrase
            print("only-state")
            return StateStatus.SUCCESS

    os = OnlyState(name="only")
    mac = Machine(os, end_state_ids=["only"])
    mac.run(flow_in=test_phrase)
    assert mac.is_end()
    assert capsys.readouterr().out == "only-state\n"


def test_repeat_node_in_machine():

    counter = 0

    class CounterState(State):
        def execute(self, board: Board) -> StateStatus:
            nonlocal counter
            counter += 1
            time.sleep(0.1)
            return StateStatus.SUCCESS

    ds1 = CounterState("ds1")
    ds2 = CounterState("ds2")
    ds3 = CounterState("ds3")
    ds4 = CounterState("ds4")
    ds5 = CounterState("ds5")

    ds1.add_transition_on_success(ds2)
    ds2.add_transition_on_success(ds3)
    ds3.add_transition_on_success(ds4)
    ds4.add_transition_on_success(ds5)
    ds5.add_transition_on_success(ds1)

    exe = Machine(ds1, rate=5)
    exe.start(None)
    for i in range(1, 6):
        time.sleep(1)
        assert counter == i*5
        assert exe._curr_state == ds5
    exe.interrupt()
    assert counter == (5 * 5)
