from behavior_machine.core import Machine, State, StateStatus, Board
from behavior_machine.library import SequentialState, PrintState, IdleState, WaitState, SetFlowState


def test_sequential_state(capsys):

    ps1 = PrintState("Print1")
    ps2 = PrintState("Print2")
    ps3 = PrintState("Print3")
    es = IdleState("endState")

    sm = SequentialState(children=[ps2, ps3])
    sm.add_children(ps1)

    sm.add_transition_on_success(es)
    exe = Machine(sm, end_state_ids=["endState"], rate=10)
    exe.run()

    assert capsys.readouterr().out == "Print2\nPrint3\nPrint1\n"


def test_nested_sequential_state(capsys):
    ps1 = PrintState("Print1")
    ps2 = PrintState("Print2")
    ps3 = PrintState("Print3")
    ps4 = PrintState("Print4")
    es = IdleState("endState")

    sm = SequentialState(children=[ps3, ps2])
    sm2 = SequentialState(children=[ps4, sm, ps1])
    sm2.add_transition_on_success(es)
    mach = Machine(sm2, end_state_ids=['endState'], rate=10)
    mach.run()

    assert capsys.readouterr().out == "Print4\nPrint3\nPrint2\nPrint1\n"


def test_exception_in_sequential_state(capsys):

    error_text = "IndexErrorInTestEXCEPTION"

    class RaiseExceptionState(State):
        def execute(self, board):
            raise IndexError(error_text)

    ps1 = PrintState("Print1")
    ps2 = PrintState("Print2")
    ps3 = PrintState("Print3")
    rs = RaiseExceptionState("rs1")
    es = IdleState("endState")

    sm = SequentialState(children=[ps2, ps3, rs], name="sm")
    sm.add_children(ps1)

    sm.add_transition_on_success(es)
    exe = Machine(sm, name="xe", end_state_ids=["endState"])
    exe.run()

    assert capsys.readouterr().out == "Print2\nPrint3\n"
    assert str(exe._internal_exception) == error_text
    assert exe._exception_raised_state_name == "xe.sm.rs1"


def test_interruption_in_sequential_state(capsys):

    ws1 = WaitState(0.1)
    ws2 = WaitState(0.1)
    ps1 = PrintState("Print1")

    sm = SequentialState(children=[ws1, ws2, ps1])
    sm.start(None)
    sm.wait(0.15)
    sm.interrupt()

    assert capsys.readouterr().out == ""
    assert sm.check_status(StateStatus.INTERRUPTED)
    assert ws2.check_status(StateStatus.INTERRUPTED)
    assert ws1.check_status(StateStatus.SUCCESS)
    assert ps1.check_status(StateStatus.NOT_RUNNING)
    assert not sm._run_thread.is_alive()
    assert not ws1._run_thread.is_alive()
    assert not ws2._run_thread.is_alive()


def test_sequential_state_success(capsys):
    ps1 = PrintState("Print1")
    ps2 = PrintState("Print2")
    es = IdleState("es")
    seqs = SequentialState(children=[ps1, ps2])
    seqs.add_transition_on_success(es)
    exe = Machine(seqs, end_state_ids=['es'])
    exe.run()

    assert capsys.readouterr().out == "Print1\nPrint2\n"
    assert exe.is_end()
    assert exe._curr_state == es
    assert seqs._status == StateStatus.SUCCESS
    assert ps1._status == StateStatus.SUCCESS
    assert ps2._status == StateStatus.SUCCESS


def test_interruption_in_machines_with_sequential_state(capsys):

    ws1 = WaitState(0.2, name="ws1")
    ws2 = WaitState(0.2, name="ws2")
    ps1 = PrintState("Print1")
    es = IdleState("es")
    iss = IdleState("iss")
    sm = SequentialState(children=[ws1, ws2, ps1])
    sm.add_transition_on_success(es)
    sm.add_transition(lambda s, b: s._curr_child.check_name('ws2'), iss)

    exe = Machine(sm, end_state_ids=["es", "iss"], rate=100)
    exe.run()
    assert exe._exception_raised_state_name == ""
    assert exe._internal_exception is None
    assert exe._status == StateStatus.SUCCESS
    assert not exe._run_thread.is_alive()
    assert exe._curr_state._name == 'iss'
    assert exe.is_end()
    assert capsys.readouterr().out == ""
    assert not sm._run_thread.is_alive()
    assert not ws1._run_thread.is_alive()
    assert not ws2._run_thread.is_alive()
    assert sm._status == StateStatus.INTERRUPTED
    assert ws2._status == StateStatus.INTERRUPTED
    assert ws1._status == StateStatus.SUCCESS
    assert ps1._status == StateStatus.NOT_RUNNING
    assert ws2.check_status(StateStatus.INTERRUPTED)
    assert ws1.check_status(StateStatus.SUCCESS)


def test_sequential_debug_info():
    w1 = WaitState(1, name="w1")
    w2 = WaitState(1, name="w2")
    seqs = SequentialState(children=[w1, w2], name="seqs")
    seqs.start(None)
    seqs.wait(0.1)
    info = seqs.get_debug_info()
    assert info['name'] == 'seqs'
    assert len(info['children']) == 2
    assert info['children'][0]['name'] == 'w1'
    assert info['children'][0]['status'] == StateStatus.RUNNING
    assert info['children'][1]['name'] == 'w2'
    assert info['children'][1]['status'] == StateStatus.NOT_RUNNING
    seqs.wait(1)
    info = seqs.get_debug_info()
    assert info['children'][0]['status'] == StateStatus.SUCCESS
    assert info['children'][1]['status'] == StateStatus.RUNNING
    seqs.wait()


def test_repeat_sequential_state():
    w1 = WaitState(0.3)
    w2 = WaitState(0.3)
    seqs = SequentialState(children=[w1, w2])
    seqs.start(None)
    seqs.wait(1)
    info = seqs.get_debug_info()
    assert info['children'][0]['status'] == StateStatus.SUCCESS
    assert info['children'][1]['status'] == StateStatus.SUCCESS
    seqs.start(None)
    seqs.wait(0.1)
    info = seqs.get_debug_info()
    assert info['children'][0]['status'] == StateStatus.RUNNING
    assert info['children'][1]['status'] == StateStatus.NOT_RUNNING


def test_sequential_state_flow(capsys):

    flow_in_text = "test_sequential_state_flow"
    first_time = True

    class PreState(State):
        def execute(self, board: Board) -> StateStatus:
            self.flow_out = flow_in_text

    class ReceiveState(State):
        def execute(self, board):
            nonlocal first_time
            if first_time:
                assert self.flow_in == flow_in_text
                first_time = False
                print("one")
                return StateStatus.SUCCESS
            else:
                assert self.flow_in is None
                print("two")
                return StateStatus.FAILED

    ps = PreState("pre")
    ws = WaitState(0.1)
    rs = ReceiveState("rs")
    es = IdleState("es")
    seqs = SequentialState(children=[rs, ws])

    ps.add_transition_on_complete(seqs)
    seqs.add_transition_on_success(seqs)
    seqs.add_transition_on_failed(es)

    me = Machine(ps, end_state_ids=['es'])
    me.start(None)
    me.wait()
    assert capsys.readouterr().out == "one\ntwo\n"


def test_sequential_state_interrupt_before_start():
    seq = SequentialState(children=[
        WaitState(1),
        WaitState(2)
    ])
    seq.interrupt()


def test_sequential_state_tick_race_condition():
    seq = SequentialState(children=[
        WaitState(1),
    ])
    seq.start(None, None)
    assert seq.tick(None) == seq
    seq.wait()


def test_sequence_state_flow():

    class FailedState(State):
        def execute(self, board: Board) -> StateStatus:
            self.flow_out = "Failed"
            return StateStatus.FAILED

    selector = SequentialState(children=[
        SetFlowState("firstState"),
        FailedState("f1"),
        SetFlowState("secondState"),
    ])
    selector.start(None)
    selector.wait()
    assert selector.flow_out == "firstState"

    selector = SequentialState(children=[
        SetFlowState("firstState"),
        SetFlowState("secondState"),
    ])
    selector.start(None)
    selector.wait()
    assert selector.flow_out == "secondState"
