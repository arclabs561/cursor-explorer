from cursor_explorer import vector as vectmod
from cursor_explorer import embeddings as embmod


def test_cosine_and_topk_and_l2():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 1.0, 0.0]
    c = [0.0, 1.0, 0.0]
    # cos similarity sanity
    assert abs(vectmod.cosine_similarity(a, a) - 1.0) < 1e-6
    assert vectmod.cosine_similarity(a, c) < 0.1
    # topk ordering
    scored = vectmod.topk(a, [a, b, c], 2)
    assert scored[0][0] == 0 and len(scored) == 2
    # l2 normalize
    v = embmod.l2_normalize([3.0, 4.0])
    assert abs(v[0]**2 + v[1]**2 - 1.0) < 1e-6
    v0 = embmod.l2_normalize([0.0, 0.0])
    assert v0 == [0.0, 0.0]


