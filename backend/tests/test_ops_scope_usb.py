"""USB / 挂载类问题应判定为运维范围内。"""
from app.services.ops_scope import assess_ops_scope, is_procedural_knowledge_question


def test_usb_umount_device_busy_in_scope():
    q = "卸载 USB 存储设备时提示 'Device is busy'，怎么办？"
    scope, reason = assess_ops_scope(q)
    assert scope == "in_scope", reason
    assert is_procedural_knowledge_question(q)


def test_cooking_still_out_of_scope():
    scope, _ = assess_ops_scope("怎么做红烧肉？")
    assert scope == "out_of_scope"
