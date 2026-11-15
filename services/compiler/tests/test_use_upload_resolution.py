"""CAL-61: an Image block left on automatic uses an attached photo when it feeds image-to-video
or 3D, which is what makes projects saved before the setting existed work."""

from __future__ import annotations


def _starter(tid):
    from calypr_compiler.templates import STARTERS

    return next(s for s in STARTERS if s.id == tid).model_copy(deep=True)


def _image_cfg(graph):
    return next(n.config for n in graph.nodes if n.type == "image")


def test_automatic_resolves_from_the_wiring():
    """Unset → on when the Image block feeds image-to-video or 3D, off when it doesn't."""
    from calypr_nodes import resolve_use_upload

    for tid, want in (
        ("tpl-image-to-video", True),
        ("tpl-image-to-3d", True),
        ("tpl-image-generation", False),
        ("tpl-street-photography", False),
    ):
        g = _starter(tid)
        for n in g.nodes:
            if n.type == "image":
                n.config = {k: v for k, v in n.config.items() if k != "use_upload"}
        assert _image_cfg(resolve_use_upload(g))["use_upload"] is want, tid
        assert "use_upload" not in _image_cfg(g), "the input graph is not mutated"


def test_automatic_never_overrides_an_explicit_choice():
    from calypr_nodes import resolve_use_upload

    g = _starter("tpl-image-to-video")
    for n in g.nodes:
        if n.type == "image":
            n.config = {**n.config, "use_upload": False}
    assert _image_cfg(resolve_use_upload(g))["use_upload"] is False
