from fidus_lab.overlay import NullOverlay, best_overlay


def test_null_overlay_records_calls():
    o = NullOverlay()
    o.set_confidence(72, "Identity")
    o.clear()
    assert o.calls == [("set", 72, "Identity"), ("clear", 0, "")]


def test_best_overlay_never_raises():
    # Whatever the environment, driving the overlay must not throw.
    o = best_overlay()
    o.set_confidence(80)
    o.clear()
